import unittest
from copy import deepcopy
from workspace import AuthoringValidationError,PRESETS,Workspace

class AuthoringTests(unittest.TestCase):
    def setUp(self): self.w=Workspace()
    def test_disclosure_does_not_mutate_creation(self):
        self.w.create("thing:a","A"); before=self.w.digest(); self.assertEqual(before,self.w.digest())
    def test_reparent_preserves_behaviour_and_network(self):
        self.w.create("thing:world","World","group"); self.w.create("thing:car","Car")
        self.w.behaviour("thing:car","att:drive","drive"); self.w.preset("thing:car","shared")
        before=deepcopy(self.w.thing("thing:car")); self.w.reparent("thing:car","thing:world"); after=self.w.thing("thing:car")
        self.assertEqual(before["behaviours"],after["behaviours"]); self.assertEqual(before["network"],after["network"])
    def test_group_promotes_without_replacing_ids(self):
        self.w.create("thing:text","Text"); self.w.group("thing:card",["thing:text"],"Card"); ids=set(self.w.canonical["things"])
        self.w.reusable("thing:card","def:card"); self.assertEqual(ids,set(self.w.canonical["things"])); self.assertEqual(self.w.thing("thing:card")["definition"],"def:card")
    def test_leaf_cannot_take_reuse_shortcut(self):
        self.w.create("thing:a","A")
        with self.assertRaises(AuthoringValidationError): self.w.reusable("thing:a","def:a")
    def test_overlay_is_sparse_same_instance(self):
        self.w.create("thing:text","Text"); self.w.group("thing:card",["thing:text"],"Card"); self.w.reusable("thing:card","def:card")
        self.w.overlay("thing:card","thing:text.text","Hello"); self.assertEqual(self.w.thing("thing:card")["overlays"],{"thing:text.text":"Hello"})
    def test_rule_and_advanced_behaviour_share_ir(self):
        self.w.create("thing:button","Button"); self.w.rule("thing:button","att:rule","clicked","toggle"); self.w.behaviour("thing:button","att:state","state-machine")
        self.assertEqual({v["ir_target"] for v in self.w.thing("thing:button")["behaviours"].values()},{"smx-ir"})
        with self.assertRaises(AuthoringValidationError): self.w.behaviour("thing:button","att:other","other",ir_target="other-runtime")
    def test_stable_port_connection_and_boundaries(self):
        self.w.create("thing:a","A"); self.w.create("thing:b","B"); self.w.port("thing:a","out","out","number"); self.w.port("thing:b","in","in","number")
        self.w.connect("conn:1",("thing:a","out"),("thing:b","in")); self.assertEqual(self.w.canonical["connections"]["conn:1"]["source"],["thing:a","out"])
        with self.assertRaises(AuthoringValidationError): self.w.connect("conn:2",("thing:b","in"),("thing:a","out"))
    def test_timeline_is_optional(self):
        self.w.create("thing:b","Button"); self.w.rule("thing:b","att:click","clicked","toggle"); self.assertEqual(self.w.canonical["timelines"],{})
    def test_timeline_available_for_time_media(self):
        self.w.create("thing:t","Title"); self.w.animate("thing:t","opacity",[(0,0),(1,1)]); self.assertTrue(self.w.canonical["timelines"])
    def test_simple_and_advanced_multiplayer_are_same_fields(self):
        self.w.create("thing:toy","Toy"); self.w.preset("thing:toy","shared"); value=deepcopy(self.w.thing("thing:toy")["network"])
        self.w.advanced_network("thing:toy",value); self.assertEqual(value,PRESETS["shared"])
        with self.assertRaises(AuthoringValidationError): self.w.advanced_network("thing:toy",{**value,"peer":7})
    def test_duplicate_identity_rejected(self):
        self.w.create("thing:a","A")
        with self.assertRaises(AuthoringValidationError): self.w.create("thing:a","Again")

if __name__=="__main__": unittest.main()
