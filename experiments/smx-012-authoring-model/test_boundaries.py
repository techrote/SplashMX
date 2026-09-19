import json,unittest
from copy import deepcopy
from services import diagnostic,import_asset,play,publish,record_conflict,record_transaction,replace_asset,set_presence,stop
from workspace import AuthoringValidationError,ProtectedAssetError,PROTECTED_ASSET_KEYS,Workspace

def bundle(d="sha256:one"):
    return {"digest":d,"source":{"id":"src:voice"},"audio":{"id":"aud:voice"},"provenance":{"license":"CC0","derivation":["trim"]}}

class BoundaryTests(unittest.TestCase):
    def setUp(self): self.w=Workspace()
    def test_play_is_transient(self):
        self.w.create("thing:a","A"); before=self.w.digest(); self.assertTrue(play(self.w).startswith("play:")); self.assertEqual(before,self.w.digest()); stop(self.w); self.assertEqual(before,self.w.digest())
    def test_publish_uses_generic_player_without_build(self):
        self.w.create("thing:a","A"); manifest=publish(self.w); self.assertEqual(manifest["runtime"],"generic-player"); self.assertFalse(manifest["requires_build"]); self.assertEqual(manifest["creation_revision"],self.w.digest())
    def test_presence_and_history_are_not_canonical(self):
        self.w.create("thing:a","A"); before=self.w.snapshot(); set_presence(self.w,"alice",{"selection":"thing:a"}); record_transaction(self.w,"tx:1","Move A")
        self.assertEqual(before,self.w.snapshot()); encoded=json.dumps(self.w.snapshot()); self.assertNotIn("alice",encoded); self.assertNotIn("tx:1",encoded)
    def test_runtime_network_and_collaboration_do_not_share_state(self):
        self.w.create("thing:toy","Toy"); self.w.preset("thing:toy","shared"); before=deepcopy(self.w.thing("thing:toy")["network"])
        record_conflict(self.w,"c:1",["Alice","Bob"]); self.assertEqual(before,self.w.thing("thing:toy")["network"]); self.assertNotIn("conflicts",self.w.canonical)
    def test_conflict_requires_retained_alternatives(self):
        with self.assertRaises(AuthoringValidationError): record_conflict(self.w,"c:bad",["only"])
    def test_author_diagnostics_cover_unloaded_permission_dependency_conflict(self):
        self.assertIn("not loaded yet",diagnostic("known_unloaded","Door")); self.assertIn("not allowed",diagnostic("capability_denied","Camera behaviour"))
        self.assertIn("unavailable or incompatible",diagnostic("dependency_unavailable","Dialogue")); self.assertIn("competing edits",diagnostic("conflict","Button"))
    def test_asset_revision_bundle_is_atomic(self):
        import_asset(self.w,"asset:voice",bundle()); replacement=bundle("sha256:two"); replace_asset(self.w,"asset:voice",replacement)
        self.assertEqual(set(self.w.canonical["assets"]["asset:voice"]),PROTECTED_ASSET_KEYS); self.assertEqual(self.w.canonical["assets"]["asset:voice"],replacement)
    def test_partial_asset_revision_rejected_without_mutation(self):
        import_asset(self.w,"asset:voice",bundle()); before=deepcopy(self.w.canonical["assets"]["asset:voice"])
        with self.assertRaises(ProtectedAssetError): replace_asset(self.w,"asset:voice",{"digest":"sha256:two","source":{},"audio":{}})
        self.assertEqual(before,self.w.canonical["assets"]["asset:voice"])
    def test_asset_replacement_preserves_logical_asset_id(self):
        import_asset(self.w,"asset:voice",bundle()); replace_asset(self.w,"asset:voice",bundle("sha256:three")); self.assertEqual(list(self.w.canonical["assets"]),["asset:voice"])
    def test_unknown_publish_target_rejected(self):
        with self.assertRaises(AuthoringValidationError): publish(self.w,"mystery")

if __name__=="__main__": unittest.main()
