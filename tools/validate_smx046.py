#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-046 validation failed: {message}")


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    fixture = json.loads(text("spec/production/smx046-networking-fixtures.json"))
    require(fixture["schema"] == "splashmx.smx046-production-networking-fixtures/1", "fixture schema")
    source_ids = {entry["source_id"] for entry in fixture["source_fixture_ports"]}
    require(source_ids == {f"TN-{i:03d}" for i in range(1, 29)}, "TN-001..TN-028 production port coverage")
    security_ids = {entry["source_id"] for entry in fixture["deferred_security_ports"]}
    require(security_ids == {"AT-023", "AT-024"}, "AT-023/AT-024 production ingress ports")

    module = text("src/splashmx/runtime/network.py")
    for anchor in (
        "class RuntimeNetworkingService", "class ProductionTransportService", "class OpaqueJoinTicketAuthority",
        "def verify_pkce_s256", "def validate_signalling_envelope", "def migrate_peer_host",
        "def reconnect_baseline", "network.stale_epoch", "network.rate_limited", "network.queue_full",
        "FORBIDDEN_REMOTE_AUTHORITY_KEYS", "PROTECTED_ASSET_FIELDS",
    ):
        require(anchor in module, f"production module anchor {anchor}")

    browser = text("src/splashmx/runtime/web/network_transport.mjs")
    for anchor in ("RTCPeerConnection", "createDataChannel", "restartIce", "connectDedicatedWss", 'parsed.protocol !== "wss:"', "network.message_oversize"):
        require(anchor in browser, f"browser adapter anchor {anchor}")

    tests = text("tests/production/test_smx046.py")
    for index in range(1, 29):
        require(f"test_TN{index:03d}_" in tests, f"missing production TN-{index:03d} test")
    for anchor in ("test_at023_", "test_at024_", "test_pkce_s256", "test_protected_asset_revision_remains_indivisible"):
        require(anchor in tests, f"missing adversarial test {anchor}")

    doc = text("docs/implementation/SMX-046-PRODUCTION-NETWORKING.md")
    for anchor in (
        "## Production contract", "## Hostile production ingress", "## Authority, control and migration",
        "## Reconnect, baseline and lifecycle/relevance", "## Protected source/audio/provenance boundary",
        "AT-023", "AT-024", "SMX-047", "No Architecture-v1 contradiction",
    ):
        require(anchor in doc, f"implementation documentation anchor {anchor}")

    workflow = text(".github/workflows/smx046-production-networking.yml")
    for anchor in (
        "tools/validate_smx046.py", "test_smx046.py", "smx046_browser_harness.mjs",
        "tools/validate_smx010.py", "tools/validate_smx017.py", "tools/validate_smx041.py", "tools/validate_smx045.py",
    ):
        require(anchor in workflow, f"CI gate anchor {anchor}")

    manifest = json.loads(text("src/MODULES.json"))
    networking = next((entry for entry in manifest["modules"] if entry["module_id"] == "networking.runtime"), None)
    require(networking is not None, "networking.runtime module manifest entry")
    require(networking["owner_issue"] == "SMX-046", "networking.runtime owner")
    require(networking["status"] == "implemented", "networking.runtime status")
    require("GATE-05" in networking["gate_ids"], "networking.runtime GATE-05 ownership")
    require(set(("ThingId", "PrincipalId", "AuthorityEpoch")).issubset(networking["canonical_identity_inputs"]), "networking durable identity inputs")
    require("transport_peer_id" in networking["forbidden_identity_classes"] and "session_id" in networking["forbidden_identity_classes"], "transient identity guardrails")

    print("SMX-046 production networking contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
