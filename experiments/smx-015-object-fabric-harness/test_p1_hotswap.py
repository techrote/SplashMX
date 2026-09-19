from __future__ import annotations

from copy import deepcopy
import unittest

from fixtures import make_world
from model import SwapError, Thing

class P1HotSwapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world, self.store, self.catalog = make_world()
        self.world.add_thing(Thing("actor"))
        self.world.attach_behavior("actor", "motion", "move", 1)
        self.world.things["actor"].attachments["motion"].private_state["speed"] = 7

    def test_compatible_swap_preserves_thing_attachment_and_private_state(self) -> None:
        thing_object_id = id(self.world.things["actor"])
        self.world.swap_behavior("actor", "motion", "move", 2)
        attachment = self.world.things["actor"].attachments["motion"]
        self.assertEqual(self.world.things["actor"].thing_id, "actor")
        self.assertEqual(id(self.world.things["actor"]), thing_object_id)
        self.assertEqual(attachment.attachment_id, "motion")
        self.assertEqual(attachment.private_state, {"speed": 7})
        self.assertEqual(attachment.revision, 2)

    def test_pending_work_requires_explicit_continuation_mapping(self) -> None:
        self.world.schedule(work_id="w1", thing_id="actor", attachment_id="motion", handler="resume", payload={"x": 1}, delay=5)
        before = deepcopy(self.world.things["actor"].attachments["motion"])
        with self.assertRaises(SwapError): self.world.swap_behavior("actor", "motion", "move", 2)
        self.assertEqual(self.world.things["actor"].attachments["motion"], before)
        self.assertEqual(self.world.pending_work[0].handler, "resume")
        self.world.swap_behavior("actor", "motion", "move", 2, continuation_map={"resume": "continue"})
        self.assertEqual(self.world.pending_work[0].handler, "continue")

    def test_incompatible_private_state_requires_explicit_migration(self) -> None:
        before = deepcopy(self.world.things["actor"].attachments["motion"])
        with self.assertRaises(SwapError): self.world.swap_behavior("actor", "motion", "move", 3)
        self.assertEqual(self.world.things["actor"].attachments["motion"], before)
        self.world.swap_behavior("actor", "motion", "move", 3, migration={"velocity": "$old.speed", "mode": "walk"})
        self.assertEqual(self.world.things["actor"].attachments["motion"].private_state, {"velocity": 7, "mode": "walk"})

    def test_bad_migration_is_atomic(self) -> None:
        before = deepcopy(self.world.things["actor"].attachments["motion"])
        with self.assertRaises(SwapError): self.world.swap_behavior("actor", "motion", "move", 3, migration={"velocity": "$old.missing", "mode": "walk"})
        self.assertEqual(self.world.things["actor"].attachments["motion"], before)

    def test_new_artifact_failure_prevents_live_swap(self) -> None:
        self.store.set_availability("artifact:move-v2", "revoked")
        before = deepcopy(self.world.things["actor"].attachments["motion"])
        with self.assertRaises(SwapError): self.world.swap_behavior("actor", "motion", "move", 2)
        self.assertEqual(self.world.things["actor"].attachments["motion"], before)

    def test_connected_semantic_port_survives_behavior_swap(self) -> None:
        self.world.things["actor"].ports.add("command:move")
        external_connection = ("actor", "command:move")
        self.world.swap_behavior("actor", "motion", "move", 2)
        self.assertEqual(external_connection, ("actor", "command:move"))
        self.assertIn("command:move", self.world.things["actor"].ports)
