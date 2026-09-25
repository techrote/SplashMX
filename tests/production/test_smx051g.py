from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from splashmx.editor.authoring import AuthoringSession
from splashmx.editor.browser_runtime import BrowserRuntimeError, BrowserRuntimeSession
from splashmx.editor.godot_play import build_editor_godot_play_projection


BASE_VISUAL = {
    "x": 64,
    "y": 64,
    "width": 160,
    "height": 100,
    "rotation": 0,
    "layer": 0,
    "shape": "rectangle",
    "fill": "#336699",
}


class SMX051GEditorHardeningTests(unittest.TestCase):
    def test_saved_dirty_reload_state_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = BrowserRuntimeSession(
                AuthoringSession.blank("smx051g-dirty"),
                Path(tmp) / "project.sqlite3",
            )
            self.assertEqual(runtime.snapshot()["storage"]["state"], "never-saved")
            self.assertTrue(runtime.snapshot()["storage"]["dirty"])

            runtime.authoring.create_thing(label="Saved", authored_state={"visual": dict(BASE_VISUAL)})
            saved = runtime.save()["saved_revision_id"]
            state = runtime.snapshot()["storage"]
            self.assertEqual(state["state"], "saved")
            self.assertFalse(state["dirty"])
            self.assertEqual(state["saved_revision_id"], saved)

            runtime.authoring.create_thing(label="Unsaved", authored_state={"visual": dict(BASE_VISUAL)})
            state = runtime.snapshot()["storage"]
            self.assertEqual(state["state"], "dirty")
            self.assertTrue(state["dirty"])
            runtime.reload()
            state = runtime.snapshot()
            self.assertEqual(state["storage"]["state"], "saved")
            self.assertFalse(state["storage"]["dirty"])
            self.assertEqual(len(state["canonical"]["things"]), 1)

    def test_smx050_backup_restore_is_prepare_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = BrowserRuntimeSession(
                AuthoringSession.blank("smx051g-backup"),
                Path(tmp) / "project.sqlite3",
            )
            first = runtime.authoring.create_thing(
                label="First",
                thing_id="first",
                authored_state={"visual": dict(BASE_VISUAL)},
            )
            revision_one = runtime.save()["saved_revision_id"]
            archive = runtime.export_recovery()

            runtime.authoring.create_thing(
                label="Later",
                thing_id="later",
                authored_state={"visual": {**BASE_VISUAL, "x": 300}},
            )
            revision_two = runtime.save()["saved_revision_id"]
            self.assertNotEqual(revision_two, revision_one)

            restored = runtime.import_recovery(archive)
            self.assertEqual(restored["recovered_revision_id"], revision_one)
            self.assertTrue(restored["requires_save"])
            self.assertIn(first, runtime.authoring.document.things)
            self.assertNotIn("later", {str(value) for value in runtime.authoring.document.things})
            self.assertEqual(runtime.snapshot()["storage"]["state"], "dirty")

    def test_invalid_backup_keeps_current_unsaved_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = BrowserRuntimeSession(
                AuthoringSession.blank("smx051g-invalid-backup"),
                Path(tmp) / "project.sqlite3",
            )
            runtime.authoring.create_thing(label="Current", authored_state={"visual": dict(BASE_VISUAL)})
            before = runtime.authoring.project
            with self.assertRaises(BrowserRuntimeError) as caught:
                runtime.import_recovery(b"not-a-splashmx-backup")
            self.assertTrue(caught.exception.code.startswith("distribution."))
            self.assertIs(runtime.authoring.project, before)
            diagnostic = runtime.snapshot()["diagnostics"][-1]
            self.assertIn("unchanged", diagnostic["message"].lower())

    def test_visual_layer_is_canonical_and_reaches_godot_projection(self) -> None:
        session = AuthoringSession.blank("smx051g-layer")
        thing = session.create_thing(
            label="Layered",
            thing_id="layered",
            authored_state={"visual": {**BASE_VISUAL, "layer": 7}},
        )
        self.assertEqual(session.document.things[thing].authored_state["visual"]["layer"], 7.0)
        session.update_visual_state(thing, visual={"layer": -3})
        projection = build_editor_godot_play_projection(session.project)
        self.assertEqual(projection["things"][0]["visual"]["layer"], -3.0)

    def test_localization_catalog_covers_marked_ordinary_ui(self) -> None:
        root = Path(__file__).resolve().parents[2]
        index = (root / "src/splashmx/editor/web/index.html").read_text(encoding="utf-8")
        catalog = (root / "src/splashmx/editor/web/i18n.js").read_text(encoding="utf-8")
        marked = set(re.findall(r'data-i18n="([^"]+)"', index))
        keys = set(re.findall(r'^\s*"([^"]+)":\s*"', catalog, re.MULTILINE))
        self.assertTrue(marked)
        self.assertEqual(marked - keys, set())
        for required in {
            "app.play", "app.save", "app.reload", "app.properties", "app.library",
            "app.rules", "app.connections", "app.timeline", "app.recovery",
        }:
            self.assertIn(required, keys)

    def test_raw_diagnostics_are_progressively_disclosed_and_shortcuts_visible(self) -> None:
        root = Path(__file__).resolve().parents[2]
        index = (root / "src/splashmx/editor/web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="inspect-raw"', index)
        self.assertIn('<details id="inspect-raw">', index)
        self.assertIn('id="inspect-summary"', index)
        self.assertIn('id="shortcuts-help"', index)
        self.assertIn('aria-keyshortcuts="Alt+["', index)
        self.assertIn('aria-keyshortcuts="Control+0"', index)


if __name__ == "__main__":
    unittest.main()
