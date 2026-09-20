# SMX-030 — logical streaming, exact acquisition, and immutable local cache

**Status:** production implementation for issue #55.  
**Architecture:** SplashMX Architecture v1.0.  
**Owner module:** `runtime.streaming`.  
**Conformance gates:** GATE-01 and GATE-09.

This implementation ports the accepted SMX-008/015 streaming semantics into the production core without turning containment, paths, URLs, cache keys, package layout, or host/runtime handles into identity. It composes with SMX-024 canonical serialization, SMX-025 local persistence, SMX-028 Behaviour replacement, and SMX-029 lifecycle/WorldSave semantics.

## Production contract

`StreamingRuntime` coordinates logical residency over `WorldRuntime`; `ExactAcquirer` resolves a bounded graph of `ExactArtifactDescriptor` values; `ImmutableArtifactCache` retains verified bytes by immutable digest only. A descriptor binds a manifest-local artifact label to an exact SHA-256 digest, exact byte length, artifact kind, exact dependency IDs, and required features. A URL, file path, package path, cache key, engine handle, peer/session ID, or process handle is never part of semantic identity.

Logical residency is separate from authored semantic existence. `stream_out()` moves only selected live Things to SMX-029 `known-unloaded` runtime state and retains their persistent runtime snapshot. The authored `ThingId` and durable references remain unchanged. `stream_in()` accepts only known-unloaded Things, resolves their exact catalog closure, validates every artifact, stages all materialization/migration work, then rehydrates the selected Things. Containment is not consulted as an implicit load unit, so a child may unload/reload while its containment parent remains resident.

Loaded, known-unloaded, tombstoned, and unknown remain distinct. A loaded request is an explicit no-op. Unknown targets fail typed. Tombstoned targets fail before acquisition and cannot be resurrected by cached bytes, stale descriptors, timers, queued work, or a previously valid catalog.

## Exact acquisition and bounded dependency graph

The acquisition path is prepare-before-publish:

1. resolve the requested exact descriptor roots;
2. walk only declared exact dependencies with independent descriptor-count, depth, per-artifact-byte, and aggregate-byte limits;
3. reject unknown required features before activation;
4. reuse a cached payload only after rechecking its exact length/digest;
5. otherwise fetch bytes through the source adapter and verify exact length/digest before caching;
6. decode and validate/migrate canonical or Behaviour artifacts while still staged;
7. reconcile the canonical Thing/Definition/protected-asset basis against the active exact `ProjectRevisionId`;
8. rehydrate on a private staged `WorldRuntime` copy;
9. publish only after the entire requested set is coherent and an optional cancellation check still permits publication.

Bounded declarative dependency cycles are allowed because exact artifacts may mutually describe a closed component graph. Graph traversal is cycle-safe and publication is still atomic. Missing descriptors, unavailable bytes, corrupt bytes, unsupported required features, incompatible project/Thing/Definition/Behaviour semantics, resource limits, source failures, and cancellation all produce typed `StreamingError` failures and leave the old coherent runtime published.

This phase intentionally does **not** implement a semver/package solver or package container. Phase-5 package work owns resolution policy. SMX-030 receives already exact descriptors and refuses to float to a merely compatible substitute.

## Canonical and Behaviour migration before activation

Canonical subgraph artifacts reuse the SMX-024 deterministic-CBOR revision/shard profile inside a small streaming envelope. `deserialize_project()` therefore performs bounded canonical decode, supported-version migration, required-feature checks, record/shard integrity checks, identity checks, and whole-project validation before the artifact may participate in activation. A canonical artifact from another `ProjectId` or exact `ProjectRevisionId` is incompatible. A same-ID Thing or Definition whose semantic record differs from the active authored basis is also incompatible rather than being silently substituted.

Behaviour artifacts use the production `splashmx.behaviour-ir/1` model. Their full handler/procedure/default-state form is encoded as canonical CBOR, reconstructed, and passed through `validate_program()` before it enters the staged program registry. The acquired Behaviour revision must exactly match every authored attachment required by the target. Semantic Behaviour version replacement remains owned by SMX-028 and requires its explicit source→target compatibility/state/pending-work contract; streaming does not smuggle a version update into ordinary rehydration.

Thus migration is staged at the correct layers: physical/canonical schema migration occurs before canonical publication; IR representation validation occurs before runtime publication; semantic Behaviour replacement remains an explicit SMX-028 transaction rather than an implicit cache/acquisition side effect.

## Immutable cache and offline exactness

`ImmutableArtifactCache` is digest-keyed, bounded, and evictable. It accepts bytes only after exact descriptor verification. It never owns `ThingId`, `AssetId`, `ProjectRevisionId`, WorldSave identity, lifecycle state, or authored meaning. Capacity pressure may decline to cache a verified artifact without invalidating the semantic acquisition, because the cache is an optimization rather than authority.

Eviction has no semantic callback. It cannot mutate the canonical document, WorldSave, durable references, lifecycle phase, protected assets, or dependency descriptors. If the source later becomes unavailable, a verified cached closure can support exact offline reload. If both cache and source lack a required exact artifact, reload fails with `streaming.dependency_unavailable` while the target remains known-unloaded. The runtime never floats to a different revision.

A Thing may be streamed out only when it has an exact reload catalog entry. This prevents deliberate eviction from manufacturing an unrecoverable semantic state through a missing acquisition plan.

## Atomic lifecycle and tombstone behaviour

SMX-029 remains the lifecycle and persistent-world authority. Streaming calls its unload/rehydrate operations only on a deep staged runtime copy. All dependency decoding, canonical reconciliation, protected-asset checks, and exact Behaviour checks happen before rehydration. If any target in a requested set fails, none of the staged rehydrations becomes authoritative.

Tombstone is stronger than cache/acquisition state. SMX-029 tombstoning drops resident scheduler state and replaces retained state with a tombstone record; SMX-030 refuses stream-in for that identity before fetching. Previously queued timers, continuations, cached artifacts, or exact dependency descriptors therefore cannot silently recreate a destroyed Thing.

Network relevance/interest and production transport policy remain Phase-9 `networking.runtime` scope. Runtime streaming provides the topology-neutral loaded/known-unloaded boundary that networking can later project onto relevance without changing Thing identity.

## Adversarial and boundary coverage

`spec/production/smx030-streaming-fixtures.json` records STP-001 through STP-028. `tests/production/test_smx030.py` exercises selective town/sword residency with an inventory reference, deterministic exact closure ordering, missing/corrupt/incompatible dependencies, wrong Behaviour revisions, required-feature rejection, descriptor/depth/count/byte limits, bounded cycles, offline cache hits, eviction/refetch, cache pressure, cancellation at multiple boundaries, tombstone non-resurrection, unknown versus known-unloaded states, exact reload-catalog requirements, inert opaque dependencies, and protected-asset conflicts.

The dedicated CI gate retains the authoritative SMX-008 research model and production SMX-024/025/028/029 regressions before running the SMX-030 validator/tests. This is intentionally a semantic/runtime acquisition gate; package solver/container, production CDN/network transfer, OS/browser storage eviction policy, and multiplayer relevance remain later issue scope.

## Protected source/audio/provenance boundary

A stable `AssetId` continues to select one complete immutable protected revision containing **content digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**. Streaming may acquire/cache/evict the exact bytes that carry such a revision, but those physical operations do not own or rewrite the protected semantics.

When a canonical subgraph carries an Asset revision, SMX-030 compares the complete `ProtectedAssetRevision`. If the same `AssetId` already names a different complete revision, the candidate fails with `streaming.protected_asset_conflict`; fields are never copied selectively. A previously absent complete revision may join the staged closure only after SMX-024 canonical validation and is published atomically with successful stream-in. Cache fill/eviction, target-private decode/transcode, package location, and future network distribution remain non-semantic derivatives/transport mechanisms and cannot replace or field-mix canonical source/audio/provenance meaning.

## Explicit handoff

SMX-030 does not broaden scope into package solving, package container security, network relevance, Godot realization, or collaboration synchronization. The next consumers are expected to use this module as a bounded exact-acquisition/residency substrate:

- SMX-031 can compose streaming with the integrated production Object Fabric without redefining reference/lifecycle semantics;
- SMX-035 package work supplies exact resolved descriptors/locks rather than teaching streaming to solve versions;
- SMX-036 publishing supplies exact offline creation closures;
- SMX-046 networking may drive logical residency from relevance policy while keeping transport identity non-canonical.

Any future implementation that needs a semantic update rather than physical reacquisition must use the owning canonical/package/hot-replacement transaction and must not disguise that update as cache churn.
