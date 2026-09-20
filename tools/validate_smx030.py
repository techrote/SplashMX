#!/usr/bin/env python3
"""Repository-native contract validator for SMX-030."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-030 validation failed: {message}")


def text(path: str) -> str:
    target = ROOT / path
    require(target.is_file(), f"missing {path}")
    return target.read_text(encoding="utf-8")


def main() -> None:
    architecture = text("docs/architecture/ARCHITECTURE-V1.md")
    for phrase in (
        "known-unloaded",
        "Logical residency is object/subgraph-centric.",
        "Cache eviction is non-semantic.",
        "A stable `AssetId` selects one complete immutable protected revision",
    ):
        require(phrase in architecture, f"Architecture-v1 authority missing {phrase!r}")

    manifest = json.loads(text("src/MODULES.json"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("runtime.streaming" in modules, "runtime.streaming module missing")
    streaming = modules["runtime.streaming"]
    require(streaming["owner_issue"] == "SMX-030", "wrong streaming module owner")
    require(streaming["status"] == "implemented", "runtime.streaming is not implemented")
    require(set(streaming["gate_ids"]) == {"GATE-01", "GATE-09"}, "streaming gate ownership drift")
    require(
        set(streaming["canonical_identity_inputs"]) == {"ThingId", "AssetId", "ProjectRevisionId"},
        "streaming identity surface drift",
    )
    for forbidden in ("cache_key", "url", "session_id", "process_handle"):
        require(forbidden in streaming["forbidden_identity_classes"], f"identity guardrail lost {forbidden}")

    fixtures = json.loads(text("spec/production/smx030-streaming-fixtures.json"))
    require(fixtures["schema"] == "splashmx.smx030-streaming-fixtures/1", "fixture schema drift")
    require(fixtures["issue"] == "SMX-030", "fixture issue drift")
    ids = [row["id"] for row in fixtures["fixtures"]]
    require(ids == [f"STP-{index:03d}" for index in range(1, 29)], "STP-001..STP-028 fixture coverage drift")
    require(
        fixtures["retained_streaming_invariants"] == [f"STR-{index:03d}" for index in range(1, 21)],
        "STR-001..STR-020 retained streaming evidence drift",
    )
    require(
        fixtures["protected_media_fields"] == [
            "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
            "provenance", "licence_attribution", "derivation_lineage",
        ],
        "protected-media field set drift",
    )
    for retained in fixtures["authority"]:
        require((ROOT / retained).is_file(), f"retained authority missing: {retained}")

    implementation = text("src/splashmx/runtime/streaming.py")
    for token in (
        "class ExactArtifactDescriptor",
        "class AcquisitionLimits",
        "class ImmutableArtifactCache",
        "class ExactAcquirer",
        "class StreamingRuntime",
        "def encode_project_artifact",
        "def decode_project_artifact",
        "def encode_ir_artifact",
        "def decode_ir_artifact",
        "streaming.integrity_failure",
        "streaming.dependency_unavailable",
        "streaming.protected_asset_conflict",
        "ReferenceState.TOMBSTONED",
        "staged.rehydrate",
    ):
        require(token in implementation, f"production implementation missing {token!r}")

    doc = text("docs/implementation/SMX-030-LOGICAL-STREAMING.md")
    for heading in (
        "## Production contract",
        "## Exact acquisition and bounded dependency graph",
        "## Canonical and Behaviour migration before activation",
        "## Immutable cache and offline exactness",
        "## Atomic lifecycle and tombstone behaviour",
        "## Adversarial and boundary coverage",
        "## Protected source/audio/provenance boundary",
    ):
        require(heading in doc, f"implementation documentation missing {heading}")
    for protected in (
        "content digest", "source identity", "source metadata", "audio/media semantics",
        "provenance", "licence/attribution", "derivation lineage",
    ):
        require(protected in doc, f"implementation docs weakened protected field {protected!r}")
    for phrase in (
        "Containment is not consulted as an implicit load unit",
        "cache is an optimization rather than authority",
        "never floats to a different revision",
        "cannot be resurrected",
        "cannot replace or field-mix canonical source/audio/provenance meaning",
    ):
        require(phrase in doc, f"streaming boundary documentation missing {phrase!r}")

    tests = text("tests/production/test_smx030.py")
    test_methods = re.findall(r"^    def (test_[a-z0-9_]+)\(", tests, flags=re.MULTILINE)
    require(len(test_methods) >= 28, "fewer than 28 production adversarial/boundary tests")
    for concept in (
        "inventory_reference_survives_selective_unload_reload",
        "missing_exact_dependency_fails_without_partial_activation",
        "corrupt_exact_dependency_fails_digest",
        "same_revision_but_different_thing_basis",
        "wrong_behaviour_revision",
        "dependency_depth_is_bounded",
        "dependency_count_is_bounded",
        "cache_eviction_does_not_change_worldsave",
        "cancel_after_fetch_still_does_not_publish",
        "tombstoned_thing_cannot_be_resurrected",
        "protected_asset_competing_complete_revision",
        "corrupt_opaque_dependency_blocks_activation",
    ):
        require(any(concept in name for name in test_methods), f"missing test family {concept}")

    workflow = text(".github/workflows/smx030-logical-streaming.yml")
    for command in (
        "python tools/validate_smx008.py",
        "experiments/smx-008-streaming-model",
        "python tools/validate_smx024.py",
        "python tools/validate_smx025.py",
        "python tools/validate_smx028.py",
        "python tools/validate_smx029.py",
        "python tools/validate_smx030.py",
        "test_smx030.py",
    ):
        require(command in workflow, f"dedicated CI missing retained gate {command}")

    registry = json.loads(text("spec/production/conformance-registry.json"))
    gates = {row["id"]: row for row in registry["gate_entries"]}
    for gate_id in ("GATE-01", "GATE-09"):
        gate = gates[gate_id]
        require(
            "docs/implementation/SMX-030-LOGICAL-STREAMING.md"
            in {row["path"] for row in gate["evidence"]},
            f"{gate_id} missing SMX-030 production evidence",
        )
        require("tools/validate_smx030.py" in gate["current_tests"], f"{gate_id} missing validator")
        require("tests/production/test_smx030.py" in gate["current_tests"], f"{gate_id} missing tests")
        require("SMX-030" not in gate["future_issue_codes"], f"{gate_id} still lists SMX-030 as future")

    regressions = {row["id"]: row for row in registry["non_droppable_regressions"]}
    media = regressions["XREG-PROTECTED-MEDIA"]
    require("runtime.streaming" in media["owner_modules"], "protected-media regression omits streaming owner")
    require(
        "docs/implementation/SMX-030-LOGICAL-STREAMING.md" in media["evidence_paths"],
        "protected-media regression omits SMX-030 evidence",
    )

    print(f"SMX-030 contract valid: {len(ids)} fixtures, {len(test_methods)} production tests")


if __name__ == "__main__":
    main()
