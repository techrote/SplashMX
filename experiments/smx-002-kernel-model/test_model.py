from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model import Fabric, Facet, Port, Relation, Thing  # noqa: E402


class KernelModelTests(unittest.TestCase):
    def test_reparent_preserves_identity_reference_control_and_authority(self) -> None:
        fabric = Fabric()
        for thing_id in ("bag:a", "bag:b", "thing:key", "thing:door", "controller:player", "authority:server"):
            fabric.add_thing(Thing(thing_id=thing_id, label=thing_id))

        key = fabric.things["thing:key"]
        key.authored_state["material"] = "brass"
        key.live_state["uses"] = 2
        before = key.semantic_snapshot()

        fabric.add_relation(Relation("contains:bag:a:thing:key", "contains", "bag:a", "thing:key"))
        fabric.add_relation(Relation("ref:key:door", "references", "thing:key", "thing:door"))
        fabric.add_relation(Relation("control:key", "controlled_by", "thing:key", "controller:player", scope="runtime"))
        fabric.add_relation(Relation("authority:key", "authority_at", "thing:key", "authority:server", scope="runtime"))

        fabric.reparent("thing:key", "bag:b")

        self.assertEqual(key.semantic_snapshot(), before)
        self.assertEqual(key.thing_id, "thing:key")
        self.assertEqual([r.target for r in fabric.relations_for("thing:key", "references")], ["thing:door"])
        self.assertEqual([r.target for r in fabric.relations_for("thing:key", "controlled_by")], ["controller:player"])
        self.assertEqual([r.target for r in fabric.relations_for("thing:key", "authority_at")], ["authority:server"])
        contains = fabric.relations_for("thing:key", "contains")
        self.assertEqual([(r.source, r.target) for r in contains], [("bag:b", "thing:key")])

    def test_simultaneous_relationships_are_distinct(self) -> None:
        fabric = Fabric()
        ids = [
            "thing:vehicle", "thing:convoy", "controller:player3", "authority:server7",
            "thing:camera", "service:worldsave", "session:room17"
        ]
        for thing_id in ids:
            fabric.add_thing(Thing(thing_id=thing_id, label=thing_id))

        relations = [
            Relation("rel:contains", "contains", "thing:convoy", "thing:vehicle"),
            Relation("rel:control", "controlled_by", "thing:vehicle", "controller:player3", scope="runtime"),
            Relation("rel:authority", "authority_at", "thing:vehicle", "authority:server7", scope="runtime"),
            Relation("rel:observe", "observes", "thing:camera", "thing:vehicle"),
            Relation("rel:persist", "persisted_via", "thing:vehicle", "service:worldsave", scope="runtime"),
            Relation("rel:replicate", "replicated_in", "thing:vehicle", "session:room17", scope="runtime"),
        ]
        for relation in relations:
            fabric.add_relation(relation)

        kinds = {relation.kind for relation in fabric.relations_for("thing:vehicle")}
        self.assertEqual(
            kinds,
            {"contains", "controlled_by", "authority_at", "observes", "persisted_via", "replicated_in"},
        )

    def test_capability_request_is_intrinsic_but_grant_is_context(self) -> None:
        fabric = Fabric()
        component = Thing(thing_id="thing:component", label="Fetcher")
        component.facets["cap:http"] = Facet(
            facet_id="cap:http",
            role="capability_request",
            implementation="capability:http",
            config={"capability": "http.fetch", "optional": True},
        )
        fabric.add_thing(component)

        before = component.semantic_snapshot()
        self.assertFalse(fabric.context.is_granted(component.thing_id, "http.fetch"))
        fabric.context.grant(component.thing_id, "http.fetch", True)
        self.assertTrue(fabric.context.is_granted(component.thing_id, "http.fetch"))
        self.assertEqual(component.semantic_snapshot(), before)

    def test_group_and_leaf_use_same_thing_type(self) -> None:
        fabric = Fabric()
        group = Thing(thing_id="thing:band", label="Band")
        group.facets["coord"] = Facet("coord", "behaviour", "SynchroniseMembers")
        leaf = Thing(thing_id="thing:drummer", label="Drummer")
        fabric.add_thing(group)
        fabric.add_thing(leaf)
        fabric.add_relation(Relation("contains:band:drummer", "contains", "thing:band", "thing:drummer"))

        self.assertIs(type(group), type(leaf))
        self.assertEqual(fabric.relations_for("thing:drummer", "contains")[0].source, "thing:band")

    def test_behaviour_replacement_preserves_thing_identity_and_unrelated_state(self) -> None:
        fabric = Fabric()
        actor = Thing(thing_id="thing:robot", label="Robot", live_state={"position": [4, 9]})
        actor.facets["movement"] = Facet("movement", "behaviour", "Patrol", private_state={"waypoint": 2})
        fabric.add_thing(actor)
        thing_id = actor.thing_id
        position = list(actor.live_state["position"])

        fabric.replace_facet(
            actor.thing_id,
            "movement",
            Facet("movement", "behaviour", "Flee", private_state={"panic": 0.5}),
        )

        self.assertEqual(actor.thing_id, thing_id)
        self.assertEqual(actor.live_state["position"], position)
        self.assertEqual(actor.facets["movement"].implementation, "Flee")

    def test_event_to_command_and_value_to_value_connections(self) -> None:
        fabric = Fabric()
        button = Thing("thing:button", "Button", ports={"clicked": Port("clicked", "event", "out")})
        door = Thing("thing:door", "Door", ports={"open": Port("open", "command", "in")})
        slider = Thing("thing:slider", "Slider", ports={"value": Port("value", "value", "read")})
        audio = Thing("thing:audio", "Audio", ports={"volume": Port("volume", "value", "write")})
        for thing in (button, door, slider, audio):
            fabric.add_thing(thing)

        fabric.connect("conn:button-door", "thing:button", "clicked", "thing:door", "open")
        fabric.connect("conn:slider-audio", "thing:slider", "value", "thing:audio", "volume")

        self.assertEqual(fabric.relations["conn:button-door"].kind, "connects")
        self.assertEqual(fabric.relations["conn:slider-audio"].source_port, "value")

    def test_runtime_handle_can_change_without_identity_change(self) -> None:
        fabric = Fabric()
        thing = Thing("thing:physics-ball", "Ball")
        fabric.add_thing(thing)
        fabric.context.runtime_handles[thing.thing_id] = "godot-node:100"
        original_id = thing.thing_id
        fabric.context.runtime_handles[thing.thing_id] = "godot-node:901"
        self.assertEqual(thing.thing_id, original_id)
        self.assertEqual(fabric.context.runtime_handles[thing.thing_id], "godot-node:901")


if __name__ == "__main__":
    unittest.main()
