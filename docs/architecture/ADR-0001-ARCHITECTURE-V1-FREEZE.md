# ADR-0001 — Freeze SplashMX Architecture v1.0

- **Status:** Accepted
- **Date:** 2026-09-19
- **Issue:** SMX-020 / #20
- **Decision scope:** durable SplashMX semantic architecture

## Context

SMX-001 through SMX-019 progressively defined and then destructively tested the SplashMX object kernel, composition, execution, canonical document, capability security, lifecycle, streaming, Godot boundary, runtime multiplayer, collaboration, authoring projection, portable components, generic publishing, integrated Object Fabric, hostile security boundary, real network topologies, offline/reconnect collaboration, and real-browser author/player projection.

The research corpus contains intentionally provisional wording and disposable implementations. Leaving every research document equally authoritative after the campaign would require future implementers to reconstruct chronology and could allow an earlier provisional assumption to be mistaken for a final decision.

SMX-020 therefore performs the explicit reconciliation required by the research programme rather than merely summarizing it.

## Decision

Freeze `docs/architecture/ARCHITECTURE-V1.md` as the semantic Architecture v1.0 baseline beneath the project constitution.

Architecture v1 adopts the following integrated decisions:

- one path-independent Thing semantic kernel for leaves and groups;
- containment/locality separate from control, authority, persistence, replication, observation and other relationships;
- ordinary group → reusable local Definition → portable package as one semantic lineage;
- stable semantic ports/connections and path-independent references;
- modular Behaviour execution through one constrained, budgeted IR/service boundary;
- transactional behaviour/update/migration publication with whole-state validation and rollback;
- an engine-independent canonical document with explicit authored/runtime/persistent/transient/collaboration/publication planes;
- semantic lifecycle and object/subgraph streaming independent of surviving engine objects or physical package/chunk boundaries;
- deny-by-default principal-attributed capabilities and layered pre-activation validation for untrusted content;
- one topology-independent runtime network model across offline, peer-hosted and dedicated-authoritative execution;
- a separate collaboration consistency plane with SplashMX-owned conflict semantics above replaceable sync/storage machinery;
- Godot as the intended first private rendering/audio/input/physics/runtime substrate, not the public compatibility boundary;
- exact immutable package/dependency locks for runtime use;
- ordinary publishing as immutable creation data consumed by versioned generic runtimes rather than per-creation Godot builds;
- exact offline closure and persistent WorldSave identity separate from mutable aliases and published creation identity;
- stable `AssetId` selecting one complete immutable digest/source/audio-or-media/provenance/licence/derivation revision across every subsystem.

The hypothesis closure in Architecture v1 deliberately narrows claims where research established semantic viability but not production certification. Production physical sandboxing, human usability, performance, storage, collaboration substrate, network deployment, distribution, and similar implementation evidence remain explicit conformance obligations rather than unresolved semantic architecture blockers.

## Contradiction reconciliation

The machine-readable audit `docs/architecture/ARCHITECTURE-V1-AUDIT.json` records the overlapping domains compared during freeze and their resolution. Important corrections discovered by destructive work are incorporated into the frozen contract, including:

- R-016-01 through R-016-04 for path normalization, serialized authority rejection, delegation ancestry bounds, and last-moment capability reauthorization;
- R-018-01 through R-018-04 for DefinitionId-scoped conflicts, delete/new-connection semantics, whole-document validation before commit, and incident-connection tombstoning;
- R-019-01 distinguishing canonical SplashMX `ConnectionId` from transient transport connection identity.

No known foundational contradiction remains among the frozen object, execution, document, lifecycle, security, network, collaboration, Godot, component, publishing, or protected-media semantics.

## Supersession and retained evidence

Research documents under `docs/research/` remain authoritative evidence and detailed domain specifications when consistent with Architecture v1. They are not deleted because they carry fixtures, counterexamples, measurements, rejected alternatives, provenance, and residual-risk boundaries.

Where provisional research wording conflicts with the constitution or `ARCHITECTURE-V1.md`, the constitution and frozen architecture take precedence. A future semantic change must use an accepted ADR, identify the affected Architecture-v1 decision, reconcile downstream contracts, and add regression evidence.

Disposable research harness code remains explicitly non-production unless separately reviewed and adopted.

## Consequences

Positive consequences:

- production implementation can retrieve a short, coherent authority chain instead of replaying the full research campaign;
- internal representation remains free to evolve while stable semantic boundaries are explicit;
- security, multiplayer, collaboration, publishing and editor work share one identity/document model;
- residual product/implementation work is visible without being misstated as architectural uncertainty;
- protected source/audio/provenance semantics remain a cross-cutting invariant rather than a subsystem convention.

Costs and constraints:

- implementations must sometimes build adapters rather than expose convenient Godot/browser/storage identities directly;
- migrations and exact dependency/publication identity require deliberate versioning from the beginning;
- the production security boundary must be proven at physical target layers even though semantic capability rules are frozen;
- collaboration/network/package technologies must fit the accepted semantics rather than redefining product behavior around library defaults;
- future architecture changes require explicit evidence and ADR/regression work.

## Implementation handoff

`docs/architecture/IMPLEMENTATION-ROADMAP-V1.md` is the dependency-ordered production handoff. It classifies research code as reusable conformance evidence, reference-only/disposable prototypes, or functionality requiring a production rewrite/selection. It keeps local/offline authoring continuously testable and defers cloud/marketplace breadth until the coherent core exists.