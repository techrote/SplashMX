from __future__ import annotations

import copy
import unittest

from model import (
    AssetRecord,
    AuthorityViolation,
    CanonicalCreation,
    CanonicalNetworkLeak,
    CapabilityDenied,
    EventMessage,
    InputMessage,
    NetworkDeclaration,
    QueueBudgetExceeded,
    ReferenceUnavailable,
    ReplayRejected,
    ReplicationField,
    RuntimeSession,
    StateUpdate,
    ThingRecord,
    TopologyPolicy,
    reject_transport_leaks,
)


def creation() -> CanonicalCreation:
    return CanonicalCreation(
        revision_id="rev-network-001",
        things=(
            ThingRecord(
                "thing-world",
                None,
                {"round": 1},
                NetworkDeclaration(
                    replicated_fields=(ReplicationField("round"),),
                    emits_events=("round_started",),
                ),
            ),
            ThingRecord(
                "thing-player",
                "thing-world",
                {"x": 0, "health": 10},
                NetworkDeclaration(
                    replicated_fields=(
                        ReplicationField("x"),
                        ReplicationField("health"),
                    ),
                    accepts_inputs=("move",),
                    emits_events=("hit",),
                ),
            ),
            ThingRecord(
                "thing-hud",
                "thing-world",
                {"visible": True},
                NetworkDeclaration(),
            ),
        ),
        assets=(
            AssetRecord(
                "asset-music",
                "sha256:music-source",
                {"uri": "package://music/source.flac", "media_type": "audio/flac"},
                {"author": "example", "license": "CC-BY-4.0", "derived_from": "master-7"},
                {"channels": 2, "sample_rate": 48000, "semantic_role": "music"},
            ),
        ),
    )


class MultiplayerSemanticTests(unittest.TestCase):
    def test_nt001_same_canonical_creation_across_topologies(self):
        item = creation()
        digest = item.digest
        sessions = (
            RuntimeSession(item, TopologyPolicy.offline()),
            RuntimeSession(item, TopologyPolicy.peer_hosted("webrtc")),
            RuntimeSession(item, TopologyPolicy.authoritative("websocket")),
        )
        self.assertEqual({session.canonical_digest for session in sessions}, {digest})
        self.assertEqual(item.digest, digest)

    def test_nt002_containment_control_authority_replication_are_independent(self):
        session = RuntimeSession(creation(), TopologyPolicy.peer_hosted())
        session.things["thing-player"].authority_principal = "host:A"
        session.set_controller("thing-player", "user:B")
        original_network = session.things["thing-player"].network
        original_epoch = session.things["thing-player"].authority_epoch
        session.reparent("thing-player", "thing-hud")
        player = session.things["thing-player"]
        self.assertEqual(player.parent_id, "thing-hud")
        self.assertEqual(player.controller_principal, "user:B")
        self.assertEqual(player.authority_principal, "host:A")
        self.assertEqual(player.authority_epoch, original_epoch)
        self.assertEqual(player.network, original_network)

    def test_nt003_client_input_is_intent_not_authoritative_state(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.things["thing-player"].authority_principal = "server"
        session.set_controller("thing-player", "user:A")
        session.receive_input(InputMessage("thing-player", "move", 7, "user:A", 1, 1))
        self.assertEqual(session.things["thing-player"].state["x"], 0)

    def test_nt004_non_controller_input_rejected(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.set_controller("thing-player", "user:A")
        with self.assertRaises(AuthorityViolation):
            session.receive_input(InputMessage("thing-player", "move", 1, "user:B", 1, 1))

    def test_nt005_duplicate_or_stale_input_rejected(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.set_controller("thing-player", "user:A")
        message = InputMessage("thing-player", "move", 1, "user:A", 4, 1)
        session.receive_input(message)
        with self.assertRaises(ReplayRejected):
            session.receive_input(message)

    def test_nt006_only_current_authority_can_author_state(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.things["thing-player"].authority_principal = "server"
        with self.assertRaises(AuthorityViolation):
            session.authoritative_state_update(
                "thing-player", "x", 9, sender_principal="user:A", sequence=1
            )
        session.authoritative_state_update(
            "thing-player", "x", 9, sender_principal="server", sequence=1
        )
        self.assertEqual(session.things["thing-player"].state["x"], 9)

    def test_nt007_authority_transfer_epoch_rejects_stale_packets(self):
        session = RuntimeSession(creation(), TopologyPolicy.peer_hosted())
        session.things["thing-player"].authority_principal = "host:A"
        session.unload("thing-player")
        stale = StateUpdate("thing-player", "x", 3, "host:A", 1, 1)
        session.receive_state(stale)
        self.assertEqual(len(session.pending_for_unloaded["thing-player"]), 1)

        new_epoch = session.transfer_authority("thing-player", "host:B")
        self.assertEqual(new_epoch, 2)
        self.assertNotIn("thing-player", session.pending_for_unloaded)
        session.restore("thing-player")
        self.assertEqual(session.things["thing-player"].state["x"], 0)

        with self.assertRaises(ReplayRejected):
            session.receive_state(stale)
        session.receive_state(StateUpdate("thing-player", "x", 4, "host:B", 2, 2))
        self.assertEqual(session.things["thing-player"].state["x"], 4)

    def test_nt008_relevance_is_peer_context_not_containment_or_existence(self):
        session = RuntimeSession(creation(), TopologyPolicy.peer_hosted())
        session.attach_peer("user:A", 17)
        session.set_relevance("user:A", {"thing-player"})
        self.assertEqual(session.peers["user:A"].relevant_things, {"thing-player"})
        self.assertEqual(session.things["thing-player"].parent_id, "thing-world")
        self.assertEqual(session.things["thing-player"].existence, "present")

    def test_nt009_reconnect_rebinds_peer_id_not_principal_or_thing(self):
        session = RuntimeSession(creation(), TopologyPolicy.peer_hosted())
        session.attach_peer("user:A", 17)
        session.set_relevance("user:A", {"thing-player"})
        session.set_controller("thing-player", "user:A")
        session.reattach_peer("user:A", 91)
        self.assertEqual(session.peers["user:A"].peer_id, 91)
        self.assertEqual(session.peers["user:A"].relevant_things, {"thing-player"})
        self.assertEqual(session.things["thing-player"].controller_principal, "user:A")

    def test_nt010_known_unloaded_state_gets_latest_bounded_delivery(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative(), max_pending_per_thing=1)
        session.things["thing-player"].authority_principal = "server"
        session.unload("thing-player")
        session.receive_state(StateUpdate("thing-player", "x", 3, "server", 1, 1))
        session.receive_state(StateUpdate("thing-player", "x", 8, "server", 1, 2))
        self.assertEqual(len(session.pending_for_unloaded["thing-player"]), 1)
        with self.assertRaises(ReplayRejected):
            session.receive_state(StateUpdate("thing-player", "x", 99, "server", 1, 2))
        session.restore("thing-player")
        self.assertEqual(session.things["thing-player"].state["x"], 8)

    def test_nt011_unloaded_event_deduplicates_and_delivers_on_restore(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.things["thing-player"].authority_principal = "server"
        session.unload("thing-player")
        event = EventMessage("thing-player", "hit", {"amount": 2}, "evt:1", "server", 1)
        self.assertTrue(session.receive_event(event))
        self.assertFalse(session.receive_event(event))
        session.restore("thing-player")
        self.assertEqual(session.delivered_events, ["evt:1"])

    def test_nt012_pending_unloaded_queue_has_hard_budget(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative(), max_pending_per_thing=1)
        session.things["thing-player"].authority_principal = "server"
        session.unload("thing-player")
        session.receive_event(EventMessage("thing-player", "hit", {}, "evt:1", "server", 1))
        with self.assertRaises(QueueBudgetExceeded):
            session.receive_event(EventMessage("thing-player", "hit", {}, "evt:2", "server", 1))

    def test_nt013_tombstoned_target_rejects_network_delivery(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.things["thing-player"].authority_principal = "server"
        session.tombstone("thing-player")
        with self.assertRaises(ReferenceUnavailable):
            session.receive_state(StateUpdate("thing-player", "x", 1, "server", 1, 1))

    def test_nt014_peer_host_migration_preserves_thing_identity_and_bumps_epoch(self):
        session = RuntimeSession(creation(), TopologyPolicy.peer_hosted())
        session.things["thing-player"].authority_principal = "host:A"
        session.unload("thing-player")
        session.receive_event(EventMessage("thing-player", "hit", {}, "evt:old", "host:A", 1))
        before_ids = set(session.things)
        session.migrate_peer_host("host:A", "host:B")
        self.assertEqual(set(session.things), before_ids)
        self.assertEqual(session.things["thing-player"].authority_principal, "host:B")
        self.assertEqual(session.things["thing-player"].authority_epoch, 2)
        self.assertNotIn("thing-player", session.pending_for_unloaded)

    def test_nt015_transport_identifiers_cannot_enter_canonical_network_data(self):
        item = creation()
        projection = copy.deepcopy(item.projection())
        projection["things"][0]["network"]["websocket"] = {"channel": 0}
        with self.assertRaises(CanonicalNetworkLeak):
            reject_transport_leaks(projection)
        projection = copy.deepcopy(item.projection())
        projection["things"][0]["network"]["peer_id"] = 7
        with self.assertRaises(CanonicalNetworkLeak):
            reject_transport_leaks(projection)

    def test_nt016_network_runtime_preserves_source_audio_and_provenance(self):
        item = creation()
        before = item.projection()["assets"]
        for policy in (
            TopologyPolicy.offline(),
            TopologyPolicy.peer_hosted(),
            TopologyPolicy.authoritative(),
        ):
            session = RuntimeSession(item, policy)
            session.attach_peer("user:A", f"{policy.name}:peer")
            self.assertEqual(item.projection()["assets"], before)
            self.assertEqual(session.canonical_digest, item.digest)

    def test_nt017_multiplayer_is_capability_mediated(self):
        with self.assertRaises(CapabilityDenied):
            RuntimeSession(
                creation(), TopologyPolicy.authoritative(), multiplayer_capability=False
            )
        RuntimeSession(creation(), TopologyPolicy.offline(), multiplayer_capability=False)

    def test_nt018_collaboration_edits_are_not_runtime_replication_messages(self):
        declaration = creation().things[1].network.as_dict()
        self.assertNotIn("document_transaction", declaration)
        self.assertNotIn("base_revision", declaration)
        self.assertEqual(set(declaration), {
            "replicated_fields",
            "accepts_inputs",
            "emits_events",
            "authority_mode",
            "relevance_mode",
        })

    def test_nt019_undeclared_state_and_event_are_rejected(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        session.things["thing-player"].authority_principal = "server"
        with self.assertRaises(AuthorityViolation):
            session.receive_state(StateUpdate("thing-player", "secret", 1, "server", 1, 1))
        with self.assertRaises(AuthorityViolation):
            session.receive_event(EventMessage("thing-player", "admin", {}, "evt:x", "server", 1))

    def test_nt020_host_migration_not_silently_available_in_authoritative_mode(self):
        session = RuntimeSession(creation(), TopologyPolicy.authoritative())
        with self.assertRaises(AuthorityViolation):
            session.migrate_peer_host("server", "user:A")


if __name__ == "__main__":
    unittest.main()
