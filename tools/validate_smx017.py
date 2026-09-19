#!/usr/bin/env python3
"""Validate the SMX-017 topology-equivalence research contract.

This validator is intentionally structural. Real Godot/browser execution is a
separate required workflow; this script prevents that workflow from silently
changing the canonical fixture, protected-media semantics or documented scope.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "smx-017-network-harness"
DOC = ROOT / "docs" / "research" / "SMX-017-NETWORK-HARNESS.md"
FIX = ROOT / "docs" / "research" / "SMX-017-NETWORK-HARNESS-FIXTURES.json"
DEC = ROOT / "docs" / "research" / "SMX-017-DECISION-EVIDENCE.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx017-real-topologies.yml"
TESTS = EXP / "test_model.py"
MAIN = EXP / "godot" / "main.gd"
BROWSER = EXP / "browser_harness.mjs"
EXPECTED_SHA = "dd5e7bb8b33ab447b4234fb8036453b248c5721e22b9f0e1c19cc57438e71580"


def fail(message: str) -> None:
    raise SystemExit(f"SMX-017 validation failed: {message}")


def require(path: pathlib.Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    doc = require(DOC)
    decision = require(DEC)
    workflow = require(WORKFLOW)
    tests = require(TESTS)
    gd = require(MAIN)
    browser = require(BROWSER)
    canonical_path = EXP / "creation.json"
    embedded_path = EXP / "godot" / "creation.json"
    canonical = canonical_path.read_bytes()
    embedded = embedded_path.read_bytes()
    if canonical != embedded:
        fail("top-level and Godot-embedded canonical fixtures are not byte-identical")
    actual_sha = hashlib.sha256(canonical).hexdigest()
    if actual_sha != EXPECTED_SHA:
        fail(f"canonical fixture SHA-256 changed: {actual_sha}")

    creation = json.loads(canonical)
    if creation.get("creation_revision_id") != "smx017-topology-equivalence-v1":
        fail("unexpected canonical creation revision")
    lower = canonical.decode("utf-8").lower()
    for forbidden in ("websocket", "webrtc", "enet", "peer_id", "nodepath", "resourceuid", '"rpc"'):
        if forbidden in lower:
            fail(f"canonical creation leaks transport/engine identity: {forbidden}")

    assets = creation.get("protected_assets", [])
    if len(assets) != 1:
        fail("fixture must contain exactly one protected-media revision")
    protected_fields = {
        "asset_id", "digest", "source_identity", "source_metadata",
        "audio_media_semantics", "provenance", "licence", "derivation",
    }
    if set(assets[0]) != protected_fields:
        fail("protected asset revision field set changed or became partial")

    fixtures = json.loads(require(FIX))
    top_ids = [x["id"] for x in fixtures.get("topology_invariants", [])]
    test_ids = [x["id"] for x in fixtures.get("boundary_tests", [])]
    if top_ids != [f"TOP-{i:03d}" for i in range(1, 21)]:
        fail("TOP-001..TOP-020 invariant set is incomplete or reordered")
    if test_ids != [f"TN-{i:03d}" for i in range(1, 29)]:
        fail("TN-001..TN-028 fixture set is incomplete or reordered")
    if fixtures.get("canonical_creation", {}).get("sha256") != EXPECTED_SHA:
        fail("fixture contract does not pin canonical SHA-256")

    discovered = sorted(set(re.findall(r"def test_(TN\d{3})_", tests)))
    expected_tests = [f"TN{i:03d}" for i in range(1, 29)]
    if discovered != expected_tests:
        fail(f"Python adversarial test IDs differ: {discovered}")

    for token in (
        "barichello/godot-ci:4.7.2", "GODOT_VERSION: 4.7.2",
        "node-version: '22.19.0'", "ws@8.18.3", "playwright@1.55.0",
        "browser_harness.mjs", "test_model.py", "smx017-integration-results.json",
    ):
        if token not in workflow:
            fail(f"real-topology workflow missing pinned contract token: {token}")

    # The one Godot runtime is policy-driven: peer/dedicated mode names belong
    # to orchestration/configuration rather than topology-specific canonical
    # branches. Require topology input/adapter here and all concrete executions
    # in the external orchestrator.
    for token in (EXPECTED_SHA, '"topology": "offline"', "cfg.topology", "WebSocketPeer.new"):
        if token not in gd:
            fail(f"single Godot runtime missing expected policy token: {token}")
    for token in ("runOffline()", "'peer'", "'dedicated'", "spawnDedicated", "chromium.launch"):
        if token not in browser:
            fail(f"real topology orchestrator missing execution mode token: {token}")

    required_doc_concepts = (
        "one canonical SplashMX creation",
        "peer-hosted-browser",
        "dedicated-authoritative",
        "cdp-frozen-fallback",
        "does not make that host trusted",
        "indivisible revision",
        "O-027",
        "not a production network stack",
    )
    doc_lower = doc.lower()
    for concept in required_doc_concepts:
        if concept.lower() not in doc_lower:
            fail(f"research document missing scope/contract concept: {concept}")

    for token in ("D-105", "D-110", "E-077", "E-081", "O-027"):
        if token not in decision:
            fail(f"decision/evidence record missing {token}")

    print(
        "SMX-017 contract valid: canonical SHA-256 pinned, 20 topology invariants, "
        "28 adversarial tests, protected-media bundle atomic, real runtime workflow pinned"
    )


if __name__ == "__main__":
    main()
