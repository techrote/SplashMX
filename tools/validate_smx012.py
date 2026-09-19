#!/usr/bin/env python3
"""Validate SMX-012 non-normative authoring fixtures and research contract."""
from __future__ import annotations
import json,pathlib,re,sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/research/SMX-012-AUTHORING-MODEL.md"
FIXTURES=ROOT/"docs/research/SMX-012-AUTHORING-FIXTURES.json"
CORPUS=ROOT/"docs/research/SMX-001-EVALUATION-CORPUS.json"
REQUIRED=[DOC,FIXTURES,ROOT/"experiments/smx-012-authoring-model/README.md",ROOT/"experiments/smx-012-authoring-model/projection.py",ROOT/"experiments/smx-012-authoring-model/workspace.py",ROOT/"experiments/smx-012-authoring-model/services.py",ROOT/"experiments/smx-012-authoring-model/test_projection.py",ROOT/"experiments/smx-012-authoring-model/test_authoring.py",ROOT/"experiments/smx-012-authoring-model/test_boundaries.py"]
errors=[]
for path in REQUIRED:
    if not path.is_file(): errors.append(f"missing SMX-012 file: {path.relative_to(ROOT)}")
try: fixtures=json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc: errors.append(f"invalid SMX-012 fixture JSON: {exc}"); fixtures={}
try: corpus=json.loads(CORPUS.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc: errors.append(f"invalid SMX-001 corpus JSON while validating SMX-012: {exc}"); corpus={}

if fixtures:
    if fixtures.get("schema")!="splashmx-smx012-authoring-fixtures-v1": errors.append("unexpected SMX-012 fixture schema")
    if fixtures.get("status")!="non-normative-research-fixtures": errors.append("SMX-012 fixtures must remain explicitly non-normative")
    invariants=[f"AUTH-{i:03d}" for i in range(1,29)]
    if fixtures.get("boundary_invariants")!=invariants: errors.append("SMX-012 boundary_invariants must be AUTH-001 through AUTH-028")
    if fixtures.get("progressive_levels")!=["canvas","interactive","reuse","together","advanced"]: errors.append("SMX-012 progressive levels changed unexpectedly")
    corpus_ids={item.get("id") for key in ("cases","adversarial_cases") for item in corpus.get(key,[]) if isinstance(item,dict)}
    ids=[]
    for entry in fixtures.get("fixtures",[]):
        fixture_id=entry.get("id"); ids.append(fixture_id)
        if not isinstance(fixture_id,str) or not re.fullmatch(r"UX-\d{3}",fixture_id): errors.append(f"invalid SMX-012 fixture id: {fixture_id!r}")
        unknown=set(entry.get("cases",[]))-corpus_ids
        if unknown: errors.append(f"{fixture_id} references unknown corpus IDs: {sorted(unknown)}")
        unknown=set(entry.get("expected",[]))-set(invariants)
        if unknown: errors.append(f"{fixture_id} references unknown invariants: {sorted(unknown)}")
    if ids!=[f"UX-{i:03d}" for i in range(1,29)]: errors.append("SMX-012 fixture IDs must be UX-001 through UX-028 in order")
    gates=fixtures.get("smx019_gates",[])
    if [g.get("id") for g in gates]!=[f"UXG-{i:03d}" for i in range(1,13)]: errors.append("SMX-019 gates must be UXG-001 through UXG-012")
    if set(fixtures.get("direct_case_coverage",[]))!={f"C-{i:03d}" for i in range(1,29)}: errors.append("SMX-012 must explicitly walk C-001 through C-028")

if DOC.is_file():
    document=DOC.read_text(encoding="utf-8"); lower=document.lower()
    for identifier in [f"AUTH-{i:03d}" for i in range(1,29)]:
        if identifier not in document: errors.append(f"SMX-012 research document does not reference {identifier}")
    for phrase in ("`UX-001` through `UX-028`","`UXG-001` through `UXG-012`","Things, Behaviours, and Connections","progressive disclosure","runtime multiplayer","collaborative editing","source/audio/provenance","generic player","SMX-019","Flash is a floor","Timeline is optional","Convergence is not enough","One per player","known-unloaded"):
        if phrase.lower() not in lower: errors.append(f"SMX-012 research document is missing required phrase: {phrase!r}")

if errors:
    print("SMX-012 validation failed:")
    for error in errors: print(" -",error)
    sys.exit(1)
print("SMX-012 research validation passed")
