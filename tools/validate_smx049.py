#!/usr/bin/env python3
"""Validate durable SMX-049 compatibility-programme evidence."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/implementation/SMX-049-COMPATIBILITY-RETENTION.md"
FIXTURE = ROOT / "spec/production/smx049-compatibility-fixtures.json"
MODEL = ROOT / "experiments/smx-049-compatibility/model.py"
TEST = ROOT / "tests/production/test_smx049.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-049 validation failed: {message}")


def main() -> None:
    for path in (DOC, FIXTURE, MODEL, TEST):
        require(path.is_file(), f"missing {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    model_text = MODEL.read_text(encoding="utf-8")
    test_text = TEST.read_text(encoding="utf-8")
    ast.parse(model_text, filename=str(MODEL))
    ast.parse(test_text, filename=str(TEST))

    required_doc_anchors = (
        "explicit-generation support with bounded migration and exact retained",
        "splashmx.project-revision/schema-0",
        "splashmx.project-revision/schema-1",
        "splashmx.package-manifest/1",
        "splashmx.creation/1",
        "splashmx.generic-player/1",
        "splashmx.world-save/1",
        "Revocation therefore wins over compatibility",
        "Protected source/audio/provenance invariant",
        "Handoff to SMX-050 and SMX-052",
        "No Architecture-v1 amendment is required",
    )
    for anchor in required_doc_anchors:
        require(anchor in doc, f"decision document lost required contract: {anchor}")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    require(fixture.get("schema") == "splashmx.smx049-compatibility-programme/1", "fixture schema changed")
    policy = fixture.get("policy", {})
    require(policy.get("support_basis") == "explicit-generation-rule-plus-executable-fixture", "support basis changed")
    require(policy.get("max_migration_steps") == 8, "migration bound changed")
    require(policy.get("security_revocation_precedence") is True, "revocation precedence weakened")
    require(policy.get("protected_asset_revision_atomic") is True, "protected Asset atomicity weakened")
    require(policy.get("hosted_binding") == "exact-creation-revision-plus-exact-runtime-profile", "hosted exact runtime binding changed")
    require(policy.get("offline_binding") == "exact-creation-revision-plus-exact-runtime-profile", "offline exact runtime binding changed")

    generations = fixture.get("current_generations", [])
    generation_keys = {(row.get("artifact_class"), row.get("generation")) for row in generations}
    expected = {
        ("canonical-project", "splashmx.project-revision/schema-0"),
        ("canonical-project", "splashmx.project-revision/schema-1"),
        ("package-component", "splashmx.package-manifest/1+resolution-lock/1"),
        ("creation-revision", "splashmx.creation/1"),
        ("world-save", "splashmx.world-save/1"),
    }
    require(expected <= generation_keys, "supported generation matrix is incomplete")

    fixtures = fixture.get("fixtures", [])
    ids = [row.get("id") for row in fixtures]
    require(ids == [f"CMP-{index:03d}" for index in range(1, 21)], "CMP-001..020 fixture registry changed")
    require(len(ids) == len(set(ids)), "duplicate fixture identity")

    required_model_anchors = (
        "CompatibilityAction.RETAINED_RUNTIME",
        "compatibility.revoked_artifact",
        "compatibility.unsupported_generation",
        "compatibility.unsupported_required_semantics",
        "compatibility.runtime_unavailable",
        "estimate_retained_runtime_bytes",
    )
    for anchor in required_model_anchors:
        require(anchor in model_text, f"executable model lost {anchor}")

    required_test_anchors = (
        "serialization.unsupported_version",
        "serialization.asset_revision_mismatch",
        "simulate_creation_v2_transition",
        "compatibility.revoked_artifact",
        "compatibility.runtime_unavailable",
    )
    for anchor in required_test_anchors:
        require(anchor in test_text, f"adversarial test lost {anchor}")

    print("SMX-049 compatibility programme validated: CMP-001..020")


if __name__ == "__main__":
    main()
