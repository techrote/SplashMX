#!/usr/bin/env python3
"""Validate SMX-013 non-normative package fixtures and research contract."""
from __future__ import annotations
import json, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/research/SMX-013-COMPONENT-PACKAGES.md"
FIXTURES=ROOT/"docs/research/SMX-013-PACKAGE-FIXTURES.json"
REQUIRED=[
    DOC,FIXTURES,
    ROOT/"experiments/smx-013-package-model/README.md",
    ROOT/"experiments/smx-013-package-model/package_model.py",
    ROOT/"experiments/smx-013-package-model/test_packages.py",
    ROOT/"experiments/smx-013-package-model/test_boundaries.py",
]
errors=[]
for path in REQUIRED:
    if not path.is_file(): errors.append(f"missing SMX-013 file: {path.relative_to(ROOT)}")
try: fixtures=json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc: errors.append(f"invalid SMX-013 fixture JSON: {exc}"); fixtures={}

if fixtures:
    if fixtures.get("schema")!="splashmx-smx013-package-fixtures-v1": errors.append("unexpected SMX-013 fixture schema")
    if fixtures.get("status")!="non-normative-research-fixtures": errors.append("SMX-013 fixtures must remain explicitly non-normative")
    invariants=[f"PKG-{i:03d}" for i in range(1,29)]
    if fixtures.get("boundary_invariants")!=invariants: errors.append("SMX-013 boundary_invariants must be PKG-001 through PKG-028")
    ids=[]
    known_cases={f"C-{i:03d}" for i in range(1,29)}|{f"A-{i:03d}" for i in range(1,17)}
    for entry in fixtures.get("fixtures",[]):
        fixture_id=entry.get("id"); ids.append(fixture_id)
        if not isinstance(fixture_id,str) or not re.fullmatch(r"PK-\d{3}",fixture_id): errors.append(f"invalid SMX-013 fixture id: {fixture_id!r}")
        unknown=set(entry.get("cases",[]))-known_cases
        if unknown: errors.append(f"{fixture_id} references unknown corpus IDs: {sorted(unknown)}")
        unknown=set(entry.get("expected",[]))-set(invariants)
        if unknown: errors.append(f"{fixture_id} references unknown invariants: {sorted(unknown)}")
    if ids!=[f"PK-{i:03d}" for i in range(1,21)]: errors.append("SMX-013 fixture IDs must be PK-001 through PK-020 in order")
    required_cases={"clean-install","dependency-update","locally-overridden-instance-after-update","denied-capability","missing-dependency","incompatible-migration"}
    if set(fixtures.get("required_acceptance_cases",[]))!=required_cases: errors.append("SMX-013 acceptance-case list changed unexpectedly")
    if set(fixtures.get("downstream_handoffs",{}))!={"SMX-014","SMX-016","SMX-019"}: errors.append("SMX-013 downstream handoffs must cover SMX-014/016/019")

if DOC.is_file():
    document=DOC.read_text(encoding="utf-8"); lower=document.lower()
    for identifier in [f"PKG-{i:03d}" for i in range(1,29)]:
        if identifier not in document: errors.append(f"SMX-013 research document does not reference {identifier}")
    for phrase in (
        "`PK-001` through `PK-020`","group → Make reusable → Make portable","exact resolution lock",
        "required | optional | lazy","one exact revision per PackageId","capability requests are attributed",
        "trust metadata is not privilege","incompatible migration","cache eviction is non-semantic",
        "source/audio/provenance","AssetId","SLSA 1.2","SPDX 3.0.1","SMX-014","SMX-016","SMX-019",
    ):
        if phrase.lower() not in lower: errors.append(f"SMX-013 research document is missing required phrase: {phrase!r}")

if errors:
    print("SMX-013 validation failed:")
    for error in errors: print(" -",error)
    sys.exit(1)
print("SMX-013 research validation passed")
