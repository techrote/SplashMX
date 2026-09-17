# SMX-002 — Universal Thing/kernel semantics

Status: candidate pre-architecture semantics for downstream falsification

Issue: SMX-002 / #2

Established: 2026-09-17

This document proposes the smallest currently defensible semantic kernel for a SplashMX **Thing**. It is deliberately not a frozen serialization schema, runtime class hierarchy, Godot mapping, scripting IR, definition/instance model, or package format. Those belong to later research.

The companion experiment under `experiments/smx-002-kernel-model/` and machine-readable fixture manifest `SMX-002-THING-KERNEL-FIXTURES.json` are evidence for the semantic invariants here, not production code.

## Contents

1. Research result — the current candidate in one page.
2. Requirements extracted from SMX-001 — what the kernel must survive.
3. Compared architecture families — scene tree, ECS, actor, prototype/delegation, and the selected hybrid.
4. Candidate kernel — identity, state, facets, ports, relationships, and context.
5. State and context taxonomy — what is intrinsic and what is not.
6. Identity and reference invariants — requirements independent of encoding.
7. Relationship model — containment is only one explicit relationship.
8. Communication boundary — command, event, and value ports.
9. Facets and embodied intent — modular extensions without hidden managers.
10. Corpus mapping — how the candidate addresses C-001 through C-028.
11. Adversarial findings — what the executable model demonstrates and does not demonstrate.
12. Scorecard assessment — evidence-based scores and explicit N/E entries.
13. Rejected or deferred alternatives — why familiar models are not adopted wholesale.
14. Hypothesis status — H-001/H-002/H-003/H-008.
15. Required handoff questions — precise work for SMX-003/004/005.
16. Comparative evidence sources — external conceptual evidence used here.

## 1. Research result

The best current candidate is a **faceted Thing envelope in an explicit object-fabric graph**.

A Thing has exactly one durable logical identity and may declare:

```text
Thing
├─ durable identity
├─ human-facing label/metadata          # never identity
├─ intrinsic state plane
├─ zero or more facets                  # behaviour, presentation, policy, etc.
├─ zero or more typed ports/interfaces
└─ explicit typed relationships         # held by the object fabric, never inferred from ancestry

Runtime/editor context
├─ capability grants
├─ active controller bindings
├─ simulation-authority bindings
├─ replication/session bindings
├─ persistence-service bindings
├─ editor selection/presence
└─ engine/runtime handles
```

The important distinction is semantic, not storage layout: **Thing meaning is the Thing plus its declared facets/interfaces and explicit object-fabric relationships.** A coordinator may index or schedule these declarations, but must not secretly become the only place where their meaning exists.

The candidate deliberately separates **declaration** from **current context**. A Thing may declare that a behaviour requires an HTTP capability, that a state cell is persistable, or that a value is eligible for replication. Whether HTTP is currently granted, which save service is active, or which peer currently has authority is runtime context, not intrinsic Thing state.

The candidate does not require every Thing to carry every facility. A static drawing may have identity + authored state + presentation facet only. A networked vehicle can additionally expose behaviour, control/authority bindings, network policy, and ports. This is how the same kernel remains lightweight enough for C-028 while being expressive enough for C-007/C-020/C-021.

### Candidate kernel invariants

- **K-001 — identity is path-independent:** renaming or reparenting must not change durable Thing identity.
- **K-002 — names are labels, not addresses:** human-readable names can collide or change without repairing references.
- **K-003 — containment is one relationship:** containment cannot imply control, authority, persistence, replication, or behaviour ownership.
- **K-004 — relationship mutation is explicit:** changing one relationship cannot silently rewrite unrelated relationship classes.
- **K-005 — context is not intrinsic state:** editor selection, active peer, capability grants, engine handles, and cache residency stay outside canonical Thing state unless explicitly projected into a separate persistent/runtime record.
- **K-006 — declaration and grant are distinct:** a capability request, persistence policy, or network policy may be intrinsic; the current grant/service/authority is contextual.
- **K-007 — facets are optional extensions:** no category-specific manager is required to make a Thing meaningful.
- **K-008 — facet-private state has an explicit namespace:** it is not silently mixed into public Thing state.
- **K-009 — interfaces are explicit:** cross-Thing effects must target declared ports/relationships rather than depend on traversal/path magic.
- **K-010 — engine handles are replaceable context:** a Godot `Node`, physics RID, audio handle, or network peer ID cannot be the durable Thing identity.
- **K-011 — same kernel can describe a group:** a group does not require a second base object system merely because it has containment relations.
- **K-012 — unresolved targets are representable:** a durable reference can remain meaningful when its target is currently absent; destruction/tombstone semantics remain for SMX-005/007.

## 2. Requirements extracted from SMX-001

The following corpus pressure is decisive for SMX-002.

- C-004 requires a slider to affect audio without either object becoming the semantic owner of the other.
- C-006/C-012 require durable references independent of current containment or residency.
- C-007 requires person, crew, vehicle, convoy, controller, and authority to remain separable.
- C-020 requires a local-only HUD to observe networked state without automatically becoming replicated state.
- C-021 requires control and simulation authority to move independently while Thing identity remains stable.
- C-022 requires requested capabilities to be distinguishable from granted capabilities.
- C-024 requires later lifecycle work to distinguish intrinsic state from reconstructible context.
- C-025 requires behaviours to be replaceable without redefining Thing identity.
- C-027 requires an exposed interface to survive internal nesting/streaming decisions.
- C-028 makes mandatory per-Thing machinery an architectural cost rather than a free abstraction.
- A-001 forbids reparenting from changing unrelated semantics.
- A-014 forbids hidden coordinators from being the only repository of Thing meaning.
- A-016 requires multiple simultaneous relationship classes without collapsing them into an overloaded `owner` field.

These cases make a plain tree node, class instance, or ECS entity insufficient **by itself** as the public semantic contract.

## 3. Compared architecture families

### 3.1 Godot/scene-tree-centric object

A tree node with script/state is an excellent engine implementation unit. Godot itself describes games as trees of nodes and scenes, provides path-based node access, and uses node hierarchy/ownership for several engine/editor behaviours.

Strengths:

- direct fit to the intended runtime substrate;
- excellent composition for rendering, transforms, UI, and lifecycle callbacks;
- scenes provide reusable nested structures.

Problems as the SplashMX kernel:

- it makes containment exceptionally prominent and therefore invites accidental hierarchy/ownership conflation;
- Godot `NodePath` is explicitly hierarchical, while H-008 requires references that survive rename/reparent;
- engine `owner`, parent/child lifetime, scene persistence, and high-level RPC semantics have meanings that are useful internally but are not the same as SplashMX control, authority, persistence, or durable identity;
- C-007/A-016 need several orthogonal relationships that should not be encoded by rearranging the tree.

Conclusion: **implementation substrate, rejected as the public semantic kernel.**

### 3.2 ECS-style entity + components + systems

Bevy's ECS documentation describes entities as unique things with sets of components, processed by systems; current Bevy also supports explicit data-driven entity relationships distinct from its canonical child relationship.

Strengths:

- optional components/facets fit C-028 and avoid a large mandatory base class;
- data-driven composition discourages deep inheritance;
- explicit relationship components demonstrate that hierarchy need not be the only relation;
- good performance precedent for many lightweight entities.

Problems if adopted literally:

- behaviour usually lives in external systems, which can recreate the hidden-manager problem P4/A-014 warns against;
- systems can make an entity's intent hard to inspect locally unless the entity explicitly declares which behaviours apply;
- definition/instance, ports, sandboxing, and author-facing intent are not solved by ECS itself.

Conclusion: **adopt component/facet and explicit-relation lessons; reject external-system ownership of meaning as the SplashMX contract.**

### 3.3 Actor-style identity + state + behaviour + messages

Akka's actor documentation is useful precedent: actors encapsulate state and behaviour behind an address/reference, communicate by messages, and can change behaviour while references remain valid.

Strengths:

- strong identity/address separation from implementation location;
- local state + explicit message boundary aligns with inspectability and sandboxing;
- behaviour can change behind a stable reference, relevant to C-025;
- naturally distinguishes communication from direct shared mutable state.

Problems if adopted literally:

- a mandatory mailbox/sequential-message execution model is too early a commitment for animation, physics, reactive values, and high-frequency media;
- actor supervision hierarchy has semantics SplashMX must not accidentally import into containment;
- pure message passing is awkward for author-facing continuous/value bindings such as C-004 unless higher-level semantics are added.

Conclusion: **adopt stable-address, encapsulation, and explicit-message lessons; reject mandatory actor scheduling/mailbox semantics at kernel level.**

### 3.4 Prototype/delegation object

Prototype systems demonstrate that reusable behaviour/state can be delegated dynamically and modified without a conventional class hierarchy. JavaScript's prototype chain is a familiar contemporary example.

Strengths:

- attractive precedent for local definitions and dynamic composition;
- supports late binding and shared reusable structure.

Problems at kernel level:

- implicit lookup through a delegation chain can make provenance and migration difficult to inspect;
- changing a prototype can change many instances implicitly, exactly where SMX-003/005/011 need explicit override/conflict semantics;
- inheritance/delegation answers a different question from control, authority, persistence, and network relations.

Conclusion: **retain as a comparison for SMX-003; do not make delegation the universal kernel.**

### 3.5 Faceted Thing + explicit relation graph

This candidate combines the useful parts above without inheriting their full execution models.

- unique stable identity from entity/actor precedents;
- optional local facets from component systems;
- explicit ports from actor/dataflow ideas;
- explicit typed relations rather than hierarchy inference;
- context/service bindings outside intrinsic state;
- no mandated scheduler, serialization encoding, definition inheritance, or Godot node mapping yet.

This candidate is selected for downstream falsification because it has no hard-gate failure in the SMX-002 scope and directly addresses A-001/A-014/A-016. It remains provisional until later destructive harnesses.

## 4. Candidate kernel

The semantic model is:

```text
ObjectFabric
├─ Thing[ThingId]
│  ├─ label / author metadata
│  ├─ intrinsic state namespaces
│  ├─ facet bindings
│  └─ port declarations
├─ Relationship[RelationId]
│  ├─ kind
│  ├─ source endpoint
│  ├─ target endpoint
│  ├─ semantic scope
│  └─ optional explicit attributes
└─ ContextBindings
   ├─ current control
   ├─ current simulation authority
   ├─ capability grants
   ├─ persistence service/session
   ├─ replication/session/relevance
   ├─ editor collaboration presence
   └─ engine/runtime handles
```

The diagram is conceptual. SMX-005 must decide whether relationship records are stored top-level, adjacent to Things, in a graph table, or in another canonical encoding. Storage location must not alter semantics.

### 4.1 What is mandatory

Every live/authored Thing needs:

1. a stable logical identity;
2. a way to carry intrinsic state, even if empty;
3. a way to expose zero or more interfaces/ports;
4. a way to attach zero or more facets;
5. participation in zero or more explicit relationships.

A static Thing can therefore be very small. Presentation, behaviour, networking, physics, persistence, and security declarations are not mandatory heavyweight base-object subsystems.

### 4.2 What is explicitly not in the kernel

The kernel does not select:

- a scheduler or event-loop algorithm;
- a bytecode/IR;
- a Godot node type;
- a serialization syntax;
- a UUID/ULID implementation;
- inheritance/prototype semantics for local definitions;
- a physics representation;
- multiplayer topology;
- CRDT/OT/collaboration mechanics.

Those are deliberate downstream questions.

## 5. State and context taxonomy

### 5.1 Authored intrinsic state

Durable author configuration belonging to the Thing's definition/instance: text, initial transform, behaviour parameters, visual choices, timeline keys, exposed values, and similar data.

### 5.2 Live intrinsic state

Current simulation state associated with the logical Thing: current transform, open/closed value, health, velocity, or other mutable values. Live state is not automatically canonical project state and is not automatically persistent.

### 5.3 Facet-private state

State private to one attached facet, namespaced by facet attachment identity. This supports encapsulation and future hot-swap/migration work without making internal counters or FSM state public Thing properties.

SMX-004/007 must decide which private state can serialize, persist, migrate, or transfer during replacement.

### 5.4 Persistence is a projection, not a fourth intrinsic bag

A persistence facet/policy should select which authored/live/facet-private state participates in a save/world snapshot. The saved result is a separate artefact/context, not another always-live property bag that can drift independently.

### 5.5 Context state

The following are contextual by default and must not silently enter intrinsic Thing state:

- editor selection, hover, gizmo state, presence cursors;
- current cache/stream residency;
- Godot node/resource/RID handles;
- current local user or peer connection;
- current controller binding;
- current simulation-authority binding;
- active replication recipients/relevance set;
- capability grants;
- active storage/save service;
- diagnostics/profiling counters.

A product feature may intentionally persist some context-derived value, but that requires an explicit projection/decision.

## 6. Identity and reference invariants

SMX-002 strengthens H-008 at the semantic-requirement level.

A durable Thing identity must:

- be opaque to authors in ordinary workflows;
- not be derived from human label, containment path, render node path, index, network peer ID, or process memory address;
- survive rename;
- survive reparent/regroup operations;
- survive save/load and stream-out/in where the Thing is considered the same logical entity;
- remain unchanged when control or simulation authority transfers;
- be distinguishable from a runtime handle;
- have non-reuse/tombstone semantics precise enough for collaboration and destroyed-target handling, to be specified by SMX-005/007.

The exact encoding and namespace are deferred. `ThingId` in experiments is deliberately a string token such as `thing:key`; this is not a format decision.

References must target durable identity plus, where relevant, an explicit port/interface rather than a hierarchy path. An unloaded target may remain a valid unresolved reference. SMX-005/007 must define `unloaded`, `unknown`, `missing`, and `destroyed/tombstoned` precisely.

## 7. Relationship model

The kernel requires first-class **typed relationships**. It does not require all relationship kinds to share one storage or lifecycle policy.

### 7.1 Structural/authored relationships

Examples:

- `contains(parent, child)` — structural/locality relationship;
- `references(source, target)` — durable semantic reference;
- `observes(source, target/interface)` — declared observation;
- `connects(source_port, target_port)` — explicit interface connection.

### 7.2 Runtime/context bindings

Examples:

- `controlled_by(thing, controller)`;
- `authority_at(thing/scope, runtime participant)`;
- `replicated_in(thing/scope, network session/relevance policy)`;
- `persisted_via(thing/scope, save/world service)`.

These are explicit relationships/bindings, but their current values are contextual rather than automatically canonical authored state.

### 7.3 Policy facets

Network, persistence, and capability **policy** can be declared by intrinsic facets:

```text
network policy: position eligible for state replication
persistence policy: open/locked eligible for world save
capability request: clipboard.write optional
```

The current replication peers, save service, or granted clipboard capability live in runtime context.

### 7.4 Mutation rule

Changing a containment relationship changes containment only. If moving a player between vehicles should also change controller, authority, persistence, or replication, that change must be represented as an additional explicit operation/rule.

The executable A-001 fixture enforces this rule.

## 8. Communication boundary

SMX-002 proposes a **minimal candidate port vocabulary** for SMX-004 to test rather than a final execution protocol.

### Command

An input representing intent/request to do something, with no implicit synchronous return value.

Examples: `Door.open`, `Animation.play`, `Spawner.spawn`.

### Event

An output representing that something occurred.

Examples: `Button.clicked`, `Door.opened`, `Timeline.marker_reached`.

### Value

A typed state/value endpoint with explicit readable/writable directionality.

Examples: slider value, volume, colour, score, target position.

This supports the most common author-facing cases without requiring every continuous value change to become an actor message or every click to become a mutable boolean.

A first-class `query` primitive is **not selected yet**. Simple reads can use readable values; asynchronous request/reply can be composed from a command + correlation + reply event. SMX-004 must test whether that remains comprehensible and deterministic for nontrivial cases.

Connections must refer to durable Thing/interface identity, not traversal paths.

## 9. Facets and embodied intent

A facet is an optional, explicitly attached semantic extension. Candidate facet roles include:

- behaviour;
- presentation;
- physics;
- persistence policy;
- network/replication policy;
- capability request;
- accessibility/localisation metadata;
- editor-only authoring metadata where it genuinely belongs to the authored Thing.

A facet may contribute:

- configuration;
- private state namespace;
- ports;
- declared requirements on other ports/facets/runtime services.

The kernel does **not** say that all facets are executable components. Presentation and policy facets may be declarative. SMX-004 decides behaviour execution; SMX-006 decides capability enforcement.

The crucial embodied-intent rule is:

> An external system may schedule, index, render, simulate, persist, or replicate a Thing, but it must do so from explicit Thing/facet/relationship declarations rather than by owning secret per-Thing semantic configuration that cannot be reconstructed.

This permits efficient centralized systems internally without recreating a `MovementManager`, `NetworkManager`, or `SaveManager` as the hidden source of each object's meaning.

## 10. Corpus mapping

The mapping below records whether the candidate **semantic kernel** can represent the case. It does not claim the downstream mechanism is implemented.

| Case | Kernel mapping | Status at SMX-002 |
|---|---|---|
| C-001 | presentation facet + authored value/timeline references | representable |
| C-002 | same Thing kernel plus containment/definition reference; exact instance model deferred | representable, SMX-003 detail |
| C-003 | presentation facet + state + `clicked` event port | representable |
| C-004 | slider value port connected to audio writable value; no ownership relation | exercised conceptually/fixture |
| C-005 | behaviour/physics/presentation facets + control binding + observer camera | representable |
| C-006 | ThingId-based reference survives containment change/unloaded target | exercised |
| C-007 | nested containment + independent control/authority bindings | exercised |
| C-008 | timeline/media facets and event/value interfaces | representable |
| C-009 | behaviour/procedural facet + explicit generated Thing identities | representable; generation semantics deferred |
| C-010 | physics facet uses engine handle as context, not identity | representable |
| C-011 | group-as-Thing + exposed ports/facets | representable; component packaging deferred |
| C-012 | durable identity/reference can remain unresolved while target absent | representable; lifecycle semantics deferred |
| C-013 | per-Thing controller + network policy/session bindings | representable; protocol deferred |
| C-014 | explicit authority binding distinct from controller | representable |
| C-015 | persistence policy + world/save service binding | representable; save contract deferred |
| C-016 | stable identity gives delete/edit conflict a durable subject | representable; conflict semantics deferred |
| C-017 | containment is an explicit relationship operation | representable |
| C-018 | definition/instance distinction can be layered over same interfaces; exact model deferred | representable, SMX-003/005 detail |
| C-019 | canonical authored state/context split supports offline document work | representable; collaboration deferred |
| C-020 | observation relation + local context without replication policy | exercised conceptually |
| C-021 | controller and authority are separate bindings; ThingId unchanged | exercised |
| C-022 | capability request facet distinct from runtime capability grant | exercised |
| C-023 | kernel semantics do not depend on Godot type IDs; schema migration deferred | representable |
| C-024 | intrinsic/context/private-state taxonomy supplies lifecycle categories | representable; exact restore deferred |
| C-025 | behaviour facet can be replaced while ThingId remains | identity aspect exercised; state handoff deferred |
| C-026 | facet/definition dependency can be explicit rather than hidden | representable; package resolution deferred |
| C-027 | external connections target exposed interface identity, not inner path | representable; stream behaviour deferred |
| C-028 | optional facets keep mandatory core small; performance not yet benchmarked | structurally representable, S-14 N/E |

No C-case required a second incompatible base semantic system during this mapping. That strengthens H-001 but does not prove runtime performance, serialization, collaboration, or network correctness.

## 11. Adversarial findings

The dependency-free experiment executes the following named invariants:

- **A-001:** reparenting changes the `contains` relation and leaves ThingId, state, reference relation, controller, and authority untouched.
- **A-014:** semantic reconstruction uses Thing/facet/relationship records; a scheduler/index is not required to contain hidden per-object meaning.
- **A-016:** containment, control, authority, observation, persistence-service, and replication-session relationships can coexist without one overloaded owner field.
- **C-022/A-003 boundary:** capability request stays intrinsic while grant stays in context.
- **C-025 identity slice:** replacing a behaviour facet does not replace ThingId.
- **C-003/C-004 communication slice:** command/event/value ports can express click-to-command and value-to-value cases.

The experiment intentionally does **not** prove:

- hot-swap private-state migration;
- event ordering or deterministic scheduling;
- serialization/restore;
- stream-out/in;
- collaboration convergence;
- network replication correctness;
- capability enforcement against hostile code;
- object-count performance.

Those scorecard entries remain N/E or partial.

## 12. Scorecard assessment

Candidate: **Faceted Thing + explicit relation graph, SMX-002 v0**

Cases exercised directly by the model/tests: C-003, C-004, C-006, C-007, C-020, C-021, C-022, C-025; adversarial A-001, A-003 (declaration/grant boundary only), A-014, A-016.

| Criterion | Score | Evidence |
|---|---:|---|
| S-01 author-facing simplicity | N/E | no editor/user workflow built yet |
| S-02 semantic coherence | 2 | same Thing/facet/relation vocabulary maps all C-001–C-028 |
| S-03 hierarchy independence | 3 | A-001/A-016 executable invariants; control/authority not mutated by reparent |
| S-04 identity/reference stability | 2 | rename/reparent/authority-transfer slices use stable ThingId; save/load/stream/collab still pending |
| S-05 behaviour composability | 1 | facet attachment/replacement supports identity independence; scheduling/state handoff deferred |
| S-06 lifecycle/restore completeness | N/E | SMX-007 |
| S-07 streaming/partial-load fitness | 1 | unresolved durable reference representable; actual streaming deferred |
| S-08 sandboxability | 1 | capability request/grant split exists; enforcement deferred |
| S-09 multiplayer topology fitness | 1 | controller/authority/network policy separated; topology tests deferred |
| S-10 collaboration fitness | 1 | stable IDs and explicit relationship operations are mergeable subjects; conflict semantics deferred |
| S-11 migration/longevity | 1 | engine handles excluded from identity; schema migrations deferred |
| S-12 Godot-boundary discipline | 3 | candidate semantics use no NodePath/Resource/RPC identity |
| S-13 testability/reproducibility | 2 | dependency-free executable invariants + fixture manifest in CI |
| S-14 performance proportionality | N/E | no benchmark |
| S-15 failure clarity | 1 | missing capability/unresolved target are explicit categories, full failure taxonomy deferred |
| S-16 progressive-disclosure continuity | N/E | SMX-012 |

Hard-gate failures among evaluated criteria: **none observed**. Hard-gate criteria marked N/E are not treated as passing.

## 13. Rejected or deferred alternatives

### Rejected: hierarchy path as durable identity

Fails C-006/C-012/A-001 and creates repair work after ordinary editing. Godot `NodePath` remains useful as a transient implementation locator only.

### Rejected: one overloaded owner/controller field

Fails C-007/C-020/C-021/A-016 because containment, input control, simulation authority, observation, persistence, and replication can differ simultaneously.

### Rejected: mandatory external systems as semantic ownership

A centralized scheduler/system may be efficient, but if `MovementSystem` or `NetworkManager` contains the only durable declaration of what a Thing is meant to do, A-014 fails. Systems must consume explicit facets/relations/context.

### Rejected: arbitrary direct object references as the durable public contract

Process pointers/Godot object references cannot survive serialization, streaming, collaboration, or server migration. Runtime handles may cache resolved references but cannot define durable identity.

### Deferred: actor mailbox as universal execution semantics

Useful precedent for encapsulation and stable references, but too constraining before SMX-004 evaluates timeline, physics, continuous values, async work, and deterministic ordering.

### Deferred: ECS as internal runtime storage

Potentially strong for performance and facet storage. SMX-009/015 can evaluate whether an ECS-like internal representation maps efficiently onto Godot. It is not necessary to expose ECS to authors.

### Deferred: prototype/delegation definitions

Promising for local classes, but exact propagation/override/conflict semantics belong to SMX-003/005/011.

## 14. Hypothesis status

### H-001 — One universal Thing model is viable: **strengthened**

The same semantic envelope maps all 28 representative cases without a second base-object category. The executable slice covers UI, cross-object values, durable references, deep nesting/control, local/network context, capabilities, and behaviour replacement identity. This is not yet proof of performance or downstream correctness.

### H-002 — Hierarchy can remain structural rather than semantic ownership: **strengthened**

A-001 and A-016 are directly exercised. Reparenting mutates containment only; independent bindings remain intact.

### H-003 — Group and object can share the same semantic kernel: **strengthened, still provisional**

The experiment represents a group with the same Thing type plus containment relations and an optional coordination facet. No second base representation is necessary for tested cases. SMX-003 must still test definition/instance propagation and complex nested coordination.

### H-008 — Stable identity must be path-independent: **strengthened**

The corpus repeatedly requires logical sameness across reparenting, authority transfer, streaming, and collaboration. The executable model demonstrates rename/reparent/control/authority independence. Exact ID namespace/encoding/tombstone rules remain for SMX-005/007.

No other hypothesis receives a status change from SMX-002.

## 15. Required handoff questions

### SMX-003 — composition/local definitions

Must resolve:

1. Is a reusable definition literally a Thing, a Thing-shaped specification, or a separate definition record sharing the kernel vocabulary?
2. How are definition identity and instance identity separated?
3. How are structural overrides represented and rebased when definitions change?
4. How are inner ports exposed through a group boundary without path coupling?
5. Which containment relations affect transform/locality, and are multiple containment/locality concepts required?
6. Can group coordination remain an explicit facet rather than ancestor-owned implicit behaviour?

Required corpus emphasis: C-002/C-006/C-007/C-011/C-017/C-018/C-027 and A-001/A-008/A-016.

### SMX-004 — behaviour execution and IR

Must resolve:

1. Validate or reject the command/event/value port vocabulary; determine whether query/request is first-class.
2. Define event/command ordering and mutation visibility.
3. Define facet-private state and hot-swap compatibility/state handoff.
4. Define requirements/provides semantics between facets and ports.
5. Define resource budgets and async/timer semantics.
6. Decide whether behaviour facets compile to one constrained IR or require multiple execution classes.

Required corpus emphasis: C-003/C-004/C-005/C-009/C-025 and A-004/A-006.

### SMX-005 — canonical document/identity

Must resolve:

1. Exact durable ID namespaces and generation/non-reuse rules for Things, definitions, ports, relationships, assets, revisions, and worlds.
2. Representation and lifecycle of unresolved versus destroyed/tombstoned references.
3. Whether relationship records are top-level graph records, endpoint-owned records, or another encoding without changing semantics.
4. State cell identity/schema and authored/live/save snapshot separation.
5. Canonical representation of facet attachments and private state.
6. Patch/transaction operations for reparent, relation change, facet replacement, and port connection.
7. Migration/unknown-field policy.

Required corpus emphasis: C-006/C-012/C-016–C-019/C-023/C-024/C-027 and A-002/A-007/A-010/A-013.

## 16. Comparative evidence sources

Checked 2026-09-17. These are conceptual F4 inputs unless otherwise noted; SplashMX does not adopt any model wholesale.

- Godot 4.7 key concepts: https://docs.godotengine.org/en/4.7/getting_started/introduction/key_concepts_overview.html — scenes/nodes as tree-composed engine primitives.
- Godot 4.7 node access: https://docs.godotengine.org/en/4.7/tutorials/scripting/nodes_and_scene_instances.html — hierarchical node lookup is an engine facility, useful as a counterexample for durable path identity.
- Bevy ECS introduction: https://bevy.org/learn/quick-start/getting-started/ecs/ — entities as unique things with sets of components processed by systems.
- Bevy explicit relationship example: https://github.com/bevyengine/bevy/blob/main/examples/ecs/relationships.rs — custom data-driven relationships can coexist with child hierarchy.
- Akka actor model guide: https://doc.akka.io/libraries/guide/concepts/akka-actor.html — encapsulated state/behaviour and message-based cooperation.
- Akka actor reference/behaviour discussion: https://doc.akka.io/libraries/akka/snapshot/general/actors.html — references shield implementation state and behaviour can change behind a stable reference.
- MDN prototype-chain guide: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Inheritance_and_the_prototype_chain — prototype/delegation precedent and dynamic chain mutation, considered for later local-definition research rather than selected as kernel semantics.

## Conclusion

SMX-002 does not establish a production class hierarchy. It establishes a stronger semantic constraint:

> **A SplashMX Thing is a stable identity participating in explicit state, facet, interface, and relationship semantics; current runtime/editor authority is supplied through explicit context rather than inferred from containment or hidden managers.**

This candidate survived the SMX-002 breadth mapping and executable relationship/identity slice without an observed hard-gate failure. The next work must attempt to break it through definition/instance propagation (SMX-003), behaviour scheduling/state migration (SMX-004), and canonical identity/patch/serialization semantics (SMX-005).