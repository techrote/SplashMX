# SMX-001 research baseline: terminology, evaluation corpus, and research scorecard

Status: authoritative research baseline for pre-architecture work

Issue: SMX-001 / #1

Established: 2026-09-17

This document standardises the vocabulary and evaluation method used by later SplashMX research. It intentionally does **not** select the final object model, scripting IR, package encoding, networking protocol, or collaboration algorithm. Definitions here constrain how research questions are stated so that competing architectures can be compared without silently changing terminology.

The machine-addressable companion corpus is [`SMX-001-EVALUATION-CORPUS.json`](SMX-001-EVALUATION-CORPUS.json). Case IDs in that file are stable research references. Later issues may extend the corpus, but should not reuse an existing ID for a different case.

## 1. Baseline principles

The following rules apply to all later pre-architecture research.

1. **A Thing's meaning must not be inferred solely from where it sits in a hierarchy.** Containment/locality may matter, but control, authority, persistence, replication, and identity are distinct dimensions until evidence proves otherwise.
2. **A candidate model must be evaluated against materially different media and interaction classes.** A model that only works cleanly for sprite games or timeline animation is not yet a universal SplashMX model.
3. **A claim of portability must include lifecycle transitions.** Rename/reparent, save/load, stream-out/in, definition update, authority transfer, and collaboration must be considered where relevant.
4. **A claim of safety must include hostile input.** Untrusted creations, components, packages, assets, network peers, and behaviour programs are normal threat cases.
5. **A claim of simplicity must be author-facing.** Hiding complexity in undocumented magic or external managers does not count as simplification.
6. **A prototype answers a named question.** Prototype code is evidence, not architecture by inertia.
7. **No aggregate score can waive a hard failure.** The research scorecard supports comparison; constitutional gate failures remain disqualifying until explicitly resolved.

## 2. Glossary

### 2.1 Core authored concepts

**Thing**

The neutral project term for an independently identifiable interactive/media entity or composite whose semantics are under study. A candidate Thing may carry or declare state, behaviours, interfaces/connections, capabilities, presentation, persistence, and network policy. `Thing` does not yet imply a specific in-memory class, Godot `Node`, ECS entity, actor, file, or serialization shape.

**Object**

An informal synonym for an individual authored entity when ordinary language is clearer. In normative architecture research prefer **Thing**, because `object` carries unwanted OO and engine-specific implications. If a document uses `object` in a technical sense, it must define that sense.

**Group**

An authored composite containing or organising other Things. Grouping may imply structural/local transform context, but does not by itself imply behavioural ownership, control, simulation authority, persistence ownership, or replication ownership. H-003 tests whether a Group can use the same semantic kernel as an ordinary Thing.

**Definition / local definition / local class**

A reusable authored definition available within a creation/project. `Local class` is author-facing shorthand under investigation; it does **not** imply conventional OO class inheritance. SMX-003 must determine definition/instance/override semantics. Until then, `definition` is the least presumptive technical term.

**Instance**

A Thing whose structure/initial semantics derive from a reusable definition while retaining its own durable identity and potentially explicit overrides. The exact propagation and override model is unresolved until SMX-003/005.

**Component**

A reusable definition promoted into a portable, packageable unit intended for use across projects. This is distinct from `behaviour`: a component may contain a graph of Things, behaviours, assets, exposed interfaces, metadata, and migrations. SMX-013 owns the portable component contract.

**Behaviour**

A modular declaration or executable representation of intent/control attached to or embodied by a Thing. Behaviours may have requirements, provided interfaces, parameters, and private state. The execution representation, scheduling semantics, state boundary, and hot-swap contract remain hypotheses for SMX-004.

**Connection**

An explicit declared relationship by which one Thing/behaviour/interface can communicate with or affect another. The primitive vocabulary—events, commands, queries, reactive state, messages, ports, or a smaller set—is intentionally unresolved. A connection must not be confused with containment.

**Port / interface**

A named, inspectable boundary through which a Thing or behaviour exposes accepted inputs, emitted outputs, readable/writable properties, commands, events, or other interaction primitives. The exact port model is unresolved; this term is used to discuss explicit boundaries without choosing the eventual vocabulary.

### 2.2 State and context

**Authored state**

Durable data that is part of the editable creation definition: e.g. an object's initial position, authored text, configured behaviour parameters, or timeline keys. Authored state should survive project save/load.

**Runtime state**

Live simulation state that changes while a creation executes: e.g. current velocity, door-open state, health, or a timer's remaining time. Some runtime state may be persistable; not all runtime state is canonical authored state.

**Persistent world/save state**

Runtime-derived state intentionally retained across execution sessions or server lifetimes. It must remain distinguishable from the distributable authored creation so a saved world is not accidentally treated as source content.

**Transient/context state**

State required by the current execution/editor environment but not part of a Thing's durable meaning: editor selection, hover state, cache residency, current network peer connection, diagnostic counters, render LOD, or collaboration cursor presence are examples. Transient state may be reconstructible and should not silently enter canonical project data.

**Behaviour-private state**

State scoped to one behaviour implementation rather than exposed as general Thing state. Whether and how it serializes, migrates, or transfers during hot-swap is unresolved and belongs to SMX-004/007.

**Context**

Information/services supplied by the surrounding runtime without becoming intrinsic Thing meaning. Examples may include current simulation clock, viewport, local user identity, network topology, capability grants, resource resolver, or editor session. Context should be explicit enough that hidden global dependencies can be identified.

### 2.3 Identity and relationships

**Identity**

The durable ability to distinguish one logical entity/definition/revision from another across operations that should preserve sameness. H-008 hypothesises that important identities must be path-independent. Exact ID namespaces and lifetimes belong to SMX-005.

**Reference**

A durable or transient relation naming another entity without implying containment or ownership. A durable reference should have defined semantics when the target is renamed, reparented, unloaded, unavailable, migrated, or destroyed.

**Containment**

A structural/locality relationship expressing that one Thing is organised within another. It may provide transform or namespace context, but does not automatically grant control, authority, persistence, or replication rights.

**Control**

A relationship identifying which source of intent currently drives an aspect of a Thing: local human input, remote player input, AI, replay, automation, or another Thing. Control may change without replacing Thing identity.

**Simulation authority**

The runtime participant whose state transition/result is treated as authoritative for a given scope in a networked simulation. Authority is not synonymous with containment, input control, authorship, persistence, or process ownership.

**Ownership**

A dangerously overloaded word. Avoid it without a qualifier. If used, specify whether it means memory/resource lifetime ownership, authoring provenance, input control, simulation authority, persistence responsibility, package provenance, or another defined relationship. `Owner` must never be allowed to stand in for all of these simultaneously.

**Observation**

A relationship in which one Thing/system receives state/events from another without necessarily controlling it or being authoritative over it.

**Replication**

The policy/mechanism by which selected state/events/inputs are propagated between runtime participants. Replication does not itself decide simulation authority or control.

### 2.4 Security, lifecycle, and distribution

**Capability**

An explicit, inspectable grant allowing otherwise-unavailable operations or runtime services. A capability is narrower than general code execution and must have defined scope/delegation semantics before untrusted components can use it. Absence of a capability is expected to fail closed.

**Persistence semantics**

Declarations/rules governing which authored/runtime/behaviour state can be stored, restored, migrated, or intentionally discarded. Persistence does not imply that the containing group or current controller owns the data.

**Presentation**

The visual/audio/textual/other media representation associated with a Thing. Presentation may be replaceable without changing identity or behaviour, but the exact boundary is researchable.

**Lifecycle**

The observable and implementation transitions through creation/instantiation, activation, sleep/dormancy, serialization, unload, restore/rehydration, and destruction/tombstone states. SMX-007 owns the normative lifecycle model.

**Streaming**

Loading, unloading, or replacing selected Things/definitions/behaviours/assets during execution or editing without requiring the entire creation to be resident. Streaming is not synonymous with scene changes or containment boundaries.

**Creation**

A complete SplashMX-authored work: animation, game, interactive story, tool, presentation, simulation, toy, or other interactive media. A creation may contain many Things and definitions.

**Editable project**

The authoring form of a creation, including material required for continued editing. Its exact artifact contract is deferred to SMX-005/014.

**Published creation**

A distributable validated form intended for generic-player execution. It is not assumed to contain arbitrary Godot project code. Exact package/runtime contracts are deferred to SMX-014.

**Package**

A transport/distribution container for a published creation or reusable component plus manifest/assets/dependencies as later specified. `Package` describes distribution, not semantic ownership.

**Runtime / player**

The software that validates, instantiates, executes, renders, and mediates a SplashMX creation. The working hypothesis is a generic versioned player rather than per-creation compilation; H-015 remains unresolved.

**Host service**

A privileged runtime facility outside untrusted authored logic, such as storage, HTTP, clipboard, microphone, network-room services, or platform integration. Access should be mediated through explicit capabilities.

**Network topology**

The arrangement of runtime participants/transports—offline/local, peer-hosted room, dedicated authoritative server, etc. H-012 tests whether topology can remain policy/runtime configuration rather than changing canonical Thing semantics.

**Collaborative authoring**

Concurrent editing of persistent creation documents, including offline work and later reconciliation. It is distinct from multiplayer simulation replication even if infrastructure is shared.

**Kernel**

In SplashMX research, the minimal semantic contract common to Things—not an operating-system kernel and not necessarily a single runtime class. SMX-002 determines whether a universal kernel is viable.

**Scene**

An author-facing spatial/screen/sequence organisation concept that may be useful in the editor. It must not be assumed equivalent to a Godot scene or canonical serialization boundary unless later evidence supports that mapping.

## 3. Known ambiguities to preserve for later research

The glossary deliberately leaves the following unresolved rather than deciding them by naming:

- whether presentation, persistence, networking, and capability declarations are intrinsic Thing facets or contextual overlays;
- whether a Group is literally the same representation as every other Thing or only shares a common kernel;
- whether local definitions use prototype, structural template, patch/override, inheritance-like, or hybrid semantics;
- which communication primitives are fundamental;
- whether behaviour-private state belongs in canonical snapshots and under what conditions;
- the exact scopes/lifetimes of IDs for Things, definitions, ports, connections, assets, revisions, players, and worlds;
- whether runtime determinism is global, scoped, opt-in, or only fixture-level;
- whether multiplayer state replication is state-, event-, input-, snapshot-, or hybrid-oriented;
- whether collaboration uses CRDT, operation log, transactional locking, explicit conflicts, or a hybrid;
- the final package encoding and whether ZIP is only a container;
- how much Godot-specific coupling is acceptable below the public compatibility boundary.

Later issues should resolve these through evidence rather than silently tightening the glossary.

## 4. Evaluation corpus

The companion JSON file is the canonical case list. This section explains the intended breadth and how cases are used.

### 4.1 Core representative cases

- **C-001 simple drawing + animation:** authored visual shape/sprite with a short transform/opacity animation.
- **C-002 nested timeline clip:** an independently animated nested clip used multiple times with per-instance configuration.
- **C-003 UI button with states:** normal/hover/pressed/disabled presentation plus a click output.
- **C-004 slider controls audio:** UI property drives volume or filter state without the slider owning the audio object.
- **C-005 player character:** input-driven motion, animation, collision, local state, and camera observation.
- **C-006 inventory key references door:** portable inventory Thing retains a meaningful reference while its target may be elsewhere or unloaded.
- **C-007 vehicle/crew/control transfer:** person -> crew -> vehicle -> convoy nesting while driver/AI/remote-player control changes independently.
- **C-008 timeline/audio sequence:** timeline-centric media where audio cues, animation, and text sequencing matter more than game logic.
- **C-009 procedural generator:** seeded generator creates or configures many Things while remaining inspectable/replayable where required.
- **C-010 physics interaction:** dynamic body, sensor/trigger, collision result, and authored response without treating physics engine identity as canonical identity.
- **C-011 reusable dialogue component:** nested UI/audio/behaviour exposed through a small public interface and reused across projects.
- **C-012 streamed town reference:** a world region unloads while an external inventory/reference remains valid and later resolves after reload.
- **C-013 peer-controlled shared toy:** multiple peers control their own cursors/avatars while manipulating shared state.
- **C-014 authoritative shared object:** a contested shared chest/score/object transition is accepted only through simulation authority.
- **C-015 persistent world:** state survives all clients leaving and later resumes without conflating save state with the distributable project.
- **C-016 collaboration delete/edit:** one author deletes a Thing while another edits it.
- **C-017 collaboration reparent conflict:** concurrent structural moves disagree about parent/group without silently changing unrelated semantics.
- **C-018 definition/instance conflict:** definition changes while another author edits an instance override.
- **C-019 offline collaboration reconnect:** two authors edit offline and later reconcile without silent data loss.
- **C-020 local-only HUD in networked world:** presentation/control state visible only to one player observes authoritative world state without being replicated as world state.
- **C-021 network authority/control transfer:** a vehicle or character transfers input control and/or simulation authority while retaining identity.
- **C-022 denied-capability component:** useful component runs when privileged capability is absent and fails closed for the denied feature.
- **C-023 schema/runtime migration:** old creation data is opened by a newer runtime with explicit migration and unsupported-feature behaviour.
- **C-024 serialize/restore pending work:** timers, queued events, behaviour-private state, and references round-trip according to declared semantics.
- **C-025 hot behaviour replacement:** `Patrol` becomes `Flee` or `HumanDriver` becomes `AIController` without reconstructing the Thing.
- **C-026 missing/incompatible component dependency:** load/update encounters absent, revoked, denied, or incompatible dependency and remains understandable/recoverable.
- **C-027 nested exposed interface across stream boundary:** external connection targets an interface exposed by a nested component whose internals can unload/reload.
- **C-028 many-instance media object:** hundreds/thousands of lightweight visual Things stress whether the semantic model mandates excessive per-object machinery.

### 4.2 Hostile/adversarial variants

Later issues should derive specific fixtures from these adversarial patterns:

- **A-001 reparent without semantic mutation:** move a Thing between groups while control, authority, durable identity, persistence, and external references remain unchanged unless explicitly edited.
- **A-002 unloaded target versus destroyed target:** a reference must be able to distinguish temporary absence from terminal invalidation where the chosen model promises that distinction.
- **A-003 hostile capability request:** nested component requests HTTP/filesystem/JavaScript/microphone access it was not granted.
- **A-004 event/timer storm:** recursive events or zero-delay timers attempt unbounded execution.
- **A-005 cyclic/deep dependency graph:** component dependencies form cycles or extreme depth.
- **A-006 hot-swap with incompatible private state:** replacement behaviour cannot consume old private state and must fail/migrate predictably.
- **A-007 collaboration resurrection:** delete/edit/reconnect sequence attempts to resurrect a tombstoned Thing accidentally.
- **A-008 definition update versus structural override:** base definition removes/moves an element an instance has overridden.
- **A-009 network authority loss:** controlling peer disappears mid-operation; identity and authoritative state must remain coherent.
- **A-010 unknown future schema fields/features:** older reader must reject, preserve, or degrade intentionally rather than reinterpret silently.
- **A-011 background-tab suspension:** browser pauses a runtime long enough to invalidate naive realtime assumptions.
- **A-012 malformed/oversized package:** parser sees corrupt metadata, path traversal attempts, decompression amplification, or oversized declared assets.
- **A-013 engine upgrade:** underlying Godot revision changes while old SplashMX content is expected to retain platform semantics.
- **A-014 hidden-manager removal:** remove/restart a coordinator and verify constituent Thing meaning is reconstructible from explicit declarations/context.
- **A-015 transitive capability confusion:** outer component with a grant embeds untrusted inner component that attempts to borrow the grant without explicit delegation.
- **A-016 multiple simultaneous relationships:** one Thing is contained by A, controlled by B, authoritative on C, observed by D, persisted by E, and replicated to F.

## 5. Architecture research scorecard

The scorecard compares candidate models. It is deliberately not a weighted leaderboard. Record **evidence and case IDs** beside every score.

Scoring scale:

- **0 — fails:** contradicts a constitution invariant or cannot represent required cases without an architectural exception.
- **1 — weak:** possible only with significant hidden coupling, special cases, unclear semantics, or author-visible complexity.
- **2 — acceptable:** coherent for required cases with understood trade-offs and testable semantics.
- **3 — strong:** coherent, simple relative to alternatives, falsification-resistant across the corpus, and leaves room for later requirements.
- **N/E — not evaluated:** no evidence yet; never convert this to a passing score.

| ID | Criterion | Evidence expected | Hard gate? |
|---|---|---|---|
| S-01 | Author-facing conceptual simplicity | workflow/concept count; no required Godot/toolchain jargon for basic cases | yes for basic workflows |
| S-02 | Semantic coherence | same terms mean the same thing across media categories | yes |
| S-03 | Hierarchy independence | C-006/C-007/A-001/A-016 without hidden ownership mutation | yes |
| S-04 | Identity/reference stability | rename/reparent/save/load/unloaded-target cases | yes |
| S-05 | Behaviour composability | explicit interfaces/state; C-025/A-006 | no until SMX-004, then gate |
| S-06 | Lifecycle/restore completeness | C-024 and absence/destruction distinction | yes before Architecture v1.0 |
| S-07 | Streaming/partial-load fitness | C-012/C-027/A-002 | yes before Architecture v1.0 |
| S-08 | Sandboxability | C-022/A-003/A-004/A-012/A-015 | yes |
| S-09 | Multiplayer topology fitness | C-013/C-014/C-020/C-021/A-009 | yes before Architecture v1.0 |
| S-10 | Collaboration fitness | C-016–C-019/A-007/A-008 | yes before Architecture v1.0 |
| S-11 | Migration/longevity | C-023/A-010/A-013 | yes |
| S-12 | Godot-boundary discipline | public semantics do not depend unnecessarily on node paths/resource IDs/RPC implementation | yes |
| S-13 | Testability/reproducibility | deterministic fixtures or exact expected invariants where applicable | yes for research conclusions |
| S-14 | Performance proportionality | representative object counts do not require obviously disproportionate mandatory machinery; environment recorded | no numeric gate yet |
| S-15 | Failure clarity | denied/missing/incompatible/unloaded cases produce explicit states rather than silent reinterpretation | yes |
| S-16 | Progressive disclosure continuity | advanced control reveals the same semantic model rather than an unrelated expert mode | yes before editor freeze |

### 5.1 Scorecard reporting format

For any candidate architecture A, later research should report:

```text
Candidate: <name/version>
Cases exercised: C-001, C-006, ...
Adversarial variants: A-001, ...
S-01: 2 — <evidence>
S-02: N/E — <why not yet evaluated>
...
Hard-gate failures: <none or list>
Known special cases: <list>
Counterevidence: <list>
```

Do not report a single total score without the per-criterion evidence. A candidate with a score of 3 in most areas and a hard-gate 0 is not considered acceptable merely because its arithmetic average is high.

## 6. Explicit failure conditions

A pre-architecture proposal is not ready for acceptance when any applicable condition below remains unexplained:

1. **Hidden semantic manager:** ordinary Thing meaning exists only in a distant coordinator not represented by explicit state/relationships/context.
2. **Path identity dependence:** rename/reparent breaks identity/reference semantics that are expected to survive those operations.
3. **Hierarchy conflation:** containment silently changes control, authority, persistence, or replication.
4. **Category fork:** common corpus cases require incompatible base object systems rather than explicit optional facets/behaviours.
5. **Unrecorded live state:** save/restore succeeds only because process objects or globals survive outside serialized state.
6. **Ambient authority:** community content can reach privileged host APIs without an explicit capability boundary.
7. **Unsafe failure:** malformed/denied/missing/incompatible input is reinterpreted, partially executed, or silently accepted.
8. **Topology rewrite:** changing offline/peer/server mode requires rewriting ordinary creation semantics or replacing Things with network-only classes.
9. **Collaboration-as-replication shortcut:** live multiplayer replication is reused as document merge semantics without satisfying the conflict corpus.
10. **Migration dead end:** old content semantics are tied to an engine implementation detail with no explicit migration/compatibility policy.
11. **Easy-mode dead end:** beginner-authored content must be rebuilt in a different expert architecture to become advanced.
12. **Prototype by inertia:** an experiment becomes normative because code exists rather than because evidence justifies the contract.
13. **Non-reproducible claim:** a behaviour/performance/determinism conclusion cannot be reproduced from recorded fixtures, versions, environment, and commands.
14. **Corpus cherry-picking:** a universal claim is supported only by friendly cases while applicable adversarial cases are omitted without explanation.

A failure condition may become an explicit accepted trade-off only through a documented project decision that reconciles the relevant constitution invariant; it cannot be waived inside a local prototype.

## 7. Source freshness policy

External evidence is classified by volatility.

### F1 — Security/runtime/engine implementation facts

Examples: Godot web export limitations, JavaScript bridge options, PCK behaviour, web networking, browser lifecycle, headless server support.

**Rule:** re-check primary sources at the start of every issue that materially relies on the fact, and again before merge if a relevant Godot/browser release landed during the work. Record the date and exact release/docs branch used. Never rely on a prior issue's snapshot as the sole evidence for a security boundary.

### F2 — Web-platform/API support facts

Examples: WebRTC, WebSocket, IndexedDB, permissions, CSP, cross-origin isolation, storage persistence.

**Rule:** use standards/authoritative browser documentation plus actual target-browser tests where behaviour matters. Refresh during every issue whose acceptance criteria depend on current browser support or lifecycle behaviour.

### F3 — Algorithm/library behaviour

Examples: CRDT library semantics, serialization libraries, package/signature implementations.

**Rule:** pin/document the exact library version/commit and verify behaviour with a reproducible fixture. Refresh when the dependency version changes.

### F4 — Conceptual/historical material

Examples: actor model literature, ECS concepts, Flash/HyperCard interaction history.

**Rule:** cite stable original/primary material where possible. Freshness is less important than correct attribution and separating historical precedent from current platform facts.

### Evidence record requirements

Every time-sensitive evidence entry should include:

- evidence ID;
- checked date;
- exact product/release or documentation branch when known;
- primary-source URL;
- factual claim in narrow wording;
- architectural implication, separately labelled as implication rather than fact;
- consuming issue(s);
- replacement/supersession note when later evidence changes it.

## 8. Primary-source snapshot refreshed for SMX-001

Checked: **2026-09-17**.

Current release context: Godot's official download/archive pages identify **Godot 4.7.2 (2026-08-18)** as the current stable Godot 4 release and **4.8-dev6 (2026-09-15)** as the newest development snapshot. `latest` documentation may therefore describe unreleased 4.8 behaviour and must be treated as unstable unless corroborated by stable/versioned docs.

- **E-006 — Web editor limitations.** Godot `latest` docs state the web editor is preliminary, supports only the Compatibility renderer, has no project exporting, and stores project files in browser IndexedDB; source can be downloaded and exported with a native editor. Primary: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html
- **E-007 — Web export baseline.** Current Godot 4.x docs state web export requires WebAssembly and WebGL 2.0, uses the Compatibility renderer, and does not support Forward+/Mobile on web. Single-threaded export is the preferred/default path; threaded export requires cross-origin isolation/SharedArrayBuffer support. Primary: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- **E-008 — Browser lifecycle/network limits.** Current web-export docs state an inactive browser tab may pause the project and can cause network disconnects; low-level networking is unavailable in browser exports, while HTTP, WebSocket client, and WebRTC are supported. Primary: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- **E-009 — JavaScript bridge hardening option.** Current compiling-for-web docs state official/default web builds include `JavaScriptBridge`, and custom templates can be compiled with `javascript_eval=no` to omit that singleton; web threads can likewise be disabled with `threads=no`. Primary: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html
- **E-010 — Runtime user-content loading is supported.** Current runtime-I/O docs cover loading user-provided images/audio/3D/fonts and reading/writing ZIP archives at runtime without requiring those files to be built into the project. Primary: https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- **E-011 — PCK/mod execution is a security boundary.** Godot's pack/mod documentation explicitly warns that runtime-loaded PCKs may contain malicious code and recommends considering cryptographic verification for distributed packs. Primary: https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- **E-012 — Headless/dedicated server substrate exists.** Current Godot docs state Godot 4 can run with the `--headless` display server or as a dedicated-server export. Primary: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html
- **E-013 — WebRTC requires signalling and is a browser-capable transport.** Current Godot WebRTC docs describe browser-available WebRTC peer/data-channel support and signalling as part of connection establishment. Primary: https://docs.godotengine.org/en/stable/tutorials/networking/webrtc.html
- **E-014 — Current Godot release context.** Official archive/download pages identify 4.7.2 as current stable and 4.8-dev6 as latest development snapshot on the checked date. Primary: https://godotengine.org/download/archive/

These are **facts/design inputs, not architecture decisions**. SMX-006/009/010/014/016/017/019 must refresh the entries they rely on.

## 9. Research-harness conventions

Every disposable harness or executable fixture created by later research should be reproducible by another agent without hidden setup.

### 9.1 Required metadata

Record, preferably beside the harness:

- `smx_issue`: owning SMX issue;
- `question`: one sentence naming what the harness is attempting to prove/disprove;
- `hypotheses`: H-IDs under test;
- `corpus_cases`: C-/A-IDs exercised;
- source commit SHA;
- runtime/engine/library versions;
- OS/browser/hardware when materially relevant;
- exact command(s) or interaction sequence;
- deterministic seed(s) where randomness exists;
- fixture/input identifiers or hashes where useful;
- expected invariant/result;
- observed result;
- pass/fail/inconclusive classification;
- known environmental caveats.

### 9.2 Determinism rules

- Prefer fixed seeds and explicit clocks for semantic tests.
- Do not use wall-clock timing as a semantic oracle when a logical tick/event count can be asserted instead.
- Sort or canonicalise unordered output before exact comparison when order is not part of the contract.
- When order *is* part of the contract, state why and assert it explicitly.
- Capture failing fixtures; do not rely on “occasionally reproduces”.

### 9.3 Performance measurement rules

When performance is the research question, record:

- hardware and power/performance mode;
- OS, browser, Godot/runtime version;
- workload dimensions and object counts;
- warm-up procedure;
- sample count/duration;
- metric definition (frame time percentile, memory delta, package size, etc.);
- whether the measurement is debug/release, browser/native/headless;
- variance where useful.

Do not promote machine-specific timings into brittle CI thresholds unless the runner is controlled and the threshold has an explicit margin/rationale.

### 9.4 Prototype isolation

- Mark disposable experiment directories clearly as experimental/non-normative.
- A later stable `spec/` or runtime module must not depend on an experiment merely because it already exists.
- Promote semantics, tests, or fixtures only after evidence supports them; production-quality refactoring is a separate decision.
- Keep generated/binary artifacts out of Git unless they are necessary, small, deterministic fixtures.

### 9.5 Failure reporting

A failed experiment is a valid research result. Record:

1. exact fixture/case IDs;
2. expected invariant;
3. actual result;
4. whether failure is implementation, environment, or architecture;
5. affected hypothesis/decision;
6. smallest next experiment or required upstream amendment.

Never change the expected result merely to match the implementation without reconciling the originating product/architecture requirement.

## 10. Hypothesis review at SMX-001

H-001 through H-018 were reviewed against the glossary, corpus, scorecard, and current evidence snapshot.

**Result:** no hypothesis is resolved by SMX-001, and no wording change is justified yet. All remain **unresolved** test propositions. The baseline makes their falsification conditions more concrete through C-/A-case IDs and S-scorecard criteria, but intentionally does not strengthen them merely because they align with the project constitution.

Later issue PRs must record explicit hypothesis status changes when evidence is actually produced.

## 11. Handoff to SMX-002 and later work

SMX-002 should treat this baseline as its evaluation input, not as a proposed Thing schema. At minimum it should exercise cases spanning visual/media, UI, nested composition, durable references, procedural/physics, networking, persistence, and collaboration-related structural pressure rather than selecting only convenient cases.

For each architecture candidate, report the C-/A-cases exercised and applicable S-criteria. Cases not evaluated remain visible as `N/E`, not silently assumed to pass.
