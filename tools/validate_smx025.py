#!/usr/bin/env python3
"""Static production-contract validation for SMX-025."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "MODULES.json"
REGISTRY = ROOT / "spec" / "production" / "conformance-registry.json"
NATIVE = ROOT / "src" / "splashmx" / "storage" / "local.py"
BROWSER = ROOT / "src" / "splashmx" / "storage" / "browser_indexeddb.mjs"
TESTS = ROOT / "tests" / "production" / "test_smx025.py"
BROWSER_TEST = ROOT / "tests" / "production" / "smx025_browser_harness.mjs"
DOC = ROOT / "docs" / "implementation" / "SMX-025-LOCAL-PERSISTENCE.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx025-local-persistence.yml"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, REGISTRY, NATIVE, BROWSER, TESTS, BROWSER_TEST, DOC, WORKFLOW):
        require(path.is_file(), f"missing SMX-025 artefact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("storage.local" in modules, "storage.local missing from module manifest")
    module = modules["storage.local"]
    require(module["owner_issue"] == "SMX-025", "storage.local owner drifted")
    require(module["status"] == "implemented", "storage.local is not implemented")
    require(module["gate_ids"] == ["GATE-01", "GATE-09"], "storage.local gate ownership drifted")
    for identity in ("ProjectId", "ProjectRevisionId"):
        require(identity in module["canonical_identity_inputs"], f"missing storage identity role {identity}")
    for responsibility in (
        "crash-safe local project persistence",
        "atomic revision recovery",
        "SQLite WAL/FULL native project ownership",
        "IndexedDB browser project ownership",
    ):
        require(responsibility in module["responsibilities"], f"storage.local missing responsibility: {responsibility}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    gate01 = next(row for row in registry["gate_entries"] if row["id"] == "GATE-01")
    gate09 = next(row for row in registry["gate_entries"] if row["id"] == "GATE-09")
    for gate in (gate01, gate09):
        for current in (
            "tools/validate_smx025.py",
            "tests/production/test_smx025.py",
            "tests/production/smx025_browser_harness.mjs",
        ):
            require(current in gate["current_tests"], f"{gate['id']} missing SMX-025 production evidence: {current}")
        require("SMX-025" not in gate["future_issue_codes"], f"{gate['id']} still treats completed SMX-025 coverage as future")
        require(
            any(row["path"] == "docs/implementation/SMX-025-LOCAL-PERSISTENCE.md" for row in gate["evidence"]),
            f"{gate['id']} missing SMX-025 implementation evidence",
        )
    protected = next(row for row in registry["non_droppable_regressions"] if row["id"] == "XREG-PROTECTED-MEDIA")
    require("storage.local" in protected["owner_modules"], "protected-media regression lost local-storage ownership")
    require(
        "docs/implementation/SMX-025-LOCAL-PERSISTENCE.md" in protected["evidence_paths"],
        "protected-media regression missing SMX-025 evidence",
    )

    native = NATIVE.read_text(encoding="utf-8")
    for marker in (
        'STORE_SCHEMA = "splashmx.local-store/1"',
        '"PRAGMA journal_mode=WAL"',
        '"PRAGMA synchronous=FULL"',
        "class StorageError",
        "class SQLiteProjectStore",
        "def import_serialized",
        "def load",
        "storage.revision_conflict",
        "storage.quota_exceeded",
        "storage.permission_denied",
        "storage.corrupt_store",
        "storage.unsupported_store_version",
        '"prepared"',
        '"head_advanced"',
        '"committed"',
    ):
        require(marker in native, f"native persistence missing marker: {marker}")

    browser = BROWSER.read_text(encoding="utf-8")
    for marker in (
        "class IndexedDBProjectStore",
        "durability: 'strict'",
        "storage.quota_exceeded",
        "storage.permission_denied",
        "storage.transaction_aborted",
        "storage.corrupt_store",
        "navigator",
        "crypto.subtle.digest",
        "heads",
    ):
        require(marker in browser, f"browser persistence missing marker: {marker}")

    tests = TESTS.read_text(encoding="utf-8")
    for marker in (
        "test_every_precommit_interruption_stage_reopens_the_previous_coherent_revision",
        "test_interruption_after_completed_commit_reopens_the_new_coherent_revision",
        "test_same_revision_identity_cannot_be_rebound_to_different_bytes",
        "test_protected_asset_bundle_survives_commit_and_reopen_as_one_revision",
        "test_corrupt_shard_is_rejected_before_caller_can_replace_active_state",
        "test_incompatible_store_version_is_typed_and_does_not_rewrite_the_store",
        "test_v0_serialized_import_migrates_and_publishes_current_semantics_atomically",
        "test_failed_migration_happens_before_store_mutation_and_preserves_old_head",
        "test_store_schema_contains_no_cache_ownership_table",
    ):
        require(marker in tests, f"SMX-025 tests missing regression: {marker}")

    browser_test = BROWSER_TEST.read_text(encoding="utf-8")
    for marker in (
        "precommitStages",
        "QuotaExceededError",
        "SecurityError",
        "storage.corrupt_store",
        "storage.unsupported_store_version",
        "protectedFields",
    ):
        require(marker in browser_test, f"SMX-025 browser harness missing: {marker}")

    doc = DOC.read_text(encoding="utf-8").lower()
    for marker in (
        "sqlite wal", "synchronous=full", "indexeddb", "durability", "previous complete head",
        "source digest", "source identity", "source metadata", "audio/media semantics", "provenance",
        "licence/attribution", "derivation lineage", "quota", "permission", "corrupt", "migration",
        "cache", "opfs", "no hosted control plane", "architecture v1.0",
    ):
        require(marker.lower() in doc, f"SMX-025 documentation missing: {marker}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "python tools/validate_smx025.py",
        "test_smx023.py",
        "test_smx024.py",
        "test_smx025.py",
        "node tests/production/smx025_browser_harness.mjs",
        "playwright@1.55.0",
    ):
        require(marker in workflow, f"SMX-025 workflow missing: {marker}")

    print("SMX-025 local-persistence contract valid: native/browser adapters, registry, docs, workflow and adversarial tests present.")


if __name__ == "__main__":
    main()
