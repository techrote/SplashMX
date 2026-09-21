from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from splashmx.canonical.core import (
    AddConnection, AddDefinition, AddThing, AssetId, ConnectionEndpoint, ConnectionId,
    ConnectionRecord, DefinitionElementRecord, DefinitionId, DefinitionRecord, ElementId,
    PortDirection, PortId, PortKind, PortRecord, ProjectId, ProjectRevisionId, RelationId,
    RenameThing, ReplaceDefinition, SemanticTransaction, SetAuthoredState, SetContainment,
    ThingId, ThingRecord, TombstoneThing, apply_transaction, empty_document,
)
from splashmx.canonical.serialization import CanonicalProjectRevision, ProtectedAssetRevision
from splashmx.collaboration.core import (
    HISTORY_VERSION, MAX_PARENTS, CollaborationError, RelayAuthenticator,
    SQLiteCollaborationStore, create_transaction, encode_transaction, transaction_id,
)


def rev(value: str) -> ProjectRevisionId:
    return ProjectRevisionId(value)


def tid(value: str) -> ThingId:
    return ThingId(value)


def stx(revision: str, *ops) -> SemanticTransaction:
    return SemanticTransaction(rev(revision), tuple(ops))


def protected_asset(marker: str) -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId("music"),
        source_digest="sha256:" + marker * 64,
        source_identity={"kind": "author-import", "logical_name": "music.wav"},
        source_metadata={"bytes": 4096, "original_extension": "wav"},
        media_semantics={"kind": "audio", "channels": 2, "sample_rate": 48000,
                         "loop": {"enabled": True, "start_frame": 64, "end_frame": 2048}},
        provenance={"creator": f"author-{marker}", "source": "original recording"},
        licence_attribution={"licence": "CC0-1.0", "attribution": ""},
        derivation_lineage=({"operation": "trim", "tool": "fixture", "parent_digest": "sha256:" + "f" * 64},),
    )


def base_project(*, ports=False, definitions=False, asset=False) -> CanonicalProjectRevision:
    out_port = PortRecord(PortId("out"), "out", PortKind.EVENT, PortDirection.OUT)
    in_port = PortRecord(PortId("in"), "in", PortKind.COMMAND, PortDirection.IN)
    doc = empty_document(ProjectId("collab-project"), rev("r0"))
    ops = [
        AddThing(ThingRecord(tid("a"), "A", {"x": 0}, {out_port.port_id: out_port} if ports else {})),
        AddThing(ThingRecord(tid("b"), "B", {"y": 0}, {in_port.port_id: in_port} if ports else {})),
    ]
    if definitions:
        element = DefinitionElementRecord(ElementId("root"), "Root", {"value": 0})
        ops += [
            AddDefinition(DefinitionRecord(DefinitionId("def-a"), 1, element.element_id, {element.element_id: element})),
            AddDefinition(DefinitionRecord(DefinitionId("def-b"), 1, element.element_id, {element.element_id: element})),
        ]
    doc = apply_transaction(doc, stx("r1", *ops))
    assets = {AssetId("music"): protected_asset("a")} if asset else {}
    return CanonicalProjectRevision(doc, assets)


def edit(base: CanonicalProjectRevision, revision: str, *ops) -> CanonicalProjectRevision:
    return CanonicalProjectRevision(apply_transaction(base.document, stx(revision, *ops)), deepcopy(dict(base.assets)))


def replace_asset(base: CanonicalProjectRevision, revision: str, marker: str) -> CanonicalProjectRevision:
    doc = deepcopy(base.document)
    doc.project_revision_id = rev(revision)
    return CanonicalProjectRevision(doc, {AssetId("music"): protected_asset(marker)})


def tx(actor, seq, base, candidate, *, parents=(), epoch=1, resolves=(), history=HISTORY_VERSION):
    return create_transaction(actor_id=actor, actor_seq=seq, parents=parents, permission_epoch=epoch,
                              base=base, candidate=candidate, resolves=resolves, history_version=history)


class SMX043ProductionCollaborationTests(unittest.TestCase):
    def test_duplicate_idempotence_and_collision(self):
        base = base_project()
        one = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "A1")))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            self.assertEqual(store.ingest(one).status, "applied")
            self.assertEqual(store.ingest(one).status, "duplicate")
            forged = tx("alice", 1, base, edit(base, "a2", RenameThing(tid("a"), "forged")))
            with self.assertRaises(CollaborationError) as caught:
                store.ingest(forged)
            self.assertEqual(caught.exception.code, "collaboration.transaction_collision")

    def test_missing_ancestor_pends_then_retries(self):
        base = base_project()
        p_state = edit(base, "a1", RenameThing(tid("a"), "parent"))
        parent = tx("alice", 1, base, p_state)
        child = tx("alice", 2, p_state, edit(p_state, "a2", SetAuthoredState(tid("a"), {"x": 2})), parents=(parent.tx_id,))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            self.assertEqual(store.ingest(child).status, "pending")
            store.ingest(parent)
            self.assertEqual([x.tx_id for x in store.retry_pending()], [child.tx_id])
            self.assertEqual(store.head_project().document.things[tid("a")].authored_state["x"], 2)

    def test_offline_disjoint_divergence_reunites(self):
        base = base_project()
        local = edit(base, "local", RenameThing(tid("a"), "Local A"))
        remote = edit(base, "remote", RenameThing(tid("b"), "Remote B"))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, local))
            self.assertEqual(store.ingest(tx("bob", 1, base, remote)).status, "applied")
            head = store.head_project()
            self.assertEqual((head.document.things[tid("a")].label, head.document.things[tid("b")].label), ("Local A", "Remote B"))
            self.assertFalse(store.unresolved_conflicts())

    def test_same_record_divergence_materializes_explicit_conflict(self):
        base = base_project()
        local = edit(base, "local", RenameThing(tid("a"), "Local"))
        remote = edit(base, "remote", RenameThing(tid("a"), "Remote"))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, local))
            result = store.ingest(tx("bob", 1, base, remote))
            self.assertEqual(result.status, "applied-conflict")
            conflict = store.unresolved_conflicts()[0]
            self.assertEqual(conflict.locus, "thing:a")
            self.assertEqual({x.document.things[tid("a")].label for x in (conflict.alternative_a, conflict.alternative_b)}, {"Local", "Remote"})

    def test_definition_conflict_locus_uses_definition_id_r018_01(self):
        base = base_project(definitions=True)
        current = base.document.definitions[DefinitionId("def-a")]
        local_def = replace(current, revision=2, elements={ElementId("root"): replace(current.elements[ElementId("root")], label="Local")})
        remote_def = replace(current, revision=2, elements={ElementId("root"): replace(current.elements[ElementId("root")], label="Remote")})
        local, remote = edit(base, "local", ReplaceDefinition(local_def)), edit(base, "remote", ReplaceDefinition(remote_def))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, local))
            store.ingest(tx("bob", 1, base, remote))
            self.assertEqual([x.locus for x in store.unresolved_conflicts()], ["definition:def-a"])

    def test_delete_remove_wins_over_concurrent_connection_r018_02_04(self):
        base = base_project(ports=True)
        deleted = edit(base, "delete", TombstoneThing(tid("a")))
        connection = ConnectionRecord(ConnectionId("c1"), ConnectionEndpoint(tid("a"), PortId("out")), ConnectionEndpoint(tid("b"), PortId("in")))
        connected = edit(base, "connect", AddConnection(connection))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, deleted))
            self.assertEqual(store.ingest(tx("bob", 1, base, connected)).status, "applied")
            head = store.head_project().document
            self.assertTrue(head.things[tid("a")].tombstoned)
            self.assertTrue(head.connections[ConnectionId("c1")].tombstoned)

    def test_full_validation_rejects_merge_cycle_r018_03(self):
        base = base_project()
        local = edit(base, "local", SetContainment(tid("b"), tid("a"), RelationId("b-under-a")))
        remote = edit(base, "remote", SetContainment(tid("a"), tid("b"), RelationId("a-under-b")))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, local))
            before = store.head_project()
            result = store.ingest(tx("bob", 1, base, remote))
            self.assertEqual(result.status, "held-invalid")
            self.assertEqual(store.head_project(), before)
            self.assertEqual(store.unresolved_conflicts()[0].kind, "document-invalid")

    def test_stale_permission_work_is_recoverable_quarantine(self):
        base = base_project()
        stale = tx("alice", 1, base, edit(base, "stale", RenameThing(tid("a"), "stale")), epoch=1)
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.advance_permission_epoch(2)
            result = store.ingest(stale)
            self.assertEqual((result.status, result.reason), ("quarantined", "permission-epoch-mismatch"))
            self.assertEqual(store.head_project(), base)
            self.assertEqual(store.recover_transaction(stale.tx_id), encode_transaction(stale))

    def test_unsupported_history_version_quarantines(self):
        base = base_project()
        future = tx("alice", 1, base, edit(base, "future", RenameThing(tid("a"), "future")), history=HISTORY_VERSION + 1)
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            result = store.ingest(future)
            self.assertEqual((result.status, result.reason), ("quarantined", "unsupported-history-version"))
            self.assertEqual(store.head_project(), base)

    def test_unknown_base_cannot_become_sync_authority(self):
        base = base_project()
        unseen = edit(base, "unseen", RenameThing(tid("a"), "unseen"))
        child = tx("alice", 1, unseen, edit(unseen, "child", RenameThing(tid("b"), "child")))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            result = store.ingest(child)
            self.assertEqual((result.status, result.reason), ("quarantined", "unknown-base-revision"))
            self.assertEqual(store.head_project(), base)

    def test_crash_before_commit_leaves_previous_coherent_head(self):
        base = base_project()
        change = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "A1")))
        for stage in ("after_receipt", "after_payload", "after_conflicts", "after_head", "before_commit"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "c.db"
                store = SQLiteCollaborationStore(path, base)
                def hook(value, target=stage):
                    if value == target:
                        raise RuntimeError("simulated crash")
                with self.assertRaises(RuntimeError):
                    store.ingest(change, fault_hook=hook)
                store.close()
                with SQLiteCollaborationStore(path, base) as reopened:
                    self.assertEqual(reopened.head_project(), base)
                    self.assertIsNone(reopened.history_status(change.tx_id))

    def test_reopen_preserves_applied_head(self):
        base = base_project()
        change = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "A1")))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.db"
            with SQLiteCollaborationStore(path, base) as store:
                store.ingest(change)
            with SQLiteCollaborationStore(path, base) as reopened:
                self.assertEqual(reopened.head_project().document.things[tid("a")].label, "A1")
                self.assertEqual(reopened.history_status(change.tx_id), "applied")

    def test_compaction_retires_stable_ordinary_payload_but_retains_receipt_and_tombstone(self):
        base = base_project()
        ordinary_state = edit(base, "a1", RenameThing(tid("a"), "A1"))
        ordinary = tx("alice", 1, base, ordinary_state)
        tombstone = tx("alice", 2, ordinary_state, edit(ordinary_state, "a2", TombstoneThing(tid("b"))), parents=(ordinary.tx_id,))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(ordinary)
            store.ingest(tombstone)
            retired = store.create_checkpoint_and_compact({"alice": 2})
            self.assertIn(ordinary.tx_id, retired)
            self.assertNotIn(tombstone.tx_id, retired)
            self.assertIsNone(store.recover_transaction(ordinary.tx_id))
            self.assertIsNotNone(store.recover_transaction(tombstone.tx_id))
            self.assertEqual(store.history_status(ordinary.tx_id), "applied")

    def test_compaction_frontier_regression_and_unseen_work_fail(self):
        base = base_project()
        one = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "A1")))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(one)
            store.create_checkpoint_and_compact({"alice": 1})
            with self.assertRaises(CollaborationError) as regression:
                store.create_checkpoint_and_compact({"alice": 0})
            self.assertEqual(regression.exception.code, "collaboration.frontier_regression")
            with self.assertRaises(CollaborationError) as unseen:
                store.create_checkpoint_and_compact({"alice": 2})
            self.assertEqual(unseen.exception.code, "collaboration.frontier_unseen")

    def test_protected_asset_conflict_keeps_complete_revision_alternatives(self):
        base = base_project(asset=True)
        local, remote = replace_asset(base, "asset-local", "b"), replace_asset(base, "asset-remote", "c")
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.ingest(tx("alice", 1, base, local))
            result = store.ingest(tx("bob", 1, base, remote))
            self.assertEqual(result.status, "applied-conflict")
            conflict = store.unresolved_conflicts()[0]
            self.assertEqual(conflict.kind, "protected-asset")
            alternatives = {x.assets[AssetId("music")].revision_digest for x in (conflict.alternative_a, conflict.alternative_b)}
            self.assertEqual(alternatives, {local.assets[AssetId("music")].revision_digest, remote.assets[AssetId("music")].revision_digest})
            for project in (conflict.alternative_a, conflict.alternative_b):
                asset = project.assets[AssetId("music")]
                self.assertTrue(asset.source_identity and asset.source_metadata and asset.media_semantics)
                self.assertTrue(asset.provenance and asset.licence_attribution and asset.derivation_lineage)

    def test_corrupt_protected_candidate_rejected_before_history(self):
        base = base_project(asset=True)
        one = tx("alice", 1, base, replace_asset(base, "next", "b"))
        corrupt = replace(one, candidate_project=one.candidate_project[:-1] + bytes((one.candidate_project[-1] ^ 1,)))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            with self.assertRaises(CollaborationError) as caught:
                store.ingest(encode_transaction(corrupt))
            self.assertEqual(caught.exception.code, "collaboration.invalid_project_snapshot")
            self.assertIsNone(store.history_status(one.tx_id))
            self.assertEqual(store.head_project(), base)

    def test_explicit_conflict_resolution_is_transactional(self):
        base = base_project()
        local, remote = edit(base, "local", RenameThing(tid("a"), "Local")), edit(base, "remote", RenameThing(tid("a"), "Remote"))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            first, second = tx("alice", 1, base, local), tx("bob", 1, base, remote)
            store.ingest(first)
            store.ingest(second)
            cid = store.unresolved_conflicts()[0].conflict_id
            current = store.head_project()
            resolution = tx("alice", 2, current, edit(current, "resolved", RenameThing(tid("a"), "Resolved")), parents=(second.tx_id,), resolves=(cid,))
            self.assertEqual(store.ingest(resolution).status, "resolution")
            self.assertFalse(store.unresolved_conflicts())
            self.assertEqual(store.conflict(cid).resolved_by, resolution.tx_id)

    def test_unknown_resolution_does_not_mutate_history(self):
        base = base_project()
        one = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "X")), resolves=("conflict-missing",))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            with self.assertRaises(CollaborationError) as caught:
                store.ingest(one)
            self.assertEqual(caught.exception.code, "collaboration.unknown_conflict")
            self.assertIsNone(store.history_status(one.tx_id))

    def test_leaf_undo_is_new_semantic_transaction_and_compaction_can_expire_it(self):
        base = base_project()
        one = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "Changed")))
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "a.db", base) as store:
            store.ingest(one)
            undo = store.prepare_undo(one.tx_id, actor_id="alice", actor_seq=2)
            store.ingest(undo)
            self.assertEqual(store.head_project().document.things[tid("a")].label, "A")
            self.assertNotEqual(store.head_project().document.project_revision_id, base.document.project_revision_id)
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "b.db", base) as store:
            store.ingest(one)
            store.create_checkpoint_and_compact({"alice": 1})
            with self.assertRaises(CollaborationError) as caught:
                store.prepare_undo(one.tx_id, actor_id="alice", actor_seq=2)
            self.assertEqual(caught.exception.code, "collaboration.undo_history_unavailable")

    def test_authenticated_relay_rejects_tamper_and_principal_substitution(self):
        base = base_project()
        one = tx("alice", 1, base, edit(base, "a1", RenameThing(tid("a"), "Relay")))
        auth = RelayAuthenticator({"alice": b"a" * 32, "bob": b"b" * 32})
        packet = auth.sign("alice", one)
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            self.assertEqual(store.ingest_relay(packet, auth).status, "applied")
        with self.assertRaises(CollaborationError) as tamper:
            auth.verify(replace(packet, transaction_bytes=packet.transaction_bytes + b"\x00"))
        self.assertEqual(tamper.exception.code, "collaboration.unauthenticated_relay")
        with self.assertRaises(CollaborationError) as mismatch:
            auth.verify(auth.sign("bob", one))
        self.assertEqual(mismatch.exception.code, "collaboration.principal_mismatch")

    def test_presence_is_transient_not_persisted_or_canonical(self):
        base = base_project()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.db"
            with SQLiteCollaborationStore(path, base) as store:
                store.set_presence("alice", cursor="stage:10,20", selections=("a", "b"))
                self.assertEqual(len(store.presence()), 1)
            with SQLiteCollaborationStore(path, base) as reopened:
                self.assertEqual(reopened.presence(), ())
                self.assertEqual(reopened.head_project(), base)

    def test_parent_count_is_independently_bounded(self):
        base = base_project()
        candidate = edit(base, "a1", RenameThing(tid("a"), "A1"))
        parents = [transaction_id(f"p{i}", 1) for i in range(MAX_PARENTS + 1)]
        with self.assertRaises(CollaborationError) as caught:
            tx("alice", 1, base, candidate, parents=parents)
        self.assertEqual(caught.exception.code, "collaboration.invalid_parents")

    def test_descendant_of_quarantined_permission_work_cannot_materialize(self):
        base = base_project()
        stale_state = edit(base, "stale", RenameThing(tid("a"), "Stale"))
        stale = tx("alice", 1, base, stale_state, epoch=1)
        child = tx("alice", 2, stale_state, edit(stale_state, "child", RenameThing(tid("b"), "Child")), parents=(stale.tx_id,), epoch=2)
        with tempfile.TemporaryDirectory() as tmp, SQLiteCollaborationStore(Path(tmp) / "c.db", base) as store:
            store.advance_permission_epoch(2)
            self.assertEqual(store.ingest(stale).status, "quarantined")
            result = store.ingest(child)
            self.assertEqual((result.status, result.reason), ("quarantined", "nonmaterialized-ancestor"))
            self.assertEqual(store.head_project(), base)


if __name__ == "__main__":
    unittest.main()
