from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from splashmx.runtime.network import (
    MAX_MESSAGES_PER_TICK,
    MessageClass,
    NetworkDeclaration,
    NetworkEnvelope,
    NetworkError,
    OpaqueJoinTicketAuthority,
    Residency,
    RuntimeNetworkingService,
    RuntimeOutcome,
    SessionIdentity,
    Topology,
    TransportPath,
    select_dedicated_path,
    select_peer_path,
    validate_signalling_envelope,
)

ROOT = Path(__file__).resolve().parents[2]
CREATION_PATH = ROOT / "experiments/smx-017-network-harness/creation.json"

PROTECTED_REVISION = {
    "revision_digest": "sha256:" + "9" * 64,
    "source_digest": "sha256:" + "8" * 64,
    "source_identity": {"logical_name": "click-master.wav"},
    "source_metadata": {"format": "wav", "channels": 1, "sample_rate_hz": 48000},
    "media_semantics": {"role": "door-confirmation", "loop": False},
    "provenance": {"origin": "SMX-017 synthetic fixture", "author": "SplashMX research harness"},
    "licence_attribution": {"licence": "CC0-1.0"},
    "derivation_lineage": [],
}


def historical_creation() -> dict:
    return json.loads(CREATION_PATH.read_text(encoding="utf-8"))


def session(principal: str, sid: str, *, expiry: int = 10_000) -> SessionIdentity:
    return SessionIdentity(principal, sid, "room:smx047", expiry)


def envelope(
    message_id: str,
    message_class: MessageClass,
    sender: str,
    sequence: int,
    *,
    thing: str,
    locus: str,
    payload: dict | None = None,
    epoch: int = 1,
) -> NetworkEnvelope:
    return NetworkEnvelope(
        message_id,
        message_class,
        sender,
        epoch,
        sequence,
        thing,
        locus,
        payload or {},
    )


class ProductionTopologyFixture:
    def __init__(self, topology: Topology):
        self.creation = historical_creation()
        self.original_creation = copy.deepcopy(self.creation)
        self.topology = topology
        self.net = RuntimeNetworkingService(topology=topology, room_id="room:smx047")
        self.host = session("host", "session:host")
        self.client = session("alice", "session:alice")
        path = {
            Topology.OFFLINE: TransportPath.LOCAL,
            Topology.PEER_HOSTED: TransportPath.WEBRTC_DIRECT,
            Topology.DEDICATED_AUTHORITATIVE: TransportPath.WSS_DEDICATED,
        }[topology]
        self.net.admit_session(self.host, transport_id=f"transport:{topology.value}:host", path=path, now=10)
        self.net.admit_session(self.client, transport_id=f"transport:{topology.value}:alice", path=path, now=10)

        by_id = {thing["thing_id"]: thing for thing in self.creation["things"]}
        self.net.register_thing(
            thing_id="world",
            declaration=NetworkDeclaration(),
            authority_session_id=self.host.session_id,
        )
        avatar_network = by_id["avatar:alice"]["network"]
        self.net.register_thing(
            thing_id="avatar:alice",
            declaration=NetworkDeclaration(
                input_kinds=frozenset(avatar_network["inputs"]),
                state_loci=frozenset(avatar_network["replicated_state"]),
            ),
            authority_session_id=self.host.session_id,
            controller_principal_id=self.client.principal_id,
        )
        door_network = by_id["door"]["network"]
        self.net.register_thing(
            thing_id="door",
            declaration=NetworkDeclaration(
                state_loci=frozenset(door_network["replicated_state"]),
                event_kinds=frozenset(door_network["events"]),
            ),
            authority_session_id=self.host.session_id,
        )
        self.net.add_protected_asset("asset:click", PROTECTED_REVISION)

    def assert_creation_untouched(self, testcase: unittest.TestCase) -> None:
        testcase.assertEqual(self.creation, self.original_creation)

    def canonical_workload(self) -> None:
        self.net.ingress(
            envelope(
                "input:move",
                MessageClass.INPUT,
                self.client.session_id,
                1,
                thing="avatar:alice",
                locus="move",
                payload={"dx": 3},
            ),
            now=20,
            tick=1,
        )
        self.net.ingress(
            envelope(
                "input:door",
                MessageClass.INPUT,
                self.client.session_id,
                2,
                thing="avatar:alice",
                locus="open_door",
            ),
            now=20,
            tick=1,
        )
        self.net.ingress(
            envelope(
                "state:avatar",
                MessageClass.STATE,
                self.host.session_id,
                1,
                thing="avatar:alice",
                locus="position_x",
                payload={"value": 3},
            ),
            now=20,
            tick=2,
        )
        self.net.ingress(
            envelope(
                "state:door",
                MessageClass.STATE,
                self.host.session_id,
                2,
                thing="door",
                locus="open",
                payload={"value": True},
            ),
            now=20,
            tick=2,
        )
        self.net.ingress(
            envelope(
                "event:door-opened",
                MessageClass.EVENT,
                self.host.session_id,
                1,
                thing="door",
                locus="door_opened",
                payload={"source": "input:door"},
            ),
            now=20,
            tick=2,
        )

    def normalized_semantics(self) -> dict:
        snapshot = self.net.semantic_snapshot()
        return {
            "room_id": snapshot["room_id"],
            "things": snapshot["things"],
            "protected_assets": snapshot["protected_assets"],
        }


class SMX047ProductionTopologyGateTests(unittest.TestCase):
    def test_same_canonical_creation_executes_all_topologies_without_rewrite(self):
        semantics = []
        creation_revisions = []
        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            fixture = ProductionTopologyFixture(topology)
            creation_revisions.append(fixture.creation["creation_revision_id"])
            fixture.canonical_workload()
            fixture.assert_creation_untouched(self)
            semantics.append(fixture.normalized_semantics())

        self.assertEqual(creation_revisions, ["smx017-topology-equivalence-v1"] * 3)
        self.assertEqual(semantics[0], semantics[1])
        self.assertEqual(semantics[1], semantics[2])
        self.assertEqual(semantics[0]["things"]["avatar:alice"]["replicated_state"]["position_x"], {"value": 3})
        self.assertEqual(semantics[0]["things"]["door"]["replicated_state"]["open"], {"value": True})

    def test_loss_latency_duplicate_reorder_and_stale_epoch_have_typed_topology_independent_results(self):
        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            dropped = ProductionTopologyFixture(topology)
            dropped.net.ingress(
                envelope("late-state", MessageClass.STATE, dropped.host.session_id, 2, thing="avatar:alice", locus="position_x", payload={"value": 2}),
                now=120,
                tick=90,
            )
            self.assertEqual(
                dropped.net.semantic_snapshot()["things"]["avatar:alice"]["replicated_state"]["position_x"],
                {"value": 2},
            )

            reordered = ProductionTopologyFixture(topology)
            reordered.net.ingress(
                envelope("newer", MessageClass.STATE, reordered.host.session_id, 2, thing="avatar:alice", locus="position_x", payload={"value": 2}),
                now=20,
                tick=1,
            )
            with self.assertRaises(NetworkError) as old:
                reordered.net.ingress(
                    envelope("older", MessageClass.STATE, reordered.host.session_id, 1, thing="avatar:alice", locus="position_x", payload={"value": 1}),
                    now=21,
                    tick=2,
                )
            self.assertEqual(old.exception.outcome, RuntimeOutcome.REORDERED)

            duplicated = ProductionTopologyFixture(topology)
            duplicated.net.ingress(
                envelope("duplicate-id", MessageClass.STATE, duplicated.host.session_id, 1, thing="avatar:alice", locus="position_x", payload={"value": 1}),
                now=20,
                tick=1,
            )
            with self.assertRaises(NetworkError) as replay:
                duplicated.net.ingress(
                    envelope("duplicate-id", MessageClass.STATE, duplicated.host.session_id, 2, thing="avatar:alice", locus="position_x", payload={"value": 2}),
                    now=21,
                    tick=2,
                )
            self.assertEqual(replay.exception.outcome, RuntimeOutcome.REPLAY)

            stale = ProductionTopologyFixture(topology)
            with self.assertRaises(NetworkError) as stale_epoch:
                stale.net.ingress(
                    envelope("future-epoch", MessageClass.INPUT, stale.client.session_id, 1, thing="avatar:alice", locus="move", payload={"dx": 1}, epoch=2),
                    now=20,
                    tick=1,
                )
            self.assertEqual(stale_epoch.exception.outcome, RuntimeOutcome.STALE_EPOCH)

    def test_browser_suspension_and_reconnect_rebind_only_transient_transport(self):
        fixture = ProductionTopologyFixture(Topology.PEER_HOSTED)
        fixture.canonical_workload()
        before = fixture.normalized_semantics()
        outcome = fixture.net.transport.suspend(fixture.client.session_id)
        self.assertEqual(outcome, RuntimeOutcome.SUSPENDED)
        fixture.net.transport.disconnect(fixture.client.session_id)
        rebound = fixture.net.reconnect_session(
            fixture.client.session_id,
            transport_id="transport:peer_hosted:alice:reconnected",
            path=TransportPath.WEBRTC_TURN,
            now=30,
        )
        self.assertEqual(rebound.session.principal_id, "alice")
        self.assertEqual(rebound.session.session_id, fixture.client.session_id)
        self.assertEqual(rebound.generation, 2)
        self.assertEqual(fixture.normalized_semantics(), before)
        fixture.net.set_relevant(fixture.client.session_id, "avatar:alice", True)
        baseline = fixture.net.reconnect_baseline(fixture.client.session_id, now=30)
        self.assertEqual(tuple(baseline["things"]), ("avatar:alice",))
        self.assertNotIn("transport:", repr(baseline))
        self.assertNotIn("session:", repr(baseline))

    def test_confirmed_peer_host_migration_and_host_loss_policy_hold_on_production_runtime(self):
        peer = ProductionTopologyFixture(Topology.PEER_HOSTED)
        peer.net.ingress(
            envelope("state-before-loss", MessageClass.STATE, peer.host.session_id, 1, thing="avatar:alice", locus="position_x", payload={"value": 7}),
            now=20,
            tick=1,
        )
        unconfirmed = peer.net.capture_checkpoint(thing_ids=["world", "avatar:alice", "door"], confirmed=False)
        before = peer.normalized_semantics()
        with self.assertRaises(NetworkError) as denied:
            peer.net.migrate_peer_host(new_authority_session_id=peer.client.session_id, checkpoint=unconfirmed, now=21)
        self.assertEqual(denied.exception.outcome, RuntimeOutcome.CHECKPOINT_UNCONFIRMED)
        self.assertEqual(peer.normalized_semantics(), before)

        confirmed = peer.net.capture_checkpoint(thing_ids=["world", "avatar:alice", "door"], confirmed=True)
        new_epoch = peer.net.migrate_peer_host(new_authority_session_id=peer.client.session_id, checkpoint=confirmed, now=22)
        self.assertEqual(new_epoch, 2)
        self.assertEqual(peer.net.semantic_snapshot()["things"]["avatar:alice"]["replicated_state"]["position_x"], {"value": 7})
        with self.assertRaises(NetworkError) as stale:
            peer.net.ingress(
                envelope("old-authority", MessageClass.STATE, peer.host.session_id, 2, thing="avatar:alice", locus="position_x", payload={"value": 99}, epoch=1),
                now=23,
                tick=2,
            )
        self.assertEqual(stale.exception.outcome, RuntimeOutcome.STALE_EPOCH)

        dedicated = ProductionTopologyFixture(Topology.DEDICATED_AUTHORITATIVE)
        self.assertEqual(dedicated.net.authority_lost(thing_id="avatar:alice"), RuntimeOutcome.AUTHORITY_LOST)
        checkpoint = dedicated.net.capture_checkpoint(thing_ids=["avatar:alice"], confirmed=True)
        with self.assertRaises(NetworkError) as no_client_promotion:
            dedicated.net.migrate_peer_host(new_authority_session_id=dedicated.client.session_id, checkpoint=checkpoint, now=20)
        self.assertEqual(no_client_promotion.exception.outcome, RuntimeOutcome.MIGRATION_UNSUPPORTED)

    def test_nat_tls_ice_signalling_and_auth_failures_are_typed_runtime_outcomes(self):
        self.assertEqual(
            select_peer_path(tls_ok=False, signalling_ok=True, webrtc_available=True, ice_direct_ok=True, turn_ok=True, wss_relay_ok=True).outcome,
            RuntimeOutcome.TLS_FAILED,
        )
        self.assertEqual(
            select_peer_path(tls_ok=True, signalling_ok=False, webrtc_available=True, ice_direct_ok=True, turn_ok=True, wss_relay_ok=True).outcome,
            RuntimeOutcome.SIGNAL_UNAVAILABLE,
        )
        no_candidate = select_peer_path(
            tls_ok=True, signalling_ok=True, webrtc_available=True, ice_direct_ok=False, turn_ok=False, wss_relay_ok=False
        )
        self.assertEqual(no_candidate.outcome, RuntimeOutcome.ICE_NO_CANDIDATE)
        relay = select_peer_path(
            tls_ok=True, signalling_ok=True, webrtc_available=True, ice_direct_ok=False, turn_ok=False, wss_relay_ok=True
        )
        self.assertEqual(relay.path, TransportPath.WSS_PEER_RELAY)
        self.assertIn(RuntimeOutcome.TRANSPORT_FALLBACK, relay.diagnostics)
        self.assertIn(RuntimeOutcome.TURN_UNAVAILABLE, relay.diagnostics)

        self.assertEqual(select_dedicated_path(tls_ok=False, server_ok=True, wss_ok=True).outcome, RuntimeOutcome.TLS_FAILED)
        self.assertEqual(select_dedicated_path(tls_ok=True, server_ok=False, wss_ok=True).outcome, RuntimeOutcome.SERVER_UNAVAILABLE)
        self.assertEqual(select_dedicated_path(tls_ok=True, server_ok=True, wss_ok=False).outcome, RuntimeOutcome.TRANSPORT_UNAVAILABLE)

        with self.assertRaises(NetworkError) as forged_signal:
            validate_signalling_envelope(
                {
                    "kind": "offer",
                    "session_id": "session:alice",
                    "transport_id": "transport:alice",
                    "offer": {"nested": {"host_handle": "forged"}},
                }
            )
        self.assertEqual(forged_signal.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

        ticket_authority = OpaqueJoinTicketAuthority()
        alice = session("alice", "session:alice")
        token = ticket_authority.issue(alice, audience="runtime", now=10, ttl_seconds=30)
        with self.assertRaises(NetworkError) as wrong_scope:
            ticket_authority.redeem(token, audience="signal", room_id="room:smx047", now=11)
        self.assertEqual(wrong_scope.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_hostile_ingress_bounds_fail_before_semantic_mutation(self):
        fixture = ProductionTopologyFixture(Topology.PEER_HOSTED)
        before = fixture.normalized_semantics()
        hostile = [
            (
                envelope("forged-sender", MessageClass.INPUT, "session:ghost", 1, thing="avatar:alice", locus="move", payload={"dx": 1}),
                RuntimeOutcome.AUTH_REQUIRED,
            ),
            (
                envelope("capability", MessageClass.INPUT, fixture.client.session_id, 1, thing="avatar:alice", locus="move", payload={"nested": [{"capability_grant": "ambient"}]}),
                RuntimeOutcome.AUTH_REJECTED,
            ),
            (
                envelope("oversize", MessageClass.INPUT, fixture.client.session_id, 1, thing="avatar:alice", locus="move", payload={"blob": "x" * 70_000}),
                RuntimeOutcome.MESSAGE_OVERSIZE,
            ),
        ]
        for message, expected in hostile:
            with self.assertRaises(NetworkError) as caught:
                fixture.net.ingress(message, now=20, tick=1)
            self.assertEqual(caught.exception.outcome, expected)
            self.assertEqual(fixture.normalized_semantics(), before)

        rate = ProductionTopologyFixture(Topology.PEER_HOSTED)
        for index in range(MAX_MESSAGES_PER_TICK):
            rate.net.ingress(
                envelope(
                    f"rate-{index}",
                    MessageClass.INPUT,
                    rate.client.session_id,
                    index + 1,
                    thing="avatar:alice",
                    locus="move",
                    payload={"dx": 0},
                ),
                now=20,
                tick=77,
            )
        with self.assertRaises(NetworkError) as limited:
            rate.net.ingress(
                envelope(
                    "rate-over",
                    MessageClass.INPUT,
                    rate.client.session_id,
                    MAX_MESSAGES_PER_TICK + 1,
                    thing="avatar:alice",
                    locus="move",
                    payload={"dx": 0},
                ),
                now=20,
                tick=77,
            )
        self.assertEqual(limited.exception.outcome, RuntimeOutcome.RATE_LIMITED)

    def test_relevance_unload_and_tombstone_remain_distinct_under_delayed_delivery(self):
        fixture = ProductionTopologyFixture(Topology.PEER_HOSTED)
        fixture.net.set_relevant(fixture.client.session_id, "door", True)
        before = fixture.net.semantic_snapshot()["things"]["door"].copy()
        fixture.net.set_relevant(fixture.client.session_id, "door", False)
        self.assertEqual(fixture.net.semantic_snapshot()["things"]["door"], before)

        fixture.net.set_residency("door", Residency.KNOWN_UNLOADED)
        fixture.net.ingress(
            envelope("door-state-1", MessageClass.STATE, fixture.host.session_id, 1, thing="door", locus="open", payload={"value": False}),
            now=20,
            tick=1,
        )
        fixture.net.ingress(
            envelope("door-state-2", MessageClass.STATE, fixture.host.session_id, 2, thing="door", locus="open", payload={"value": True}),
            now=40,
            tick=30,
        )
        fixture.net.ingress(
            envelope("door-event", MessageClass.EVENT, fixture.host.session_id, 1, thing="door", locus="door_opened"),
            now=40,
            tick=30,
        )
        restored = fixture.net.set_residency("door", Residency.RESIDENT)
        self.assertEqual([item.message_id for item in restored], ["door-event", "door-state-2"])

        fixture.net.set_residency("door", Residency.KNOWN_UNLOADED)
        fixture.net.ingress(
            envelope("door-event-after", MessageClass.EVENT, fixture.host.session_id, 2, thing="door", locus="door_opened"),
            now=41,
            tick=31,
        )
        fixture.net.set_residency("door", Residency.TOMBSTONED)
        self.assertEqual(fixture.net.pending_count("door"), 0)
        with self.assertRaises(NetworkError) as resurrect:
            fixture.net.set_residency("door", Residency.RESIDENT)
        self.assertEqual(resurrect.exception.outcome, RuntimeOutcome.TARGET_TOMBSTONED)

    def test_protected_asset_revision_remains_indivisible_across_topologies_and_migration(self):
        observed = []
        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            fixture = ProductionTopologyFixture(topology)
            observed.append(fixture.net.protected_asset("asset:click"))
        self.assertEqual(observed, [PROTECTED_REVISION, PROTECTED_REVISION, PROTECTED_REVISION])

        peer = ProductionTopologyFixture(Topology.PEER_HOSTED)
        checkpoint = peer.net.capture_checkpoint(thing_ids=["world", "avatar:alice", "door"], confirmed=True)
        peer.net.migrate_peer_host(new_authority_session_id=peer.client.session_id, checkpoint=checkpoint, now=20)
        self.assertEqual(peer.net.protected_asset("asset:click"), PROTECTED_REVISION)

        incomplete = copy.deepcopy(PROTECTED_REVISION)
        incomplete.pop("media_semantics")
        with self.assertRaises(NetworkError):
            peer.net.add_protected_asset("asset:broken", incomplete)
        self.assertEqual(peer.net.protected_asset("asset:click"), PROTECTED_REVISION)

    def test_canonical_and_runtime_semantic_surfaces_do_not_leak_transport_engine_identity(self):
        creation_text = CREATION_PATH.read_text(encoding="utf-8").lower()
        for forbidden in ("webrtc", "websocket", "peer_id", "nodepath", "resourceuid", "rpc"):
            self.assertNotIn(forbidden, creation_text)

        for topology in (Topology.OFFLINE, Topology.PEER_HOSTED, Topology.DEDICATED_AUTHORITATIVE):
            fixture = ProductionTopologyFixture(topology)
            fixture.canonical_workload()
            semantic_text = repr(fixture.net.semantic_snapshot()).lower()
            for forbidden in ("transport:", "session:", "nodepath", "resourceuid", "socket_id", "godot_peer_id"):
                self.assertNotIn(forbidden, semantic_text)


if __name__ == "__main__":
    unittest.main()
