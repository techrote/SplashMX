"""Thin same-origin browser bridge for the SMX-032 authoring shell.

The HTTP layer owns no document semantics.  Browser actions are decoded, checked and
forwarded to :mod:`splashmx.editor.authoring`, which in turn publishes only through
the production canonical transaction boundary.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from splashmx.canonical.core import SemanticError
from splashmx.canonical.serialization import SerializationError
from splashmx.editor.authoring import AuthoringError, AuthoringSession


WEB_ROOT = Path(__file__).with_name("web")
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
_MAX_REQUEST_BYTES = 8 * 1024 * 1024


class BrowserBridge:
    """Decode bounded JSON actions and delegate to one production authoring session."""

    def __init__(self, session: AuthoringSession | None = None):
        self.session = session or AuthoringSession.blank()

    def state(self) -> dict[str, Any]:
        return self.session.snapshot()

    def apply(self, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict) or not isinstance(request.get("action"), str):
            raise AuthoringError("authoring.invalid_request", "Choose a supported authoring action.")
        action = request["action"]
        data = request.get("data", {})
        if not isinstance(data, dict):
            raise AuthoringError("authoring.invalid_request", "Authoring action data must be an object.")
        result: Any = None
        if action == "createThing":
            result = str(
                self.session.create_thing(
                    label=_string(data, "label"),
                    thing_id=_optional_string(data, "thing_id"),
                    authored_state=_mapping(data.get("authored_state", {}), "authored_state"),
                )
            )
        elif action == "addPort":
            result = str(
                self.session.add_port(
                    _string(data, "thing_id"),
                    port_id=_string(data, "port_id"),
                    name=_string(data, "name"),
                    kind=_string(data, "kind"),
                    direction=_string(data, "direction"),
                )
            )
        elif action == "group":
            result = str(
                self.session.group_things(
                    _string_list(data, "members"),
                    label=str(data.get("label", "Group")),
                    group_id=_optional_string(data, "group_id"),
                )
            )
        elif action == "makeReusable":
            result = str(
                self.session.make_reusable(
                    _string(data, "root_id"),
                    definition_id=_optional_string(data, "definition_id"),
                )
            )
        elif action == "instantiateReusable":
            result = str(self.session.instantiate_reusable(_string(data, "definition_id")))
        elif action in {"attachRule", "attachBehaviour"}:
            method = self.session.attach_rule if action == "attachRule" else self.session.attach_behaviour
            actions = data.get("actions")
            if actions is not None and not isinstance(actions, list):
                raise AuthoringError("authoring.invalid_behaviour", "Actions must be a list.")
            result = str(
                method(
                    _string(data, "thing_id"),
                    attachment_id=_optional_string(data, "attachment_id"),
                    event=str(data.get("event", "activate")),
                    actions=actions,
                )
            )
        elif action == "connect":
            result = str(
                self.session.connect(
                    source_thing_id=_string(data, "source_thing_id"),
                    source_port_id=_string(data, "source_port_id"),
                    target_thing_id=_string(data, "target_thing_id"),
                    target_port_id=_string(data, "target_port_id"),
                    connection_id=_optional_string(data, "connection_id"),
                )
            )
        elif action == "timeline":
            keyframes = data.get("keyframes", [])
            if not isinstance(keyframes, list):
                raise AuthoringError("authoring.invalid_timeline", "Timeline keyframes must be a list.")
            result = self.session.add_timeline_track(
                _string(data, "thing_id"),
                property_name=_string(data, "property"),
                keyframes=keyframes,
                track_id=_optional_string(data, "track_id"),
            )
        elif action == "select":
            self.session.select(_string_list(data, "thing_ids"))
        elif action == "inspect":
            self.session.set_inspect_open(bool(data.get("open", False)))
        elif action == "importAsset":
            encoded = _string(data, "content_base64")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise AuthoringError("authoring.invalid_import", "The selected source file could not be read.") from exc
            thing_id, asset_id = self.session.import_asset_thing(
                content=content,
                source_name=_string(data, "source_name"),
                media_type=_string(data, "media_type"),
                media_semantics=_mapping(data.get("media_semantics"), "media_semantics"),
                provenance=_mapping(data.get("provenance"), "provenance"),
                licence_attribution=_mapping(data.get("licence_attribution"), "licence_attribution"),
                derivation_lineage=_mapping_list(data.get("derivation_lineage"), "derivation_lineage"),
                asset_id=_optional_string(data, "asset_id"),
                thing_id=_optional_string(data, "thing_id"),
                label=_optional_string(data, "label"),
            )
            result = {"thing_id": str(thing_id), "asset_id": str(asset_id)}
        else:
            raise AuthoringError("authoring.unknown_action", "Choose a supported authoring action.")
        return {"ok": True, "result": result, "state": self.state()}


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} is required.")
    return value


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} must be text.")
    return value


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} must be a list of Things.")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthoringError("authoring.invalid_request", f"{label.replace('_', ' ')} must be an object.")
    return value


def _mapping_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AuthoringError("authoring.invalid_request", f"{label.replace('_', ' ')} must be a list.")
    return value


def make_handler(bridge: BrowserBridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SplashMXAuthoring/1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
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

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/state":
                self._json(HTTPStatus.OK, {"ok": True, "state": bridge.state()})
                return
            static = _STATIC.get(path)
            if static is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That editor resource was not found."}})
                return
            filename, mime = static
            body = (WEB_ROOT / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/action":
                self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That editor action was not found."}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 0 or length > _MAX_REQUEST_BYTES:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "authoring.request_too_large", "message": "That authoring change is too large for one request."}})
                return
            try:
                body = self.rfile.read(length)
                request = json.loads(body.decode("utf-8"))
                response = bridge.apply(request)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "authoring.invalid_request", "message": "That authoring request could not be read."}})
                return
            except (AuthoringError, SemanticError, SerializationError) as exc:
                self._json(
                    HTTPStatus.CONFLICT,
                    {"error": {"code": getattr(exc, "code", "authoring.invalid_edit"), "message": str(exc)}},
                )
                return
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "authoring.invalid_request", "message": str(exc)}})
                return
            self._json(HTTPStatus.OK, response)

    return Handler


def run_server(host: str, port: int, *, project_id: str = "local-project") -> ThreadingHTTPServer:
    bridge = BrowserBridge(AuthoringSession.blank(project_id))
    return ThreadingHTTPServer((host, port), make_handler(bridge))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SplashMX browser authoring shell")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project-id", default="local-project")
    args = parser.parse_args(argv)
    server = run_server(args.host, args.port, project_id=args.project_id)
    print(f"SMX032 READY http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
