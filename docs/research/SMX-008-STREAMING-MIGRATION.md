# SMX-008 — Streaming, dependency acquisition, hot replacement, and state migration

Status: candidate pre-architecture streaming contract for downstream multiplayer/component/destructive falsification

Issue: SMX-008 / #8

Established: 2026-09-19

This document defines the current candidate for streaming SplashMX Things, definitions, behaviours, assets, and object subgraphs across residency boundaries while preserving the identity/lifecycle/security contracts established by SMX-002 through SMX-007.

The selected direction is a **hybrid logical-record + immutable-artifact streaming model**. Logical Things and references keep stable semantic identity independently of how bytes are batched. Runtime acquisition operates on exact immutable artifact descriptors and explicit dependency edges, stages the full required closure, validates it, then publishes atomically. Cache/prefetch/eviction are performance policy below those semantics.

The companion experiment under `experiments/smx-008-streaming-model/` and `SMX-008-STREAMING-FIXTURES.json` are non-normative evidence for the semantics below.

## Contents

| Section | Summary |
|---|---|
| 1. Research result | States the selected hybrid model and invariants. |
| 2. Constraints inherited from SMX-001–007 | Records what streaming may not break. |
| 3. Compared load-unit models | Compares Thing, scene/subgraph, package, asset-bundle, and hybrid models. |
| 4. Semantic versus physical load units | Separates logical records from byte/chunk batching. |
| 5. Artifact and instance separation | Defines independently resident definitions/behaviours/assets versus instance state. |
| 6. Dependency graph and descriptors | Defines explicit required/optional/lazy dependencies and exact resolved artifacts. |
| 7. Acquisition state machine | Defines bounded staged acquisition and atomic publication. |
| 8. Reference semantics while unloaded | Defines valid unresolved references and delivery policies. |
| 9. Town/inventory case | Demonstrates an inventory reference surviving region unload. |
| 10. On-demand reusable component | Defines streamed definition acquisition and instantiation. |
| 11. Cache, prefetch, pins, and eviction | Keeps performance policy non-semantic. |
| 12. Nested groups and public interfaces | Preserves stable exposed references across unloaded internals. |
| 13. Behaviour implementation residency | Separates executable artifact residency from attachment state. |
| 14. Semantic detach versus code eviction | Defines state-retain/discard choices explicitly. |
| 15. Hot replacement | Defines quiescent acquisition/migration/swap/rollback. |
| 16. Definition/component replacement | Extends replacement to composed graphs and overlays. |
| 17. Failure states | Distinguishes missing, denied, incompatible, invalid, cancelled, and offline states. |
| 18. Cycles and bounded dependency closure | Defines cycle handling without hidden initialization order. |
| 19. Retry and interruption | Defines cancellation and idempotent retry. |
| 20. Security/trust integration | Applies SMX-006 before live materialization. |
| 21. Host/server migration opportunity | Defines a portable state capsule without distributed assumptions. |
| 22. Corpus and executable evidence | Maps SG fixtures to the baseline corpus. |
| 23. Architecture scorecard | Records evidence-backed scores and N/E areas. |
| 24. Comparative external evidence | Records Godot/OCI/TUF/SemVer precedents. |
| 25. Downstream handoffs | Defines SMX-010/013/015/016 obligations. |
| 26. Hypothesis status | Updates H-005/H-010/H-011/H-018. |

## 1. Research result

The candidate has four distinct layers:

```text
Logical object fabric
  ThingId / DefinitionId / BehaviourId / AssetId / PortId / references
            |
            | semantic dependency declarations
            v
Resolved dependency lock
  logical dependency -> exact immutable descriptor
  {kind, lineage/version, digest, size, features, trust/provenance}
            |
            v
Acquisition/cache layer
  fetch -> bound -> verify -> parse -> validate/migrate -> stage
            |
            v
Atomic residency publication
  resident Things + resident immutable artifacts + rebuilt engine context
```

The architecture deliberately does **not** make a scene, folder, ZIP, PCK, CDN object, Godot Resource path, or package file the semantic owner of a Thing.

### Streaming invariants

- **STR-001 — logical identity is independent of physical load unit.** Repacking a Thing into another chunk/bundle/cache entry does not change ThingId, DefinitionId, BehaviourId, AssetId, PortId, or connection identity.
- **STR-002 — physical stream units are batching policy, not object semantics.** A runtime may fetch one record, a compact chunk, a package section, or a larger bundle as long as observable logical semantics are unchanged.
- **STR-003 — dependency edges are explicit and typed.** Required executable/code/data dependencies are not inferred solely from containment or current scene ancestry.
- **STR-004 — a durable reference does not imply residency.** Referencing an unloaded Thing keeps a valid `known_unloaded` reference and does not automatically load the target unless a declared operation/policy requests it.
- **STR-005 — required, optional, and lazy dependencies are distinct.** Missing required dependencies block publication/activation; optional dependencies may select an explicit fallback; lazy dependencies are acquired only when demanded.
- **STR-006 — streaming consumes exact resolved immutable descriptors.** Version-range solving is upstream/downstream package policy; the streamer works with an exact descriptor including digest and byte bound before live use.
- **STR-007 — acquisition publishes atomically.** Required closure is fetched/verified/validated/migrated in staging before any new graph/artifact becomes visible to ordinary execution.
- **STR-008 — security checks precede live materialization.** Digest/provenance/feature/schema/capability/resource checks happen before content is admitted to the user-content runtime boundary.
- **STR-009 — cancellation cannot create a partially live graph.** Cancelled/failed staged loads leave pre-existing live state unchanged; already verified immutable cache blobs may remain as inert cache entries.
- **STR-010 — cache eviction is not semantic destruction.** Evicting reconstructible bytes/code/assets does not emit creation/destruction events or change stable identity.
- **STR-011 — active executable dependencies are pinned or execution is explicitly blocked/dormant.** The runtime cannot silently evict code needed by a currently executable attachment and continue as though semantics were unchanged.
- **STR-012 — instance state and implementation/source artifacts have independent residency.** A behaviour/definition artifact can be absent from cache while stable instance/attachment state remains preserved, subject to activation/pinning rules.
- **STR-013 — hot replacement occurs at a quiescent boundary and is transactional.** New artifacts are acquired and fully validated before affecting the old live version.
- **STR-014 — state migration is explicit, bounded, deterministic, and side-effect-free.** Replacement cannot reinterpret old private/instance state implicitly.
- **STR-015 — replacement must reconcile public interfaces and pending work.** Stable ports, attachment identities, continuations, timers, queued durable work, and overlays are retained/mapped/cancelled explicitly or the swap is rejected.
- **STR-016 — acquisition failures have typed causes.** Missing, offline, denied, incompatible, invalid/malicious, cancelled, and resource-exhausted states are not collapsed into “null”.
- **STR-017 — resolved dependency cycles are bounded and staged as a closure.** Cycles do not imply user-code initialization order; if validation requires an impossible side-effectful cycle, the graph is rejected.
- **STR-018 — stream-in is not first creation.** Rehydrating an existing Thing does not replay `created` semantics merely because its bytes/engine object were absent.
- **STR-019 — dependency/cache policy is independent of containment.** A stream set may span containment branches, and a containment subtree need not be the minimum load unit.
- **STR-020 — a portable migration capsule contains semantic state and exact dependency requirements, not host handles.** This allows later host/server migration without making distributed placement an ordinary Thing property.

## 2. Constraints inherited from SMX-001–007

Streaming must preserve accepted project decisions:

From SMX-002:

- stable identity is path-independent;
- containment is not control/authority/persistence/replication;
- references and ports are explicit;
- context/engine handles are not intrinsic Thing state.

From SMX-003:

- definitions/elements and concrete Things have distinct stable identities;
- instances carry sparse overlays/provenance;
- stable exposed ports survive internal restructure;
- reconciliation conflicts are explicit.

From SMX-004:

- behaviour turns are bounded and transactional;
- cross-Thing communication is asynchronous command/event/value semantics;
- timers/continuations and private state have stable attachment identity;
- hot replacement is already quiescent/transactional at behaviour level.

From SMX-005:

- canonical records can be partially loaded;
- physical chunk location is non-semantic;
- logical IDs are distinct from content digests;
- transaction/migration semantics are staged and fail-safe;
- reference states include `known_unloaded`, `tombstoned`, `unknown`, `incompatible`, and dependency unavailable.

From SMX-006:

- dependency/package acquisition crosses an untrusted-content boundary;
- no executable Godot PCK/GDScript/GDExtension/JavaScriptBridge authority is granted by loading content;
- size/depth/fanout/digest/trust validation is required;
- signatures/provenance never grant host capability.

From SMX-007:

- existence, residency, and activity are orthogonal;
- unloading requires durable state or reconstructibility;
- stream-in uses staged restore rather than first creation;
- world-logical work may mature while a target is unloaded;
- external side effects are never replayed merely because a Thing was restored.

## 3. Compared load-unit models

### 3.1 One Thing = one physical load unit

Attractive because it maximizes object-centricity.

Strengths:

- direct identity/load mapping;
- fine-grained eviction;
- simple mental model.

Problems:

- pathological metadata/I/O overhead for many tiny Things;
- repeated definition/asset/code payloads unless separately deduplicated;
- physical fetch granularity becomes accidentally normative;
- many use cases need an atomic closure rather than one object byte record.

**Result:** rejected as a required physical format. Logical Thing-level loading remains supported above coarser batching.

### 3.2 Containment subtree / scene as load unit

Strengths:

- spatial regions and editor groups often align with locality;
- efficient bulk loading;
- maps naturally to conventional game-engine scene streaming.

Problems:

- violates P5 if hierarchy becomes the only load dependency;
- inventory references, shared definitions, global UI, external controllers, and cross-region relationships do not align cleanly;
- nested public interfaces may need to remain meaningful when internal subtree is absent;
- object/server migration may need non-tree subgraphs.

**Result:** useful stream-set heuristic, rejected as universal semantic boundary.

### 3.3 Whole package/component as load unit

Strengths:

- strong trust/version/distribution boundary;
- easy immutable verification;
- simple CDN/cache unit.

Problems:

- too coarse for large worlds and memory pressure;
- package can contain many unrelated regions/assets;
- conflates distribution with residency.

**Result:** package is a provenance/resolution boundary, not necessarily the residency unit.

### 3.4 Asset-bundle/chunk-only streaming

Strengths:

- good I/O/compression locality;
- operationally efficient.

Problems:

- bundle placement can change between releases;
- not sufficient to express semantic object references, pending work, behaviour state, or stable exposed interfaces.

**Result:** implementation technique below canonical semantics.

### 3.5 Hybrid logical records + exact immutable artifacts + policy-defined stream sets

This candidate allows:

- stable per-Thing semantics;
- arbitrary stream-set selection;
- batching into efficient physical chunks;
- separately cached definitions/behaviours/assets;
- exact content verification;
- atomic graph closure publication.

**Result:** selected for downstream falsification.

## 4. Semantic versus physical load units

SplashMX needs a distinction between:

### Semantic load target

What the runtime is trying to make usable, e.g.:

- Thing `thing:sword-17`;
- public component `component:door-controller`;
- Definition `def:robot`;
- Behaviour `behaviour:wander`;
- Asset `asset:forest-audio`;
- explicit stream set `region:town-west`.

### Physical acquisition unit

What bytes are fetched:

- a single immutable record;
- a chunk containing many records;
- a package section;
- a content-addressed blob;
- a compressed bundle;
- an editor-store page.

The catalog maps semantic identity to physical descriptors. Repacking is therefore an implementation optimization.

## 5. Artifact and instance separation

The model distinguishes:

### Mutable logical/runtime instance state

Examples:

- Thing public state;
- behaviour attachment private state;
- timers/continuations;
- runtime-created objects;
- persistent relations;
- instance overlay/runtime projection.

This follows SMX-007 save/lifecycle semantics.

### Immutable source/implementation artifacts

Examples:

- Definition revision;
- Behaviour implementation/IR revision;
- portable component definition revision;
- immutable asset blob;
- schema/migration module in the constrained migration model;
- package manifest/lock metadata.

These may be evicted/reacquired by exact descriptor.

### Consequences

A concrete instance does not cease to exist because its source Definition artifact leaves the local cache. Provenance retains the exact revision identity needed for later editing/reconciliation.

A dormant/unloaded behaviour attachment can retain private state while the implementation artifact is evicted. Before the attachment executes again, the required implementation must be reacquired and compatibility-checked.

## 6. Dependency graph and descriptors

### 6.1 Authored requirement

An authored component/package may declare a dependency requirement:

```text
DependencyRequirement
  logical_dependency_id
  kind
  compatibility_requirement
  required | optional | lazy
  requested features/interfaces
  declared fallback?          # for optional dependency
```

The exact constraint language/version resolver belongs to SMX-013.

### 6.2 Resolved dependency lock

Streaming should consume an already exact result:

```text
ResolvedArtifact
  logical_dependency_id
  artifact_kind
  lineage/version/revision
  content_digest
  byte_size
  required features/schema
  provenance/trust metadata reference
  dependency descriptors
```

The content digest identifies immutable bytes; it does not replace the logical DefinitionId/BehaviourId/AssetId.

### 6.3 Dependency edge classes

At streaming time, useful edge classes include:

- **hard/runtime-required** — target cannot activate/use the requested capability without it;
- **optional** — load may complete using a declared fallback;
- **lazy** — exact dependency is known but not acquired until a declared operation requires it;
- **editor/reconciliation-only** — e.g. source Definition revision needed to apply base updates but not to run a fully materialized instance;
- **presentation-only** — can sometimes use placeholder/degraded representation;
- **boundary/context** — a loaded subgraph may require a small stable proxy/anchor rather than the entire related object.

A durable reference is **not automatically** a hard dependency.

### 6.4 Dependency closure

An acquisition attempt computes a bounded closure of hard dependencies plus currently requested optional/lazy edges.

Limits from SMX-006 apply:

- visited artifact count;
- depth;
- total bytes;
- per-artifact bytes;
- metadata fanout;
- migration work;
- dependency cycle/role visits.

## 7. Acquisition state machine

Candidate acquisition phases:

```text
REQUESTED
  -> DESCRIPTORS_RESOLVED
  -> POLICY_AUTHORIZED
  -> FETCHING
  -> BYTES_VERIFIED
  -> PARSED
  -> VALIDATED
  -> MIGRATED_IF_REQUIRED
  -> CLOSURE_STAGED
  -> PUBLISHED
```

Typed terminal/non-live states:

```text
MISSING
OFFLINE_OR_UNREACHABLE
DENIED
INCOMPATIBLE
INVALID_OR_MALICIOUS
RESOURCE_EXHAUSTED
CANCELLED
FAILED_TRANSIENT
```

### 7.1 Atomic publication

Until `PUBLISHED`:

- newly acquired Things/definitions/behaviours are not visible to ordinary user execution;
- public connections are not rebound;
- replacement version is not active;
- durable pending events are not delivered into the staged graph;
- author lifecycle hooks are not run.

Verified immutable blobs may enter an inert cache before publication.

### 7.2 Publication transaction

Publication:

1. validates full required closure;
2. constructs/hydrates logical shells;
3. binds references and stable public interfaces;
4. restores durable scheduler work;
5. rebuilds transient engine context;
6. validates final graph;
7. atomically swaps residency/catalog pointers;
8. then admits queued durable deliveries/external inputs.

## 8. Reference semantics while unloaded

SMX-005/007 states remain:

- `loaded`;
- `known_unloaded`;
- `tombstoned`;
- `unknown`;
- `incompatible`;
- `dependency_unavailable`.

### Reference lookup does not force load

Ordinary inspection of a ThingRef can return identity + status without I/O.

An operation may explicitly request:

- `load_target`;
- `send_durable_and_wake`;
- `send_if_resident`;
- `fail_if_unloaded`;
- `drop_if_ephemeral`.

The exact author-facing vocabulary remains an editor/runtime projection decision, but the policy cannot be hidden synchronous traversal.

## 9. Town/inventory case

Required case:

```text
Player/Inventory (resident)
  slot_2 -> ThingRef thing:sword-17

TownWest stream set
  contains thing:sword-17
  contains many unrelated buildings/NPCs
```

When TownWest unloads:

1. `thing:sword-17` runtime state is snapshotted or proven reconstructible;
2. the sword becomes `known_unloaded`;
3. Inventory retains `ThingRef thing:sword-17`;
4. no path repair occurs;
5. inspecting the slot does not require TownWest to load;
6. using/equipping the sword may request `thing:sword-17` plus its hard dependency closure;
7. the streamer may load only the sword + required definition/behaviour/asset/context boundary rather than the entire town;
8. after publication, the reference resolves `loaded` with the same ThingId.

This directly supports H-011 without requiring one Thing per physical file.

## 10. On-demand reusable component

Example:

```text
creation requests "weather-clock component"
 -> resolver/lock selects exact component revision
 -> streamer receives immutable descriptors
 -> security/trust checks
 -> acquire Definition + Behaviour + required assets
 -> validate public interface/capabilities/features
 -> publish source artifacts
 -> instantiate concrete Things with new ThingIds
 -> attach provenance to exact Definition revision
```

Acquisition itself must not execute arbitrary user initialization code. First logical instance creation may run ordinary `created` semantics only after the entire required closure is published.

## 11. Cache, prefetch, pins, and eviction

These are runtime policy, not canonical meaning.

### Prefetch

May acquire/verify artifacts before any Thing needs them.

Prefetch must not:

- emit `created`/`restored`;
- activate behaviours;
- grant capabilities;
- bind public live references.

### Pinning

Artifacts must be pinned while their absence would violate active semantics.

Examples:

- active behaviour implementation;
- currently decoding/playing required asset if no fallback exists;
- migration code during a replacement transaction.

### Eviction

Eviction may remove:

- reconstructible asset bytes;
- behaviour/definition artifact bytes when not pinned;
- derived caches.

Eviction cannot remove:

- the only durable copy of required runtime state;
- stable logical identity/catalog information needed to distinguish unloaded from unknown/tombstoned;
- state needed for pending durable work.

## 12. Nested groups and public interfaces

A group/component may expose:

```text
root public PortId: port:open
    -> internal ElementId door-leaf + PortId open_internal
```

External connection targets `root ThingId + port:open`, not the internal path.

If internals unload:

- public interface identity remains in catalog/definition metadata;
- current implementation endpoint may be known-unloaded;
- durable command can queue/load/wake according to policy;
- internal reparenting/rechunking does not repair the external connection.

A loaded child does not necessarily require the whole containment chain. If transform/locality semantics require an unloaded ancestor, the stream closure may include a minimal boundary/anchor record or mark that ancestor as a hard semantic dependency. This is an explicit edge, not a universal “load every parent” rule.

## 13. Behaviour implementation residency

Behaviour attachment identity/state and implementation bytes are distinct.

### Active attachment

Required implementation must be resident/pinned. Eviction is forbidden until:

- attachment becomes dormant/unloaded;
- behaviour is semantically detached;
- or replacement commits.

### Dormant/unloaded attachment

Private state, PRNG position, timers/continuations, and provenance remain in runtime/save state while implementation bytes may be evicted.

Wake/restore requires:

1. exact implementation reacquisition;
2. version/private-state/continuation compatibility validation;
3. migration if required;
4. then activation.

### Missing implementation during wake

Typed result:

- dependency unavailable;
- denied;
- incompatible;
- invalid;
- offline.

The runtime does not silently discard attachment state.

## 14. Semantic detach versus code eviction

These are different operations.

### Code eviction

- behaviour attachment still semantically exists;
- private state is retained;
- implementation can be reacquired;
- no user-visible detach semantics.

### Semantic detach

Behaviour is intentionally removed from the Thing.

Detach must specify state policy:

- **discard_state** — attachment state is destroyed;
- **retain_capsule** — state is retained as an inert, typed detached-state capsule for an explicitly compatible later reattachment/migration.

A retained capsule carries no execution authority. It records attachment lineage/schema/state only.

This avoids both accidental state loss and hidden forever-state retention.

## 15. Hot replacement

Hot replacement combines SMX-004 executor rules, SMX-003 instance reconciliation, SMX-005 migration, and SMX-007 lifecycle.

Candidate sequence:

1. select exact new resolved artifact descriptor;
2. acquire/verify/parse/validate new artifact in staging;
3. preflight public ports/features/capabilities/private-state schema;
4. request quiescent boundary for affected Things/attachments;
5. snapshot affected runtime state and pending work;
6. run bounded deterministic side-effect-free state migration;
7. map retained public ports/connections;
8. map/cancel/reject timers/continuations/pending durable work explicitly;
9. validate candidate effective graph;
10. atomically switch implementation/revision pointers + migrated state;
11. resume scheduler;
12. release old artifact pins; old bytes become evictable.

### Failure

Any failure before commit leaves:

- old implementation active;
- old private/public state unchanged;
- pending work unchanged;
- public connections unchanged;
- old artifact pinned.

New verified bytes may remain inert in cache.

## 16. Definition/component replacement

A new Definition/component revision may affect many concrete instances.

The system combines:

- SMX-003 base-revision reconciliation;
- SMX-005 semantic transaction;
- SMX-007 snapshot/restore;
- SMX-008 staged artifact acquisition.

For an affected set:

1. acquire new immutable Definition/component revision;
2. compute per-instance reconciliation/migration plans using stable ElementIds/overlays;
3. identify invalidated overrides/exposed interfaces/protected deletions;
4. stage all required compatible replacements;
5. either commit the selected atomic scope or surface explicit conflicts.

Whether a project allows partial instance-by-instance upgrade or requires one atomic component-version cut is product/package policy; each individual live instance swap still cannot be half-applied.

## 17. Failure states

### `missing`

Resolved artifact/target does not exist in known repository/catalog.

### `offline_or_unreachable`

Artifact is known but acquisition transport is unavailable.

### `denied`

Current host/user/security policy refuses acquisition or required capability/trust rule.

### `incompatible`

Bytes may be valid, but runtime features/schema/interface/version requirements cannot be satisfied.

### `invalid_or_malicious`

Digest/signature/schema/parser/security validation fails.

This state should not be auto-retried from the same exact source descriptor without policy change/new bytes.

### `resource_exhausted`

Declared/observed package/dependency/parse/migration budgets exceeded.

### `cancelled`

Caller/policy cancelled before publication.

### `failed_transient`

Retryable I/O/storage/host failure where bytes are not known malicious/incompatible.

Required dependency failure blocks publication/activation. Optional dependency failure uses only an explicitly declared fallback/degraded path.

## 18. Cycles and bounded dependency closure

Resolved immutable dependency graphs may contain cycles, e.g. mutually referring declarative component definitions.

Streaming can support these by:

1. discovering a bounded strongly connected closure;
2. fetching/verifying all members;
3. allocating logical shells/registrations;
4. validating references/interfaces across the staged set;
5. publishing the set atomically.

What is **not** allowed is arbitrary user initialization with order-dependent side effects during acquisition. If a dependency relationship requires “run A to discover B, run B to finish A” with privileged/author side effects, it is not a valid declarative acquisition cycle.

SMX-013 may choose to prohibit package-resolution cycles for usability. SMX-008 merely shows they are not intrinsically incompatible with stable logical references once exact artifacts are already resolved.

## 19. Retry and interruption

Each acquisition has an `AttemptId` and staging area.

Cancellation/failure:

- discards staged mutable graph/state;
- leaves live world untouched;
- may keep verified immutable blobs keyed by digest;
- records typed failure/diagnostics;
- does not fire author lifecycle hooks.

Retry:

- creates a new AttemptId;
- may reuse verified immutable cache bytes;
- re-runs current policy/trust/feature compatibility checks;
- cannot assume a previous capability grant still exists;
- publishes only after complete validation.

This makes retry idempotent with respect to live semantics even when cache progress is retained.

## 20. Security/trust integration

Acquisition is a host/runtime service governed by SMX-006.

### Ordinary content does not fetch arbitrary code itself

A component can request an allowed logical dependency. The host resolver/acquisition service decides:

- repository/source policy;
- trust metadata;
- current offline/online policy;
- bounded download;
- exact descriptor;
- digest verification.

The component does not receive raw HTTP/filesystem/native authority.

### Before publication

Validate:

- descriptor size/digest;
- provenance/signature policy;
- required feature support;
- canonical schema;
- IR validation/budgets;
- migration limits;
- capability declarations;
- dependency depth/count/bytes;
- asset decoder bounds.

### Malicious dependency

No partial graph becomes live. Existing world remains unchanged. The exact malicious/invalid artifact can be quarantined by host policy, but quarantine storage is non-semantic.

## 21. Host/server migration opportunity

SMX-008 does not make distributed placement a Thing property, but the existing semantics permit a later portable migration unit:

```text
MigrationCapsule
  selected Thing/subgraph stable IDs
  quiescent runtime snapshot
  durable pending work
  authored/definition/behaviour provenance
  exact resolved dependency descriptors/locks
  external reference IDs
  required capabilities/features declarations

NOT included:
  socket/peer IDs
  current simulation authority token
  live capability grants
  Godot/native/browser handles
```

Destination host:

1. validates capsule;
2. acquires exact required artifacts;
3. stages restore;
4. rebinds current authority/controller/capability/network context;
5. atomically publishes;
6. source/destination handoff protocol is supplied later by SMX-010/017.

This keeps ordinary Things topology-agnostic.

## 22. Corpus and executable evidence

Companion manifest: `docs/research/SMX-008-STREAMING-FIXTURES.json`.

Direct executable coverage:

| Fixture | Cases | Observation |
|---|---|---|
| SG-001 | C-006/C-012 | Inventory retains stable sword reference while town/sword unload; sword reloads with same ThingId without whole town. |
| SG-002 | C-011/C-026 | Exact reusable component Definition/Behaviour artifacts acquire on demand before first instance creation. |
| SG-003 | C-026/A-012/A-015 | Missing/denied/digest-invalid required dependency produces typed failure and no partial publication. |
| SG-004 | C-026 | Missing optional dependency uses declared fallback and does not block required closure. |
| SG-005 | C-025 | Active behaviour pins implementation; dormant attachment can evict implementation while retaining private state and reacquire before wake. |
| SG-006 | C-025/A-006 | Hot replacement migrates private state and continuations transactionally. |
| SG-007 | C-025/A-006 | Incompatible/migration-failing replacement leaves old implementation/state/work unchanged. |
| SG-008 | A-012 | Cancelled acquisition publishes nothing; verified cache bytes may be reused by retry. |
| SG-009 | C-026 | Exact cyclic declarative artifact closure stages/publishes atomically without initialization-order side effects. |
| SG-010 | C-011/C-027 | External stable public port survives nested internal unload/reload and rechunking. |
| SG-011 | C-025 | Semantic behaviour detach explicitly retains or discards state; code eviction alone never means detach. |
| SG-012 | C-015/C-024 | Portable migration capsule restores on a fresh host after dependency reacquisition without host/network/capability handles. |

### Not proven here

- production async I/O/cache performance;
- exact package/version solver;
- distributed source/destination handoff/consensus;
- CDN/offline repository selection;
- cryptographic trust-root management;
- Godot resource/asset loader mapping;
- large-world memory/latency heuristics;
- real malicious package parser campaign.

## 23. Architecture scorecard

Candidate: hybrid logical records + exact immutable artifact dependency closure

| Score | Assessment |
|---|---|
| S-01: 2 | Streaming complexity can remain hidden; author UX not tested. |
| S-02: 3 | Same logical object semantics survive unloaded/cache states. |
| S-03: 3 | Stream sets/dependency closure are explicitly independent of hierarchy. |
| S-04: 3 | Thing/definition/port identity survives unload/repack/reload. |
| S-05: 3 | Behaviour state/code separation and transactional replacement are explicit. |
| S-06: 3 | Streaming composes directly with SMX-007 save/restore state. |
| S-07: 3 | Partial loading, dependency closure, eviction, cancellation, retry and unloaded references are directly modeled. |
| S-08: 3 | Acquisition applies SMX-006 before publication. |
| S-09: 2 | Host-migration capsule is plausible; actual multiplayer authority handoff remains SMX-010/017. |
| S-10: N/E | Collaborative package/edit acquisition remains SMX-011/018. |
| S-11: 3 | Exact immutable descriptors + explicit state migration support compatibility evolution. |
| S-12: 3 | Godot ResourceLoader/path/cache semantics remain substrate-only. |
| S-13: 3 | Deterministic fixtures exercise failures, cycles, migration and fresh-host restore. |
| S-14: N/E | Performance/memory heuristics not benchmarked. |
| S-15: 3 | Failure states and rollback/cancellation behavior are explicit. |
| S-16: 2 | Required/optional/lazy dependencies permit progressive disclosure; UX later. |

Hard-gate failures observed in SMX-008 scope: **none in the model**.

## 24. Comparative external evidence — checked 2026-09-19

These are design precedents, not selected public dependencies.

### Godot 4.7 ResourceLoader

Godot 4.7 exposes:

- resource dependency inspection;
- cache modes;
- threaded load request/status/get operations;
- missing-resource failure policy.

Source:
https://docs.godotengine.org/en/4.7/classes/class_resourceloader.html

**Implication:** Godot has useful internal asynchronous/cache substrate, but its path/resource cache cannot define SplashMX stable identity or dependency semantics.

### OCI Image Specification descriptors

OCI manifests use descriptors carrying content digest and byte size for immutable referenced content.

Source:
https://specs.opencontainers.org/image-spec/manifest/

**Implication:** digest + size + media/type metadata is strong precedent for exact immutable artifact acquisition, without using content digest as mutable logical object identity.

### The Update Framework (TUF)

Current TUF specification explicitly addresses:

- bounded target downloads;
- target hashes/sizes;
- rollback/freeze/mix-and-match/extraneous-dependency attacks;
- bounded delegated-role traversal.

Source:
https://github.com/theupdateframework/specification/blob/master/tuf-spec.md

**Implication:** secure acquisition needs bounded verified metadata/content and coherent version/trust state. SplashMX does not adopt the complete TUF role model in SMX-008; SMX-013/014/016 can evaluate distribution trust machinery later.

### Semantic Versioning 2.0.0

SemVer defines version changes relative to a declared public API and distinguishes incompatible major changes from backward-compatible minor/patch changes.

Source:
https://semver.org/

**Implication:** useful compatibility vocabulary for package/component authors, but version ranges and solver behavior are deliberately owned by SMX-013. Streaming consumes exact resolved artifacts.

## 25. Downstream handoffs

### SMX-009 Godot substrate mapping

Must determine:

- how canonical artifacts map to Godot runtime assets/resources without exposing path identity;
- threaded/background loading strategy;
- cache invalidation/pins;
- asset decoder bounds;
- rehydration of Nodes/physics/audio resources;
- whether browser/native loading constraints require different physical batching while preserving STR semantics.

### SMX-010 runtime multiplayer

May assume a portable quiescent subgraph snapshot + exact dependency set can be constructed.

Must define:

- authoritative source/destination handoff;
- in-flight network input cut;
- peer-visible identity continuity;
- replication pause/resume;
- duplicate-authority avoidance;
- server-region failure/retry.

### SMX-011 collaboration

Must keep collaboration document synchronization distinct from runtime streaming. Editing an unloaded canonical record and live runtime residency are different consistency problems.

### SMX-013 component/package ecosystem

Owns:

- logical package/component IDs;
- version constraint syntax;
- dependency solver;
- lockfile/snapshot format;
- provenance/signature trust roots;
- vendoring/remix/fork rules;
- package-cycle policy;
- repository/source selection.

SMX-008 requires only that runtime acquisition receive exact immutable descriptors and typed required/optional/lazy semantics.

### SMX-014 publishing

Owns distribution/container/CDN/offline packaging while preserving the logical/physical load-unit split.

### SMX-015 object-fabric destructive harness

Must attack:

- inventory reference across region eviction;
- behaviour swap while durable timer/continuation is pending;
- nested exposed interface while internals unload/rechunk;
- cancellation during multi-artifact load;
- required dependency turning invalid/denied during retry;
- cyclic closure;
- definition revision + instance overlay migration under stream-in.

### SMX-016 security harness

Must attack:

- malicious descriptors/digests;
- dependency depth/fanout/byte bombs;
- cache poisoning;
- mix-and-match exact artifacts;
- malicious migration;
- optional/required dependency confusion;
- cancellation/retry authority confusion.

## 26. Hypothesis status

### H-005 — behaviour is safely composable and dynamically replaceable

**Strengthened further.** SMX-008 composes acquisition, quiescent migration, pending-work reconciliation, rollback, and code/state residency separation around the SMX-004 hot-swap model. Production integrated runtime remains SMX-015.

### H-010 — same Thing semantics can survive unloaded state

**Strengthened further.** The town/inventory and nested-interface fixtures show unloaded targets retain stable identity/reference semantics and can return through staged restore without first-creation semantics.

### H-011 — streaming can be object-centric rather than scene-centric

**Strengthened substantially at model level.** A semantic stream target can be a Thing/subgraph/component while physical bytes are independently batched. The demonstrated town case reloads one referenced sword + hard dependency closure rather than the entire containment region. Production performance remains unproven.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened further.** Hot replacement consumes exact immutable source artifacts and explicit bounded state/interface/pending-work migration; failures retain the old live version atomically. Real cross-engine migrations remain later work.

No other hypothesis receives a status change from SMX-008.
