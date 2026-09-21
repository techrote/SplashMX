from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from spike import (
    CANDIDATES, CollaborationStoreError, InvalidAssetRevision, MissingAncestor,
    RETAINED_CLASSES, SemanticDagStore, SimulatedCrash, TransactionCollision,
    TxEnvelope, benchmark, fixture_envelope, selected_candidate, tx_id,
    validate_protected_alternatives, validate_protected_asset_revision,
)

CR_EXPECTED = {
    "CR-001":["CH-003","CH-017"], "CR-002":["CH-004","CH-003"],
    "CR-003":["CH-005"], "CR-004":["CH-006"], "CR-005":["CH-007"],
    "CR-006":["CH-007"], "CR-007":["CH-007"], "CR-008":["CH-008"],
    "CR-009":["CH-009"], "CR-010":["CH-010"], "CR-011":["CH-011"],
    "CR-012":["CH-012"], "CR-013":["CH-012"], "CR-014":["CH-013"],
    "CR-015":["CH-014"], "CR-016":["CH-015"], "CR-017":["CH-016"],
    "CR-018":["CH-017","CH-018"], "CR-019":["CH-019"],
    "CR-020":["CH-020"], "CR-021":["CH-021"], "CR-022":["CH-022"],
    "CR-023":["CH-023"], "CR-024":["CH-024","CH-005"],
    "CR-025":["CH-025"], "CR-026":["CH-001","CH-026"],
    "CR-027":["CH-027"], "CR-028":["CH-028","CH-002"],
}


def asset(revision: str, *, source: str = "source-A") -> dict[str, object]:
    return {
        "asset_id": "asset:music", "revision_digest": revision,
        "source_digest": f"digest:{source}", "source_identity": source,
        "source_metadata": {"container":"wav","sample_rate":48000,"channels":2},
        "media_semantics": {"kind":"audio","loop":True,"gain_db":-1.5},
        "provenance": {"author":"fixture","capture":"local"},
        "licence_attribution": {"spdx":"CC-BY-4.0","credit":"fixture"},
        "derivation_lineage": {"parent":"none","operation":"source"},
    }


class SelectionTests(unittest.TestCase):
    def test_only_semantic_tx_dag_checkpoint_store_is_architecture_compatible(self) -> None:
        self.assertEqual(selected_candidate().name, "semantic_tx_dag_checkpoint_store")
        self.assertEqual([x.name for x in CANDIDATES if x.architecture_compatible],
                         ["semantic_tx_dag_checkpoint_store"])

    def test_direct_document_crdt_and_ot_do_not_gain_semantic_authority(self) -> None:
        rows = {x.name:x for x in CANDIDATES}
        self.assertFalse(rows["document_crdt_direct"].semantic_transactions)
        self.assertFalse(rows["server_ordered_ot_direct"].offline_without_server_authority)
        self.assertTrue(rows["bare_semantic_oplog"].semantic_transactions)
        self.assertFalse(rows["bare_semantic_oplog"].bounded_compaction_possible)


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "collab.sqlite3"
        self.store = SemanticDagStore(self.path)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def env(self, actor: str, seq: int, *, parents: tuple[str,...]=(),
            semantic_class: str="ordinary", value: object=None) -> TxEnvelope:
        return TxEnvelope(tx_id(actor, seq), actor, seq, parents, 1, 3, semantic_class,
                          {"value": seq if value is None else value})

    def test_all_cr001_through_cr028_are_representable_as_complete_semantic_transactions(self) -> None:
        self.assertEqual(list(CR_EXPECTED), [f"CR-{n:03d}" for n in range(1,29)])
        for seq, (cr_id, expected) in enumerate(CR_EXPECTED.items(), 1):
            env = fixture_envelope(cr_id, expected, seq)
            status = "quarantined" if env.semantic_class == "quarantine" else (
                "held" if env.semantic_class in {"conflict", "protected_alternative"} else "applied")
            self.store.append(env, final_status=status)
        self.assertEqual(self.store.receipt_count(), 28)
        self.assertEqual(self.store.payload_count(), 28)

    def test_missing_causal_ancestor_pends_then_retries_after_reunion(self) -> None:
        child = self.env("bob", 2, parents=(tx_id("bob", 1),))
        with self.assertRaises(MissingAncestor):
            self.store.append(child)
        self.assertEqual(self.store.receipt_count(), 0)
        self.store.append(self.env("bob", 1))
        self.assertEqual(self.store.retry_pending(), (child.tx_id,))
        self.assertEqual(self.store.receipt_count(), 2)

    def test_duplicate_replay_is_idempotent_and_same_id_different_content_is_corruption(self) -> None:
        first = self.env("alice", 1, value={"x":1})
        self.assertEqual(self.store.append(first), "applied")
        self.assertEqual(self.store.append(first), "duplicate")
        with self.assertRaises(TransactionCollision):
            self.store.append(self.env("alice", 1, value={"x":999}))
        self.assertEqual(self.store.receipt_count(), 1)

    def test_reorder_across_independent_actors_does_not_require_relay_order(self) -> None:
        self.store.append(self.env("b", 1, value="second-logical"))
        self.store.append(self.env("a", 1, value="first-logical"))
        self.assertEqual(self.store.receipt_count(), 2)

    def test_precommit_crash_at_each_meaningful_stage_reopens_previous_coherent_state(self) -> None:
        baseline = self.env("a", 1)
        self.store.append(baseline)
        self.store.close()
        for stage in ("after_receipt", "after_payload", "before_commit"):
            probe = SemanticDagStore(self.path)
            with self.assertRaises(SimulatedCrash):
                probe.append(self.env("a", 2, parents=(baseline.tx_id,)), crash_stage=stage)
            probe.close()
            reopened = SemanticDagStore(self.path)
            self.assertEqual((reopened.receipt_count(), reopened.payload_count()), (1,1), stage)
            reopened.close()
        self.store = SemanticDagStore(self.path)

    def test_compaction_uses_explicit_stability_frontier_and_retains_promised_semantics(self) -> None:
        classes = ["ordinary","tombstone","conflict","quarantine","protected_alternative","resolution"]
        parent: tuple[str,...] = ()
        ids = {}
        for seq, semantic_class in enumerate(classes, 1):
            env = self.env("a", seq, parents=parent, semantic_class=semantic_class)
            status = "held" if semantic_class in {"conflict","protected_alternative"} else (
                "quarantined" if semantic_class == "quarantine" else "applied")
            self.store.append(env, final_status=status)
            ids[semantic_class] = env.tx_id
            parent = (env.tx_id,)
        retired = self.store.create_checkpoint_and_compact(snapshot={"revision":"r6"}, stable_frontier={"a":6})
        self.assertEqual(set(retired), {ids["ordinary"], ids["resolution"]})
        retained = set(self.store.retained_payload_ids())
        for semantic_class in RETAINED_CLASSES:
            self.assertIn(ids[semantic_class], retained)
        self.assertEqual(self.store.receipt_count(), 6)
        self.assertEqual(self.store.checkpoint_floor(), {"a":6})
        self.assertEqual(self.store.append(self.env("a", 1)), "duplicate")
        with self.assertRaises(TransactionCollision):
            self.store.append(self.env("a", 1, value="forged"))

    def test_frontier_never_advances_over_unseen_work_or_moves_backwards(self) -> None:
        self.store.append(self.env("a", 1))
        with self.assertRaises(CollaborationStoreError):
            self.store.create_checkpoint_and_compact(snapshot={}, stable_frontier={"a":2})
        self.store.create_checkpoint_and_compact(snapshot={}, stable_frontier={"a":1})
        with self.assertRaises(CollaborationStoreError):
            self.store.create_checkpoint_and_compact(snapshot={}, stable_frontier={"a":0})

    def test_compacted_ancestor_is_still_causally_satisfied_by_checkpoint_floor(self) -> None:
        first = self.env("a", 1)
        self.store.append(first)
        self.store.create_checkpoint_and_compact(snapshot={"r":1}, stable_frontier={"a":1})
        self.assertEqual(self.store.append(self.env("b", 1, parents=(first.tx_id,))), "applied")

    def test_local_project_ownership_requires_no_relay_or_cloud_head(self) -> None:
        self.store.append(self.env("local", 1, value={"offline":True}))
        self.store.close()
        self.store = SemanticDagStore(self.path)
        self.assertEqual((self.store.receipt_count(), self.store.payload_count()), (1,1))


class ProtectedAssetTests(unittest.TestCase):
    def test_complete_protected_asset_revision_is_accepted(self) -> None:
        validate_protected_asset_revision(asset("rev-A"))

    def test_incomplete_protected_asset_alternative_is_rejected_before_history_admission(self) -> None:
        value = asset("rev-A")
        del value["media_semantics"]
        with self.assertRaises(InvalidAssetRevision):
            validate_protected_asset_revision(value)

    def test_competing_replacements_remain_whole_alternatives_not_field_merged(self) -> None:
        left = asset("rev-A", source="source-left")
        right = asset("rev-B", source="source-right")
        right["media_semantics"] = {"kind":"audio","loop":False,"gain_db":-9.0}
        validate_protected_alternatives([left, right])
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticDagStore(Path(tmp) / "assets.sqlite3")
            env = TxEnvelope(tx_id("asset-author",1), "asset-author", 1, (), 1, 1,
                             "protected_alternative", {"alternatives":[left,right]})
            store.append(env, final_status="held")
            raw = store.db.execute("SELECT body_json FROM tx_payloads WHERE tx_id=?", (env.tx_id,)).fetchone()[0]
            persisted = json.loads(raw)["alternatives"]
            store.close()
        self.assertEqual(persisted, [left, right])
        self.assertNotEqual(persisted[0]["source_identity"], persisted[1]["source_identity"])
        self.assertNotEqual(persisted[0]["media_semantics"], persisted[1]["media_semantics"])


class MeasurementTests(unittest.TestCase):
    def test_measurement_exposes_history_checkpoint_receipt_tradeoff(self) -> None:
        result = benchmark(256)
        self.assertEqual(result["edit_count"], 256)
        self.assertGreater(result["pre_payload_bytes"], result["post_payload_bytes"])
        self.assertGreater(result["receipt_bytes"], 0)
        self.assertGreater(result["checkpoint_bytes"], 0)
        self.assertGreater(result["retired_payload_count"], 0)
        self.assertGreater(result["retained_payload_count"], 0)


if __name__ == "__main__":
    unittest.main()
