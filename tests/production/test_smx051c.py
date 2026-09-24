from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from splashmx.editor.authoring import AuthoringSession
from splashmx.editor.browser_runtime import BrowserRuntimeError
from splashmx.editor.browser_server import BrowserBridge
from splashmx.editor.godot_play import (
    EDITOR_GODOT_PLAY_CONTRACT,
    EditorGodotPlayError,
    build_editor_godot_play_projection,
)


class SMX051CGodotPlayTests(unittest.TestCase):
    def _session(self) -> AuthoringSession:
        session = AuthoringSession.blank("smx051c-tests")
        thing = session.create_thing(
            label="Sprite",
            thing_id="sprite",
            authored_state={
                "visual": {
                    "x": 40,
                    "y": 50,
                    "width": 120,
                    "height": 80,
                    "rotation": 0,
                    "shape": "rectangle",
                    "fill": "#336699",
                }
            },
        )
        session.add_timeline_track(
            thing,
            property_name="visual.x",
            keyframes=[{"tick": 0, "value": 40}, {"tick": 60, "value": 160}],
            track_id="move-x",
        )
        return session

    def test_projection_preserves_stable_identity_visual_and_timeline(self) -> None:
        session = self._session()
        projection = build_editor_godot_play_projection(session.project)
        self.assertEqual(projection["contract"], EDITOR_GODOT_PLAY_CONTRACT)
        self.assertEqual(projection["project_revision_id"], str(session.document.project_revision_id))
        self.assertEqual(projection["required_features"], ["render_2d"])
        self.assertEqual(len(projection["things"]), 1)
        thing = projection["things"][0]
        self.assertEqual(thing["thing_id"], "sprite")
        self.assertEqual(thing["visual"]["fill"], "#336699")
        self.assertEqual(
            thing["timeline_tracks"],
            [{
                "property": "visual.x",
                "keyframes": [{"tick": 0.0, "value": 40.0}, {"tick": 60.0, "value": 160.0}],
            }],
        )

    def test_unsupported_timeline_property_is_not_promoted_to_godot_semantics(self) -> None:
        session = self._session()
        thing = next(iter(session.document.things))
        session.add_timeline_track(
            thing,
            property_name="custom.score",
            keyframes=[{"tick": 0, "value": 1}, {"tick": 60, "value": 2}],
            track_id="score",
        )
        projection = build_editor_godot_play_projection(session.project)
        tracks = projection["things"][0]["timeline_tracks"]
        self.assertEqual([row["property"] for row in tracks], ["visual.x"])

    def test_transient_engine_identity_in_track_is_rejected(self) -> None:
        session = self._session()
        thing = next(iter(session.document.things))
        authored = dict(session.document.things[thing].authored_state)
        tracks = [dict(row) for row in authored["timeline_tracks"]]
        tracks[0]["NodePath"] = "/root/Leak"
        authored["timeline_tracks"] = tracks
        session.document.things[thing] = session.document.things[thing].__class__(
            session.document.things[thing].thing_id,
            session.document.things[thing].label,
            authored,
            session.document.things[thing].ports,
            session.document.things[thing].behaviours,
            session.document.things[thing].tombstoned,
        )
        with self.assertRaises(EditorGodotPlayError) as caught:
            build_editor_godot_play_projection(session.project)
        self.assertEqual(caught.exception.code, "godot.forbidden_transient_identity")

    def test_bridge_reports_runtime_availability_and_requires_active_play(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp) / "web"
            web.mkdir()
            (web / "index.html").write_text("<!doctype html><title>runtime</title>", encoding="utf-8")
            bridge = BrowserBridge(
                self._session(),
                store_path=Path(tmp) / "project.sqlite3",
                godot_web_root=web,
            )
            try:
                state = bridge.state()
                self.assertTrue(state["godot_player"]["available"])
                self.assertEqual(state["godot_player"]["runtime"], "Godot 4.7.2")
                with self.assertRaises(BrowserRuntimeError) as caught:
                    bridge.godot_play_projection()
                self.assertEqual(caught.exception.code, "browser.play_not_active")
                bridge.apply({"action": "play", "data": {}})
                projection = bridge.godot_play_projection()
                self.assertEqual(projection["contract"], EDITOR_GODOT_PLAY_CONTRACT)
                bridge.apply({"action": "stop", "data": {}})
            finally:
                bridge.close()

    def test_bridge_without_runtime_reports_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = BrowserBridge(self._session(), store_path=Path(tmp) / "project.sqlite3")
            try:
                self.assertFalse(bridge.state()["godot_player"]["available"])
            finally:
                bridge.close()

    def test_invalid_runtime_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                BrowserBridge(
                    self._session(),
                    store_path=Path(tmp) / "project.sqlite3",
                    godot_web_root=Path(tmp) / "missing",
                )


if __name__ == "__main__":
    unittest.main()
