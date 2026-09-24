# SMX-051A — First functional visual-authoring vertical slice

**Parent:** SMX-051 / #76  
**Issue:** #111  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`

## Purpose

SMX-048 human evidence showed that the previous minimal browser shell was useful as a semantic/conformance harness but did not provide a meaningful creative workflow. SMX-051A is the first product-facing correction.

The slice establishes a real spatial Stage while preserving the existing canonical Thing model. It intentionally does **not** introduce a second browser document model or make DOM layout canonical.

## Canonical visual projection

A visual Thing may carry a `visual` object inside its existing canonical `authored_state`:

- `x`, `y`
- `width`, `height`
- `rotation`
- `shape` (`rectangle` or `ellipse`)
- `fill` (six-digit RGB colour)

`AuthoringSession.update_visual_state()` validates and publishes changes through `SetAuthoredState` and the existing semantic transaction boundary. Updating visual properties preserves all unrelated authored state and stable `ThingId`.

The browser's pointer-drag preview is transient editor feedback only. The semantic result is published once through `updateVisual` when the gesture completes.

## Author workflow

The ordinary Stage now provides:

- visible authored objects instead of list-only cards;
- click/checkbox selection;
- pointer drag movement;
- a visible resize handle;
- keyboard movement with Arrow keys;
- keyboard resize with Shift+Arrow;
- simple Properties for position, size, rotation, shape and fill;
- visual state that survives Save, Reload and process restart.

Existing Ports, Connections, Rules, Behaviours and Timeline controls remain available as advanced/legacy surfaces while their dedicated SMX-051 product slices are rebuilt.

## Architecture boundary

This slice remains below Architecture v1:

- visual state is ordinary SplashMX-authored state;
- Thing identity remains stable and path-independent;
- DOM nodes are disposable editor projections and never semantic identity;
- Godot remains the intended runtime/rendering substrate;
- this slice does not claim that browser DOM editing is the final runtime renderer;
- Play/Stop still requires a later SMX-051 slice to expose the production Godot-backed visual runtime.

No protected-media, capability, package, collaboration or networking invariant is changed.

## Evidence

The retained SMX-032 unit and real-Chromium campaigns now additionally exercise:

- canonical visual-state validation;
- preservation of unrelated authored state;
- visible Stage object creation;
- real pointer drag -> canonical position;
- real pointer resize -> canonical size;
- keyboard movement/resize;
- author-facing Properties;
- Save/Reload visual persistence;
- full server-process restart with the same project store.

## Residual product work

SMX-051A is deliberately not the complete FlashMX-class editor. Remaining parent #76 work includes:

- Timeline/keyframe UI and visible animation;
- reusable Library and visible instantiation;
- beginner Rule/Behaviour workflow;
- Connection authoring without manual internal identifiers;
- Godot-backed visual Play/Stop;
- author-facing Inspect/recovery;
- localization and final accessibility/device qualification;
- follow-up human verification after a functional workflow exists.
