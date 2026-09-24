"""Bounded canonical -> Godot editor Play projection.

This module projects only author-visible visual/Timeline semantics needed by the
SMX-051C Godot Play slice.  Godot/runtime/browser handles never enter the
projection and the projection never becomes canonical state.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from splashmx.canonical.serialization import CanonicalProjectRevision
from splashmx.runtime.godot import validate_target_value

EDITOR_GODOT_PLAY_CONTRACT = "splashmx.editor-godot-play/1"
VISUAL_PROPERTIES = frozenset({
    "visual.x",
    "visual.y",
    "visual.rotation",
    "visual.width",
    "visual.height",
})
_MAX_THINGS = 10_000
_MAX_TRACKS = 4_096
_MAX_KEYFRAMES = 4_096


class EditorGodotPlayError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise EditorGodotPlayError(code, message)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("godot_play.invalid_visual", f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        _fail("godot_play.invalid_visual", f"{label} must be finite")
    return result


def _visual(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        _fail("godot_play.invalid_visual", "visual authored state must be an object")
    required = {"x", "y", "width", "height", "rotation", "shape", "fill"}
    if set(value) != required:
        _fail("godot_play.invalid_visual", "visual authored state fields are invalid")
    shape = value["shape"]
    fill = value["fill"]
    if shape not in {"rectangle", "ellipse"}:
        _fail("godot_play.invalid_visual", "unsupported visual shape")
    if (
        not isinstance(fill, str)
        or len(fill) != 7
        or not fill.startswith("#")
        or any(ch not in "0123456789abcdefABCDEF" for ch in fill[1:])
    ):
        _fail("godot_play.invalid_visual", "visual fill must be six-digit RGB")
    width = _number(value["width"], "width")
    height = _number(value["height"], "height")
    if width < 12 or height < 12:
        _fail("godot_play.invalid_visual", "visual size is below the supported minimum")
    return {
        "x": _number(value["x"], "x"),
        "y": _number(value["y"], "y"),
        "width": width,
        "height": height,
        "rotation": _number(value["rotation"], "rotation"),
        "shape": shape,
        "fill": fill.lower(),
    }


def _tracks(value: Any, thing_id: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or len(value) > _MAX_TRACKS:
        _fail("godot_play.invalid_timeline", "Timeline track collection is invalid or too large")
    rows: list[dict[str, Any]] = []
    for track in value:
        if not isinstance(track, Mapping):
            _fail("godot_play.invalid_timeline", "Timeline track must be an object")
        if str(track.get("target_thing_id", "")) != thing_id:
            _fail("godot_play.invalid_timeline", "Timeline target differs from containing Thing")
        prop = track.get("property")
        if prop not in VISUAL_PROPERTIES:
            continue
        keyframes = track.get("keyframes")
        if not isinstance(keyframes, (list, tuple)) or not keyframes or len(keyframes) > _MAX_KEYFRAMES:
            _fail("godot_play.invalid_timeline", "visual Timeline keyframes are invalid or too large")
        clean: list[dict[str, float]] = []
        prior_tick = -1.0
        for frame in keyframes:
            if not isinstance(frame, Mapping):
                _fail("godot_play.invalid_timeline", "Timeline keyframe must be an object")
            tick = _number(frame.get("tick"), "Timeline tick")
            value_number = _number(frame.get("value"), "Timeline value")
            if tick < 0 or tick < prior_tick:
                _fail("godot_play.invalid_timeline", "Timeline ticks must be non-negative and ordered")
            prior_tick = tick
            clean.append({"tick": tick, "value": value_number})
        rows.append({"property": prop, "keyframes": clean})
    return rows


def build_editor_godot_play_projection(project: CanonicalProjectRevision) -> dict[str, Any]:
    if not isinstance(project, CanonicalProjectRevision):
        _fail("godot_play.invalid_project", "Godot Play requires a canonical project revision")
    things = []
    for thing_id, thing in sorted(project.document.things.items(), key=lambda row: str(row[0])):
        if thing.tombstoned:
            continue
        visual = _visual(thing.authored_state.get("visual"))
        if visual is None:
            continue
        identity = str(thing_id)
        things.append({
            "thing_id": identity,
            "label": str(thing.label),
            "visual": visual,
            "timeline_tracks": _tracks(thing.authored_state.get("timeline_tracks"), identity),
        })
        if len(things) > _MAX_THINGS:
            _fail("godot_play.resource_limit", "Godot Play visual Thing limit exceeded")

    projection = {
        "contract": EDITOR_GODOT_PLAY_CONTRACT,
        "project_id": str(project.document.project_id),
        "project_revision_id": str(project.document.project_revision_id),
        "ticks_per_second": 60,
        "required_features": ["render_2d"],
        "things": things,
    }
    # Reuse the production target-value guard so forbidden target/runtime identity
    # classes cannot be smuggled through this editor-specific projection.
    try:
        validate_target_value(projection, where="editor Godot Play projection")
    except ValueError as exc:
        _fail(getattr(exc, "code", "godot_play.invalid_projection"), str(exc))
    return projection


__all__ = [
    "EDITOR_GODOT_PLAY_CONTRACT",
    "EditorGodotPlayError",
    "VISUAL_PROPERTIES",
    "build_editor_godot_play_projection",
]
