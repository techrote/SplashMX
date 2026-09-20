# SMX-031 — production-core vertical conformance gate

**Status:** production integration gate  
**Issue:** #56  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Programme authority:** `docs/implementation/PRODUCTION-PROGRAMME-V1.md`

SMX-031 does not introduce another runtime, semantic kernel, or proof-model substrate. It composes the production modules delivered by SMX-023 through SMX-030 into one durable non-UI vertical and makes their cross-boundary invariants executable before browser editor, package, or Godot breadth is allowed to depend on them.

## Contents

| Section | Summary |
|---|---|
| Production contract | Defines the integrated gate and the production modules it is allowed to use. |
| Vertical flow | Records create/reuse/behave/connect/play/stop/save/restore behavior. |
| Lifecycle and exact streaming | Defines unload/rehydrate, exact artifacts and fresh-runtime behavior. |
| Failure and rollback seams | Defines the adversarial boundaries that must remain atomic. |
| Capability and resource boundaries | Keeps execution bounded and host authority explicit. |
| Protected source/audio/provenance boundary | Restates the indivisible protected-media contract. |
| Benchmark evidence | Defines the measured evidence emitted by CI. |
| Downstream handoff | States what later phases may now rely on and what remains out of scope. |

## Production contract

The gate is implemented by `tests/production/smx031_harness.py`; that file is an integration fixture only. It imports and delegates to these production modules directly:

- `canonical.core` — stable IDs, transactions, grouping/Definitions, Connections;
- `canonical.serialization` — canonical project envelope and protected Asset revisions;
- `storage.local` — crash-safe local canonical project persistence;
- `execution.ir` — Rule compilation, Behaviour IR, deterministic scheduling and budgets;
- `security.capabilities` — principal-attributed deny-by-default capabilities;
- `execution.hotswap` — prepare-before-publish Behaviour replacement;
- `runtime.lifecycle` — WorldSave, unload/rehydrate, tombstones and fresh-runtime restore;
- `runtime.streaming` — exact acquisition and immutable cache behavior.

No code from the pre-v1 Python research models or the SMX-019 browser proof implementation is used to make the production result pass. Those artifacts remain retained evidence only.

The executable fixture contract is `spec/production/smx031-core-gate-fixtures.json`, `PCG-001..PCG-024`. The dedicated regression is `.github/workflows/smx031-production-core-gate.yml`.

## Vertical flow

The representative fixture creates a canonical project with a grouped subgraph, promotes that group to a local reusable Definition, and instantiates a second copy with independent stable `ThingId` values. It attaches a compiled beginner Rule and a materially separate advanced Behaviour through the production common IR, creates a stable-port Connection, and includes a durable inventory-style reference to a separate Thing.

Play creates a `WorldRuntime` from the exact authored document and program registry. Rule and Behaviour mutations affect transient runtime state only. The canonical authored revision remains unchanged. Stop is represented by discarding the transient Play runtime and rebuilding from the same authored revision; authored defaults therefore return without changing semantic identity.

Save/reload uses `SQLiteProjectStore`, not a fixture-local persistence implementation. The project round-trip must preserve Definitions/instances, relationships, stable-port Connections, Behaviour attachment revisions and the complete protected Asset revision.

World state is snapshotted independently through the SMX-029 WorldSave plane. The gate launches a new Python process that reopens the canonical project store, parses the WorldSave and restores a fresh `WorldRuntime` from semantic state plus the exact Behaviour registry. The subprocess receives no surviving engine/browser/network/session/capability object from the originating runtime.

## Lifecycle and exact streaming

The fixture streams the Behaviour-bearing worker Thing to `known-unloaded` while keeping the inventory reference holder resident. That durable reference continues to name the same `ThingId`; it does not degrade to unknown and it does not force containment-region loading.

Re-entry acquires a digest-bound canonical project artifact plus the exact required Behaviour IR through `runtime.streaming`. Acquisition validates exact project revision, Thing basis, Behaviour revision and protected Asset revision before staged rehydration is published. Missing exact dependencies are typed failures and leave the previously coherent known-unloaded WorldSave unchanged.

Cache eviction remains non-semantic: removing verified artifact bytes from the local immutable cache cannot change WorldSave, authored state, stable references, protected Asset meaning or lifecycle state. A tombstoned Thing is never a cache miss and can never be resurrected by a catalog entry.

## Failure and rollback seams

SMX-031 intentionally crosses failure boundaries rather than only replaying a happy path. The production test campaign verifies that:

- a duplicate canonical identity fails the whole authored transaction and leaves the prior project revision unchanged;
- a failed Behaviour hot replacement leaves the exact previous program and runtime state active;
- missing streaming dependencies fail before activation;
- corrupt WorldSave bytes fail before fresh runtime publication;
- rebinding one `ProjectRevisionId` to different canonical/protected-Asset bytes is rejected by the physical store;
- a competing complete protected Asset revision cannot be silently substituted during stream-in;
- tombstones remain destructive semantic facts rather than load-state hints.

These checks complement, rather than replace, the narrower SMX-023..030 module tests. The gate exists specifically to catch incorrect assumptions at module seams.

## Capability and resource boundaries

The representative runtime includes an amplification Behaviour executed under a deliberately small production `BudgetLimits` instruction ceiling. It first stages a public mutation and then exceeds the instruction budget. The activation faults with the typed execution budget code and the staged public mutation is rolled back, proving that the integration path does not weaken the SMX-026 transactional budget boundary.

The same fixture derives the worker principal from stable `ThingId + BehaviourAttachmentId` semantics and requests a required `network.http` capability from an empty `CapabilityBroker`. The request is denied. There is no ambient authority inherited from containment, project provenance, connection structure, persistence or protected media metadata.

Capability grants, leases, host handles and transient session identifiers are not serialized into the canonical project or WorldSave. A later authorized host call must still cross the SMX-027 trusted host-service boundary and perform final-use authorization immediately before host use.

## Protected source/audio/provenance boundary

A stable `AssetId` continues to select exactly one complete immutable protected revision. The revision is indivisible across **content/source digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**.

SMX-031 verifies the complete field set survives canonical serialization, local persistence, fresh-process reopen and streaming. It also creates a competing complete revision for the same `AssetId` and proves that streaming rejects the conflict atomically rather than mixing fields from the two revisions.

WorldSave, caches, decoded/transcoded derivatives, runtime state, capability state and the integration harness itself have no authority to redefine or partially replace those protected fields.

## Benchmark evidence

`tools/measure_smx031.py` executes the production vertical repeatedly and writes `splashmx.benchmark-evidence/1` metadata. The dedicated workflow validates the evidence shape against the SMX-021 contract and uploads the JSON artifact.

The measurements are **conformance/footprint evidence for the non-UI integration gate**, not a Phase-6 performance qualification. They record named runtime/environment data plus representative end-to-end local vertical latency and persisted canonical/WorldSave byte sizes. They must not be converted into a supported-hardware claim; GATE-10 remains owned by later measured target work.

## Downstream handoff

Once this gate is green on `main`, SMX-032/browser authoring and SMX-037/Godot realization selection may treat the non-UI production core as an executable dependency rather than rebuilding semantics in UI/platform-specific mocks. The stable handoff is the existing production module surface plus the PCG regression campaign, not a new SMX-031 API layer.

This gate does **not** implement browser UI, package resolution/publication, Godot rendering/audio/input/physics bindings, hostile package/media parser hardening, collaboration, multiplayer transport, or distribution. Those remain owned by their dependency-ordered production issues. Architecture v1 is unchanged.
