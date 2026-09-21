#!/usr/bin/env python3
"""Validate the SMX-042 collaboration-substrate selection handoff."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-042-COLLABORATION-SUBSTRATE-SELECTION.md"
FIXTURES = ROOT / "docs/research/SMX-042-COLLABORATION-SUBSTRATE-FIXTURES.json"
EVIDENCE = ROOT / "docs/research/SMX-042-COLLABORATION-SUBSTRATE-EVIDENCE.json"
SMX018 = ROOT / "docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json"
SPIKE = ROOT / "experiments/smx-042-collaboration-substrate-spike/spike.py"
TESTS = ROOT / "experiments/smx-042-collaboration-substrate-spike/test_spike.py"
README = ROOT / "experiments/smx-042-collaboration-substrate-spike/README.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, EVIDENCE, SMX018, SPIKE, TESTS, README):
        require(path.is_file(), f"missing SMX-042 artifact: {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "semantic transaction DAG",
        "validated checkpoints",
        "explicit causal-stability frontier",
        "SQLite WAL + `synchronous=FULL`",
        "IndexedDB read/write transactions",
        "relay/store copies are replicas",
        "CR-001 through CR-028",
        "compact **transaction receipts",
        "No Architecture-v1 contradiction was found",
        "SMX-043 production handoff",
    ):
        require(phrase in doc, f"SMX-042 selection lost required phrase: {phrase}")

    for phrase in (
        "revision/content digest",
        "source digest and logical source identity",
        "exact source metadata",
        "audio/media semantic metadata",
        "provenance",
        "licence/attribution",
        "derivation lineage",
        "may not combine fields from competing Asset revisions",
    ):
        require(phrase in doc, f"SMX-042 protected-Asset contract lost: {phrase}")

    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(
        data.get("schema") == "splashmx.smx042-collaboration-substrate-fixtures/1",
        "wrong SMX-042 fixture schema",
    )
    require(
        data.get("selected_substrate") == "semantic_tx_dag_checkpoint_store",
        "selected substrate changed unexpectedly",
    )
    invariants = data.get("selection_invariants")
    require(
        [row.get("id") for row in invariants] == [f"CS-{n:03d}" for n in range(1, 13)],
        "CS invariant set must remain contiguous CS-001..CS-012",
    )
    adversarial = data.get("adversarial_fixtures")
    require(
        [row.get("id") for row in adversarial] == [f"CSF-{n:03d}" for n in range(1, 14)],
        "CSF adversarial set must remain contiguous CSF-001..CSF-013",
    )

    inherited = json.loads(SMX018.read_text(encoding="utf-8"))
    inherited_rows = {
        row["id"]: row["expected"]
        for row in inherited["fixtures"]
    }
    represented_rows = {
        row["id"]: row["expected"]
        for row in data["cr_representability"]
    }
    require(
        list(represented_rows) == [f"CR-{n:03d}" for n in range(1, 29)],
        "SMX-042 must explicitly represent contiguous CR-001..CR-028",
    )
    require(
        represented_rows == inherited_rows,
        "SMX-042 CR mapping drifted from the authoritative SMX-018 fixture corpus",
    )

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    require(
        evidence.get("contract") == "splashmx.benchmark-evidence/1",
        "SMX-042 evidence must use the SMX-021 benchmark metadata contract",
    )
    require(evidence.get("target_profile") == "native", "unexpected evidence target")
    require(evidence.get("sample_count", 0) >= 1, "missing evidence sample")
    metrics = {row["name"]: row for row in evidence.get("metrics", [])}
    for name in (
        "ingest",
        "compaction",
        "history_payload_before",
        "history_payload_after",
        "receipt_index",
        "checkpoint",
        "retired_payload_count",
        "retained_payload_count",
    ):
        require(name in metrics, f"missing SMX-042 measurement: {name}")
    require(
        metrics["history_payload_after"]["value"] < metrics["history_payload_before"]["value"],
        "captured compaction evidence must actually reduce ordinary payload",
    )
    require(metrics["receipt_index"]["value"] > 0, "receipt retention evidence missing")
    require(metrics["retained_payload_count"]["value"] > 0, "semantic retained-history evidence missing")

    spike = SPIKE.read_text(encoding="utf-8")
    for token in (
        "semantic_tx_dag_checkpoint_store",
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=FULL",
        "TransactionCollision",
        "MissingAncestor",
        "checkpoint_floor",
        "create_checkpoint_and_compact",
        "RETAINED_CLASSES",
        "PROTECTED_ASSET_FIELDS",
    ):
        require(token in spike, f"spike lost required boundary: {token}")

    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_all_cr001_through_cr028_are_representable_as_complete_semantic_transactions",
        "test_missing_causal_ancestor_pends_then_retries_after_reunion",
        "test_duplicate_replay_is_idempotent_and_same_id_different_content_is_corruption",
        "test_precommit_crash_at_each_meaningful_stage_reopens_previous_coherent_state",
        "test_compaction_uses_explicit_stability_frontier_and_retains_promised_semantics",
        "test_compacted_ancestor_is_still_causally_satisfied_by_checkpoint_floor",
        "test_local_project_ownership_requires_no_relay_or_cloud_head",
        "test_incomplete_protected_asset_alternative_is_rejected_before_history_admission",
        "test_competing_replacements_remain_whole_alternatives_not_field_merged",
        "test_measurement_exposes_history_checkpoint_receipt_tradeoff",
    ):
        require(token in tests, f"adversarial regression missing: {token}")

    print("SMX-042 collaboration substrate selection contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-042 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
