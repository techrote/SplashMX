# SplashMX decision and evidence log

This is a compact durable register. Detailed research belongs in issue-specific documents; this file records what the project currently believes, why, and where to retrieve the evidence.

## Status vocabulary

- **FACT** — current primary-source fact, version/date sensitive where applicable.
- **HYPOTHESIS** — proposition awaiting or undergoing falsification.
- **DECISION** — accepted project choice supported by available evidence.
- **OPEN** — unresolved question/blocker.
- **REJECTED** — considered direction that should not be silently reintroduced without new evidence.

## Project decisions

### D-001 — Research before production editor

**Status:** DECISION.

The object/execution/document/security/lifecycle model is researched before building a production Flash-style editor. Familiar editor metaphors must not hard-code Flash/Godot assumptions.

**Source:** Constitution; research roadmap.

### D-002 — Godot is substrate, not canonical public contract

**Status:** DECISION.

Godot is the intended runtime/rendering substrate, while SplashMX owns durable author-facing object/document/package semantics.

**Source:** Constitution P10/P12; H-007/H-014/H-018.

### D-003 — Runtime multiplayer and collaborative editing are distinct consistency problems

**Status:** DECISION.

They may share infrastructure but are researched/specified separately.

**Source:** P7/P8; H-013; SMX-010/011.

### D-004 — No arbitrary GDScript as the default community execution model

**Status:** DECISION.

Community/user-authored executable intent must pass through a constrained, inspectable, budgetable boundary unless later evidence justifies a controlled exception.

**Source:** P9; H-006/H-009.

### D-005 — Generic runtime/player is the preferred publishing hypothesis

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Ordinary creations should ideally be packages consumed by versioned generic web/native/server players rather than independently compiled Godot projects.

**Tested by:** SMX-009/014/017/019.

### D-006 — Destructive prototypes precede Architecture v1.0

**Status:** DECISION.

Architecture freeze is gated by integrated object-fabric, sandbox, network, collaboration, and browser vertical-slice falsification.

**Source:** P15; SMX-015–020.

### D-007 — Stable evaluation IDs and explicit not-evaluated state

**Status:** DECISION.

Representative cases use `C-###`, adversarial variants use `A-###`, and scorecard criteria use `S-##`. Omitted applicable cases remain `N/E`, not implicitly passing.

**Source:** SMX-001 baseline/corpus.

### D-008 — Scorecards do not waive constitutional hard gates

**Status:** DECISION.

Per-criterion scores are evidence aids, not an aggregate leaderboard. A hard-gate failure cannot be averaged away.

**Source:** SMX-001 S-01–S-16.

### D-009 — Research harness results require reproducibility metadata

**Status:** DECISION.

Executable research records question, hypothesis IDs, corpus IDs, source commit, versions, commands, fixtures/seeds, expected invariant, result, and environmental caveats.

**Source:** SMX-001 baseline; AGENTS.

### D-010 — Durable Thing identity must not be derived from hierarchy or engine handle

**Status:** DECISION at semantic-requirement level; exact encoding remains open.

Thing identity must survive rename/reparent/control/authority transfer and be distinct from labels, paths, Godot handles, process identity, and peer IDs.

**Source:** SMX-002 K-001/K-002/K-010; T-001/T-007; C-006/C-007/C-012/C-017/C-021; A-001/A-016.

### D-011 — Containment, control, authority, observation, persistence, and replication are separate semantics

**Status:** DECISION at object-fabric semantic level.

One overloaded `owner`/parent field must not stand for these dimensions.

**Source:** SMX-002 K-003/K-004; T-001/T-002; C-007/C-020/C-021; A-016.

### D-012 — Intrinsic declaration and runtime/editor context are separate planes

**Status:** DECISION at semantic level.

Thing state/facets may declare requirements/policy; current capability grants, controller/authority, sessions/services, selection, residency, diagnostics, and engine handles remain context unless explicitly projected/persisted.

**Source:** SMX-002 K-005/K-006/K-010; T-003/T-007.

### D-013 — Command/event/value is the current candidate port vocabulary

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

SMX-002 found command/event/directional-value sufficient for basic UI/cross-Thing cases. Query/request-response and scheduler/ordering semantics remain SMX-004 work.

### D-014 — Current kernel candidate is faceted Thing + explicit relation graph

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Stable Thing identity, intrinsic state namespaces, optional facets, explicit ports, typed relationships, and explicit context bindings are the current universal-kernel candidate.

**Source:** SMX-002 research/fixtures; later SMX-003 evidence strengthens composition compatibility.

### D-015 — Local definitions use stable definition/element provenance distinct from concrete Thing identity

**Status:** DECISION at semantic-requirement level; canonical encoding remains SMX-005 work.

A reusable local definition has a durable definition identity and stable element identities. Concrete instances have their own Thing IDs plus explicit provenance to definition elements/revisions. `instance-of` is provenance, not control, authority, persistence ownership, or runtime ownership.

**Reason:** path-addressed inheritance cannot safely support reparenting, instance overlays, collaboration, durable references, or internal restructure. The SMX-003 experiment promotes an existing group without replacing concrete Thing IDs and creates multiple independent concrete instances from the same definition graph.

**Source:** `docs/research/SMX-003-COMPOSITION-DEFINITIONS.md` CMP-002–CMP-005; CT-001/CT-002.

### D-016 — Instance variation is represented by sparse explicit overlays over an immutable base revision

**Status:** DECISION at semantic level; patch encoding remains open.

An instance records only intentional departures from a specific definition revision plus local additions/suppressions. Compatible definition changes propagate to unoverridden loci; valid explicit overrides continue to win at their declared loci.

**Reason:** this preserves author intent without requiring live prototype-chain lookup or duplicating the complete base graph into every instance.

**Source:** SMX-003 CMP-006/CMP-007/CMP-011; CT-003/CT-004/CT-007.

### D-017 — Definition updates reconcile transactionally and fail explicitly on invalidated semantic targets

**Status:** DECISION at semantic level; canonical conflict record/transaction format remains open.

A definition revision is planned against an instance's base revision + overlay before commit. Removed/type-incompatible override targets, missing local-attachment targets, invalid public-interface bindings, and protected destructive changes produce explicit conflicts. A conflicting update must not leave the instance half-migrated.

**Reason:** silent dropping/reinterpretation of overrides or partial structural mutation would make reuse, migration, and collaboration untrustworthy.

**Source:** SMX-003 CMP-008/CMP-009; CT-005/CT-006/CT-009.

### D-018 — Public group/component interfaces are stable indirections over internal element ports

**Status:** DECISION at semantic level.

External connections target a containing/root Thing's stable public port identity. The public port may bind to an internal `ElementId + PortId`; internal reparenting/replacement can change that binding without changing the external connection identity when compatible.

**Reason:** C-011/C-027 require encapsulation and restructure without path repair.

**Source:** SMX-003 CMP-010; CT-008/CT-009.

## Primary-source and comparative evidence

### E-001 — Godot web editor export limitation

**Status:** FACT, time-sensitive; superseded in precision by E-007.

Godot web editor documentation reports no normal project-export capability.

Source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

### E-002 — Godot web renderer/platform constraints

**Status:** FACT, time-sensitive; superseded in precision by E-008/E-009.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-003 — Custom Godot web build can reduce JavaScript exposure

**Status:** FACT, time-sensitive; superseded in precision by E-012.

Source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### E-004 — Godot runtime/package facilities are not automatically safe for untrusted executable content

**Status:** FACT/design input, time-sensitive; superseded in precision by E-013.

Sources: Godot runtime I/O and PCK documentation.

### E-005 — Godot networking is candidate substrate, not settled SplashMX protocol

**Status:** FACT/design input, time-sensitive.

Sources: Godot high-level multiplayer, WebSocket/WebRTC, and dedicated-server documentation.

### E-006 — Current Godot release context (checked 2026-09-17)

**Status:** FACT, time-sensitive.

Official archive listed Godot 4.7.2 stable (2026-08-18) and 4.8-dev6 (2026-09-15) on the checked date.

Source: https://godotengine.org/download/archive/

### E-007 — Web editor remains preliminary/non-exporting (checked 2026-09-17)

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

### E-008 — Web export baseline is WebAssembly/WebGL 2 Compatibility (checked 2026-09-17)

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-009 — Single-threaded web export is preferred/default; threading changes hosting requirements

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-010 — Browser background suspension is architecturally relevant

**Status:** FACT, time-sensitive.

Current Godot web-export docs report inactive-tab pausing can affect network connections.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-011 — Browser networking surface is restricted

**Status:** FACT, time-sensitive.

Godot web builds expose browser-suitable HTTP/WebSocket/WebRTC paths rather than arbitrary low-level networking.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-012 — Custom web templates can omit JavaScriptBridge/eval support

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### E-013 — Runtime file/ZIP loading exists; executable PCK/mod loading is security-sensitive

**Status:** FACT, time-sensitive.

Sources:
- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html

### E-014 — Headless/dedicated execution and WebRTC substrate are available

**Status:** FACT, time-sensitive.

Sources:
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html
- https://docs.godotengine.org/en/stable/tutorials/networking/webrtc.html

### E-015 — Godot's core project composition is scene/node-tree oriented

**Status:** FACT / conceptual comparison input.

Sources:
- https://docs.godotengine.org/en/4.7/getting_started/introduction/key_concepts_overview.html
- https://docs.godotengine.org/en/4.7/tutorials/scripting/nodes_and_scene_instances.html

### E-016 — ECS precedent separates unique entities, optional components, and explicit relationships

**Status:** FACT / conceptual comparison input.

Sources:
- https://bevy.org/learn/quick-start/getting-started/ecs/
- https://github.com/bevyengine/bevy/blob/main/examples/ecs/relationships.rs

### E-017 — Actor precedent separates stable reference from encapsulated state/behaviour

**Status:** FACT / conceptual comparison input.

Sources:
- https://doc.akka.io/libraries/guide/concepts/akka-actor.html
- https://doc.akka.io/libraries/akka/snapshot/general/actors.html

### E-018 — Prototype delegation is flexible but makes inherited lookup implicit

**Status:** FACT / conceptual comparison input.

MDN documents dynamic inherited-property lookup through prototype chains; SMX-002 retained prototype/delegation only as a comparison for later local-definition research.

Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Inheritance_and_the_prototype_chain

### E-019 — Godot scene inheritance demonstrates base-structure/local-modification trade-offs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Godot stable documentation for inherited imported scenes allows local modification/addition while restricting removal of nodes supplied by the base scene.

Source: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html

**Implication:** practical scene inheritance proves the workflow class is useful, but its structural restrictions are an engine/editor choice rather than a SplashMX semantic requirement.

### E-020 — Unity prefab precedent supports linked instances, nested definitions, and explicit overrides

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Current Unity documentation describes prefab instances remaining linked to source assets, nested prefabs, per-instance overrides, and prefab variants; variant documentation also exposes structural restrictions such as reparent/removal constraints for inherited objects.

Sources:
- https://docs.unity3d.com/current/Manual/prefabs-introduction.html
- https://docs.unity3d.com/current/Manual/prefabs-override.html
- https://docs.unity3d.com/6000.0/Manual/PrefabVariants.html

**Implication:** sparse explicit overlays and visible provenance are strong precedents; hierarchy/path-coupled restrictions are not copied automatically.

### E-021 — Self prototype/delegation precedent shows seamless reuse and implicit-role costs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Self uses prototype objects, cloning, parent/delegation slots, traits, and mixins rather than mandatory classes. Its programming-style documentation notes that class-like versus instance-like object roles are conventional rather than intrinsic.

Sources:
- https://handbook.selflanguage.org/2024.1/worldorg.html
- https://handbook.selflanguage.org/2024.1/progguid.html
- https://handbook.selflanguage.org/2024.1/glossary.html

**Implication:** ordinary objects becoming reusable exemplars is desirable, while implicit dynamic lookup/provenance is a poor fit for SplashMX migration/collaboration requirements.

## Hypothesis review snapshots

### SMX-001

H-001–H-018: **unresolved**; baseline added corpus/scorecard only.

### SMX-002

- H-001: **strengthened**.
- H-002: **strengthened**.
- H-003: **strengthened, still provisional**.
- H-008: **strengthened**.
- Others: no status change.

### SMX-003

- H-002: **strengthened further**.
- H-003: **strengthened**.
- H-004: **strengthened**; local promotion/instances/overlays demonstrated, portable packaging still pending SMX-013.
- H-005: **unresolved / no direct status change**.
- Others: no status change.

Detailed evidence: `docs/research/SMX-003-COMPOSITION-DEFINITIONS.md` and its fixture/harness artifacts.

## Open architectural questions

### O-001 — Minimal universal port vocabulary

Command/event/value remains the current candidate; query/request-response, ordering, directionality, and async semantics remain open.

Owner: SMX-004.

### O-002 — Where behaviour state lives

Behaviour-private state has an explicit facet namespace, but serialization/hot-swap/migration compatibility remain open. SMX-003 adds the question of inherited behaviour attachment identity across definition revisions.

Owner: SMX-004/007.

### O-003 — Definition/instance model

**Status:** RESOLVED PROVISIONALLY by SMX-003.

Current candidate: stable local-definition graph + concrete instance graph + sparse explicit overlay, with explicit reconciliation between immutable base revisions. This remains subject to SMX-005 canonical representation, SMX-011 collaboration, SMX-013 packaging, and SMX-015 destructive falsification.

### O-004 — Canonical encoding

Human-readable, binary, database-like, or hybrid representation remains open. It must encode Thing/Definition/Revision/Element/Port identities, overlays, exposures, transactions/conflicts, partial loading, and migration.

Owner: SMX-005.

### O-005 — Runtime IR shape

Event rules, bytecode, dataflow, state machines, or hybrid remain open against determinism, sandboxing, inspectability, hot replacement, authoring projection, and performance.

Owner: SMX-004.

### O-006 — Multiplayer replication boundary

State/event/input/snapshot/hybrid replication must align with Thing authority and browser/server topology.

Owner: SMX-010/017.

### O-007 — Collaboration substrate

Stable base-revision/overlay/reconciliation loci are now inputs, not a conflict-resolution algorithm. Desired user-visible concurrent-edit semantics remain open.

Owner: SMX-011/018.

### O-008 — Durable identity namespace and tombstones

Exact generation format, namespace scope, cross-package addressing, non-reuse, tombstone lifetime, and unresolved/destroyed reference representation remain open.

Owner: SMX-005/007.

### O-009 — Canonical reconciliation/conflict transaction model

SMX-003 requires plan-before-commit definition reconciliation and explicit conflict states for invalidated overlays, public interfaces, local attachments, and protected deletion. Exact transaction/conflict schemas, revision ancestry, rollback, and collaboration interaction remain open.

Owner: SMX-005/011.

## Maintenance rule

When an issue resolves or materially changes an entry here, update this file in the same PR or explicitly supersede it with an ADR referenced here. Do not allow stale early assumptions to remain indistinguishable from current decisions.
