from __future__ import annotations

from copy import deepcopy
import unittest

from fixtures import make_world
from model import Definition, DefinitionConflict, DefinitionElement, IdentityError, Thing

class P2CompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world, _, _ = make_world()
        self.world.add_thing(Thing("button", state={"enabled": True}, facets={"group"}, ports={"press"}))
        self.world.add_thing(Thing("label", state={"text": "Go"}, facets={"text"}, ports={"set_text"}))
        self.world.add_thing(Thing("sound", facets={"audio"}, ports={"play"}))
        self.world.reparent("label", "button")
        self.world.reparent("sound", "button")
        self.world.controller_by_thing["button"] = "ui"
        self.world.authority_by_thing["button"] = "local"

    def test_group_promotion_preserves_original_concrete_ids(self) -> None:
        definition, instance = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        self.assertEqual(instance.root_thing_id, "button")
        self.assertEqual(instance.thing_by_element["label"], "label")
        self.assertEqual(set(self.world.things), {"button", "label", "sound"})
        self.assertEqual(definition.root_element_id, "root")

    def test_nested_instance_uses_same_thing_semantics_and_independent_relationships(self) -> None:
        _, first = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        second = self.world.instantiate("def:button", instance_id="inst:second", prefix="copy")
        self.assertEqual(self.world.things[second.root_thing_id].facets, {"group"})
        self.world.controller_by_thing[second.root_thing_id] = "player:2"
        self.world.authority_by_thing[second.root_thing_id] = "server"
        self.world.reparent(second.root_thing_id, "button")
        self.assertEqual(self.world.controller_by_thing[second.root_thing_id], "player:2")
        self.assertEqual(self.world.authority_by_thing[second.root_thing_id], "server")
        self.assertNotEqual(first.root_thing_id, second.root_thing_id)

    def test_public_exposure_is_stable_indirection_not_internal_path(self) -> None:
        definition, _ = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        definition.exposures["activate_sound"] = ("sound", "play")
        self.world.definitions["def:button"] = definition
        self.world.instances["inst:first"].connected_public_ports.add("activate_sound")
        self.assertEqual(self.world.resolve_exposure("inst:first", "activate_sound"), ("sound", "play"))
        self.world.reparent("sound", None); self.world.reparent("sound", "label")
        self.assertEqual(self.world.resolve_exposure("inst:first", "activate_sound"), ("sound", "play"))

    def test_compatible_definition_restructure_updates_revision_without_replacing_ids(self) -> None:
        definition, _ = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        definition.exposures["activate_sound"] = ("sound", "play")
        self.world.definitions["def:button"] = deepcopy(definition)
        self.world.instances["inst:first"].connected_public_ports.add("activate_sound")
        new = deepcopy(definition); new.revision = 2; new.elements["sound"].parent_element = "label"
        before = deepcopy(self.world.instances["inst:first"].thing_by_element)
        self.world.update_definition(new)
        self.assertEqual(self.world.instances["inst:first"].thing_by_element, before)
        self.assertEqual(self.world.instances["inst:first"].base_revision, 2)

    def test_definition_removal_conflicting_with_override_rolls_back(self) -> None:
        definition, _ = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        self.world.instances["inst:first"].state_overrides["label"] = {"text": "Launch"}
        new = deepcopy(definition); new.revision = 2; del new.elements["label"]
        before_def = deepcopy(self.world.definitions["def:button"]); before_inst = deepcopy(self.world.instances["inst:first"])
        with self.assertRaises(DefinitionConflict): self.world.update_definition(new)
        self.assertEqual(self.world.definitions["def:button"], before_def)
        self.assertEqual(self.world.instances["inst:first"], before_inst)

    def test_connected_public_port_cannot_disappear_silently(self) -> None:
        definition, _ = self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        definition.exposures["activate_sound"] = ("sound", "play")
        self.world.definitions["def:button"] = deepcopy(definition)
        self.world.instances["inst:first"].connected_public_ports.add("activate_sound")
        new = deepcopy(definition); new.revision = 2; new.exposures = {}
        with self.assertRaises(DefinitionConflict): self.world.update_definition(new)

    def test_promotion_rejects_identity_collisions_before_mutation(self) -> None:
        self.world.definitions["def:existing"] = Definition("def:existing", 1, "root", {"root": DefinitionElement("root")})
        before_defs = deepcopy(self.world.definitions); before_instances = deepcopy(self.world.instances)
        with self.assertRaises(IdentityError):
            self.world.promote_group("button", "def:existing", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:new")
        self.assertEqual(self.world.definitions, before_defs)
        self.assertEqual(self.world.instances, before_instances)

    def test_instantiation_identity_collision_is_preflighted_atomically(self) -> None:
        self.world.promote_group("button", "def:button", {"button": "root", "label": "label", "sound": "sound"}, instance_id="inst:first")
        self.world.add_thing(Thing("copy:label"))
        before_things = deepcopy(self.world.things); before_instances = deepcopy(self.world.instances)
        with self.assertRaises(IdentityError): self.world.instantiate("def:button", instance_id="inst:second", prefix="copy")
        self.assertEqual(self.world.things, before_things)
        self.assertEqual(self.world.instances, before_instances)
