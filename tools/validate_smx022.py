#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/research'
EXP=ROOT/'experiments/smx-022-storage-spike'
SPEC=ROOT/'spec/production'
required=[
 DOC/'SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md',
 DOC/'SMX-022-PHYSICAL-STORE-FIXTURES.json',
 DOC/'SMX-022-NATIVE-EVIDENCE.json',
 EXP/'README.md',EXP/'spike.py',EXP/'test_spike.py',EXP/'browser_harness.mjs',
 ROOT/'.github/workflows/smx022-physical-store.yml',
]
for p in required:
    if not p.is_file(): raise SystemExit(f'SMX-022 missing required file: {p.relative_to(ROOT)}')
fixtures=json.loads((DOC/'SMX-022-PHYSICAL-STORE-FIXTURES.json').read_text())
evidence=json.loads((DOC/'SMX-022-NATIVE-EVIDENCE.json').read_text())
modules=json.loads((ROOT/'src/MODULES.json').read_text())
registry=json.loads((SPEC/'conformance-registry.json').read_text())
bench_schema=json.loads((SPEC/'benchmark-evidence.schema.json').read_text())
if fixtures.get('schema')!='splashmx-smx022-physical-store-fixtures-v1': raise SystemExit('bad SMX-022 fixture schema')
if [x['id'] for x in fixtures['workloads']] != [f'PX-{i:03d}' for i in range(1,10)]: raise SystemExit('SMX-022 workloads must be PX-001..PX-009')
expected_protected=['digest','source_identity','source_metadata','audio_or_media_semantics','provenance','licence_attribution','derivation_lineage']
if fixtures['protected_media_fields']!=expected_protected: raise SystemExit('protected-media fields changed')
statuses={m['module_id']:m['status'] for m in modules['modules']}
for module in ('canonical.core','canonical.serialization','storage.local'):
    if statuses.get(module)!='planned': raise SystemExit(f'SMX-022 must leave {module} planned')
required_bench={'contract','evidence_id','captured_at_utc','target_profile','runtime','environment','workload','sample_count','metrics'}
if evidence.get('schema')!='splashmx-smx022-native-evidence-v1' or not evidence.get('benchmark_evidence'): raise SystemExit('native evidence wrapper missing')
for row in evidence['benchmark_evidence']:
    if set(row)!=required_bench: raise SystemExit(f'benchmark evidence fields mismatch: {row.get("evidence_id")}')
    if row['contract']!='splashmx.benchmark-evidence/1' or row['target_profile']!='native': raise SystemExit('benchmark contract/profile mismatch')
    if not re.fullmatch(r'[A-Za-z0-9._:-]+',row['evidence_id']): raise SystemExit('bad evidence id')
    if row['sample_count']<1 or not row['metrics']: raise SystemExit('bad evidence sample/metrics')
    for m in row['metrics']:
        if not re.fullmatch(r'[a-z][a-z0-9_.-]*',m['name']): raise SystemExit(f'bad metric name {m["name"]}')
        if m['statistic'] not in {'single','min','max','mean','median','p50','p90','p95','p99'}: raise SystemExit('bad metric statistic')
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
doc=(DOC/'SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md').read_text()
for marker in ('SMX-024','SMX-025','known_unloaded','QuotaExceededError','synchronous=FULL','protected `AssetId`'):
    if marker not in doc: raise SystemExit(f'decision record missing {marker}')
print(f'SMX-022 spike contracts valid: {len(fixtures["workloads"])} workloads, {len(evidence["benchmark_evidence"])} native benchmark records; production modules remain planned.')
