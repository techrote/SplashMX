#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from production_contracts import validate
ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/research'
EXP=ROOT/'experiments/smx-022-storage-spike'
SPEC=ROOT/'spec/production'
RAG=ROOT/'docs/03-RAG-INDEX.md'
required=[
 DOC/'SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md',
 DOC/'SMX-022-PHYSICAL-STORE-FIXTURES.json',
 DOC/'SMX-022-NATIVE-EVIDENCE.json',
 DOC/'SMX-022-BROWSER-EVIDENCE.json',
 EXP/'README.md',EXP/'spike.py',EXP/'test_spike.py',EXP/'browser_harness.mjs',
 ROOT/'.github/workflows/smx022-physical-store.yml',RAG,
]
for p in required:
    if not p.is_file(): raise SystemExit(f'SMX-022 missing required file: {p.relative_to(ROOT)}')
fixtures=json.loads((DOC/'SMX-022-PHYSICAL-STORE-FIXTURES.json').read_text())
evidence=json.loads((DOC/'SMX-022-NATIVE-EVIDENCE.json').read_text())
browser_evidence=json.loads((DOC/'SMX-022-BROWSER-EVIDENCE.json').read_text())
modules=json.loads((ROOT/'src/MODULES.json').read_text())
registry=json.loads((SPEC/'conformance-registry.json').read_text())
bench_schema=json.loads((SPEC/'benchmark-evidence.schema.json').read_text())
if fixtures.get('schema')!='splashmx-smx022-physical-store-fixtures-v1': raise SystemExit('bad SMX-022 fixture schema')
if [x['id'] for x in fixtures['workloads']] != [f'PX-{i:03d}' for i in range(1,10)]: raise SystemExit('SMX-022 workloads must be PX-001..PX-009')
expected_protected=['digest','source_identity','source_metadata','audio_or_media_semantics','provenance','licence_attribution','derivation_lineage']
if fixtures['protected_media_fields']!=expected_protected: raise SystemExit('protected-media fields changed')
# SMX-022 selected mechanisms below Architecture v1 but did not own or implement
# the production modules. Validate that durable ownership boundary, not a stale
# snapshot of later modules' current lifecycle status: downstream issues are
# expected to advance these records from planned as they land.
module_rows={m['module_id']:m for m in modules['modules']}
expected_owners={
    'canonical.core':'SMX-023',
    'canonical.serialization':'SMX-024',
    'storage.local':'SMX-025',
}
for module,owner in expected_owners.items():
    row=module_rows.get(module)
    if row is None: raise SystemExit(f'SMX-022 downstream module missing: {module}')
    if row.get('owner_issue')!=owner:
        raise SystemExit(f'SMX-022 downstream ownership changed: {module} must remain owned by {owner}')
    if row.get('owner_issue')=='SMX-022':
        raise SystemExit(f'SMX-022 must not own production module {module}')
required_bench={'contract','evidence_id','captured_at_utc','target_profile','runtime','environment','workload','sample_count','metrics'}
if evidence.get('schema')!='splashmx-smx022-native-evidence-v1' or not evidence.get('benchmark_evidence'): raise SystemExit('native evidence wrapper missing')
for row in evidence['benchmark_evidence']:
    validate(row, bench_schema)
    if set(row)!=required_bench: raise SystemExit(f'benchmark evidence fields mismatch: {row.get("evidence_id")}')
    if row['contract']!='splashmx.benchmark-evidence/1' or row['target_profile']!='native': raise SystemExit('benchmark contract/profile mismatch')
    if not re.fullmatch(r'[A-Za-z0-9._:-]+',row['evidence_id']): raise SystemExit('bad evidence id')
    if row['sample_count']<1 or not row['metrics']: raise SystemExit('bad evidence sample/metrics')
    for m in row['metrics']:
        if not re.fullmatch(r'[a-z][a-z0-9_.-]*',m['name']): raise SystemExit(f'bad metric name {m["name"]}')
        if m['statistic'] not in {'single','min','max','mean','median','p50','p90','p95','p99'}: raise SystemExit('bad metric statistic')
if browser_evidence.get('schema')!='splashmx-smx022-browser-evidence-v1' or not browser_evidence.get('benchmark_evidence'):
    raise SystemExit('browser evidence wrapper missing')
for row in browser_evidence['benchmark_evidence']:
    validate(row, bench_schema)
    if row['target_profile']!='browser' or not row.get('browser'):
        raise SystemExit(f'browser benchmark profile/identity mismatch: {row.get("evidence_id")}')
source=browser_evidence.get('source',{})
if source.get('workflow_run_id')!=35470286634 or source.get('workflow_head_sha')!='596e48cf43aa267b5a2781ac6e80b0acff228784':
    raise SystemExit('browser evidence source provenance changed')
if source.get('artifact_sha256')!='33b472b3f769376c68e3a7af05edc9c758832d8363a34319556826721c070d5d':
    raise SystemExit('browser evidence artifact digest changed')
obs=browser_evidence.get('platform_observations',{})
if obs.get('indexeddb_reported_durability')!='strict':
    raise SystemExit('captured Chromium evidence did not report strict IndexedDB durability')
assertions=browser_evidence.get('interruption_assertions',{})
expected_states={
    'indexeddb_after_abort':('r0','assetrev:000001:0'),
    'indexeddb_after_page_interruption':('r0','assetrev:000001:0'),
    'indexeddb_after_completed_commit':('r1','assetrev:000001:1'),
}
for key,(head,asset_rev) in expected_states.items():
    row=assertions.get(key,{})
    if row.get('head')!=head or row.get('asset_revision')!=asset_rev:
        raise SystemExit(f'IndexedDB recovery assertion changed: {key}')
    if row.get('protected_fields')!=['asset_id','audio_or_media_semantics','derivation_lineage','digest','licence_attribution','provenance','revision','source_identity','source_metadata']:
        raise SystemExit(f'protected Asset bundle incomplete in {key}')
for key,expected in (
    ('opfs_after_page_interruption',('r0','assetrev:000001:0')),
    ('opfs_after_completed_close',('r1','assetrev:000001:1')),
):
    row=assertions.get(key,{})
    if (row.get('revision'),row.get('asset_revision'))!=expected:
        raise SystemExit(f'OPFS recovery assertion changed: {key}')
for gid in ('GATE-01','GATE-09'):
    gate=next(g for g in registry['gate_entries'] if g['id']==gid)
    paths={e['path'] for e in gate['evidence']}
    if 'docs/research/SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md' not in paths: raise SystemExit(f'{gid} missing SMX-022 evidence link')
workflow=(ROOT/'.github/workflows/smx022-physical-store.yml').read_text()
for marker in ('playwright@1.55.0','browser_harness.mjs','spike.py','upload-artifact@v7'):
    if marker not in workflow: raise SystemExit(f'SMX-022 workflow missing {marker}')
ci=(ROOT/'.github/workflows/ci.yml').read_text()
for marker in ('python tools/validate_smx022.py',"-p 'test_spike.py' -v"):
    if marker not in ci: raise SystemExit(f'CI missing SMX-022 marker: {marker}')
rag=RAG.read_text()
for marker in (
    'SMX-022 physical encoding/store retrieval rules',
    'deterministic CBOR',
    'IndexedDB',
    'OPFS',
    'SQLite WAL',
    'SMX-024/025',
    'tools/validate_smx022.py',
    '.github/workflows/smx022-physical-store.yml',
):
    if marker not in rag: raise SystemExit(f'RAG missing SMX-022 retrieval marker: {marker}')
doc=(DOC/'SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md').read_text()
for marker in ('SMX-024','SMX-025','known_unloaded','QuotaExceededError','synchronous=FULL','protected `AssetId`'):
    if marker not in doc: raise SystemExit(f'decision record missing {marker}')
print(f'SMX-022 spike contracts valid: {len(fixtures["workloads"])} workloads, {len(evidence["benchmark_evidence"])} native and {len(browser_evidence["benchmark_evidence"])} browser benchmark records; downstream production ownership remains explicit.')
