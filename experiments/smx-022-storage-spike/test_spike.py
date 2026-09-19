import importlib.util, json, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('spike',Path(__file__).with_name('spike.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class T(unittest.TestCase):
    def test_cbor_deterministic_and_strict(self):
        a={'z':1,'aa':2,'n':-3,'b':b'xx','arr':[1,True,None,1.5,-0.0]}
        b={'arr':[1,True,None,1.5,-0.0],'b':b'xx','n':-3,'aa':2,'z':1}
        ea=m.cbor_encode(a); self.assertEqual(ea,m.cbor_encode(b)); self.assertEqual(m.cbor_decode(ea),a)
        with self.assertRaises(ValueError): m.cbor_encode({'x':float('nan')})
        with self.assertRaises(ValueError): m.cbor_decode(b'\xa2\x61a\x01\x61a\x02')
    def test_protected_asset_is_complete_revision(self):
        required={'digest','source_identity','source_metadata','audio_or_media_semantics','provenance','licence_attribution','derivation_lineage'}
        self.assertTrue(required <= set(m.protected_asset(1)))
    def test_id_sharding_is_placement_only(self):
        records=m.make_project('nested')['records']; enc,chunks,man=m.stable_bucket_pack(records,16*1024)
        rid='thing:00000010'; bits=man['bucket_bits']; h=int.from_bytes(__import__('hashlib').sha256(rid.encode()).digest()[:4],'big'); bucket=h>>(32-bits) if bits else 0
        chunk=next(c for c in chunks if c['bucket']==bucket)
        got=m.cbor_decode(m.chunk_lookup(chunk['bytes'],rid)); self.assertEqual(got['id'],rid); self.assertEqual(got['value']['thing_id'],rid)
        self.assertNotIn('bucket',got['value']); self.assertNotIn('offset',got['value'])
    def test_single_edit_changes_one_shard_for_many_fixture(self):
        records=m.make_project('many')['records']; _,a,ma=m.stable_bucket_pack(records,64*1024); _,b,mb=m.stable_bucket_pack(m.update_record(records,'thing:00000100'),64*1024)
        da={x['bucket']:x['digest'] for x in a}; db={x['bucket']:x['digest'] for x in b}; self.assertEqual(sum(da[k]!=db[k] for k in da),1); self.assertEqual(ma['bucket_bits'],mb['bucket_bits'])
    def test_native_crash_recovery(self):
        for journal in ('WAL','DELETE'):
            r=m.bench_sqlite(journal,samples=1); self.assertEqual(r['crash_before_commit_head'],'r0'); self.assertEqual(r['abrupt_after_commit_head'],'r1')
        r=m.bench_atomic_file(samples=1); self.assertEqual(r['crash_before_head'],'r0'); self.assertEqual(r['abrupt_after_head'],'r1')

if __name__=='__main__': unittest.main()
