#!/usr/bin/env python3
"""Validate SMX-007 non-normative lifecycle fixtures and references."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-007-LIFECYCLE-RESTORE.md"
FIXTURES = ROOT / "docs/research/SMX-007-LIFECYCLE-FIXTURES.json"
CORPUS = ROOT / "docs/research/SMX-001-EVALUATION-CORPUS.json"
REQUIRED = [
    DOC,
    FIXTURES,
    ROOT / "experiments/smx-007-lifecycle-model/README.md",
    ROOT / "experiments/smx-007-lifecycle-model/model.py",
    ROOT / "experiments/smx-007-lifecycle-model/test_model.py",
]

errors: list[str] = []
for path in REQUIRED:
    if not path.is_file():
        errors.append(f"missing SMX-007 file: {path.relative_to(ROOT)}")

try:
    fixture_data = json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-007 fixture JSON: {exc}")
    fixture_data = {}

try:
    corpus_data = json.loads(CORPUS.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-001 corpus JSON while validating SMX-007: {exc}")
    corpus_data = {}

if fixture_data:
    if fixture_data.get("schema") != "splashmx-smx007-lifecycle-fixtures-v1":
        errors.append("unexpected SMX-007 fixture schema")
    if fixture_data.get("status") != "non-normative-research-fixtures":
        errors.append("SMX-007 fixtures must remain explicitly non-normative")

    invariants = fixture_data.get("lifecycle_invariants")
    expected_invariants = [f"LIF-{index:03d}" for index in range(1, 19)]
    if invariants != expected_invariants:
        errors.append("SMX-007 lifecycle_invariants must be LIF-001 through LIF-018")

    corpus_ids = {
        item.get("id")
        for key in ("cases", "adversarial_cases")
        for item in corpus_data.get(key, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    entries = fixture_data.get("fixtures")
    fixture_ids: list[str] = []
    if not isinstance(entries, list) or not entries:
        errors.append("SMX-007 fixtures must contain a non-empty fixtures list")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append("SMX-007 fixture list contains a non-object entry")
                continue

            fixture_id = entry.get("id")
            if not isinstance(fixture_id, str) or not re.fullmatch(r"LT-\d{3}", fixture_id):
                errors.append(f"invalid SMX-007 fixture id: {fixture_id!r}")
            else:
                fixture_ids.append(fixture_id)

            cases = entry.get("cases")
            if not isinstance(cases, list) or not cases:
                errors.append(f"SMX-007 fixture {fixture_id!r} has no corpus coverage")
            else:
                unknown = sorted(set(map(str, cases)) - corpus_ids)
                if unknown:
                    errors.append(
                        f"SMX-007 fixture {fixture_id!r} references unknown corpus IDs: "
                        + ", ".join(unknown)
                    )

            expected = entry.get("expected")
            if not isinstance(expected, list) or not expected:
                errors.append(f"SMX-007 fixture {fixture_id!r} has no expected invariants")
            else:
                unknown = sorted(set(map(str, expected)) - set(expected_invariants))
                if unknown:
                    errors.append(
                        f"SMX-007 fixture {fixture_id!r} references unknown invariants: "
                        + ", ".join(unknown)
                    )

    if len(fixture_ids) != len(set(fixture_ids)):
        errors.append("duplicate SMX-007 fixture IDs")

    direct = list(fixture_data.get("direct_case_coverage", [])) + list(
        fixture_data.get("direct_adversarial_coverage", [])
    )
    unknown_direct = sorted(set(map(str, direct)) - corpus_ids)
    if unknown_direct:
        errors.append(
            "SMX-007 direct coverage references unknown corpus IDs: "
            + ", ".join(unknown_direct)
        )

    if DOC.is_file():
        document = DOC.read_text(encoding="utf-8")
        for identifier in expected_invariants + fixture_ids:
            if identifier not in document:
                errors.append(f"SMX-007 research document does not reference {identifier}")

if errors:
    print("SMX-007 validation failed:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SMX-007 research validation passed")
