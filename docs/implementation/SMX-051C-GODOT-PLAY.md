# SMX-051C — Editor Play through the production Godot Web runtime

**Parent:** SMX-051 / #76  
**Issue:** #115  
**Godot baseline:** 4.7.2  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`

## Purpose

SMX-051C closes the product gap exposed by SMX-048 where **Play** changed browser/editor state but produced no visible creative output.

Ordinary product Play now requires the existing production Godot Web runtime. There is **no DOM Play fallback**. If the qualified Godot runtime is unavailable, the editor stays in Edit mode and reports that condition explicitly.

The existing SMX-051B browser Timeline Preview remains a transient authoring aid and is deliberately separate from Play.

## Canonical-to-target projection

The editor exposes a bounded read-only Play projection with contract:

`splashmx.editor-godot-play/1`

For the current slice it contains only:

- canonical ProjectId and ProjectRevisionId;
- stable ThingId and author label;
- validated visual authored state: position, size, rotation, shape and fill;
- supported visual Timeline tracks and numeric keyframes;
- target feature requirement and ticks-per-second.

The projection reuses the SMX-038 target-value guard. Forbidden engine, browser, process, transport or session identity fields fail before Godot receives the projection.

The projection is available only while the semantic browser runtime is in Play mode. It is not saved as another document and cannot become canonical authority.

## Same exported generic Godot runtime

SMX-051C extends the **same exported generic Godot runtime** established by SMX-038. It does not generate project-specific GDScript or a per-creation Godot build.

The existing SMX-038 fixture/evidence mode remains unchanged when the runtime is launched normally. A Web launch carrying `editor_live=1` enters the editor-live presentation path:

1. obtain the same-origin bounded Play projection;
2. validate its contract and reject forbidden target/runtime identity;
3. create private Godot presentation bindings keyed by stable ThingId;
4. realize visual Things with `Node2D` + `Polygon2D`;
5. apply authored visual state;
6. evaluate supported Timeline tracks against engine frame time;
7. emit bounded semantic evidence containing only stable identity and author-visible visual values.

Godot Node/object identity remains private and disposable.

## Editor integration

`browser_server.py` may be launched with:

`--godot-web-root <qualified exported Web runtime directory>`

The path is process-local configuration only. The editor:

- advertises whether the runtime is available;
- serves its files under a same-origin `/godot/` path with traversal containment;
- exposes the read-only Play projection at `/api/godot-play-projection`;
- embeds the Godot Web player only after product Play begins.

When Play is active, the authored Stage is replaced by the embedded Godot player surface. Stop destroys/hides that browser runtime view and returns to the authored Stage. Runtime presentation does not write visual or Timeline results back to authored state.

When no qualified Web runtime is supplied, Play fails explicitly and remains in Edit mode.

## Timeline execution

For SMX-051C the generic Godot target executes the visual properties introduced by SMX-051A/B:

- `visual.x`
- `visual.y`
- `visual.rotation`
- `visual.width`
- `visual.height`

Numeric keyframes use deterministic linear interpolation within the authored track. The real-target evidence samples start, midpoint and end values through Godot itself.

This is deliberately narrow. Rule/Behaviour execution, Connections, protected-media presentation, audio, physics and broader target features remain later SMX-051 product slices or retained SMX-038 facilities as appropriate.

## State separation

The existing semantic Play coordinator remains responsible for the authored/runtime mode boundary. Product Play additionally requires the Godot target.

During Godot Play:

- ProjectRevisionId does not advance;
- authored visual state remains unchanged;
- Timeline records remain unchanged;
- editor DOM identity does not enter the target projection;
- Godot object identity does not enter authored state.

Stop returns to exactly the authored editor basis.

## Real-target evidence

SMX-051C extends the existing SMX-038 Godot workflow rather than creating another runtime build.

The sequence is:

1. validate the SMX-038 production target contract;
2. export the generic Godot 4.7.2 Web/Linux runtime once;
3. run the retained SMX-038 exported-Web Chromium evidence;
4. serve that exact exported Web directory through the production editor;
5. create a visual Thing and Timeline through ordinary editor UI;
6. press ordinary Play;
7. observe a real Godot canvas;
8. verify stable ThingId and start/mid/end Timeline samples emitted by Godot;
9. verify authored canonical state is unchanged;
10. Stop and return to the authored Stage.

This proves editor → canonical projection → exported Godot Web runtime execution on one exact source head without promoting Godot handles into SplashMX semantics.

## Compatibility with retained SMX-033 evidence

SMX-033 still owns the semantic Play/Stop, save/reload and authored/runtime separation contract. Its older browser harness now distinguishes two cases:

- ordinary product Play without a supplied Godot runtime must fail explicitly;
- the semantic runtime boundary remains directly probeable for its retained regression evidence.

The SMX-051C real-target campaign owns the ordinary product Play success path.

## Residual product work

SMX-051C does not complete #76. Remaining major product work includes:

- useful Library/reusable-instance UI;
- beginner Rule/Behaviour authoring with visible output;
- Connection authoring without manual IDs;
- richer author-facing Properties/Inspect/recovery;
- media/audio/runtime presentation breadth;
- localization and final accessibility/input qualification;
- follow-up human testing after those workflows are functional.

## Architecture impact

Architecture v1 is unchanged.

SplashMX still owns Thing/Behaviour/Connection/Timeline and durable document semantics. Godot 4.7.2 remains the first private rendering/runtime substrate. The editor and Godot runtime are two projections of the same canonical authored revision rather than competing document models.
