from __future__ import annotations

from copy import deepcopy
import unittest

from fixtures import make_world
from model import AcquisitionError, SwapError, Thing

class P4StreamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world, self.store, self.catalog = make_world()
        self.world.add_thing(Thing("inventory", refs={"key_target": "door"}))
        self.world.add_thing(Thing("town", facets={"group"}))
        self.world.add_thing(Thing("door", state={"locked": True}, runtime_required_artifacts={"artifact:audio"}))
        self.world.reparent("door", "town")
        self.world.attach_behavior("door", "motion", "move", 1)

    def test_inventory_reference_distinguishes_unloaded_from_destroyed(self) -> None:
        self.world.unload(["town", "door"])
        self.assertEqual(self.world.things["inventory"].refs["key_target"], "door")
        self.assertEqual(self.world.resolve_ref("door"), "known_unloaded")
        self.world.load(["door"]); self.assertEqual(self.world.resolve_ref("door"), "loaded")
        self.world.destroy("door"); self.assertEqual(self.world.resolve_ref("door"), "tombstoned")

    def test_loading_referenced_door_does_not_load_containment_region(self) -> None:
        self.world.unload(["town", "door"]); self.world.load(["door"])
        self.assertIn("door", self.world.resident); self.assertNotIn("town", self.world.resident)

    def test_failed_dependency_load_has_no_partial_thing_publication(self) -> None:
        self.world.unload(["door"]); self.store.set_availability("artifact:audio", "offline"); before = set(self.world.resident)
        with self.assertRaises(AcquisitionError): self.world.load(["door"])
        self.assertEqual(self.world.resident, before); self.assertEqual(self.world.resolve_ref("door"), "known_unloaded")

    def test_tampered_dependency_load_has_no_partial_publication(self) -> None:
        self.world.unload(["door"]); self.store.tamper("artifact:audio", b"different-but-invalid"); before = set(self.world.resident)
        with self.assertRaises(AcquisitionError): self.world.load(["door"])
        self.assertEqual(self.world.resident, before)

    def test_unloaded_behavior_can_migrate_then_rehydrate_with_same_thing_id(self) -> None:
        self.world.unload(["door"]); self.world.things["door"].attachments["motion"].private_state["speed"] = 9
        self.world.schedule(work_id="resume", thing_id="door", attachment_id="motion", handler="resume", delay=20)
        self.world.swap_behavior("door", "motion", "move", 3, migration={"velocity": "$old.speed", "mode": "walk"}, continuation_map={"resume": "continue"})
        self.world.load(["door"]); attachment = self.world.things["door"].attachments["motion"]
        self.assertEqual(self.world.things["door"].thing_id, "door")
        self.assertEqual(attachment.private_state, {"velocity": 9, "mode": "walk"})
        self.assertEqual(self.world.pending_work[0].handler, "continue")

    def test_failed_unloaded_migration_rolls_back_before_rehydrate(self) -> None:
        self.world.unload(["door"]); before = deepcopy(self.world.things["door"].attachments["motion"])
        with self.assertRaises(SwapError): self.world.swap_behavior("door", "motion", "move", 3)
        self.assertEqual(self.world.things["door"].attachments["motion"], before)
        self.world.load(["door"]); self.assertEqual(self.world.things["door"].attachments["motion"].revision, 1)

    def test_resident_creation_with_missing_dependency_is_atomic(self) -> None:
        before_things = deepcopy(self.world.things); before_resident = set(self.world.resident)
        candidate = Thing("late-object", runtime_required_artifacts={"artifact:missing"})
        with self.assertRaises(AcquisitionError): self.world.add_thing(candidate)
        self.assertEqual(self.world.things, before_things); self.assertEqual(self.world.resident, before_resident); self.assertNotIn("late-object", self.world.things)
