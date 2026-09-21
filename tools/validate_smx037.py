#!/usr/bin/env python3
"""Validate the durable SMX-037 selection handoff and regression surface."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-037 contract drift: {needle!r} missing from {path}")


def main() -> None:
    require(
        "docs/research/SMX-037-GODOT-BINDING-SELECTION.md",
        "facet_sparse",
        "centralized SplashMX turn bridge",
        "ThingId -> transient private binding entry -> zero/one/many Godot Objects",
        "protected Asset revision",
        "SMX-038",
        "No Architecture-v1 semantic amendment was required",
    )
    require(
        "experiments/smx-037-godot-binding-spike/main.gd",
        'const CANDIDATES = ["node_per_thing", "scene_subtree", "facet_sparse"]',
        "forbidden_handle_rejected",
        "scheduler_reorder_equivalent",
        "binding_recreation_preserves_thing_id",
        "protected_asset_ref_preserved",
    )
    require(
        "tools/export_smx037_fixture.py",
        "build_project",
        "FORBIDDEN_HANDLE_FIELDS",
        "protected_asset_refs",
        "target_profiles",
    )
    require(
        "tools/measure_smx037.py",
        "splashmx.benchmark-evidence/1",
        "headless_process_startup_to_exit_seconds",
        '"selected_candidate"',
    )
    require(
        ".github/workflows/smx037-godot-binding.yml",
        "barichello/godot-ci:4.7.2",
        "Godot 4.7.2 realization + scheduler evidence",
        "--export-release \"Web\"",
        "--export-release \"Linux\"",
    )

    corpus = json.loads((ROOT / "spec/production/smx037-godot-binding-fixtures.json").read_text(encoding="utf-8"))
    if corpus.get("contract") != "splashmx.smx037-godot-binding-fixtures/1":
        raise SystemExit("SMX-037 fixture contract drift")
    cases = corpus.get("cases", [])
    ids = [case.get("id") for case in cases]
    expected = [f"GBS-{index:03d}" for index in range(1, 25)]
    if ids != expected:
        raise SystemExit("SMX-037 GBS fixture sequence drift")
    if len({case.get("claim") for case in cases}) != len(cases):
        raise SystemExit("SMX-037 GBS fixture claims must be unique")

    print("SMX-037 selection contract: OK")


if __name__ == "__main__":
    main()
