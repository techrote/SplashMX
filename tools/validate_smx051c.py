#!/usr/bin/env python3
"""Validate the SMX-051C editor -> production Godot Play integration contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-051C contract drift: {needle!r} missing from {path}")


def main() -> None:
    require(
        "docs/implementation/SMX-051C-GODOT-PLAY.md",
        "splashmx.editor-godot-play/1",
        "same exported generic Godot runtime",
        "no DOM Play fallback",
        "ThingId",
        "Timeline",
        "authored state",
        "Architecture v1 is unchanged",
    )
    require(
        "src/splashmx/editor/godot_play.py",
        'EDITOR_GODOT_PLAY_CONTRACT = "splashmx.editor-godot-play/1"',
        "build_editor_godot_play_projection",
        "validate_target_value",
        "visual.x",
        "visual.rotation",
    )
    require(
        "src/splashmx/editor/browser_server.py",
        "/api/godot-play-projection",
        "/godot/index.html?editor_live=1",
        "--godot-web-root",
        "relative_to(root)",
        "frame-src 'self'",
    )
    require(
        "src/splashmx/editor/web/app.js",
        "Godot Play runtime is not available",
        "Playing through the Godot runtime.",
        "renderGodotPlayer",
        "startPlay",
    )
    require(
        "src/splashmx/runtime/godot_target/main.gd",
        "SMX051C_PLAY_READY=",
        "SMX051C_SAMPLE=",
        "splashmx.editor-godot-play/1",
        "_ready_editor_live",
        "_process_editor_live",
        "Polygon2D.new()",
    )
    require(
        "tests/production/smx051c_editor_godot_harness.mjs",
        "real_godot_canvas_visible",
        "stable_thing_identity_reaches_godot",
        "godot_timeline_start_mid_end",
        "godot_play_does_not_mutate_authored_state",
        "stop_restores_authored_editor",
    )
    require(
        ".github/workflows/smx038-godot-runtime.yml",
        "Serve production editor with the exact exported Godot runtime",
        "Exercise editor to real Godot Play path in Chromium",
        "tests/production/test_smx051c.py",
        "tests/production/smx051c_editor_godot_harness.mjs",
    )
    print("SMX-051C editor Godot Play contract: OK")


if __name__ == "__main__":
    main()
