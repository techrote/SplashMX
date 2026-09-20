#!/usr/bin/env python3
"""Validate the SMX-034 selection handoff and non-droppable package boundaries."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-034-PACKAGE-SUBSTRATE-SELECTION.md"
FIXTURES = ROOT / "docs/research/SMX-034-PACKAGE-SUBSTRATE-FIXTURES.json"
SPIKE = ROOT / "experiments/smx-034-package-spike/spike.py"
TESTS = ROOT / "experiments/smx-034-package-spike/test_spike.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, SPIKE, TESTS):
        require(path.is_file(), f"missing SMX-034 artifact: {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    required_phrases = [
        "bounded deterministic PubGrub-family",
        "exact resolution lock",
        "SPB1",
        "deterministic-CBOR index",
        "no paths, extraction, links, install scripts",
        "CatalogSnapshot",
        "Trust is not capability",
        "No ambient install authority",
        "SMX-035 production handoff",
        "one exact revision per `PackageId`",
        "Runtime floating resolution",
    ]
    for phrase in required_phrases:
        require(phrase in doc, f"SMX-034 selection lost required phrase: {phrase}")

    # Keep the protected Asset contract explicit without requiring one particular
    # prose sentence. These are the seven indivisible semantic groups inherited
    # from Architecture v1 and the production serialization/streaming work.
    protected_phrases = [
        "revision/content digest",
        "source digest and logical source identity",
        "exact source metadata",
        "audio/media semantic metadata",
        "provenance",
        "licence/attribution",
        "derivation lineage",
    ]
    for phrase in protected_phrases:
        require(phrase in doc, f"SMX-034 protected-media contract lost: {phrase}")
    require(
        "may not combine fields from competing Asset revisions" in doc,
        "SMX-034 must continue to reject protected-Asset field mixing",
    )

    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(data.get("schema") == "splashmx.smx034-package-substrate-fixtures/1", "wrong fixture schema")
    fixtures = data.get("fixtures")
    require(isinstance(fixtures, list), "fixtures must be a list")
    ids = [row.get("id") for row in fixtures]
    require(ids == [f"PS-{number:03d}" for number in range(1, 29)], "PS fixture set must remain contiguous PS-001..PS-028")
    classes = {row.get("class") for row in fixtures}
    require({"version", "resolution", "resource", "bundle", "authority", "protected-media", "trust", "identity"}.issubset(classes), "fixture classes incomplete")

    spike = SPIKE.read_text(encoding="utf-8")
    for token in (
        "decode_canonical_cbor",
        "encode_canonical_cbor",
        "max_decisions",
        "max_total_bytes",
        "SPB1_MAGIC",
        "_FORBIDDEN_AUTHORITY_KEYS",
        "_PROTECTED_ASSET_KEYS",
    ):
        require(token in spike, f"spike lost required boundary: {token}")

    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_one_revision_per_package_conflict_is_typed",
        "test_solver_work_limit_fails_closed",
        "test_digest_substitution_rejected",
        "test_path_or_extraction_metadata_is_not_in_schema",
        "test_serialized_capability_grant_rejected_recursively",
        "test_protected_asset_field_mixing_surface_is_closed",
    ):
        require(token in tests, f"adversarial regression missing: {token}")

    print("SMX-034 package-substrate selection contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-034 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
