#!/usr/bin/env python3
"""Validate SMX-015 non-normative Object Fabric fixtures and synthesis contract."""
from __future__ import annotations
import json, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/research/SMX-015-OBJECT-FABRIC-HARNESS.md"
FIXTURES=ROOT/"docs/research/SMX-015-OBJECT-FABRIC-FIXTURES.json"
DECISION=ROOT/"docs/research/SMX-015-DECISION-EVIDENCE.md"
RAG=ROOT/"docs/03-RAG-INDEX.md"
LOG=ROOT/"docs/05-DECISION-AND-EVIDENCE-LOG.md"
REQUIRED=[
    DOC,FIXTURES,DECISION,RAG,LOG,
    ROOT/"experiments/smx-015-object-fabric-harness/README.md",
    ROOT/"experiments/smx-015-object-fabric-harness/model.py",
    ROOT/"experiments/smx-015-object-fabric-harness/fixtures.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_p0_kernel.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_p1_hotswap.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_p2_composition.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_p3_restore.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_p4_streaming.py",
    ROOT/"experiments/smx-015-object-fabric-harness/test_protected_media.py",
]
errors=[]
for path in REQUIRED:
    if not path.is_file(): errors.append(f"missing SMX-015 file: {path.relative_to(ROOT)}")
try:
    fixtures=json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError,json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-015 fixture JSON: {exc}"); fixtures={}

invariants=[f"OF-{i:03d}" for i in range(1,31)]
known_cases={f"C-{i:03d}" for i in range(1,29)}|{f"A-{i:03d}" for i in range(1,17)}
if fixtures:
    if fixtures.get("schema")!="splashmx-smx015-object-fabric-fixtures-v1": errors.append("unexpected SMX-015 fixture schema")
    if fixtures.get("status")!="non-normative-research-fixtures": errors.append("SMX-015 fixtures must remain explicitly non-normative")
    if fixtures.get("boundary_invariants")!=invariants: errors.append("SMX-015 boundary_invariants must be OF-001 through OF-030")
    if fixtures.get("required_experiments") != ["P0-universal-kernel","P1-hot-behaviour-replacement","P2-nested-composition-local-definitions","P3-exact-serialize-restore","P4-stream-arbitrary-subgraphs"]:
        errors.append("SMX-015 required_experiments must preserve P0 through P4 in order")
    ids=[]
    for entry in fixtures.get("fixtures",[]):
        fixture_id=entry.get("id"); ids.append(fixture_id)
        if not isinstance(fixture_id,str) or not re.fullmatch(r"OH-\d{3}",fixture_id): errors.append(f"invalid SMX-015 fixture id: {fixture_id!r}")
        unknown=set(entry.get("cases",[]))-known_cases
        if unknown: errors.append(f"{fixture_id} references unknown corpus IDs: {sorted(unknown)}")
        unknown=set(entry.get("expected",[]))-set(invariants)
        if unknown: errors.append(f"{fixture_id} references unknown invariants: {sorted(unknown)}")
        if not entry.get("purpose"): errors.append(f"{fixture_id} has no purpose")
    if ids!=[f"OH-{i:03d}" for i in range(1,21)]: errors.append("SMX-015 fixture IDs must be OH-001 through OH-020 in order")
    required_cases={"materially-different-corpus-objects","identity-and-independent-relationships","hot-swap-state-and-pending-work","nested-definition-instance-and-public-interface","fresh-runtime-restore","unloaded-reference-versus-destruction","failed-dependency-atomicity","protected-source-audio-provenance","non-normative-scope-and-failure-classification"}
    if set(fixtures.get("required_acceptance_cases",[]))!=required_cases: errors.append("SMX-015 acceptance-case list changed unexpectedly")
    if set(fixtures.get("downstream_handoffs",{}))!={"SMX-016","SMX-017","SMX-018","SMX-019","SMX-020"}: errors.append("SMX-015 downstream handoffs must cover SMX-016 through SMX-020")

if DOC.is_file():
    document=DOC.read_text(encoding="utf-8"); lower=document.lower()
    for identifier in invariants:
        if identifier not in document: errors.append(f"SMX-015 synthesis document does not reference {identifier}")
    required_phrases=("`Thing` semantic type","P0 universal kernel","P1 hot behaviour replacement","P2 nested composition","P3 exact serialize/restore","P4 stream arbitrary subgraphs","37 deterministic","fresh `FabricWorld`","known_unloaded","tombstoned","source/audio/provenance","AssetId","NodePath","O-020 remains **OPEN**","No upstream authoritative contract required semantic amendment","SMX-016","SMX-017","SMX-018","SMX-019","SMX-020")
    for phrase in required_phrases:
        if phrase.lower() not in lower: errors.append(f"SMX-015 synthesis document is missing required phrase: {phrase!r}")

if DECISION.is_file():
    text=DECISION.read_text(encoding="utf-8")
    for identifier in ("D-087","D-088","D-089","D-090","E-069","O-020"):
        if identifier not in text: errors.append(f"SMX-015 decision/evidence handoff is missing {identifier}")

if RAG.is_file():
    text=RAG.read_text(encoding="utf-8")
    for phrase in ("SMX-015 Object Fabric destructive-harness retrieval rules","OF-001","OF-030","OH-001","OH-020","SMX-015-DECISION-EVIDENCE.md","source/audio/provenance"):
        if phrase not in text: errors.append(f"RAG index is missing SMX-015 retrieval marker: {phrase!r}")

if LOG.is_file():
    text=LOG.read_text(encoding="utf-8")
    for identifier in ("## SMX-015 decision/evidence register","D-087","D-088","D-089","D-090","E-069","O-020 update"):
        if identifier not in text: errors.append(f"project decision/evidence register is missing SMX-015 marker: {identifier!r}")
    if "protected source/audio/provenance" not in text:
        errors.append("project decision/evidence register lost the SMX-015 protected-media boundary")

if errors:
    print("SMX-015 validation failed:")
    for error in errors: print(" -",error)
    sys.exit(1)
print("SMX-015 research validation passed")
