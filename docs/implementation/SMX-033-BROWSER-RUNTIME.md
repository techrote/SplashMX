# SMX-033 — Browser Play/Stop, local save, diagnostics and accessibility baseline

**Status:** production implementation for SMX-033 / #58  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Production dependencies:** SMX-025, SMX-029, SMX-031, SMX-032  
**Conformance:** GATE-04 production integration; BRW-001 through BRW-020

## Production contract

SMX-033 completes the minimal production browser create → behave/connect → Play → Stop/edit → Save/reload loop without introducing a browser shadow document model. `BrowserRuntimeSession` is a coordinator only: authored state remains `AuthoringSession` + SMX-023/024 canonical semantics, Play uses SMX-029 `WorldRuntime`, and Save/reload uses SMX-025 `SQLiteProjectStore`.

Play constructs a fresh transient runtime from the exact active canonical document and exact versioned Rule/Behaviour programs. The browser may inspect/select while playing, but semantic edits are rejected until Stop so the runtime cannot silently diverge from its authored basis. Stop discards the transient runtime and reveals the unchanged authored project. Runtime mutation is never copied back into canonical state implicitly.

## Save, reload and offline-local ownership

Save validates and atomically publishes the authored canonical project through SMX-025. Reload prepares and validates the complete stored candidate before replacing the active authoring session; corruption, permission denial, quota exhaustion, incompatible revisions or migration failure cannot destructively replace in-memory work. Rule/Behaviour programs are rebuilt from their exact persisted authored projection through the SMX-026 compiler after reload.

The browser shell and production bridge require no hosted control plane or external web dependency. The measured browser campaign uses only same-origin local resources and the local project store, then performs a page reload against that local ownership boundary. This is the Phase-4 offline-local editor claim; immutable publication/offline player closure remains SMX-036.

## Typed author diagnostics

Storage/runtime/semantic failures are mapped to stable codes plus author-language recovery text. Storage permission/quota/corruption diagnostics explicitly state that the current project remains unchanged. Diagnostics live in the transient browser/editor plane and are shown in Inspect; they are not serialized into the canonical project, protected assets, WorldSave or collaboration state. Raw SQLite/traceback/substrate details are not ordinary author-facing copy.

## R-019-01 and identity boundary

Canonical Connections continue to use stable `ConnectionId` and stable `ThingId + PortId` endpoints. Browser ingress recursively rejects fields such as `connection_handle`, `transport_peer_id`, socket/session/process identity and DOM-node identity rather than silently accepting them as semantic identity. Save/reload retains the exact semantic ConnectionId. This ports R-019-01 to the production browser boundary.

## Keyboard and accessibility baseline

The shell uses semantic `main`, `section`, `aside`, `nav`, `fieldset`, `legend`, labels and real buttons; status and diagnostic regions expose polite live semantics. A skip link targets Stage. Project actions are named and keyboard reachable. Explicit shortcuts are Control/Command+Enter for Play, Escape for Stop, Control/Command+S for Save and Alt+I for Inspect. Thing selection checkboxes receive accessible names. This is a testable structural/keyboard baseline, not a claim of human accessibility certification; SMX-048 owns novice/accessibility studies.

## Protected source/audio/provenance boundary

SMX-033 does not alter protected-media meaning. Stable `AssetId` still selects one indivisible immutable source digest + source identity/metadata + audio/media semantics + provenance + licence/attribution + derivation-lineage revision. Play, diagnostics, local-store placement and browser reload cannot field-mix competing asset revisions or replace canonical source meaning. Target-private decoding/transcoding/caches remain non-semantic derivatives.

## Adversarial and boundary evidence

`spec/production/smx033-browser-runtime-fixtures.json` defines BRW-001..BRW-020. `tests/production/test_smx033.py` covers transient Play/Stop rollback, verified save/reload with Behaviour reconstruction, permission/quota/corrupt-store nondestruction, edit-during-Play rejection, typed diagnostics, and R-019-01 transport-identity rejection. The retained SMX-025, SMX-029, SMX-031 and SMX-032 checks remain prerequisites in the dedicated workflow.

`tests/production/smx033_browser_harness.mjs` drives pinned Playwright Chromium over the real production bridge. It exercises create → ports/Rule/Connection → keyboard Play → Stop → keyboard Save → unsaved edit → verified reload → page reload, checks accessibility structure and R-019-01 at the HTTP boundary, and emits `artifacts/smx033-browser-results.json`.

## Measured acceptance semantics

The evidence envelope names the exact build SHA, browser version, Node version, OS/architecture, workload and sample count. It records startup-to-ready, create, Play-start, Save, verified-reload and page-reload observations plus Chromium JS-heap data when exposed. These numbers are observations from a named CI environment/workload and are **not universal performance SLOs**. Hardware-class targets and publishable budgets remain later performance work.

## Residual scope

SMX-033 does not claim package/publishing completion, collaboration/multiplayer UX, Godot rendering/audio realization, generic offline publication, or human novice/accessibility certification. It completes the Phase-4 editor/player integration boundary needed before package and publication phases.

Architecture v1 is unchanged. The browser bridge, local-store placement and keyboard choices are implementation decisions below the frozen semantic boundary.
