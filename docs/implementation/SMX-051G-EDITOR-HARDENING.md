# SMX-051G — editor hardening, recovery, accessibility and localization

**Issue:** #120  
**Parent:** #76 / SMX-051  
**Dependency:** SMX-051F / #119 merged on authoritative `main`  
**Architecture:** SplashMX Architecture v1.0 unchanged

## Gap audit

SMX-051A–F established the functional creative spine: visual Stage, Timeline, real
Godot Play/Stop, beginner Rules, grouping/reusable Library and named compatible
Connections. The remaining #76 implementation gaps were cross-cutting product
surface issues rather than missing semantic subsystems:

- the browser exposed a saved revision identifier but not a clear saved/dirty state;
- Reload did not state that unsaved work would be discarded;
- SMX-050 recovery archives existed only as a production primitive, not editor UX;
- raw canonical JSON was the first Inspect representation;
- Stage zoom/pan and stacking controls were incomplete;
- shortcuts existed but were not discoverable in-product;
- ordinary copy had no stable localization catalogue;
- no single campaign exercised the whole SMX-051A–F visible workflow.

SMX-051G addresses only those bounded gaps. It does not broaden Rule/Connection
vocabulary, create another document/runtime model or claim final human usability
evidence.

## Save, dirty state and safe recovery

`BrowserRuntimeSession.snapshot()` now exposes one explicit local storage state:

- **Not saved yet** — no verified durable local head is known;
- **Unsaved changes** — the active ProjectRevision differs from the verified saved head;
- **Saved** — the active ProjectRevision is the verified local head.

Reload remains the existing SMX-025 verified load path. When dirty, the visible
Reload control explicitly says that unsaved changes will be discarded.

Backup and recovery reuse the existing SMX-050 deterministic bounded recovery
archive. The editor can download the active canonical project as a recovery archive
and restore an archive for the same ProjectId. Restore is prepare-before-replace:
the complete archive and canonical project are decoded, validated and Rule programs
rebuilt before active editor state changes. A malformed, unsupported, oversized or
wrong-project backup leaves current work unchanged and produces an author-facing
typed diagnostic. Restoring does not silently overwrite the durable saved head;
Save remains the explicit publication action.

## Properties, Inspect and diagnostics

Ordinary visual editing remains in **Properties**. Stacking is an ordinary visual
property and can also be changed with **Send backward / Bring forward** controls.

**Inspect** is now progressive disclosure:

- the first view is a structured selection summary with stable identity and useful
  counts/relationships;
- raw canonical diagnostic JSON remains available inside a collapsed advanced
  disclosure;
- typed diagnostics remain visible separately.

Routine creation, animation, reuse, Rules, Connections, persistence and Play do not
require raw JSON or internal identifiers.

## Stage viewport and stacking

Stage viewport zoom is process-local editor context, not canonical project meaning.
The Stage is scrollable for pan and provides visible Zoom out / 100% / Zoom in
controls plus keyboard equivalents. Pointer movement/resizing remains expressed in
authored coordinates at any zoom level.

Stacking is canonical author-visible visual state as `visual.layer`, bounded to
-1000..1000. The browser Stage projects it to CSS stacking and the existing generic
Godot target projects the same value to target-private `z_index`. Stable ThingId
and all existing visual/Timeline semantics remain unchanged.

## Accessibility and input classes

The production browser editor declares and tests these supported authoring classes:

- pointer/mouse primary activation and direct Stage manipulation;
- keyboard navigation and native form controls;
- touch/pointer events through the existing Pointer Events paths where the browser
  supplies them.

Core controls have visible focus, native roles/states or explicit accessible names.
Stage Things expose selected state, the Stage itself can receive focus and keyboard
pan, and all major areas remain reachable through normal document order. Shortcut
help is visible in-product and documents Save, Play/Stop, Inspect, Group/Ungroup,
zoom and stacking commands. No new keyboard trap or pointer-only semantic action is
introduced.

## Localization boundary

`src/splashmx/editor/web/i18n.js` defines the first stable author-copy catalogue.
Ordinary static copy is addressed with `data-i18n` keys and dynamic hardening
messages use the same `t(key, values)` boundary. English is the built-in fallback;
additional locale catalogues can be registered without changing canonical project,
Rule, Connection or runtime semantics.

The durable test scans marked ordinary UI copy and fails if a referenced catalogue
key is missing. Localization infrastructure is a presentation boundary only.

## Integrated product regression

`tests/production/smx051g_editor_godot_harness.mjs` drives pinned real Chromium
against the exact exported Godot 4.7.2 Web runtime and exercises, through visible
product surfaces:

1. create visible content;
2. keyboard position/resize;
3. stacking plus Stage zoom/pan;
4. create a second Thing;
5. author a visible Timeline animation;
6. add a beginner Rule;
7. group;
8. make reusable and create a second visible instance;
9. author a named compatible Connection without entering internal IDs;
10. Play through real Godot and physically trigger the connected interaction;
11. Stop with authored/runtime separation intact;
12. Save, make an unsaved alteration and Reload;
13. export and restore an SMX-050 backup;
14. inspect through progressive disclosure;
15. reopen after a full editor-process restart.

This campaign is a regression gate only. It does **not** substitute for the final
human verification still required by parent #76.

## Failure coverage

Unit coverage retains and extends realistic non-destructive outcomes:

- quota and permission failures from SMX-033;
- corrupt local reload from SMX-033;
- missing qualified Godot runtime from SMX-051C;
- malformed/unsupported recovery archive;
- project-identity mismatch on recovery;
- save/dirty/reload state transitions.

All failure paths preserve the current coherent project unless the author completes
an explicitly valid restore or reload action.

## Residual boundary

SMX-051G does not claim final cross-platform release qualification (#77), universal
touch/device support, broad new authoring vocabulary, arbitrary component variants,
or final human usability/accessibility acceptance. Parent #76 remains open for the
required follow-up human verification.

## Architecture impact

None.

SplashMX still owns canonical Thing/Behaviour/Connection/Timeline/Definition and
persistence semantics. Stage viewport state is editor-local. Visual stacking is
ordinary authored visual state projected consistently into the existing private
Godot target. Recovery reuses the SMX-050 archive format, and localization remains
presentation-only.
