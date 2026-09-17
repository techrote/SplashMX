# SplashMX architecture hypotheses

These are **testable propositions**, not settled architecture. Each hypothesis should either accumulate evidence, be refined, or be rejected. Do not treat wording here as a substitute for issue acceptance criteria.

## H-001 — One universal Thing model is viable

A small core representation can describe ordinary objects, groups, reusable local definitions, UI elements, audio objects, procedural systems, and networked entities without category-specific ownership managers.

**Falsify if:** representative SMX-001 cases require incompatible base semantics rather than optional facets/behaviours.

## H-002 — Hierarchy can remain structural rather than semantic ownership

Containment/transform hierarchy can coexist with independent behavioural, persistence, authority, control, and replication relationships.

**Falsify if:** common operations require behaviour meaning to be inferred from ancestry or force reparenting to rewrite unrelated semantics.

## H-003 — Group and object can share the same semantic kernel

A group can itself be a Thing with state, behaviours, ports, and exposed controls while containing Things that preserve their own meaning.

**Falsify if:** group-level coordination requires a fundamentally separate object category or hidden manager semantics.

## H-004 — Local classes can emerge from ordinary composition

An authored Thing/group can become a reusable local definition, then a portable component, without being rewritten into a different programming construct.

**Falsify if:** reusable definitions need a separate incompatible authoring model.

## H-005 — Behaviour is safely composable and dynamically replaceable

Intent/control can be represented as modular behaviours with explicit requirements/provides/state, allowing compatible behaviours to be attached, removed, or replaced on a live Thing without replacing its durable identity.

**Falsify if:** behaviour hot-swap requires object reconstruction for ordinary cases or causes unavoidable hidden state loss.

## H-006 — Built-ins, visual rules, and future text can target one IR

A constrained intermediate representation can support beginner rules and advanced authored behaviour while remaining inspectable, budgetable, portable, and sandboxable.

**Falsify if:** beginner and advanced execution require separate semantics that cannot be reconciled without semantic surprises.

## H-007 — SplashMX should own the canonical document format

Durable creation identity, references, object semantics, migrations, and package compatibility should be represented above Godot scenes/resources.

**Falsify if:** Godot-native serialization can demonstrably satisfy portability, migration, collaboration, sandbox, partial-loading, and long-term-compatibility requirements without leaking engine contracts.

## H-008 — Stable identity must be path-independent

Things/definitions/connections need durable identifiers that survive rename, reparent, save/load, stream-out/in, collaboration, and network authority transfer.

**Falsify if:** a simpler identity scheme satisfies all required lifecycle operations without ambiguity or repair heuristics.

## H-009 — Capability security can bound untrusted components

Untrusted creations/components can run useful logic while lacking ambient access to Godot, browser JavaScript, native extensions, filesystem, arbitrary network, and privileged host APIs.

**Falsify if:** required everyday functionality inherently needs ambient host authority rather than explicit capability mediation.

## H-010 — The same Thing semantics can survive unloaded state

A Thing can be dormant/serialized/unloaded and later rehydrated while preserving meaningful identity, references, declared state, and behaviour contracts.

**Falsify if:** common semantics depend on continuously resident process objects.

## H-011 — Streaming can be object-centric rather than scene-centric

Arbitrary relevant object subgraphs, definitions, behaviours, and assets can be loaded/unloaded independently enough to support future large worlds and dynamic components.

**Falsify if:** coherent streaming necessarily follows scene/package boundaries that conflict with the Thing model.

## H-012 — Multiplayer topology can be policy, not object taxonomy

The same canonical creation can support offline, peer-hosted small-room, and authoritative-server execution primarily by changing authority/replication/topology policy rather than replacing ordinary objects with network-specific subclasses.

**Falsify if:** correct networked execution requires fundamentally different creation semantics for each topology.

## H-013 — Runtime multiplayer and collaborative editing must remain separate consistency layers

They may share transport/infrastructure, but live simulation authority/replication and persistent concurrent document editing require different semantics.

**Falsify if:** one consistency model can handle both classes without compromising understandable conflict resolution, responsiveness, or authority.

## H-014 — Godot can remain a replaceable-enough substrate boundary

SplashMX can exploit Godot for rendering/audio/input/physics/platform/runtime facilities while keeping public creation, execution, networking, and package semantics sufficiently independent for long-term evolution.

**Falsify if:** required performance/functionality forces widespread public dependence on Godot-specific identities or behaviours.

## H-015 — Generic players are preferable to per-creation builds

For ordinary publishing, one versioned generic runtime can load validated SplashMX packages, enabling instant publish/share, predictable sandboxing, and easier compatibility management.

**Falsify if:** browser/native constraints make generic loading materially worse than generated builds for core use cases.

## H-016 — Sophisticated internals can project to a simple authoring vocabulary

Things + behaviours + connections, combined with stage/timeline/rules/component views, can expose advanced capabilities through progressive disclosure while keeping beginner workflows simpler than conventional game-engine editing.

**Falsify if:** authors routinely need to understand internal execution, networking, schema, or engine details to perform basic interactive-media tasks.

## H-017 — Offline-first authoring is compatible with cloud collaboration

The canonical project model can live locally and remain fully useful offline while optional sync/collaboration layers reconcile shared work.

**Falsify if:** required collaboration semantics force cloud authority into the canonical storage model.

## H-018 — Compatibility can be migration-driven rather than engine-version-driven

Versioned SplashMX schemas/IR/manifests plus explicit migrations can let old creations survive underlying Godot upgrades.

**Falsify if:** practical migrations cannot preserve semantics across representative runtime/schema changes.

## Hypothesis handling

For each hypothesis touched by an issue, the PR should record one of:

- **strengthened** — evidence supports the present wording;
- **refined** — evidence supports a narrower/different formulation;
- **weakened** — contrary evidence exists but does not yet reject it;
- **rejected** — evidence demonstrates the proposition is unsuitable;
- **unresolved** — available evidence is insufficient.

Architecture v1.0 must not silently convert unresolved hypotheses into facts.

## SMX-001 review record — 2026-09-17

SMX-001 reviewed H-001 through H-018 against the authoritative glossary, representative/adversarial corpus, scorecard, and current upstream-fact snapshot in `docs/research/SMX-001-RESEARCH-BASELINE.md`.

**Status of every H-001–H-018 after SMX-001: unresolved.**

No wording change is justified by baseline construction alone. The new C-/A-case corpus and S-scorecard make later falsification more concrete, but are not empirical support for the hypotheses. Later issues must update individual status only when they generate actual evidence.

## SMX-002 review record — 2026-09-17

Evidence: `docs/research/SMX-002-THING-KERNEL.md`, `docs/research/SMX-002-THING-KERNEL-FIXTURES.json`, and `experiments/smx-002-kernel-model/`.

- **H-001 strengthened.** One faceted Thing semantic envelope maps all 28 representative SMX-001 cases without requiring a second base object category. The executable slice covers UI/ports, cross-object values, durable references, nesting/control, local/network context, capability declaration/grant separation, and behaviour-facet replacement identity. Runtime performance and later subsystem correctness remain unproven.
- **H-002 strengthened.** A-001/A-016 are exercised directly: changing containment does not mutate control, authority, reference, persistence-service, or replication-session relationships.
- **H-003 strengthened, still provisional.** The same experimental `Thing` type represents a group and a leaf; group meaning is expressed through containment plus optional facets. SMX-003 must still test definition/instance propagation and complex nested coordination.
- **H-008 strengthened.** Corpus pressure plus executable rename/reparent/control/authority independence supports a path-independent durable logical identity requirement. Exact ID encoding, namespaces, non-reuse, and tombstone semantics remain for SMX-005/007.

H-004–H-007 and H-009–H-018 receive no status change from SMX-002. The candidate kernel is explicitly provisional and must still survive downstream composition, execution, serialization, lifecycle, networking, collaboration, and destructive-harness work.

## SMX-003 review record — 2026-09-17

Evidence: `docs/research/SMX-003-COMPOSITION-DEFINITIONS.md`, `docs/research/SMX-003-COMPOSITION-FIXTURES.json`, and `experiments/smx-003-composition-model/`.

- **H-002 strengthened further.** Promotion, structural override, definition revision, and instance reconciliation preserve controller/authority/persistence/replication context unless explicitly changed. A-001/A-016 remain satisfied through the new definition/instance layer.
- **H-003 strengthened.** Groups remain ordinary Things with their own state/facets/ports while their members retain independent Thing identities and semantics. No separate group base-object category was required by the composition experiment.
- **H-004 strengthened.** An ordinary authored group can be promoted into a reusable local definition while the original concrete Things remain the first instance with unchanged Thing IDs. Multiple independent instances, sparse overlays, local additions, and base-revision propagation are exercised. Cross-project packaging remains SMX-013 work, so the full local-definition-to-portable-component hypothesis is not yet proven end-to-end.
- **H-005 unresolved / no direct status change.** SMX-003 provides stable semantic loci for inherited/overridden behaviours, but executable hot-swap state transfer and behaviour compatibility remain SMX-004/007 work.

No other hypothesis receives a status change from SMX-003.

## SMX-004 review record — 2026-09-17

Evidence: `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md`, `docs/research/SMX-004-BEHAVIOUR-FIXTURES.json`, and `experiments/smx-004-behaviour-model/`.

- **H-005 strengthened.** The bounded-turn model demonstrates stable attachment-private state, quiescent hot replacement, same-schema preservation, explicit private-state migration, continuation remapping, and atomic rejection without replacing Thing identity. Persistence across unload/restore and production package migration remain unproven.
- **H-006 strengthened.** A compiled beginner event/action rule and a nontrivial hand-authored behaviour use the same validated handler/instruction IR type. Timers, conditions, private/public state, asynchronous services, and reusable behaviour do not require a second execution engine in the tested model. Full visual/text compilers and demanding workloads remain untested.
- **H-009 strengthened narrowly at the execution-boundary level, still unresolved end-to-end.** Unknown opcodes fail validation, no arbitrary host-call instruction exists, runtime services are explicit/capability-mediated, optional capability denial can degrade cleanly, and hard execution budgets are demonstrated. SMX-006/016 must still test package/parser attacks, confused-deputy cases, memory amplification, target-specific host bridges, and real sandbox escape.

No other hypothesis receives a status change from SMX-004.

## SMX-005 review record — 2026-09-17

Evidence: `docs/research/SMX-005-CANONICAL-DOCUMENT.md`, `docs/research/SMX-005-DOCUMENT-FIXTURES.json`, and `experiments/smx-005-document-model/`.

- **H-007 strengthened.** The Thing/definition/instance/behaviour/port/connection/asset/migration semantics from SMX-002–004 fit an engine-independent typed logical-record graph with stable IDs, immutable revision/chunk lineage, semantic transactions, and content-addressed immutable blobs. No SMX-005 requirement benefits from making Godot scenes/resources the public canonical format.
- **H-008 strengthened further.** The document model and executable fixtures preserve Thing/reference identity across rename, reparent, physical chunk relocation, partial loading, instance provenance, public-interface restructure, and asset-content replacement without path repair. Final concrete ID encoding remains open.
- **H-018 strengthened at the schema/document layer; unresolved end-to-end.** Deterministic staged migration preserves IDs/references and compatible optional extension data, rejects unsupported required features, validates target state before commit, and leaves the source untouched on failure. Actual migration across future Godot/runtime semantic changes remains for SMX-009/015/020.

No other hypothesis receives a status change from SMX-005.
