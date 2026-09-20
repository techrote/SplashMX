#!/usr/bin/env python3
"""Repository-native contract validator for SMX-029."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-029 validation failed: {message}")


def text(path: str) -> str:
    target = ROOT / path
    require(target.is_file(), f"missing {path}")
    return target.read_text(encoding="utf-8")


def main() -> None:
    architecture = text("docs/architecture/ARCHITECTURE-V1.md")
    for phrase in (
        "WorldSave",
        "known-unloaded",
        "A stable `AssetId` selects one complete immutable protected revision",
    ):
        require(phrase in architecture, f"Architecture-v1 authority missing {phrase!r}")

    manifest = json.loads(text("src/MODULES.json"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("runtime.lifecycle" in modules, "runtime.lifecycle module missing")
    lifecycle = modules["runtime.lifecycle"]
    require(lifecycle["owner_issue"] == "SMX-029", "wrong lifecycle module owner")
    require(lifecycle["status"] == "implemented", "runtime.lifecycle is not marked implemented")
    require(
        set(lifecycle["gate_ids"]) == {"GATE-02", "GATE-09"},
        "lifecycle gate ownership drift",
    )
    require(
        set(lifecycle["canonical_identity_inputs"]) == {"ThingId", "WorldSaveId"},
        "lifecycle identity surface drift",
    )

    fixtures = json.loads(text("spec/production/smx029-lifecycle-fixtures.json"))
    require(
        fixtures["schema"] == "splashmx.smx029-lifecycle-fixtures/1",
        "fixture schema drift",
    )
    require(fixtures["issue"] == "SMX-029", "fixture issue drift")
    ids = [row["id"] for row in fixtures["fixtures"]]
    require(
        ids == [f"WS-{index:03d}" for index in range(1, 29)],
        "WS-001..WS-028 fixture coverage drift",
    )
    require(
        fixtures["retained_lifecycle_invariants"]
        == [f"LIF-{index:03d}" for index in range(1, 19)],
        "LIF-001..LIF-018 retained lifecycle evidence drift",
    )
    require(
        fixtures["protected_media_fields"]
        == [
            "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
            "provenance", "licence_attribution", "derivation_lineage",
        ],
        "protected-media field set drift",
    )
    for retained in fixtures["retained_research"]:
        require((ROOT / retained).is_file(), f"retained evidence missing: {retained}")

    implementation = text("src/splashmx/runtime/lifecycle.py")
    for token in (
        "class WorldRuntime",
        "class WorldSaveSnapshot",
        "class SQLiteWorldSaveStore",
        "def restore_world_save",
        "def serialize_world_save",
        "worldsave.forbidden_transient_state",
        "restore_policy: str = \"reauthorize\"",
        "capability_broker.resolve_requirements",
        "PRAGMA synchronous=FULL",
        "world_revisions",
        "world_heads",
    ):
        require(token in implementation, f"production implementation missing {token!r}")

    doc = text("docs/implementation/SMX-029-LIFECYCLE-WORLDSAVE.md")
    for heading in (
        "## Production contract",
        "## Lifecycle and reference states",
        "## WorldSave plane",
        "## Pending work and side effects",
        "## Fresh-process restore and capability rebinding",
        "## Crash-safe persistence",
        "## Adversarial and boundary coverage",
        "## Protected source/audio/provenance boundary",
    ):
        require(heading in doc, f"implementation documentation missing {heading}")
    for protected in (
        "content digest", "source identity", "source metadata", "audio/media semantics",
        "provenance", "licence/attribution", "derivation lineage",
    ):
        require(protected in doc, f"implementation docs weakened protected field {protected!r}")
    for phrase in (
        "authored-project bytes",
        "never places that descriptor back into the executable host-service request outbox",
        "No grant ID or capability token occurs in WorldSave bytes",
        "does not embed, rewrite, field-mix or partially replace that protected revision",
    ):
        require(phrase in doc, f"WorldSave boundary documentation missing {phrase!r}")

    tests = text("tests/production/test_smx029.py")
    test_methods = re.findall(r"^    def (test_[a-z0-9_]+)\(", tests, flags=re.MULTILINE)
    require(len(test_methods) >= 25, "fewer than 25 production adversarial/boundary tests")
    for concept in (
        "snapshot_is_non_mutating",
        "authored_project_and_runtime_world_state",
        "tombstoned_unknown_and_known_unloaded",
        "timer_and_queue_order_restore",
        "external_service_wait_is_persisted_but_never_implicitly_reissued",
        "transient_session_or_capability_handles",
        "required_capability_is_rebound",
        "revoked_capability",
        "store_crash_boundaries",
        "failed_restore_leaves_committed_worldsave_head",
        "fresh_process_restore_has_no_surviving_python_runtime_objects",
        "does_not_own_protected_asset_revision_bundles",
    ):
        require(any(concept in name for name in test_methods), f"missing test family {concept}")

    workflow = text(".github/workflows/smx029-lifecycle-worldsave.yml")
    for command in (
        "python tools/validate_smx007.py",
        "python tools/validate_smx025.py",
        "python tools/validate_smx027.py",
        "python tools/validate_smx028.py",
        "python tools/validate_smx029.py",
        "test_smx029.py",
    ):
        require(command in workflow, f"dedicated CI missing retained gate {command}")

    registry = json.loads(text("spec/production/conformance-registry.json"))
    gates = {row["id"]: row for row in registry["gate_entries"]}
    for gate_id in ("GATE-02", "GATE-09"):
        gate = gates[gate_id]
        require(
            "docs/implementation/SMX-029-LIFECYCLE-WORLDSAVE.md"
            in {row["path"] for row in gate["evidence"]},
            f"{gate_id} missing SMX-029 production evidence",
        )
        require("tools/validate_smx029.py" in gate["current_tests"], f"{gate_id} missing validator")
        require("tests/production/test_smx029.py" in gate["current_tests"], f"{gate_id} missing tests")
        require("SMX-029" not in gate["future_issue_codes"], f"{gate_id} still lists SMX-029 as future")

    print(f"SMX-029 contract valid: {len(ids)} fixtures, {len(test_methods)} production tests")


if __name__ == "__main__":
    main()
