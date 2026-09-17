# SplashMX decision and evidence log

This is a compact durable register. Detailed research belongs in issue-specific documents; this file records what the project currently believes, why, and where to retrieve the evidence.

## Status vocabulary

- **FACT** — current primary-source fact, version/date sensitive where applicable.
- **HYPOTHESIS** — proposition awaiting or undergoing falsification.
- **DECISION** — accepted project choice supported by available evidence.
- **OPEN** — unresolved question/blocker.
- **REJECTED** — considered direction that should not be silently reintroduced without new evidence.

## Initial planning review — 2026-09-17

### D-001 — Research before production editor

**Status:** DECISION

The project will not begin by reproducing a Flash-style editor UI. The object/execution/document/security/lifecycle model must be investigated first, then projected upward into authoring UX.

**Reason:** beginning with familiar editor metaphors risks hard-coding Flash or Godot assumptions before the platform semantics are understood.

**Source:** `docs/00-PROJECT-CONSTITUTION.md`, `docs/01-RESEARCH-ROADMAP.md`.

### D-002 — Godot is substrate, not canonical public contract

**Status:** DECISION

SplashMX will initially target Godot as runtime/rendering substrate while owning its durable author-facing object/document/package semantics.

**Reason:** long-lived creations, sandboxed user logic, collaboration, partial streaming, migrations, and topology-independent networking should not be coupled unnecessarily to Godot internal serialization or scene semantics.

**Source:** Constitution P10/P12; Hypotheses H-007/H-014/H-018.

### D-003 — Runtime multiplayer and collaborative editing are distinct consistency problems

**Status:** DECISION

They may share infrastructure but must be researched and specified separately.

**Reason:** runtime simulation asks for timely authority/replication of live state; collaborative editing asks for durable reconciliation of concurrent document changes, including offline edits.

**Source:** Constitution P7/P8; H-013; SMX-010/011 roadmap entries.

### D-004 — No arbitrary GDScript as the default community execution model

**Status:** DECISION

Community/user-authored executable intent must pass through a constrained, inspectable, budgetable execution boundary unless later evidence justifies a strictly controlled exception.

**Reason:** arbitrary engine-level code defeats the intended capability sandbox and long-term portable execution contract.

**Source:** Constitution P9; H-006/H-009.

### D-005 — Generic runtime/player is the preferred publishing hypothesis

**Status:** HYPOTHESIS/PROVISIONAL DIRECTION

Ordinary published creations should ideally be packages consumed by versioned generic web/native/server players rather than independently compiled Godot projects.

**Must be tested by:** SMX-009, SMX-014, SMX-017, SMX-019.

### D-006 — Destructive prototypes precede Architecture v1.0

**Status:** DECISION

Architecture freeze is gated on integrated object-fabric, sandbox, network, collaboration, and browser vertical-slice falsification work.

**Source:** Constitution P15; SMX-015 through SMX-020.

## SMX-001 baseline methodology — 2026-09-17

### D-007 — Stable evaluation IDs and explicit not-evaluated state

**Status:** DECISION

Representative cases use stable `C-###` IDs, adversarial variants use `A-###`, and scorecard criteria use `S-##`. Later research must state which applicable cases were exercised. An omitted case is `N/E` (not evaluated), not implicitly passing.

**Reason:** universal-architecture claims need a reproducible cross-domain corpus and must not silently cherry-pick friendly examples.

**Source:** `docs/research/SMX-001-RESEARCH-BASELINE.md`, `docs/research/SMX-001-EVALUATION-CORPUS.json`.

### D-008 — Scorecards do not waive constitutional hard gates

**Status:** DECISION

Candidate architectures may be scored 0–3 per criterion with evidence, but the project does not use an aggregate score to average away a hard-gate failure.

**Reason:** a model that is elegant in most dimensions but grants ambient authority, conflates hierarchy with authority, or cannot preserve identity is not acceptable merely because its arithmetic average is high.

**Source:** SMX-001 research baseline, scorecard S-01–S-16.

### D-009 — Research harness results require reproducibility metadata

**Status:** DECISION

Executable research must name its question, hypothesis IDs, corpus IDs, source commit, runtime/library versions, commands, seeds/fixtures, expected invariant, observed result, and environmental caveats where relevant.

**Reason:** pre-architecture evidence must be independently reproducible and must not become architecture by prototype inertia.

**Source:** SMX-001 research baseline section 9; AGENTS prototype discipline.

## SMX-002 Thing-kernel research — 2026-09-17

### D-010 — Durable Thing identity must not be derived from hierarchy or engine handle

**Status:** DECISION at the semantic-requirement level; exact encoding remains open.

A Thing that is logically the same entity across rename, reparent, controller/authority transfer, save/load, or stream-out/in must retain a stable opaque identity distinct from label, containment path, Godot `NodePath`, process pointer, physics RID, or network peer ID.

**Reason:** C-006/C-007/C-012/C-017/C-021 and A-001/A-016 make ordinary reparent/control operations incompatible with path-derived identity. The SMX-002 experiment directly demonstrates reparent/control/authority/engine-handle independence.

**Source:** `docs/research/SMX-002-THING-KERNEL.md` K-001/K-002/K-010; fixtures T-001/T-007. Exact namespaces, generation, non-reuse, and tombstone semantics remain SMX-005/007 work.

### D-011 — Containment, control, authority, observation, persistence, and replication are separate explicit semantics

**Status:** DECISION at the object-fabric semantic level.

SplashMX must not use one overloaded `owner`/parent relation to stand for these dimensions. Containment is one typed relationship. Current controller and simulation authority are explicit runtime/context bindings; observation is explicit; persistence/replication policy is declared separately from the currently active service/session.

**Reason:** C-007/C-020/C-021 and A-016 require these relationships to differ simultaneously. T-001/T-002 demonstrate that changing containment need not mutate the others.

**Source:** SMX-002 Thing-kernel research K-003/K-004; T-001/T-002.

### D-012 — Intrinsic declaration and runtime/editor context are separate planes

**Status:** DECISION at the semantic level.

Thing state/facets may declare capability requirements, persistence eligibility, network policy, presentation, behaviour parameters, and intrinsic values. Current capability grants, active controller/authority, replication recipients, save service, editor selection, cache residency, diagnostics, and engine handles are context unless an explicit higher-level operation persists/projects them.

**Reason:** this avoids transient runtime/editor facts silently becoming durable Thing meaning and allows the same Thing to execute under different users, peers, services, and engine handles.

**Source:** SMX-002 K-005/K-006/K-010; T-003/T-007.

### D-013 — Command/event/value is the current candidate port vocabulary, not a frozen protocol

**Status:** HYPOTHESIS/PROVISIONAL DIRECTION.

SMX-002 found `command`, `event`, and directional `value` ports sufficient for its basic UI/cross-Thing cases. First-class query/request-response remains unresolved.

**Reason:** a pure message model is awkward for continuous author-facing value binding, while a pure reactive-value model is awkward for discrete intent/occurrence. The three-way vocabulary covers C-003/C-004 without yet choosing scheduling/IR semantics.

**Must be tested by:** SMX-004 against C-005/C-009/C-025 and A-004/A-006 plus async/query cases.

### D-014 — The current kernel candidate is faceted Thing + explicit relation graph

**Status:** HYPOTHESIS/PROVISIONAL DIRECTION for downstream falsification, not Architecture v1.0.

The candidate combines stable Thing identity, intrinsic state namespaces, optional facets, explicit ports/interfaces, first-class typed relationships, and explicit runtime/editor context bindings. Storage layout and implementation technology are intentionally unspecified.

**Reason:** it maps all C-001–C-028 without a second base-object category and has no observed hard-gate failure in the SMX-002 scope. The executable slice exercises A-001/A-014/A-016 and capability/port/behaviour-identity cases.

**Must be tested by:** SMX-003/004/005 and later SMX-015 destructive integration.

## Initial primary-source snapshot — repository creation, 2026-09-17

These observations were planning inputs. For later research, use the more explicit SMX-001 freshness policy and E-006–E-014 refresh below; relevant issues must still re-check current upstream state.

### E-001 — Godot web editor export limitation

**Status:** FACT, time-sensitive.

Godot `latest` documentation states that the web editor cannot perform project exporting; source can be downloaded and exported with a native editor.

Primary source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

Implication: a SplashMX browser editor should not assume it can invoke the ordinary native Godot export pipeline. This supports investigating generic precompiled players/packages.

### E-002 — Godot web renderer/platform constraints

**Status:** FACT, time-sensitive.

Godot documentation describes web export using WebAssembly/WebGL and the Compatibility renderer. Single-threaded web export is documented as the preferred/default approach for broad hosting compatibility; threaded web builds impose additional cross-origin-isolation constraints.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

Implication: web-first architectural experiments should explicitly record whether they require threading and avoid assuming native rendering/runtime features exist in browser builds.

### E-003 — Custom Godot web build can reduce JavaScript exposure

**Status:** FACT, time-sensitive.

Godot compiling-for-web documentation exposes build options including disabling JavaScript `eval`/bridge support.

Primary source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

Implication: SMX-006/016 should evaluate hardened custom runtime builds instead of assuming stock export templates are the final security boundary.

### E-004 — Godot runtime/package facilities are useful but not automatically safe for untrusted executable content

**Status:** FACT/DESIGN INPUT, time-sensitive.

Godot documents runtime file loading and PCK/ZIP/mod mechanisms. Relevant Godot packaging documentation warns against treating untrusted executable pack content as safe.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html

Implication: use Godot I/O facilities where useful, but do not equate a Godot PCK containing scripts with a SplashMX-safe community package.

### E-005 — Godot networking is candidate substrate, not settled SplashMX protocol

**Status:** FACT/DESIGN INPUT, time-sensitive.

Godot provides high-level multiplayer facilities and browser-appropriate networking options including WebSocket/WebRTC, plus dedicated/headless server paths. Its abstractions are closely integrated with Godot runtime concepts.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/stable/classes/class_websocketmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/classes/class_webrtcmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

Implication: SMX-009/010/017 must compare direct adoption, lower-level use, and hybrid mapping instead of inheriting Godot networking semantics by default.

## SMX-001 primary-source refresh — checked 2026-09-17

The authoritative freshness rules are in `docs/research/SMX-001-RESEARCH-BASELINE.md`. These entries narrow facts and separate them from architectural implications.

### E-006 — Current Godot release context

**Status:** FACT, time-sensitive.

Godot's official archive/download pages list 4.7.2-stable, released 2026-08-18, as the current stable Godot 4 release and 4.8-dev6, released 2026-09-15, as the newest development snapshot on the checked date.

Primary source: https://godotengine.org/download/archive/

**Implication:** `latest` documentation may describe unreleased 4.8 behaviour. Research must record whether evidence comes from stable/versioned or latest/unstable docs.

### E-007 — Web editor remains non-exporting and preliminary

**Status:** FACT, time-sensitive.

Godot `latest` web-editor documentation describes the web editor as preliminary, supports only the Compatibility renderer, lists no project exporting, and describes browser IndexedDB-backed project storage.

Primary source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

**Implication:** SplashMX browser authoring cannot assume access to the normal native Godot export path.

### E-008 — Web export baseline is WebAssembly/WebGL 2 Compatibility

**Status:** FACT, time-sensitive.

Godot 4 web-export documentation states browser export requires WebAssembly and WebGL 2.0 and uses the Compatibility rendering method; Forward+/Mobile are not supported on the web platform in the checked docs.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

**Implication:** browser-baseline architecture must not assume Vulkan/Forward+ semantics.

### E-009 — Single-threaded web export is preferred/default; threading changes hosting requirements

**Status:** FACT, time-sensitive.

Godot web-export documentation states single-threaded web export is the preferred/default path. Enabling thread support requires cross-origin isolation/SharedArrayBuffer-related serving requirements.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

**Implication:** research should justify any dependency on threads rather than assuming them.

### E-010 — Browser background suspension is architecturally relevant

**Status:** FACT, time-sensitive.

Current web-export docs state a project may be paused when its browser tab becomes inactive and note this can cause networked games to disconnect after long enough suspension.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

**Implication:** SMX-010/017 must include lifecycle/reconnect cases such as A-011 rather than assuming continuously ticking browser clients.

### E-011 — Browser networking surface is restricted

**Status:** FACT, time-sensitive.

Current Godot web-export docs state low-level networking is not implemented in web builds; supported browser-facing options include HTTP, WebSocket client, and WebRTC.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

**Implication:** transport availability is substrate policy, not evidence that SplashMX should expose Godot networking semantics publicly.

### E-012 — Custom web templates can omit JavaScriptBridge/eval support

**Status:** FACT, time-sensitive.

Godot compiling-for-web docs state the JavaScriptBridge singleton is included by default/official templates and can be omitted by compiling with `javascript_eval=no`; threads can likewise be disabled with `threads=no`.

Primary source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

**Implication:** SMX-006/016 should test whether a hardened custom runtime materially reduces ambient host exposure.

### E-013 — Runtime file/ZIP loading exists; executable PCK/mod loading is explicitly security-sensitive

**Status:** FACT, time-sensitive.

Godot runtime I/O docs describe runtime user-content loading and ZIP access. Godot pack/mod docs warn that loaded PCKs may contain malicious code and identify compromised or replaced packs as a security risk.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html

**Implication:** Godot I/O can be implementation substrate, but an untrusted SplashMX package must not simply become an executable Godot mod pack.

### E-014 — Headless/dedicated execution and WebRTC substrate are available

**Status:** FACT, time-sensitive.

Godot 4 documentation supports `--headless`/dedicated-server execution. Godot's WebRTC documentation describes browser-available peer/data-channel support and signalling as part of establishing peer connections.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html
- https://docs.godotengine.org/en/stable/tutorials/networking/webrtc.html

**Implication:** peer and authoritative server experiments are plausible substrate directions, but their semantics remain unresolved until SMX-009/010/017.

## SMX-002 comparative-model evidence — checked 2026-09-17

These are conceptual F4 inputs and current documentation examples. They justify comparisons, not adoption of the referenced frameworks.

### E-015 — Godot's core project composition is scene/node-tree oriented

**Status:** FACT / conceptual comparison input.

Godot 4.7 documentation describes games as trees of nodes grouped into reusable scenes and documents hierarchical node lookup.

Primary sources:

- https://docs.godotengine.org/en/4.7/getting_started/introduction/key_concepts_overview.html
- https://docs.godotengine.org/en/4.7/tutorials/scripting/nodes_and_scene_instances.html

**Implication:** this is an efficient substrate model, but SplashMX durable identity/relationship semantics must not assume hierarchy/path equivalence.

### E-016 — ECS precedent separates unique entities, optional components, and explicit relationships

**Status:** FACT / conceptual comparison input.

Bevy's ECS guide describes entities as unique things with sets of components processed by systems. Its relationship facilities demonstrate custom data-driven entity relations in addition to child hierarchy.

Primary sources:

- https://bevy.org/learn/quick-start/getting-started/ecs/
- https://github.com/bevyengine/bevy/blob/main/examples/ecs/relationships.rs

**Implication:** optional facet data and explicit relations are useful precedents; external system ownership of object meaning is not adopted as a SplashMX requirement.

### E-017 — Actor precedent separates stable reference from encapsulated state/behaviour

**Status:** FACT / conceptual comparison input.

Akka documentation describes actors as encapsulated state/behaviour communicating through messages and actor references; behaviour can change while the externally used reference remains stable.

Primary sources:

- https://doc.akka.io/libraries/guide/concepts/akka-actor.html
- https://doc.akka.io/libraries/akka/snapshot/general/actors.html

**Implication:** stable logical address and explicit communication support SMX-002's direction, while mandatory mailbox/scheduler semantics remain deferred to SMX-004.

### E-018 — Prototype delegation is flexible but makes inherited lookup implicit

**Status:** FACT / conceptual comparison input.

MDN's prototype-chain guide documents dynamic delegation/inherited-property lookup through mutable prototype chains.

Primary source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Inheritance_and_the_prototype_chain

**Implication:** prototype/delegation remains a useful comparison for SMX-003 local definitions, but is not selected as the universal Thing kernel because propagation/provenance/conflict semantics must remain explicit.

## SMX-001 hypothesis review

H-001 through H-018 remained **unresolved** after SMX-001. SMX-001 added a falsification corpus and evaluation scorecard but produced no empirical evidence sufficient to strengthen, refine, weaken, or reject architecture hypotheses.

## SMX-002 hypothesis review

- H-001: **strengthened**.
- H-002: **strengthened**.
- H-003: **strengthened, still provisional**.
- H-008: **strengthened**.
- All other hypotheses: no status change from SMX-002.

Detailed evidence and limitations are recorded in `docs/research/SMX-002-THING-KERNEL.md`.

## Open architectural questions

### O-001 — Minimal universal port vocabulary

SMX-002 narrows this to a current candidate of command/event/value ports. Whether query/request-response is first-class, and exact ordering/direction semantics, remain open.

Owner: SMX-004.

### O-002 — Where behaviour state lives

SMX-002 assigns behaviour-private state an explicit facet namespace but does not decide serialization, hot-swap state transfer, or migration compatibility.

Owner: SMX-004/007.

### O-003 — Definition/instance model

Prototype inheritance, structural definitions, patches/overrides, or a hybrid may best fit local classes and collaboration. SMX-002 intentionally leaves open whether a definition is literally a Thing or a Thing-shaped specification sharing the same kernel vocabulary.

Owner: SMX-003/005/011.

### O-004 — Canonical encoding

Human-readable, binary, database-like, or hybrid representations need comparison against diffability, partial loading, deterministic encoding, package size, validation, and migration. SMX-002's object-fabric graph is semantic, not a storage layout decision.

Owner: SMX-005.

### O-005 — Runtime IR shape

Event rules, bytecode, dataflow, state machines, or a hybrid need empirical comparison against determinism, sandboxing, inspectability, hot replacement, authoring projection, and performance.

Owner: SMX-004.

### O-006 — Multiplayer replication boundary

State replication, event replication, simulation inputs, snapshots, or hybrid strategies must align with Thing authority and browser/server topology. SMX-002 separates declaration/policy from current runtime authority but does not select replication mechanics.

Owner: SMX-010/017.

### O-007 — Collaboration substrate

Desired user-visible conflict semantics must be specified before choosing CRDT/OT/operation-log technology. Stable Thing/relation identities are now an input, not a conflict-resolution algorithm.

Owner: SMX-011/018.

### O-008 — Durable identity namespace and tombstones

Path independence is now a semantic requirement. Exact generation format, namespace scope, cross-package addressing, non-reuse, tombstone lifetime, and unresolved/destroyed reference representation remain open.

Owner: SMX-005/007.

## Maintenance rule

When an issue resolves or materially changes an entry here, update this file in the same PR or explicitly supersede it with an ADR referenced here. Do not allow stale early assumptions to remain indistinguishable from current decisions.
