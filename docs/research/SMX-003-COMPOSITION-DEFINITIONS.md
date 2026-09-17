# SMX-003 — Composition, local definitions, instances, and overrides

Status: candidate pre-architecture semantics for downstream falsification

Issue: SMX-003 / #3

Established: 2026-09-17

This document refines the SMX-002 faceted Thing + explicit relation graph into a composition and reuse model. It deliberately does **not** freeze the canonical file encoding, collaboration algorithm, runtime scheduler, package format, or portable-component contract.

The selected candidate is a **stable local-definition graph + concrete instance graph + sparse explicit overlay**. An ordinary authored group can be promoted into a reusable local definition without replacing its existing Things; promotion adds definition provenance while preserving concrete Thing identities and unrelated runtime/context relationships.

The companion experiment under `experiments/smx-003-composition-model/` and `SMX-003-COMPOSITION-FIXTURES.json` are non-normative research evidence for the semantics below.

## Contents

1. Research result
2. Constraints inherited from SMX-001/002
3. Compared definition/instance models
4. Candidate definition and instance model
5. Relationship taxonomy for composition
6. Group-as-Thing semantics
7. Promotion from ordinary structure to local definition
8. Sparse overlay and override semantics
9. Definition revision and instance reconciliation
10. Exposed interfaces and stable external connections
11. Structural conflicts and failure policy
12. Corpus/adversarial evaluation
13. Executable experiment and scorecard
14. Hypothesis status and downstream handoffs
15. Comparative evidence sources

## 1. Research result

The current candidate is:

```text
LocalDefinition[DefinitionId, RevisionId]
├─ DefinitionElement[ElementId]
│  ├─ authored state/facets/ports
│  └─ authored relations using ElementId endpoints
└─ ExposedInterface[PublicPortId]
   └─ binds to an internal ElementId + PortId

Concrete Instance
├─ root ThingId
├─ ElementId -> ThingId provenance map
├─ base DefinitionId + base RevisionId
├─ sparse explicit OverlaySet
│  ├─ value/facet overrides
│  ├─ structural relation overrides
│  ├─ local additions
│  └─ suppressions
└─ normal ObjectFabric context
   ├─ controller
   ├─ simulation authority
   ├─ persistence/session bindings
   └─ replication/session bindings
```

The definition uses the **same authored semantic vocabulary** as a Thing—state, facets, ports, and explicit relations—but definition elements live in a separate durable identity domain from concrete Things. Each concrete instance element receives its own `ThingId` and keeps a provenance link to the `DefinitionId + ElementId` that supplied its inherited authored semantics.

There is no live prototype-chain lookup. The effective instance is a concrete graph plus explicit overlay provenance. Definition revisions are reconciled into instances as explicit transactions. This keeps inherited intent inspectable and makes later collaboration/migration work possible without hidden lookup rules.

### Composition invariants

- **CMP-001 — groups use the Thing kernel:** a group may carry its own state, facets, and ports while containing independently meaningful Things.
- **CMP-002 — containment is not definition membership:** concrete `contains` relations and definition `defines-member` provenance are distinct.
- **CMP-003 — instance provenance is not behavioural ownership:** `instance-of` identifies the authored source of inherited semantics; it does not grant control, authority, persistence ownership, or runtime ownership.
- **CMP-004 — promotion preserves concrete identity:** promoting an existing group/subgraph to a local definition does not reconstruct its existing Things.
- **CMP-005 — definition elements have stable IDs:** overrides and propagation address stable `ElementId`/port IDs, never hierarchy paths or labels.
- **CMP-006 — overlays are sparse and explicit:** an instance stores only intentional departures from its base definition plus local additions/suppressions.
- **CMP-007 — overrides win at their declared semantic locus:** compatible base changes propagate everywhere else without erasing an intentional instance override.
- **CMP-008 — invalidated override targets become explicit conflicts:** removed/type-incompatible elements, facets, properties, or exposed ports are not silently reinterpreted.
- **CMP-009 — destructive propagation is reference-aware:** definition updates do not silently destroy a concrete instance Thing that has protected local state, overrides, local descendants, exposed bindings, or inbound durable references.
- **CMP-010 — public interfaces are stable indirections:** external consumers target the containing/root Thing's public port ID, not internal paths; internal reparenting may rebind implementation without changing the external connection identity.
- **CMP-011 — local additions are first-class instance structure:** instance-only Things can attach to definition-derived structure without becoming part of the base definition until an explicit promote/apply operation.
- **CMP-012 — reparent/control/authority remain orthogonal:** structural movement or definition propagation changes only the explicitly affected structural/provenance semantics unless additional operations say otherwise.

## 2. Constraints inherited from SMX-001/002

SMX-003 must preserve the following accepted semantic decisions:

- durable Thing identity is path-independent;
- containment, control, simulation authority, observation, persistence, and replication are separate semantics;
- runtime/editor context is not silently intrinsic Thing state;
- engine handles are not durable identity;
- group and leaf objects may share the same Thing kernel;
- cross-Thing references and ports are explicit.

The most relevant corpus pressure is:

- **C-002:** nested reusable animated structures with per-instance differences;
- **C-006:** durable references survive grouping/reparenting;
- **C-007:** person → crew → vehicle → convoy while control/authority vary independently;
- **C-011:** nested reusable component with a small public interface;
- **C-017/C-018:** structural and definition-vs-instance concurrent edits must have identifiable semantic loci;
- **C-021:** control/authority transfer cannot be tied to hierarchy;
- **C-027:** externally connected interface must survive internal restructure/stream boundaries;
- **A-001:** reparenting cannot mutate unrelated semantics;
- **A-008:** base structural change versus instance structural override must be explicit;
- **A-016:** several relationship classes must coexist simultaneously.

These cases rule out path-addressed overrides and any model where an instance's meaning is an implicit side effect of its current container.

## 3. Compared definition/instance models

### 3.1 Deep class inheritance

A conventional class hierarchy could encode a base group and subclasses/instances.

Useful lessons:

- named reusable definitions;
- inherited defaults with local specialization.

Problems for SplashMX:

- class ancestry easily becomes behavioural ownership rather than composition;
- structural nested objects do not map naturally to one class chain;
- multiple reusable nested definitions create inheritance/containment ambiguity;
- collaboration and instance provenance become hard to express when behaviour lookup is implicit;
- ordinary authored groups would need conversion into a separate programming-language construct.

**Result:** rejected as the primary authoring/reuse model.

### 3.2 Prototype/delegation lookup

Self demonstrates that prototypes, parent slots, traits, and cloning can provide powerful reuse without mandatory classes. It also demonstrates the cost of highly dynamic implicit lookup: the Self style guide explicitly notes that the language cannot intrinsically distinguish objects playing class-like and instance-like roles.

Useful lessons:

- ordinary objects can become reusable exemplars;
- live systems can avoid a class/instance conceptual cliff;
- delegation can share behaviour flexibly.

Problems for SplashMX:

- implicit lookup makes provenance less inspectable;
- changing a delegate can alter many descendants without an explicit reconciliation transaction;
- structural overrides, migration, collaboration, and old-content compatibility need exact semantic loci;
- dynamic parent changes risk confusing definition ancestry with containment/control relationships.

**Result:** useful conceptual precedent for seamless promotion, rejected as the canonical instance-update mechanism.

### 3.3 Scene inheritance / inherited scene tree

Godot scene inheritance demonstrates a practical base-scene + local-modification workflow. Current stable documentation for imported-scene inheritance also illustrates the structural restrictions common in inheritance-based scene systems: base nodes cannot simply be removed while derived content can add nodes.

Useful lessons:

- familiar WYSIWYG editing of inherited structure;
- direct fit to Godot implementation concepts.

Problems for SplashMX:

- tree position remains too central as the addressing/provenance mechanism;
- base-node restrictions are an implementation/product trade-off, not a semantic requirement SplashMX should inherit automatically;
- scene inheritance does not by itself separate containment from control/authority/persistence;
- portable local definitions should not require Godot scene conversion.

**Result:** useful substrate/editor precedent, not the public definition model.

### 3.4 Prefab/variant + overrides

Unity's current prefab documentation is useful precedent for nested reusable assets whose instances stay linked to a source while carrying property/structural overrides. Prefab variants additionally show that an override set can itself be reusable. Unity also documents restrictions such as inherited-object reparent/removal limits, showing that structural override semantics must be designed explicitly rather than assumed.

Useful lessons:

- source/instance provenance can remain visible;
- sparse overrides are understandable;
- nested definitions can retain their own source links;
- update/revert/apply operations can be explicit author actions.

Problems if copied literally:

- a hierarchy-addressed prefab implementation would conflict with SplashMX path-independent identity;
- “apply to base” semantics need collaboration-safe transactions and capability/security boundaries;
- structural restrictions should be based on semantic safety, not inherited from another engine's representation.

**Result:** strong precedent for sparse explicit overlays; adapted rather than cloned.

### 3.5 Stable definition graph + sparse overlay

This candidate uses:

- stable definition and element identities;
- concrete Thing identities for every instance;
- an explicit provenance map;
- sparse override operations with stable targets;
- local additions/suppressions;
- explicit definition-revision reconciliation.

It retains the usability advantage of prefab/prototype systems while avoiding live implicit inheritance lookup and path-based identity.

**Result:** selected candidate for downstream falsification.

## 4. Candidate definition and instance model

### 4.1 Identity domains

At minimum, SMX-003 requires distinct durable semantic roles:

- `DefinitionId` — reusable local definition identity;
- `RevisionId` — immutable definition revision identity/version marker;
- `ElementId` — stable member identity within the definition lineage;
- `ThingId` — concrete instance/live authored Thing identity;
- `PortId` — stable interface identity scoped to an element/root interface.

SMX-005 decides concrete encodings/namespaces/non-reuse/tombstones.

### 4.2 Definition elements

A `DefinitionElement` contains only authored semantics appropriate to a reusable source:

- authored intrinsic state;
- authored facet declarations/configuration;
- port declarations;
- authored structural/connection relations using stable element/port IDs;
- labels/editor metadata that are explicitly non-identifying.

Runtime controller, authority, cache residency, peer/session, and engine handles do not belong in the definition.

### 4.3 Concrete instance

A concrete instance contains ordinary Things plus provenance:

```text
Instance root ThingId: thing:robot-A
Base: definition:robot @ revision:7
Provenance:
  element:root      -> thing:robot-A
  element:left_arm  -> thing:robot-A-left-arm
  element:right_arm -> thing:robot-A-right-arm
Overlay:
  element:left_arm.state.tint = "rust"
  element:right_arm.parent = element:tool_mount
```

The concrete Things remain valid independent identities. `instance-of` is provenance, not their address and not their controller.

### 4.4 No runtime read-through requirement

The architecture does not require property lookup to walk into the definition at runtime. A player/editor may materialize effective authored state for performance and validation. What must remain durable is the base revision + overlay provenance needed to explain/reconcile the instance.

This distinction reduces accidental prototype semantics and makes package migration/collaboration auditable.

## 5. Relationship taxonomy for composition

The following relationships must remain distinct.

### `contains(parent ThingId, child ThingId)`

Concrete structural/locality relation between live/authored Things. It may affect local transforms/editor grouping, but not controller, authority, identity, persistence, or replication by implication.

### `defines-member(DefinitionId, ElementId)`

Definition composition membership. This answers “which authored elements make up this reusable definition?” It is not a live containment relationship and has no runtime authority semantics.

### `instance-of(ThingId, DefinitionId, ElementId, RevisionId)`

Provenance: which definition element supplied inherited authored semantics to this concrete Thing. It does not mean behavioural ownership.

### `controls(controller, ThingId)`

Current intent-driving relationship, inherited unchanged from SMX-002 context semantics.

### `observes(source, target/interface)`

Explicit observation without implying containment or control.

### `authority-at(scope, runtime participant)`

Current simulation-authority binding. It is contextual, not a definition relationship.

### `coordinates-with`

Not selected as a primitive kernel relationship. Coordination should normally be represented by explicit ports/connections or a coordination behaviour/facet. A named relation can be added later only if it gains precise independent semantics.

This is intentional: the object fabric should not accumulate vague relation names that merely restate hidden manager behaviour.

## 6. Group-as-Thing semantics

A group is an ordinary Thing that participates in `contains` relations.

It may independently have:

- state (for example `enabled`, `formation`, or `selected_variant`);
- behaviour facets (for example synchronise members);
- presentation (for example group-level transform/mask);
- its own ports;
- external references;
- controller/authority/persistence/network policies.

Contained members retain their own Things, facets, ports, and relationships.

Therefore:

```text
Band (Thing)
  contains Guitarist (Thing)
  contains Drummer (Thing)
  contains Singer (Thing)

Band.command:start_song
Band.event:song_finished
```

is valid without making `Band` the behavioural owner of every member. A group behaviour that coordinates members must do so through explicit relationships/ports or declared member interfaces.

Nested composition therefore scales:

```text
Person -> Crew -> Vehicle -> Convoy -> World
```

while controller/authority relationships can point elsewhere at every level.

## 7. Promotion from ordinary structure to local definition

Promotion must not require rebuilding the selected Things.

Candidate operation:

1. Select an authored Thing/subgraph rooted at an existing group or leaf.
2. Mint a new `DefinitionId` and stable `ElementId`s for the selected authored structure.
3. Copy the selected **authored semantic plane** into definition elements: authored state, facets, ports, and authored relations.
4. Record the current concrete Things as the first instance by adding `ElementId -> ThingId` provenance.
5. Set the instance's base revision to the newly created definition revision.
6. Leave concrete Thing IDs, external references, runtime controllers, authority, persistence bindings, and replication context unchanged.
7. Any pre-existing instance-specific authored differences that should not become the reusable base are represented as explicit overlay operations during promotion.

The experiment exercises the simpler case where the selected structure becomes the initial base and the original concrete graph becomes its first instance without identity change.

This satisfies the intended author flow:

```text
ordinary object/group
      ↓ “Make reusable”
local definition + existing first instance
      ↓ “Share/package” later
portable component (SMX-013)
```

No programming-language class declaration is required.

## 8. Sparse overlay and override semantics

An `OverlaySet` records intentional deviations from the chosen base revision.

### 8.1 Value/property override

Targets a stable semantic locus such as:

```text
(ElementId, state namespace/key)
(ElementId, facet attachment/config key)
```

The override remains authoritative at that locus until removed/reverted or made invalid by a schema/structural change.

### 8.2 Structural relation override

Targets a stable relation locus rather than a path. Example:

```text
move element:weapon from element:hand to element:back_mount
```

If the base later reparents `element:weapon`, the instance override continues to win while its target remains valid.

### 8.3 Local addition

An instance may contain a Thing that has no `ElementId` in the base definition. The overlay records its local identity and attachment relation.

A local addition remains local across base updates. “Apply/promote to definition” is a separate explicit authoring transaction.

### 8.4 Suppression/removal override

An instance may intentionally suppress an inherited element/facet/relation without mutating the base definition.

Suppression must not silently destroy externally referenced concrete Things. Runtime/lifecycle details are deferred, but the reconciliation planner must surface protected-reference cases before committing destructive changes.

### 8.5 Why overrides are not “last writer wins” document edits

An override is durable authored intent relative to a definition. It is not a collaboration conflict-resolution algorithm.

For example, if base `speed` changes from 5 to 6 while one instance explicitly overrides speed to 10, the effective instance remains 10. That is expected inheritance semantics, not a conflict.

SMX-011 later decides what happens if two collaborators concurrently edit the same overlay/base records.

## 9. Definition revision and instance reconciliation

Definition edits create a new revision. Instances reconcile from `(old base revision, overlay)` to `(new base revision, rebased overlay)`.

### 9.1 Non-conflicting propagation

- base changes an unoverridden property → instance receives the new value;
- base adds a new element → instance receives a new concrete Thing for that `ElementId`;
- base reparents an unoverridden element → instance follows the new base structure;
- base edits an overridden property → instance override continues to win if semantically compatible;
- base reparents an element that has an instance parent override → instance override continues to win;
- base adds unrelated ports/facets/relations → instance inherits them unless explicitly suppressed.

### 9.2 Conflict conditions

Reconciliation produces an explicit conflict rather than guessing when:

- an overlay target `ElementId` is removed from the new base;
- an overridden property/facet/port changes kind/schema such that the override is no longer type/semantically compatible;
- a local addition's attachment target disappears;
- a public exposure's internal target disappears or becomes incompatible;
- a destructive base change would retire a concrete Thing with protected inbound durable references, unresolved local descendants, or instance-local semantic state that cannot be mapped safely;
- element identity/provenance becomes ambiguous rather than being expressible as a stable-ID change/migration.

A conflict keeps the prior instance revision valid until resolved. The update must not partially mutate unrelated semantics and then fail halfway.

### 9.3 Resolution is explicit

Possible later editor resolutions include:

- keep local element as detached instance-only Thing;
- reattach local addition to another element;
- retarget an override/exposure;
- discard the override/local data;
- accept deletion and tombstone the concrete Thing;
- migrate the override through a declared schema migration.

SMX-005/011 define canonical transaction/conflict records; this issue establishes only the semantic need.

## 10. Exposed interfaces and stable external connections

Nested definitions need a stable external boundary.

A group/definition root can declare a public port:

```text
public port: dialogue.advance
internal binding: element:text_controller.command:advance
```

An external connection targets:

```text
thing:dialogue-instance / port:dialogue.advance
```

It does **not** target:

```text
thing:dialogue-instance/children/panel/text_controller/advance
```

Internal reparenting or replacement can update the exposure binding while preserving the public port identity. This is essential for C-011/C-027.

Rules:

- exposed `PublicPortId` is stable independently of the internal path;
- internal binding endpoints use stable `ElementId + PortId`;
- base update may rebind a public port to a compatible internal endpoint;
- removing/changing a public port is an explicit interface-breaking change;
- if external connections exist, removal/incompatibility must be surfaced before destructive propagation.

This pattern allows encapsulation without sacrificing inspectability.

## 11. Structural conflicts and failure policy

### A-008 — definition update versus structural override

The experiment covers the important distinction:

- base reparents an element while an instance also has a deliberate parent override → the overlay remains authoritative if both endpoints remain valid;
- base removes the overridden element or the overlay's target parent → reconciliation conflicts explicitly.

This avoids both undesirable extremes:

1. silently discarding local structure whenever the base changes;
2. freezing the entire base subtree merely because an instance has one override.

### Protected deletion

A base removal can propagate automatically only when the instance element has no semantic protection requiring human/migration handling. Protection includes at least:

- an overlay targeting the element;
- a local child attached to it;
- an exposed public port targeting it;
- an inbound durable external reference known to the object fabric.

The complete destroyed/tombstone lifecycle belongs to SMX-005/007.

### Transactional requirement

Reconciliation planning must be separable from commit. An instance with conflicts remains at its prior coherent base revision until a valid plan exists. Partial application that leaves provenance half-updated is a hard failure.

## 12. Corpus/adversarial evaluation

| Case | Candidate mapping | SMX-003 status |
|---|---|---|
| C-002 | definition graph + concrete provenance + sparse overlay | exercised |
| C-006 | concrete ThingId/reference unaffected by promotion/reparent | exercised |
| C-007 | nested containment plus independent context relations | exercised |
| C-011 | group/root public interface forwards to internal element port | exercised |
| C-017 | structural relation has stable IDs and explicit operation locus | representable; collaboration merge deferred |
| C-018 | base revision and instance overlay are distinguishable semantic documents | exercised model-level; concurrent edit merge deferred |
| C-021 | controller/authority context survives reparent/update independently | exercised |
| C-027 | public port identity survives internal reparent | exercised |
| A-001 | concrete reparent does not mutate unrelated context | inherited + exercised |
| A-008 | compatible structural override survives base move; invalidated target conflicts | exercised |
| A-016 | composition/provenance/control/authority can coexist | exercised |

The candidate does not claim to solve C-016–C-019 collaboration reconciliation; it provides stable semantic loci needed by SMX-011.

## 13. Executable experiment and scorecard

The dependency-free research harness exercises:

- promotion of an ordinary group without changing existing Thing IDs or controller/authority bindings;
- creation of multiple instances with distinct Thing IDs and common definition provenance;
- instance property override surviving a compatible base update while untouched fields inherit;
- instance structural reparent override surviving a base reparent;
- local addition preservation across base updates;
- explicit conflict when a base removes an element that has an override/local child/inbound durable reference;
- stable public external port through internal reparent;
- conflict when a definition update removes an exposed implementation endpoint;
- group root behaviour/state remaining independent from contained member behaviour/state;
- definition reconciliation leaving context relationships untouched.

### Scorecard impact

- **S-02 semantic coherence: 2** — same Thing/port/relation concepts are retained; definition elements use authored kernel semantics.
- **S-03 hierarchy independence: 3 within scope** — promotion, reparent, and revision propagation do not mutate controller/authority/persistence identity implicitly.
- **S-04 identity/reference stability: 3 within scope** — concrete Thing IDs and external public-port targets remain stable under tested restructure.
- **S-13 reproducibility: 3** — deterministic dependency-free fixtures/tests are in CI.
- **S-15 failure clarity: 2** — invalidated overrides/exposures/deletions become explicit conflicts; canonical conflict encoding remains SMX-005/011.
- **S-16 progressive-disclosure continuity: 2 conceptually** — ordinary group → “Make reusable” → local definition/instance without a programming-language conversion; editor UX remains SMX-012.

Other scorecard dimensions remain unchanged/N/E where SMX-003 provides no direct evidence.

## 14. Hypothesis status and downstream handoffs

### H-002 — strengthened

Composition research adds further executable evidence that hierarchy can remain structural while control/authority and provenance are independent.

### H-003 — strengthened

Groups in the experiment are ordinary Things with their own state/facets/ports and explicit containment. No separate group base-object system is required.

### H-004 — strengthened

An ordinary group can be promoted into a reusable local definition while the existing group becomes the first instance without replacing concrete Thing IDs. Multiple independent instances and overlays are demonstrated. Portable cross-project packaging remains SMX-013, so H-004 is not yet fully proven end-to-end.

### H-005 — unresolved / no direct status change

The definition model supports behaviour/facet overrides structurally, but hot-swap state transfer and executable behaviour compatibility remain SMX-004/007 work.

### Required SMX-004 handoff

SMX-004 must decide:

- whether behaviour attachment identity needs a stable definition-element-local identity distinct from facet type;
- how behaviour private state is scoped across definition revisions and instance overrides;
- how replacing an inherited behaviour with an instance override interacts with hot-swap state transfer;
- whether command/event/value ports remain sufficient under nested exposed interfaces and async behaviour;
- event ordering for definition update/instance reconcile lifecycle hooks.

### Required SMX-005 handoff

SMX-005 must specify canonical representations for:

- `DefinitionId`, immutable revision identity, `ElementId`, `ThingId`, port IDs, and their namespaces;
- base revision + sparse overlay provenance;
- structured override operations and target loci;
- local additions/suppressions;
- exposed interface bindings;
- reconciliation transactions and explicit conflict records;
- protected deletion/inbound-reference checks;
- provenance/tombstone behaviour after base element removal;
- stable references to definition elements versus concrete Things.

### Required SMX-011 handoff

Collaboration semantics must distinguish:

- editing the definition base;
- editing one instance overlay;
- applying/promoting an overlay to the base;
- concurrent structural moves;
- deleting a definition element while another author edits an instance override;
- conflict records produced by definition revision reconciliation versus conflicts produced by concurrent document edits.

### Required SMX-013 handoff

Portable component research should start from the local definition model rather than inventing a second component object system. Packaging should preserve definition/element/public-interface identities and explicit capabilities/dependencies while remaining free to choose external package identity/version semantics.

## 15. Comparative evidence sources

These sources are **comparative evidence**, not adopted platform contracts.

- Godot stable documentation — scene inheritance for imported scenes: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- Unity current manual — introduction to prefabs/nested instances/overrides: https://docs.unity3d.com/current/Manual/prefabs-introduction.html
- Unity current manual — overriding prefab instance data: https://docs.unity3d.com/current/Manual/prefabs-override.html
- Unity 6 manual — prefab variants and structural override restrictions: https://docs.unity3d.com/6000.0/Manual/PrefabVariants.html
- Self Handbook 2024.1 — world organization, traits/prototypes/mixins: https://handbook.selflanguage.org/2024.1/worldorg.html
- Self Handbook 2024.1 — programming-style discussion of shared behaviour/prototypes: https://handbook.selflanguage.org/2024.1/progguid.html
- Self Handbook glossary — prototype, cloning, inheritance, traits definitions: https://handbook.selflanguage.org/2024.1/glossary.html

The design conclusion does not depend on any one engine/language model. Their value is exposing recurring trade-offs: sparse overrides and visible provenance are useful; implicit lookup and path/hierarchy-coupled identity make structural evolution harder to reason about.
