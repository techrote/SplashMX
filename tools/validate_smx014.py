#!/usr/bin/env python3
"""Validate SMX-014 non-normative publishing fixtures and research contract."""
from __future__ import annotations
import json, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/research/SMX-014-PUBLISHING-RUNTIME.md"
FIXTURES=ROOT/"docs/research/SMX-014-PUBLISHING-FIXTURES.json"
REQUIRED=[
    DOC,FIXTURES,
    ROOT/"experiments/smx-014-publishing-model/README.md",
    ROOT/"experiments/smx-014-publishing-model/publishing_model.py",
    ROOT/"experiments/smx-014-publishing-model/test_publishing.py",
    ROOT/"experiments/smx-014-publishing-model/test_boundaries.py",
]
errors=[]
for path in REQUIRED:
    if not path.is_file(): errors.append(f"missing SMX-014 file: {path.relative_to(ROOT)}")
try: fixtures=json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc: errors.append(f"invalid SMX-014 fixture JSON: {exc}"); fixtures={}

invariants=[f"PUB-{i:03d}" for i in range(1,31)]
if fixtures:
    if fixtures.get("schema")!="splashmx-smx014-publishing-fixtures-v1": errors.append("unexpected SMX-014 fixture schema")
    if fixtures.get("status")!="non-normative-research-fixtures": errors.append("SMX-014 fixtures must remain explicitly non-normative")
    if fixtures.get("boundary_invariants")!=invariants: errors.append("SMX-014 boundary_invariants must be PUB-001 through PUB-030")
    ids=[]
    known_cases={f"C-{i:03d}" for i in range(1,29)}|{f"A-{i:03d}" for i in range(1,17)}
    for entry in fixtures.get("fixtures",[]):
        fixture_id=entry.get("id"); ids.append(fixture_id)
        if not isinstance(fixture_id,str) or not re.fullmatch(r"PB-\d{3}",fixture_id): errors.append(f"invalid SMX-014 fixture id: {fixture_id!r}")
        unknown=set(entry.get("cases",[]))-known_cases
        if unknown: errors.append(f"{fixture_id} references unknown corpus IDs: {sorted(unknown)}")
        unknown=set(entry.get("expected",[]))-set(invariants)
        if unknown: errors.append(f"{fixture_id} references unknown invariants: {sorted(unknown)}")
    if ids!=[f"PB-{i:03d}" for i in range(1,21)]: errors.append("SMX-014 fixture IDs must be PB-001 through PB-020 in order")
    required_cases={
        "artifact-taxonomy","generic-player-no-author-export","compatibility-and-future-content",
        "target-projection","pre-execution-security","offline-and-hosted","smx017-handoff",
        "smx019-handoff","protected-media-preservation",
    }
    if set(fixtures.get("required_acceptance_cases",[]))!=required_cases: errors.append("SMX-014 acceptance-case list changed unexpectedly")
    if set(fixtures.get("downstream_handoffs",{}))!={"SMX-015","SMX-016","SMX-017","SMX-019","SMX-020"}: errors.append("SMX-014 downstream handoffs must cover SMX-015/016/017/019/020")

if DOC.is_file():
    document=DOC.read_text(encoding="utf-8"); lower=document.lower()
    for identifier in invariants:
        if identifier not in document: errors.append(f"SMX-014 research document does not reference {identifier}")
    for phrase in (
        "`PB-001` through `PB-020`","EditableProject","PublishedCreationRevision","GenericPlayerRuntime",
        "WorldSave","HostedRelease","OfflineBundle","ordinary publishing creates an immutable SplashMX creation revision",
        "required feature/extension/IR/schema","exact locked dependency closure","before activation",
        "headless","source/audio/provenance","AssetId","per-creation Godot export","SMX-017","SMX-019",
        "4.7.2 stable","export templates","PCK/mod","Runtime loading supports",
    ):
        if phrase.lower() not in lower: errors.append(f"SMX-014 research document is missing required phrase: {phrase!r}")

if errors:
    print("SMX-014 validation failed:")
    for error in errors: print(" -",error)
    sys.exit(1)
print("SMX-014 research validation passed")
