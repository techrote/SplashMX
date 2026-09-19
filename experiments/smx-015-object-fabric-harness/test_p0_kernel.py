from __future__ import annotations

from copy import deepcopy
import unittest

from fixtures import make_world
from model import FabricError, IdentityError, Thing

class P0UniversalKernelTests(unittest.TestCase):
    def test_materially_different_corpus_cases_use_one_thing_type(self) -> None:
        world, _, _ = make_world()
        cases = [("drawing", {"visual", "timeline"}), ("slider", {"ui", "interaction"}), ("music", {"audio", "timeline"}), ("player", {"physics", "gameplay"}), ("generator", {"procedural", "simulation"}), ("server-state", {"persistence", "network"})]
        for thing_id, facets in cases:
            world.add_thing(Thing(thing_id, facets=facets))
        self.assertEqual({type(t) for t in world.things.values()}, {Thing})
        self.assertEqual(len(world.things), len(cases))

    def test_multiple_relationships_are_independent_of_containment(self) -> None:
        world, _, _ = make_world()
        for thing_id in ("world", "car", "driver", "observer"):
            world.add_thing(Thing(thing_id))
        world.reparent("driver", "car")
        world.controller_by_thing["car"] = "driver"
        world.authority_by_thing["car"] = "server"
        world.persistence_by_thing["car"] = "world-save"
        world.replication_by_thing["car"] = "shared"
        world.observer_by_thing["car"] = "observer"
        before = (world.controller_by_thing["car"], world.authority_by_thing["car"], world.persistence_by_thing["car"], world.replication_by_thing["car"], world.observer_by_thing["car"])
        world.reparent("driver", "world")
        after = (world.controller_by_thing["car"], world.authority_by_thing["car"], world.persistence_by_thing["car"], world.replication_by_thing["car"], world.observer_by_thing["car"])
        self.assertEqual(before, after)

    def test_duplicate_thing_identity_fails_closed(self) -> None:
        world, _, _ = make_world(); world.add_thing(Thing("thing:x"))
        with self.assertRaises(IdentityError): world.add_thing(Thing("thing:x"))

    def test_destroyed_identity_is_not_reusable(self) -> None:
        world, _, _ = make_world(); world.add_thing(Thing("thing:x")); world.destroy("thing:x")
        self.assertEqual(world.resolve_ref("thing:x"), "tombstoned")
        with self.assertRaises(IdentityError): world.add_thing(Thing("thing:x"))

    def test_containment_cycle_is_rejected_without_relationship_mutation(self) -> None:
        world, _, _ = make_world()
        for thing_id in ("a", "b", "c"): world.add_thing(Thing(thing_id))
        world.reparent("b", "a"); world.reparent("c", "b"); before = deepcopy(world.parent_by_child)
        with self.assertRaises(FabricError): world.reparent("a", "c")
        self.assertEqual(world.parent_by_child, before)
