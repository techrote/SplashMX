#!/usr/bin/env python3
"""Static production-contract validation for SMX-024."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "MODULES.json"
REGISTRY = ROOT / "spec" / "production" / "conformance-registry.json"
SERIALIZATION = ROOT / "src" / "splashmx" / "canonical" / "serialization.py"
TESTS = ROOT / "tests" / "production" / "test_smx024.py"
DOC = ROOT / "docs" / "implementation" / "SMX-024-CANONICAL-SERIALIZATION.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx024-canonical-serialization.yml"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, REGISTRY, SERIALIZATION, TESTS, DOC, WORKFLOW):
        require(path.is_file(), f"missing SMX-024 artefact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("canonical.serialization" in modules, "canonical.serialization missing from module manifest")
    module = modules["canonical.serialization"]
    require(module["owner_issue"] == "SMX-024", "canonical.serialization owner drifted")
    require(module["status"] == "implemented", "canonical.serialization is not implemented")
    require(module["gate_ids"] == ["GATE-01", "GATE-09"], "canonical.serialization gate ownership drifted")
    for identity in ("ThingId", "AssetId", "ProjectId", "ProjectRevisionId"):
        require(identity in module["canonical_identity_inputs"], f"missing serialization identity role {identity}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    gate01 = next(row for row in registry["gate_entries"] if row["id"] == "GATE-01")
    gate09 = next(row for row in registry["gate_entries"] if row["id"] == "GATE-09")
    for gate in (gate01, gate09):
        for current in ("tools/validate_smx024.py", "tests/production/test_smx024.py"):
            require(current in gate["current_tests"], f"{gate['id']} missing SMX-024 production evidence: {current}")
        require("SMX-024" not in gate["future_issue_codes"], f"{gate['id']} still treats completed SMX-024 coverage as future")
    protected = next(row for row in registry["non_droppable_regressions"] if row["id"] == "XREG-PROTECTED-MEDIA")
    require("canonical.serialization" in protected["owner_modules"], "protected-media regression lost serialization ownership")
    require("SMX-024" not in protected["future_issue_codes"], "protected-media regression still treats SMX-024 as future coverage")
    require(registry["protected_media_fields"] == [
        "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
        "provenance", "licence_attribution", "derivation_lineage",
    ], "protected-media field contract drifted")

    source = SERIALIZATION.read_text(encoding="utf-8")
    for marker in (
        "CANONICAL_PROFILE = \"splashmx.deterministic-cbor/1\"",
        "SHARD_POLICY = \"sha256-prefix/1\"",
        "class ProtectedAssetRevision",
        "class CanonicalProjectRevision",
        "class MigrationRegistry",
        "def encode_canonical_cbor",
        "def decode_canonical_cbor",
        "def serialize_project",
        "def deserialize_project",
        "def prepare_migration",
        "serialization.asset_revision_mismatch",
        "serialization.forbidden_transient_identity",
        "serialization.unsupported_version",
        "serialization.unsupported_feature",
    ):
        require(marker in source, f"canonical serialization missing marker: {marker}")

    tests = TESTS.read_text(encoding="utf-8")
    for marker in (
        "test_round_trip_preserves_semantic_equality_stable_ids_and_protected_media",
        "test_logically_equal_mapping_insertion_orders_produce_identical_bytes",
        "test_protected_asset_partial_field_mix_rejected_by_revision_digest",
        "test_derivative_digest_cannot_silently_replace_canonical_source_revision",
        "test_corrupt_shard_fails_before_materialization",
        "test_newer_schema_version_is_typed_failure_not_silent_reinterpretation",
        "test_failed_migration_does_not_publish_or_mutate_prior_revision",
        "test_migration_injecting_transient_identity_is_rejected_before_publish",
        "test_duplicate_cbor_map_key_is_rejected_before_overwrite",
        "test_non_finite_floats_are_rejected",
        "test_negative_zero_remains_distinguishable",
    ):
        require(marker in tests, f"SMX-024 tests missing regression: {marker}")

    doc = DOC.read_text(encoding="utf-8").lower()
    for marker in (
        "deterministic-cbor", "stable `assetid`", "source digest", "source identity",
        "source metadata", "audio/media semantics", "provenance", "licence/attribution",
        "derivation lineage", "validate", "before any caller may publish", "smx-025",
        "architecture v1.0", "transient", "target-private",
    ):
        require(marker.lower() in doc, f"SMX-024 documentation missing: {marker}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("python tools/validate_smx024.py" in workflow, "SMX-024 workflow lacks validator")
    require("test_smx023.py" in workflow, "SMX-024 workflow lacks canonical-core regression")
    require("test_smx024.py" in workflow, "SMX-024 workflow lacks production adversarial tests")

    print("SMX-024 canonical-serialization contract valid: module, registry, docs, workflow and adversarial tests present.")


if __name__ == "__main__":
    main()
