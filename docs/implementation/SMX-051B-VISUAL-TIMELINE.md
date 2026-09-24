# SMX-051B — Visible Timeline and editor animation preview

**Parent:** SMX-051 / #76  
**Issue:** #113  
**Follows:** SMX-051A / #111 / PR #112

## Purpose

SMX-051B makes authored animation visible and understandable without inventing a browser execution runtime.

A selected visual Thing can receive an animation track using ordinary property names, see the track and keyframes in a Timeline, scrub a playhead and run a short editor preview.

## Canonical boundary

Timeline records continue to use the existing canonical `timeline_tracks` projection written through `AuthoringSession.add_timeline_track()` and `SetAuthoredState`.

The ordinary visual UI currently exposes these authored loci:

- `visual.x` — Horizontal position
- `visual.y` — Vertical position
- `visual.rotation` — Rotation
- `visual.width` — Width
- `visual.height` — Height

The selected `ThingId`, track record and keyframes are canonical authored state.

## Transient preview

The editor interpolates numeric keyframes only to display a transient Stage projection at the current playhead.

Scrubbing and Preview:

- do not call `updateVisual`;
- do not advance `ProjectRevisionId`;
- do not mutate the Thing's authored base `visual` state;
- do not create runtime/world state;
- reset to the authored base presentation when Preview ends or Reset preview is used.

This deliberately remains an authoring visualization. It is **not** called Play and does not claim to execute the production runtime.

## Product workflow

The Timeline surface provides:

- property choices in author language rather than a raw property identifier;
- start/end values and bounded duration;
- visible track rows;
- visible keyframe markers;
- a keyboard-operable range playhead;
- deterministic linear interpolation for the current two-keyframe visual authoring slice;
- a bounded Preview animation that returns to authored state.

## Evidence

The retained SMX-032 production unit/browser campaign adds coverage for:

- canonical `visual.x` Timeline state without changing base visual state;
- ordinary UI track creation;
- visible Timeline row/keyframes;
- midpoint scrub producing the expected visual Stage position;
- unchanged canonical revision/base visual state during scrub;
- animated Preview followed by restoration of authored Stage state;
- Timeline persistence through Save/Reload and full server restart.

## Explicit residual

This is not the Godot-backed Play implementation.

The next SMX-051 slice must adapt the production SMX-037/038 Godot target from its existing generic/evidence input into the ordinary editor Play path, so Play visibly realizes the same canonical visual and Timeline semantics rather than executing a JavaScript shadow runtime.

Architecture v1 is unchanged.
