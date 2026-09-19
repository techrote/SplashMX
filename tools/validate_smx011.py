#!/usr/bin/env python3
"""Validate SMX-011 non-normative collaboration fixtures and research contract."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-011-COLLABORATION-SEMANTICS.md"
FIXTURES = ROOT / "docs/research/SMX-011-COLLABORATION-FIXTURES.json"
CORPUS = ROOT / "docs/research/SMX-001-EVALUATION-CORPUS.json"
REQUIRED = [
    DOC,
    FIXTURES,
    ROOT / "experiments/smx-011-collaboration-model/README.md",
    ROOT / "experiments/smx-011-collaboration-model/model.py",
    ROOT / "experiments/smx-011-collaboration-model/test_model.py",
]

errors: list[str] = []
for path in REQUIRED:
    if not path.is_file():
        errors.append(f"missing SMX-011 file: {path.relative_to(ROOT)}")

try:
    fixture_data = json.loads(FIXTURES.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-011 fixture JSON: {exc}")
    fixture_data = {}

try:
    corpus_data = json.loads(CORPUS.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    errors.append(f"invalid SMX-001 corpus JSON while validating SMX-011: {exc}")
    corpus_data = {}

if fixture_data:
    if fixture_data.get("schema") != "splashmx-smx011-collaboration-fixtures-v1":
        errors.append("unexpected SMX-011 fixture schema")
    if fixture_data.get("status") != "non-normative-research-fixtures":
        errors.append("SMX-011 fixtures must remain explicitly non-normative")

    expected_invariants = [f"COL-{index:03d}" for index in range(1, 25)]
    if fixture_data.get("boundary_invariants") != expected_invariants:
        errors.append("SMX-011 boundary_invariants must be COL-001 through COL-024")

    corpus_ids = {
        item.get("id")
        for key in ("cases", "adversarial_cases")
        for item in corpus_data.get(key, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    entries = fixture_data.get("fixtures")
    fixture_ids: list[str] = []
    if not isinstance(entries, list) or not entries:
        errors.append("SMX-011 fixtures must contain a non-empty fixtures list")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append("SMX-011 fixture list contains a non-object entry")
                continue
            fixture_id = entry.get("id")
            if not isinstance(fixture_id, str) or not re.fullmatch(r"CF-\d{3}", fixture_id):
                errors.append(f"invalid SMX-011 fixture id: {fixture_id!r}")
            else:
                fixture_ids.append(fixture_id)

            cases = entry.get("cases")
            if not isinstance(cases, list) or not cases:
                errors.append(f"SMX-011 fixture {fixture_id!r} has no corpus coverage")
            else:
                unknown = sorted(set(map(str, cases)) - corpus_ids)
                if unknown:
                    errors.append(
                        f"SMX-011 fixture {fixture_id!r} references unknown corpus IDs: "
                        + ", ".join(unknown)
                    )

            expected = entry.get("expected")
            if not isinstance(expected, list) or not expected:
                errors.append(f"SMX-011 fixture {fixture_id!r} has no expected invariants")
            else:
                unknown = sorted(set(map(str, expected)) - set(expected_invariants))
                if unknown:
                    errors.append(
                        f"SMX-011 fixture {fixture_id!r} references unknown invariants: "
                        + ", ".join(unknown)
                    )

    expected_fixtures = [f"CF-{index:03d}" for index in range(1, 29)]
    if fixture_ids != expected_fixtures:
        errors.append("SMX-011 fixture IDs must be CF-001 through CF-028 in order")
    if len(fixture_ids) != len(set(fixture_ids)):
        errors.append("duplicate SMX-011 fixture IDs")

    direct = list(fixture_data.get("direct_case_coverage", [])) + list(
        fixture_data.get("direct_adversarial_coverage", [])
    )
    unknown_direct = sorted(set(map(str, direct)) - corpus_ids)
    if unknown_direct:
        errors.append(
            "SMX-011 direct coverage references unknown corpus IDs: "
            + ", ".join(unknown_direct)
        )

if DOC.is_file():
    document = DOC.read_text(encoding="utf-8")
    for identifier in [f"COL-{index:03d}" for index in range(1, 25)]:
        if identifier not in document:
            errors.append(f"SMX-011 research document does not reference {identifier}")
    if "`CF-001` through `CF-028`" not in document:
        errors.append("SMX-011 research document must reference the CF-001 through CF-028 fixture range")
    required_phrases = (
        "human-visible",
        "runtime multiplayer",
        "source/audio/provenance",
        "SMX-018",
        "Automerge",
        "Yjs",
        "ShareDB",
        "Convergence is not enough",
        "permission",
        "known-unloaded",
    )
    lower = document.lower()
    for phrase in required_phrases:
        if phrase.lower() not in lower:
            errors.append(
                f"SMX-011 research document is missing required phrase: {phrase!r}"
            )

if errors:
    print("SMX-011 validation failed:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SMX-011 research validation passed")
