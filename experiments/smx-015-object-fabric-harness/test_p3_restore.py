from __future__ import annotations

from copy import deepcopy
import json
import unittest

from fixtures import asset_bundle, make_world
from model import CompatibilityError, FabricWorld, IdentityError, Thing

class P3RestoreTests(unittest.TestCase):
    def make_snapshot_world(self):
        world, store, catalog = make_world()
        world.add_thing(Thing("town", facets={"group"}))
        world.add_thing(Thing("door", state={"open": False}, ports={"unlock"}, refs={"key": "key"}))
        world.add_thing(Thing("key", state={"uses": 3}, refs={"door": "door"}))
        world.reparent("door", "town")
        world.attach_behavior("door", "motion", "move", 1)
        world.things["door"].attachments["motion"].private_state["speed"] = 5
        world.schedule(work_id="timer:close", thing_id="door", attachment_id="motion", handler="resume", payload={"reason": "timeout"}, delay=10)
        world.set_context("door", godot_node="Node2D#123", peer_id=8841, capability_grant={"clipboard": "lease:session"})
        world.replace_asset("door", asset_bundle())
        definition, _ = world.promote_group("town", "def:town", {"town": "root", "door": "door"}, instance_id="inst:town")
        definition.exposures["door_unlock"] = ("door", "unlock")
        world.definitions["def:town"] = definition
        return world, store, catalog

    def test_fresh_runtime_json_roundtrip_preserves_semantic_state(self) -> None:
        world, store, catalog = self.make_snapshot_world()
        snap = json.loads(json.dumps(world.snapshot(snapshot_id="s1"), sort_keys=True))
        restored = FabricWorld.restore(snap, artifact_store=store, behavior_catalog=catalog)
        self.assertIsNot(restored, world)
        self.assertEqual(restored.things["door"].state, {"open": False})
        self.assertEqual(restored.things["door"].refs["key"], "key")
        self.assertEqual(restored.things["key"].refs["door"], "door")
        self.assertEqual(restored.things["door"].attachments["motion"].private_state["speed"], 5)
        self.assertEqual(restored.pending_work[0].work_id, "timer:close")
        self.assertEqual(restored.instances["inst:town"].thing_by_element["door"], "door")

    def test_transient_engine_peer_and_capability_context_is_not_serialized(self) -> None:
        world, _, _ = self.make_snapshot_world(); raw = json.dumps(world.snapshot(snapshot_id="s1"), sort_keys=True)
        self.assertNotIn("Node2D#123", raw); self.assertNotIn("8841", raw); self.assertNotIn("lease:session", raw); self.assertNotIn('"context"', raw)

    def test_restored_context_rebinds_empty(self) -> None:
        world, store, catalog = self.make_snapshot_world()
        restored = FabricWorld.restore(world.snapshot(snapshot_id="s1"), artifact_store=store, behavior_catalog=catalog)
        self.assertEqual(restored.context, {})

    def test_missing_behavior_revision_blocks_restore_before_publication(self) -> None:
        world, store, catalog = self.make_snapshot_world(); reduced = {k: v for k, v in catalog.items() if k != ("move", 1)}
        with self.assertRaises(CompatibilityError): FabricWorld.restore(world.snapshot(snapshot_id="s1"), artifact_store=store, behavior_catalog=reduced)

    def test_duplicate_thing_id_in_snapshot_is_rejected(self) -> None:
        world, store, catalog = self.make_snapshot_world(); snap = world.snapshot(snapshot_id="s1"); snap["things"].append(deepcopy(snap["things"][0]))
        with self.assertRaises(IdentityError): FabricWorld.restore(snap, artifact_store=store, behavior_catalog=catalog)

    def test_live_tombstone_identity_collision_is_rejected(self) -> None:
        world, store, catalog = self.make_snapshot_world(); snap = world.snapshot(snapshot_id="s1"); snap["tombstones"].append("door")
        with self.assertRaises(IdentityError): FabricWorld.restore(snap, artifact_store=store, behavior_catalog=catalog)

    def test_protected_audio_source_and_provenance_bundle_roundtrips_exactly(self) -> None:
        world, store, catalog = self.make_snapshot_world(); expected = deepcopy(world.things["door"].assets["asset:voice"])
        restored = FabricWorld.restore(world.snapshot(snapshot_id="s1"), artifact_store=store, behavior_catalog=catalog)
        self.assertEqual(restored.things["door"].assets["asset:voice"], expected)

    def test_restore_rejects_unknown_or_cyclic_containment_before_publication(self) -> None:
        world, store, catalog = self.make_snapshot_world(); unknown = world.snapshot(snapshot_id="s1"); unknown["parent_by_child"]["door"] = "missing-parent"
        with self.assertRaises(CompatibilityError): FabricWorld.restore(unknown, artifact_store=store, behavior_catalog=catalog)
        cyclic = world.snapshot(snapshot_id="s2"); cyclic["parent_by_child"]["door"] = "town"; cyclic["parent_by_child"]["town"] = "door"
        with self.assertRaises(CompatibilityError): FabricWorld.restore(cyclic, artifact_store=store, behavior_catalog=catalog)
