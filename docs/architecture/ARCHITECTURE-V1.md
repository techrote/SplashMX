# SplashMX Architecture v1.0

**Status:** FROZEN ARCHITECTURE BASELINE  
**Freeze date:** 2026-09-19  
**Research basis:** SMX-001 through SMX-019, including destructive Object Fabric, hostile security, real topology, collaboration, and browser vertical-slice evidence  
**Engine evidence baseline:** Godot 4.7.2 stable and browser/runtime facts checked 2026-09-19

Architecture v1.0 is the reconciled semantic contract for the first production implementation of SplashMX. It freezes the relationships and invariants that downstream code must preserve. It does **not** freeze every byte format, algorithm, library, visual design, cloud service, or optimization.

If an older research document conflicts with this file, this file wins unless a later accepted ADR explicitly supersedes it. The research corpus remains retained as evidence and design provenance.

## Contents

| Section | Summary |
|---|---|
| 1. Authority, scope, and change rule | Defines what is frozen and how contradictions are handled. |
| 2. Product and authoring contract | Freezes the approachable one-system author model. |
| 3. Canonical Object Fabric | Freezes Thing, identity, relationships, composition, ports, and hot-swap semantics. |
| 4. Execution model | Freezes the common bounded IR/service boundary and visible ordering rules. |
| 5. Document, lifecycle, streaming, and compatibility | Freezes durable state, loading, restore, migration, and exact-dependency rules. |
| 6. Security and trust boundaries | Freezes deny-by-default capabilities and pre-activation enforcement. |
| 7. Runtime networking and collaboration | Freezes topology-independent simulation semantics and a separate edit consistency plane. |
| 8. Godot and platform boundary | Freezes what SplashMX owns versus what the engine supplies privately. |
| 9. Components and publishing | Freezes local-definition portability, generic-player publishing, worlds, and offline paths. |
| 10. Protected media/provenance invariant | Freezes source/audio/provenance atomicity across every subsystem. |
| 11. Hypothesis closure | Records final H-001–H-018 disposition. |
| 12. Residual implementation risks and non-frozen choices | Prevents implementation unknowns from masquerading as architecture decisions. |
| 13. Production conformance gates | Defines what implementation must prove before claiming Architecture-v1 compatibility. |

## 1. Authority, scope, and change rule

The authority chain after this freeze is:

1. `docs/00-PROJECT-CONSTITUTION.md` — product invariants;
2. this document — Architecture v1.0 semantic contract;
3. accepted Architecture-v1 ADRs under `docs/architecture/`;
4. domain research/specification documents explicitly referenced here — detailed evidence and boundary definitions;
5. `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md` — dependency ordering and verification plan, not a semantic authority above the architecture;
6. retained SMX research experiments and fixtures — evidence/regressions, not production code by default.

A production implementation may choose different internal data structures, libraries, storage engines, transports, rendering structures, or physical packaging only when observable SplashMX semantics remain equivalent.

When implementation evidence contradicts this architecture, the permitted response is not a hidden adapter special case. The contradiction must be recorded, the affected architecture/ADR amended explicitly, and a regression added. This carries forward the correction rule demonstrated by SMX-015 through SMX-019.

Architecture v1.0 deliberately freezes **semantics before physical representation**. The final canonical byte encoding, production CRDT/database, package container, trust-root machinery, distribution topology, editor visual language, and broad performance budgets remain implementation choices or named follow-up research.

## 2. Product and authoring contract

SplashMX remains a creative-computing environment whose minimum usability/capability floor is historical Flash, not a Flash clone. Constitution P1–P15 remain in force.

The durable beginner vocabulary is:

- **Thing** — a durable semantic object with stable identity, state, explicit relationships, optional behaviours, ports, and declarations;
- **Behaviour** — modular intent executed through the common constrained execution boundary;
- **Connection** — a durable declared relationship between stable public ports.

**Stage, Timeline, Rules, Components, Together, People, Publish, and Inspect are projections over that same semantic fabric.** They are not separate underlying architectures.

Authoring must obey these frozen rules:

- Beginner and advanced views reveal progressively more of the same records and execution semantics. There is no disposable “easy mode” document model.
- Timeline is optional. Time-based animation may use Timeline, while ordinary interactive/programmatic work does not need to be forced through it.
- A beginner Rule and an advanced Behaviour target the same semantic IR boundary. Advanced authoring may expose more structure but may not switch to an incompatible execution system.
- Grouping changes structural containment, not behaviour ownership, persistence ownership, simulation authority, replication, or control unless those relationships are explicitly edited.
- An ordinary group can become a reusable local definition without replacing the first instance’s concrete `ThingId` values.
- Runtime multiplayer controls (**Together**) and collaborative authoring (**People**) remain visibly and semantically separate.
- Ordinary create → play → stop/edit → save/reload → publish/load does not require knowledge of Godot Node/SceneTree/Resource/RPC concepts, schemas, package managers, compilers, exporters, or deployment pipelines.
- Diagnostics presented to ordinary authors must be expressible in SplashMX terms even when the internal cause comes from the engine, browser, parser, network, store, or package layer.

SMX-019 proves executable projectability of this contract in a real Chromium slice; it does not prove novice comprehension, final terminology, accessibility, localization, or broad production UX quality. Those remain product verification obligations, not permission to introduce a second conceptual system.

## 3. Canonical Object Fabric

### 3.1 Thing kernel

A Thing is a semantic record, not a Godot Node, scene path, DOM node, transport peer, database row identity, or live process object.

The kernel separates:

- durable logical identity;
- intrinsic authored state;
- selected persistent runtime/world state;
- behaviour-private state;
- explicit relationships and interfaces;
- declared capability/network/persistence requirements;
- transient runtime/editor/transport/engine context.

A group and a leaf use the same Thing kernel. Groups may have their own state, behaviours, and ports while containing Things that retain independent meaning.

### 3.2 Identity and references

Durable identifiers are path-independent and non-interchangeable by role. At minimum the semantic model distinguishes identities such as `ThingId`, `DefinitionId`, definition element identity, `Behaviour` attachment identity, `PortId`, `ConnectionId`, `AssetId`, package/revision identities, creation/revision identities, and persistent world/save identities.

Rename, reparent, physical chunk relocation, load/unload, save/restore, reconnect, authority transfer, definition promotion, and target projection do not rewrite semantic identity merely because an implementation handle changes.

References resolve into explicit states such as live/loaded, known-unloaded, tombstoned/destroyed, or unknown/invalid where the relevant domain requires that distinction. “Not presently resident” is not equivalent to “does not exist”.

### 3.3 Relationship taxonomy

Containment, transform locality, control, simulation authority, persistence ownership, replication/relevance, observation, editor selection, and collaboration presence are different relationships/context classes.

No relationship is inferred from another merely because a convenient engine hierarchy happens to colocate them. In particular:

- parenthood does not grant control or authority;
- package provenance does not grant capability;
- runtime peer identity does not become Thing identity;
- editor selection/presence does not become canonical authored state.

### 3.4 Definitions, instances, and overrides

An ordinary authored group may be promoted into a local reusable definition while preserving the original concrete Things as the first instance. A definition has stable semantic loci for elements and public interface ports. Instances carry provenance to a definition revision plus sparse, explicit overrides and local additions where allowed.

Definition revision reconciliation is semantic and transactional. Invalidated overlay loci, removed required public ports, identity collisions, incompatible structure, or failed migration reject the update rather than partially mutating the live instance.

Definition/instance conflict detection is scoped by actual definition identity, not coincident element names. This incorporates R-018-01.

### 3.5 Connections and ports

Connections use stable semantic endpoints such as `ThingId + PortId`; hierarchy paths and transient engine/transport handles are forbidden substitutes.

Canonical `ConnectionId` is explicitly distinct from a transport connection/peer/session identifier. This incorporates R-019-01.

A Thing tombstone remove-wins over a concurrent new connection that names the deleted Thing as an endpoint, and tombstoning a Thing atomically tombstones incident live connections so dangling active edges cannot survive. This incorporates R-018-02/R-018-04.

### 3.6 Behaviour state and hot replacement

Behaviour attachment has stable semantic identity and private state distinct from Thing public state. Ordinary compatible replacement follows:

`acquire exact artifact → validate → reach quiescent replacement point → migrate/map private state and pending work → validate complete result → commit atomically`

Failure leaves the previous implementation/state live. Incompatible pending work is explicitly mapped, cancelled under declared semantics, or causes rejection; it is never silently guessed or discarded.

Hot replacement does not imply arbitrary compatibility. Compatibility is an explicit contract enforced before commit.

## 4. Execution model

SplashMX owns a constrained, inspectable execution semantics and IR boundary for ordinary user content. Arbitrary GDScript, C#, native extension code, browser JavaScript, raw host calls, or engine scripting are not ordinary content semantics.

Architecture v1.0 freezes these properties:

- Built-ins, beginner Rules, visual logic, and future advanced/textual authoring target one semantic execution boundary. Front ends may differ; author-visible meaning must not fork.
- Scheduling is turn/event based with explicit ordering guarantees where observable. The runtime must not make undocumented engine callback order part of the public language.
- State writes/events are staged according to the accepted behaviour contract; composite semantic transactions validate before publication.
- Time, randomness, external services, network input, and other nondeterminism are explicit inputs/services. Deterministic replay is supported only where the declared workload and captured inputs permit it; full-world lockstep determinism is not a universal requirement.
- Timers, delayed work, and continuations have explicit durable/non-durable lifecycle semantics rather than relying on surviving engine coroutine objects.
- Resource budgets are semantic and independently bound instruction work, recursion/depth, allocations, emitted events/work, timers/queues, service requests, package/dependency expansion, and other amplification classes where relevant.
- Unknown required IR operations/features fail closed. Optional feature fallback must be declared rather than guessed.
- Runtime services are invoked only through capability-mediated adapters attributed to the originating principal.

The exact production VM, bytecode, compiler implementation, and textual syntax are not frozen. Their observable semantics and security boundary are.

## 5. Document, lifecycle, streaming, and compatibility

### 5.1 Canonical document and state planes

SplashMX owns an engine-independent typed logical record graph. The following planes remain separate:

- editable authored project state;
- transient editor/session context;
- transient runtime materialization/context;
- selected persistent world/save state;
- collaboration history/conflict state;
- immutable published creation revisions.

A Play session must not silently write runtime state back into editable authored state. Presence, selection, transport IDs, engine object handles, capability grants/leases, and equivalent current-process context are not durable canonical fields.

### 5.2 Semantic transaction rule

Every multi-record semantic edit/migration/update is staged and the **complete resulting semantic document** is validated before commit. Local pairwise convergence or a structurally valid patch does not excuse a globally invalid document. This incorporates R-018-03.

### 5.3 Lifecycle and restore

Creation/instantiation, activation, dormancy/sleep, snapshot/save, unload, rehydrate/restore, and destruction/tombstone are explicit semantic phases where observable.

Restore reconstructs meaning from canonical authored basis plus permitted persistent state and exact required artifacts. It does not depend on a surviving Godot object, process pointer, NodePath, RID, socket, capability token, browser object, or in-memory manager.

Lifecycle work such as timers/queued actions/private behaviour state follows explicit save/unload/restore contracts. Restore does not replay external side effects merely because an implementation object was reconstructed.

### 5.4 Streaming and partial loading

Logical residency is object/subgraph-centric. A required Thing may load independently of its containment region when its exact hard dependency closure permits this. Physical chunk/package/bundle boundaries may be optimized independently and do not become semantic ownership boundaries.

References distinguish known-unloaded from destroyed/invalid. Cache eviction is non-semantic. Unload is not destruction.

Dependency acquisition is explicit, bounded, integrity-checked, capability-aware, and prepare-before-activate. Interrupted or failed acquisition cannot publish partial semantic state.

### 5.5 Versions, migrations, and compatibility

Compatibility is driven by SplashMX-owned schema/IR/feature/interface identities plus explicit bounded migrations, not by implicit equality of a Godot version.

Migrations are staged, capability-free unless a separately trusted administrative process is explicitly defined, bounded, and target-validated before commit. Failure leaves the old coherent state/revision intact.

Unknown required semantics fail closed. Older content may be migrated, interpreted by retained compatible runtimes, or rejected with a typed outcome; the architecture does not promise that arbitrary future semantic breaks can always be losslessly migrated.

## 6. Security and trust boundaries

Ordinary downloaded creations/components/assets/network inputs are untrusted.

### 6.1 No ambient authority

Ordinary user content has no ambient authority over:

- arbitrary Godot APIs or scripting;
- JavaScriptBridge/eval/browser host objects;
- GDExtension/native code/process execution;
- unrestricted filesystem or raw sockets;
- arbitrary network destinations;
- host credentials/secrets;
- capability issuance/delegation roots.

Useful privileged operations are mediated by explicit, inspectable, revocable capabilities and trusted runtime services.

### 6.2 Principal attribution and delegation

Capability requests/grants are attributed to the actual requesting principal/component. Parent packages do not confer their grants on dependencies. Signing, publisher identity, source availability, remix rights, licence, or provenance do not grant runtime authority.

Delegation can only narrow a live delegable grant and is bounded by depth/count/ancestry rules. Missing, cyclic, corrupt, expired, or revoked ancestry is non-live. Authorization is rechecked immediately before crossing the host adapter so revocation/expiry between admission and use fails closed. This incorporates R-016-03/R-016-04.

### 6.3 Parse/acquire/activate order

Untrusted content follows a fail-closed pipeline. Representative ordering is:

`bounded parse/path normalization → structural/schema validation → exact identity/integrity/dependency closure → compatibility/migration planning → capability policy → decoder/host/runtime binding → activation`

Package path normalization/collision rejection is host-independent and occurs before unsafe extraction. Recursive serialized authority/raw-host fields are rejected. This incorporates R-016-01/R-016-02.

### 6.4 Layered enforcement

Security is enforced independently at parser/container, schema/document, dependency resolver, migration, IR executor, runtime service/capability adapter, decoder/media, storage, and network-ingress boundaries. A lower layer being “sandboxed” does not waive the higher semantic checks.

### 6.5 Residual security risk

SMX-016 is strong semantic hostile evidence, **not end-to-end production sandbox certification**. Production must still prove actual browser/native/headless process/origin isolation, archive-library safety, decoder safety, cryptographic trust/signature/revocation machinery, calibrated engine/GPU/audio memory accounting, browser permission/lifecycle behavior, and hardened runtime build configuration.

These are mandatory implementation gates, not unresolved permission to weaken the semantic capability model.

## 7. Runtime networking and collaboration

### 7.1 Runtime simulation networking

One canonical creation/network declaration supports offline/local, peer-hosted browser, and dedicated-authoritative execution. The real SMX-017 campaign used the same canonical creation across these topologies.

The semantic network model separates:

- authenticated principal/session identity;
- transient transport peer/connection identity;
- input control;
- simulation authority and authority epoch;
- replication/relevance policy;
- durable Thing identity;
- persistence/world ownership.

Transport IDs and Godot peer/RPC identities remain private runtime context.

Clients/peers submit allowed intent according to policy; authoritative state changes are accepted only from the current authority. Stale prior-authority epochs and replayed/duplicate traffic are rejected according to the network contract. Reconnect may bind a new transport identity without replacing the principal/Thing. Host migration transfers semantic state/checkpoint and increments authority epoch rather than serializing old host handles.

Relevance/unloaded delivery is bounded and may coalesce state where the contract permits it. Tombstoned/unknown targets do not silently resurrect from queued network traffic.

Topology-specific latency, interpolation/prediction, transport selection, authentication deployment, NAT/TLS/ICE/signalling, scaling, and congestion policy are private runtime/service concerns unless a future semantic requirement proves otherwise.

### 7.2 Collaborative authoring

Collaborative authoring is a separate consistency plane from simulation replication.

SplashMX owns semantic edit transactions/conflict outcomes above a replaceable causal sync/store substrate. The collaboration layer preserves causal ancestry, transaction identity, tombstones, explicit conflict alternatives/resolution, permission epochs, schema/history compatibility, and selective history semantics promised by the product.

Replica byte equality is insufficient: the resulting canonical document must also satisfy semantic invariants.

Offline edits may be authored without a cloud document becoming canonical authority, then reconciled later. Missing causal ancestors pend. Stale-permission work remains recoverable history but cannot materialize as authorized shared state. Presence/cursors/selections are transient and remain outside canonical authored state.

The production CRDT/OT/log/database, compaction strategy, tombstone retention, relay/storage topology, authentication, and large-history performance remain implementation choices subject to these semantics.

## 8. Godot and platform boundary

Godot is the intended first production substrate, not the SplashMX compatibility boundary.

### 8.1 SplashMX owns

SplashMX owns:

- Thing/Definition/Behaviour/Connection/Asset/package/creation/world semantic identity;
- canonical project/published/save-state models;
- behaviour IR and author-visible execution semantics;
- capability/security semantics;
- dependency/package/update/migration semantics;
- runtime multiplayer authority/replication/relevance semantics;
- collaboration transaction/conflict semantics;
- protected source/audio/provenance semantics;
- generic-player compatibility and activation policy.

### 8.2 Godot supplies privately

Godot may supply target-private implementations for:

- rendering and scene realization;
- audio playback/mixing facilities;
- input collection;
- physics;
- platform abstraction;
- resource decode/import;
- web/native/headless runtime builds;
- storage adapters;
- networking transports;
- timing/event-loop integration and other trusted host services.

Node, NodePath, SceneTree, RID, ResourceUID/resource path, MultiplayerPeer peer IDs, RPC annotations, imported-resource cache identity, engine serialization, and similar handles are not canonical author-facing identity.

### 8.3 Accepted coupling and target variance

Architecture v1 intentionally accepts practical dependence on Godot behavior/performance for the first renderer/audio/input/physics/runtime implementation. “Replaceable-enough” means durable user content semantics are not defined in terms of Godot internals; it does **not** mean another engine can be substituted at zero cost.

The evidence baseline is Godot 4.7.2 stable, checked 2026-09-19. Browser target constraints such as Compatibility/WebGL2 rendering, WebAssembly, persistence policy, tab suspension, browser transport subset, and web-audio differences are runtime capability/policy outcomes rather than new Thing types or canonical forks.

Target-private resource transforms/transcodes/placeholders/engine imports never replace canonical source identity or provenance.

## 9. Components and publishing

### 9.1 Local definition to portable component

Portability extends the same semantic lineage:

`ordinary group → Make reusable → local Definition → Make portable → PackageId + immutable PackageRevision`

Packaging introduces a distribution namespace and exact immutable revision; it does not create a package-specific runtime object taxonomy or rewrite existing first-instance `ThingId` values.

Human version requirements are resolved intentionally into an exact immutable project lock before runtime/streaming/publishing/offline execution. Required, optional, and lazy dependencies are distinct. The Architecture-v1 conservative rule is one exact active revision per `PackageId` per creation lock unless a later ADR proves a safe parallel-version model.

Updates are staged and atomic. Overlay/interface/state/migration/capability incompatibility leaves the old exact coherent lock/state active. Cache residency is non-semantic. Uninstall is reference-aware.

### 9.2 Artefact taxonomy

The architecture distinguishes:

- editable project/revision;
- local definition;
- portable component package/revision;
- immutable published creation (`CreationId` lineage + `CreationRevisionId`);
- persistent `WorldSave`/world lineage anchored to an explicit creation basis;
- trusted generic web/native/headless player/server runtime build;
- immutable hosted release;
- mutable friendly share/embed alias;
- exact offline-capable closure/bundle/install state.

These roles are not interchangeable identities.

### 9.3 Ordinary Publish

Ordinary Publish creates/identifies an immutable SplashMX creation revision consumed by a separately built versioned generic runtime. It does **not** run a per-creation Godot export/compile step for ordinary authors.

Before activation, the generic runtime resolves mutable locators to an immutable release/revision, bounded-parses and verifies it, negotiates required schema/IR/features, stages allowed migrations, acquires/verifies the exact dependency and asset closure, evaluates current capabilities, and only then binds/executes untrusted semantics.

Unknown required features fail closed. Unsupported ordinary content does not silently fall back to privileged generated code.

### 9.4 Web/native/headless and offline/share

Web/native/headless profiles consume the same semantic `CreationRevisionId`; target payload projection/stripping may differ only under declared semantic usage requirements.

Hosted aliases may intentionally retarget, but historical immutable releases/revisions do not mutate. Offline launch uses the exact verified cached closure or reports typed unavailability/incompatibility; it does not float to a different compatible package/creation revision.

Persistent worlds do not silently advance when a new creation revision is published. Updating a world basis requires an explicit validated migration.

Per-creation builds are an exceptional **trusted deployment class**, not the ordinary publishing fallback or an escape hatch for untrusted GDScript/C#/native/JavaScript authority.

## 10. Protected media/provenance invariant

This invariant is cross-cutting and cannot be weakened by storage, collaboration, package, network, browser, engine, target, cache, import, publish, restore, or migration implementations.

A stable `AssetId` selects one complete immutable protected revision containing at least:

- content digest;
- source identity;
- source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution metadata;
- derivation lineage.

A replacement is accepted as one complete coherent revision or rejected before commit. Competing concurrent replacements remain complete alternatives; they are never field-merged into synthetic provenance.

Decoded/transcoded/imported/cached/target-private artifacts are derivatives of the canonical protected revision. They may not replace its source identity, semantic metadata, provenance, licence, or derivation record.

This invariant is explicitly verified in SMX-005/007/008/009/010/011/012/013/014/015/016/017/018/019 evidence and remains a production regression gate.

## 11. Hypothesis closure

The detailed machine-readable closure and contradiction audit is in `ARCHITECTURE-V1-AUDIT.json`. No hypothesis remains an unresolved Architecture-v1 blocker.

| Hypothesis | Final Architecture v1.0 status | Frozen interpretation |
|---|---|---|
| H-001 | accepted as decision | One faceted Thing kernel is the canonical base semantic model. |
| H-002 | accepted as decision | Hierarchy is structural/local; unrelated ownership/control/authority semantics are explicit. |
| H-003 | accepted as decision | Group and leaf share the Thing kernel. |
| H-004 | accepted with narrowed/refined scope | Local definition → portable package keeps one semantic lineage; physical package/discovery UX is not frozen. |
| H-005 | accepted with narrowed/refined scope | Compatible behaviour replacement is transactional with explicit state/pending-work migration; arbitrary hot compatibility is not promised. |
| H-006 | accepted with narrowed/refined scope | Built-ins/Rules/advanced authoring share one semantic IR boundary; final textual syntax/compiler/VM encoding is not frozen. |
| H-007 | accepted as decision | SplashMX owns canonical durable semantics above Godot serialization. |
| H-008 | accepted as decision | Durable semantic identity is path-independent. |
| H-009 | accepted with narrowed/refined scope | Capability semantics are accepted; production physical sandbox/decoder/crypto isolation still requires destructive implementation proof. |
| H-010 | accepted as decision | Thing meaning survives dormant/unloaded/rehydrated state without always-resident process objects. |
| H-011 | accepted with narrowed/refined scope | Logical streaming is object/subgraph-centric; physical byte batching/package/chunk boundaries may differ. |
| H-012 | accepted with narrowed/refined scope | Topology is runtime policy over one canonical network model for offline/peer/dedicated cases; transport/deployment details remain private. |
| H-013 | accepted as decision | Runtime simulation networking and document collaboration are separate consistency systems. |
| H-014 | accepted with narrowed/refined scope | Godot is replaceable-enough at the durable semantic boundary, not zero-cost replaceable as an implementation substrate. |
| H-015 | accepted as decision | Generic versioned runtimes are the ordinary publication model; per-creation builds are exceptional trusted deployments. |
| H-016 | accepted with narrowed/refined scope | One semantic system projects into the simple browser workflow; human comprehension/accessibility/final terminology remain product evidence gates. |
| H-017 | accepted with narrowed/refined scope | Offline-first canonical authoring is compatible with later sync; production durable collaboration storage/compaction/relay remains to implement. |
| H-018 | accepted with narrowed/refined scope | Compatibility is SplashMX-schema/IR/feature/migration driven; indefinite lossless migration of every future semantic change is not promised. |

No H-001–H-018 proposition is rejected by the completed research campaign. The narrowed statuses prevent model/prototype evidence from being overstated as production security, usability, performance, distribution, or durability certification.

## 12. Residual implementation risks and non-frozen choices

The architecture is coherent without pretending the implementation is already solved. The following remain explicit implementation/research obligations:

- **Real runtime performance and budgets:** final Godot object-fabric representation, browser startup/heap, frame/physics/audio cost, large-project editor responsiveness, memory accounting, and hardware/browser envelopes need production-grade measurement. Existing measurements are evidence, not universal SLOs.
- **Physical sandbox hardening:** process/origin isolation, archive libraries, media decoders, cryptographic trust roots/signature rotation/revocation freshness, hardened Godot templates, and calibrated CPU/GPU/audio/memory quotas require destructive implementation testing.
- **Canonical physical encoding/storage:** final bytes, index/chunking, database/file layout, crash-consistent persistence, browser quota/eviction/journaling, and migration tooling remain choices constrained by the semantic contract.
- **Package ecosystem:** final PackageId/version syntax, solver, container/index, registry/federation/CDN/mirroring, trust distribution, persistent cache, discovery, and marketplace UX remain implementation/product work.
- **Collaboration substrate:** CRDT/OT/oplog/database choice, compaction/tombstone retention, relay authentication/backpressure/outage handling, large-history performance, and conflict UI remain open below fixed semantic outcomes.
- **Networking deployment:** production authentication, WAN/NAT/TLS/ICE/signalling, cross-browser/mobile lifecycle, transport selection, congestion/scaling, anti-cheat policy, cluster consensus, and durable server failover remain below the frozen semantic layer.
- **Human usability/accessibility:** novice comprehension, terminology, accessibility, localization, touch/keyboard behavior, discoverability, and broad user studies remain first-class release gates.
- **Distribution/runtime retention:** CDN/hosting, historical runtime retention, native packaging/installers, long-term offline distribution and release operations remain product/infrastructure work.

These are not excuses to reopen established semantic decisions unless implementation evidence shows a genuine contradiction.

## 13. Production conformance gates

A production milestone may claim Architecture-v1 conformance only when relevant gates are green:

1. **Canonical semantics gate:** stable IDs/references, document validation, definition/instance semantics, complete protected asset revisions, and deterministic fixtures survive round-trip/migration without engine/process handles.
2. **Execution gate:** common IR semantics, ordering, hot replacement, lifecycle-persistent pending work, and independent resource budgets have adversarial tests.
3. **Security gate:** malformed package/document/IR/media/network cases fail before unsafe activation; no ambient host authority; revocation/delegation and resource limits are enforced at the real adapter boundary.
4. **Browser player/editor gate:** create→behave/connect→play→save/reload→publish/load and exact offline reload work without exposing engine/build/package internals; accessibility and real-user usability are independently tested.
5. **Multiplayer gate:** the same canonical creation executes offline, peer-hosted, and dedicated-authoritative under policy changes, with authority epochs/reconnect/failure behavior and hostile ingress verified on production transports.
6. **Collaboration gate:** accepted conflict corpus converges or surfaces explicit conflicts correctly under the selected production substrate, including offline reunion, schema migration, permissions, tombstones, crash consistency, and compaction.
7. **Component/package gate:** exact locks, update/migration rollback, principal-attributed capabilities, offline use, provenance/licensing, and hostile distribution/trust cases pass against production parser/store/resolver code.
8. **Publishing gate:** immutable creation revisions load in generic web/native/headless runtimes through the prepare-before-activate pipeline; hosted/offline/world identities remain distinct and exact.
9. **Compatibility gate:** version negotiation/migrations are failure-safe across supported historical fixtures and target/runtime upgrades; unsupported required semantics yield typed failure rather than silent reinterpretation.
10. **Performance gate:** named supported hardware/browser/runtime targets meet published workload budgets without violating the semantic or security boundaries above.

The production roadmap orders these gates so simple local/offline authoring remains continuously demonstrable rather than postponed until after infrastructure breadth.