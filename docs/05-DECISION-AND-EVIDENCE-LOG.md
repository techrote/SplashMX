# SplashMX decision and evidence log — post Architecture v1.0

**Status:** active post-freeze register from 2026-09-19.  
**Exact pre-freeze decision/evidence chronology:** `docs/05-DECISION-AND-EVIDENCE-LOG.pre-v1.md`  
**Frozen architecture:** `docs/architecture/ARCHITECTURE-V1.md`  
**Machine-readable reconciliation:** `docs/architecture/ARCHITECTURE-V1-AUDIT.json`

The full D-/E-/O- chronology accumulated by SMX-001 through SMX-019 is preserved byte-for-byte at the historical path above. It remains the evidence trail for research-era decisions, primary-source freshness, rejected alternatives, measurements, and open questions.

This active file starts at SMX-020 so future agents do not need to traverse more than one hundred historical entries to discover the current authority. Historical entries remain citable by their original IDs and are not renumbered or rewritten.

## SMX-020 Architecture v1.0 freeze register

### D-117 — Architecture v1 freezes one Thing fabric with explicit relationships and path-independent identity

**Status:** DECISION / Architecture v1.0.

Leaves, groups, local reusable structures, portable components, runtime objects and authoring projections use one SplashMX Thing semantic fabric. Durable semantic identity is independent of hierarchy path and target-private runtime handles. Containment/locality does not silently imply behaviour ownership, input control, simulation authority, persistence ownership, replication/relevance, observation, collaboration presence, or editor selection.

Ordinary group → reusable local `Definition` preserves existing first-instance `ThingId` values. Stable public ports and canonical `ConnectionId` identify semantic interfaces independently of paths and transient transport connections.

**Evidence:** SMX-002/003/005/015 destructive evidence; R-018-01/R-018-02/R-018-04; R-019-01. Final contract: `docs/architecture/ARCHITECTURE-V1.md` sections 2–3.

### D-118 — Architecture v1 freezes one constrained execution/service boundary for ordinary user intent

**Status:** DECISION / Architecture v1.0.

Built-ins, beginner Rules, visual logic and future advanced/textual authoring target one bounded semantic IR/service boundary. Arbitrary GDScript, C#, native extension execution, browser JavaScript host access and raw engine/OS APIs are not ordinary user-content semantics.

Scheduling/order where author-visible is SplashMX-defined. Timers/continuations are explicit semantic work rather than durable engine stacks. Resource amplification classes are independently bounded. Runtime services are capability-mediated and attributed to the originating principal. Compatible behaviour replacement is staged, quiescent, migration-aware and atomic; failure preserves the old coherent state.

**Evidence:** SMX-004/006/008/015/016; R-016-03/R-016-04. Final contract: Architecture v1 sections 4 and 6.

### D-119 — Architecture v1 freezes canonical state planes, whole-result validation, semantic lifecycle, object-centric logical streaming and migration-driven compatibility

**Status:** DECISION / Architecture v1.0.

Editable authored state, transient editor/session context, transient runtime materialization, selected persistent `WorldSave` state, collaboration history/conflict state and immutable published creation revisions are distinct planes. Multi-record semantic changes stage and validate the complete resulting document before commit.

Restore reconstructs from semantic authored basis + permitted persistent state + exact artifacts, not surviving Godot/process handles. Known-unloaded is distinct from tombstoned/destroyed. Logical streaming may load object/subgraph closures independently of containment while physical chunks/packages/cache batches remain non-semantic policy. Compatibility is expressed through SplashMX schema/IR/features/interfaces and explicit bounded migrations rather than implicit Godot-version equality.

**Evidence:** SMX-005/007/008/013/014/015/018; R-018-03. Final contract: Architecture v1 section 5.

### D-120 — Architecture v1 freezes topology-independent runtime networking and a separate collaboration consistency plane

**Status:** DECISION / Architecture v1.0.

Offline/local, peer-hosted browser and dedicated-authoritative execution share one canonical runtime network declaration and Thing semantics. Principal/session identity, transient transport peer identity, control, simulation authority/epoch, replication/relevance, containment and persistence remain distinct.

Collaborative editing uses durable causal semantic transactions, tombstones, conflicts/resolution, schema/history handling, permissions epochs and offline reunion above a replaceable sync/store substrate. Runtime replication is not reused as document collaboration merely because infrastructure can be shared.

**Evidence:** SMX-010/011/017/018/019. Final contract: Architecture v1 section 7.

### D-121 — Architecture v1 freezes Godot as private first substrate rather than the public compatibility boundary

**Status:** DECISION / Architecture v1.0.

SplashMX owns durable object/document/execution/security/network/collaboration/package/publication semantics. Godot may privately supply rendering, audio, input, physics, runtime/platform facilities, decoding/import, storage adapters and network transports.

`Node`, `NodePath`, `SceneTree`, `RID`, `ResourceUID`/resource paths, Godot peer IDs/RPC annotations and imported-resource identities are not canonical SplashMX identity. Architecture v1 accepts practical first-implementation dependence on Godot behavior/performance while keeping durable user content sufficiently engine-independent for migration/evolution.

The architecture evidence baseline is Godot 4.7.2 stable, checked 2026-09-19. Target-specific browser/native/headless limitations are typed runtime capabilities/policy rather than new canonical object models.

**Evidence:** SMX-009/014/017/019 and pre-freeze E-040..E-049/E-083..E-087. Final contract: Architecture v1 section 8.

### D-122 — Architecture v1 freezes exact component locks and generic immutable-data publishing

**Status:** DECISION / Architecture v1.0.

An ordinary local Definition becomes portable by adding `PackageId` + immutable package revision around the same semantic lineage. Human version requirements resolve intentionally to an exact immutable lock before runtime/streaming/publishing/offline use. Required/optional/lazy edges, staged update/migration and rollback are explicit; package provenance/signatures/source/remix/licensing never mint host capability.

Ordinary Publish creates an immutable SplashMX `CreationRevisionId` for a separately built versioned generic web/native/headless runtime. It does not invoke per-creation Godot export/compilation. Hosted aliases may retarget without rewriting immutable releases; offline execution requires the exact verified cached closure or typed unavailability/incompatibility. `WorldSave` is a separate lineage anchored to an explicit creation basis.

**Evidence:** SMX-013/014/016/019. Final contract: Architecture v1 section 9.

### D-123 — Protected source/audio/provenance semantics are an indivisible cross-cutting Architecture-v1 invariant

**Status:** DECISION / Architecture v1.0; protected semantic boundary.

A stable `AssetId` selects one complete immutable revision containing:

- digest;
- source identity;
- source metadata;
- audio/media semantics;
- provenance;
- licence/attribution metadata;
- derivation lineage.

Replacement commits the complete coherent revision or leaves the previous one untouched. Concurrent alternatives remain complete revisions and are never field-merged into synthetic provenance. Decoded/transcoded/imported/cached/target-private artifacts are derivatives and cannot replace the canonical source identity/metadata/audio-media meaning/provenance/licence/derivation record.

This invariant applies to documents, lifecycle, streaming, packages, collaboration, networking, publishing, offline caches, web/native/headless projection, migration and Godot bindings.

**Evidence:** SMX-005/007/008/009/010/011/012/013/014/015/016/017/018/019 protected-media regressions. Final contract: Architecture v1 section 10.

### E-088 — SMX-020 contradiction audit closes the cross-domain research seams required for Architecture v1

**Status:** REPRODUCIBLE REPOSITORY EVIDENCE / freeze audit, 2026-09-19.

`docs/architecture/ARCHITECTURE-V1-AUDIT.json` records final disposition for exactly H-001 through H-018 and twenty-two cross-domain seams spanning containment/authority, Godot/canonical identity, semantic/transport Connection identity, runtime networking/collaboration, state planes, Definition/package lineage, requirements/exact locks, generic publish/per-creation builds, protected media/target derivatives, logical streaming/physical chunks, signatures/capabilities, durable/live handles, delete/Connection behavior, semantic validation/convergence, definition conflict identity, staged migration/activation, creation/world identity, offline exactness, Together/People, authoring views/model, browser-store/semantic identity and Godot RPC/network semantics.

All twenty-two audit rows resolve to explicit Architecture-v1 rules and cite retained SMX evidence. The validator `tools/validate_smx020.py` fails the freeze if any H-001–H-018 disposition is missing, a contradiction row is unresolved, protected-media fields change, the corrective findings disappear, or the post-freeze authority/roadmap chain is incomplete.

No hypothesis remains a deferred/unresolved Architecture-v1 blocker. Narrowed statuses deliberately avoid converting semantic/model evidence into unearned claims of production sandbox certification, performance, human usability, storage durability, distribution scale or network operations.

### O-029 — Post-freeze implementation evidence obligations

**Status:** OPEN implementation/product obligations; not Architecture-v1 semantic blockers.

Architecture v1 does not pretend that research prototypes are production implementations. The following must be resolved by the dependency-ordered production roadmap and its conformance gates:

1. real Godot/browser/native/headless object-fabric, startup, memory, frame, physics and audio performance budgets;
2. production process/origin isolation, archive parsing, media decoder safety, cryptographic trust/signature/revocation, hardened runtime configuration and calibrated resource accounting;
3. final canonical physical encoding, indexes/chunks, crash-consistent local/browser storage, quota/eviction and migration tooling;
4. package version syntax/solver/container/index/registry/federation/CDN/trust/cache/discovery implementation;
5. production collaboration CRDT/OT/oplog/database choice, compaction/tombstone retention, crash consistency, relay/backpressure/authentication and large-history performance;
6. production multiplayer authentication, transport/signalling/NAT/TLS/ICE, browser/mobile lifecycle, congestion/scaling, anti-cheat and durable server failover;
7. novice comprehension, final terminology, accessibility, localization, touch/keyboard behavior, discoverability and broad usability evidence;
8. hosted distribution/CDN, historical runtime retention, native packaging/installers and long-term offline release operations.

Owner/order: `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md`. A later spike that discovers a semantic contradiction must amend Architecture v1 through an explicit ADR plus regression; selecting an implementation beneath the frozen boundary does not itself reopen the architecture.

## SMX-022 physical representation/store selection register

### D-124 — SMX-022 selects deterministic CBOR, stable-ID shards and target-specific transactional local stores

**Status:** DECISION / production mechanism selection beneath Architecture v1.

Canonical record/revision bytes use a SplashMX-owned deterministic-CBOR profile. Partial access uses bounded stable-semantic-ID hash shards with local indexes and a small immutable root manifest; physical shard/offset/database placement remains non-semantic. Browser editable-project ownership uses one IndexedDB revision/head transaction with prepared OPFS immutable blobs/chunks. Native editable-project ownership uses SQLite WAL with synchronous=FULL plus prepared immutable blob/chunk files. Rollback-journal FULL remains a compatible native fallback.

The selected mechanisms preserve whole-result validation-before-publication, previous-head rollback, known-unloaded references, protected Asset revision atomicity, replaceable cache/chunk placement and future semantic collaboration/history loci. No canonical/core/storage production module is activated by this spike.

**Evidence:** `docs/research/SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md`, `SMX-022-PHYSICAL-STORE-FIXTURES.json`, `SMX-022-NATIVE-EVIDENCE.json`; RFC 8949; Protocol Buffers canonical-serialization warning; SQLite atomic-commit/durability documentation; current IndexedDB/OPFS/Storage API evidence.

### E-089 — SMX-022 comparative native mechanism evidence is reproducible; real-browser campaign remains an explicit merge gate

**Status:** REPRODUCIBLE SPIKE EVIDENCE, 2026-09-19.

The disposable SMX-022 harness compares canonical JSON and deterministic CBOR across tiny/nested/many fixtures, bounded shard policies across a 1,500-Thing/3,000-Connection project, and abrupt native publication recovery. Deterministic CBOR was 18–20% smaller than the canonical JSON projection in the captured fixtures. Stable-ID sharding made a direct partial read orders of magnitude cheaper than monolithic decode in the disposable oracle and falsified a 256 KiB default because tiny-edit write amplification rose to about 562x. SQLite WAL/FULL, rollback/FULL and careful atomic revision files all reopened coherently at the previous head before commit and the new head after completed publication.

These timing observations are environment-specific evidence, not product SLOs. The dedicated pinned-Chromium workflow must pass before merge and its artifact is to be incorporated into the issue/PR evidence.

### O-030 — SMX-024/025 own productionization below the selected physical boundary

**Status:** OPEN implementation detail, not a renewed broad mechanism-selection question.

SMX-024 owns the production deterministic-CBOR implementation, exact record/schema layout, bounded parser, golden bytes, shard-policy identifier, migration fixtures and protected Asset serialization. SMX-025 owns IndexedDB/OPFS and SQLite adapters, typed quota/denial/corruption failures, reopen/interruption recovery, orphan GC, backup/export behavior, checkpoint/GC cadence and tuning. Neither may turn database rows, paths, DOM/FileSystem handles, cache keys, byte offsets or shard placement into canonical identity.

## Historical late-campaign regression anchors

These compact anchors retain exact marker strings consumed by already-merged SMX-015/016/018/019 validators. They point to the byte-identical pre-v1 log for full text and do not re-open or duplicate the frozen decisions above.

## SMX-015 decision/evidence register

Historical entries: D-087 · D-088 · D-089 · D-090 · E-069 · O-020 update. The SMX-015 destructive Object Fabric result retained the **protected source/audio/provenance** boundary and handed real Godot/browser performance evidence forward rather than overclaiming it.

## SMX-016 decision/evidence register

Historical entries: D-091 through D-098 (including D-091 and D-098), E-070 through E-073 (including E-070 and E-073), O-025. The hostile harness retained the **protected source/audio/provenance** boundary and R-016-01 through R-016-04 while explicitly not claiming end-to-end physical sandbox certification.

## SMX-018 decision/evidence register

Historical entries: D-099 through D-104 (including D-099 and D-104), E-074 through E-076 (including E-074 and E-076), O-026, R-018-01 through R-018-04 (including R-018-01 and R-018-04). The collaboration harness retained complete **protected source/audio/provenance** alternatives rather than field-merging them.

## SMX-019 decision/evidence register

Historical entries: D-111 · D-112 · D-113 · D-114 · D-115 · D-116; E-083 · E-084 · E-085 · E-086 · E-087; O-028. SMX-019 supplied the real-Chromium author/player projection evidence and R-019-01 while preserving the complete protected Asset revision semantics.

## Historical decision/evidence retrieval

Use `docs/05-DECISION-AND-EVIDENCE-LOG.pre-v1.md` for D-001 through D-116, E-001 through E-087, O-001 through O-028 and their exact dates/sources/wording. Those records are intentionally historical and must not be edited to make the final architecture appear predetermined.

The post-freeze RAG index maps current domains to the relevant retained research evidence. New decisions/evidence/open questions should continue numbering from this file rather than rewriting the archived pre-v1 chronology.