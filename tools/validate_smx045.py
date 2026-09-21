#!/usr/bin/env python3
"""Validate the SMX-045 network deployment/auth/signalling selection handoff."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/SMX-045-NETWORK-DEPLOYMENT-SELECTION.md"
FIXTURES = ROOT / "docs/research/SMX-045-NETWORK-DEPLOYMENT-FIXTURES.json"
SMX017 = ROOT / "docs/research/SMX-017-NETWORK-HARNESS-FIXTURES.json"
SPIKE = ROOT / "experiments/smx-045-network-deployment-spike/spike.py"
TESTS = ROOT / "experiments/smx-045-network-deployment-spike/test_spike.py"
BROWSER = ROOT / "experiments/smx-045-network-deployment-spike/browser_probe.mjs"
README = ROOT / "experiments/smx-045-network-deployment-spike/README.md"
WORKFLOW = ROOT / ".github/workflows/smx045-network-deployment.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, SMX017, SPIKE, TESTS, BROWSER, README, WORKFLOW):
        require(path.is_file(), f"missing SMX-045 artifact: {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    doc_lower = doc.lower()
    for phrase in (
        "WebRTC DataChannel",
        "authenticated WSS",
        "ICE/STUN/TURN",
        "authorization-code + PKCE",
        "short-lived room/audience-bound runtime join ticket",
        "principal_id",
        "session_id",
        "transport_id",
        "peer host may be current simulation authority",
        "dedicated-authoritative baseline",
        "SMX-046 production handoff",
        "No Architecture-v1 contradiction was found",
        "not product latency/throughput SLOs",
    ):
        require(phrase.lower() in doc_lower, f"SMX-045 selection lost required phrase: {phrase}")

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
        require(phrase in doc, f"SMX-045 protected-Asset contract lost: {phrase}")

    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(
        data.get("schema") == "splashmx.smx045-network-deployment-fixtures/1",
        "wrong SMX-045 fixture schema",
    )
    selected = data.get("selected_paths", {})
    require(selected.get("peer_primary") == "webrtc_datachannel_direct", "peer primary drifted")
    require(selected.get("peer_nat_relay") == "webrtc_datachannel_turn", "TURN path drifted")
    require(selected.get("peer_fallback") == "wss_peer_relay", "peer fallback drifted")
    require(selected.get("dedicated") == "wss_dedicated_authority", "dedicated baseline drifted")
    require(selected.get("auth_control_plane") == "authorization_code_pkce", "auth profile drifted")

    invariants = data.get("selection_invariants", [])
    require(
        [row.get("id") for row in invariants] == [f"ND-{n:03d}" for n in range(1, 17)],
        "ND invariant set must remain contiguous ND-001..ND-016",
    )
    adversarial = data.get("adversarial_fixtures", [])
    require(
        [row.get("id") for row in adversarial] == [f"NDF-{n:03d}" for n in range(1, 17)],
        "NDF adversarial set must remain contiguous NDF-001..NDF-016",
    )

    outcomes = set(data.get("typed_outcomes", []))
    required_outcomes = {
        "network.auth_required",
        "network.auth_expired",
        "network.auth_rejected",
        "network.tls_failed",
        "network.signalling_unavailable",
        "network.signalling_oversize",
        "network.ice_no_candidate",
        "network.turn_unavailable",
        "network.transport_unavailable",
        "network.transport_fallback",
        "network.suspended",
        "network.reconnect_required",
        "network.reconnect_failed",
        "network.server_unavailable",
        "network.authority_lost",
    }
    require(required_outcomes <= outcomes, "typed network outcome set is incomplete")

    inherited = json.loads(SMX017.read_text(encoding="utf-8"))
    tn_ids = [row["id"] for row in inherited["boundary_tests"]]
    require(tn_ids == [f"TN-{n:03d}" for n in range(1, 29)], "SMX-017 TN corpus drifted")
    require(
        data["inherits"]["smx017_boundary_tests"] == tn_ids,
        "SMX-045 inherited TN mapping drifted from SMX-017",
    )

    spike = SPIKE.read_text(encoding="utf-8")
    for token in (
        "class JoinTicketAuthority",
        "class RuntimeOutcome",
        "class TransportPath",
        "select_peer_path",
        "select_dedicated_path",
        "validate_signal",
        "reconnect",
        "dedicated_authority_failure",
        "PROTECTED_ASSET_FIELDS",
        "CI-local mechanism evidence only",
    ):
        require(token in spike, f"spike lost required boundary: {token}")

    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_principal_session_and_transport_identity_are_role_distinct_across_reconnect",
        "test_join_ticket_is_short_lived_scoped_single_use_and_not_capability_authority",
        "test_join_ticket_scope_tamper_expiry_and_wrong_room_fail_closed",
        "test_peer_transport_selection_direct_turn_and_wss_fallback_are_explicit",
        "test_peer_transport_failures_map_to_typed_outcomes",
        "test_dedicated_authority_uses_wss_and_never_promotes_client_on_server_loss",
        "test_suspension_reconnect_preserves_session_only_while_session_is_live",
        "test_signalling_is_bounded_and_cannot_import_principal_capability_or_host_identity",
        "test_peer_and_dedicated_trust_models_are_explicitly_different",
        "test_complete_protected_asset_revision_survives_network_projection_unchanged",
    ):
        require(token in tests, f"SMX-045 adversarial regression missing: {token}")

    browser = BROWSER.read_text(encoding="utf-8")
    for token in (
        "RTCPeerConnection",
        "smx-semantic-envelope",
        "restartIce",
        'iceTransportPolicy: "relay"',
        "network.ice_no_candidate",
        "smx045-browser-evidence.json",
    ):
        require(token in browser, f"browser mechanism probe lost required token: {token}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for token in (
        "validate_smx045.py",
        "test_*.py",
        "browser_probe.mjs",
        "playwright@1.55.0",
        "smx045-network-evidence",
    ):
        require(token in workflow, f"SMX-045 workflow lost required step: {token}")

    print("SMX-045 network deployment/auth/signalling selection contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-045 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
