#!/usr/bin/env python3
"""Repository-native contract validator for SMX-031."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-031 validation failed: {message}")


def text(path: str) -> str:
    target = ROOT / path
    require(target.is_file(), f"missing {path}")
    return target.read_text(encoding="utf-8")


def main() -> None:
    architecture = text("docs/architecture/IMPLEMENTATION-ROADMAP-V1.md")
    for phrase in (
        "fresh-process restore of representative graphs without surviving Godot objects",
        "inventory/reference-to-unloaded-target case",
        "cache eviction remains non-semantic",
        "minimal local create → play → stop → save/reload flow stays green",
    ):
        require(phrase in architecture, f"Phase-3 authority missing {phrase!r}")

    programme = text("docs/implementation/PRODUCTION-PROGRAMME-V1.md")
    require("SMX-031" in programme and "Production-core vertical conformance gate" in programme,
            "production programme lost SMX-031 gate")
    require("#53 + #54 + #55 ─> #56 production-core gate" in programme,
            "production-core dependency edge drift")

    manifest = json.loads(text("src/MODULES.json"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    required_modules = {
        "canonical.core", "canonical.serialization", "storage.local", "execution.ir",
        "security.capabilities", "execution.hotswap", "runtime.lifecycle", "runtime.streaming",
    }
    require(required_modules <= set(modules), "production-core module set is incomplete")
    for module_id in required_modules:
        require(modules[module_id]["status"] == "implemented", f"{module_id} is not implemented")
    require("SMX-031" not in {row["owner_issue"] for row in manifest["modules"]},
            "SMX-031 must remain an integration gate, not invent a second semantic module")

    fixtures = json.loads(text("spec/production/smx031-core-gate-fixtures.json"))
    require(fixtures["schema"] == "splashmx.smx031-core-gate-fixtures/1", "fixture schema drift")
    require(fixtures["issue"] == "SMX-031", "fixture issue drift")
    ids = [row["id"] for row in fixtures["fixtures"]]
    require(ids == [f"PCG-{index:03d}" for index in range(1, 25)], "PCG-001..PCG-024 coverage drift")
    require(set(fixtures["production_modules"]) == required_modules, "fixture production module set drift")
    require(
        fixtures["protected_media_fields"] == [
            "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
            "provenance", "licence_attribution", "derivation_lineage",
        ],
        "protected-media field set drift",
    )

    harness = text("tests/production/smx031_harness.py")
    for token in (
        "apply_transaction(", "PromoteGroup(", "InstantiateDefinition(", "AddConnection(",
        "compile_rule(", "WorldRuntime.create(", "SQLiteProjectStore(", "serialize_world_save(",
        "restore_world_save(", "StreamingRuntime(", "replace_behaviour(", "CapabilityBroker()",
        "ProtectedAssetRevision.create(",
    ):
        require(token in harness, f"integration harness missing production boundary {token!r}")
    for forbidden in (
        "experiments/smx-", "smx019", "browser_vertical_slice", "ProofModel", "FakeRuntime",
    ):
        require(forbidden not in harness, f"integration harness depends on proof/mock substrate {forbidden!r}")

    tests = text("tests/production/test_smx031.py")
    test_methods = re.findall(r"^    def (test_[a-z0-9_]+)\(", tests, flags=re.MULTILINE)
    require(len(test_methods) >= 18, "fewer than 18 integrated adversarial/boundary tests")
    for concept in (
        "complete_create_reuse_behave_connect_play_stop_save_reload_vertical",
        "fresh_process_restore",
        "durable_reference_to_unloaded_thing",
        "missing_exact_stream_dependency",
        "protected_asset_competing_complete_revision",
        "hot_replacement",
        "instruction_budget_fault",
        "required_capability_denial",
        "failed_canonical_transaction",
        "same_project_revision_cannot_be_rebound",
        "cache_eviction",
        "tombstoned_thing",
    ):
        require(any(concept in name for name in test_methods), f"missing integrated test family {concept}")

    doc = text("docs/implementation/SMX-031-PRODUCTION-CORE-GATE.md")
    for heading in (
        "## Production contract",
        "## Vertical flow",
        "## Lifecycle and exact streaming",
        "## Failure and rollback seams",
        "## Capability and resource boundaries",
        "## Protected source/audio/provenance boundary",
        "## Benchmark evidence",
        "## Downstream handoff",
    ):
        require(heading in doc, f"implementation documentation missing {heading}")
    for protected in (
        "content/source digest", "source identity", "source metadata", "audio/media semantics",
        "provenance", "licence/attribution", "derivation lineage",
    ):
        require(protected in doc, f"implementation docs weakened protected field {protected!r}")
    lower_doc = doc.lower()
    for phrase in (
        "does not introduce another runtime, semantic kernel, or proof-model substrate",
        "no code from the pre-v1 python research models",
        "cache eviction remains non-semantic",
        "there is no ambient authority",
        "architecture v1 is unchanged",
    ):
        require(phrase in lower_doc, f"integration boundary documentation missing {phrase!r}")

    benchmark_schema = json.loads(text("spec/production/benchmark-evidence.schema.json"))
    require(benchmark_schema["properties"]["contract"]["const"] == "splashmx.benchmark-evidence/1",
            "SMX-021 benchmark evidence contract drift")
    measure = text("tools/measure_smx031.py")
    for token in (
        '"contract": "splashmx.benchmark-evidence/1"',
        '"target_profile": "headless"',
        '"vertical_flow_seconds"',
        '"project_store_bytes"',
        '"worldsave_bytes"',
        "complete_vertical_flow",
    ):
        require(token in measure, f"benchmark evidence generator missing {token!r}")

    workflow = text(".github/workflows/smx031-production-core-gate.yml")
    for command in (
        "python tools/validate_smx023.py",
        "python tools/validate_smx024.py",
        "python tools/validate_smx025.py",
        "python tools/validate_smx026.py",
        "python tools/validate_smx027.py",
        "python tools/validate_smx028.py",
        "python tools/validate_smx029.py",
        "python tools/validate_smx030.py",
        "python tools/validate_smx031.py",
        "test_smx031.py",
        "python tools/measure_smx031.py",
        "actions/upload-artifact@v7",
    ):
        require(command in workflow, f"dedicated CI missing retained gate {command}")

    registry = json.loads(text("spec/production/conformance-registry.json"))
    gates = {row["id"]: row for row in registry["gate_entries"]}
    evidence_path = "docs/implementation/SMX-031-PRODUCTION-CORE-GATE.md"
    for gate_id in ("GATE-01", "GATE-02", "GATE-09"):
        gate = gates[gate_id]
        require(evidence_path in {row["path"] for row in gate["evidence"]},
                f"{gate_id} missing SMX-031 integration evidence")
        require("tools/validate_smx031.py" in gate["current_tests"], f"{gate_id} missing SMX-031 validator")
        require("tests/production/test_smx031.py" in gate["current_tests"], f"{gate_id} missing SMX-031 tests")
        require("SMX-031" not in gate["future_issue_codes"], f"{gate_id} still lists SMX-031 as future")

    regressions = {row["id"]: row for row in registry["non_droppable_regressions"]}
    media = regressions["XREG-PROTECTED-MEDIA"]
    require(evidence_path in media["evidence_paths"], "protected-media regression omits SMX-031 evidence")

    print(f"SMX-031 contract valid: {len(ids)} fixtures, {len(test_methods)} integrated tests")


if __name__ == "__main__":
    main()
