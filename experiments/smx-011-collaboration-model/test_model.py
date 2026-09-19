from __future__ import annotations

import itertools
import unittest

from model import (
    CollaborationValidationError,
    CollaborationWorkspace,
    DuplicateTransactionError,
    Operation,
    Transaction,
)


def asset_bundle(tag: str) -> dict:
    return {
        "digest": f"sha256:{tag}",
        "source": {"master_digest": f"sha256:master-{tag}", "media_type": "audio/flac", "logical_source": f"source:{tag}"},
        "audio": {"channels": 2, "sample_rate": 48000, "semantic_role": "music"},
        "provenance": {"author": f"author-{tag}", "license": "CC-BY-4.0", "derived_from": f"master:{tag}"},
    }


def base_state() -> dict:
    return {
        "document_id": "doc:collab",
        "revision_id": "rev:base",
        "schema_version": 1,
        "things": {
            "world": {"parent": None, "props": {"name": "World"}, "ports": [], "existence": "present"},
            "x": {"parent": "world", "props": {"title": "base", "left": 0, "right": 0}, "ports": ["out"], "existence": "present"},
            "y": {"parent": "world", "props": {"value": 0}, "ports": ["in"], "existence": "present"},
            "a": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
            "b": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
            "c": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
        },
        "catalog_status": {"world": "loaded", "x": "loaded", "y": "loaded", "a": "loaded", "b": "loaded", "c": "loaded"},
        "definitions": {"def:widget": {"revision_id": "defrev:1", "elements": {"body": {"color": "white"}, "label": {"text": "hello"}}}},
        "instances": {"inst:widget": {"definition_id": "def:widget", "base_revision_id": "defrev:1", "component_version": "1.0.0", "overlays": {}}},
        "connections": {"conn:base": {"source_thing": "x", "source_port": "out", "target_thing": "y", "target_port": "in", "tombstoned": False}},
        "keyframes": {},
        "groups": {},
        "assets": {"asset:music": {"asset_id": "asset:music", "label": "Theme", "revision_bundle": asset_bundle("base")}},
    }


def op(kind: str, target: str, **data) -> Operation:
    return Operation(kind, target, data)


def tx(tx_id: str, actor: str, *operations: Operation, deps=(), permission_epoch: int = 1, schema_version: int = 1, inverse_of: str | None = None, resolves=()) -> Transaction:
    return Transaction(tx_id, actor, tuple(operations), frozenset(deps), permission_epoch, schema_version, inverse_of, frozenset(resolves))


def conflict_kinds(result) -> list[str]:
    return [item.kind for item in result.conflicts]


class CollaborationSemanticTests(unittest.TestCase):
    def test_cf001_independent_property_edits_merge_regardless_of_arrival_order(self):
        a = tx("tx:a", "alice", op("set_property", "x", key="left", value=1))
        b = tx("tx:b", "bob", op("set_property", "x", key="right", value=2))
        snapshots = []
        for order in ((a, b), (b, a)):
            w = CollaborationWorkspace(base_state())
            for item in order: w.add(item)
            snapshots.append(w.canonical_snapshot())
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(snapshots[0]["things"]["x"]["props"]["left"], 1)
        self.assertEqual(snapshots[0]["things"]["x"]["props"]["right"], 2)

    def test_cf002_same_property_keeps_prior_coherent_value_and_both_proposals(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_property", "x", key="title", value="A")))
        w.add(tx("tx:b", "bob", op("set_property", "x", key="title", value="B")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertEqual(conflict_kinds(result), ["same_property"])
        self.assertEqual(set(result.conflicts[0].tx_ids), {"tx:a", "tx:b"})

    def test_cf003_delete_edit_is_remove_wins_without_resurrection(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:delete", "alice", op("delete_thing", "x")))
        w.add(tx("tx:edit", "bob", op("set_property", "x", key="title", value="late")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["existence"], "tombstoned")
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertIn("delete_edit", conflict_kinds(result))
        self.assertIn("tx:delete", result.applied)
        self.assertNotIn("tx:edit", result.applied)

    def test_cf004_reparent_reparent_holds_prior_legal_parent(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("reparent", "x", parent="a")))
        w.add(tx("tx:b", "bob", op("reparent", "x", parent="b")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["parent"], "world")
        self.assertEqual(conflict_kinds(result), ["reparent"])

    def test_cf005_compatible_definition_edit_and_instance_overlay_both_survive(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:def", "alice", op("definition_set", "def:widget", element="body", key="color", value="blue")))
        w.add(tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")))
        result = w.materialize()
        self.assertEqual(result.state["definitions"]["def:widget"]["elements"]["body"]["color"], "blue")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")
        self.assertEqual(result.conflicts, ())

    def test_cf006_definition_removal_versus_overlay_is_explicit_atomic_conflict(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:remove", "alice", op("definition_remove_element", "def:widget", element="body")))
        w.add(tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")))
        result = w.materialize()
        self.assertIn("body", result.state["definitions"]["def:widget"]["elements"])
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"], {})
        self.assertEqual(conflict_kinds(result), ["definition_instance"])

    def test_cf007_reparent_and_connection_through_stable_port_merge(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:move", "alice", op("reparent", "x", parent="a")))
        w.add(tx("tx:connect", "bob", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["parent"], "a")
        self.assertEqual(result.state["connections"]["conn:new"]["source_thing"], "x")
        self.assertEqual(result.conflicts, ())

    def test_cf008_port_removal_versus_new_connection_is_protected_conflict(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:port", "alice", op("delete_port", "x", port="out")))
        w.add(tx("tx:connect", "bob", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")))
        result = w.materialize()
        self.assertIn("out", result.state["things"]["x"]["ports"])
        self.assertNotIn("conn:new", result.state["connections"])
        self.assertEqual(conflict_kinds(result), ["structure_connection"])

    def test_cf009_independent_keyframes_merge(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_keyframe", "kf:a", track="t", time=1, value=10)))
        w.add(tx("tx:b", "bob", op("set_keyframe", "kf:b", track="t", time=2, value=20)))
        result = w.materialize()
        self.assertEqual(set(result.state["keyframes"]), {"kf:a", "kf:b"})
        self.assertEqual(result.conflicts, ())

    def test_cf010_overlapping_keyframe_locus_is_explicit_conflict(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_keyframe", "kf:a", track="t", time=1, value=10)))
        w.add(tx("tx:b", "bob", op("set_keyframe", "kf:b", track="t", time=1, value=20)))
        result = w.materialize()
        self.assertEqual(result.state["keyframes"], {})
        self.assertEqual(conflict_kinds(result), ["timeline_overlap"])

    def test_cf011_overlapping_grouping_commands_remain_atomic(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:ab", "alice", op("group", "group:ab", members=["a", "b"])))
        w.add(tx("tx:bc", "bob", op("group", "group:bc", members=["b", "c"])))
        result = w.materialize()
        self.assertEqual(result.state["groups"], {})
        self.assertEqual(result.state["things"]["b"]["parent"], "world")
        self.assertEqual(conflict_kinds(result), ["group_overlap"])

    def test_cf012_compatible_component_update_preserves_local_overlay(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:update", "alice", op("component_update", "inst:widget", from_version="1.0.0", to_version="1.1.0", migration_ok=True)))
        w.add(tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")))
        result = w.materialize()
        self.assertEqual(result.state["instances"]["inst:widget"]["component_version"], "1.1.0")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")

    def test_cf013_incompatible_component_update_is_held_while_local_edit_survives(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:update", "alice", op("component_update", "inst:widget", from_version="1.0.0", to_version="2.0.0", migration_ok=False)))
        w.add(tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")))
        result = w.materialize()
        self.assertEqual(result.state["instances"]["inst:widget"]["component_version"], "1.0.0")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")
        self.assertIn("component_update_local_edit", conflict_kinds(result))

    def test_cf014_connection_remove_wins_same_id_recreate(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:delete", "alice", op("delete_connection", "conn:base")))
        w.add(tx("tx:create", "bob", op("create_connection", "conn:base", source_thing="x", source_port="out", target_thing="y", target_port="in")))
        result = w.materialize()
        self.assertTrue(result.state["connections"]["conn:base"]["tombstoned"])
        self.assertIn("connection_remove_recreate", conflict_kinds(result))

    def test_cf015_offline_reconnect_unions_change_sets_and_converges(self):
        left = CollaborationWorkspace(base_state()); right = CollaborationWorkspace(base_state())
        left.add(tx("tx:left", "alice", op("set_property", "x", key="left", value=9)))
        right.add(tx("tx:right", "bob", op("set_property", "x", key="right", value=8)))
        left.sync_from(right); right.sync_from(left)
        self.assertEqual(left.persisted_collaboration_snapshot(), right.persisted_collaboration_snapshot())
        self.assertEqual(left.canonical_snapshot()["things"]["x"]["props"]["left"], 9)
        self.assertEqual(left.canonical_snapshot()["things"]["x"]["props"]["right"], 8)

    def test_cf016_asset_rename_and_replacement_merge_without_changing_asset_id(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:rename", "alice", op("asset_rename", "asset:music", label="New Theme", expected_label="Theme")))
        w.add(tx("tx:replace", "bob", op("asset_replace", "asset:music", bundle=asset_bundle("next"), expected_digest="sha256:base")))
        result = w.materialize(); asset = result.state["assets"]["asset:music"]
        self.assertEqual(asset["asset_id"], "asset:music")
        self.assertEqual(asset["label"], "New Theme")
        self.assertEqual(asset["revision_bundle"], asset_bundle("next"))

    def test_cf017_concurrent_asset_replacements_never_field_mix_source_audio_provenance(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("asset_replace", "asset:music", bundle=asset_bundle("A"))))
        w.add(tx("tx:b", "bob", op("asset_replace", "asset:music", bundle=asset_bundle("B"))))
        result = w.materialize()
        self.assertEqual(result.state["assets"]["asset:music"]["revision_bundle"], asset_bundle("base"))
        self.assertEqual(conflict_kinds(result), ["asset_replacement"])

    def test_cf018_selective_undo_is_compensating_transaction_and_preserves_remote_work(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_property", "x", key="left", value=1)))
        w.add(tx("tx:b", "bob", op("set_property", "x", key="right", value=2)))
        w.add(tx("tx:undo-a", "alice", op("set_property", "x", key="left", value=0, expected=1), deps=("tx:a", "tx:b"), inverse_of="tx:a"))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertEqual(result.state["things"]["x"]["props"]["right"], 2)

    def test_cf019_undo_precondition_cannot_clobber_later_edit(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_property", "x", key="left", value=1)))
        w.add(tx("tx:b", "bob", op("set_property", "x", key="left", value=2), deps=("tx:a",)))
        w.add(tx("tx:undo", "alice", op("set_property", "x", key="left", value=0, expected=1), deps=("tx:b",), inverse_of="tx:a"))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 2)
        self.assertIn("precondition_failed", conflict_kinds(result))

    def test_cf020_stale_permission_epoch_is_rejected_but_history_retained(self):
        w = CollaborationWorkspace(base_state(), permission_epochs={"alice": 2})
        w.add(tx("tx:offline", "alice", op("set_property", "x", key="title", value="offline"), permission_epoch=1))
        snapshot = w.persisted_collaboration_snapshot()
        self.assertEqual(snapshot["canonical"]["things"]["x"]["props"]["title"], "base")
        self.assertEqual(snapshot["rejections"], [{"tx_id": "tx:offline", "reason": "permission_epoch_changed"}])
        self.assertIn("tx:offline", snapshot["history"])

    def test_cf021_presence_cursor_selection_are_ephemeral(self):
        w = CollaborationWorkspace(base_state())
        before = w.persisted_collaboration_snapshot()
        w.set_presence("alice", {"cursor": [4, 8], "selection": ["x"]})
        self.assertNotEqual(w.ephemeral_presence(), {})
        self.assertEqual(w.persisted_collaboration_snapshot(), before)

    def test_cf022_runtime_multiplayer_fields_or_operations_are_rejected(self):
        w = CollaborationWorkspace(base_state())
        with self.assertRaises(CollaborationValidationError):
            w.add(tx("tx:peer", "alice", op("set_property", "x", key="left", value=1, peer_id=7)))
        with self.assertRaises(CollaborationValidationError):
            w.add(tx("tx:runtime", "alice", op("runtime_state", "x", value=1)))

    def test_cf023_identical_replay_is_idempotent_but_transaction_id_collision_rejected(self):
        w = CollaborationWorkspace(base_state())
        original = tx("tx:a", "alice", op("set_property", "x", key="left", value=1))
        w.add(original); w.add(original)
        self.assertEqual(w.canonical_snapshot()["things"]["x"]["props"]["left"], 1)
        with self.assertRaises(DuplicateTransactionError):
            w.add(tx("tx:a", "alice", op("set_property", "x", key="left", value=9)))

    def test_cf024_known_unloaded_target_pends_then_applies_when_materialized(self):
        state = base_state(); state["catalog_status"]["x"] = "known_unloaded"
        w = CollaborationWorkspace(state); w.add(tx("tx:a", "alice", op("set_property", "x", key="left", value=4)))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertEqual(result.pending[0].reason, "known_unloaded_target")
        state2 = base_state(); w2 = CollaborationWorkspace(state2); w2.add(next(iter(w.transactions.values())))
        self.assertEqual(w2.canonical_snapshot()["things"]["x"]["props"]["left"], 4)

    def test_cf025_tombstoned_target_rejects_late_edit_without_resurrection(self):
        state = base_state(); state["catalog_status"]["x"] = "tombstoned"; state["things"]["x"]["existence"] = "tombstoned"
        w = CollaborationWorkspace(state); w.add(tx("tx:late", "alice", op("set_property", "x", key="left", value=4)))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["existence"], "tombstoned")
        self.assertIn("target_tombstoned", conflict_kinds(result))

    def test_cf026_schema_mismatch_is_quarantined_for_migration(self):
        w = CollaborationWorkspace(base_state()); w.add(tx("tx:future", "alice", op("set_property", "x", key="left", value=4), schema_version=2))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertEqual(result.rejections[0].reason, "schema_migration_required")

    def test_cf027_explicit_resolution_transaction_supersedes_held_proposals_without_rewriting_history(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_property", "x", key="title", value="A")))
        w.add(tx("tx:b", "bob", op("set_property", "x", key="title", value="B")))
        w.add(tx("tx:resolve", "alice", op("set_property", "x", key="title", value="B", expected="base"), deps=("tx:a", "tx:b"), resolves=("tx:a", "tx:b")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "B")
        self.assertEqual(result.conflicts, ())
        self.assertEqual(len(result.resolved_conflicts), 1)
        self.assertEqual(set(w.transactions), {"tx:a", "tx:b", "tx:resolve"})

    def test_cf028_every_arrival_permutation_produces_same_canonical_and_conflict_snapshot(self):
        items = [
            tx("tx:a", "alice", op("set_property", "x", key="title", value="A")),
            tx("tx:b", "bob", op("set_property", "x", key="title", value="B")),
            tx("tx:c", "carol", op("set_property", "x", key="right", value=3)),
        ]
        snapshots = []
        for order in itertools.permutations(items):
            w = CollaborationWorkspace(base_state())
            for item in order: w.add(item)
            snapshots.append(w.persisted_collaboration_snapshot())
        self.assertTrue(all(item == snapshots[0] for item in snapshots[1:]))
        self.assertEqual(snapshots[0]["canonical"]["things"]["x"]["props"]["title"], "base")
        self.assertEqual(snapshots[0]["canonical"]["things"]["x"]["props"]["right"], 3)

    def test_boundary_transaction_atomicity_dominates_pairwise_remove_wins(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("delete_thing", "y"), op("set_property", "x", key="title", value="A")))
        w.add(tx("tx:b", "bob", op("set_property", "y", key="value", value=7), op("set_property", "x", key="title", value="B")))
        result = w.materialize()
        self.assertEqual(result.state["things"]["y"]["existence"], "present")
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertIn("delete_edit", conflict_kinds(result)); self.assertIn("same_property", conflict_kinds(result))
        self.assertNotIn("tx:a", result.applied); self.assertNotIn("tx:b", result.applied)

    def test_boundary_incomplete_asset_revision_bundle_is_rejected(self):
        w = CollaborationWorkspace(base_state()); incomplete = asset_bundle("next"); incomplete.pop("provenance")
        with self.assertRaises(CollaborationValidationError):
            w.add(tx("tx:bad", "alice", op("asset_replace", "asset:music", bundle=incomplete)))

    def test_boundary_causal_dependency_cycle_is_rejected(self):
        w = CollaborationWorkspace(base_state())
        w.add(tx("tx:a", "alice", op("set_property", "x", key="left", value=1), deps=("tx:b",)))
        w.add(tx("tx:b", "bob", op("set_property", "x", key="right", value=2), deps=("tx:a",)))
        with self.assertRaises(CollaborationValidationError): w.materialize()


if __name__ == "__main__":
    unittest.main()
