# SMX-018 — Collaborative-editing conflict and offline-reconnect harness

Status: **destructive research evidence / pre-Architecture-v1.0**  
Issue: SMX-018 / #18  
Evidence date: **2026-09-19**

SMX-018 turns the user-visible collaboration semantics from SMX-011 into a serialized, multi-replica, adversarial execution harness. It deliberately does **not** select a production CRDT/OT/database/cloud relay. The tested candidate is the minimum semantic substrate SMX-011 actually requires: local append-only semantic transactions, explicit causal dependencies, content-checked transaction identity, a dumb relay that transports serialized transactions without deciding document meaning, and deterministic SplashMX materialization/conflict validation above that relay.

The result strengthens the local-first model, but it also found four concrete boundary defects that a mechanically convergent substrate could otherwise hide. Those repairs are recorded as R-018-01 through R-018-04 and are requirements for later implementations.

## Contents

| Section | Summary |
|---|---|
| 1. Result | States what the destructive harness establishes and does not establish. |
| 2. Harness shape | Describes replicas, serialized relay, semantic materializer and validation boundary. |
| 3. Executed conflict corpus | Maps the required issue cases to CR-001–CR-028. |
| 4. Repairs found | Records R-018-01–R-018-04. |
| 5. Offline/reconnect and causality | Records reorder, duplicate, missing-ancestor and stale-permission behavior. |
| 6. History, undo and resolution | Shows causal undo/redo and explicit conflict resolution. |
| 7. Protected media | Preserves the indivisible AssetId revision contract. |
| 8. Size/performance observations | Records bounded model evidence without pretending it is production data. |
| 9. Hypothesis reconciliation | Updates H-013/H-017/H-018 at destructive-model level. |
| 10. Residual work | Hands production substrate/storage/UX evidence to SMX-019/020. |

## 1. Result

The SMX-011 product semantics survive a multi-editor execution model in which two replicas can diverge offline, serialize transactions through a relay, receive the same transaction set in different orders, receive duplicate deliveries, reconnect with missing causal ancestors, and rematerialize the document independently.

The central result is stronger than “both replicas have the same bytes”:

- automatic-merge cases converge to the same **valid SplashMX document**;
- explicit-conflict cases converge to the same retained conflict record while keeping the prior coherent document active;
- tombstone cases do not resurrect destroyed Thing or Connection identities;
- multi-operation transactions are validated and committed atomically;
- stale permission/schema work remains inspectable history but is not admitted to shared canonical state;
- cursors/selections/presence never enter relay history or persisted collaboration snapshots;
- runtime multiplayer/session/capability fields are rejected recursively from collaboration payloads;
- the current protected media revision is never synthesized by field-wise merging two competing replacements.

The harness contains **39 deterministic tests**, including CR-001–CR-028 and eleven additional adversarial/boundary tests. `docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json` is the machine-readable contract. `experiments/smx-018-collaboration-harness/` contains the disposable implementation and reproducible footprint probe.

This evidence does **not** make the Python relay a production architecture. It intentionally leaves CRDT/OT/log/database selection, durable browser/native storage, compaction, cloud relay failure handling, authentication, and large-project performance open.

## 2. Harness shape

```text
Editor A replica                    Editor B replica
├─ same canonical base              ├─ same canonical base
├─ local semantic tx log            ├─ local semantic tx log
├─ local transient presence         ├─ local transient presence
└─ current permission policy        └─ current permission policy
          │                                  │
          └──────── serialized tx ───────────┘
                         │
                 content-checked relay
                 ├─ tx id -> exact payload
                 ├─ duplicate idempotence
                 └─ same-id/different-payload rejection
                         │
          ┌──────────────┴──────────────┐
          │                             │
 deterministic semantic           deterministic semantic
 materializer + validator         materializer + validator
```

The relay has no map/list/register conflict rules. It cannot choose a property winner, resurrect a tombstone, decide a component migration, or mint permission. Its job is only to preserve exact transaction identity and bytes while allowing adversarial delivery order. SplashMX semantics remain above it.

Every candidate transaction is applied to a private copy and the resulting document is semantically validated before publication. This matters because replica equality can converge on an invalid graph. The harness therefore treats **document validity as an independent gate from causal convergence**.

The model carries the four planes from SMX-011 unchanged:

1. canonical authored document;
2. durable collaboration transactions/conflicts/history;
3. separate runtime multiplayer state;
4. transient collaboration presence.

## 3. Executed conflict corpus

The required issue corpus is executable rather than prose-only:

| Required pressure | Trace(s) | Observed semantic outcome |
|---|---|---|
| delete vs edit | CR-003, CR-024 | Thing tombstone wins; edit remains non-materialized; no resurrection. |
| same-property concurrent edit | CR-002 | prior coherent value remains active; both proposals form deterministic conflict. |
| reparent vs reparent | CR-004 | prior legal parent remains; both target parents retained as conflict intent. |
| definition edit vs instance override | CR-005–CR-007 | compatible edits merge; destructive same-definition overlap conflicts; unrelated definition identities do not false-conflict. |
| structural edit vs new connection | CR-008–CR-011 | stable unchanged ports commute; port/Thing deletion protects endpoints; invalid endpoint/port never materializes. |
| overlapping timeline/keyframe edits | CR-012–CR-013 | independent keys merge; same semantic time/locus conflicts. |
| A+B grouping vs B+C grouping | CR-014 | neither grouping partially materializes. |
| component update vs local edit | CR-015–CR-016 | compatible migration preserves overlay; incompatible update is held while valid local edit survives. |
| connection create/remove races | CR-017–CR-018 | remove-wins prevents same-ID resurrection; two different creates of one ConnectionId conflict explicitly. |
| offline batches + reconnect | CR-001, CR-002, CR-018–CR-019 | union/reorder/duplicate schedules converge; missing ancestors pend until available. |
| collaborative undo/redo/history | CR-020, CR-025 | undo/redo are new causal edits with current preconditions; resolution is later history, not history rewrite. |
| permission change while offline | CR-021 | stale permission epoch is rejected from shared state while transaction remains recoverable history. |
| transient presence | CR-022 | cursor/selection remains local ephemeral state and never appears in relay or persisted snapshot. |
| schema crossing | CR-023 | incompatible operation is quarantined for migration rather than mechanically merged. |
| protected media | CR-027 | complete competing revisions remain alternatives; AssetId remains stable; no source/audio/provenance/licence/derivation field mixing. |
| transaction/document atomicity | CR-028 | a multi-operation transaction that would violate a canonical invariant is wholly held. |

The test suite also permutes arrival order, injects duplicate delivery, tests causal cycles and transaction-ID collisions, validates every accepted document, and executes a 256-edit offline batch.

## 4. Repairs found

### R-018-01 — Definition/instance conflicts require DefinitionId scope

The SMX-011 disposable model compared a removed definition element and an instance overlay primarily by element name. Two unrelated definitions can both contain an element called `body`; those edits must not conflict merely because the local element label matches.

**Repair:** conflict detection resolves an instance to its actual `DefinitionId` before classifying definition-removal/overlay overlap. CR-006 proves the same-definition conflict; CR-007 proves the unrelated-definition non-conflict.

This is a harness/model correction, not a change to COL-007's intended semantics.

### R-018-02 — Thing deletion must dominate a concurrent new connection endpoint

A connection operation targets its `ConnectionId`, so naive same-target conflict detection can miss that it semantically references a concurrently deleted Thing.

**Repair:** connection endpoints are semantic references. Concurrent `delete Thing X` versus `create Connection ... X.port ...` is classified explicitly; the Thing tombstone is the narrow remove-wins result and the new connection is held. CR-010 is the regression.

This tightens COL-005/COL-008 rather than inventing a new ownership relation.

### R-018-03 — Convergence never bypasses whole-document semantic validation

A transaction can be mechanically well formed yet create a connection to a missing port/Thing, an invalid overlay locus, or another structurally illegal state.

**Repair:** every transaction is staged on a copy and the resulting canonical document is validated before commit. A failure holds the complete transaction as `precondition_failed`; earlier operations in the same transaction do not leak through. CR-011 and CR-028 are the regressions.

### R-018-04 — Thing tombstone atomically tombstones incident live connections

Once active-edge validation was added, deleting a Thing with existing live connections exposed an underspecified referential-integrity consequence. Keeping those connections active produces an invalid canonical graph; preserving them as active would also create a later resurrection hazard.

**Repair:** the semantic effect of a durable Thing tombstone includes tombstoning incident live ConnectionIds in the same atomic transaction. The connection records/history remain available but are no longer active edges. The repair preserves stable identities and does not infer behavioural ownership from hierarchy.

## 5. Offline/reconnect and causality

CR-001 and CR-002 author work on disconnected replicas, reconnect them through a serialized relay, and deliberately deliver the same transaction set in opposite orders. The replicas converge to identical semantic snapshots for both an automatic-merge case and an explicit-conflict case.

CR-019 withholds a causal ancestor while delivering its dependent transaction. The child remains `missing_causal_dependency`; it is not guessed, reordered as independent, or discarded. After the ancestor arrives, both replicas materialize the same accepted state.

Duplicate delivery is idempotent because `TransactionId` names exact content. Reusing the same ID with different content is corruption and is rejected at the relay/replica boundary. A causal cycle is likewise a typed invalid history rather than a topological-order accident.

Current permission policy is context, not serialized authority. CR-021 authors an edit offline at permission epoch 1, reunites under epoch 2, and retains the transaction in history while rejecting it from materialized shared state. No capability token or host grant is accepted in collaboration data.

## 6. History, undo and resolution

Selective undo and redo are ordinary later transactions. CR-020 proves that undo of Alice's edit preserves Bob's unrelated edit; a stale inverse precondition becomes an explicit conflict instead of rewinding newer work. The additional redo adversary emits a new causal edit and likewise leaves remote work untouched.

CR-025 demonstrates explicit conflict resolution. Two concurrent proposals are held; a later transaction that causally depends on and explicitly resolves both proposals applies a chosen/new value. The proposal transaction IDs remain in durable history, and the conflict is marked resolved rather than erased.

This keeps the SMX-011 rule that collaboration history is causal rather than one fictitious global undo timeline.

## 7. Protected source/audio/provenance semantics

SMX-013 through SMX-016 strengthened the protected-media wording after SMX-011. SMX-018 therefore uses the current complete revision contract explicitly:

```text
stable AssetId
└─ one immutable revision alternative
   ├─ digest
   ├─ source identity / metadata
   ├─ audio/media semantics
   ├─ provenance
   ├─ licence
   └─ derivation
```

A label/organizational edit is a distinct locus and can merge with one complete replacement. Two concurrent replacement revisions are indivisible alternatives. Missing `licence`, `derivation`, source, audio/media, provenance, or digest data rejects the replacement before history admission. No CRDT-style field merge may synthesize a revision whose bytes/source/audio/provenance/licensing lineage were never authored together.

This is a representation tightening for the destructive harness; it preserves, rather than redefines, the protected source/audio/provenance semantics accumulated through SMX-009/010/013/014/015/016.

## 8. Size/performance observations

`experiments/smx-018-collaboration-harness/measure.py` makes the only performance/size claim this model can support. On the local reference execution used while developing this repair (CPython **3.13.5**, Linux 6.18.44 x86_64), a deterministic 256-edit offline batch produced:

- **53,394 bytes** of canonical serialized transaction payloads at the relay;
- **10,922 bytes** for the resulting persisted collaboration snapshot;
- **6,208 bytes** for its canonical authored-document portion;
- median full rematerialization of **139.8 ms** across 15 runs (138.5–147.8 ms observed).

These numbers are **not** production CRDT/database/browser measurements. The implementation intentionally recomputes pairwise conflict classification and rematerializes from the small research log, so its asymptotics are unsuitable as a production design decision. The useful evidence is that storage/history cost is observable and must be measured independently from canonical document size; O-021 therefore remains open rather than quietly treating this prototype as a persistence design.

## 9. Hypothesis reconciliation

### H-013 — runtime multiplayer and collaboration are separate consistency layers

**Strengthened further.** The executable collaboration path requires causal edit ancestry, explicit conflicts/resolutions, selective undo, schema/history handling, permission revalidation and durable tombstones. Runtime multiplayer peer IDs, authority epochs, replication messages and transport handles are recursively rejected from this data. Nothing in the harness benefits from reusing SMX-010 state/event/input replication as document consistency.

### H-017 — offline-first authoring is compatible with collaboration

**Strengthened substantially at destructive model level; production durability remains open.** Independent offline batches reunite under adversarial delivery order/duplication and preserve valid work. Conflicting work is surfaced rather than silently replaced by a server copy. A relay transports history but is not canonical document authority.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened narrowly at collaboration-history level.** Schema-incompatible transactions are quarantined until deterministic semantic migration rather than being merged just because the storage representation converges. Real multi-version migration/compaction remains open.

No other hypothesis receives a status change from SMX-018. Existing Thing, execution, security, lifecycle, streaming, runtime multiplayer, publishing and protected-media contracts remain unchanged except for R-018-01–R-018-04's explicit collaboration-integrity refinements.

## 10. Residual work and handoff

SMX-018 does **not** choose the final collaboration substrate. O-021 remains open for the underlying persistence questions; SMX-018 records the production collaboration handoff as **O-026**, including:

- production CRDT/OT/semantic-log/database selection or hybridization;
- checkpoint/compaction and tombstone/conflict-retention proof;
- browser/native persistent-store crash consistency and quota behavior;
- relay outage, backpressure, authentication and multi-device discovery;
- production multi-version operation migration;
- large-project causal-index/history performance;
- conflict-resolution, history, presence and offline-recovery UX.

SMX-019 must exercise the accepted collaboration semantics in the browser vertical slice where practical and measure user-visible storage/latency/failure behavior. SMX-020 must carry any remaining durability/compaction/substrate uncertainty into Architecture v1.0 rather than presenting this deterministic Python harness as production sync proof.
