# SMX-032 — Minimal browser authoring shell over the production core

**Status:** production implementation for SMX-032 / #57  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Production dependencies:** SMX-023 through SMX-031  
**Conformance:** GATE-04 partial production ownership; EDT-001 through EDT-024

## Production contract

SMX-032 establishes the first production browser authoring surface on top of the production semantic core. It implements the bounded authoring path that must exist before SMX-033 can perform the broader browser play/save diagnostics, accessibility and measured-acceptance gate.

The ordinary author workflow is deliberately expressed in SplashMX terms: **Stage, Thing, Rule, Behaviour, Connection, Timeline, reusable part, media and Inspect**. The implementation does not require authors to understand engine objects, host resource identities, transport details, package-resolution machinery or per-creation build/export concepts.

Every semantic edit is prepared through `AuthoringSession` and published only through the SMX-023 `SemanticTransaction`/`apply_transaction` boundary. The candidate `CanonicalProjectRevision` is revalidated before it replaces the active session revision. Failed composite edits therefore cannot leak partially created groups, relationships, Connections, Behaviour attachments or protected media records.

## No browser shadow document model

The browser is a thin view/action client. `src/splashmx/editor/web/app.js` keeps a read-only projection returned by `/api/state`; it does not maintain a second canonical document, assign semantic meaning independently or implement its own merge/validation rules. Browser actions are sent to the same-origin bounded bridge in `browser_server.py`, which delegates them to `AuthoringSession`, and `AuthoringSession` delegates canonical meaning to the SMX-023/024/026 production modules.

This is intentional. The existing production semantic core is currently Python. Re-implementing it in JavaScript solely to obtain a browser page would create exactly the easy-model/real-model split forbidden by AUTH-002. A later deployment mechanism may replace the host bridge beneath the same action/transaction boundary, but it must not change the durable object, identity, execution or protected-media semantics.

## Stage, grouping and reuse

Blank Stage creation maps directly to `AddThing`. Grouping creates an ordinary group Thing and explicit `CONTAINS` relationships; it does not transfer Behaviour, persistence, authority or other ownership. Group failure is one atomic transaction.

`Make reusable` walks the explicit containment subgraph and invokes production `PromoteGroup`. The concrete first instance retains the exact existing ThingIds. Instantiation of that Definition allocates a new independent set of concrete ThingIds. There is no separate prefab/class object model.

The real-Chromium campaign and production unit tests cover both the success path and the unknown-member rollback boundary.

## Rules, Behaviours and Connections

The shell exposes Rule and Behaviour attachment as two authoring projections. Both lower through the SMX-026 constrained Rule/Behaviour IR compiler and publish only an exact versioned Behaviour revision attachment. Unsupported actions fail before the attachment transaction is published; no privileged host-code fallback exists.

Connections are authored from stable `ThingId + PortId` endpoints and receive a canonical `ConnectionId`. A hierarchy path cannot be substituted for `PortId`, and a connection to a missing/incompatible endpoint fails the whole transaction. This explicitly retains R-019-01: semantic `ConnectionId` is canonical while transport/session connection identity remains private runtime context.

## Timeline and Inspect

Timeline remains optional. A non-Timeline interactive Thing is fully valid. The minimal Timeline projection records authored keyframes against a stable ThingId/property locus; it does not become universal program flow or Behaviour ownership. Obvious implementation-locator targets are rejected at the authoring boundary and canonical authored-value validation remains the final guard.

Inspect reveals stable SplashMX identity and authored details from the same state projection. Opening Inspect is editor state only and does not advance the project revision.

## Transient editor state

Selection and Inspect visibility live in `EditorState`, outside `CanonicalDocument`, `CanonicalProjectRevision` and protected asset records. Selection changes are explicitly tested to leave `ProjectRevisionId` unchanged. The browser state envelope returns `canonical` and `editor` as separate top-level planes so a view cannot accidentally masquerade transient selection as authored content.

This issue does not implement collaboration presence/history, runtime Play state, save/reload UX or publication state; those remain separate planes and downstream issues own their integration.

## Protected source/audio/provenance boundary

Media import is a canonical transaction plus a complete SMX-024 `ProtectedAssetRevision`. The authoring boundary requires non-empty source bytes and explicit media semantics, provenance, licence/attribution and derivation lineage. It derives the immutable source digest, computes the revision digest from the complete bundle, then publishes the new Thing and Asset together only after validation.

A stable `AssetId` therefore continues to select one indivisible immutable **source digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage** revision. An existing AssetId cannot be rebound by the editor to competing source bytes. Incomplete import fails with neither Thing nor Asset published, and SMX-024 still rejects any attempt to retain an old revision digest while field-mixing protected metadata.

Target-private decoding/transcoding, thumbnails, caches, browser object URLs and future engine resources are not canonical source meaning and are not introduced by this shell.

## Ordinary author language

The static Stage surface is checked by `assert_author_surface_vocabulary()` and by the real Chromium campaign. Common visible copy uses SplashMX concepts rather than substrate/toolchain terminology. Server failures cross the browser boundary as typed authoring errors instead of raw stack traces.

This is a structural vocabulary guard, not the final usability/accessibility decision. SMX-033 owns keyboard/focus diagnostics, baseline accessibility, browser Play/Stop, crash-safe save/reload integration, measured latency and broader author-language recovery acceptance. SMX-048 later owns the human study.

## Conformance and adversarial evidence

`spec/production/smx032-editor-fixtures.json` records **EDT-001 through EDT-024**. The direct production suite covers:

- blank Stage creation and canonical revision advancement;
- transient selection/Inspect separation;
- grouping/reuse identity preservation and rollback;
- independent reusable-instance identity allocation;
- Rule/Behaviour common-IR lowering and unsupported-action failure;
- stable-port Connection semantics, hierarchy-path rejection and invalid-endpoint rollback;
- optional Timeline semantics and locator-target rejection;
- complete protected-media import, incomplete import rollback, AssetId rebinding rejection and digest-bound anti-field-mixing;
- transient authority rejection; and
- R-019-01 plus author-vocabulary regression coverage.

`tests/production/smx032_browser_harness.mjs` launches the actual production authoring bridge and drives the static shell in pinned Playwright Chromium. It exercises create → select → group → make reusable → add stable ports → connect → Rule/Behaviour → Timeline → Inspect → protected-media import, then sends invalid Connection and incomplete-media requests to verify browser-boundary rollback. The harness emits `artifacts/smx032-browser-results.json`.

The dedicated workflow first retains SMX-023, SMX-024, SMX-026 and SMX-031 validation/tests, then runs the SMX-032 validator and direct production suite, and finally the real Chromium campaign.

## Residual scope and SMX-033 handoff

SMX-032 intentionally stops before the P4 gate. It does **not** claim final browser usability, accessibility, persistence UX, Play/Stop integration, generic publication, offline player closure, performance budgets or human-study evidence. Those claims remain owned by SMX-033 and later production phases.

SMX-033 must consume this shell rather than create a parallel editor model. It should integrate production runtime Play/Stop and SMX-025 save/reload, add author-facing diagnostics and focus/keyboard/accessibility coverage, measure the declared browser workflow, and keep transient editor state excluded from canonical and published state.

Architecture v1 is unchanged by SMX-032. The selected browser bridge is an implementation placement below the frozen semantic boundary, not a new public object, package, execution or publication contract.
