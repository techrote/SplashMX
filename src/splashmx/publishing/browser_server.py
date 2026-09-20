"""Thin browser adapter for the SMX-036 generic player.

The browser surface owns presentation only.  Immutable publication parsing,
closure verification, compatibility and capability policy stay in GenericPlayer
and must complete before this adapter reports a creation active.
"""
from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .generic import (
    CreationRevisionId,
    GenericPlayer,
    HostedReleaseId,
    HostedReleaseStore,
    PreparedCreation,
    PublicationError,
)

WEB_ROOT = Path(__file__).with_name("web")
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_MAX_REQUEST_BYTES = 64 * 1024


class BrowserPlayerBridge:
    """Browser-facing coordinator over immutable release storage and GenericPlayer."""

    def __init__(self, store: HostedReleaseStore, player: GenericPlayer | None = None):
        self.store = store
        self.player = player or GenericPlayer()
        self._active_summary: dict[str, Any] | None = None

    def state(self) -> dict[str, Any]:
        return {"active": None if self._active_summary is None else dict(self._active_summary)}

    @staticmethod
    def _summary(prepared: PreparedCreation) -> dict[str, Any]:
        return {
            "creation_revision_id": str(prepared.manifest.creation_revision_id),
            "creation_id": str(prepared.manifest.creation_id),
            "project_id": str(prepared.manifest.project_id),
            "project_revision_id": str(prepared.manifest.project_revision_id),
            "player_profile": prepared.manifest.player_profile,
        }

    def load(self, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise PublicationError("publication.invalid_browser_request", "Player request must be an object")
        mode = request.get("mode", "alias")
        value = request.get("value")
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 1024:
            raise PublicationError("publication.invalid_browser_request", "Player locator must be bounded text")
        if mode == "alias":
            locator: CreationRevisionId | HostedReleaseId | str = value
        elif mode == "creation_revision":
            locator = CreationRevisionId(value)
        elif mode == "hosted_release":
            locator = HostedReleaseId(value)
        else:
            raise PublicationError("publication.invalid_browser_request", "Unknown player locator role")

        # load_hosted performs resolve -> prepare -> activate.  The callback is
        # therefore unreachable for malformed/incompatible/tampered content.
        summary = self.player.load_hosted(self.store, locator, self._summary)
        self._active_summary = dict(summary)
        return {"ok": True, "active": dict(summary)}


def make_handler(bridge: BrowserPlayerBridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SplashMXGenericPlayer/1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state":
                self._json(HTTPStatus.OK, {"ok": True, "state": bridge.state()})
                return
            static = _STATIC.get(path)
            if static is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "publication.not_found", "message": "Player resource not found"}})
                return
            filename, mime = static
            body = (WEB_ROOT / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/load":
                self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "publication.not_found", "message": "Player action not found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 0 or length > _MAX_REQUEST_BYTES:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "publication.request_too_large", "message": "Player request is too large"}})
                return
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                response = bridge.load(request)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "publication.invalid_browser_request", "message": "Player request could not be read"}, "state": bridge.state()})
                return
            except PublicationError as exc:
                self._json(HTTPStatus.CONFLICT, {"error": {"code": exc.code, "message": str(exc)}, "state": bridge.state()})
                return
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "publication.invalid_browser_request", "message": str(exc)}, "state": bridge.state()})
                return
            self._json(HTTPStatus.OK, response)

    return Handler


def run_server(host: str, port: int, store: HostedReleaseStore, *, player: GenericPlayer | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(BrowserPlayerBridge(store, player)))


__all__ = ["BrowserPlayerBridge", "make_handler", "run_server"]
