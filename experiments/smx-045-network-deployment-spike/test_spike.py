#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from spike import (
    JoinTicketAuthority,
    MAX_SIGNAL_BYTES,
    RuntimeOutcome,
    SessionIdentity,
    TicketError,
    TransportPath,
    bind_transport,
    candidate_matrix,
    dedicated_authority_failure,
    reconnect,
    select_dedicated_path,
    select_peer_path,
    trust_profiles,
    validate_protected_asset_revision,
    validate_signal,
)


class NetworkDeploymentSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = SessionIdentity("principal:alice", "session:one", "room:alpha")
        self.authority = JoinTicketAuthority(b"k" * 32)

    def test_principal_session_and_transport_identity_are_role_distinct_across_reconnect(self):
        first = bind_transport(self.session, path=TransportPath.WEBRTC_DIRECT, transport_id="transport:7")
        second, outcome = reconnect(first, new_transport_id="transport:8", session_still_valid=True)
        self.assertIsNone(outcome)
        self.assertIsNotNone(second)
        self.assertEqual(second.session, first.session)
        self.assertNotEqual(second.transport_id, first.transport_id)
        self.assertNotEqual(second.transport_id, second.session.principal_id)
        self.assertNotEqual(second.transport_id, second.session.session_id)

    def test_join_ticket_is_short_lived_scoped_single_use_and_not_capability_authority(self):
        token = self.authority.issue(self.session, audience="signal", now=100, ttl_seconds=30, nonce="n1")
        redeemed = self.authority.redeem(token, audience="signal", room_id="room:alpha", now=110)
        self.assertEqual(redeemed, self.session)
        with self.assertRaises(TicketError) as replay:
            self.authority.redeem(token, audience="signal", room_id="room:alpha", now=111)
        self.assertEqual(replay.exception.outcome, RuntimeOutcome.AUTH_REJECTED)
        self.assertNotIn("capability", token.lower())

    def test_join_ticket_scope_tamper_expiry_and_wrong_room_fail_closed(self):
        wrong_room = self.authority.issue(self.session, audience="signal", now=100, nonce="n2")
        with self.assertRaises(TicketError) as scope:
            self.authority.redeem(wrong_room, audience="signal", room_id="room:other", now=101)
        self.assertEqual(scope.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

        expired = self.authority.issue(self.session, audience="signal", now=100, ttl_seconds=1, nonce="n3")
        with self.assertRaises(TicketError) as expiry:
            self.authority.redeem(expired, audience="signal", room_id="room:alpha", now=102)
        self.assertEqual(expiry.exception.outcome, RuntimeOutcome.AUTH_EXPIRED)

        valid = self.authority.issue(self.session, audience="signal", now=100, nonce="n4")
        body, sig = valid.split(".")
        forged = ("A" if body[0] != "A" else "B") + body[1:] + "." + sig
        with self.assertRaises(TicketError) as tamper:
            self.authority.redeem(forged, audience="signal", room_id="room:alpha", now=101)
        self.assertEqual(tamper.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

    def test_peer_transport_selection_direct_turn_and_wss_fallback_are_explicit(self):
        direct = select_peer_path(
            tls_ok=True, signalling_ok=True, webrtc_available=True,
            ice_direct_ok=True, turn_ok=True, wss_relay_ok=True,
        )
        self.assertEqual(direct.path, TransportPath.WEBRTC_DIRECT)
        self.assertIsNone(direct.outcome)

        turn = select_peer_path(
            tls_ok=True, signalling_ok=True, webrtc_available=True,
            ice_direct_ok=False, turn_ok=True, wss_relay_ok=True,
        )
        self.assertEqual(turn.path, TransportPath.WEBRTC_TURN)

        fallback = select_peer_path(
            tls_ok=True, signalling_ok=True, webrtc_available=True,
            ice_direct_ok=False, turn_ok=False, wss_relay_ok=True,
        )
        self.assertEqual(fallback.path, TransportPath.WSS_PEER_RELAY)
        self.assertEqual(
            fallback.diagnostics,
            (RuntimeOutcome.TURN_UNAVAILABLE, RuntimeOutcome.TRANSPORT_FALLBACK),
        )

    def test_peer_transport_failures_map_to_typed_outcomes(self):
        cases = (
            (
                dict(tls_ok=False, signalling_ok=True, webrtc_available=True, ice_direct_ok=True, turn_ok=True, wss_relay_ok=True),
                RuntimeOutcome.TLS_FAILED,
            ),
            (
                dict(tls_ok=True, signalling_ok=False, webrtc_available=True, ice_direct_ok=True, turn_ok=True, wss_relay_ok=True),
                RuntimeOutcome.SIGNAL_UNAVAILABLE,
            ),
            (
                dict(tls_ok=True, signalling_ok=True, webrtc_available=True, ice_direct_ok=False, turn_ok=False, wss_relay_ok=False),
                RuntimeOutcome.ICE_NO_CANDIDATE,
            ),
            (
                dict(tls_ok=True, signalling_ok=True, webrtc_available=False, ice_direct_ok=False, turn_ok=False, wss_relay_ok=False),
                RuntimeOutcome.TRANSPORT_UNAVAILABLE,
            ),
        )
        for kwargs, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(select_peer_path(**kwargs).outcome, expected)

    def test_dedicated_authority_uses_wss_and_never_promotes_client_on_server_loss(self):
        decision = select_dedicated_path(tls_ok=True, server_ok=True, wss_ok=True)
        self.assertEqual(decision.path, TransportPath.WSS_DEDICATED)
        self.assertEqual(dedicated_authority_failure(), RuntimeOutcome.AUTHORITY_LOST)
        self.assertEqual(
            select_dedicated_path(tls_ok=True, server_ok=False, wss_ok=True).outcome,
            RuntimeOutcome.SERVER_UNAVAILABLE,
        )
        self.assertEqual(
            select_dedicated_path(tls_ok=False, server_ok=True, wss_ok=True).outcome,
            RuntimeOutcome.TLS_FAILED,
        )

    def test_suspension_reconnect_preserves_session_only_while_session_is_live(self):
        first = bind_transport(self.session, path=TransportPath.WSS_PEER_RELAY, transport_id="transport:old")
        rebound, outcome = reconnect(first, new_transport_id="transport:new", session_still_valid=True)
        self.assertIsNone(outcome)
        self.assertEqual(rebound.session, self.session)
        self.assertEqual(rebound.transport_id, "transport:new")

        rebound, outcome = reconnect(first, new_transport_id="transport:new2", session_still_valid=False)
        self.assertIsNone(rebound)
        self.assertEqual(outcome, RuntimeOutcome.AUTH_EXPIRED)

        rebound, outcome = reconnect(first, new_transport_id="transport:old", session_still_valid=True)
        self.assertIsNone(rebound)
        self.assertEqual(outcome, RuntimeOutcome.RECONNECT_FAILED)

    def test_signalling_is_bounded_and_cannot_import_principal_capability_or_host_identity(self):
        accepted = validate_signal({
            "kind": "offer",
            "session_id": "session:one",
            "transport_id": "transport:9",
            "offer": "sdp",
        })
        self.assertEqual(accepted["session_id"], "session:one")
        for field in ("principal_id", "thing_id", "capability", "host_handle", "peer_id"):
            message = {"kind": "candidate", "session_id": "session:one", field: "forged"}
            with self.subTest(field=field), self.assertRaises(TicketError) as rejected:
                validate_signal(message)
            self.assertEqual(rejected.exception.outcome, RuntimeOutcome.AUTH_REJECTED)

        huge = {
            "kind": "candidate",
            "session_id": "session:one",
            "candidate": "x" * (MAX_SIGNAL_BYTES + 1),
        }
        with self.assertRaises(TicketError) as oversize:
            validate_signal(huge)
        self.assertEqual(oversize.exception.outcome, RuntimeOutcome.SIGNAL_OVERSIZE)

    def test_peer_and_dedicated_trust_models_are_explicitly_different(self):
        profiles = trust_profiles()
        self.assertIn("not trusted for fairness", profiles["peer_hosted"]["simulation_authority"])
        self.assertEqual(
            profiles["dedicated_authoritative"]["simulation_authority"],
            "operated dedicated service",
        )
        self.assertNotEqual(
            profiles["peer_hosted"]["simulation_authority"],
            profiles["dedicated_authoritative"]["simulation_authority"],
        )

    def test_candidate_matrix_does_not_claim_one_transport_fits_every_workload(self):
        rows = {row["candidate"]: row for row in candidate_matrix()}
        self.assertEqual(rows["WebRTC DataChannel"]["peer_hosted"], "selected primary")
        self.assertEqual(rows["WebSocket/WSS"]["dedicated"], "selected baseline")
        self.assertEqual(rows["ENet/UDP"]["peer_hosted"], "rejected baseline")
        self.assertEqual(rows["WebTransport/custom QUIC"]["dedicated"], "deferred")

    def test_complete_protected_asset_revision_survives_network_projection_unchanged(self):
        revision = {
            "revision_digest": "sha256:revision",
            "source_digest": "sha256:source",
            "source_identity": "asset-source:click",
            "source_metadata": {"name": "click.wav", "channels": 2},
            "media_semantics": {"kind": "audio", "loop": False},
            "provenance": {"origin": "author"},
            "licence_attribution": {"licence": "CC0"},
            "derivation_lineage": {"parents": []},
        }
        before = copy.deepcopy(revision)
        projected = validate_protected_asset_revision(revision)
        self.assertEqual(projected, before)
        self.assertEqual(revision, before)
        partial = dict(revision)
        del partial["media_semantics"]
        with self.assertRaises(ValueError):
            validate_protected_asset_revision(partial)

    def test_transport_binding_refuses_identity_aliasing(self):
        for invalid in ("principal:alice", "session:one", "room:alpha", ""):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bind_transport(self.session, path=TransportPath.WEBRTC_DIRECT, transport_id=invalid)


if __name__ == "__main__":
    unittest.main()
