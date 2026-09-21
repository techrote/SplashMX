from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from splashmx.canonical.core import (
    AssetId, ProjectRevisionId, RenameThing, SemanticTransaction, ThingId, apply_transaction,
)
from splashmx.canonical.serialization import CanonicalProjectRevision, ProtectedAssetRevision
from splashmx.collaboration.core import CollaborationError, RelayAuthenticator, create_transaction
from splashmx.editor.authoring import AuthoringSession
from splashmx.editor.browser_server import BrowserBridge
from splashmx.editor.people import MAX_RELAY_QUEUE, PeopleError, PeopleSession


def base_project() -> CanonicalProjectRevision:
    session = AuthoringSession.blank("smx044-project")
    session.create_thing(label="A", thing_id="a")
    return session.project


def edit(base: CanonicalProjectRevision, revision: str, label: str) -> CanonicalProjectRevision:
    document = apply_transaction(
        base.document,
        SemanticTransaction(ProjectRevisionId(revision), (RenameThing(ThingId("a"), label),)),
    )
    return CanonicalProjectRevision(document, deepcopy(dict(base.assets)))


def protected(marker: str) -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId("music"),
        source_digest="sha256:" + marker * 64,
        source_identity={"kind": "author-import", "logical_name": f"music-{marker}.wav"},
        source_metadata={"bytes": 4096 + ord(marker), "original_extension": "wav"},
        media_semantics={"kind": "audio", "channels": 2, "sample_rate": 48000, "loop": {"enabled": True, "start_frame": 8, "end_frame": 2048}},
        provenance={"creator": f"author-{marker}", "source": "original recording"},
        licence_attribution={"licence": "CC0-1.0", "attribution": f"author-{marker}"},
        derivation_lineage=({"operation": "trim", "tool": "fixture", "parent_digest": "sha256:" + marker * 64},),
    )


def asset_project(base: CanonicalProjectRevision, revision: str, marker: str) -> CanonicalProjectRevision:
    document = deepcopy(base.document)
    document.project_revision_id = ProjectRevisionId(revision)
    return CanonicalProjectRevision(document, {AssetId("music"): protected(marker)})


class SMX044PeopleConformanceTests(unittest.TestCase):
    def test_browser_people_is_local_first_and_presence_is_transient(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "project.sqlite3"
            bridge = BrowserBridge(AuthoringSession.blank("browser-people"), store_path=local_path)
            response = bridge.apply({"action": "createThing", "data": {"label": "Local", "thing_id": "local"}})
            state = response["state"]
            self.assertEqual(state["people"]["plane"], "collaboration")
            self.assertEqual(state["together"]["plane"], "runtime-networking")
            self.assertEqual(state["people"]["head_revision_id"], state["canonical"]["project_revision_id"])
            authored_revision = state["canonical"]["project_revision_id"]
            bridge.apply({"action": "peoplePresence", "data": {"cursor": "stage", "selections": ["local"]}})
            self.assertEqual(len(bridge.state()["people"]["presence"]), 1)
            bridge.close()

            # No ordinary Save was needed: collaboration history is a separate local-first
            # durable plane. Presence is deliberately absent after process/store reopen.
            reopened = BrowserBridge(AuthoringSession.blank("browser-people"), store_path=local_path)
            state = reopened.state()
            self.assertEqual(state["canonical"]["project_revision_id"], authored_revision)
            self.assertEqual([x["thing_id"] for x in state["canonical"]["things"]], ["local"])
            self.assertEqual(state["people"]["presence"], [])
            reopened.close()

    def test_local_history_storage_fault_does_not_discard_local_candidate(self):
        base = base_project()
        candidate = edit(base, "local-edit", "Still local")
        with tempfile.TemporaryDirectory() as tmp:
            people = PeopleSession(base, Path(tmp) / "people.sqlite3")
            def fail(stage: str) -> None:
                if stage == "after_head":
                    raise RuntimeError("simulated collaboration storage interruption")
            self.assertIsNone(people.record_local(candidate, fault_hook=fail))
            status = people.snapshot()
            self.assertTrue(status["unsynced_local_work"])
            self.assertEqual(people.head_project(), base)
            result = people.retry_local()
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "applied")
            self.assertEqual(people.head_project().document.things[ThingId("a")].label, "Still local")
            self.assertFalse(people.snapshot()["unsynced_local_work"])
            people.close()

    def test_relay_offline_authentication_and_backpressure_are_fail_closed(self):
        base = base_project()
        remote = edit(base, "remote", "Remote")
        transaction = create_transaction(actor_id="bob", actor_seq=1, parents=(), permission_epoch=1, base=base, candidate=remote)
        auth = RelayAuthenticator({"bob": b"b" * 32, "mallory": b"m" * 32})
        packet = auth.sign("bob", transaction)
        with tempfile.TemporaryDirectory() as tmp:
            people = PeopleSession(base, Path(tmp) / "people.sqlite3")
            people.set_relay_online(False)
            with self.assertRaises(PeopleError) as offline:
                people.enqueue_relay(packet, auth)
            self.assertEqual(offline.exception.code, "people.relay_offline")
            self.assertEqual(people.head_project(), base)
            people.set_relay_online(True)
            forged = replace(packet, mac_hex="00" * 32)
            with self.assertRaises(CollaborationError) as unauthenticated:
                people.enqueue_relay(forged, auth)
            self.assertEqual(unauthenticated.exception.code, "collaboration.unauthenticated_relay")
            for _ in range(MAX_RELAY_QUEUE):
                people.enqueue_relay(packet, auth)
            with self.assertRaises(PeopleError) as full:
                people.enqueue_relay(packet, auth)
            self.assertEqual(full.exception.code, "people.relay_backpressure")
            self.assertEqual(people.head_project(), base)
            results = people.drain_relay()
            self.assertEqual(results[0].status, "applied")
            self.assertTrue(all(row.status == "duplicate" for row in results[1:]))
            self.assertEqual(people.head_project().document.things[ThingId("a")].label, "Remote")
            people.close()

    def test_stale_permission_epoch_is_recoverable_not_authoritative(self):
        base = base_project()
        remote = edit(base, "stale", "Stale remote")
        transaction = create_transaction(actor_id="bob", actor_seq=1, parents=(), permission_epoch=1, base=base, candidate=remote)
        auth = RelayAuthenticator({"bob": b"b" * 32})
        with tempfile.TemporaryDirectory() as tmp:
            people = PeopleSession(base, Path(tmp) / "people.sqlite3")
            people.store.advance_permission_epoch(2)
            people.enqueue_relay(auth.sign("bob", transaction), auth)
            result = people.drain_relay()[0]
            self.assertEqual((result.status, result.reason), ("quarantined", "permission-epoch-mismatch"))
            self.assertEqual(people.head_project(), base)
            self.assertIsNotNone(people.store.recover_transaction(transaction.tx_id))
            people.close()

    def test_people_conflict_resolution_is_causal_and_protected_asset_atomic(self):
        seed = base_project()
        base = asset_project(seed, "asset-base", "a")
        local = asset_project(base, "asset-local", "b")
        remote = asset_project(base, "asset-remote", "c")
        auth = RelayAuthenticator({"bob": b"b" * 32})
        remote_tx = create_transaction(actor_id="bob", actor_seq=1, parents=(), permission_epoch=1, base=base, candidate=remote)
        with tempfile.TemporaryDirectory() as tmp:
            people = PeopleSession(base, Path(tmp) / "people.sqlite3")
            self.assertEqual(people.record_local(local).status, "applied")
            people.enqueue_relay(auth.sign("bob", remote_tx), auth)
            incoming = people.drain_relay()[0]
            self.assertEqual(incoming.status, "applied-conflict")
            conflict = people.store.unresolved_conflicts()[0]
            self.assertEqual((conflict.kind, conflict.locus), ("protected-asset", "asset:music"))
            alternatives = [conflict.alternative_a.assets[AssetId("music")], conflict.alternative_b.assets[AssetId("music")]]
            result = people.resolve_conflict(conflict.conflict_id, "alternative-b")
            self.assertEqual(result.status, "resolution")
            resolved = people.head_project().assets[AssetId("music")]
            self.assertIn(resolved, alternatives)
            # Equality is on the entire protected revision object: digest/source/audio/
            # provenance/licence/lineage move together; no field-wise merge is possible.
            self.assertTrue(any(resolved == alternative for alternative in alternatives))
            self.assertFalse(people.store.unresolved_conflicts())
            self.assertIsNotNone(people.store.conflict(conflict.conflict_id).resolved_by)
            people.close()

    def test_compaction_and_reopen_retain_unresolved_conflict_meaning(self):
        base = base_project()
        local, remote = edit(base, "local", "Local"), edit(base, "remote", "Remote")
        remote_tx = create_transaction(actor_id="bob", actor_seq=1, parents=(), permission_epoch=1, base=base, candidate=remote)
        auth = RelayAuthenticator({"bob": b"b" * 32})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.sqlite3"
            people = PeopleSession(base, path)
            people.record_local(local)
            people.enqueue_relay(auth.sign("bob", remote_tx), auth)
            people.drain_relay()
            conflict_id = people.store.unresolved_conflicts()[0].conflict_id
            people.store.create_checkpoint_and_compact({"local-author": 1, "bob": 1})
            self.assertEqual(people.store.unresolved_conflicts()[0].conflict_id, conflict_id)
            people.close()
            reopened = PeopleSession(base, path)
            self.assertEqual(reopened.store.unresolved_conflicts()[0].conflict_id, conflict_id)
            reopened.close()

    def test_future_history_is_quarantined_instead_of_destructively_migrated(self):
        base = base_project()
        remote = edit(base, "future", "Future")
        transaction = create_transaction(actor_id="bob", actor_seq=1, parents=(), permission_epoch=1, base=base, candidate=remote, history_version=999)
        auth = RelayAuthenticator({"bob": b"b" * 32})
        with tempfile.TemporaryDirectory() as tmp:
            people = PeopleSession(base, Path(tmp) / "people.sqlite3")
            people.enqueue_relay(auth.sign("bob", transaction), auth)
            result = people.drain_relay()[0]
            self.assertEqual((result.status, result.reason), ("quarantined", "unsupported-history-version"))
            self.assertEqual(people.head_project(), base)
            self.assertIsNotNone(people.store.recover_transaction(transaction.tx_id))
            people.close()


if __name__ == "__main__":
    unittest.main()
