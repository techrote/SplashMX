# SMX-015 decision and evidence handoff

**Status:** authoritative issue-level handoff for the SMX-015 destructive Object Fabric campaign, 2026-09-19. This file complements the repository-wide decision/evidence register and exists so downstream agents can retrieve the integrated findings without inferring them from test implementation.

## D-087 — P0–P4 share one stable semantic Object Fabric

**Status:** DECISION at integrated research-model level; production Godot/browser realization remains downstream.

The P0 universal-kernel, P1 live behaviour replacement, P2 local-definition/instance, P3 fresh restore, and P4 selective-streaming paths all use the same path-independent `ThingId` and explicit relationship/state contracts. Containment, controller, simulation authority, persistence, replication, observation, definition provenance, behaviour attachment, and residency stay distinct. No P0–P4 case required hierarchy or a live engine object to become ownership/identity.

**Evidence:** `OF-001`–`OF-010`, `OF-015`–`OF-021`, `OH-001`–`OH-020`, and the 37 deterministic tests in `experiments/smx-015-object-fabric-harness/`.

## D-088 — Hot replacement is prepare/acquire/validate/migrate/map/commit, with whole-operation rollback

**Status:** DECISION at integrated hot-replacement/lifecycle/streaming semantic level.

Replacement artifacts are exact and validated before live mutation. Stable `ThingId` and `AttachmentId` survive compatible replacement. Same-schema private state is preserved; incompatible schemas require explicit bounded migration. Durable pending work must remain compatible, be explicitly mapped, or be explicitly cancelled. Failure at acquisition, integrity, continuation compatibility, or migration leaves the previous implementation/state/work coherent. The same rules apply while the Thing record is logically unloaded; rehydration does not create a new Thing identity.

**Evidence:** `OF-010`–`OF-014`, `OF-021`–`OF-023`; P1/P4 adversarial tests.

## D-089 — Fresh restore and object-centric residency operate on semantic state, not surviving process objects

**Status:** DECISION at integrated lifecycle/streaming boundary.

A semantic snapshot can cross a JSON round trip and reconstruct the tested object graph in a fresh runtime from explicit records plus declared behaviour/artifact catalogs. Durable state includes tested Thing/definition/instance identities, references, private behaviour state, durable pending work, residency, relationships, tombstones, and protected asset revisions. Godot objects/resources/RIDs/NodePaths, peer/session IDs, live capability grants, decoded target-media handles, and editor/runtime context are excluded and must be rebound from current policy. References continue to distinguish `loaded`, `known_unloaded`, `tombstoned`, and `unknown`; a referenced Thing may reload without its containment region.

**Evidence:** `OF-015`–`OF-024`; P3/P4 tests including inventory-key → unloaded-door pressure.

## D-090 — Protected source/audio/provenance is an indivisible revision boundary through integration operations

**Status:** DECISION, explicit SMX-015 carry-forward of the protected-media contract.

A stable `AssetId` selects a complete immutable revision containing digest, source identity and metadata, audio/media semantics, provenance, licence, and derivation lineage. Snapshot/restore, unload/reload, definition/behaviour activity, and target-private runtime context cannot field-merge or rewrite that revision. Incomplete replacements fail without mutating the previous revision; a valid competing replacement replaces the whole bundle. Decoded/transcoded engine resources remain transient derivatives rather than canonical source identity.

**Evidence:** `OF-025`–`OF-027`, `OH-017`/`OH-018`, `test_protected_media.py`, and the P3 protected-media round-trip test.

## E-069 — Integrated Object Fabric falsification evidence

**Status:** REPRODUCIBLE RESEARCH EVIDENCE, non-production; 2026-09-19.

`experiments/smx-015-object-fabric-harness/` contains 37 deterministic adversarial/boundary tests covering the required P0–P4 experiments. The machine-addressable contract is `docs/research/SMX-015-OBJECT-FABRIC-FIXTURES.json` (`OF-001`–`OF-030`, `OH-001`–`OH-020`), and the synthesis is `docs/research/SMX-015-OBJECT-FABRIC-HARNESS.md`.

The integrated run found implementation hazards—publish-before-validation, partial identity mutation, invalid containment restoration, silent pending-work loss, and synthetic protected-media field mixing—but **no contradiction requiring amendment of the accepted upstream semantic contracts**. Each discovered implementation hazard is represented by an adversarial regression. `OF-030` requires future architecture-level failures to amend the authoritative upstream contract rather than be hidden by local special cases.

This evidence strengthens H-001/H-002/H-003/H-004/H-005/H-007/H-008/H-010/H-011/H-014/H-018 at the scoped integrated-model level. It does not strengthen H-009 security proof, H-012/H-013 network/collaboration claims, H-015 generic-player performance, H-016 usability, or H-017 production local-first persistence beyond their existing evidence.

## O-020 update — Real Godot/browser Object Fabric performance remains open after SMX-015

**Status:** OPEN. This update supersedes the earlier assignment of SMX-015 as a co-owner for real Godot/browser performance evidence.

SMX-015 now supplies a named semantic workload and integrated boundary, but the destructive harness intentionally invokes no Godot runtime, browser, native renderer, WebAssembly build, physics/audio/render binding, or production storage implementation. Therefore CPython execution time is not evidence for Godot Node/RID/resource creation cost, browser startup/heap/frame time, instance materialization cost, restore latency, or streaming/binding churn.

**Owner:** SMX-019 must measure real named Godot/browser builds and hardware for creation/binding, definition-instance materialization, hot replacement, fresh restore, selective residency, startup/memory/frame-time, and related generic-player/editor paths. SMX-020 must carry any unresolved performance risk into Architecture v1.0 rather than treating this model result as a benchmark.

## Downstream ownership

- **SMX-016:** hostile parser/package/IR/capability/resource attacks; the SMX-015 Python model is not a sandbox.
- **SMX-017:** real offline/peer-hosted/dedicated topology equivalence under loss, suspension, reconnect, and host failure while preserving SMX-015 identity/lifecycle/streaming semantics.
- **SMX-018:** real collaboration substrate/convergence/compaction evidence over canonical semantic loci; runtime replication is still not the edit protocol.
- **SMX-019:** real Godot/browser editor/player/storage/performance and create→play→save/reload→publish/load evidence, including O-020.
- **SMX-020:** final reconciliation/freeze using both the P0–P4 positive evidence and all explicitly unproven areas.
