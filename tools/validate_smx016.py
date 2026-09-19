#!/usr/bin/env python3
"""Validate SMX-016 adversarial security fixtures, synthesis, RAG and evidence."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-016-SECURITY-HARNESS.md"
FIXTURES = ROOT / "docs/research/SMX-016-SECURITY-FIXTURES.json"
DECISION = ROOT / "docs/research/SMX-016-DECISION-EVIDENCE.md"
RAG = ROOT / "docs/03-RAG-INDEX.md"
HYP = ROOT / "docs/02-ARCHITECTURE-HYPOTHESES.md"
LOG = ROOT / "docs/05-DECISION-AND-EVIDENCE-LOG.md"
SEC = ROOT / "docs/research/SMX-006-CAPABILITY-SANDBOX.md"
REQUIRED = [
    DOC, FIXTURES, DECISION, RAG, HYP, LOG, SEC,
    ROOT / "experiments/smx-016-security-harness/README.md",
    ROOT / "experiments/smx-016-security-harness/model.py",
    ROOT / "experiments/smx-016-security-harness/test_harness.py",
]
errors: list[str] = []
for path in REQUIRED:
    if not path.is_file():
        errors.append(f"missing SMX-016 file: {path.relative_to(ROOT)}")

try:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-016 fixture JSON: {exc}")
    fixtures = {}

invariants = [f"ADV-{i:03d}" for i in range(1, 29)]
fixture_ids = [f"AT-{i:03d}" for i in range(1, 29)]
known_cases = {f"C-{i:03d}" for i in range(1, 29)} | {f"A-{i:03d}" for i in range(1, 17)}
required_families = {
    "package-path-and-container",
    "canonical-structure-and-authority-fields",
    "exact-lock-and-dependency-confusion",
    "capability-escalation-delegation-revocation",
    "nested-confused-deputy",
    "ir-allocation-event-timer-service-exhaustion",
    "migration-ordering-and-capability-freedom",
    "network-forgery-replay-scope-and-resource",
    "target-host-boundaries",
    "protected-source-audio-provenance",
    "decoder-preflight",
}
if fixtures:
    if fixtures.get("schema") != "splashmx-smx016-adversarial-security-fixtures-v1":
        errors.append("unexpected SMX-016 fixture schema")
    if fixtures.get("status") != "non-normative-research-fixtures":
        errors.append("SMX-016 fixtures must remain explicitly non-normative")
    if fixtures.get("security_invariants") != invariants:
        errors.append("SMX-016 security_invariants must be ADV-001 through ADV-028")
    if set(fixtures.get("required_attack_families", [])) != required_families:
        errors.append("SMX-016 required attack-family set changed unexpectedly")
    ids: list[str] = []
    covered: set[str] = set()
    for entry in fixtures.get("fixtures", []):
        fixture_id = entry.get("id")
        ids.append(fixture_id)
        if not isinstance(fixture_id, str) or not re.fullmatch(r"AT-\d{3}", fixture_id):
            errors.append(f"invalid SMX-016 fixture id: {fixture_id!r}")
        unknown_cases = set(entry.get("cases", [])) - known_cases
        if unknown_cases:
            errors.append(f"{fixture_id} references unknown corpus IDs: {sorted(unknown_cases)}")
        unknown_invariants = set(entry.get("expected", [])) - set(invariants)
        if unknown_invariants:
            errors.append(f"{fixture_id} references unknown invariants: {sorted(unknown_invariants)}")
        covered.update(entry.get("expected", []))
        if not entry.get("purpose"):
            errors.append(f"{fixture_id} has no purpose")
    if ids != fixture_ids:
        errors.append("SMX-016 fixture IDs must be AT-001 through AT-028 in order")
    if covered != set(invariants):
        errors.append(f"SMX-016 fixtures do not cover all invariants: {sorted(set(invariants)-covered)}")
    repairs = [entry.get("id") for entry in fixtures.get("observed_repairs", [])]
    if repairs != ["R-016-01", "R-016-02", "R-016-03", "R-016-04"]:
        errors.append("SMX-016 observed repairs must remain R-016-01 through R-016-04")
    bundle = fixtures.get("protected_semantics", {}).get("asset_revision_bundle", [])
    for required in ("AssetId", "immutable digest", "source identity", "audio/media semantics", "provenance", "licence", "derivation"):
        if required not in bundle:
            errors.append(f"SMX-016 protected asset bundle lost {required!r}")

if DOC.is_file():
    text = DOC.read_text(encoding="utf-8")
    for identifier in invariants + fixture_ids + ["R-016-01", "R-016-02", "R-016-03", "R-016-04"]:
        if identifier not in text:
            errors.append(f"SMX-016 synthesis does not reference {identifier}")
    for phrase in (
        "38 deterministic", "not an end-to-end sandbox certification", "before extraction",
        "use-time", "host-call recorder", "decoder recorder", "source/audio/provenance",
        "AssetId", "web_hardened", "web_official", "native", "headless",
        "H-006", "H-009", "H-011", "H-014", "H-015", "O-025",
        "SMX-017", "SMX-018", "SMX-019", "SMX-020",
    ):
        if phrase.lower() not in text.lower():
            errors.append(f"SMX-016 synthesis is missing required phrase: {phrase!r}")

if DECISION.is_file():
    text = DECISION.read_text(encoding="utf-8")
    for identifier in [*(f"D-{i:03d}" for i in range(91, 99)), *(f"E-{i:03d}" for i in range(70, 74)), "O-025"]:
        if identifier not in text:
            errors.append(f"SMX-016 decision/evidence handoff is missing {identifier}")

if RAG.is_file():
    text = RAG.read_text(encoding="utf-8")
    for phrase in (
        "SMX-016 adversarial-security retrieval rules", "ADV-001", "ADV-028",
        "AT-001", "AT-028", "SMX-016-DECISION-EVIDENCE.md", "source/audio/provenance",
    ):
        if phrase not in text:
            errors.append(f"RAG index is missing SMX-016 retrieval marker: {phrase!r}")

if HYP.is_file():
    text = HYP.read_text(encoding="utf-8")
    for phrase in ("## SMX-016 review", "H-006", "H-009", "H-011", "H-014", "H-015", "O-025"):
        if phrase not in text:
            errors.append(f"hypothesis register is missing SMX-016 marker: {phrase!r}")

if LOG.is_file():
    text = LOG.read_text(encoding="utf-8")
    for phrase in (
        "## SMX-016 decision/evidence register", "D-091", "D-098", "E-070", "E-073", "O-025"
    ):
        if phrase not in text:
            errors.append(f"project decision/evidence register is missing SMX-016 marker: {phrase!r}")
    if "protected source/audio/provenance" not in text:
        errors.append("project decision/evidence register lost the SMX-016 protected-media boundary")

if SEC.is_file():
    text = SEC.read_text(encoding="utf-8")
    for phrase in (
        "## SMX-016 hostile-proof reconciliation", "R-016-01", "R-016-02", "R-016-03", "R-016-04",
        "recursive", "use-time",
    ):
        if phrase.lower() not in text.lower():
            errors.append(f"SMX-006 security contract is missing SMX-016 reconciliation marker: {phrase!r}")

if errors:
    print("SMX-016 validation failed:")
    for error in errors:
        print(" -", error)
    sys.exit(1)
print("SMX-016 research validation passed")
