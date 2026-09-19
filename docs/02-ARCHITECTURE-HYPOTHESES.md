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

## SMX-006 review record — 2026-09-17

Evidence: `docs/research/SMX-006-CAPABILITY-SANDBOX.md`, `docs/research/SMX-006-SECURITY-FIXTURES.json`, and `experiments/smx-006-security-model/`.

- **H-006 strengthened indirectly.** The bounded-turn common IR from SMX-004 exposes a finite service boundary where capability checks can be applied uniformly without adding a privileged second user execution engine. Actual hostile IR/compiler testing remains SMX-016.
- **H-009 strengthened substantially at model level, still unresolved end-to-end.** Principal-scoped grants, monotonic narrowing delegation, live revocation, deny-by-default host mediation, parser/migration/network limits, nested-component isolation, and signature-without-privilege semantics are directly exercised. Real Godot/browser/native escape resistance and decoder/process isolation remain unproven.
- **H-014 strengthened narrowly.** Current Godot host facilities can remain behind adapters: JavaScriptBridge can be omitted from custom web templates, while untrusted PCK/GDExtension/native-code routes are excluded from ordinary content. Production mapping/maintenance/performance remain SMX-009/019 work.
- **H-015 strengthened narrowly from security architecture.** A generic player centralizes parser validation, capability mediation, quota enforcement, and platform hardening. Publishing/runtime performance evidence remains SMX-014/019.

No other hypothesis receives a status change from SMX-006.

## SMX-007 review record — 2026-09-17

Evidence: `docs/research/SMX-007-LIFECYCLE-RESTORE.md`, `docs/research/SMX-007-LIFECYCLE-FIXTURES.json`, and `experiments/smx-007-lifecycle-model/`.

- **H-008 strengthened further.** Stable Thing/reference identity now survives semantic dormancy, unload, JSON-round-tripped snapshot reconstruction in a fresh runtime model, and explicit tombstone resolution. No hierarchy path or engine/process object participates in restoration.
- **H-010 strengthened substantially at model level.** A Thing can become known-unloaded and later be reconstructed from authored basis + persistent runtime snapshot while retaining public/private state, deterministic PRNG position, durable timers/queued work, provenance, references, and explicit absence states. Full object-centric streaming implementation remains SMX-008/015.
- **H-018 strengthened further at runtime-snapshot layer, unresolved end-to-end.** Restore checks authored basis and behaviour/private-state versions and requires explicit migration/rejection rather than silently deserializing engine objects. Real cross-Godot-version compatibility remains for SMX-009/015/020.

No other hypothesis receives a status change from SMX-007.

## SMX-008 review record — 2026-09-19

Evidence: `docs/research/SMX-008-STREAMING-MIGRATION.md`, `docs/research/SMX-008-STREAMING-FIXTURES.json`, and `experiments/smx-008-streaming-model/`.

- **H-005 strengthened further.** Streaming acquisition now composes with the bounded-turn hot-swap model: replacement artifacts are acquired/validated before a quiescent transactional migration, pending continuations are explicitly mapped, and failed migration leaves the old live implementation/state/pins intact.
- **H-010 strengthened further.** The town/inventory, code-eviction, nested-interface, and migration-capsule cases preserve Thing/attachment meaning across unloaded source/runtime artifacts without requiring a surviving process object.
- **H-011 strengthened substantially at model level.** The town fixture unloads a containment region while a resident inventory keeps a stable reference, then reloads only the referenced sword plus its hard artifact closure. Logical streaming is therefore object/subgraph-centric while physical byte batching remains non-semantic. Production performance remains unproven.
- **H-018 strengthened further.** Exact immutable source artifacts plus explicit bounded state/interface/pending-work migration support hot replacement without engine-object deserialization or silent state reinterpretation.

No other hypothesis receives a status change from SMX-008.

## SMX-009 review record — 2026-09-19

Evidence: `docs/research/SMX-009-GODOT-BOUNDARY.md`, `docs/research/SMX-009-GODOT-BOUNDARY-FIXTURES.json`, and `experiments/smx-009-godot-boundary-model/`.

- **H-007 strengthened further.** Current Godot 4.7.2 facilities are useful behind adapters, but the same canonical package can be projected across web/native/headless without NodePath/RID/ResourceUID identity, and the adversarial model rejects such engine identities from canonical data.
- **H-009 strengthened further at the mapping layer, still unresolved end-to-end.** Ordinary content remains unable to request GDScript/C#/GDExtension/JavaScriptBridge/eval/raw-host authority; current web builds can additionally remove JavaScriptBridge/eval as defence in depth. Real host escape resistance remains SMX-016.
- **H-014 strengthened substantially at model/platform-boundary level.** Rendering, audio, input, physics, resource decode/import, storage and transport can be treated as target-private services while SplashMX owns stable identity, behaviour, canonical state, source/audio/provenance semantics and network meaning. Real Godot frame/object cost remains unmeasured.
- **H-015 strengthened at model/package-loading level.** One canonical revision loads through generic web/native/headless target profiles with explicit required/optional feature outcomes; current Godot/web constraints do not require per-creation builds for ordinary constrained content. Startup, distribution and authoring UX remain SMX-014/019 work.
- **H-018 strengthened further.** Snapshots and migration state exclude engine handles; target projection and derived/imported resources preserve canonical revision and source/provenance identity. Actual migration across future Godot versions remains for SMX-015/020.

No other hypothesis receives a status change from SMX-009.

## SMX-010 review record — 2026-09-19

Evidence: `docs/research/SMX-010-RUNTIME-MULTIPLAYER.md`, `docs/research/SMX-010-RUNTIME-MULTIPLAYER-FIXTURES.json`, and `experiments/smx-010-multiplayer-model/`.

- **H-012 strengthened substantially at model level, still awaiting the real topology harness.** One canonical creation and one authored network declaration are exercised unchanged under offline, peer-hosted, and dedicated-authoritative policies. Control, simulation authority, relevance, reconnect, and host migration are runtime relationships/context rather than network-specific object subclasses. SMX-017 must still test real browser/server transports, packet loss/latency, tab suspension, reconnect, and host-loss failure.
- **H-013 strengthened.** Runtime replication uses state/event/input/baseline/relevance/authority semantics and deliberately contains no canonical edit-transaction, base-revision, or collaboration-conflict protocol. Collaboration remains a separate consistency layer even if later implementations share authentication or transport infrastructure.
- **H-014 strengthened further at the network boundary.** Godot peer IDs, SceneTree authority, RPC annotations, and transport transfer modes remain target-private adapter data. Current WebSocket/WebRTC/headless facilities can implement topology policy without entering durable Thing identity or canonical network meaning.

No other hypothesis receives a status change from SMX-010. Existing source/audio/provenance, lifecycle, migration, security, and canonical-document protections remain unchanged.

## SMX-011 review record — 2026-09-19

Evidence: `docs/research/SMX-011-COLLABORATION-SEMANTICS.md`, `docs/research/SMX-011-COLLABORATION-FIXTURES.json`, and `experiments/smx-011-collaboration-model/`.

- **H-013 strengthened substantially.** SMX-011 independently requires durable causal semantic edit transactions, preconditions, tombstones, retained alternatives, explicit conflicts/resolution, schema-aware history, permissions revalidation and selective collaborative undo. Those requirements are materially different from SMX-010 runtime state/event/input/authority/relevance replication. Shared authentication or transport remains possible, but the consistency protocols stay separate.
- **H-017 strengthened at model level; real persistence/synchronization remains unproven.** Offline replicas author transactions without cloud document authority, exchange causal work later, and converge for the deterministic conflict corpus without silent loss of independent work. Browser/native persistence, compaction, relay outage behavior and production security/performance remain SMX-018/019 work.
- **H-018 strengthened narrowly and constrained at collaboration-history level.** Historical edits are schema-aware and must deterministically migrate or quarantine before reconciliation; structural convergence in a CRDT/OT substrate cannot bypass SplashMX schema/feature compatibility. Multi-version history migration/compaction remains SMX-018/020.

No other hypothesis receives a status change from SMX-011. Existing source/audio/provenance, lifecycle, migration, security, streaming and runtime-network protections remain unchanged.

## SMX-012 review record — 2026-09-19

Evidence: `docs/research/SMX-012-AUTHORING-MODEL.md`, `docs/research/SMX-012-AUTHORING-FIXTURES.json`, and `experiments/smx-012-authoring-model/`.

- **H-016 strengthened at authoring-projection/model level, still awaiting real browser usability evidence.** All 28 representative corpus cases project through one Things/Behaviours/Connections semantic fabric with Stage/Timeline/Rules/Components/Together/People/Publish/Inspect as progressively disclosed views rather than new ownership systems. Beginner Rules and advanced Behaviours target the same execution boundary, ordinary groups promote to reusable definitions without identity replacement, Timeline remains optional, multiplayer presets expose the same control/authority/replication/relevance declaration as Advanced, and collaborative editing remains visibly separate from runtime multiplayer. Twenty-seven executable boundary tests exercise the projection and reject identity reuse, hierarchy-as-ownership, second-model reuse/logic, invalid stable-port connections, transient-state persistence, collaboration/runtime conflation, and partial protected-media revisions. SMX-019 must still measure discoverability, interaction friction, diagnostics, browser constraints and end-to-end create→play→save/reload→publish/load usability before H-016 can be treated as production-proven.

No other hypothesis receives a status change from SMX-012. Existing source/audio/provenance, lifecycle, migration, security, streaming, runtime-network and collaboration protections remain unchanged.

## SMX-013 review record — 2026-09-19

Evidence: `docs/research/SMX-013-COMPONENT-PACKAGES.md`, `docs/research/SMX-013-PACKAGE-FIXTURES.json`, and `experiments/smx-013-package-model/`.

- **H-004 strengthened substantially at semantic/package-model level, still awaiting real browser/publishing proof.** The same `DefinitionId`/`ElementId`/stable public `PortId` lineage moves from an ordinary local reusable group into a `PackageId` distribution namespace without replacing existing concrete `ThingId` values or introducing a package-specific object class. Other projects instantiate ordinary Things with explicit provenance to the exact package/definition revision. Final package bytes, registry transport, and authoring UX remain SMX-014/019 work.
- **H-009 strengthened further at the package/dependency layer, still unresolved end-to-end.** Transitive capability requests remain attributed to the requesting dependency principal, parent grants are not inherited, explicit delegation only narrows a live lease, required denial blocks staged install/update, and signatures/source/remix/provenance metadata do not grant authority. Real hostile archive/parser/signature/dependency-confusion and host-escape testing remains SMX-016.
- **H-011 strengthened further at the distribution/resolution layer.** Human dependency requirements resolve into exact immutable locks/descriptors consumed by the existing object-centric streamer; package boundaries and cache residency remain non-semantic, and offline execution requires the exact verified locked closure rather than substituting another compatible cached version.
- **H-018 strengthened further at the component-update layer.** Human version labels select candidate revisions, but actual compatibility is checked against stable public loci, required features/schema, local overlays and explicit state migrations. Failed or incompatible updates leave the previous exact lock, instances, state, interfaces and pending work coherent and active.

No other hypothesis receives a status change from SMX-013. Existing source/audio/provenance, lifecycle, collaboration, multiplayer, Godot-boundary and progressive-authoring protections remain unchanged.

## SMX-014 review record — 2026-09-19

Evidence: `docs/research/SMX-014-PUBLISHING-RUNTIME.md`, `docs/research/SMX-014-PUBLISHING-FIXTURES.json`, and `experiments/smx-014-publishing-model/`.

- **H-014 strengthened further at the publishing/runtime boundary, still awaiting real integration/performance evidence.** Ordinary publication, compatibility/migration, hosted/offline distribution, world/save lineage, exact dependency locks and protected source/audio/provenance semantics remain SplashMX-owned. Godot export machinery produces trusted generic runtime builds rather than becoming a per-creation public contract. Runtime media loading and headless operation supply private implementation mechanisms; real startup/frame/storage costs remain SMX-015/019 work.
- **H-015 strengthened substantially at semantic/proof-model level, not yet production-proven.** One immutable `CreationRevisionId` is consumed by precompiled web/native/headless runtime profiles; 39 deterministic tests exercise compatibility negotiation, exact dependencies/assets, migration, capability denial, target stripping, hosted aliases, offline closure, persistent-world separation and prepare-before-activate failure. No current ordinary requirement forces a per-creation build. SMX-017/019 must still test real browser/server runtime behavior, size/startup/performance and author experience.
- **H-018 strengthened further at publication/runtime-negotiation level.** Compatibility is expressed through SplashMX schema/IR/required-feature negotiation plus explicit bounded migrations and typed unsupported-future outcomes. Persistent worlds carry an explicit creation basis and separate migration contract; compatibility does not reduce to matching a Godot version.

No other hypothesis receives a status change from SMX-014. Existing source/audio/provenance, package/capability, lifecycle, multiplayer, collaboration and progressive-authoring protections remain unchanged.

## SMX-015 review record — 2026-09-19

Evidence: `docs/research/SMX-015-OBJECT-FABRIC-HARNESS.md`, `docs/research/SMX-015-OBJECT-FABRIC-FIXTURES.json`, and `experiments/smx-015-object-fabric-harness/`.

- **H-001 strengthened further at integrated model level.** P0 exercises one Thing kernel across materially different visual, UI, audio, gameplay/physics, procedural and persistent cases without category-specific ownership managers.
- **H-002 strengthened further.** P0/P2/P4 keep containment structural while control, authority, persistence, replication, observation and durable references remain independent through reparenting, definition promotion and selective residency.
- **H-003 strengthened further.** Groups, leaves and instantiated reusable content remain the same Thing semantic type in nested composition.
- **H-004 strengthened further at local-definition integration level.** Ordinary groups promote without replacing first-instance Thing identities; collision and reconciliation failures are preflighted/atomic. Portable distribution remains covered by SMX-013 rather than redefined here.
- **H-005 strengthened substantially at integrated lifecycle/streaming level.** Exact artifact acquisition, attachment-private-state migration, pending-work remapping, rollback, unload and later rehydrate compose without replacing the Thing or attachment identity.
- **H-006 unchanged.** SMX-015 consumes the accepted behaviour contract but adds no new compiler/IR breadth evidence.
- **H-007 strengthened further.** P3 reconstructs the tested semantic world into a fresh runtime from an engine-independent projection plus declared behaviour/artifact catalogs.
- **H-008 strengthened further.** Stable identities survive promotion, nested instantiation, internal restructure, hot replacement, JSON snapshot/restore and unload/reload.
- **H-009 unchanged; hostile proof remains SMX-016.** The harness preserves the no-ambient-authority boundary and excludes capability/engine/session handles from persistence, but intentionally does not claim sandbox escape resistance.
- **H-010 strengthened substantially at integrated model level.** Meaningful Thing, reference, behaviour-private, pending-work and protected-media state survives both fresh restore and known-unloaded residency.
- **H-011 strengthened substantially at integrated model level.** The inventory/door/town pressure proves the tested door can load independently of its containment region while exact dependencies validate atomically.
- **H-014 strengthened further at integrated semantic boundary, not performance level.** No tested semantic path requires a public Godot identity or surviving engine object. Real Godot/browser binding and frame cost remains O-020/SMX-019 work.
- **H-018 strengthened substantially at integrated model level.** Behaviour, definition, restore and dependency changes are explicit-version/migration/validation driven and rollback-safe rather than implicitly engine-version driven.

H-012/H-013/H-015/H-016/H-017 receive no direct status change from SMX-015. Existing source/audio/provenance, capability, multiplayer, collaboration, publishing and authoring protections remain unchanged.

## SMX-016 review — 2026-09-19

Evidence: `docs/research/SMX-016-SECURITY-HARNESS.md`, `docs/research/SMX-016-SECURITY-FIXTURES.json`, `docs/research/SMX-016-DECISION-EVIDENCE.md`, and `experiments/smx-016-security-harness/`.

- **H-006 strengthened at hostile model level.** Unknown/raw-host opcodes fail closed and recursive instruction, allocation, emitted-work, timer, queue and service-request amplification are independently budgeted without introducing a privileged second user execution path. Compiler completeness and real-runtime accounting remain later implementation work.
- **H-009 strengthened substantially, still unresolved end-to-end.** The hostile campaign directly exercises no ambient authority, originating-principal attribution, narrowed and depth-bounded delegation, corrupt/cyclic ancestry, live revocation, raw-host denial, recursive authority-token rejection and target-independent semantic mediation. O-025 retains real Godot/browser/native escape resistance, decoder safety, process/origin hardening, production crypto/archive behavior and calibrated quotas.
- **H-011 strengthened narrowly at hostile acquisition/dependency boundary.** Exact immutable package descriptors plus a bounded acyclic dependency closure reject substitution/confusion before migration or activation without executable Godot scene/PCK semantics.
- **H-014 strengthened at semantic host-boundary level; physical target isolation remains target-specific.** The same raw-host deny rule holds even when a target physically exposes JavaScriptBridge/GDExtension/process/filesystem facilities to trusted host code. Real target integration remains SMX-019/O-025 evidence.
- **H-015 strengthened from hostile-boundary centralization.** A versioned generic player provides one pre-activation enforcement point for exact-lock, parser, migration, capability, target and decoder checks. This does not prove browser startup/size/performance.

No other hypothesis receives a status change from SMX-016. Protected source/audio/provenance semantics remain unchanged and indivisible.
