from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from splashmx.editor.authoring import AuthoringError, AuthoringSession
from splashmx.editor.browser_runtime import BrowserRuntimeSession
from splashmx.editor.browser_server import BrowserBridge
from splashmx.editor.godot_play import (
    EDITOR_GODOT_RUNTIME_UPDATE_CONTRACT,
    EditorGodotPlayError,
    build_editor_godot_play_projection,
)


BASE_VISUAL = {
    "x": 64,
    "y": 64,
    "width": 160,
    "height": 100,
    "rotation": 0,
    "shape": "rectangle",
    "fill": "#336699",
}


class SMX051DInteractiveRuleTests(unittest.TestCase):
    def _session(self) -> tuple[AuthoringSession, object]:
        session = AuthoringSession.blank("smx051d-tests")
        thing = session.create_thing(
            label="Button",
            thing_id="button",
            authored_state={"visual": dict(BASE_VISUAL)},
        )
        return session, thing

    def test_beginner_visual_rule_uses_canonical_attachment_and_common_ir(self) -> None:
        session, thing = self._session()
        attachment = session.attach_visual_rule(thing, fill="#ff5a5f", attachment_id="click-colour")
        record = session.document.things[thing].behaviours[attachment]
        self.assertEqual(record.authored_config["projection"], "Rule")
        self.assertEqual(record.authored_config["event"], "pointer_click")
        self.assertEqual(record.authored_config["author_kind"], "visual-fill")
        self.assertEqual(
            record.authored_config["actions"],
            [{
                "action": "set_public",
                "key": "visual.fill",
                "value": "#ff5a5f",
            }],
        )
        program = session.programs[record.behaviour_revision]
        self.assertEqual(program.source_kind, "rule")
        self.assertEqual(program.handlers[0].trigger, "pointer_click")
        self.assertEqual(program.handlers[0].instructions[0].op, "set_public")

    def test_rule_edit_preserves_attachment_identity_and_delete_is_canonical(self) -> None:
        session, thing = self._session()
        attachment = session.attach_visual_rule(thing, fill="#ff5a5f", attachment_id="click-colour")
        first = session.document.things[thing].behaviours[attachment]
        session.update_visual_rule(thing, attachment, fill="#22cc88")
        second = session.document.things[thing].behaviours[attachment]
        self.assertEqual(second.attachment_id, first.attachment_id)
        self.assertNotEqual(second.behaviour_revision, first.behaviour_revision)
        self.assertEqual(second.authored_config["actions"][0]["value"], "#22cc88")
        self.assertNotIn(first.behaviour_revision, session.programs)
        self.assertIn(second.behaviour_revision, session.programs)

        session.remove_rule(thing, attachment)
        self.assertNotIn(attachment, session.document.things[thing].behaviours)
        self.assertNotIn(second.behaviour_revision, session.programs)

    def test_duplicate_beginner_rule_and_invalid_fill_fail_without_partial_edit(self) -> None:
        session, thing = self._session()
        session.attach_visual_rule(thing, fill="#ff5a5f")
        revision = session.document.project_revision_id
        with self.assertRaises(AuthoringError) as duplicate:
            session.attach_visual_rule(thing, fill="#22cc88")
        self.assertEqual(duplicate.exception.code, "authoring.rule_exists")
        self.assertEqual(session.document.project_revision_id, revision)

        other = session.create_thing(
            label="Other",
            thing_id="other",
            authored_state={"visual": dict(BASE_VISUAL)},
        )
        revision = session.document.project_revision_id
        with self.assertRaises(AuthoringError) as invalid:
            session.attach_visual_rule(other, fill="not-a-colour")
        self.assertEqual(invalid.exception.code, "authoring.invalid_visual")
        self.assertEqual(session.document.project_revision_id, revision)

    def test_pointer_rule_waits_for_real_input_and_mutates_transient_runtime_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, thing = self._session()
            session.attach_visual_rule(thing, fill="#ff5a5f")
            authored_revision = session.document.project_revision_id
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")

            runtime.play()
            self.assertEqual(
                runtime.world.runtime.states[thing].public_state["visual"]["fill"],
                BASE_VISUAL["fill"],
            )
            runtime.world.dispatch(thing, "pointer_click", {"pointer": "primary"})
            runtime.world.runtime.run_current_tick()
            self.assertEqual(
                runtime.world.runtime.states[thing].public_state["visual.fill"],
                "#ff5a5f",
            )
            self.assertEqual(
                runtime.world.runtime.states[thing].public_state["visual"]["fill"],
                BASE_VISUAL["fill"],
            )
            self.assertEqual(session.document.project_revision_id, authored_revision)
            self.assertEqual(
                session.document.things[thing].authored_state["visual"]["fill"],
                BASE_VISUAL["fill"],
            )
            runtime.stop()
            self.assertIsNone(runtime.world)
            self.assertEqual(
                session.document.things[thing].authored_state["visual"]["fill"],
                BASE_VISUAL["fill"],
            )

    def test_save_reload_rebuilds_click_rule_without_firing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, thing = self._session()
            attachment = session.attach_visual_rule(thing, fill="#22cc88")
            runtime = BrowserRuntimeSession(session, Path(tmp) / "project.sqlite3")
            saved = runtime.save()["saved_revision_id"]
            runtime.reload()
            self.assertEqual(str(runtime.authoring.document.project_revision_id), saved)
            record = runtime.authoring.document.things[thing].behaviours[attachment]
            self.assertIn(record.behaviour_revision, runtime.authoring.programs)
            runtime.play()
            self.assertEqual(
                runtime.world.runtime.states[thing].public_state["visual"]["fill"],
                BASE_VISUAL["fill"],
            )

    def test_play_projection_exposes_only_supported_interactive_event(self) -> None:
        session, thing = self._session()
        session.attach_visual_rule(thing, fill="#ff5a5f")
        projection = build_editor_godot_play_projection(session.project)
        self.assertEqual(projection["required_features"], ["input", "render_2d"])
        self.assertEqual(projection["things"][0]["thing_id"], str(thing))
        self.assertEqual(projection["things"][0]["interactive_events"], ["pointer_click"])

    def test_bridge_dispatches_godot_input_through_runtime_and_returns_bounded_visual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, thing = self._session()
            session.attach_visual_rule(thing, fill="#22cc88")
            authored_revision = str(session.document.project_revision_id)
            bridge = BrowserBridge(session, store_path=Path(tmp) / "project.sqlite3")
            try:
                bridge.apply({"action": "play", "data": {}})
                response = bridge.godot_runtime_event({
                    "thing_id": str(thing),
                    "trigger": "pointer_click",
                    "payload": {"pointer": "primary"},
                })
                update = response["update"]
                self.assertEqual(update["contract"], EDITOR_GODOT_RUNTIME_UPDATE_CONTRACT)
                self.assertEqual(update["project_revision_id"], authored_revision)
                self.assertEqual(update["thing_id"], str(thing))
                self.assertEqual(update["visual"]["fill"], "#22cc88")
                self.assertEqual(
                    bridge.session.document.things[thing].authored_state["visual"]["fill"],
                    BASE_VISUAL["fill"],
                )
                bridge.apply({"action": "stop", "data": {}})
                self.assertEqual(
                    bridge.session.document.things[thing].authored_state["visual"]["fill"],
                    BASE_VISUAL["fill"],
                )
            finally:
                bridge.close()

    def test_bridge_rejects_unsupported_or_unmatched_runtime_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session, thing = self._session()
            session.attach_visual_rule(thing, fill="#ff5a5f")
            bridge = BrowserBridge(session, store_path=Path(tmp) / "project.sqlite3")
            try:
                bridge.apply({"action": "play", "data": {}})
                with self.assertRaises(EditorGodotPlayError) as unsupported:
                    bridge.godot_runtime_event({
                        "thing_id": str(thing),
                        "trigger": "keyboard_key",
                        "payload": {},
                    })
                self.assertEqual(unsupported.exception.code, "godot_play.unsupported_event")

                with self.assertRaises(EditorGodotPlayError) as unmatched:
                    bridge.godot_runtime_event({
                        "thing_id": "missing",
                        "trigger": "pointer_click",
                        "payload": {},
                    })
                self.assertEqual(unmatched.exception.code, "godot_play.unknown_thing")
            finally:
                bridge.close()


if __name__ == "__main__":
    unittest.main()
