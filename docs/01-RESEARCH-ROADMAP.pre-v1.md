# SplashMX pre-architecture research roadmap

Status: initial reviewed plan, 2026-09-17.

This roadmap intentionally delays production-editor work until the underlying object fabric, execution boundary, security model, lifecycle, and portability assumptions have survived falsification.

## Research strategy

SplashMX is not being designed by choosing a familiar engine architecture and simplifying its UI. The programme works in the opposite direction:

1. define product invariants and author-facing promises;
2. formalise the minimum universal object semantics needed to uphold them;
3. test those semantics against composition, behaviour, serialization, streaming, security, multiplayer, and collaboration;
4. map the resulting platform model onto Godot only after the public contracts are understood;
5. project the model back upward into an editor that remains approachable;
6. attempt to break the entire model with destructive prototypes;
7. freeze Architecture v1.0 only after contradictions are reconciled.

## Dependency graph

```text
SMX-001 Research baseline / adversarial corpus
    |
    v
SMX-002 Universal Thing/kernel semantics
    |
    +--------------------+
    v                    v
SMX-003 Composition      SMX-004 Behaviour execution + IR
    |                    |
    +----------+---------+
               v
SMX-005 Canonical document / identity / schema
    |          |           |
    v          v           v
SMX-006     SMX-007      SMX-009
Security    Lifecycle    Godot substrate/browser mapping
    |          |           |
    |          v           |
    +------> SMX-008 <------+ 
             Streaming
                |
        +-------+--------------------+
        v                            v
SMX-010 Runtime multiplayer      SMX-011 Collaboration semantics
        |                            |
        +-------------+--------------+
                      v
                SMX-012 Editor projection
                      |
                SMX-013 Component/package ecosystem
                      |
                SMX-014 Publish/player/server topology
                      |
          +-----------+-----------+
          v           v           v
      SMX-015     SMX-016     SMX-017
      Fabric      Security    Network
      harness     harness     harness
          |           |           |
          +-----------+-----------+
                      |
                 SMX-018
            Collaboration harness
                      |
                 SMX-019
           Browser vertical slice
                      |
                 SMX-020
          Architecture v1.0 freeze
```

Dependencies in issue bodies are authoritative if this diagram is later refined.

## Work packages

### SMX-001 — Research baseline, terminology, adversarial corpus, and scorecard

Purpose: make later architectural arguments comparable and falsifiable.

Outputs:

- glossary separating object, group, local class, instance, behaviour, connection, state, context, authority, capability, persistence, and identity;
- representative/adversarial object corpus covering UI, animation, games, simulation, audio, procedural systems, networking, and collaborative editing;
- research scorecard and failure criteria;
- upstream-source freshness register;
- minimal research-harness conventions.

Gate: no universal object design is accepted until it can be tested against the corpus.

### SMX-002 — Universal Thing/kernel semantics

Purpose: determine the smallest stable semantics of a SplashMX Thing.

Investigate:

- intrinsic state versus runtime/editor/context state;
- durable identity independent of hierarchy/path;
- declared ports/messages/connections;
- behaviours/facets and their private/public state;
- capabilities, persistence, presentation, and networking as intrinsic declarations versus contextual overlays;
- whether groups and local classes can use the same core representation.

Gate: model must describe the SMX-001 corpus without inventing category-specific managers for meaning.

### SMX-003 — Composition, groups, local classes, instances, and overrides

Purpose: prove that hierarchy can express locality/composition without becoming behavioural ownership.

Investigate:

- group-as-Thing semantics;
- reusable local definitions;
- structural inheritance versus prototype/instance models;
- instance overrides and definition propagation;
- exposed inner properties;
- connection stability under reparenting/restructuring;
- control/authority relationships independent of containment.

Gate: nested structures such as person -> crew -> vehicle -> convoy -> world must remain coherent at every level.

### SMX-004 — Behaviour execution semantics and safe IR

Purpose: establish how embodied intent executes without arbitrary user GDScript.

Investigate:

- event/rule/dataflow/state-machine primitives;
- scheduler and event ordering;
- deterministic operations;
- asynchronous operations and timers;
- resource/instruction budgets;
- behaviour private state;
- hot replacement/state handoff;
- common IR shared by built-ins, visual rules, and future textual logic.

Gate: behaviour can be replaced on a live object without reconstructing identity, and the execution model can be sandboxed.

### SMX-005 — Canonical document model, identity, schema, diff, and migration

Purpose: define the durable representation owned by SplashMX rather than Godot.

Investigate:

- object/definition/instance IDs;
- references independent of paths;
- canonical encoding;
- content-addressed assets;
- schemas and unknown future fields;
- diff/patch/transaction semantics;
- migration;
- collaboration friendliness;
- deterministic encoding where required;
- editable project versus runtime state boundaries.

Gate: editor, player, validator, server, thumbnailer, migration tool, and collaboration layer could all consume the same canonical semantics.

### SMX-006 — Threat model and capability sandbox

Purpose: treat community components as hostile input before an ecosystem exists.

Investigate:

- capability grants and delegation;
- arbitrary network/browser/filesystem/native-code exclusion;
- malformed packages;
- decompression/resource exhaustion;
- instruction/time/memory budgets;
- authority confusion across nested components;
- user-visible permission representation;
- custom hardened Godot web/runtime builds where beneficial.

Gate: there is an explicit attack surface and enforcement boundary; security is not dependent on author goodwill.

### SMX-007 — Runtime lifecycle, serialization, restore, and determinism

Purpose: define what happens to Things through active, dormant, saved, unloaded, and restored states.

Investigate:

- lifecycle phases;
- timers and pending messages;
- reference semantics to absent objects;
- exact restore fixtures;
- deterministic versus intentionally nondeterministic state;
- transient/context state exclusion;
- replay opportunities and limits.

Gate: representative active worlds can serialize and reconstruct without hidden managers being required to restore meaning.

### SMX-008 — Streaming, dependency acquisition, hot replacement, and migration

Purpose: prove Things can cross load boundaries with meaning intact.

Investigate:

- partial object-graph loading;
- stream-in/out;
- lazy dependency resolution;
- dangling but valid references to unloaded objects;
- behaviour-only streaming;
- hot component/version replacement;
- state migration;
- future server/region migration implications.

Gate: a town can unload while an inventory item retains a valid reference to a Thing in that town, and reload restores coherent relationships.

### SMX-009 — Godot substrate and browser-runtime mapping

Purpose: determine what Godot should implement internally and where SplashMX must own the abstraction.

Research current Godot/web facts and prototype selected mappings for:

- rendering/audio/input/physics;
- runtime asset loading;
- browser storage;
- web export constraints;
- custom export-template hardening;
- WebSocket/WebRTC transports;
- headless/dedicated-server operation;
- performance/overhead of object-fabric mappings;
- which Godot APIs must never become public contracts.

Gate: produce a boundary map: `SplashMX owns` versus `Godot supplies`.

### SMX-010 — Runtime multiplayer semantics and topology independence

Purpose: make multiplayer a Thing/network facet rather than a global manager architecture.

Investigate:

- object authority;
- replicated state/events;
- reliability/frequency;
- interest/relevance;
- ownership transfer;
- interpolation/prediction boundaries;
- peer-room versus authoritative-server topology;
- reconnection and host migration;
- transport independence;
- cheat/security implications.

Gate: one canonical creation model can plausibly execute offline, peer-hosted, and dedicated-authoritative without separate object types.

### SMX-011 — Collaborative authoring semantics and local-first research

Purpose: define desired human conflict semantics before choosing CRDT/OT structures.

Cases must include concurrent delete/edit, reparent/reparent, class-definition edit versus instance override, timeline conflict, grouping conflict, component-version changes, and offline reconnection.

Compare CRDT, operation-log, transaction, and hybrid approaches after desired outcomes are specified.

Gate: the project has explicit merge semantics rather than a technology-selected conflict model.

### SMX-012 — Editor projection and progressive disclosure

Purpose: prove the sophisticated platform model can remain less technical than a conventional game engine.

Research author-facing projections for:

- stage;
- timeline;
- library/components;
- behaviours;
- rules/connections;
- multiplayer;
- reusable local classes;
- advanced internals;
- future textual logic.

Define progressive-disclosure levels and vocabulary tests.

Gate: simple workflows do not require authors to understand the internal object fabric, Godot, networking, or packaging.

### SMX-013 — Component/package ecosystem

Purpose: establish safe portable Things/components and dependency semantics.

Investigate:

- local class -> packaged component promotion;
- exposed parameters/ports;
- dependency manifests;
- semantic/version compatibility policy;
- capability requests;
- transitive dependency/capability rules;
- remix/source permissions;
- integrity/signing options;
- update and migration policy.

Gate: a community component can be inserted, inspected, updated, constrained, and removed without becoming arbitrary host code.

### SMX-014 — Publishing, generic players, server execution, and longevity

Purpose: reduce publishing to an author action rather than an export toolchain.

Investigate/package-contract separation for:

- editable projects;
- published creations;
- reusable components;
- saved persistent worlds;
- web/native players;
- headless server runtime;
- offline bundles;
- hosted share links;
- embedding;
- runtime/schema compatibility and migration.

Gate: a published creation is data + constrained logic for a generic runtime, not an arbitrary exported Godot project by default.

### SMX-015 — Destructive Object Fabric harness (P0-P4)

Purpose: integrate and falsify the core semantics.

Required experiments:

- P0 universal kernel across adversarial corpus subset;
- P1 hot behaviour replacement preserving identity/state contract;
- P2 nested groups/local definitions without hidden behavioural ownership;
- P3 exact serialize/restore fixtures;
- P4 stream arbitrary subgraphs out/in with stable references.

Gate: failures amend upstream specs; do not paper over them in the harness.

### SMX-016 — Adversarial sandbox harness

Purpose: attempt to escape or exhaust the capability boundary.

Include malformed packages, recursive/event storms, memory amplification, oversized/decompression inputs, authority escalation, nested-component capability confusion, forbidden host API attempts, and network-policy violations.

Gate: failures result in enforceable design changes or explicitly documented unresolved blockers.

### SMX-017 — Network topology equivalence harness

Purpose: run the same canonical creation through offline, peer-hosted browser, and dedicated-authoritative modes.

Measure semantic divergence, required package differences, latency handling, authority transfer, reconnection, and browser constraints.

Gate: topology changes configuration/policy, not the fundamental creation/object model.

### SMX-018 — Collaboration conflict harness

Purpose: exercise the explicit SMX-011 conflict corpus with two or more simulated editors, including offline edits and reconnection.

Gate: conflict outcomes are explainable to users and preserve document validity.

### SMX-019 — Browser editor/player vertical slice

Purpose: test the architecture against the product promise.

Build the smallest browser-hosted authoring/playback slice capable of creating a few Things, applying behaviour, connecting them, playing immediately, saving/reloading canonical data, and exercising one multiplayer/collaboration path if prior gates support it.

This is not a production editor. It is an architectural usability experiment.

Gate: internal sophistication does not leak into the basic blank-canvas -> interactive-result workflow.

### SMX-020 — Architecture v1.0 reconciliation and implementation roadmap

Purpose: reconcile all evidence into a coherent architecture rather than preserving every early hypothesis.

Outputs:

- Architecture v1.0;
- accepted/rejected/deferred ADRs;
- canonical object/document/runtime diagrams;
- security model;
- network/collaboration separation;
- Godot boundary map;
- compatibility/migration policy;
- editor projection principles;
- measured residual risks;
- production implementation roadmap and dependency graph.

Gate: contradictions are either resolved or explicitly retained as blockers. No production roadmap may silently assume unresolved research succeeded.

## Cross-cutting review questions

Every issue should ask, where applicable:

1. Does this push Godot implementation detail above the compatibility boundary?
2. Does this create a hidden manager that owns another Thing's meaning?
3. Does hierarchy accidentally become behavioural/network/persistence ownership?
4. Can the same concept survive reparenting, streaming, serialization, and network authority transfer?
5. Can untrusted community content exploit ambient authority?
6. Does the design remain comprehensible through progressive disclosure?
7. Does the representation have a migration path for old content?
8. Is the conclusion supported by evidence or merely familiarity?

## Current upstream facts to re-verify during relevant issues

As of 2026-09-17, current Godot documentation reports, among other things:

- the Godot web editor cannot itself perform normal project exports;
- web projects use WebAssembly/WebGL and the Compatibility renderer;
- single-threaded web export is the preferred/default route for broad hosting compatibility, while threaded builds impose cross-origin-isolation requirements;
- custom web builds can disable JavaScript `eval` support;
- browser runtime and native/headless runtimes have materially different platform capabilities;
- Godot supports runtime file loading and multiple networking transports, but its high-level multiplayer abstractions should not automatically be treated as SplashMX's stable public protocol.

These are inputs, not eternal assumptions. Relevant issues must refresh them against current primary documentation/source before making durable decisions.
