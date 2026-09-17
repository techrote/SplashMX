from __future__ import annotations

import copy
import unittest

from model import (
    ConcreteGraph,
    DefinitionElement,
    LocalElement,
    Thing,
    apply_plan,
    effective_parent,
    effective_state,
    instantiate,
    plan_reconcile,
    promote_group,
    public_target,
    resolve_exposure,
)


class CompositionModelTests(unittest.TestCase):
    def base_graph(self) -> ConcreteGraph:
        return ConcreteGraph(
            things={
                "thing:car": Thing(
                    "thing:car", {"kind": "car"}, {"group_sync"}, {"drive"}
                ),
                "thing:wheel": Thing("thing:wheel", {"size": 18}, {"spin"}, set()),
                "thing:seat": Thing(
                    "thing:seat", {"occupied": False}, {"seat"}, {"enter"}
                ),
            },
            parent_by_child={
                "thing:wheel": "thing:car",
                "thing:seat": "thing:car",
            },
            controller_by_thing={"thing:car": "player:3"},
            authority_by_thing={"thing:car": "server:A"},
            persistence_by_thing={"thing:car": "world:save"},
            replication_by_thing={"thing:car": "room:7"},
        )

    def promoted(self):
        graph = self.base_graph()
        definition, instance = promote_group(
            graph,
            "thing:car",
            "def:car",
            {
                "thing:car": "el:root",
                "thing:wheel": "el:wheel",
                "thing:seat": "el:seat",
            },
        )
        return graph, definition, instance

    def test_ct001_promotion_preserves_ids_context_and_member_meaning(self):
        _, definition, instance = self.promoted()
        self.assertEqual(instance.root_thing_id, "thing:car")
        self.assertEqual(instance.thing_by_element["el:wheel"], "thing:wheel")
        self.assertEqual(instance.controller_by_thing["thing:car"], "player:3")
        self.assertEqual(instance.authority_by_thing["thing:car"], "server:A")
        self.assertEqual(instance.persistence_by_thing["thing:car"], "world:save")
        self.assertEqual(instance.replication_by_thing["thing:car"], "room:7")
        self.assertIn("group_sync", definition.elements["el:root"].facets)
        self.assertIn("spin", definition.elements["el:wheel"].facets)

    def test_ct002_multiple_instances_get_independent_thing_ids(self):
        _, definition, _ = self.promoted()
        first = instantiate(definition, "inst:A")
        second = instantiate(definition, "inst:B")
        self.assertNotEqual(first.root_thing_id, second.root_thing_id)
        self.assertEqual(set(first.thing_by_element), set(second.thing_by_element))
        self.assertTrue(
            all(
                first.thing_by_element[element_id]
                != second.thing_by_element[element_id]
                for element_id in definition.elements
            )
        )

    def test_ct003_property_override_survives_compatible_base_update(self):
        _, definition, instance = self.promoted()
        definition.elements["el:root"].state.update({"speed": 5, "colour": "red"})
        instance.state_overrides["el:root"] = {"speed": 10}

        updated = copy.deepcopy(definition)
        updated.revision = 2
        updated.elements["el:root"].state.update({"speed": 6, "colour": "blue"})

        plan = plan_reconcile(definition, updated, instance)
        self.assertTrue(plan.ok, plan.conflicts)
        apply_plan(instance, plan)
        self.assertEqual(
            effective_state(updated, instance, "el:root"),
            {"kind": "car", "speed": 10, "colour": "blue"},
        )

    def test_ct004_structural_override_wins_compatible_base_reparent(self):
        _, definition, instance = self.promoted()
        definition.elements["el:mountA"] = DefinitionElement(
            "el:mountA", "mountA", parent_element="el:root"
        )
        definition.elements["el:mountB"] = DefinitionElement(
            "el:mountB", "mountB", parent_element="el:root"
        )
        definition.elements["el:wheel"].parent_element = "el:mountA"
        instance.thing_by_element["el:mountA"] = "thing:mountA"
        instance.thing_by_element["el:mountB"] = "thing:mountB"
        instance.parent_overrides["el:wheel"] = "el:mountB"

        updated = copy.deepcopy(definition)
        updated.revision = 2
        updated.elements["el:wheel"].parent_element = "el:root"

        plan = plan_reconcile(definition, updated, instance)
        self.assertTrue(plan.ok, plan.conflicts)
        apply_plan(instance, plan)
        self.assertEqual(effective_parent(updated, instance, "el:wheel"), "el:mountB")

    def test_ct005_removed_overridden_element_conflicts_without_partial_apply(self):
        _, definition, instance = self.promoted()
        instance.state_overrides["el:wheel"] = {"size": 22}
        updated = copy.deepcopy(definition)
        updated.revision = 2
        del updated.elements["el:wheel"]

        plan = plan_reconcile(definition, updated, instance)
        self.assertFalse(plan.ok)
        self.assertEqual(instance.base_revision, 1)
        with self.assertRaises(ValueError):
            apply_plan(instance, plan)
        self.assertEqual(instance.thing_by_element["el:wheel"], "thing:wheel")

    def test_ct006_removed_referenced_element_conflicts(self):
        _, definition, instance = self.promoted()
        wheel_thing = instance.thing_by_element["el:wheel"]
        updated = copy.deepcopy(definition)
        updated.revision = 2
        del updated.elements["el:wheel"]

        plan = plan_reconcile(definition, updated, instance, {wheel_thing})
        self.assertFalse(plan.ok)
        self.assertIn(
            "removed element has protected instance semantics: el:wheel",
            plan.conflicts,
        )

    def test_ct007_local_addition_survives_base_update(self):
        _, definition, instance = self.promoted()
        instance.local_elements["local:radio"] = LocalElement(
            "local:radio",
            "thing:radio",
            {"station": "A"},
            parent_base_element="el:root",
        )
        updated = copy.deepcopy(definition)
        updated.revision = 2
        updated.elements["el:root"].state["kind"] = "car-v2"

        plan = plan_reconcile(definition, updated, instance)
        self.assertTrue(plan.ok, plan.conflicts)
        apply_plan(instance, plan)
        self.assertEqual(instance.local_elements["local:radio"].thing_id, "thing:radio")
        self.assertEqual(
            instance.local_elements["local:radio"].parent_base_element, "el:root"
        )

    def test_ct008_public_port_survives_internal_reparent(self):
        _, definition, instance = self.promoted()
        definition.elements["el:seat"].ports.add("enter")
        definition.exposures["public:enter"] = ("el:seat", "enter")
        instance.connected_public_ports.add("public:enter")
        external_target_before = public_target(instance, "public:enter")

        updated = copy.deepcopy(definition)
        updated.revision = 2
        updated.elements["el:seat"].parent_element = "el:wheel"

        plan = plan_reconcile(definition, updated, instance)
        self.assertTrue(plan.ok, plan.conflicts)
        apply_plan(instance, plan)
        self.assertEqual(external_target_before, public_target(instance, "public:enter"))
        self.assertEqual(
            resolve_exposure(updated, instance, "public:enter"),
            ("thing:seat", "enter"),
        )

    def test_ct009_removed_exposure_implementation_conflicts(self):
        _, definition, instance = self.promoted()
        definition.elements["el:seat"].ports.add("enter")
        definition.exposures["public:enter"] = ("el:seat", "enter")
        instance.connected_public_ports.add("public:enter")

        updated = copy.deepcopy(definition)
        updated.revision = 2
        del updated.elements["el:seat"]

        plan = plan_reconcile(definition, updated, instance)
        self.assertFalse(plan.ok)
        self.assertTrue(
            any("exposure target element missing" in message for message in plan.conflicts)
        )

    def test_ct010_reconcile_leaves_runtime_context_untouched(self):
        _, definition, instance = self.promoted()
        context_before = (
            copy.deepcopy(instance.controller_by_thing),
            copy.deepcopy(instance.authority_by_thing),
            copy.deepcopy(instance.persistence_by_thing),
            copy.deepcopy(instance.replication_by_thing),
        )
        updated = copy.deepcopy(definition)
        updated.revision = 2
        updated.elements["el:root"].state["kind"] = "car-v2"

        plan = plan_reconcile(definition, updated, instance)
        self.assertTrue(plan.ok, plan.conflicts)
        apply_plan(instance, plan)
        self.assertEqual(
            context_before,
            (
                instance.controller_by_thing,
                instance.authority_by_thing,
                instance.persistence_by_thing,
                instance.replication_by_thing,
            ),
        )


if __name__ == "__main__":
    unittest.main()
