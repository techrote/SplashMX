from __future__ import annotations

import base64
import hashlib
import unittest

from splashmx.runtime.network import (
    MAX_MESSAGES_PER_TICK, MAX_PENDING_EVENTS_PER_THING, MessageClass, NetworkDeclaration,
    NetworkEnvelope, NetworkError, OpaqueJoinTicketAuthority, PROTECTED_ASSET_FIELDS,
    Residency, RuntimeNetworkingService, RuntimeOutcome, SessionIdentity, Topology,
    TransportPath, validate_signalling_envelope, verify_pkce_s256,
)


def session(principal: str, sid: str, *, room: str = "room:1", expiry: int = 1000) -> SessionIdentity:
    return SessionIdentity(principal, sid, room, expiry)


def env(mid: str, cls: MessageClass, sid: str, seq: int, *, epoch: int = 1, thing: str = "avatar", locus: str = "move", payload=None):
    return NetworkEnvelope(mid, cls, sid, epoch, seq, thing, locus, payload or {})


def protected(marker: str = "a"):
    values = {
        "revision_digest": "sha256:" + marker * 64,
        "source_digest": "sha256:" + "f" * 64,
        "source_identity": {"logical_name": "song.wav"},
        "source_metadata": {"bytes": 4096, "extension": "wav"},
        "media_semantics": {"kind": "audio", "sample_rate": 48000, "channels": 2},
        "provenance": {"creator": "artist"},
        "licence_attribution": {"licence": "CC0-1.0"},
        "derivation_lineage": [{"operation": "trim", "parent": "sha256:" + "e" * 64}],
    }
    assert set(values) == set(PROTECTED_ASSET_FIELDS)
    return values


class SMX046NetworkTests(unittest.TestCase):
    def setUp(self):
        self.net = RuntimeNetworkingService(topology=Topology.PEER_HOSTED, room_id="room:1")
        self.host = session("principal:host", "session:host")
        self.client = session("principal:alice", "session:alice")
        self.net.admit_session(self.host, transport_id="transport:h1", path=TransportPath.WEBRTC_DIRECT, now=10)
        self.net.admit_session(self.client, transport_id="transport:a1", path=TransportPath.WEBRTC_DIRECT, now=10)
        self.net.register_thing(
            thing_id="avatar",
            declaration=NetworkDeclaration(frozenset({"move"}), frozenset({"position"}), frozenset({"hit"}), {"move": {"axis": (-1.0, 1.0)}}),
            authority_session_id=self.host.session_id, authority_epoch=1,
            controller_principal_id=self.client.principal_id,
        )

    def _make_topology_service(self, topology: Topology):
        net = RuntimeNetworkingService(topology=topology, room_id="room:1")
        host = session("principal:host", "session:host")
        path = {Topology.OFFLINE: TransportPath.LOCAL, Topology.PEER_HOSTED: TransportPath.WEBRTC_DIRECT, Topology.DEDICATED_AUTHORITATIVE: TransportPath.WSS_DEDICATED}[topology]
        net.admit_session(host, transport_id=f"transport:{topology.value}", path=path, now=10)
        net.register_thing(thing_id="avatar", declaration=NetworkDeclaration(frozenset({"move"}), frozenset({"position"}), frozenset({"hit"}), {"move": {"axis": (-1.0, 1.0)}}), authority_session_id="session:host", controller_principal_id="principal:host")
        return net

    def test_TN001_same_authoritative_semantics_across_offline_peer_and_dedicated(self):
        semantic = []
        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            net = self._make_topology_service(topology)
            net.ingress(env("state", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 4}), now=20, tick=1)
            semantic.append(net.semantic_snapshot()["things"])
        self.assertEqual(semantic[0], semantic[1]); self.assertEqual(semantic[1], semantic[2])

    def test_TN002_control_transfer_does_not_transfer_simulation_authority(self):
        self.net.set_controller("avatar", "principal:host")
        with self.assertRaises(NetworkError) as old_controller:
            self.net.ingress(env("old-control", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(old_controller.exception.outcome, RuntimeOutcome.CONTROLLER_REJECTED)
        self.net.ingress(env("authority-still-host", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 1}), now=20, tick=1)
        self.assertEqual(self.net.semantic_snapshot()["things"]["avatar"]["replicated_state"]["position"], {"x": 1})

    def test_TN003_transport_rebind_preserves_principal(self):
        rebound = self.net.reconnect_session("session:alice", transport_id="transport:new", path=TransportPath.WEBRTC_TURN, now=20)
        self.assertEqual(rebound.session.principal_id, "principal:alice"); self.assertEqual(rebound.session.session_id, "session:alice")

    def test_TN004_reconnect_requires_new_transport_identity(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.reconnect_session("session:alice", transport_id="transport:a1", path=TransportPath.WEBRTC_DIRECT, now=20)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.RECONNECT_FAILED)

    def test_TN005_non_controller_input_rejected(self):
        intruder = session("principal:mallory", "session:mallory")
        self.net.admit_session(intruder, transport_id="transport:m", path=TransportPath.WEBRTC_DIRECT, now=10)
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("tn5", MessageClass.INPUT, "session:mallory", 1, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.CONTROLLER_REJECTED)

    def test_TN006_duplicate_input_is_rejected_without_semantic_mutation(self):
        self.net.ingress(env("dup", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=1)
        before = self.net.semantic_snapshot()
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("dup", MessageClass.INPUT, "session:alice", 2, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.REPLAY); self.assertEqual(self.net.semantic_snapshot(), before)

    def test_TN007_reordered_input_is_rejected(self):
        self.net.ingress(env("seq2", MessageClass.INPUT, "session:alice", 2, payload={"axis": 0}), now=20, tick=1)
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("seq1", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.REORDERED)

    def test_TN008_stale_authority_epoch_is_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("stale", MessageClass.INPUT, "session:alice", 1, epoch=2, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.STALE_EPOCH)

    def test_TN009_unconfirmed_host_loss_cannot_migrate(self):
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=False)
        with self.assertRaises(NetworkError) as caught:
            self.net.migrate_peer_host(new_authority_session_id="session:alice", checkpoint=checkpoint, now=20)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.CHECKPOINT_UNCONFIRMED)

    def test_TN010_confirmed_host_migration_bumps_epoch_and_preserves_state(self):
        self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 2}), now=20, tick=1)
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=True)
        self.assertEqual(self.net.migrate_peer_host(new_authority_session_id="session:alice", checkpoint=checkpoint, now=20), 2)
        thing = self.net.semantic_snapshot()["things"]["avatar"]
        self.assertEqual(thing["authority_epoch"], 2); self.assertEqual(thing["replicated_state"]["position"], {"x": 2})

    def test_TN011_forged_remote_state_is_not_input(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("forged-state", MessageClass.STATE, "session:alice", 1, locus="position", payload={"x": 9}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.AUTHORITY_REJECTED)

    def test_TN012_undeclared_input_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("undeclared-input", MessageClass.INPUT, "session:alice", 1, locus="teleport", payload={}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.LOCUS_REJECTED)

    def test_TN013_out_of_range_input_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("out-of-range", MessageClass.INPUT, "session:alice", 1, payload={"axis": 2}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.LOCUS_REJECTED)

    def test_TN014_nested_capability_injection_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("cap", MessageClass.INPUT, "session:alice", 1, payload={"nested": [{"capability_grant": "ambient"}]}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_TN015_host_handle_injection_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("handle", MessageClass.INPUT, "session:alice", 1, payload={"host_handle": "engine"}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_TN016_oversized_message_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("oversize", MessageClass.INPUT, "session:alice", 1, payload={"blob": "x" * 70000}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.MESSAGE_OVERSIZE)

    def test_TN017_known_unloaded_state_is_coalesced(self):
        self.net.set_residency("avatar", Residency.KNOWN_UNLOADED)
        self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 1}), now=20, tick=1)
        self.net.ingress(env("s2", MessageClass.STATE, "session:host", 2, locus="position", payload={"x": 2}), now=20, tick=2)
        pending = self.net.set_residency("avatar", Residency.RESIDENT)
        self.assertEqual([item.message_id for item in pending], ["s2"])

    def test_TN018_reliable_event_survives_unload_and_deduplicates(self):
        self.net.set_residency("avatar", Residency.KNOWN_UNLOADED)
        self.net.ingress(env("event-1", MessageClass.EVENT, "session:host", 1, locus="hit", payload={"damage": 1}), now=20, tick=1)
        with self.assertRaises(NetworkError) as duplicate:
            self.net.ingress(env("event-1", MessageClass.EVENT, "session:host", 2, locus="hit", payload={"damage": 1}), now=20, tick=2)
        self.assertEqual(duplicate.exception.outcome, RuntimeOutcome.REPLAY)
        self.assertEqual([item.message_id for item in self.net.set_residency("avatar", Residency.RESIDENT)], ["event-1"])

    def test_TN019_relevance_leave_is_not_unload_or_destroy(self):
        self.net.set_relevant("session:alice", "avatar", True); before = self.net.semantic_snapshot()["things"]["avatar"]
        self.net.set_relevant("session:alice", "avatar", False)
        self.assertEqual(self.net.semantic_snapshot()["things"]["avatar"], before)

    def test_TN020_tombstone_drops_pending_and_rejects_future_delivery(self):
        self.net.set_residency("avatar", Residency.KNOWN_UNLOADED)
        self.net.ingress(env("pending", MessageClass.EVENT, "session:host", 1, locus="hit"), now=20, tick=1)
        self.net.set_residency("avatar", Residency.TOMBSTONED); self.assertEqual(self.net.pending_count("avatar"), 0)
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("future", MessageClass.EVENT, "session:host", 2, locus="hit"), now=20, tick=2)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.TARGET_TOMBSTONED)

    def test_TN021_stale_state_cannot_roll_back(self):
        self.net.ingress(env("s2", MessageClass.STATE, "session:host", 2, locus="position", payload={"x": 2}), now=20, tick=1); before = self.net.semantic_snapshot()
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 1}), now=20, tick=2)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.REORDERED); self.assertEqual(self.net.semantic_snapshot(), before)

    def test_TN022_non_authority_state_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("not-authority", MessageClass.STATE, "session:alice", 1, locus="position", payload={"x": 3}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.AUTHORITY_REJECTED)

    def test_TN023_undeclared_state_locus_rejected(self):
        with self.assertRaises(NetworkError) as caught:
            self.net.ingress(env("unknown-locus", MessageClass.STATE, "session:host", 1, locus="secret", payload={"x": 3}), now=20, tick=1)
        self.assertEqual(caught.exception.outcome, RuntimeOutcome.LOCUS_REJECTED)

    def test_TN024_protected_asset_bundle_is_atomic(self):
        original = protected("a"); self.net.add_protected_asset("music", original)
        incomplete = original.copy(); incomplete.pop("media_semantics")
        with self.assertRaises(NetworkError): self.net.add_protected_asset("music-broken", incomplete)
        self.assertEqual(self.net.protected_asset("music"), original)

    def test_TN025_topology_projection_does_not_mutate_protected_bundle(self):
        original = protected("a")
        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            net = self._make_topology_service(topology); net.add_protected_asset("music", original)
            self.assertEqual(net.protected_asset("music"), original)

    def test_TN026_semantic_snapshot_contains_no_transport_or_engine_identity(self):
        text = repr(self.net.semantic_snapshot()).lower()
        for forbidden in ("transport:", "session:", "nodepath", "resourceuid", "socket"):
            self.assertNotIn(forbidden, text)

    def test_TN027_thing_identity_is_identical_across_topologies(self):
        ids = [tuple(self._make_topology_service(topology).semantic_snapshot()["things"]) for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE)]
        self.assertEqual(ids, [("avatar",), ("avatar",), ("avatar",)])

    def test_TN028_checkpoint_excludes_transport_peer_and_session_handle(self):
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=True).to_serializable(); text = repr(checkpoint)
        self.assertNotIn("transport:", text); self.assertNotIn("session:", text)

    def test_pkce_s256_and_opaque_join_ticket_scope_expiry_replay(self):
        verifier = "A" * 43; challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertTrue(verify_pkce_s256(verifier, challenge)); self.assertFalse(verify_pkce_s256("wrong", challenge))
        tickets = OpaqueJoinTicketAuthority(); token = tickets.issue(self.client, audience="signal", now=10, ttl_seconds=30)
        self.assertEqual(tickets.redeem(token, audience="signal", room_id="room:1", now=11), self.client)
        with self.assertRaises(NetworkError) as replay: tickets.redeem(token, audience="signal", room_id="room:1", now=12)
        self.assertEqual(replay.exception.outcome, RuntimeOutcome.AUTH_REJECTED)
        wrong = tickets.issue(self.client, audience="signal", now=20)
        with self.assertRaises(NetworkError) as scope: tickets.redeem(wrong, audience="dedicated", room_id="room:1", now=21)
        self.assertEqual(scope.exception.outcome, RuntimeOutcome.AUTH_REJECTED)
        expired = tickets.issue(self.client, audience="signal", now=30, ttl_seconds=1)
        with self.assertRaises(NetworkError) as expiry: tickets.redeem(expired, audience="signal", room_id="room:1", now=32)
        self.assertEqual(expiry.exception.outcome, RuntimeOutcome.AUTH_EXPIRED)

    def test_reconnect_rebinds_transport_without_replacing_principal_session_or_thing(self):
        before = self.net.semantic_snapshot(); rebound = self.net.reconnect_session("session:alice", transport_id="transport:a2", path=TransportPath.WEBRTC_TURN, now=20)
        self.assertEqual((rebound.session.principal_id, rebound.session.session_id, rebound.transport_id, rebound.generation), ("principal:alice", "session:alice", "transport:a2", 2))
        self.assertEqual(self.net.semantic_snapshot(), before); self.net.transport.disconnect("session:alice")
        rebound2 = self.net.reconnect_session("session:alice", transport_id="transport:a3", path=TransportPath.WSS_PEER_RELAY, now=21)
        self.assertEqual(rebound2.generation, 3); self.assertEqual(rebound2.session.principal_id, "principal:alice")

    def test_client_input_is_intent_and_non_controller_or_forged_state_rejected(self):
        result = self.net.ingress(env("i1", MessageClass.INPUT, "session:alice", 1, payload={"axis": 1}), now=20, tick=1)
        self.assertEqual(result.status, "intent_accepted"); self.assertEqual(self.net.semantic_snapshot()["things"]["avatar"]["replicated_state"], {})
        intruder = session("principal:mallory", "session:mallory"); self.net.admit_session(intruder, transport_id="transport:m1", path=TransportPath.WEBRTC_DIRECT, now=20)
        with self.assertRaises(NetworkError) as control: self.net.ingress(env("i2", MessageClass.INPUT, "session:mallory", 1, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(control.exception.outcome, RuntimeOutcome.CONTROLLER_REJECTED)
        with self.assertRaises(NetworkError) as forged: self.net.ingress(env("s1", MessageClass.STATE, "session:alice", 2, locus="position", payload={"x": 99}), now=20, tick=1)
        self.assertEqual(forged.exception.outcome, RuntimeOutcome.AUTHORITY_REJECTED)

    def test_stale_epoch_replay_reorder_and_recursive_authority_injection_fail(self):
        with self.assertRaises(NetworkError) as stale: self.net.ingress(env("e0", MessageClass.INPUT, "session:alice", 1, epoch=2, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(stale.exception.outcome, RuntimeOutcome.STALE_EPOCH)
        self.net.ingress(env("i1", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=2)
        with self.assertRaises(NetworkError) as replay: self.net.ingress(env("i1", MessageClass.INPUT, "session:alice", 2, payload={"axis": 0}), now=20, tick=2)
        self.assertEqual(replay.exception.outcome, RuntimeOutcome.REPLAY)
        with self.assertRaises(NetworkError) as reorder: self.net.ingress(env("i0", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=2)
        self.assertEqual(reorder.exception.outcome, RuntimeOutcome.REORDERED)
        with self.assertRaises(NetworkError) as injection: self.net.ingress(env("i3", MessageClass.INPUT, "session:alice", 3, payload={"nested": [{"capability_grant": "ambient"}]}), now=20, tick=3)
        self.assertEqual(injection.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_known_unloaded_state_coalesces_reliable_events_queue_and_tombstone_cannot_resurrect(self):
        self.net.set_residency("avatar", Residency.KNOWN_UNLOADED)
        self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 1}), now=20, tick=1)
        self.net.ingress(env("s2", MessageClass.STATE, "session:host", 2, locus="position", payload={"x": 2}), now=20, tick=1)
        self.net.ingress(env("e1", MessageClass.EVENT, "session:host", 1, locus="hit", payload={"damage": 1}), now=20, tick=1)
        pending = self.net.set_residency("avatar", Residency.RESIDENT)
        self.assertEqual([(item.message_class.value, item.message_id) for item in pending], [("event", "e1"), ("state", "s2")])
        self.net.set_residency("avatar", Residency.TOMBSTONED)
        with self.assertRaises(NetworkError): self.net.set_residency("avatar", Residency.RESIDENT)

    def test_reconnect_baseline_contains_semantics_and_watermarks_but_no_transport_identity(self):
        self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 3}), now=20, tick=1)
        self.net.set_relevant("session:alice", "avatar", True); self.net.reconnect_session("session:alice", transport_id="transport:a2", path=TransportPath.WEBRTC_TURN, now=21)
        baseline = self.net.reconnect_baseline("session:alice", now=21)
        self.assertEqual(baseline["things"]["avatar"]["state_watermarks"]["position"], 1)
        self.assertNotIn("transport:", repr(baseline)); self.assertNotIn("session:", repr(baseline))

    def test_leave_drops_transient_session_context_without_destroying_thing(self):
        before = self.net.semantic_snapshot(); self.net.leave_session("session:alice"); self.assertEqual(self.net.semantic_snapshot(), before)
        with self.assertRaises(NetworkError) as gone: self.net.ingress(env("i-gone", MessageClass.INPUT, "session:alice", 1, payload={"axis": 0}), now=20, tick=1)
        self.assertEqual(gone.exception.outcome, RuntimeOutcome.AUTH_REQUIRED)

    def test_relevance_leave_does_not_unload_destroy_or_transfer_authority(self):
        self.net.set_relevant("session:alice", "avatar", True); before = self.net.semantic_snapshot()["things"]["avatar"].copy()
        self.net.set_relevant("session:alice", "avatar", False)
        self.assertFalse(self.net.is_relevant("session:alice", "avatar")); self.assertEqual(self.net.semantic_snapshot()["things"]["avatar"], before)

    def test_confirmed_peer_host_migration_preserves_state_increments_epoch_and_rejects_old_epoch(self):
        self.net.ingress(env("s1", MessageClass.STATE, "session:host", 1, locus="position", payload={"x": 4}), now=20, tick=1)
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=True); serialized = checkpoint.to_serializable()
        self.assertNotIn("session:host", repr(serialized)); self.assertNotIn("transport:h1", repr(serialized))
        self.assertEqual(self.net.migrate_peer_host(new_authority_session_id="session:alice", checkpoint=checkpoint, now=20), 2)
        with self.assertRaises(NetworkError) as old: self.net.ingress(env("s-old", MessageClass.STATE, "session:host", 2, epoch=1, locus="position", payload={"x": 9}), now=20, tick=2)
        self.assertEqual(old.exception.outcome, RuntimeOutcome.STALE_EPOCH)

    def test_unconfirmed_checkpoint_cannot_migrate_and_dedicated_authority_never_client_promotes(self):
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=False)
        with self.assertRaises(NetworkError) as unconfirmed: self.net.migrate_peer_host(new_authority_session_id="session:alice", checkpoint=checkpoint, now=20)
        self.assertEqual(unconfirmed.exception.outcome, RuntimeOutcome.CHECKPOINT_UNCONFIRMED)
        dedicated = RuntimeNetworkingService(topology=Topology.DEDICATED_AUTHORITATIVE, room_id="room:1"); server = session("principal:service", "session:server")
        dedicated.admit_session(server, transport_id="transport:server", path=TransportPath.WSS_DEDICATED, now=10)
        dedicated.register_thing(thing_id="avatar", declaration=NetworkDeclaration(), authority_session_id="session:server")
        self.assertEqual(dedicated.authority_lost(thing_id="avatar"), RuntimeOutcome.AUTHORITY_LOST)
        with self.assertRaises(NetworkError) as unsupported: dedicated.migrate_peer_host(new_authority_session_id="session:server", checkpoint=dedicated.capture_checkpoint(thing_ids=["avatar"], confirmed=True), now=20)
        self.assertEqual(unsupported.exception.outcome, RuntimeOutcome.MIGRATION_UNSUPPORTED)

    def test_rate_and_unloaded_event_queue_bounds(self):
        self.net.set_residency("avatar", Residency.KNOWN_UNLOADED)
        for n in range(1, MAX_PENDING_EVENTS_PER_THING + 1): self.net.ingress(env(f"e{n}", MessageClass.EVENT, "session:host", n, locus="hit"), now=20, tick=n)
        with self.assertRaises(NetworkError) as full: self.net.ingress(env("overflow", MessageClass.EVENT, "session:host", MAX_PENDING_EVENTS_PER_THING + 1, locus="hit"), now=20, tick=999)
        self.assertEqual(full.exception.outcome, RuntimeOutcome.QUEUE_FULL)
        fresh = RuntimeNetworkingService(topology=Topology.PEER_HOSTED, room_id="room:1"); fresh.admit_session(self.client, transport_id="transport:a", path=TransportPath.WEBRTC_DIRECT, now=10)
        fresh.register_thing(thing_id="avatar", declaration=NetworkDeclaration(frozenset({"move"})), authority_session_id="session:alice", controller_principal_id="principal:alice")
        for n in range(MAX_MESSAGES_PER_TICK): fresh.ingress(env(f"r{n}", MessageClass.INPUT, "session:alice", n + 1), now=20, tick=77)
        with self.assertRaises(NetworkError) as limited: fresh.ingress(env("r-over", MessageClass.INPUT, "session:alice", MAX_MESSAGES_PER_TICK + 1), now=20, tick=77)
        self.assertEqual(limited.exception.outcome, RuntimeOutcome.RATE_LIMITED)

    def test_signalling_is_bounded_and_cannot_import_semantic_or_host_authority(self):
        good = validate_signalling_envelope({"kind": "offer", "session_id": "session:alice", "transport_id": "transport:a1", "offer": "sdp"}); self.assertEqual(good["kind"], "offer")
        with self.assertRaises(NetworkError) as bad: validate_signalling_envelope({"kind": "offer", "session_id": "session:alice", "transport_id": "transport:a1", "offer": {"nested": {"host_handle": "x"}}})
        self.assertEqual(bad.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_at023_forged_sender_and_cross_room_admission_fail_before_semantics(self):
        before = self.net.semantic_snapshot()
        with self.assertRaises(NetworkError) as forged: self.net.ingress(env("forge", MessageClass.INPUT, "session:ghost", 1), now=20, tick=1)
        self.assertEqual(forged.exception.outcome, RuntimeOutcome.AUTH_REQUIRED)
        with self.assertRaises(NetworkError) as cross_room: self.net.admit_session(session("principal:bob", "session:bob", room="room:other"), transport_id="transport:b", path=TransportPath.WEBRTC_DIRECT, now=20)
        self.assertEqual(cross_room.exception.outcome, RuntimeOutcome.AUTH_REJECTED); self.assertEqual(self.net.semantic_snapshot(), before)

    def test_at024_message_bytes_and_tree_depth_are_independently_bounded(self):
        with self.assertRaises(NetworkError) as oversize: self.net.ingress(env("huge", MessageClass.INPUT, "session:alice", 1, payload={"blob": "x" * 70000}), now=20, tick=1)
        self.assertEqual(oversize.exception.outcome, RuntimeOutcome.MESSAGE_OVERSIZE)
        nested = {}; cursor = nested
        for _ in range(34): child = {}; cursor["ok"] = child; cursor = child
        with self.assertRaises(NetworkError) as deep: self.net.ingress(env("deep", MessageClass.INPUT, "session:alice", 1, payload=nested), now=20, tick=2)
        self.assertEqual(deep.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_protected_asset_revision_remains_indivisible_across_migration_and_snapshot(self):
        original = protected("a"); self.net.add_protected_asset("music", original)
        checkpoint = self.net.capture_checkpoint(thing_ids=["avatar"], confirmed=True)
        self.net.migrate_peer_host(new_authority_session_id="session:alice", checkpoint=checkpoint, now=20)
        self.assertEqual(self.net.protected_asset("music"), original); snap = self.net.semantic_snapshot(); self.assertEqual(snap["protected_assets"]["music"], original)
        incomplete = original.copy(); incomplete.pop("provenance")
        with self.assertRaises(NetworkError) as rejected: self.net.add_protected_asset("broken", incomplete)
        self.assertEqual(rejected.exception.outcome, RuntimeOutcome.AUTH_REJECTED)


if __name__ == "__main__":
    unittest.main()
