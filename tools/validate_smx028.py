#!/usr/bin/env python3
"""Repository-native contract validator for SMX-028."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-028 validation failed: {message}")


def text(path: str) -> str:
    target = ROOT / path
    require(target.is_file(), f"missing {path}")
    return target.read_text(encoding="utf-8")


def main() -> None:
    architecture = text("docs/architecture/ARCHITECTURE-V1.md")
    require(
        "Failure leaves the previous implementation/state live" in architecture,
        "Architecture-v1 hot-replacement rollback authority missing",
    )
    require(
        "never silently guessed or discarded" in architecture,
        "Architecture-v1 pending-work authority missing",
    )
    require(
        "A stable `AssetId` selects one complete immutable protected revision" in architecture,
        "protected-media invariant missing from Architecture v1",
    )

    manifest = json.loads(text("src/MODULES.json"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("execution.hotswap" in modules, "execution.hotswap module missing")
    hot = modules["execution.hotswap"]
    require(hot["owner_issue"] == "SMX-028", "wrong hot-swap owner")
    require(hot["status"] == "implemented", "execution.hotswap is not marked implemented")
    require(set(hot["gate_ids"]) == {"GATE-02", "GATE-09"}, "hot-swap gate ownership drift")
    require(
        set(hot["canonical_identity_inputs"]) == {"ThingId", "BehaviourAttachmentId"},
        "hot-swap durable identity surface drift",
    )

    fixtures = json.loads(text("spec/production/smx028-hotswap-fixtures.json"))
    require(fixtures["schema"] == "splashmx.smx028-hotswap-fixtures/1", "fixture schema drift")
    require(fixtures["issue"] == "SMX-028", "fixture issue drift")
    ids = [row["id"] for row in fixtures["fixtures"]]
    require(ids == [f"HS-{index:03d}" for index in range(1, 25)], "HS-001..HS-024 fixture coverage drift")
    require(
        fixtures["protected_media_fields"]
        == [
            "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
            "provenance", "licence_attribution", "derivation_lineage",
        ],
        "protected-media field set drift",
    )
    for retained in fixtures["retained_research"]:
        require((ROOT / retained).is_file(), f"retained research evidence missing: {retained}")

    implementation = text("src/splashmx/execution/hotswap.py")
    for token in (
        "class ReplacementContract",
        "class PrivateStateMigration",
        "class PendingWorkMigration",
        "class HandlerMigration",
        "def principal_for_attachment",
        "def replace_behaviour",
        "capability_broker.resolve_requirements",
        "_validate_plain(result",
        "replacement.pending_work_undeclared",
        "replacement.pending_service_undeclared",
    ):
        require(token in implementation, f"production implementation missing {token!r}")
    require("capabilitytoken" not in implementation.lower(), "hot-swap source must not mint capability tokens")

    doc = text("docs/implementation/SMX-028-HOT-REPLACEMENT.md")
    for heading in (
        "## Production contract",
        "## Private-state migration",
        "## Pending work",
        "## Capability rebinding",
        "## Adversarial and boundary coverage",
        "## Protected source/audio/provenance boundary",
    ):
        require(heading in doc, f"implementation documentation missing {heading}")
    for protected in (
        "content digest", "source identity", "source metadata", "audio/media semantics",
        "provenance", "licence/attribution", "derivation lineage",
    ):
        require(protected in doc, f"implementation docs weakened protected field {protected!r}")

    tests = text("tests/production/test_smx028.py")
    test_methods = re.findall(r"^    def (test_[a-z0-9_]+)\(", tests, flags=re.MULTILINE)
    require(len(test_methods) >= 19, "fewer than 19 production adversarial/boundary tests")
    for concept in (
        "pending_timer_requires_explicit",
        "mapping_to_missing_target_handler",
        "pending_service_request_requires_explicit",
        "required_capability_is_rebound",
        "revoked_or_expired_capability",
        "authority_like_private_state",
        "attachment_rng_stream_is_preserved",
        "committed_emitted_work",
    ):
        require(any(concept in name for name in test_methods), f"missing test family {concept}")

    workflow = text(".github/workflows/smx028-hotswap.yml")
    for command in (
        "python tools/validate_smx004.py",
        "python tools/validate_smx008.py",
        "test_p1_hotswap.py",
        "python tools/validate_smx026.py",
        "python tools/validate_smx027.py",
        "python tools/validate_smx028.py",
        "test_smx028.py",
    ):
        require(command in workflow, f"dedicated CI missing retained gate {command}")

    print(f"SMX-028 contract valid: {len(ids)} fixtures, {len(test_methods)} production tests")


if __name__ == "__main__":
    main()
