"""SMX-051E grouping, reusable Definition and Library workflow regressions."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from splashmx.canonical.core import DefinitionId, ElementId, RelationshipKind, ThingId
from splashmx.editor.authoring import AuthoringError, AuthoringSession
from splashmx.editor.browser_runtime import BrowserRuntimeSession
from splashmx.editor.godot_play import build_editor_godot_play_projection


def visual(x: float, y: float, fill: str) -> dict[str, object]:
    return {
        "visual": {
            "x": x,
            "y": y,
            "width": 120,
            "height": 80,
            "rotation": 0,
            "shape": "rectangle",
            "fill": fill,
        }
    }


class SMX051EGroupingLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = AuthoringSession.blank("smx051e-test")

    def _active_parent(self, child: ThingId) -> ThingId | None:
        for relation in self.session.document.relationships.values():
            if (
                not relation.tombstoned
                and relation.kind is RelationshipKind.CONTAINS
                and relation.target == child
            ):
                return relation.source
        return None

    def _pair(self) -> tuple[ThingId, ThingId, ThingId]:
        first = self.session.create_thing(
            label="First",
            thing_id="first",
            authored_state=visual(40, 50, "#336699"),
        )
        second = self.session.create_thing(
            label="Second",
            thing_id="second",
            authored_state=visual(220, 80, "#cc6633"),
        )
        group = self.session.group_things([first, second], label="Pair", group_id="pair")
        return first, second, group

    def test_group_move_and_ungroup_preserve_concrete_child_identity(self) -> None:
        first, second, group = self._pair()
        self.assertNotIn("visual", self.session.document.things[group].authored_state)
        first_before = dict(self.session.document.things[first].authored_state["visual"])
        second_before = dict(self.session.document.things[second].authored_state["visual"])

        moved = self.session.move_group(group, dx=25, dy=-10)
        self.assertEqual(set(moved), {first, second})
        self.assertEqual(self.session.document.things[first].authored_state["visual"]["x"], first_before["x"] + 25)
        self.assertEqual(self.session.document.things[first].authored_state["visual"]["y"], first_before["y"] - 10)
        self.assertEqual(self.session.document.things[second].authored_state["visual"]["x"], second_before["x"] + 25)
        self.assertEqual(self.session.document.things[second].authored_state["visual"]["y"], second_before["y"] - 10)
        self.assertEqual(self._active_parent(first), group)
        self.assertEqual(self._active_parent(second), group)

        children = self.session.ungroup(group)
        self.assertEqual(set(children), {first, second})
        self.assertFalse(self.session.document.things[first].tombstoned)
        self.assertFalse(self.session.document.things[second].tombstoned)
        self.assertTrue(self.session.document.things[group].tombstoned)
        self.assertIsNone(self._active_parent(first))
        self.assertIsNone(self._active_parent(second))
        self.assertEqual(self.session.editor.selection, {first, second})

    def test_make_reusable_and_second_instance_reuse_canonical_definition_lineage(self) -> None:
        first, second, group = self._pair()
        self.session.add_timeline_track(
            first,
            property_name="visual.x",
            keyframes=[{"tick": 0, "value": 40}, {"tick": 60, "value": 140}],
            track_id="move-first",
        )
        self.session.attach_visual_rule(first, attachment_id="click-first", fill="#ff5a5f")

        first_instance_ids = {first, second, group}
        definition_id = self.session.make_reusable(group, definition_id="pair-definition")
        self.assertEqual(definition_id, DefinitionId("pair-definition"))
        self.assertEqual(set(self.session.document.instances[group].thing_by_element.values()), first_instance_ids)
        self.assertEqual(self.session.document.instances[group].root_thing_id, group)
        self.assertTrue(first_instance_ids.issubset(self.session.document.things))

        second_root = self.session.instantiate_reusable(definition_id)
        first_instance = self.session.document.instances[group]
        second_instance = self.session.document.instances[second_root]
        first_concrete = set(first_instance.thing_by_element.values())
        second_concrete = set(second_instance.thing_by_element.values())
        self.assertEqual(first_instance.definition_id, second_instance.definition_id)
        self.assertTrue(first_concrete.isdisjoint(second_concrete))
        self.assertEqual(first_instance.root_thing_id, group)
        self.assertIn(group, self.session.document.things)

        first_element = next(
            element for element, concrete in first_instance.thing_by_element.items()
            if concrete == first
        )
        second_first = second_instance.thing_by_element[first_element]
        second_first_state = self.session.document.things[second_first].authored_state
        self.assertEqual(second_first_state["visual"]["x"], 88.0)
        self.assertEqual(second_first_state["visual"]["y"], 98.0)
        tracks = second_first_state["timeline_tracks"]
        self.assertEqual(tracks[0]["target_thing_id"], str(second_first))
        self.assertEqual(tracks[0]["keyframes"], [{"tick": 0, "value": 88.0}, {"tick": 60, "value": 188.0}])
        self.assertEqual(
            second_instance.state_overrides[first_element]["timeline_tracks"][0]["target_thing_id"],
            str(second_first),
        )

        first_x = self.session.document.things[first].authored_state["visual"]["x"]
        edited = dict(second_first_state["visual"])
        edited["x"] = edited["x"] + 30
        self.session.update_visual_state(second_first, visual=edited)
        self.assertEqual(self.session.document.things[first].authored_state["visual"]["x"], first_x)
        self.assertEqual(
            self.session.document.instances[second_root].state_overrides[first_element]["visual"]["x"],
            edited["x"],
        )

        projection = build_editor_godot_play_projection(self.session.project)
        projected_ids = {row["thing_id"] for row in projection["things"]}
        self.assertIn(str(first), projected_ids)
        self.assertIn(str(second_first), projected_ids)
        self.assertNotIn(str(group), projected_ids)
        self.assertNotIn(str(second_root), projected_ids)
        projected_copy = next(row for row in projection["things"] if row["thing_id"] == str(second_first))
        self.assertEqual(projected_copy["timeline_tracks"][0]["keyframes"][-1]["value"], 188.0)
        projected_first = next(row for row in projection["things"] if row["thing_id"] == str(first))
        self.assertIn("pointer_click", projected_first["interactive_events"])

    def test_reusable_instances_cannot_be_silently_ungrouped(self) -> None:
        _, _, group = self._pair()
        self.session.make_reusable(group, definition_id="pair-definition")
        before = self.session.document
        with self.assertRaises(AuthoringError) as caught:
            self.session.ungroup(group)
        self.assertEqual(caught.exception.code, "authoring.reusable_ungroup_unsupported")
        self.assertEqual(self.session.document, before)

    def test_save_reload_and_fresh_runtime_restore_group_definition_and_instances(self) -> None:
        first, second, group = self._pair()
        definition = self.session.make_reusable(group, definition_id="pair-definition")
        second_root = self.session.instantiate_reusable(definition)
        expected_first_mapping = dict(self.session.document.instances[group].thing_by_element)
        expected_second_mapping = dict(self.session.document.instances[second_root].thing_by_element)

        with tempfile.TemporaryDirectory() as temp:
            store = Path(temp) / "project.sqlite3"
            runtime = BrowserRuntimeSession(self.session, store)
            saved = runtime.save()
            self.assertEqual(saved["saved_revision_id"], str(self.session.document.project_revision_id))

            runtime.authoring.move_group(second_root, dx=15, dy=20)
            runtime.reload()
            self.session = runtime.authoring
            self.assertEqual(self.session.document.instances[group].thing_by_element, expected_first_mapping)
            self.assertEqual(self.session.document.instances[second_root].thing_by_element, expected_second_mapping)

            restarted = BrowserRuntimeSession(AuthoringSession.blank("smx051e-test"), store)
            restarted.reload()
            restored = restarted.authoring
            self.assertIn(group, restored.document.instances)
            self.assertIn(second_root, restored.document.instances)
            self.assertEqual(restored.document.instances[group].definition_id, definition)
            self.assertEqual(restored.document.instances[second_root].definition_id, definition)
            self.assertEqual(restored.document.instances[group].thing_by_element, expected_first_mapping)
            self.assertEqual(restored.document.instances[second_root].thing_by_element, expected_second_mapping)
            self.assertFalse(restored.document.things[first].tombstoned)
            self.assertFalse(restored.document.things[second].tombstoned)

    def test_snapshot_keeps_library_internal_ids_out_of_author_copy_contract(self) -> None:
        first, second, group = self._pair()
        definition = self.session.make_reusable(group, definition_id="pair-definition")
        self.session.instantiate_reusable(definition)
        snapshot = self.session.snapshot()
        rows = [row for row in snapshot["canonical"]["definitions"] if row["definition_id"] == str(definition)]
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["root_thing_id"] for row in rows}, set(map(str, self.session.document.instances)))
        self.assertTrue(all(row["element_count"] == 3 for row in rows))
        self.assertEqual({thing.thing_id for thing in self.session.document.things.values() if not thing.tombstoned} >= {first, second, group}, True)


if __name__ == "__main__":
    unittest.main()
