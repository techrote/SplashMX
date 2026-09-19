# SMX-019 — Browser editor/player architectural usability vertical slice

**Status:** destructive pre-Architecture-v1 browser integration evidence
**Issue:** #19
**Evidence date:** 2026-09-19

This campaign executes the accepted authoring, document, publication, multiplayer, collaboration and protected-media contracts in a deliberately small browser product slice. It is not a production editor and it is not a human-usability or accessibility study. Its purpose is to discover whether the accepted architecture can actually project into a small author-facing workflow without forcing engine, transport, storage, schema, package-manager or build-system concepts into ordinary work.

## Contents

| Section | Summary |
|---|---|
| 1. Result | Records the end-to-end architectural outcome and one corrective boundary finding. |
| 2. Executed slice | Describes the actual blank-canvas through offline generic-player workflow. |
| 3. Semantic mapping | Shows which accepted records each browser surface edits or projects. |
| 4. Runtime/publication boundary | Defines why this is generic data playback rather than per-creation compilation. |
| 5. Multiplayer/collaboration | Exercises bounded peer runtime while keeping People separate from Together. |
| 6. Browser constraints and measurements | Records storage/offline/error and measurable CI seams without invented thresholds. |
| 7. Adversarial and protected-media evidence | Summarizes 34 deterministic tests and immutable media checks. |
| 8. Classification, limitations and handoff | Separates validated architecture from product work retained under O-028. |

## 1. Result

All twelve SMX-012 `UXG-001`–`UXG-012` gates are represented by executable browser/model evidence. A user can start from a blank Stage; create ordinary Things; group them and Make reusable without replacing their concrete identities; add a Rule/Behaviour, stable-port Connection and optional Timeline track; Play and Stop without writing runtime state back into authored state; Save and hard-reload; Publish an immutable creation revision; launch that revision in a separately deployed generic player; and reload the exact same revision from an offline browser cache.

The browser UI exposes the small vocabulary **Thing / Behaviour / Connection**, with Stage, Timeline, Rules, Components, Together, People, Publish and Inspect as views. The executable project model remains the accepted typed semantic record graph rather than a DOM tree, engine scene or UI-specific beginner document.

One defect was found and repaired rather than hidden:

- **R-019-01 — semantic ConnectionId must not be mistaken for transient transport connection identity.** An early hostile-field filter would have banned generic `connection_id`, colliding with canonical SplashMX Connection records. The repaired boundary permits canonical `connection_id` while rejecting explicit runtime handles such as `transport_peer_id` and `connection_handle`. The regression is executable.

No result requires weakening Thing identity, authored/runtime/save/context separation, capability mediation, exact package/publication semantics, runtime-vs-collaboration separation, or the protected source/audio/provenance contract.

## 2. Executed browser slice

The real Playwright campaign performs this path in Chromium:

1. load a blank editor and wait for browser offline support to become ready;
2. add Button and Lamp Things plus one protected sound record;
3. group the Things and promote the ordinary group with **Make reusable**;
4. add a beginner Rule represented by the common Behaviour IR;
5. add a stable-port Connection and an optional Timeline motion;
6. select the **Shared** Together preset and inspect the same advanced network declaration;
7. show transient collaborator presence and retain a durable competing edit in People;
8. Play, interact, verify runtime-only state mutation, then Stop;
9. Save, hard reload, verify transient presence/play context is absent and durable authored/conflict state remains;
10. Publish an immutable `CreationRevisionId` and load it in the generic player;
11. interact in the player, then disable browser networking and reload the exact cached revision;
12. execute compatibility/capability/storage-denial paths and a two-page peer-hosted shared-state path.

The campaign fails on visible substrate/build vocabulary, identity replacement during reuse, preview-state leakage, publication revision substitution, protected-media mutation, offline substitution, capability/compatibility activation mistakes, or peer divergence.

The test is intentionally narrow enough that a failing architectural seam is attributable. It is not a benchmark game, visual-polish exercise, production sync engine, final package format or final editor design.

## 3. Semantic mapping

| Browser surface | Canonical/runtime meaning |
|---|---|
| Stage | View of canonical Things and structural containment. |
| Things list | Stable `ThingId` records; names are labels, not identity. |
| Group | Structural containment between ordinary Things. |
| Make reusable / Components | Adds Definition/Element provenance and public interface without replacing first-instance `ThingId`s. |
| Rules | Beginner projection that emits the same constrained Behaviour IR used by Advanced authoring. |
| Connections | Canonical `ConnectionId` plus stable `ThingId + PortId` endpoints. |
| Timeline | Optional tracks targeting `ThingId + property`; ordinary interaction works without Timeline. |
| Play | Creates a transient runtime materialization/copy; Stop discards it. |
| Save | Persists editable canonical state but clears selection, presence and play-session context. |
| Together | Edits topology-independent spawn/control/authority/replication/relevance declaration. |
| People | Shows edit-plane presence and durable conflict alternatives; it does not define runtime authority. |
| Publish | Deterministically projects runtime-required semantics into an immutable creation revision. |
| Generic player | Validates exact revision/features/capabilities/integrity before activation. |

The JavaScript implementation under `experiments/smx-019-browser-vertical-slice/` is disposable host/test code. JavaScript objects, DOM identities, local-storage keys, CacheStorage keys, service-worker URLs, WebSocket connection IDs and Playwright selectors are not canonical SplashMX identity.

## 4. Runtime/publication boundary

Ordinary Publish does **not** invoke a Godot export, compiler, bundler or per-creation build. The editor creates immutable data from the accepted project semantics. A separately deployed generic browser player resolves that exact `CreationRevisionId`, verifies publication/revision integrity, validates required semantic features and required capability grants, then materializes runtime state.

The revision identity covers the whole immutable publication envelope, including declared capability requirements; the separate semantic digest covers runtime semantic records. Changing required capability declarations therefore creates a different immutable published revision even when the visible Thing graph is unchanged.

Hosted and offline paths use the same revision. The browser service worker and CacheStorage are only distribution/cache adapters. Offline launch may reuse the exact cached revision; it may not float to a different compatible publication.

SMX-017 separately supplies real Godot 4.7.2 browser/headless export/topology evidence. SMX-019 deliberately keeps its disposable player host independent so the campaign tests **replaceable projection and generic-runtime semantics**, rather than accidentally promoting Godot or JavaScript identities into public creation contracts. Final product binding of these semantics into the production generic Godot player remains implementation work, not a new architecture question.

## 5. Multiplayer and collaboration remain separate

The editor's **Shared** Together preset and Advanced view edit one declaration containing `spawn_scope`, `control`, `authority`, `replication` and `relevance`. Transient socket/peer/session identifiers are not authored fields.

For a bounded integration check, two generic-player pages load the identical immutable publication. The relay gives each page a distinct transient transport connection ID. The first principal is current peer authority; a non-authority page sends input intent; the authority applies the accepted runtime action and broadcasts state; both pages converge. Those connection and current-authority values stay runtime context and do not enter canonical content.

This does not replace SMX-017's destructive reconnect, host-loss and topology-equivalence campaign.

**People** is independently exercised: transient collaborator presence can be shown without changing Together, while durable conflict alternatives survive an editable save/reload but are excluded from published runtime content. This preserves SMX-011/018's separation between collaborative editing and live simulation consistency.

## 6. Browser constraints and measured evidence

The harness uses three deliberately non-semantic browser facilities:

- editable project storage: browser local key/value storage in the disposable slice;
- exact offline publication closure: service worker + CacheStorage;
- peer integration: WebSocket relay with transient connection IDs.

Storage denial is forced and must produce an author-facing save failure rather than silent loss. Required semantic incompatibility and required capability denial are forced and must fail before runtime activation. Offline reload must yield the exact `CreationRevisionId` already cached or fail unavailable; the test forbids revision substitution.

`browser_harness.mjs` emits `artifacts/smx019-browser-results.json` containing pinned runtime/browser environment, editor-load time, Publish time, player-load time, offline-reload time, peer-convergence time, total campaign duration, author gesture count, encountered author vocabulary, browser storage observations, protected asset identity/digest and static harness byte counts. CI uploads this file as an artefact. These are **observations**, not premature product SLOs.

Automated interaction establishes executable projectability and catches vocabulary/round-trip seams. It does **not** establish novice comprehension, discoverability in an unguided study, accessibility, localization quality, final terminology, mobile suitability or broad production performance.

## 7. Adversarial and protected-media evidence

`test_model.mjs` contains **34 deterministic tests**. They cover all UXG gates plus duplicate Thing identity, hierarchy-path ports, invalid reuse shortcuts, authored/runtime state isolation, transient save stripping, conflict alternative retention, exact/deterministic publication, network-context rejection, dangling references, unsupported IR, recursive host-identity rejection, R-019-01, publication-plane filtering, immutable-publication tamper detection, unsupported required features, required/optional capability handling and canonical digest ordering.

Protected media is explicit throughout. Stable `AssetId` selects one complete immutable revision containing:

- digest;
- source identity and source metadata;
- audio/media semantics;
- provenance;
- licence;
- derivation.

An incomplete replacement is rejected before commit and leaves the previous revision untouched. A complete replacement may retain `AssetId` while changing the entire revision coherently. Publish copies the complete protected revision unchanged. Generic-player activation, offline cache and peer runtime use that canonical record; decoded/runtime/cache state cannot replace or field-mix it.

## 8. Classification, limitations and handoff

The browser campaign classifies findings as follows:

| Class | SMX-019 result |
|---|---|
| Architecture validated | One semantic system projects through the full create→play→save/reload→publish/load path; generic immutable data publication works; Together/People remain separate. |
| UX projection defect | R-019-01 showed naming-based hostile filtering can accidentally collide with canonical author semantics; repaired with explicit runtime-handle names. |
| Godot substrate limitation | None newly demonstrated here; SMX-017 owns real Godot/browser topology evidence. |
| Browser limitation | Persistence/offline availability is conditional and must remain typed/non-semantic. |
| Package/runtime defect | No publication revision substitution or protected-media synthesis survived the harness. |
| Unresolved product work | Final production editor/player binding, human studies, accessibility/localization, broad performance, durable production persistence/cache policy and distribution scale. |

**O-028** retains those product-level obligations. They are not grounds to reopen the accepted architecture unless implementation evidence later demonstrates an actual semantic contradiction.

SMX-020 may therefore use this campaign as the final browser projection/destructive usability input, together with SMX-015 Object Fabric, SMX-016 hostile sandbox, SMX-017 topology and SMX-018 collaboration evidence. Architecture v1.0 should preserve the explicit limitations above rather than converting automated browser evidence into stronger human/product claims.
