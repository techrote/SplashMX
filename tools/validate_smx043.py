#!/usr/bin/env python3
"""Validate the SMX-043 production collaboration handoff."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/implementation/SMX-043-PRODUCTION-COLLABORATION.md"
FIXTURES = ROOT / "spec/production/smx043-collaboration-fixtures.json"
CORE = ROOT / "src/splashmx/collaboration/core.py"
INIT = ROOT / "src/splashmx/collaboration/__init__.py"
TESTS = ROOT / "tests/production/test_smx043.py"
MODULES = ROOT / "src/MODULES.json"
WORKFLOW = ROOT / ".github/workflows/smx043-production-collaboration.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, CORE, INIT, TESTS, MODULES, WORKFLOW):
        require(path.is_file(), f"missing SMX-043 artifact: {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "semantic transaction DAG",
        "validated checkpoint",
        "explicit causal-stability frontier",
        "SQLite WAL with `synchronous=FULL`",
        "remote relay/store is never canonical ownership",
        "R-018-01",
        "R-018-02",
        "R-018-03",
        "R-018-04",
        "No Architecture-v1 contradiction was found",
    ):
        require(phrase.lower() in doc.lower(), f"SMX-043 document lost required contract: {phrase}")
    for phrase in (
        "revision/content digest",
        "source digest and logical source identity",
        "exact source metadata",
        "audio/media semantic metadata",
        "provenance",
        "licence/attribution",
        "derivation lineage",
        "never merges those fields independently",
    ):
        require(phrase in doc, f"SMX-043 protected-Asset contract lost: {phrase}")

    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(fixtures.get("schema") == "splashmx.smx043-production-collaboration-fixtures/1", "wrong SMX-043 fixture schema")
    invariants = fixtures.get("invariants", [])
    require([x.get("id") for x in invariants] == [f"PC-{i:03d}" for i in range(1, 25)], "PC fixtures must remain contiguous PC-001..PC-024")
    require(fixtures.get("required_regressions") == ["R-018-01", "R-018-02", "R-018-03", "R-018-04", "R-019-01"], "corrective regression set drifted")
    require(len(fixtures.get("protected_asset_fields", [])) == 7, "complete protected Asset field set is required")

    core = CORE.read_text(encoding="utf-8")
    for token in (
        "COLLABORATION_FORMAT = \"splashmx.collaboration-transaction/1\"",
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=FULL",
        "missing-ancestor",
        "permission-epoch-mismatch",
        "unknown-base-revision",
        "base-parent-mismatch",
        "canonical-validation-failed",
        "create_checkpoint_and_compact",
        "prepare_undo",
        "RelayAuthenticator",
        "protected-asset",
        "_enforce_remove_wins",
    ):
        require(token in core, f"production collaboration boundary lost token: {token}")

    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_missing_ancestor_pends_then_retries",
        "test_offline_disjoint_divergence_reunites",
        "test_definition_conflict_locus_uses_definition_id_r018_01",
        "test_delete_remove_wins_over_concurrent_connection_r018_02_04",
        "test_full_validation_rejects_merge_cycle_r018_03",
        "test_stale_permission_work_is_recoverable_quarantine",
        "test_crash_before_commit_leaves_previous_coherent_head",
        "test_compaction_retires_stable_ordinary_payload_but_retains_receipt_and_tombstone",
        "test_protected_asset_conflict_keeps_complete_revision_alternatives",
        "test_explicit_conflict_resolution_is_transactional",
        "test_authenticated_relay_rejects_tamper_and_principal_substitution",
        "test_presence_is_transient_not_persisted_or_canonical",
    ):
        require(token in tests, f"SMX-043 adversarial regression missing: {token}")

    modules = json.loads(MODULES.read_text(encoding="utf-8"))
    collab = next((x for x in modules.get("modules", []) if x.get("module_id") == "collaboration.core"), None)
    require(collab is not None, "collaboration.core module missing")
    require(collab.get("owner_issue") == "SMX-043", "collaboration.core owner drifted")
    require(collab.get("status") == "implemented", "collaboration.core must be implemented")
    require("TransactionId" in collab.get("canonical_identity_inputs", []), "TransactionId semantic identity missing")
    require("GATE-06" in collab.get("gate_ids", []), "collaboration gate ownership missing")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for token in (
        "python tools/validate_smx018.py",
        "python tools/validate_smx023.py",
        "python tools/validate_smx024.py",
        "python tools/validate_smx025.py",
        "python tools/validate_smx042.py",
        "python tools/validate_smx043.py",
        "python -m unittest tests.production.test_smx043 -v",
    ):
        require(token in workflow, f"SMX-043 workflow lost inherited gate: {token}")

    print("SMX-043 production collaboration contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-043 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
