"""Thin same-origin browser bridge for SplashMX production authoring/runtime.

The HTTP layer owns no document semantics. Browser actions are decoded and forwarded
to production authoring, runtime, storage and People/collaboration boundaries. People
is explicitly distinct from future Together/runtime networking.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from threading import RLock
from typing import Any, Mapping
from urllib.parse import urlparse

from splashmx.canonical.core import SemanticError, ThingId
from splashmx.canonical.serialization import SerializationError
from splashmx.collaboration.core import CollaborationError, RelayAuthenticator, RelayPacket
from splashmx.editor.authoring import AuthoringError, AuthoringSession
from splashmx.editor.godot_play import (
    EditorGodotPlayError,
    POINTER_CLICK_EVENT,
    build_editor_godot_play_projection,
    build_editor_godot_runtime_update,
)
from splashmx.editor.browser_runtime import BrowserRuntimeError, BrowserRuntimeSession, rebuild_program_catalog
from splashmx.editor.people import PeopleError, PeopleSession
from splashmx.runtime.lifecycle import LifecycleError
from splashmx.storage.local import StorageError

WEB_ROOT = Path(__file__).with_name("web")
_STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8")}
_MAX_REQUEST_BYTES = 8 * 1024 * 1024
_FORBIDDEN_TRANSIENT_FIELDS = {"transportpeerid", "connectionhandle", "socketid", "sessionid", "processhandle", "domnodeidentity"}
_GENERATED_ID_SUFFIX = re.compile(r"-(\d{6})(?::\d+)?$")


def _generated_identity_counter(project) -> int:
    """Recover the monotonic browser-generated identity floor from canonical state."""
    document = project.document
    tokens = [
        *(str(value) for value in document.things),
        *(str(value) for value in document.relationships),
        *(str(value) for value in document.connections),
        *(str(value) for value in document.definitions),
        *(str(value) for value in document.instances),
        *(str(value) for value in project.assets),
    ]
    for thing in document.things.values():
        for attachment in thing.behaviours.values():
            tokens.append(str(attachment.attachment_id))
            tokens.append(str(attachment.behaviour_revision))
        tracks = thing.authored_state.get("timeline_tracks", ())
        if isinstance(tracks, (list, tuple)):
            for row in tracks:
                if isinstance(row, Mapping) and isinstance(row.get("track_id"), str):
                    tokens.append(row["track_id"])
    values = [int(match.group(1)) for token in tokens if (match := _GENERATED_ID_SUFFIX.search(token))]
    return max(values, default=0)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reject_transient_identity(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _normalise(key) in _FORBIDDEN_TRANSIENT_FIELDS:
                raise AuthoringError("authoring.forbidden_transient_identity", "Runtime transport/session identity cannot be authored as SplashMX identity.")
            _reject_transient_identity(child)
    elif isinstance(value, list):
        for child in value:
            _reject_transient_identity(child)


class BrowserBridge:
    """Decode bounded JSON actions and delegate to production coordinators."""

    def __init__(
        self,
        session: AuthoringSession | None = None,
        *,
        store_path: str | Path = ".splashmx/local-project.sqlite3",
        runtime: BrowserRuntimeSession | None = None,
        collaboration_store_path: str | Path | None = None,
        principal_id: str = "local-author",
        godot_web_root: str | Path | None = None,
    ):
        authoring = session or AuthoringSession.blank()
        self.runtime = runtime or BrowserRuntimeSession(authoring, store_path)
        self._lock = RLock()
        self._closed = False
        self.godot_web_root: Path | None = None
        if godot_web_root is not None:
            candidate = Path(godot_web_root).resolve()
            if not candidate.is_dir() or not (candidate / "index.html").is_file():
                raise ValueError("Godot Web runtime directory must contain index.html")
            self.godot_web_root = candidate
        self._people_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="splashmx-people")
        collaboration_path = Path(collaboration_store_path) if collaboration_store_path is not None else Path(str(store_path) + ".collaboration.sqlite3")
        try:
            # SQLiteCollaborationStore deliberately keeps Python's default thread
            # affinity. Construct and use it on one dedicated owner thread instead of
            # weakening the store with a cross-thread connection.
            self.people = self._people_executor.submit(
                PeopleSession,
                self.runtime.authoring.project,
                collaboration_path,
                principal_id=principal_id,
            ).result()
        except BaseException:
            self._people_executor.shutdown(wait=True, cancel_futures=True)
            raise
        # The collaboration store is local-first durable history. On process restart its
        # validated head wins over a newly-created blank shell, never a remote cache.
        if self._people_call("head_project") != self.runtime.authoring.project:
            self._adopt_people_head()

    @property
    def session(self) -> AuthoringSession:
        return self.runtime.authoring

    def _people_call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Run one collaboration/store operation on its SQLite owner thread."""
        if self._closed:
            raise PeopleError("people.bridge_closed", "The collaboration bridge is closed.")
        return self._people_executor.submit(
            lambda: getattr(self.people, method)(*args, **kwargs)
        ).result()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self._people_call("close")
            finally:
                self._closed = True
                self._people_executor.shutdown(wait=True, cancel_futures=True)

    def _adopt_people_head(self) -> None:
        prior_editor = self.runtime.authoring.editor
        prior_identity_counter = getattr(self.runtime.authoring, "_identity_counter", 0)
        head = self._people_call("head_project")
        counter = self._people_call("author_revision_counter")
        candidate = AuthoringSession(head, revision_counter=counter)
        candidate._identity_counter = max(
            prior_identity_counter,
            _generated_identity_counter(head),
        )
        candidate.editor = prior_editor
        candidate.programs.update(rebuild_program_catalog(candidate))
        self.runtime.authoring = candidate
        self.runtime.world = None

    def _record_people_local(self, before_project) -> None:
        if self.session.project == before_project:
            return
        self._people_call("record_local", self.session.project)
        people = self._people_call("snapshot")
        if (
            not people["unsynced_local_work"]
            and people["head_revision_id"] != str(self.session.document.project_revision_id)
        ):
            # A genuine merge/conflict can publish a head different from the authored
            # candidate. Ordinary local edits already are that head and must retain
            # editor-only counters/program state instead of rebuilding the session.
            self._adopt_people_head()

    def receive_relay(self, packet: RelayPacket, authenticator: RelayAuthenticator) -> tuple[Any, ...]:
        """Production relay ingress seam; HTTP authoring never accepts raw relay identity."""
        with self._lock:
            self._people_call("enqueue_relay", packet, authenticator)
            results = self._people_call("drain_relay")
            if results:
                self._adopt_people_head()
            return results

    def state(self) -> dict[str, Any]:
        with self._lock:
            state = self.runtime.snapshot()
            state["people"] = self._people_call("snapshot")
            state["together"] = {
                "plane": "runtime-networking",
                "available": False,
                "note": "Together runtime networking is separate from People collaboration.",
            }
            state["godot_player"] = {
                "available": self.godot_web_root is not None,
                "url": "/godot/index.html?editor_live=1",
                "runtime": "Godot 4.7.2",
            }
            return state

    def godot_play_projection(self) -> dict[str, Any]:
        with self._lock:
            if not self.runtime.playing:
                raise BrowserRuntimeError(
                    "browser.play_not_active",
                    "Start Play before requesting the Godot runtime projection.",
                )
            return build_editor_godot_play_projection(self.session.project)

    def godot_runtime_event(self, request: Any) -> dict[str, Any]:
        """Dispatch one validated target input through the production constrained runtime."""
        with self._lock:
            if not isinstance(request, dict):
                raise EditorGodotPlayError("godot_play.invalid_event", "The runtime input event is invalid.")
            _reject_transient_identity(request)
            if not self.runtime.playing or self.runtime.world is None:
                raise EditorGodotPlayError("godot_play.runtime_unavailable", "Play is not active.")
            thing_id = _string(request, "thing_id")
            trigger = _string(request, "trigger")
            if trigger != POINTER_CLICK_EVENT:
                raise EditorGodotPlayError(
                    "godot_play.unsupported_event",
                    "That runtime interaction is not supported by this editor Play target.",
                )
            world = self.runtime.world
            tid = ThingId(thing_id)
            if tid not in world.runtime.states:
                raise EditorGodotPlayError("godot_play.unknown_thing", "That interactive Thing is not active in Play.")
            projection = build_editor_godot_play_projection(self.session.project)
            projected = next((row for row in projection["things"] if row["thing_id"] == thing_id), None)
            if projected is None or trigger not in projected.get("interactive_events", []):
                raise EditorGodotPlayError(
                    "godot_play.no_matching_rule",
                    "That Thing has no matching interactive Rule.",
                )
            before_faults = len(world.runtime.faults)
            matches = world.dispatch(tid, trigger, request.get("payload"))
            if matches <= 0:
                raise EditorGodotPlayError(
                    "godot_play.no_matching_rule",
                    "That Thing has no matching interactive Rule.",
                )
            world.runtime.run_current_tick()
            if len(world.runtime.faults) > before_faults:
                fault = world.runtime.faults[-1]
                raise EditorGodotPlayError(fault.code, fault.message)
            return {
                "ok": True,
                "update": build_editor_godot_runtime_update(
                    world,
                    project_revision_id=str(self.session.document.project_revision_id),
                    thing_id=thing_id,
                ),
            }

    def apply(self, request: Any) -> dict[str, Any]:
        # ThreadingHTTPServer may dispatch concurrent requests. Serialize semantic
        # mutations/snapshots so project revisions, collaboration receipts and the
        # People owner-thread handoff have one explicit browser-boundary order.
        with self._lock:
            return self._apply_locked(request)

    def _apply_locked(self, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict) or not isinstance(request.get("action"), str):
            raise AuthoringError("authoring.invalid_request", "Choose a supported authoring action.")
        action = request["action"]
        data = request.get("data", {})
        if not isinstance(data, dict):
            raise AuthoringError("authoring.invalid_request", "Authoring action data must be an object.")
        _reject_transient_identity(data)

        if action == "peoplePresence":
            selections = _string_list_optional(data, "selections")
            self._people_call("set_presence", cursor=_optional_string(data, "cursor"), selections=selections)
            return {"ok": True, "result": None, "state": self.state()}
        if action == "peopleRetryLocal":
            self._people_call("retry_local")
            if not self._people_call("snapshot")["unsynced_local_work"]:
                self._adopt_people_head()
            return {"ok": True, "result": None, "state": self.state()}
        if action == "peopleResolveConflict":
            result = self._people_call("resolve_conflict", _string(data, "conflict_id"), _string(data, "choice"))
            self._adopt_people_head()
            return {"ok": True, "result": {"transaction_id": str(result.tx_id), "status": result.status}, "state": self.state()}

        if action == "play": result = self.runtime.play(); return {"ok": True, "result": result, "state": self.state()}
        if action == "stop": result = self.runtime.stop(); return {"ok": True, "result": result, "state": self.state()}
        if action == "save": result = self.runtime.save(); return {"ok": True, "result": result, "state": self.state()}
        if action == "reload":
            before = self.session.project
            identity_floor = getattr(self.session, "_identity_counter", 0)
            result = self.runtime.reload()
            self.session._identity_counter = max(
                identity_floor,
                _generated_identity_counter(self.session.project),
            )
            self._record_people_local(before)
            return {"ok": True, "result": result, "state": self.state()}
        if action == "clearDiagnostics": self.runtime.clear_diagnostics(); return {"ok": True, "result": None, "state": self.state()}
        if self.runtime.playing and action not in {"select", "inspect"}:
            raise BrowserRuntimeError("browser.edit_while_playing", "Stop Play before changing the authored project.")

        before = self.session.project
        result: Any = None
        if action == "createThing": result = str(self.session.create_thing(label=_string(data, "label"), thing_id=_optional_string(data, "thing_id"), authored_state=_mapping(data.get("authored_state", {}), "authored_state")))
        elif action == "addPort": result = str(self.session.add_port(_string(data, "thing_id"), port_id=_string(data, "port_id"), name=_string(data, "name"), kind=_string(data, "kind"), direction=_string(data, "direction")))
        elif action == "group": result = str(self.session.group_things(_string_list(data, "members"), label=str(data.get("label", "Group")), group_id=_optional_string(data, "group_id")))
        elif action == "makeReusable": result = str(self.session.make_reusable(_string(data, "root_id"), definition_id=_optional_string(data, "definition_id")))
        elif action == "instantiateReusable": result = str(self.session.instantiate_reusable(_string(data, "definition_id")))
        elif action in {"attachRule", "attachBehaviour"}:
            if action == "attachRule" and data.get("author_kind") == "visual-fill":
                result = str(self.session.attach_visual_rule(
                    _string(data, "thing_id"),
                    attachment_id=_optional_string(data, "attachment_id"),
                    fill=_string(data, "fill"),
                ))
            else:
                method = self.session.attach_rule if action == "attachRule" else self.session.attach_behaviour
                actions = data.get("actions")
                if actions is not None and not isinstance(actions, list): raise AuthoringError("authoring.invalid_behaviour", "Actions must be a list.")
                result = str(method(_string(data, "thing_id"), attachment_id=_optional_string(data, "attachment_id"), event=str(data.get("event", "activate")), actions=actions))
        elif action == "updateVisualRule":
            result = str(self.session.update_visual_rule(_string(data, "thing_id"), _string(data, "attachment_id"), fill=_string(data, "fill")))
        elif action == "removeRule":
            self.session.remove_rule(_string(data, "thing_id"), _string(data, "attachment_id"))
        elif action == "connect": result = str(self.session.connect(source_thing_id=_string(data, "source_thing_id"), source_port_id=_string(data, "source_port_id"), target_thing_id=_string(data, "target_thing_id"), target_port_id=_string(data, "target_port_id"), connection_id=_optional_string(data, "connection_id")))
        elif action == "timeline":
            keyframes = data.get("keyframes", [])
            if not isinstance(keyframes, list): raise AuthoringError("authoring.invalid_timeline", "Timeline keyframes must be a list.")
            result = self.session.add_timeline_track(_string(data, "thing_id"), property_name=_string(data, "property"), keyframes=keyframes, track_id=_optional_string(data, "track_id"))
        elif action == "updateVisual":
            result = self.session.update_visual_state(_string(data, "thing_id"), visual=_mapping(data.get("visual"), "visual"))
        elif action == "select": self.session.select(_string_list(data, "thing_ids"))
        elif action == "inspect": self.session.set_inspect_open(bool(data.get("open", False)))
        elif action == "importAsset":
            encoded = _string(data, "content_base64")
            try: content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc: raise AuthoringError("authoring.invalid_import", "The selected source file could not be read.") from exc
            thing_id, asset_id = self.session.import_asset_thing(content=content, source_name=_string(data, "source_name"), media_type=_string(data, "media_type"), media_semantics=_mapping(data.get("media_semantics"), "media_semantics"), provenance=_mapping(data.get("provenance"), "provenance"), licence_attribution=_mapping(data.get("licence_attribution"), "licence_attribution"), derivation_lineage=_mapping_list(data.get("derivation_lineage"), "derivation_lineage"), asset_id=_optional_string(data, "asset_id"), thing_id=_optional_string(data, "thing_id"), label=_optional_string(data, "label"))
            result = {"thing_id": str(thing_id), "asset_id": str(asset_id)}
        else: raise AuthoringError("authoring.unknown_action", "Choose a supported authoring action.")
        self._record_people_local(before)
        return {"ok": True, "result": result, "state": self.state()}


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value: raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} is required.")
    return value

def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None: return None
    if not isinstance(value, str) or not value: raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} must be text.")
    return value

def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value): raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} must be a list of Things.")
    return value

def _string_list_optional(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value): raise AuthoringError("authoring.invalid_request", f"{key.replace('_', ' ')} must be a list of text identities.")
    return value

def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict): raise AuthoringError("authoring.invalid_request", f"{label.replace('_', ' ')} must be an object.")
    return value

def _mapping_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value): raise AuthoringError("authoring.invalid_request", f"{label.replace('_', ' ')} must be a list.")
    return value


def make_handler(bridge: BrowserBridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SplashMXAuthoring/3"
        def log_message(self, format: str, *args: Any) -> None: return
        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(body)
        def _bytes(self, status: int, body: bytes, mime: str, *, editor_csp: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if editor_csp:
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state": self._json(HTTPStatus.OK, {"ok": True, "state": bridge.state()}); return
            if path == "/api/godot-play-projection":
                try:
                    projection = bridge.godot_play_projection()
                except (BrowserRuntimeError, EditorGodotPlayError) as exc:
                    self._json(HTTPStatus.CONFLICT, {"error": {"code": getattr(exc, "code", "godot_play.invalid_projection"), "message": str(exc)}})
                    return
                self._json(HTTPStatus.OK, {"ok": True, "projection": projection})
                return
            if path.startswith("/godot/"):
                root = bridge.godot_web_root
                if root is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "godot_play.runtime_unavailable", "message": "The Godot Play runtime is not installed for this editor."}})
                    return
                relative = path[len("/godot/"):] or "index.html"
                candidate = (root / relative).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That runtime resource was not found."}})
                    return
                if not candidate.is_file():
                    self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That runtime resource was not found."}})
                    return
                mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                self._bytes(HTTPStatus.OK, candidate.read_bytes(), mime)
                return
            static = _STATIC.get(path)
            if static is None: self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That editor resource was not found."}}); return
            filename, mime = static; self._bytes(HTTPStatus.OK, (WEB_ROOT / filename).read_bytes(), mime, editor_csp=True)
        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path not in {"/api/action", "/api/godot-runtime-event"}:
                self._json(HTTPStatus.NOT_FOUND, {"error": {"code": "authoring.not_found", "message": "That editor action was not found."}})
                return
            try: length = int(self.headers.get("Content-Length", "0"))
            except ValueError: length = -1
            if length < 0 or length > _MAX_REQUEST_BYTES:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "authoring.request_too_large", "message": "That authoring change is too large for one request."}})
                return
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                response = bridge.godot_runtime_event(request) if path == "/api/godot-runtime-event" else bridge.apply(request)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "authoring.invalid_request", "message": "That authoring request could not be read."}})
                return
            except (AuthoringError, BrowserRuntimeError, EditorGodotPlayError, PeopleError, CollaborationError, SemanticError, SerializationError, LifecycleError, StorageError) as exc:
                self._json(HTTPStatus.CONFLICT, {"error": {"code": getattr(exc, "code", "authoring.invalid_edit"), "message": str(exc)}, "state": bridge.state()})
                return
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "authoring.invalid_request", "message": str(exc)}})
                return
            self._json(HTTPStatus.OK, response)
    return Handler


class BrowserHTTPServer(ThreadingHTTPServer):
    """Threaded static/API server with explicit bridge lifecycle ownership."""

    daemon_threads = False
    block_on_close = True

    def __init__(self, server_address, bridge: BrowserBridge):
        self.bridge = bridge
        self._bridge_closed = False
        super().__init__(server_address, make_handler(bridge))

    def server_close(self) -> None:
        # Let ThreadingMixIn finish active request handlers before closing the
        # collaboration owner thread they may still be using.
        super().server_close()
        if not self._bridge_closed:
            self.bridge.close()
            self._bridge_closed = True


def run_server(host: str, port: int, *, project_id: str = "local-project", store_path: str | Path = ".splashmx/local-project.sqlite3", godot_web_root: str | Path | None = None) -> BrowserHTTPServer:
    bridge = BrowserBridge(AuthoringSession.blank(project_id), store_path=store_path, godot_web_root=godot_web_root)
    return BrowserHTTPServer((host, port), bridge)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SplashMX browser authoring shell"); parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8765); parser.add_argument("--project-id", default="local-project"); parser.add_argument("--store-path", default=".splashmx/local-project.sqlite3"); parser.add_argument("--godot-web-root", default=None); args = parser.parse_args(argv)
    server = run_server(args.host, args.port, project_id=args.project_id, store_path=args.store_path, godot_web_root=args.godot_web_root)
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"SMX032 READY {url}", flush=True)
    print(f"SMX033 READY {url}", flush=True)
    print(f"SMX044 READY {url}", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
