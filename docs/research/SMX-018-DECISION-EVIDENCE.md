# SMX-018 decision/evidence handoff

Status: authoritative issue-level handoff for SMX-018 destructive collaboration evidence, 2026-09-19. This file supplements the project register and must be retrieved with `SMX-018-COLLABORATION-HARNESS.md` and its fixtures.

## Decisions

### D-099 — Collaboration transport is semantically subordinate to the SplashMX transaction/conflict layer

The destructive harness transports exact serialized semantic transactions through a content-checked relay that has no document merge policy. Offline/reconnect/reorder/duplicate behavior therefore does not require the relay, CRDT, OT engine, database, or transport to become the public authoring model. Production substrate selection remains open provided it preserves CH-001–CH-028.

### D-100 — Replica convergence and canonical document validity are independent gates

Equal replicas are insufficient. Every candidate semantic transaction is staged atomically and the resulting SplashMX graph is validated before commit. Invalid endpoints, ports, overlays, structure or protected-media bundles hold the whole transaction rather than converging on an invalid document.

### D-101 — Definition/instance collaboration loci include DefinitionId, not only local element names

Definition removal and instance-overlay conflict classification resolves the instance's actual DefinitionId. Identically named elements in unrelated definitions do not conflict. This is R-018-01 and tightens COL-007 without changing definition/instance ownership semantics.

### D-102 — Durable Thing deletion has explicit referential-integrity consequences

A concurrent new connection naming a deleted Thing is held under the Thing tombstone/remove-wins rule (R-018-02). Tombstoning a Thing also tombstones incident live ConnectionIds in the same atomic semantic edit (R-018-04), leaving history intact but no dangling active edge. Hierarchy still does not imply behavioral/network/persistence ownership.

### D-103 — Offline authority is never serialized into collaboration history

Offline edits retain actor/permission-epoch evidence, but reunion revalidates current policy. Stale permission work remains recoverable history and is rejected from shared materialization. Runtime peer/session IDs, authority epochs, capability grants and host handles remain forbidden collaboration data.

### D-104 — Protected asset revisions are indivisible collaboration alternatives

A stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. Label metadata may merge independently, but concurrent replacements remain complete alternatives and incomplete revisions are rejected before history admission.

## Evidence

### E-074 — 39 deterministic multi-editor collaboration tests pass in the disposable harness

`experiments/smx-018-collaboration-harness/` executes CR-001–CR-028 plus eleven boundary/adversarial tests. It exercises offline divergence/reunion, opposite arrival order, duplicate delivery, transaction-ID collision, missing causal ancestry, delete/edit, reparenting, definitions/instances, stable ports/connections, timeline overlap, grouping, component update, selective undo/redo, permission changes, transient presence, schema mismatch, known-unloaded/tombstoned targets, explicit resolution, protected asset replacement, transaction atomicity and causal-cycle rejection.

### E-075 — Four semantic-integrity defects are now explicit regressions

R-018-01 through R-018-04 cover DefinitionId-scoped conflict classification, Thing-delete/new-connection interaction, whole-document validation before transaction commit, and atomic tombstoning of incident connections. These arose from destructive integration pressure rather than broad rediscovery.

### E-076 — The operation-log research footprint is measurable but not production evidence

The reproducible 256-edit probe records serialized history, persisted collaboration snapshot and canonical document sizes plus CPython rematerialization timing. The reference development run on CPython 3.13.5/Linux x86_64 produced 53,394 bytes transaction history, 10,922 bytes persisted collaboration snapshot and 6,208 bytes canonical snapshot; median rematerialization was 139.8 ms across 15 runs. This intentionally does not select a production CRDT/database/compaction strategy.

## Hypothesis effects

- **H-013 strengthened further.** Collaboration requires causal edits/conflicts/history/undo/schema/policy semantics absent from runtime replication, and runtime-multiplayer fields are rejected from collaboration payloads.
- **H-017 strengthened substantially at destructive model level; production durability remains open.** Valid offline work survives reorder/duplicate reunion without cloud-document authority or silent server-copy loss.
- **H-018 strengthened narrowly at collaboration-history level.** Schema-incompatible work is quarantined pending deterministic semantic migration rather than mechanically merged.

## O-026 — Production collaboration substrate, compaction and durable synchronization

**Status: OPEN after SMX-018.** The harness validates semantic requirements but does not choose/qualify a production CRDT/OT/log/database, compaction/checkpoint/tombstone-retention proof, browser/native crash-consistent store, relay outage/backpressure/authentication behavior, multi-version migration at production scale, or large-project conflict/history performance and UX.

Owner: SMX-019 for browser/editor integration and storage/latency/failure evidence where practical; SMX-020 for Architecture v1.0 reconciliation and any residual research spike.
