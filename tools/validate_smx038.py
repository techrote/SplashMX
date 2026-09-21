#!/usr/bin/env python3
"""Validate the durable SMX-038 production Godot runtime contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-038 contract drift: {needle!r} missing from {path}")


def main() -> None:
    require(
        "docs/implementation/SMX-038-GODOT-RUNTIME.md",
        "ThingId -> transient private binding entry -> zero / one / many Godot objects",
        "prepare-before-publish",
        "SemanticTurnBridge",
        "TrustedHostServiceBoundary.execute",
        "godot.required_feature_unavailable",
        "GRT-001..032",
        "source identity",
        "audio/media semantics",
        "provenance",
        "licence/attribution",
        "derivation lineage",
        "No SMX-038 evidence contradicts Architecture v1",
    )
    require(
        "src/splashmx/runtime/godot.py",
        "class BindingTable",
        "class SemanticTurnBridge",
        "build_host_service_adapters",
        "class MediaDerivativeCache",
        "godot.required_feature_unavailable",
        "godot.forbidden_transient_identity",
        "CAP_RENDER",
        "CAP_AUDIO",
        "CAP_INPUT",
        "CAP_PHYSICS",
    )
    require(
        "src/splashmx/runtime/godot_target/main.gd",
        "splashmx.smx038-godot-profile-evidence/1",
        "_materialize_all",
        "_recreate_binding",
        "_schedule_trace",
        "_exercise_adapters",
        "_exercise_derivative_cache",
        "semantic_only_zero_binding",
        "frame_measurement_class",
    )
    require(
        "tools/export_smx038_fixture.py",
        "CoreFixture.create",
        "serialize_world_save",
        "RuntimeProjection",
        "worldsave_fingerprint",
        "protected_asset_refs",
    )
    require(
        "tools/measure_smx038.py",
        "restore_world_save",
        "splashmx.smx038-semantic-performance-evidence/1",
        "worldsave_roundtrip_usec_median",
        "protected_asset_ref",
        "not a universal hardware performance SLO",
    )
    require(
        "tests/production/smx038_browser_harness.mjs",
        "SMX038_RESULT=",
        'evidence.profile === "browser"',
        "frame_samples",
        "protected_asset_refs",
        "boundary_results",
    )
    require(
        ".github/workflows/smx038-godot-runtime.yml",
        "barichello/godot-ci:4.7.2",
        "Godot 4.7.2 native headless materialization and exports",
        "Exported Godot web runtime in pinned Chromium",
        "--export-release \"Web\"",
        "--export-release \"Linux\"",
        "tools/measure_smx038.py",
    )

    corpus = json.loads(
        (ROOT / "spec/production/smx038-godot-runtime-fixtures.json").read_text(
            encoding="utf-8"
        )
    )
    if corpus.get("schema") != "splashmx.smx038-godot-runtime-fixtures/1":
        raise SystemExit("SMX-038 fixture contract drift")
    cases = corpus.get("cases", [])
    ids = [case.get("id") for case in cases]
    expected = [f"GRT-{index:03d}" for index in range(1, 33)]
    if ids != expected:
        raise SystemExit("SMX-038 GRT fixture sequence drift")
    if len({case.get("claim") for case in cases}) != len(cases):
        raise SystemExit("SMX-038 GRT fixture claims must be unique")
    expected_media = [
        "digest",
        "source_identity",
        "source_metadata",
        "audio_media_semantics",
        "provenance",
        "licence_attribution",
        "derivation_lineage",
    ]
    if corpus.get("protected_media_fields") != expected_media:
        raise SystemExit("SMX-038 protected-media field contract drift")

    modules = json.loads((ROOT / "src/MODULES.json").read_text(encoding="utf-8"))
    matches = [
        row for row in modules.get("modules", [])
        if row.get("module_id") == "runtime.godot"
    ]
    if len(matches) != 1:
        raise SystemExit("SMX-038 runtime.godot module ownership drift")
    module = matches[0]
    if module.get("owner_issue") != "SMX-038" or module.get("status") != "implemented":
        raise SystemExit("SMX-038 runtime.godot module is not implemented/owned correctly")
    if module.get("canonical_identity_inputs") != ["ThingId", "AssetId"]:
        raise SystemExit("SMX-038 canonical identity inputs drifted")
    required_forbidden = {
        "NodePath", "RID", "ResourceUID", "resource_path", "transport_peer_id",
        "connection_handle", "socket_id", "session_id", "process_handle",
    }
    if not required_forbidden <= set(module.get("forbidden_identity_classes", [])):
        raise SystemExit("SMX-038 forbidden durable identity classes drifted")

    print("SMX-038 production Godot runtime contract: OK")


if __name__ == "__main__":
    main()
