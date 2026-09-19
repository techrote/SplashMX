# SMX-007 — Runtime lifecycle, snapshots, restore, dormancy, and deterministic state

Status: candidate pre-architecture lifecycle contract for downstream streaming/network/destructive falsification

Issue: SMX-007 / #7

Established: 2026-09-17

This document defines the current candidate for how SplashMX Things move through runtime lifecycle transitions without relying on surviving Godot objects or hidden global-manager state. It builds directly on the SMX-004 bounded-turn executor, SMX-005 authored/runtime/save/context plane separation, and SMX-006 security boundary.

The central result is that **lifecycle is not one linear enum**. SplashMX should model at least three orthogonal semantic axes — existence, residency, and activity — while treating snapshot/save/restore as atomic operations over explicitly selected runtime state. A Thing can therefore be present + resident + active, present + resident + dormant, present + unloaded, or tombstoned without confusing those meanings.

The companion experiment under `experiments/smx-007-lifecycle-model/` and `SMX-007-LIFECYCLE-FIXTURES.json` are non-normative evidence for the semantics below.

## Contents

| Section | Summary |
|---|---|
| 1. Research result | States the lifecycle axes and accepted invariants. |
| 2. State-plane model | Separates authored, runtime, save/world, and transient context state. |
| 3. Lifecycle axes | Defines existence, residency, activity, and internal restore phases. |
| 4. Observable lifecycle operations | Defines creation, activation, semantic dormancy, snapshot, unload, restore, and destruction. |
| 5. Quiescent snapshot semantics | Defines the atomic cut over runtime state. |
| 6. Persistable runtime state | Defines what a save/snapshot may record. |
| 7. Pending work taxonomy | Defines durable, ephemeral, reconstructible, and external-wait work. |
| 8. Timer and clock domains | Defines active-time, world-logical, and external-wall-clock behaviour. |
| 9. External services and side effects | Prevents restore from duplicating already-issued external effects. |
| 10. References, absence, and tombstones | Preserves identity through dormancy/unload/destruction. |
| 11. Restore pipeline | Defines shell creation, hydration, reference binding, scheduler restore, context rebinding, and activation. |
| 12. Lifecycle events | Defines which events occur on first creation, wake, restore, and destruction. |
| 13. Definition/behaviour compatibility | Defines version/schema obligations at restore. |
| 14. Physics/presentation/network state | Classifies common engine-facing runtime state. |
| 15. Determinism and replay | Defines what exact replay needs and what restore alone guarantees. |
| 16. Security/capability interaction | Carries SMX-006 rules through save/restore. |
| 17. Corpus and executable evidence | Maps LT fixtures to baseline cases/adversarial variants. |
| 18. Architecture scorecard | Records evidence-backed scores and N/E areas. |
| 19. Downstream handoffs | Defines SMX-008/010/015 assumptions. |
| 20. Hypothesis status | Updates H-008/H-010/H-018. |

## 1. Research result

The candidate semantic lifecycle is:

```text
Existence axis:
  PRESENT  <---------------------->  TOMBSTONED
    |
    +-- a live logical identity         durable record of destruction;
        with authored/runtime meaning   identity is not silently reused

Residency axis (only while PRESENT):
  RESIDENT <----------------------> UNLOADED

Activity axis (only while PRESENT + RESIDENT):
  ACTIVE   <----------------------> DORMANT

Snapshot/save:
  atomic operation over a quiescent runtime cut;
  not itself an existence/residency/activity state.

Restore/rehydration:
  internal staged operation that reconstructs a PRESENT runtime from
  authored definitions + compatible persistent snapshot/save data +
  freshly rebound transient context.
```

This avoids the common but misleading sequence:

```text
active -> sleeping -> serialized -> unloaded -> restored
```

because “serialized” is not mutually exclusive with “active”, and a save file does not become the live Thing.

### Lifecycle invariants

- **LIF-001 — identity outlives residency:** unloading removes resident process/engine state but does not change or reuse the Thing's durable identity.
- **LIF-002 — save/snapshot is an operation, not a Thing state:** taking a snapshot does not imply dormancy, unload, or deactivation.
- **LIF-003 — snapshots occur at quiescent turn boundaries:** no behaviour activation is half-committed in a persistent snapshot.
- **LIF-004 — authored/runtime/save/context planes remain separate:** restore reconstructs runtime state from authored semantics plus selected save/runtime projection; it does not serialize engine/context handles.
- **LIF-005 — restore does not require surviving in-memory objects:** all required durable runtime meaning is reconstructible from records, definitions, and explicit snapshot state.
- **LIF-006 — durable internal pending work is explicit:** persistable timers, continuations, queued internal events/commands, and deterministic PRNG state are serialized as typed scheduler records rather than hidden stacks/closures.
- **LIF-007 — external effects are never implicitly replayed by restore:** a previously issued HTTP/file/notification/etc. operation is not reissued merely because the snapshot says a behaviour was awaiting it.
- **LIF-008 — service/network handles and live grants are context, not save authority:** snapshots may retain non-authoritative correlation metadata, but not active host capability leases, sockets, peer IDs, engine objects, or native handles.
- **LIF-009 — timer semantics name a clock domain:** active-time, world-logical, and external-wall-clock deadlines are not silently interchanged.
- **LIF-010 — semantic dormancy is explicit; implementation sleep is invisible:** an optimisation may only sleep work if observable semantics remain equivalent.
- **LIF-011 — unloaded references remain valid when the catalog knows the target:** a reference to an unloaded Thing resolves as `known_unloaded`, not dangling.
- **LIF-012 — destruction creates an explicit tombstone state:** ordinary destruction does not silently convert the old ID into “unknown” or reuse it for a new Thing.
- **LIF-013 — restore is staged and atomic at world/subgraph scope:** validation/version/schema failure leaves the prior world/save state untouched rather than producing a half-restored graph.
- **LIF-014 — restore does not replay first-creation hooks by default:** first creation, restore, wake, and ordinary activation are distinct lifecycle causes.
- **LIF-015 — deterministic restore is weaker than deterministic replay:** restore can reproduce a saved state exactly while future execution may diverge if external inputs differ.
- **LIF-016 — snapshot compatibility is explicit:** authored revision, behaviour definition/version, private-state schema, and required runtime features are checked/migrated before activation.
- **LIF-017 — runtime authority/topology is rebound, not persisted as object meaning:** controller, simulation authority, replication sessions, and peer IDs are re-established by current runtime/network policy.
- **LIF-018 — historical rewind and ordinary respawn are distinct:** loading a historical snapshot may recreate a prior world revision containing an old ThingId; ordinary post-destruction respawn creates a new logical ThingId unless an explicit world-revision rollback is being performed.

## 2. State-plane model

SMX-005 established four planes. SMX-007 assigns lifecycle meaning to them.

### 2.1 Authored canonical document

Examples:

- Thing/Definition/Element/Port/Connection identities;
- initial/default authored state;
- behaviour definitions and attachment declarations;
- definition provenance/instance overlays;
- persistence declarations;
- asset references;
- capability *requests* and policies;
- authored timeline/rule/configuration.

This is project meaning, not a save game.

### 2.2 Live runtime simulation state

Examples:

- mutable public Thing state;
- behaviour-attachment private state;
- current animation/timeline position where semantically live;
- deterministic PRNG stream state/draw positions;
- logical clocks;
- pending internal events/commands;
- durable timers/continuations;
- runtime physics state such as velocity where gameplay-relevant;
- fault/suspension state if it changes future semantics.

This state exists while resident and may be projected into a save/snapshot according to persistence policy.

### 2.3 Persistent save/world state

A save/world snapshot is an explicit projection over runtime state, addressed by stable logical IDs and version/schema metadata.

It may contain:

- current persistable Thing state;
- attachment-private state;
- runtime-created persistent Things and their authored/provenance basis;
- persistent runtime destruction tombstones;
- durable internal pending work;
- deterministic PRNG state;
- logical clock state;
- selected physics/timeline state;
- safe non-authoritative external-wait correlation metadata;
- snapshot lineage and authored/runtime schema requirements.

It does **not** silently contain the entire editor document or transient runtime context.

### 2.4 Transient context

Rebound after restore:

- Godot Node/RID/audio/physics handles;
- renderer caches;
- editor selection and collaboration presence;
- active peer/session IDs;
- current network transport;
- controller bindings where session-specific;
- simulation authority assignment where topology-specific;
- live capability grants/leases;
- browser/OS permission objects;
- file/socket/device handles;
- in-flight decoder/job handles;
- instrumentation/debug handles.

These may have durable *policies* or declarations elsewhere, but the live handle/grant itself is not save authority.

## 3. Lifecycle axes

### 3.1 Existence

`PRESENT`

The logical Thing belongs to the current world/document/save revision.

`TOMBSTONED`

The identity is known to have been destroyed/removed in this world lineage. A tombstone may record:

- ThingId;
- destruction revision/tick;
- optional reason/classification;
- retention/compaction metadata;
- references needed for diagnostics/migration.

A tombstone is not a live Thing and has no active behaviour.

### 3.2 Residency

`RESIDENT`

A runtime representation is materialized and can participate according to its activity state.

`UNLOADED`

The Thing remains semantically present in the world/catalog, but no live execution/engine object is required. Its durable runtime state is represented in a snapshot/chunk/save/world store.

A `known_unloaded` reference is valid.

### 3.3 Activity

`ACTIVE`

Normal author-visible processing is enabled according to its behaviours/timeline/physics.

`DORMANT`

Semantic processing is intentionally reduced/paused according to explicit dormancy rules. Dormancy may be author-visible if product semantics expose it.

A dormant Thing is still resident and may be woken by allowed wake conditions.

### 3.4 Hidden implementation states

The runtime may internally use phases such as:

- allocating shell;
- validating snapshot;
- hydrating;
- binding references;
- rebuilding engine resources;
- rebinding context;
- staging scheduler;
- committing restore.

These are not ordinary author lifecycle states and should not leak as arbitrary event ordering.

## 4. Observable lifecycle operations

### 4.1 First creation / instantiation

First creation establishes a new ThingId and initial runtime state from authored/default semantics.

First-creation hooks, if any, run **once for that logical creation event**, after state and required references are valid.

A save restore of an existing Thing does not count as first creation.

### 4.2 Activation

Entering ACTIVE from an inactive runtime state may enable:

- normal input;
- tick/update handlers;
- scheduled work in active-time domains;
- normal physics/control policy.

Activation itself is not proof of first creation or restore.

### 4.3 Semantic dormancy

Entering DORMANT:

- occurs at a quiescent turn boundary;
- stops ordinary active-time processing;
- preserves runtime state;
- may keep explicitly declared wake subscriptions/index entries;
- freezes active-time timers;
- does not erase queued durable work;
- does not change identity/containment/control/authority by implication.

World-logical deadlines may continue according to their own clock domain and can create wake/pending-delivery obligations.

### 4.4 Snapshot/save

Snapshot:

1. requests a quiescent cut;
2. completes/rolls back the currently executing bounded turn;
3. captures a consistent logical clock/scheduler cut;
4. validates snapshot schemas/persistence policy;
5. writes a new immutable/transactional snapshot record;
6. does not alter activity/residency unless a later operation asks for it.

### 4.5 Unload

Unload is permitted only after durable state required for future semantics has been captured or proven reconstructible.

Unload:

- removes resident engine/process objects;
- removes transient handles/context bindings;
- preserves stable identities/catalog entries;
- persists durable simulation state/pending work according to policy;
- cancels/detaches ephemeral runtime work;
- leaves references resolvable as `known_unloaded`.

### 4.6 Restore/rehydrate

Restore reconstructs from:

- compatible authored canonical revision/package;
- save/snapshot records;
- current host/runtime policy/context.

It does not require the old Godot Node/object to survive.

### 4.7 Destruction

Destruction occurs at a quiescent boundary and:

- stops/cancels runtime work according to destruction policy;
- makes future direct resolution tombstoned;
- retains the ThingId in a tombstone/index according to retention policy;
- does not permit ordinary ID reuse;
- may emit one explicit destruction event before/at commit according to future event semantics.

Ordinary respawn is a new ThingId. Historical world rewind may restore the old ID because it selects an earlier world revision, not because the ID was reused.

## 5. Quiescent snapshot semantics

A valid snapshot cut cannot contain:

- a half-applied behaviour turn;
- provisional private/public writes;
- staged-but-not-committed follow-on effects;
- a definition/behaviour hot swap half-migrated;
- a canonical transaction half-committed.

### 5.1 Snapshot barrier

Candidate algorithm:

```text
request snapshot
  -> stop admitting new external inputs into target snapshot domain
  -> finish current bounded activation(s) to defined serial-equivalent boundary
  -> commit/rollback those turns
  -> freeze logical scheduler cut
  -> classify pending work
  -> serialize durable state
  -> validate snapshot
  -> atomically publish SnapshotId
  -> resume normal admission
```

The implementation may parallelize internally if the resulting cut is equivalent.

### 5.2 Snapshot scope

A snapshot can cover:

- entire world/session simulation;
- explicit persistent subgraph;
- one object/component for transfer/streaming.

Partial snapshots must preserve external references by ID and declare dependencies. They do not silently copy every referenced object.

## 6. Persistable runtime state

Candidate snapshot record for one Thing:

```text
ThingRuntimeSnapshot
  thing_id
  authored_basis:
    document_revision
    definition_revision?
    element_provenance?
  existence = PRESENT
  persisted_public_state
  behaviour_attachments:
    attachment_id
    behaviour_definition_id
    behaviour_revision
    private_state_schema
    persisted_private_state
    prng_state_or_seed_plus_draw_position
    fault/suspension state?   # only if semantically relevant
  durable pending work
  selected physics/timeline state
  persistent runtime relations
  persistence metadata
```

Not every field must be saved for every Thing.

### 6.1 Persistence policy

State loci should be classifiable as:

- **authored default** — reconstruct from canonical document; omit from save unless changed/needed;
- **persistent runtime** — save current value;
- **session runtime** — do not survive save/restore;
- **reconstructible** — omit and recompute from persistent sources;
- **context** — never save as authority/engine handle.

## 7. Pending work taxonomy

Pending work cannot be treated uniformly.

### 7.1 Durable internal work

Examples:

- logical timer continuation;
- queued event/command that has already been committed;
- deterministic scheduled AI transition;
- local delayed animation/state transition.

Snapshot includes enough data to restore:

- stable work ID;
- target Thing/attachment/handler/continuation ID;
- payload;
- clock domain/due representation;
- queue ordering key/causal order;
- persistence class;
- required behaviour/private-state schema version.

### 7.2 Session-ephemeral work

Examples:

- pointer hover event;
- current peer input packet not yet committed;
- render-frame callback;
- transient audio-buffer callback;
- editor selection event.

Dropped on save/unload unless a higher-level semantic process has already converted it into durable state.

### 7.3 Reconstructible work

Examples:

- renderer dirty flags;
- navigation cache;
- broad-phase physics cache;
- derived waveform thumbnail;
- interpolation caches.

Omit and rebuild.

### 7.4 External waits

Examples:

- HTTP response pending;
- file chooser pending;
- notification permission prompt pending;
- remote service response pending.

Snapshot may record a non-authoritative wait descriptor if product semantics need it:

```text
ExternalWait
  wait_id
  originating_attachment_id
  service_name
  correlation_id      # not a capability token
  restore_policy
  requested_logical_tick
```

but never the capability lease, browser object, socket, file handle, promise, or native object.

## 8. Timer and clock domains

SMX-004 requires explicit clock domains. SMX-007 defines lifecycle behaviour.

### 8.1 `thing_active` clock

- advances only while the Thing is semantically ACTIVE;
- pauses in DORMANT;
- snapshot stores remaining/due active-time state;
- unload preserves it without advancing;
- restore resumes from saved remaining time when reactivated.

Use for “after 2 seconds of this object actually running”.

### 8.2 `world_logical` clock

- advances with the authoritative world simulation;
- can mature while target is dormant/unloaded;
- if target is resident/dormant, the timer may be an explicit wake condition;
- if target is unloaded, maturity creates a durable pending-delivery/wake obligation rather than requiring a resident object.

Use for “open this door at world tick N” or persistent-world scheduling.

### 8.3 `external_wall` clock

Wall-clock time is an external nondeterministic input.

A wall deadline must declare an explicit resume policy such as:

- `cancel_on_restore`;
- `sample_on_resume` — host supplies current time as a fresh external input;
- `host_durable_deadline` — trusted host service owns the durable alarm and later emits a result/event.

SplashMX must not silently convert wall elapsed time into deterministic simulation elapsed time.

## 9. External services and side effects

### 9.1 No implicit reissue

If an HTTP request was already issued before snapshot, restore must not call HTTP again simply because the behaviour is still awaiting a result.

That would duplicate side effects and violate LIF-007.

### 9.2 Restore policies for external waits

Candidate policies:

- **cancel_on_restore** — resume continuation with explicit cancellation/restored-without-result error;
- **host_resume** — only if a trusted host service supports durable correlation without serializing authority/handles;
- **session_only** — external wait is omitted; dependent runtime state must tolerate loss;
- **author_reissue** — restore reports absence and author logic explicitly chooses to issue a *new* request with new causal/request identity.

No policy means “blindly replay the original service invocation”.

### 9.3 Side-effect receipts

A future runtime may maintain host-owned idempotency/effect receipts for services that need exactly-once-ish behaviour. Such receipts are service infrastructure, not general author-visible capability tokens.

SMX-007 does not require exactly-once external I/O.

## 10. References, absence, and tombstones

SMX-005 reference states remain authoritative:

- `loaded`;
- `known_unloaded`;
- `tombstoned`;
- `unknown`;
- `incompatible`;
- `dependency_unavailable`.

Lifecycle adds:

### Dormant target

A dormant resident target still resolves as loaded. Communication may:

- queue until wake;
- be a wake trigger;
- fail by explicit port/dormancy policy.

It is not “missing”.

### Unloaded target

References remain typed stable IDs. A command/event to an unloaded target requires explicit delivery policy:

- durable queue + wake/load;
- durable mailbox/pending delivery;
- reject because target not resident;
- drop only if the connection/event is explicitly ephemeral.

No generic synchronous call is possible, consistent with SMX-004.

### Tombstoned target

Resolution returns tombstoned with optional destruction metadata. Code may branch explicitly; the runtime does not retarget the reference to a new object with a similar name/path.

### Unknown target

Unknown means the identity cannot be resolved in the current catalog/dependencies. It is distinct from unloaded and destroyed.

## 11. Restore pipeline

Candidate staged restore:

1. **validate save header** — schema/runtime feature/version constraints;
2. **resolve authored basis** — document/package/definition/behaviour revisions;
3. **migrate if required** — deterministic staged migrations before live activation;
4. **allocate logical shells** — ThingIds/attachment identities/reference slots, without author code;
5. **hydrate persistable state** — public/private/PRNG/physics/timeline state;
6. **restore persistent runtime-created structure/relations/tombstones**;
7. **resolve references** — loaded/known-unloaded/tombstoned/etc.;
8. **restore durable scheduler work** — timers/continuations/queue ordering;
9. **restore external-wait descriptors** without issuing host side effects;
10. **rebuild reconstructible caches/engine objects**;
11. **rebind current context** — capabilities, peer/session, authority, controller, services;
12. **validate fully hydrated graph**;
13. **atomically publish restored world/subgraph**;
14. **optionally admit a fresh explicit restore/resume lifecycle input**;
15. **resume external input admission**.

Failure before step 13 leaves the pre-existing live world or unopened save unchanged.

## 12. Lifecycle events

Lifecycle events must distinguish causes.

Candidate semantics:

### `created`

Delivered only for first logical creation of a new Thing in this world lineage.

Not delivered for:

- load from save;
- stream-in/rehydrate;
- wake from dormancy.

### `became_dormant` / `woke`

Optional semantic events when the product exposes semantic dormancy. Hidden implementation sleep must not emit them.

### `restored`

Not implicitly treated as `created`.

If SplashMX exposes an author `restored` event, it is a **fresh post-restore external/lifecycle input after the snapshot has committed**, not replay of pre-snapshot work. Authors should therefore expect it to run each time that snapshot is restored.

The runtime itself performs no arbitrary author side effect during hydration.

### `destroying` / `destroyed`

Exact event timing remains subject to later executor/world integration, but destruction must be atomic with work cancellation/tombstone creation.

## 13. Definition/behaviour compatibility

A save/snapshot references the authored/runtime basis required to interpret state.

At minimum check:

- document/package lineage/revision;
- Thing/Definition/Element provenance;
- behaviour definition/version;
- attachment identity;
- private-state schema;
- continuation/handler IDs;
- required runtime features;
- snapshot schema.

### Compatible changes

May restore directly or through deterministic migration.

### Incompatible changes

Must not silently reinterpret bytes/state. Options:

- migrate snapshot/private state;
- map continuations explicitly;
- reject restore with structured compatibility error;
- restore an older compatible runtime/package if product distribution supports it.

Definition/instance authored reconciliation remains separate from runtime snapshot migration; the two can be composed transactionally.

## 14. Physics, presentation, and network-facing state

### 14.1 Physics

Persist if semantically needed:

- transform;
- linear/angular velocity;
- gameplay-relevant body mode;
- sleeping/active semantic state if it affects future behavior.

Usually reconstruct:

- broad-phase/narrow-phase caches;
- solver warm-start caches;
- engine RIDs.

Exact Godot mapping belongs SMX-009.

### 14.2 Animation/timeline

If timeline position/state determines future semantics, persist:

- logical playhead;
- clip/state-machine state;
- direction/rate if semantically authored/runtime;
- pending semantic markers already/not-yet consumed as needed to avoid duplicate marker events.

Reconstruct render interpolation.

### 14.3 Audio

Persist only when product semantics require continuity, e.g. logical music timeline position. Do not persist device/audio-buffer handles.

### 14.4 Network

Do not persist as object meaning:

- socket/WebRTC/WebSocket objects;
- peer IDs;
- replication channel sequence numbers unless part of a topology-specific server recovery mechanism;
- current room transport;
- client interpolation buffers.

Persist authoritative world state separately. On restore, current multiplayer topology/authority rebinds according to SMX-010 policy.

## 15. Determinism and replay

### 15.1 Deterministic restore

A deterministic restore means:

> Given the same authored compatible basis + same validated snapshot, SplashMX reconstructs the same declared simulation state, durable scheduler state, logical clocks, and deterministic PRNG positions before new external inputs are admitted.

This is a concrete SMX-007 requirement.

### 15.2 Deterministic future execution

Future state is deterministic only when subsequent external inputs are also identical and the used substrate operations have deterministic semantics within the declared model.

### 15.3 Exact replay opportunity

Exact or diagnostic replay can be built from:

- authored/runtime version;
- initial snapshot;
- deterministic IR;
- ordered scheduler;
- logical clock;
- PRNG stream states;
- ordered external input log:
  - network messages;
  - host service results;
  - external clock samples;
  - sensors;
  - user input;
  - explicit entropy.

Replay mode should supply recorded inputs rather than contacting live services.

### 15.4 Limits

SMX-007 does **not** claim:

- cross-platform floating-point physics will be bit-identical;
- browser/Godot rendering is deterministic;
- external HTTP/filesystem/network actors are deterministic;
- live multiplayer can be reproduced without logging authoritative external inputs;
- a save alone is a complete replay log.

Deterministic restoration of declared state is the narrower requirement.

## 16. Security/capability interaction

Carry forward SMX-006.

### Capability grants

Live grants/leases are host/user policy state, not authored/save authority tokens.

On restore:

1. capability **requests/declarations** come from authored content;
2. current host/user policy decides current grants;
3. browser/OS permission is checked independently;
4. restored behaviour sees current availability;
5. absence/revocation follows required/optional semantics.

A save cannot resurrect an expired/revoked grant.

### Handles

Never persist raw:

- file handles;
- browser objects/promises;
- sockets;
- camera/microphone tracks;
- Godot objects/RIDs;
- native pointers;
- grant handles/tokens.

### External wait metadata

Non-authoritative correlation IDs may be saved if bounded and required by a service restore policy. They must not be usable as capabilities.

## 17. Corpus and executable evidence

Companion manifest: `docs/research/SMX-007-LIFECYCLE-FIXTURES.json`.

Direct executable coverage:

| Fixture | Cases | Observation |
|---|---|---|
| LT-001 | C-024 | Snapshot/restore reconstructs public/private state, logical tick, deterministic PRNG, and durable timer without original runtime objects. |
| LT-002 | C-006/C-012 | Unloaded referenced target remains `known_unloaded` with same ThingId. |
| LT-003 | C-024 | Taking snapshot does not change active/resident state. |
| LT-004 | C-024 | Dormancy freezes active-time timer while world-logical time continues. |
| LT-005 | C-012 | World-logical timer maturing for unloaded target becomes durable pending delivery rather than requiring resident object. |
| LT-006 | A-002 | Restore never automatically reissues an already-issued external service request. |
| LT-007 | A-002 | Restored context contains no engine handles, peer IDs, capability grants, or host service handles. |
| LT-008 | C-025 | Behaviour/private-state version mismatch fails restore unless explicit migration is supplied. |
| LT-009 | C-002/C-024 | Definition/instance provenance and runtime state restore independently without path/object-pointer dependence. |
| LT-010 | C-024/A-002 | First-creation hook is not replayed on restore; explicit restore event is a fresh post-commit input. |
| LT-011 | C-006 | Destruction creates tombstone; old reference resolves tombstoned and ordinary respawn uses new ID. |
| LT-012 | C-024 | Same snapshot restores identical deterministic simulation state before external input; different later external input may diverge without violating restore determinism. |

### Not proven here

- production Godot object reconstruction;
- exact physics state mapping;
- streaming I/O scheduling/performance;
- network topology recovery;
- collaboration save/edit convergence;
- crash-consistent on-disk package database implementation;
- bit-identical cross-platform physics/replay;
- host durable service correlation across process/browser restart.

## 18. Architecture scorecard

Candidate: orthogonal lifecycle axes + quiescent save/snapshot projection + staged restore

| Score | Assessment |
|---|---|
| S-01: 2 | Author-facing lifecycle can be simple; final editor UX not tested. |
| S-02: 3 | One lifecycle/state vocabulary covers Things/groups/behaviours without category-specific managers. |
| S-03: 3 | Lifecycle state is independent of hierarchy. |
| S-04: 3 | Identity survives dormancy/unload/restore; tombstone prevents silent reuse. |
| S-05: 3 | Behaviour-private state, timers/continuations, PRNG and migration obligations are explicit. |
| S-06: 3 | Save/restore model is directly executable in fixtures. |
| S-07: 2 | Unloaded state and pending-delivery semantics are explicit; full streaming remains SMX-008. |
| S-08: 3 | Capability/host handles are excluded from save authority and external effects are not replayed implicitly. |
| S-09: 2 | Network/session state is explicitly contextual; full topology semantics remain SMX-010. |
| S-10: N/E | Collaborative document/save interaction remains SMX-011/018. |
| S-11: 3 | Snapshot/version/schema compatibility and migrations are explicit. |
| S-12: 3 | No Godot process object is part of durable lifecycle semantics. |
| S-13: 3 | Deterministic round-trip fixtures test hidden-memory independence. |
| S-14: N/E | Snapshot/restore performance not benchmarked. |
| S-15: 3 | Version mismatch, external wait, tombstone, unavailable context, and restore failures are explicit. |
| S-16: 2 | Lifecycle concepts can remain largely hidden until needed; UX remains later work. |

Hard-gate failures observed in SMX-007 scope: **none in the model**.

## 19. Downstream handoffs

### SMX-008 streaming

May assume:

- presence/residency/activity are distinct;
- unload requires durable state or reconstructibility;
- references to unloaded Things remain valid stable IDs;
- durable world-logical work may mature while target is unloaded and create pending delivery/wake obligations;
- no Godot object must survive unload;
- stream-in uses the staged restore pipeline;
- engine/resource caches are reconstructible context.

Must still define:

- chunk/subgraph dependency scheduling;
- eviction/load policy;
- memory budgets;
- unresolved dependency handling;
- atomic multi-object stream transactions;
- asset streaming.

### SMX-009 Godot mapping

Must map:

- logical shell/hydration to Nodes/resources/components;
- physics semantic state vs engine caches;
- rebuildable engine handles;
- pause/process modes without leaking them into public lifecycle semantics.

### SMX-010 multiplayer

Must treat as runtime/topology context:

- current peer/session ID;
- transport;
- simulation authority assignment;
- controller binding;
- replication/interpolation queues.

Persistent world state may restore independently; topology rebinds after restore.

### SMX-015 destructive object-fabric harness

Must test integrated:

- snapshot while nested definition instances exist;
- behaviour swap + timer + unload + restore;
- cross-reference to unloaded/tombstoned targets;
- external service wait across snapshot/restore;
- world-logical pending delivery to unloaded object;
- deterministic state equality without original process objects.

## 20. Hypothesis status

### H-008 — stable identity must be path-independent

**Strengthened further.** Lifecycle fixtures require identity to survive dormancy, unload, reconstruction in a fresh runtime, and tombstone resolution; no hierarchy/engine pointer participates.

### H-010 — same Thing semantics can survive unloaded state

**Strengthened substantially at model level.** Stable IDs, save projections, explicit durable scheduler work, known-unloaded references, and staged reconstruction reproduce runtime semantics without surviving process objects. Full streaming implementation remains SMX-008/015.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened further at runtime-snapshot layer, unresolved end-to-end.** Restore checks authored basis/behaviour/private-state/continuation schema and uses explicit migration/rejection rather than engine object deserialization. Future real Godot-version migrations remain unproven.

No other hypothesis receives a status change from SMX-007.
