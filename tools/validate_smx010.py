#!/usr/bin/env python3
"""Validate SMX-010 non-normative runtime-multiplayer fixtures and references."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-010-RUNTIME-MULTIPLAYER.md"
FIXTURES = ROOT / "docs/research/SMX-010-RUNTIME-MULTIPLAYER-FIXTURES.json"
CORPUS = ROOT / "docs/research/SMX-001-EVALUATION-CORPUS.json"
REQUIRED = [
    DOC,
    FIXTURES,
    ROOT / "experiments/smx-010-multiplayer-model/README.md",
    ROOT / "experiments/smx-010-multiplayer-model/model.py",
    ROOT / "experiments/smx-010-multiplayer-model/test_model.py",
]

errors: list[str] = []
for path in REQUIRED:
    if not path.is_file():
        errors.append(f"missing SMX-010 file: {path.relative_to(ROOT)}")

try:
    fixture_data = json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-010 fixture JSON: {exc}")
    fixture_data = {}

try:
    corpus_data = json.loads(CORPUS.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-001 corpus JSON while validating SMX-010: {exc}")
    corpus_data = {}

if fixture_data:
    if fixture_data.get("schema") != "splashmx-smx010-runtime-multiplayer-fixtures-v1":
        errors.append("unexpected SMX-010 fixture schema")
    if fixture_data.get("status") != "non-normative-research-fixtures":
        errors.append("SMX-010 fixtures must remain explicitly non-normative")

    invariants = fixture_data.get("boundary_invariants")
    expected_invariants = [f"NET-{index:03d}" for index in range(1, 21)]
    if invariants != expected_invariants:
        errors.append("SMX-010 boundary_invariants must be NET-001 through NET-020")

    corpus_ids = {
        item.get("id")
        for key in ("cases", "adversarial_cases")
        for item in corpus_data.get(key, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    entries = fixture_data.get("fixtures")
    fixture_ids: list[str] = []
    if not isinstance(entries, list) or not entries:
        errors.append("SMX-010 fixtures must contain a non-empty fixtures list")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append("SMX-010 fixture list contains a non-object entry")
                continue
            fixture_id = entry.get("id")
            if not isinstance(fixture_id, str) or not re.fullmatch(r"NT-\d{3}", fixture_id):
                errors.append(f"invalid SMX-010 fixture id: {fixture_id!r}")
            else:
                fixture_ids.append(fixture_id)

            cases = entry.get("cases")
            if not isinstance(cases, list) or not cases:
                errors.append(f"SMX-010 fixture {fixture_id!r} has no corpus coverage")
            else:
                unknown = sorted(set(map(str, cases)) - corpus_ids)
                if unknown:
                    errors.append(
                        f"SMX-010 fixture {fixture_id!r} references unknown corpus IDs: "
                        + ", ".join(unknown)
                    )

            expected = entry.get("expected")
            if not isinstance(expected, list) or not expected:
                errors.append(f"SMX-010 fixture {fixture_id!r} has no expected invariants")
            else:
                unknown = sorted(set(map(str, expected)) - set(expected_invariants))
                if unknown:
                    errors.append(
                        f"SMX-010 fixture {fixture_id!r} references unknown invariants: "
                        + ", ".join(unknown)
                    )

    expected_fixtures = [f"NT-{index:03d}" for index in range(1, 21)]
    if fixture_ids != expected_fixtures:
        errors.append("SMX-010 fixture IDs must be NT-001 through NT-020 in order")
    if len(fixture_ids) != len(set(fixture_ids)):
        errors.append("duplicate SMX-010 fixture IDs")

    direct = list(fixture_data.get("direct_case_coverage", [])) + list(
        fixture_data.get("direct_adversarial_coverage", [])
    )
    unknown_direct = sorted(set(map(str, direct)) - corpus_ids)
    if unknown_direct:
        errors.append(
            "SMX-010 direct coverage references unknown corpus IDs: "
            + ", ".join(unknown_direct)
        )

    if DOC.is_file():
        document = DOC.read_text(encoding="utf-8")
        for identifier in expected_invariants:
            if identifier not in document:
                errors.append(f"SMX-010 research document does not reference {identifier}")
        # Fixture-by-fixture corpus mapping lives canonically in the companion JSON.
        # The prose document must advertise the complete inclusive fixture range but
        # need not duplicate every NT identifier merely to satisfy validation.
        if "`NT-001` through `NT-020`" not in document:
            errors.append("SMX-010 research document must reference the NT-001 through NT-020 fixture range")
        required_phrases = (
            "Godot 4.7.2",
            "source/audio/provenance",
            "SMX-017",
            "peer-hosted",
            "dedicated authoritative",
            "collaborative editing",
        )
        for phrase in required_phrases:
            if phrase not in document:
                errors.append(
                    f"SMX-010 research document is missing required phrase: {phrase!r}"
                )

if errors:
    print("SMX-010 validation failed:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SMX-010 research validation passed")
