#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-047 validation failed: {message}")


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    fixture = json.loads(text("spec/production/smx047-topology-gate-fixtures.json"))
    require(fixture["schema"] == "splashmx.smx047-production-topology-gate/1", "fixture schema")
    require(fixture["depends_on"] == ["SMX-046"], "dependency handoff")
    require(
        fixture["canonical_creation"]["path"] == "experiments/smx-017-network-harness/creation.json",
        "same retained SMX-017 canonical creation",
    )
    require(
        {profile["semantic_topology"] for profile in fixture["supported_profiles"]}
        == {"offline", "peer_hosted", "dedicated_authoritative"},
        "all Architecture-v1 production topology profiles",
    )
    require(
        {case["id"] for case in fixture["fault_campaign"]} == {f"NTG-{index:03d}" for index in range(1, 13)},
        "NTG-001..NTG-012 gate coverage",
    )
    require(
        set(fixture["protected_asset_invariant"]["fields"])
        == {
            "revision_digest",
            "source_digest",
            "source_identity",
            "source_metadata",
            "media_semantics",
            "provenance",
            "licence_attribution",
            "derivation_lineage",
        },
        "complete protected Asset field contract",
    )

    creation = json.loads(text("experiments/smx-017-network-harness/creation.json"))
    require(creation["creation_revision_id"] == "smx017-topology-equivalence-v1", "canonical creation revision identity")
    require(
        [thing["thing_id"] for thing in creation["things"]] == ["world", "avatar:alice", "door"],
        "retained stable Thing identities",
    )

    tests = text("tests/production/test_smx047.py")
    for anchor in (
        "test_same_canonical_creation_executes_all_topologies_without_rewrite",
        "test_loss_latency_duplicate_reorder_and_stale_epoch_have_typed_topology_independent_results",
        "test_browser_suspension_and_reconnect_rebind_only_transient_transport",
        "test_confirmed_peer_host_migration_and_host_loss_policy_hold_on_production_runtime",
        "test_nat_tls_ice_signalling_and_auth_failures_are_typed_runtime_outcomes",
        "test_hostile_ingress_bounds_fail_before_semantic_mutation",
        "test_relevance_unload_and_tombstone_remain_distinct_under_delayed_delivery",
        "test_protected_asset_revision_remains_indivisible_across_topologies_and_migration",
        "test_canonical_and_runtime_semantic_surfaces_do_not_leak_transport_engine_identity",
    ):
        require(anchor in tests, f"production regression anchor {anchor}")
    for anchor in ("RuntimeNetworkingService", "select_peer_path", "select_dedicated_path", "PROTECTED_REVISION"):
        require(anchor in tests, f"real production boundary usage {anchor}")

    browser_adapter = text("src/splashmx/runtime/web/network_transport.mjs")
    require("RTCPeerConnection" in browser_adapter, "real browser WebRTC boundary")
    require('this.#channel?.readyState === "open"' in browser_adapter, "peer DataChannel send path")
    require('this.#socket?.readyState === 1' in browser_adapter, "dedicated WSS send path")
    require("encodeSemanticEnvelope(envelope, this.#maxBytes)" in browser_adapter, "shared bounded semantic encoding")
    require("network.reconnect_required" in browser_adapter, "disconnected send typed failure")

    browser_harness = text("tests/production/smx047_browser_harness.mjs")
    for anchor in (
        "openPeer",
        "BrowserRuntimeTransport",
        "WebSocketServer",
        "restartIce",
        "dedicated-input",
        "trigger-malformed",
        "malformed_inbound_closed_with_policy_code",
        "semantic_roundtrip_ms",
    ):
        require(anchor in browser_harness, f"browser topology evidence anchor {anchor}")

    doc = text("docs/implementation/SMX-047-PRODUCTION-TOPOLOGY-GATE.md")
    for anchor in (
        "## Production topology equivalence",
        "## Hostile and degraded network campaign",
        "## Production browser adapter evidence and corrective repair",
        "## Protected source/audio/provenance boundary",
        "CI-local mechanism observations",
        "No unresolved topology-specific semantic contradiction",
    ):
        require(anchor in doc, f"implementation documentation anchor {anchor}")

    workflow = text(".github/workflows/smx047-production-topology-gate.yml")
    for anchor in (
        "tools/validate_smx017.py",
        "tools/validate_smx041.py",
        "tools/validate_smx045.py",
        "tools/validate_smx046.py",
        "tools/validate_smx047.py",
        "test_smx046.py",
        "test_smx047.py",
        "smx047_browser_harness.mjs",
        "playwright@1.55.0",
        "ws@8.18.3",
    ):
        require(anchor in workflow, f"CI gate anchor {anchor}")

    print("SMX-047 production topology-equivalence gate contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
