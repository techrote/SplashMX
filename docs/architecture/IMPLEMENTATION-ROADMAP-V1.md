# SplashMX Architecture v1 production implementation roadmap

**Status:** Architecture-v1 production roadmap  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Date:** 2026-09-19

This roadmap orders production work from the smallest coherent local/offline editor-player substrate outward. It deliberately does not imply that every research harness should graduate into production code.

**Active issue decomposition:** `docs/implementation/PRODUCTION-PROGRAMME-V1.md` maps this roadmap to SMX-021–052 / issues #46–77, hard dependency edges, concurrency windows and execution gates. The programme document is an execution map and does not override this roadmap or Architecture v1.

## Contents

| Section | Summary |
|---|---|
| 1. Roadmap rules | Defines ordering, evidence, and anti-feature-creep rules. |
| 2. Research artefact disposition | Classifies what is reusable, reference-only, or must be rewritten. |
| 3. Phase 0 — frozen-contract guardrails | Makes Architecture v1 machine-checkable before production code expands. |
| 4. Phase 1 — canonical core and protected assets | Builds the durable semantic records, validation, transactions, and asset boundary. |
| 5. Phase 2 — bounded execution and capabilities | Implements common IR execution, scheduling, budgets, and host mediation. |
| 6. Phase 3 — lifecycle, persistence, and streaming | Adds local/offline save, restore, exact acquisition, and partial residency. |
| 7. Phase 4 — minimal browser editor/player | Keeps simple authoring continuously executable against the real core. |
| 8. Phase 5 — components and generic publishing | Adds exact package locks, portable components, immutable publication, and offline load. |
| 9. Phase 6 — Godot production binding and performance | Replaces research bindings with measured production substrate adapters. |
| 10. Phase 7 — security hardening | Proves the real parser/decoder/runtime/crypto boundary rather than only model semantics. |
| 11. Phase 8 — collaboration | Selects and validates a production sync/store substrate under fixed conflict semantics. |
| 12. Phase 9 — production multiplayer | Implements production transports/auth/lifecycle while retaining topology independence. |
| 13. Phase 10 — distribution and product hardening | Adds hosting, durable distribution, accessibility, usability, and operational breadth. |
| 14. Remaining research spikes | Keeps genuine unknowns explicit rather than hiding them inside feature tasks. |

## 1. Roadmap rules

1. **Architecture semantics first.** Production code may optimize representation but may not silently alter Architecture-v1 meaning.
2. **Local/offline core before cloud breadth.** Editing, playing, saving, restoring, packaging, and exact offline playback must work without requiring a hosted control plane.
3. **Simple authoring is a continuous gate.** Every phase that changes canonical semantics, execution, storage, packages, publishing, networking, or collaboration must keep the minimal create → play → save/reload workflow demonstrable.
4. **Security before ecosystem scale.** No public untrusted-component ecosystem is accepted until production parser/IR/capability/decoder boundaries pass hostile tests.
5. **Evidence before optimization claims.** Performance targets must name hardware, browser/runtime versions, workload, sample size, and metric definition.
6. **Do not productionize a research harness by inertia.** Reuse fixtures and invariants aggressively; rewrite disposable proof implementations when they are unsuitable for production.
7. **Protected media is a cross-cutting release gate.** Stable `AssetId` plus complete immutable digest/source/audio-or-media/provenance/licence/derivation semantics must survive every phase.
8. **No hidden cloud dependency.** Hosted collaboration, discovery, marketplaces, CDN distribution, and remote services extend the system; they do not become required for canonical local project ownership.

## 2. Research artefact disposition

### 2.1 Reuse as durable conformance material

The following are valuable inputs to production CI and should be ported or wrapped rather than discarded:

- SMX-001 representative/adversarial corpus and scorecard;
- machine-readable fixtures from SMX-002 through SMX-019;
- correction regressions R-016-01..04, R-018-01..04, and R-019-01;
- protected-media atomicity fixtures;
- lifecycle/streaming/tombstone/exact-lock cases;
- topology-equivalence scenarios from SMX-017;
- collaboration conflict/reconnect schedules from SMX-018;
- browser UXG/BV acceptance flows from SMX-019;
- repository validators where they check semantics rather than implementation filenames.

These fixtures are evidence contracts. They may need format adapters as production schemas mature, but their semantic claims should remain traceable.

### 2.2 Reference-only / disposable implementations

The Python proof models under most `experiments/smx-00x-*` directories are intentionally non-production. Their algorithms, data structures, storage, and timing are not production commitments. Preserve them as readable counterexample/reference material while production code is implemented independently against the same semantic fixtures.

The SMX-019 JavaScript editor/player/server is also a disposable architectural-UX harness. Its DOM model, local-storage keys, service worker, WebSocket relay, and JavaScript object layout must not become canonical merely because the slice worked.

The SMX-017 real-topology harness is stronger integration evidence, but its test relay/orchestration remains test infrastructure rather than the product network service.

### 2.3 Must be rewritten or selected for production

Production requires deliberate implementations for:

- canonical encoding, indexing, validation, transactions, and crash-consistent storage;
- behaviour compiler(s), VM/interpreter/executor, scheduler, and budget accounting;
- capability grant store and trusted host-service adapters;
- dependency/package resolver, immutable cache/store, trust/signature handling, and migrations;
- Godot binding/materialization layer;
- browser/native/headless persistence and cache adapters;
- generic player/server runtime;
- editor UI/application state;
- collaboration sync/store/relay substrate;
- runtime network transports, authentication, signalling, and authoritative server services;
- media import/decode/transcode isolation and derivative caches.

No research implementation is exempt from a production suitability review.

## 3. Phase 0 — frozen-contract guardrails

**Goal:** make Architecture v1 difficult to accidentally violate before production code grows.

Deliverables:

- Architecture-v1 audit/validator retained in CI;
- a production conformance fixture registry that maps each frozen invariant to source evidence and future implementation tests;
- schema for reporting typed failures without exposing Godot/browser/package-manager jargon;
- explicit compatibility/version fields for production artefacts from day one;
- benchmark metadata format for later browser/native/headless measurements.

Gate:

- Architecture validation, local Markdown/reference validation, and research regression suites remain green;
- every production package/module declares which Architecture-v1 responsibilities it owns;
- no production code is allowed to treat NodePath/RID/resource path/socket/session/DOM identity as canonical semantic identity.

## 4. Phase 1 — canonical core and protected assets

**Goal:** implement the smallest production-grade semantic kernel and durable project representation before editor breadth.

Implement:

- `ThingId`, definition/element identity, behaviour attachment identity, stable `PortId`/`ConnectionId`, `AssetId`, project/revision identity and typed references;
- Thing records and explicit relationship/context taxonomy;
- local group/definition/instance/overlay semantics;
- stable ports/connections, tombstones, delete/connection atomicity;
- semantic transactions with whole-document validation-before-commit;
- authored versus transient/runtime/persistent/collaboration planes;
- complete protected asset revision bundles;
- deterministic/canonical logical serialization requirements and migration envelope;
- local crash-safe project persistence sufficient for a small project.

Do **not** add package registries, hosted collaboration, marketplace concepts, or sophisticated rendering tools here.

Adversarial gate:

- rename/reparent/load boundary identity stability;
- duplicate identity and dangling invalid endpoint rejection;
- definition/instance reconciliation and R-018 regressions;
- complete asset replacement only; field mixing is impossible;
- transient engine/session/capability handles are rejected from durable records;
- failed transaction/migration leaves the previous coherent revision intact.

## 5. Phase 2 — bounded execution and capabilities

**Goal:** execute useful behaviour without introducing a privileged second scripting architecture.

Implement:

- versioned common IR semantics;
- beginner-rule compiler as the first front end;
- scheduler/event ordering and mutation publication rules;
- behaviour-private state and stable attachment identity;
- timers/delayed work/continuations with lifecycle-ready representations;
- compatible hot replacement with state/pending-work migration and rollback;
- independently enforced CPU/instruction, recursion, allocation, emitted-work, timer/queue and service-request budgets;
- principal attribution;
- capability declaration/grant/revocation/delegation model;
- trusted host-service adapter API with final authorization immediately before host use.

Keep arbitrary GDScript, C#, native extension and JavaScript host access outside ordinary user content.

Adversarial gate:

- unknown/forbidden opcodes fail closed;
- recursive/event/timer/allocation amplification terminates under deterministic semantic limits;
- R-016 delegation/revocation cases pass against real capability code;
- hot-replacement failure cannot partially mutate live state;
- beginner Rule and a materially nontrivial advanced behaviour execute through the same semantics.

## 6. Phase 3 — lifecycle, persistence, and streaming

**Goal:** make the local/offline runtime durable enough that production editor work cannot accidentally depend on always-live engine objects.

Implement:

- activation/dormancy/snapshot/unload/rehydrate/tombstone lifecycle;
- persistent world/save-state representation separated from editable authored state;
- restore from semantic state plus exact artifacts into a fresh process/runtime;
- durable timers/pending work where promised;
- known-unloaded versus tombstoned/unknown reference states;
- object/subgraph logical residency;
- bounded exact dependency acquisition and cache abstraction;
- transactional behaviour/definition/dependency migration;
- local/offline cache/store sufficient for exact rehydration.

Gate:

- fresh-process restore of representative graphs without surviving Godot objects;
- inventory/reference-to-unloaded-target case;
- selective subgraph load independent of containment region when dependencies permit it;
- cache eviction remains non-semantic;
- missing/corrupt/incompatible exact dependencies produce typed failure without partial activation;
- the minimal local create → play → stop → save/reload flow stays green.

## 7. Phase 4 — minimal browser editor/player

**Goal:** project the real production core into the smallest usable browser authoring loop before platform complexity accumulates.

Implement only enough UI to exercise:

- blank Stage and Thing creation/import;
- grouping/nesting;
- Make reusable/local Definition;
- Behaviour/Rule attachment;
- stable-port Connection;
- optional Timeline property animation;
- Play/Stop over transient runtime state;
- Save/reload through the production local store;
- Inspect with author-language diagnostics.

Keep Together, People, package browsing, rich publishing, and marketplace breadth minimal or absent until their underlying production layers exist.

Gate:

- port UXG-001..UXG-012/BV boundary tests to the production editor/player seams as applicable;
- basic flow contains no Node/SceneTree/Resource/RPC/schema/package-manager/build terminology requirement;
- keyboard/accessibility structure begins here, not at the end of the project;
- real browser startup, load, interaction, save, and memory metrics are recorded with named environments;
- browser storage denial/quota failure is explicit and non-destructive.

## 8. Phase 5 — components and generic publishing

**Goal:** move the same local reusable semantics across project and publication boundaries without turning authors into package/build engineers.

Implement:

- local Definition → portable package promotion preserving semantic lineage;
- production package manifest/container candidate and bounded parser;
- exact resolution lock and immutable cache/store;
- required/optional/lazy dependency behavior;
- staged package update/reconciliation/migration/rollback;
- package provenance/licence/remix/source metadata independent of execution trust;
- immutable `CreationRevisionId` publication;
- versioned generic browser player first, then native/headless profiles as needed;
- prepare-before-activate compatibility/exact-closure/capability pipeline;
- hosted-release identity abstraction and exact offline closure/install path;
- persistent WorldSave basis separation.

Gate:

- ordinary Publish performs no per-creation Godot export/compile;
- exact same immutable creation revision loads hosted and offline;
- floating dependency/revision substitution is impossible during playback;
- target stripping/transcoding cannot rewrite protected media semantics;
- package update failure leaves previous lock and live state coherent;
- malformed/corrupt package bytes cannot execute migrations/IR before validation.

## 9. Phase 6 — Godot production binding and performance

**Goal:** replace model-level object-fabric assumptions with measured production adapters while keeping Godot identities private.

Implement and measure:

- canonical Thing → target-private Godot realization/binding lifecycle;
- rendering, audio, input and physics adapters;
- runtime media decoding/import and derivative caches;
- browser/native/headless player builds from the same runtime source;
- binding replacement/recreation without semantic identity mutation;
- engine event-loop integration with SplashMX scheduling guarantees;
- headless presentation omission driven by semantic usage rather than file type.

Measure named Godot/browser/native builds and hardware for:

- runtime startup;
- WebAssembly download/start/heap where applicable;
- object/binding creation and churn;
- representative render/physics/audio workloads;
- save/load/materialization time;
- frame-time distributions and memory;
- large-enough object counts to reveal architecture overhead.

Gate:

- no NodePath/RID/ResourceUID/peer identity leaks into canonical records;
- unsupported target features produce declared capability/compatibility results;
- performance findings are reconciled architecturally if they force a semantic compromise rather than hidden in adapters.

## 10. Phase 7 — security hardening

**Goal:** turn model-level hostile evidence into a production untrusted-content boundary.

Implement/prove:

- path normalization and archive/container extraction safety;
- cryptographic integrity/signature/trust-root/revocation policy appropriate to chosen distribution design;
- hardened Godot web/native/headless builds with unnecessary host bridges removed where practical;
- media decoder/import isolation strategy;
- process/origin/sandbox boundaries for target runtimes;
- calibrated CPU/memory/GPU/audio/decode/decompression/dependency limits;
- hostile network-ingress validation at real adapters;
- security telemetry and typed user-facing denial/failure outcomes.

Gate:

- port the full SMX-016 attack matrix to production parser/resolver/executor/host code;
- fuzz/malformed-input campaigns cover the chosen physical container/schema/IR encodings;
- capability revocation/delegation passes at real host boundaries;
- no parser/migration/decoder/IR executes before the preceding verification stage allows it;
- target-specific weaker isolation is explicitly documented and either mitigated or treated as a release blocker for untrusted public content.

## 11. Phase 8 — collaboration

**Goal:** implement local-first shared editing without allowing the synchronization technology to dictate product conflict semantics.

First run a bounded spike comparing candidate CRDT/OT/oplog/database combinations against the frozen SMX-011/018 outcomes, including compaction and crash consistency. Then select a production substrate by evidence.

Implement:

- durable semantic transaction history;
- causal synchronization and offline reunion;
- tombstone/conflict retention sufficient for promised semantics;
- explicit conflict materialization/resolution;
- selective undo/history as actually promised by the editor;
- schema/history migration/quarantine;
- permissions epochs and authenticated relay/store paths;
- transient presence separate from canonical state;
- crash-consistent local collaboration store and compaction.

Gate:

- every CR-001..CR-028 class runs under reorder, duplication, disconnect/reconnect, crash/restart and compaction;
- canonical document validity is checked independently of substrate convergence;
- offline work is not silently discarded;
- protected asset alternatives remain complete coherent revisions;
- relay/storage outage does not make the remote copy the hidden canonical authority.

## 12. Phase 9 — production multiplayer

**Goal:** put the accepted topology-independent runtime semantics onto production transports and deployment infrastructure.

Implement:

- authenticated principal/session establishment;
- peer-hosted browser transport/service path;
- dedicated-authoritative server transport/service path;
- transport negotiation/signalling as required by chosen adapters;
- authority epochs, reconnect, join/leave and supported host migration;
- relevance/interest and bounded unloaded delivery;
- interpolation/prediction only for workload classes that require it;
- hostile ingress, replay/duplicate/reorder and rate/resource protection;
- production observability for authority/control/replication without leaking transport IDs into canonical state.

Gate:

- rerun SMX-017’s same-canonical-creation equivalence campaign on production adapters;
- browser background/suspension and reconnect are tested on supported browsers/devices;
- peer-host and dedicated-authoritative trust differences are explicit;
- packet loss/reordering/latency/host-loss scenarios match declared semantic outcomes;
- NAT/TLS/ICE/signalling/authentication failures yield typed runtime outcomes rather than project rewrites.

## 13. Phase 10 — distribution and product hardening

**Goal:** scale the coherent local system into a durable product without making hosting infrastructure the architecture.

Potential work after the local/offline/player/package/security foundations are green:

- hosted immutable releases and friendly aliases;
- CDN/cache invalidation and historical runtime retention;
- native packaging/installers where product evidence justifies them;
- collaboration/network service operations and regional resilience;
- component discovery/registry/federation/marketplace layers;
- project/package provenance presentation;
- accessibility certification and remediation;
- localization;
- touch/keyboard/device workflows;
- novice and expert usability studies;
- recovery/backup/export/import UX;
- broad performance qualification and supported-hardware matrix.

Gate:

- cloud/service loss must not invalidate ordinary local project ownership or exact offline content already installed;
- aliases/marketplace entries never become immutable semantic identity;
- accessibility and human usability are release criteria, not optional polish;
- operational shortcuts may not grant public content additional authority.

## 14. Remaining research spikes

These are intentionally named as spikes because Architecture v1 fixes the surrounding semantics but evidence is still needed before committing to a production mechanism:

1. **Canonical physical encoding/store spike:** compare compact canonical encoding and crash-consistent local stores under migration, partial load, browser persistence and diff/collaboration needs.
2. **Real Godot binding/performance spike:** measure candidate realization layouts and scheduler integration before hardening an object-to-node/resource mapping.
3. **Production sandbox/decoder/crypto spike:** select practical archive/media/trust isolation and quantify target-specific residual attack surface.
4. **Package resolver/distribution spike:** choose version syntax/solver/container/index/trust/discovery mechanisms while preserving exact runtime locks and no ambient install authority.
5. **Collaboration substrate/compaction spike:** compare candidate sync/storage stacks under the destructive conflict corpus, long offline histories, compaction and crash recovery.
6. **Network deployment spike:** test production browser/native transports, authentication, signalling/NAT/TLS, suspension/reconnect and server failure behavior.
7. **Human usability/accessibility study:** validate novice comprehension and progressive disclosure against the production browser slice; automated UXG evidence is not a substitute.
8. **Historical compatibility programme:** define supported fixture generations, migration retention policy and historical generic-runtime strategy before public content has long-lived installed bases.

A spike that discovers a genuine semantic contradiction must reopen the relevant Architecture-v1 decision through an ADR and regression. A spike that only selects an implementation below the boundary should not reopen the architecture.