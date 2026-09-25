from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from splashmx.canonical.core import ConnectionId, PortDirection, PortId, PortKind
from splashmx.editor.authoring import (
    AuthoringError,
    AuthoringSession,
    CHANGE_COLOUR_PORT_ID,
    CLICKED_PORT_ID,
)
from splashmx.editor.browser_runtime import BrowserRuntimeError, BrowserRuntimeSession
from splashmx.editor.godot_play import build_editor_godot_play_projection


BASE_VISUAL = {
    "x": 64,
    "y": 64,
    "width": 160,
    "height": 100,
    "rotation": 0,
    "shape": "rectangle",
    "fill": "#336699",
}


class SMX051FVisualConnectionTests(unittest.TestCase):
    def _session(self) -> tuple[AuthoringSession, object, object]:
        session = AuthoringSession.blank("smx051f-tests")
        source = session.create_thing(
            label="Button",
            thing_id="button",
            authored_state={"visual": dict(BASE_VISUAL)},
        )
        target = session.create_thing(
            label="Lamp",
            thing_id="lamp",
            authored_state={"visual": {**BASE_VISUAL, "x": 300, "fill": "#554433"}},
        )
        return session, source, target

    def _ready_pair(self) -> tuple[AuthoringSession, object, object]:
        session, source, target = self._session()
        session.attach_visual_rule(target, fill="#22cc88", attachment_id="lamp-change-colour")
        return session, source, target

    def test_named_endpoint_projection_derives_from_real_canonical_capabilities(self) -> None:
        session, source, target = self._session()
        source_port = session.document.things[source].ports[CLICKED_PORT_ID]
        self.assertEqual(source_port.name, "Clicked")
        self.assertIs(source_port.kind, PortKind.EVENT)
        self.assertIs(source_port.direction, PortDirection.OUT)

        projection = session.connection_authoring_projection()
        self.assertEqual(projection["sources"][0]["events"], [{"port_id": "clicked", "label": "Clicked"}])
        self.assertEqual(projection["targets"], [])

        session.attach_visual_rule(target, fill="#22cc88")
        target_port = session.document.things[target].ports[CHANGE_COLOUR_PORT_ID]
        self.assertEqual(target_port.name, "Change colour")
        self.assertIs(target_port.kind, PortKind.COMMAND)
        self.assertIs(target_port.direction, PortDirection.IN)

        projection = session.connection_authoring_projection()
        target_row = next(row for row in projection["targets"] if row["thing_id"] == str(target))
        self.assertEqual(
            target_row["actions"],
            [{"port_id": str(target_port.port_id), "label": target_port.name}],
        )

    def test_named_connection_creation_retains_stable_canonical_identity_and_visible_projection(self) -> None:
        session, source, target = self._ready_pair()
        connection = session.connect_named(
            source_thing_id=source,
            source_port_id=CLICKED_PORT_ID,
            target_thing_id=target,
            target_port_id=CHANGE_COLOUR_PORT_ID,
            connection_id="button-lamp",
        )
        self.assertEqual(connection, ConnectionId("button-lamp"))
        record = session.document.connections[connection]
        self.assertEqual(record.source.thing_id, source)
        self.assertEqual(record.source.port_id, PortId("clicked"))
        self.assertEqual(record.target.thing_id, target)
        self.assertEqual(record.target.port_id, PortId("change-colour"))

        card = session.connection_authoring_projection()["connections"][0]
        self.assertEqual(card["connection_id"], "button-lamp")
        self.assertEqual(card["source_thing_label"], "Button")
        self.assertEqual(card["source_event_label"], "Clicked")
        self.assertEqual(card["target_thing_label"], "Lamp")
        self.assertEqual(card["target_action_label"], "Change colour")
        self.assertTrue(card["play_supported"])
        self.assertIsNone(card["recovery"])

    def test_incompatible_pairing_fails_without_partial_mutation(self) -> None:
        session, source, target = self._ready_pair()
        before_revision = session.document.project_revision_id
        before_connections = dict(session.document.connections)

        with self.assertRaises(AuthoringError) as named:
            session.connect_named(
                source_thing_id=source,
                source_port_id=CLICKED_PORT_ID,
                target_thing_id=target,
                target_port_id=CLICKED_PORT_ID,
                connection_id="bad-named",
            )
        self.assertEqual(named.exception.code, "authoring.connection_action_unavailable")
        self.assertEqual(session.document.project_revision_id, before_revision)
        self.assertEqual(session.document.connections, before_connections)

        with self.assertRaises(AuthoringError) as canonical:
            session.connect(
                source_thing_id=source,
                source_port_id=CLICKED_PORT_ID,
                target_thing_id=target,
                target_port_id=CLICKED_PORT_ID,
                connection_id="bad-canonical",
            )
        self.assertEqual(canonical.exception.code, "canonical.incompatible_ports")
        self.assertEqual(session.document.project_revision_id, before_revision)
        self.assertEqual(session.document.connections, before_connections)

    def test_edit_preserves_connection_id_and_delete_tombstones_same_record(self) -> None:
        session, source, target = self._ready_pair()
        alternate = session.create_thing(
            label="Alternate button",
            thing_id="alternate",
            authored_state={"visual": {**BASE_VISUAL, "y": 220}},
        )
        connection = session.connect_named(
            source_thing_id=source,
            source_port_id=CLICKED_PORT_ID,
            target_thing_id=target,
            target_port_id=CHANGE_COLOUR_PORT_ID,
            connection_id="stable-connection",
        )

        updated = session.update_named_connection(
            connection,
            source_thing_id=alternate,
            source_port_id=CLICKED_PORT_ID,
            target_thing_id=target,
            target_port_id=CHANGE_COLOUR_PORT_ID,
        )
        self.assertEqual(updated, connection)
        self.assertEqual(session.document.connections[connection].source.thing_id, alternate)
        self.assertEqual(
            session.connection_authoring_projection()["connections"][0]["connection_id"],
            "stable-connection",
        )

        session.remove_connection(connection)
        self.assertTrue(session.document.connections[connection].tombstoned)
        self.assertEqual(session.connection_authoring_projection()["connections"], [])

    def test_save_reload_preserves_exact_connection_and_rule_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, source, target = self._ready_pair()
            connection = session.connect_named(
                source_thing_id=source,
                source_port_id=CLICKED_PORT_ID,
                target_thing_id=target,
                target_port_id=CHANGE_COLOUR_PORT_ID,
                connection_id="persisted-connection",
            )
            expected = session.document.connections[connection]
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")
            runtime.save()
            runtime.reload()
            self.assertEqual(runtime.authoring.document.connections[connection], expected)
            projection = runtime.authoring.connection_authoring_projection()
            self.assertTrue(projection["connections"][0]["play_supported"])
            self.assertEqual(projection["targets"][0]["actions"][0]["label"], "Change colour")

    def test_connection_play_routes_to_existing_rule_without_authored_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, source, target = self._ready_pair()
            session.connect_named(
                source_thing_id=source,
                source_port_id=CLICKED_PORT_ID,
                target_thing_id=target,
                target_port_id=CHANGE_COLOUR_PORT_ID,
                connection_id="runtime-connection",
            )
            authored_revision = session.document.project_revision_id
            authored_target = dict(session.document.things[target].authored_state["visual"])
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")

            runtime.play()
            affected = runtime.dispatch_pointer_event(source, {"pointer": "primary"})
            self.assertEqual(affected, [target])
            self.assertEqual(
                runtime.world.runtime.states[target].public_state["visual.fill"],
                "#22cc88",
            )
            self.assertEqual(session.document.project_revision_id, authored_revision)
            self.assertEqual(session.document.things[target].authored_state["visual"], authored_target)

            runtime.stop()
            self.assertIsNone(runtime.world)
            self.assertEqual(session.document.project_revision_id, authored_revision)
            self.assertEqual(session.document.things[target].authored_state["visual"], authored_target)

    def test_stale_target_rule_fails_explicitly_and_never_publishes_authored_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, source, target = self._ready_pair()
            attachment = next(iter(session.document.things[target].behaviours))
            session.connect_named(
                source_thing_id=source,
                source_port_id=CLICKED_PORT_ID,
                target_thing_id=target,
                target_port_id=CHANGE_COLOUR_PORT_ID,
                connection_id="stale-connection",
            )
            session.remove_rule(target, attachment)
            card = session.connection_authoring_projection()["connections"][0]
            self.assertFalse(card["play_supported"])
            self.assertIn("Add that Rule again", card["recovery"])

            authored_revision = session.document.project_revision_id
            authored_target = dict(session.document.things[target].authored_state["visual"])
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")
            runtime.play()
            with self.assertRaises(BrowserRuntimeError) as caught:
                runtime.dispatch_pointer_event(source, {"pointer": "primary"})
            self.assertEqual(caught.exception.code, "browser.connection_action_unavailable")
            self.assertEqual(session.document.project_revision_id, authored_revision)
            self.assertEqual(session.document.things[target].authored_state["visual"], authored_target)

    def test_godot_projection_exposes_connected_source_input_without_source_rule(self) -> None:
        session, source, target = self._ready_pair()
        session.connect_named(
            source_thing_id=source,
            source_port_id=CLICKED_PORT_ID,
            target_thing_id=target,
            target_port_id=CHANGE_COLOUR_PORT_ID,
            connection_id="godot-source",
        )
        projection = build_editor_godot_play_projection(session.project)
        source_row = next(row for row in projection["things"] if row["thing_id"] == str(source))
        self.assertEqual(source_row["interactive_events"], ["pointer_click"])
        self.assertEqual(projection["required_features"], ["input", "render_2d"])


if __name__ == "__main__":
    unittest.main()
