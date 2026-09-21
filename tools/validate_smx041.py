#!/usr/bin/env python3
"""Validate durable SMX-041 production hostile-content security gate."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-041 contract drift: {needle!r} missing from {path}")


def main() -> None:
    historical = json.loads(
        (ROOT / "docs/research/SMX-016-SECURITY-FIXTURES.json").read_text(encoding="utf-8")
    )
    gate = json.loads(
        (ROOT / "spec/production/smx041-security-gate-fixtures.json").read_text(encoding="utf-8")
    )
    if gate.get("contract") != "splashmx.smx041-untrusted-content-security-gate/1":
        raise SystemExit("SMX-041 fixture contract drift")
    if gate.get("architecture_gate") != "GATE-03":
        raise SystemExit("SMX-041 must remain bound to Architecture-v1 GATE-03")

    historical_ids = [row["id"] for row in historical["fixtures"]]
    gate_ids = [row["id"] for row in gate["coverage"]]
    if gate_ids != historical_ids or gate_ids != [f"AT-{i:03d}" for i in range(1, 29)]:
        raise SystemExit("SMX-041 must account for every AT-001..AT-028 row in order")

    historical_adv = set(historical["security_invariants"])
    covered_adv = {
        item
        for row in gate["coverage"]
        for item in row.get("attack_classes", [])
    }
    if covered_adv != historical_adv:
        missing = sorted(historical_adv - covered_adv)
        extra = sorted(covered_adv - historical_adv)
        raise SystemExit(f"SMX-041 ADV coverage drift; missing={missing} extra={extra}")

    deferred = [row for row in gate["coverage"] if row.get("status") != "pass"]
    if [row["id"] for row in deferred] != ["AT-023", "AT-024"]:
        raise SystemExit("Only not-yet-existing runtime-network ingress may be deferred at SMX-041")
    if any(row.get("status") != "deferred-no-runtime-network-surface" for row in deferred):
        raise SystemExit("SMX-041 network deferral must state the absent production surface precisely")
    if any(row.get("production_evidence") != ["SMX-046", "SMX-047"] for row in deferred):
        raise SystemExit("SMX-041 deferred network rows must route to SMX-046/047")

    campaigns = gate.get("malformed_campaigns", {})
    expected_campaigns = {
        "canonical_cbor", "spb1", "behaviour_ir", "media_request", "publication_closure"
    }
    if set(campaigns) != expected_campaigns or any(
        row.get("status") != "pass" for row in campaigns.values()
    ):
        raise SystemExit("SMX-041 malformed campaign record is incomplete")

    target_rows = gate.get("target_decisions", [])
    targets = {row.get("target"): row for row in target_rows}
    expected_targets = {
        "web", "linux-native", "linux-headless",
        "windows-native", "macos-native", "mobile",
    }
    if set(targets) != expected_targets:
        raise SystemExit("SMX-041 target release-decision matrix is incomplete")
    if targets["web"]["decision"] != "release-blocked-public-untrusted-decode":
        raise SystemExit("SMX-041 must not overclaim the current web decoder boundary")
    if targets["linux-native"]["decision"] != "conditionally-eligible":
        raise SystemExit("Linux native eligibility must remain conditional on the runtime sandbox probe")
    if targets["linux-headless"]["decision"] != "conditionally-eligible":
        raise SystemExit("Linux headless eligibility must remain conditional on the runtime sandbox probe")
    for target in ("windows-native", "macos-native", "mobile"):
        if targets[target]["decision"] != "release-blocked-public-untrusted-decode":
            raise SystemExit(f"{target} cannot claim public-untrusted decode without a production isolator")

    if gate.get("downstream_security_prerequisites") != [
        "SMX-043", "SMX-045", "SMX-046", "SMX-050"
    ]:
        raise SystemExit("SMX-041 downstream security-gate routing drift")

    require(
        "tests/production/test_smx041.py",
        "test_canonical_cbor_mutation_campaign_is_typed",
        "test_spb1_mutation_campaign_never_escapes_typed_boundary",
        "test_ir_host_opcode_and_authority_campaign_fails_closed",
        "test_media_authority_mutations_never_invoke_worker",
        "test_expiry_after_admission_wins_at_final_real_adapter_boundary",
        "test_full_historical_attack_matrix_is_accounted_for",
        "test_current_target_release_decisions_are_fail_closed",
    )
    require(
        "docs/implementation/SMX-041-UNTRUSTED-CONTENT-SECURITY-GATE.md",
        "AT-001..AT-028",
        "AT-023 / AT-024",
        "release-blocked",
        "conditionally eligible",
        "SMX-043",
        "SMX-045",
        "SMX-046",
        "SMX-050",
        "protected Asset",
        "No Architecture-v1 amendment",
    )
    require(
        ".github/workflows/smx041-untrusted-content-gate.yml",
        "python tools/validate_smx041.py",
        "tests.production.test_smx024",
        "tests.production.test_smx026",
        "tests.production.test_smx027",
        "tests.production.test_smx035_adversarial",
        "tests.production.test_smx036_adversarial",
        "tests.production.test_smx038",
        "tests.production.test_smx040",
        "tests.production.test_smx041",
        "smx040_web_worker_test.mjs",
    )
    print("SMX-041 production untrusted-content security gate: OK")


if __name__ == "__main__":
    main()
