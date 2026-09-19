#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "smx-019-browser-vertical-slice"
DOC = ROOT / "docs" / "research"

required = [
    DOC / "SMX-019-BROWSER-VERTICAL-SLICE.md",
    DOC / "SMX-019-BROWSER-VERTICAL-SLICE-FIXTURES.json",
    DOC / "SMX-019-DECISION-EVIDENCE.md",
    EXP / "README.md",
    EXP / "model.mjs",
    EXP / "test_model.mjs",
    EXP / "index.html",
    EXP / "editor.mjs",
    EXP / "player.html",
    EXP / "player.mjs",
    EXP / "server.mjs",
    EXP / "browser_harness.mjs",
    EXP / "styles.css",
    EXP / "sw.js",
    ROOT / ".github" / "workflows" / "smx019-browser-slice.yml",
]

for path in required:
    if not path.is_file():
        raise SystemExit(f"SMX-019 missing required file: {path.relative_to(ROOT)}")

fixtures = json.loads((DOC / "SMX-019-BROWSER-VERTICAL-SLICE-FIXTURES.json").read_text(encoding="utf-8"))
uxg = [item["id"] for item in fixtures["upstream_hard_gates"]]
bv = [item["id"] for item in fixtures["browser_gates"]]
if uxg != [f"UXG-{i:03d}" for i in range(1, 13)]:
    raise SystemExit(f"SMX-019 fixtures must cover UXG-001..UXG-012 exactly; got {uxg}")
if bv != [f"BV-{i:03d}" for i in range(1, 21)]:
    raise SystemExit(f"SMX-019 fixtures must cover BV-001..BV-020 exactly; got {bv}")
if [item["id"] for item in fixtures.get("repairs", [])] != ["R-019-01"]:
    raise SystemExit("SMX-019 fixtures must retain R-019-01")

model = (EXP / "model.mjs").read_text(encoding="utf-8")
tests = (EXP / "test_model.mjs").read_text(encoding="utf-8")
editor_html = (EXP / "index.html").read_text(encoding="utf-8").lower()
editor = (EXP / "editor.mjs").read_text(encoding="utf-8")
player = (EXP / "player.mjs").read_text(encoding="utf-8")
harness = (EXP / "browser_harness.mjs").read_text(encoding="utf-8")
research = (DOC / "SMX-019-BROWSER-VERTICAL-SLICE.md").read_text(encoding="utf-8")
local_evidence = (DOC / "SMX-019-DECISION-EVIDENCE.md").read_text(encoding="utf-8")
hypotheses = (ROOT / "docs" / "02-ARCHITECTURE-HYPOTHESES.md").read_text(encoding="utf-8")
rag = (ROOT / "docs" / "03-RAG-INDEX.md").read_text(encoding="utf-8")
decisions = (ROOT / "docs" / "05-DECISION-AND-EVIDENCE-LOG.md").read_text(encoding="utf-8")
workflow = (ROOT / ".github" / "workflows" / "smx019-browser-slice.yml").read_text(encoding="utf-8")

count = len(re.findall(r"\btest\('", tests))
if count != 34:
    raise SystemExit(f"SMX-019 must retain exactly 34 deterministic model/boundary tests; found {count}")

for term in ["thing_id", "definition_id", "attachment_id", "connection_id", "track_id", "creation_revision_id", "semantic_digest"]:
    if term not in model:
        raise SystemExit(f"SMX-019 model missing accepted semantic identity: {term}")

for protected in ["digest", "source", "media", "provenance", "licence", "derivation"]:
    if protected not in model or protected not in research.lower():
        raise SystemExit(f"SMX-019 protected-media contract missing {protected}")

for forbidden_visible in ["godot", "scenetree", "nodepath", "resourceuid", "rpc", "package manager", "export preset", "build toolchain"]:
    if forbidden_visible in editor_html:
        raise SystemExit(f"SMX-019 ordinary editor HTML leaks forbidden author-facing vocabulary: {forbidden_visible}")

for expected in ["Add Button Thing", "Make reusable", "Add Rule", "Connect", "Add Timeline motion", "Play", "Save", "Publish", "Together", "People", "Inspect"]:
    if expected not in (EXP / "index.html").read_text(encoding="utf-8"):
        raise SystemExit(f"SMX-019 editor surface missing author operation: {expected}")

for code in ["required_feature_unsupported", "required_capability_denied", "creation_digest_mismatch", "host_identity_forbidden"]:
    if code not in model + player:
        raise SystemExit(f"SMX-019 typed boundary missing: {code}")

if "connection_handle" not in model or "connection_id" not in model:
    raise SystemExit("SMX-019 R-019-01 regression boundary is missing")

for plane in ["authoring", "collaboration"]:
    if f"Object.hasOwn(creation, '{plane}')" not in tests:
        raise SystemExit(f"SMX-019 published-plane regression missing: {plane}")

for marker in ["setOffline(true)", "topology=peer", "deny=camera", "unsupported_feature=1", "deny_storage=1"]:
    if marker not in harness:
        raise SystemExit(f"SMX-019 browser harness missing destructive path: {marker}")

for marker in ["D-111", "D-112", "D-113", "D-114", "D-115", "D-116", "E-083", "E-084", "E-085", "E-086", "E-087", "O-028"]:
    if marker not in decisions or marker not in local_evidence:
        raise SystemExit(f"SMX-019 durable/local evidence register missing {marker}")

if "## SMX-019 review record" not in hypotheses:
    raise SystemExit("SMX-019 hypothesis review record missing")
if "## SMX-019 browser vertical-slice retrieval rules" not in rag:
    raise SystemExit("SMX-019 RAG retrieval rules missing")
if "34 adversarial/boundary tests" not in rag:
    raise SystemExit("SMX-019 RAG must record the 34-test evidence boundary")

for marker in ["playwright@1.55.0", "ws@8.18.3", "browser_harness.mjs", "test_model.mjs", "upload-artifact@v4"]:
    if marker not in workflow:
        raise SystemExit(f"SMX-019 CI workflow missing reproducibility pin/step: {marker}")

staging = list((ROOT / "tools").glob("_smx019_payload.*"))
if staging:
    raise SystemExit(f"SMX-019 staging payload files must not survive final repair: {[p.name for p in staging]}")

print("SMX-019 browser vertical-slice contract validated")
