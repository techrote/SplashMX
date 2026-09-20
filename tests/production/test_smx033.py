from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from splashmx.editor.authoring import AuthoringError, AuthoringSession
from splashmx.editor.browser_runtime import BrowserRuntimeError, BrowserRuntimeSession, diagnostic_for
from splashmx.editor.browser_server import BrowserBridge
from splashmx.storage.local import StorageError


class _FailingStore:
    code = "storage.permission_denied"
    def __init__(self, path): self.path = path
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def save(self, project): raise StorageError(self.code, "injected storage failure")
    def load(self, project_id): raise StorageError(self.code, "injected storage failure")


class _QuotaStore(_FailingStore):
    code = "storage.quota_exceeded"


class SMX033Tests(unittest.TestCase):
    def test_play_is_transient_and_stop_discards_runtime_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = AuthoringSession.blank("play-project")
            thing = session.create_thing(label="Counter", authored_state={"count": 0})
            session.attach_rule(thing, event="activate", actions=[{"action": "add_public", "key": "count", "value": 1}])
            authored_revision = session.document.project_revision_id
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")
            result = runtime.play()
            self.assertEqual(result["mode"], "play")
            self.assertEqual(runtime.world.runtime.states[thing].public_state["count"], 1)
            self.assertEqual(runtime.authoring.document.things[thing].authored_state["count"], 0)
            self.assertEqual(runtime.authoring.document.project_revision_id, authored_revision)
            runtime.stop()
            self.assertIsNone(runtime.world)
            self.assertEqual(runtime.authoring.document.things[thing].authored_state["count"], 0)

    def test_save_reload_is_verified_and_rebuilds_behaviour_programs(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = AuthoringSession.blank("reload-project")
            thing = session.create_thing(label="Saved", authored_state={"count": 0})
            attachment = session.attach_behaviour(thing, event="activate", actions=[{"action": "add_public", "key": "count", "value": 1}])
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")
            saved = runtime.save()["saved_revision_id"]
            runtime.authoring.create_thing(label="Unsaved")
            self.assertEqual(len(runtime.authoring.snapshot()["canonical"]["things"]), 2)
            reloaded = runtime.reload()["reloaded_revision_id"]
            self.assertEqual(reloaded, saved)
            self.assertEqual(len(runtime.authoring.snapshot()["canonical"]["things"]), 1)
            revision = runtime.authoring.document.things[thing].behaviours[attachment].behaviour_revision
            self.assertIn(revision, runtime.authoring.programs)
            runtime.play()
            self.assertEqual(runtime.world.runtime.states[thing].public_state["count"], 1)

    def test_permission_failure_is_explicit_and_non_destructive(self):
        session = AuthoringSession.blank("permission-project")
        session.create_thing(label="Unsaved")
        before = session.project
        runtime = BrowserRuntimeSession(session, "ignored.sqlite3", store_factory=_FailingStore)
        with self.assertRaises(BrowserRuntimeError) as caught:
            runtime.save()
        self.assertEqual(caught.exception.code, "storage.permission_denied")
        self.assertIs(runtime.authoring.project, before)
        diagnostic = runtime.snapshot()["diagnostics"][-1]
        self.assertEqual(diagnostic["code"], "storage.permission_denied")
        self.assertIn("unchanged", diagnostic["message"])

    def test_quota_failure_is_explicit_and_non_destructive(self):
        session = AuthoringSession.blank("quota-project")
        thing = session.create_thing(label="Unsaved")
        before_revision = session.document.project_revision_id
        runtime = BrowserRuntimeSession(session, "ignored.sqlite3", store_factory=_QuotaStore)
        with self.assertRaises(BrowserRuntimeError) as caught:
            runtime.save()
        self.assertEqual(caught.exception.code, "storage.quota_exceeded")
        self.assertEqual(runtime.authoring.document.project_revision_id, before_revision)
        self.assertIn(thing, runtime.authoring.document.things)

    def test_corrupt_reload_keeps_active_unsaved_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.sqlite3"
            session = AuthoringSession.blank("corrupt-project")
            session.create_thing(label="Saved")
            runtime = BrowserRuntimeSession(session, path)
            runtime.save()
            runtime.authoring.create_thing(label="Unsaved survives failed reload")
            before = runtime.authoring.project
            # Damage the SQLite file after closing the successful save connection.
            path.write_bytes(b"not-a-sqlite-database")
            with self.assertRaises(BrowserRuntimeError):
                runtime.reload()
            self.assertIs(runtime.authoring.project, before)
            self.assertEqual(len(runtime.authoring.snapshot()["canonical"]["things"]), 2)

    def test_semantic_connection_id_cannot_be_replaced_by_transport_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge = BrowserBridge(AuthoringSession.blank("connection-project"), store_path=Path(tmp) / "p.sqlite3")
            a = bridge.apply({"action": "createThing", "data": {"label": "A", "thing_id": "a"}})["result"]
            b = bridge.apply({"action": "createThing", "data": {"label": "B", "thing_id": "b"}})["result"]
            bridge.apply({"action": "addPort", "data": {"thing_id": a, "port_id": "out", "name": "Out", "kind": "event", "direction": "out"}})
            bridge.apply({"action": "addPort", "data": {"thing_id": b, "port_id": "in", "name": "In", "kind": "command", "direction": "in"}})
            response = bridge.apply({"action": "connect", "data": {"source_thing_id": a, "source_port_id": "out", "target_thing_id": b, "target_port_id": "in", "connection_id": "semantic-connection"}})
            self.assertEqual(response["result"], "semantic-connection")
            self.assertEqual(response["state"]["canonical"]["connections"][0]["connection_id"], "semantic-connection")
            with self.assertRaises(AuthoringError) as caught:
                bridge.apply({"action": "connect", "data": {"source_thing_id": a, "source_port_id": "out", "target_thing_id": b, "target_port_id": "in", "connection_handle": "rtc-channel-7"}})
            self.assertEqual(caught.exception.code, "authoring.forbidden_transient_identity")

    def test_edit_while_playing_fails_without_advancing_authored_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge = BrowserBridge(AuthoringSession.blank("edit-play-project"), store_path=Path(tmp) / "p.sqlite3")
            bridge.apply({"action": "createThing", "data": {"label": "A"}})
            before = bridge.session.document.project_revision_id
            bridge.apply({"action": "play", "data": {}})
            with self.assertRaises(BrowserRuntimeError) as caught:
                bridge.apply({"action": "createThing", "data": {"label": "B"}})
            self.assertEqual(caught.exception.code, "browser.edit_while_playing")
            self.assertEqual(bridge.session.document.project_revision_id, before)

    def test_diagnostics_are_author_language_not_raw_storage_errors(self):
        message = diagnostic_for(StorageError("storage.quota_exceeded", "SQLITE_FULL raw detail"))
        self.assertEqual(message.title, "Storage is full")
        self.assertNotIn("SQLITE", message.message)
        self.assertTrue(message.recoverable)


if __name__ == "__main__":
    unittest.main()
