#!/usr/bin/env python3
"""Validate SMX-018 collaboration harness fixtures, synthesis, regressions and RAG."""
from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-018-COLLABORATION-HARNESS.md"
FIXTURES = ROOT / "docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json"
DECISION = ROOT / "docs/research/SMX-018-DECISION-EVIDENCE.md"
README = ROOT / "experiments/smx-018-collaboration-harness/README.md"
MODEL = ROOT / "experiments/smx-018-collaboration-harness/model.py"
TESTS = ROOT / "experiments/smx-018-collaboration-harness/test_harness.py"
MEASURE = ROOT / "experiments/smx-018-collaboration-harness/measure.py"
RAG = ROOT / "docs/03-RAG-INDEX.md"
HYP = ROOT / "docs/02-ARCHITECTURE-HYPOTHESES.md"
LOG = ROOT / "docs/05-DECISION-AND-EVIDENCE-LOG.md"
UPSTREAM = ROOT / "docs/research/SMX-011-COLLABORATION-SEMANTICS.md"
REQUIRED = [DOC, FIXTURES, DECISION, README, MODEL, TESTS, MEASURE, RAG, HYP, LOG, UPSTREAM]
errors: list[str] = []

for path in REQUIRED:
    if not path.is_file():
        errors.append(f"missing SMX-018 file: {path.relative_to(ROOT)}")

try:
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-018 fixture JSON: {exc}")
    fixtures = {}

invariants = [f"CH-{i:03d}" for i in range(1, 29)]
trace_ids = [f"CR-{i:03d}" for i in range(1, 29)]
repairs = [f"R-018-{i:02d}" for i in range(1, 5)]

if fixtures:
    if fixtures.get("schema") != "splashmx-smx018-collaboration-harness-v1":
        errors.append("unexpected SMX-018 fixture schema")
    if fixtures.get("status") != "non-normative-destructive-research-fixtures":
        errors.append("SMX-018 fixtures must remain explicitly non-normative")
    found_invariants = [item.get("id") for item in fixtures.get("semantic_invariants", [])]
    if found_invariants != invariants:
        errors.append("SMX-018 invariants must be CH-001 through CH-028 in order")
    found_traces = [item.get("id") for item in fixtures.get("fixtures", [])]
    if found_traces != trace_ids:
        errors.append("SMX-018 fixture IDs must be CR-001 through CR-028 in order")
    known = set(invariants)
    covered: set[str] = set()
    for entry in fixtures.get("fixtures", []):
        expected = set(entry.get("expected", []))
        unknown = expected - known
        if unknown:
            errors.append(f"{entry.get('id')} references unknown invariant(s): {sorted(unknown)}")
        if not entry.get("purpose"):
            errors.append(f"{entry.get('id')} has no purpose")
        covered.update(expected)
    if covered != known:
        errors.append(f"SMX-018 fixtures do not cover all invariants: {sorted(known-covered)}")
    found_repairs = [item.get("id") for item in fixtures.get("observed_repairs", [])]
    if found_repairs != repairs:
        errors.append("SMX-018 observed repairs must remain R-018-01 through R-018-04")
    bundle = fixtures.get("protected_semantics", {}).get("asset_revision_bundle", [])
    for required in (
        "AssetId", "immutable digest", "source identity/metadata", "audio/media semantics",
        "provenance", "licence", "derivation",
    ):
        if required not in bundle:
            errors.append(f"SMX-018 protected asset bundle lost {required!r}")

if TESTS.is_file():
    test_text = TESTS.read_text(encoding="utf-8")
    try:
        tree = ast.parse(test_text)
        test_count = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        )
        if test_count != 39:
            errors.append(f"SMX-018 adversarial suite must contain 39 tests, found {test_count}")
    except SyntaxError as exc:
        errors.append(f"SMX-018 test file does not parse: {exc}")
    for i in range(1, 29):
        if f"test_cr{i:03d}_" not in test_text:
            errors.append(f"SMX-018 tests do not implement CR-{i:03d}")

if DOC.is_file():
    text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "39 deterministic tests", "R-018-01", "R-018-04", "offline", "reconnect",
        "delete vs edit", "reparent", "timeline", "grouping", "component update",
        "selective undo", "permission", "presence", "DefinitionId", "document validity",
        "source/audio/provenance", "AssetId", "licence", "derivation", "H-013", "H-017",
        "H-018", "O-021", "O-026", "production CRDT/database/browser measurements",
    ):
        if phrase.lower() not in text.lower():
            errors.append(f"SMX-018 synthesis is missing required phrase: {phrase!r}")

if DECISION.is_file():
    text = DECISION.read_text(encoding="utf-8")
    for identifier in [
        *(f"D-{i:03d}" for i in range(99, 105)),
        *(f"E-{i:03d}" for i in range(74, 77)),
        "O-026",
    ]:
        if identifier not in text:
            errors.append(f"SMX-018 decision/evidence handoff is missing {identifier}")

if UPSTREAM.is_file():
    text = UPSTREAM.read_text(encoding="utf-8")
    for phrase in (
        "## SMX-018 destructive-harness reconciliation", "R-018-01", "R-018-02",
        "R-018-03", "R-018-04", "DefinitionId", "incident live connections",
    ):
        if phrase not in text:
            errors.append(f"SMX-011 collaboration contract is missing SMX-018 reconciliation marker: {phrase!r}")

if RAG.is_file():
    text = RAG.read_text(encoding="utf-8")
    for phrase in (
        "SMX-018 collaboration-harness retrieval rules", "SMX-018-COLLABORATION-HARNESS.md",
        "SMX-018-DECISION-EVIDENCE.md", "CH-001", "CH-028", "CR-001", "CR-028",
        "R-018-01", "R-018-04", "source/audio/provenance",
    ):
        if phrase not in text:
            errors.append(f"RAG index is missing SMX-018 retrieval marker: {phrase!r}")

if HYP.is_file():
    text = HYP.read_text(encoding="utf-8")
    for phrase in (
        "## SMX-018 review record", "H-013", "H-017", "H-018", "O-026",
        "R-018-01", "R-018-04",
    ):
        if phrase not in text:
            errors.append(f"hypothesis register is missing SMX-018 marker: {phrase!r}")

if LOG.is_file():
    text = LOG.read_text(encoding="utf-8")
    for phrase in (
        "## SMX-018 decision/evidence register", "D-099", "D-104", "E-074", "E-076",
        "O-026", "R-018-01", "R-018-04", "protected source/audio/provenance",
    ):
        if phrase not in text:
            errors.append(f"project decision/evidence register is missing SMX-018 marker: {phrase!r}")

if errors:
    print("SMX-018 validation failed:")
    for error in errors:
        print(" -", error)
    sys.exit(1)
print("SMX-018 research validation passed")
