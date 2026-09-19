# SMX-011 — Collaborative authoring conflict semantics

Status: candidate pre-architecture semantic contract for SMX-018 destructive falsification

Issue: SMX-011 / #11

Established: 2026-09-19

This document defines the **human-visible collaboration behavior before selecting a CRDT, OT engine, database, sync service, or wire protocol**. It builds on the stable ID/transaction model from SMX-003/005 and deliberately remains separate from SMX-010 runtime multiplayer replication.

The selected candidate is a **SplashMX-owned semantic transaction + conflict layer over a replaceable causal synchronization/storage substrate**. Independent semantic loci merge automatically. Concurrent edits that would make an authored invariant ambiguous or illegal remain explicit user-visible conflicts, while deletion/tombstone cases use narrow remove-wins rules to prevent accidental resurrection. Convergence is required, but byte/state equality alone is not sufficient evidence of correct collaboration semantics.

The companion JSON fixtures and Python model are non-normative evidence. They do not select Automerge, Yjs, ShareDB, a production server, a package format, or a final history-store implementation.

## Contents

| Section | Summary |
|---|---|
| 1. Result and invariants | Defines the collaboration semantic boundary and COL-001–COL-024. |
| 2. State planes | Separates canonical document, durable collaboration history/conflicts, runtime multiplayer, and transient presence. |
| 3. Transaction and causal model | Defines semantic transaction identity, causal ancestry, preconditions, conflict and resolution records. |
| 4. Human-visible conflict corpus | Defines product behavior for every issue-required conflict class before implementation selection. |
| 5. Local-first reconnect | Defines offline work, reunion, replay/idempotence, tombstones, and permission revalidation. |
| 6. Undo/redo and resolution | Defines selective compensating edits instead of a fictitious global linear undo stack. |
| 7. Migration and partial loading | Defines schema-aware operation migration/quarantine and known-unloaded handling. |
| 8. Protected media/provenance semantics | Prevents source/audio/provenance field mixing during concurrent asset replacement. |
| 9. Implementation-family comparison | Compares structured CRDT, OT, operation-log/transaction, and hybrid approaches. |
| 10. Executable evidence | Maps CF-001–CF-028 plus extra boundary tests to the candidate. |
| 11. SMX-018 handoff | Defines the destructive multi-editor conflict-corpus test plan. |
| 12. Hypothesis status | Reconciles H-013/H-017/H-018. |
| 13. Primary/comparative sources | Records current source material checked for SMX-011. |

## 1. Research result and semantic invariants

SplashMX collaboration should synchronize **author intent expressed as stable-ID semantic transactions**, not expose a storage CRDT or transport packet format as the authoring model. The merge layer must be able to retain incompatible proposals, preserve a coherent executable document, and ask for an explicit resolution where automatic choice would hide meaningful intent.

- **COL-001 — semantic edit subjects:** collaborative operations address stable document IDs and semantic loci, never hierarchy paths, JSON indexes, file offsets, transient peer IDs, or Godot handles.
- **COL-002 — human-visible semantics precede machinery:** desired conflict outcomes are product rules. A CRDT/OT/library is acceptable only if it can implement those rules without redefining them.
- **COL-003 — independent loci auto-merge:** concurrent edits that commute under SplashMX semantics materialize automatically regardless of delivery order.
- **COL-004 — incompatible same-locus intent is retained explicitly:** concurrent incompatible values are not silently discarded merely to obtain a deterministic winner. The prior coherent value may remain active until a user/policy resolution transaction is authored.
- **COL-005 — delete/edit is tombstone/remove-wins:** a concurrent edit cannot resurrect the same destroyed identity. The edit remains inspectable/recoverable in collaboration history, but ordinary materialization keeps the tombstone.
- **COL-006 — structural invariants outrank mechanical convergence:** incompatible reparent/grouping operations are held rather than manufacturing a deterministic but arbitrary structure.
- **COL-007 — definition and instance edits retain distinct meaning:** compatible base-definition changes and instance overlays coexist; removal/invalidation of an overlay target is an explicit reconciliation conflict.
- **COL-008 — connections use stable ports:** structural movement can coexist with connection edits, but deletion/incompatibility of a referenced port conflicts with a concurrent connection operation before destructive propagation.
- **COL-009 — timeline edits target semantic keyframe loci:** independent keys merge; incompatible edits to the same key/time locus are explicit conflicts rather than array-index races.
- **COL-010 — multi-object structural commands are atomic:** grouping, multi-move, component-restructure, and similar commands must not partially apply merely because some constituent records could merge.
- **COL-011 — component update never consumes local work implicitly:** compatible update/migration may preserve a local overlay; an update that cannot absorb a concurrent local edit is held and surfaced.
- **COL-012 — connection deletion prevents same-ID resurrection:** concurrent remove/recreate of the same `ConnectionId` is remove-wins. A deliberate later connection uses a new ID or an explicit resolution transaction.
- **COL-013 — offline work is first-class:** a local replica can author transactions without cloud authority. Reconnection exchanges causal changes; duplicate delivery/order cannot silently lose valid independent work.
- **COL-014 — history is causal, not one fake global timeline:** transaction identity, ancestry and resolution relations survive synchronization independently of UI presentation order.
- **COL-015 — undo/redo is collaborative semantic editing:** undo emits a new compensating transaction with current preconditions. It cannot rewind or overwrite unrelated remote work.
- **COL-016 — permissions are revalidated on reunion/materialization:** an offline edit authored under stale permissions cannot mint authority. It is rejected/quarantined from shared state while remaining available to the author for recovery/export where policy permits.
- **COL-017 — presence is transient:** cursors, selections, typing indicators, viewport state and ordinary online presence are neither canonical document state nor durable edit history.
- **COL-018 — collaboration history is schema-aware:** operations/history crossing schema or IR versions are deterministically migrated or quarantined before reconciliation; sync convergence does not waive feature/schema compatibility.
- **COL-019 — partial loading preserves absence semantics:** `known_unloaded`, tombstoned, unknown and incompatible targets remain distinct. A valid edit to known-unloaded content may remain pending rather than becoming dangling or guessed.
- **COL-020 — synchronization substrate is replaceable:** CRDT/OT/custom log/database/server mechanisms may implement causal exchange/storage but do not become SplashMX public authoring semantics by accident.
- **COL-021 — runtime multiplayer remains a separate consistency layer:** SMX-010 state/event/input/authority/relevance messages are not collaboration transactions and cannot substitute for base revisions, conflicts, causal edit history or undo.
- **COL-022 — protected asset replacement is atomic:** an `AssetId` remains stable while one replacement revision carries its immutable digest, logical source/audio identity, provenance/licensing and derivation metadata as a coherent unit. Concurrent replacements cannot field-mix those records.
- **COL-023 — unresolved conflicts preserve a coherent executable side:** conflict metadata/proposals may be durable collaboration state, while canonical materialization retains the last coherent state or the narrow accepted winner rule. Publishing affected unresolved loci must fail or require an explicit product policy; it must not guess.
- **COL-024 — SMX-018 must test semantic invariants as well as convergence:** equal replicas are necessary, not sufficient. The destructive harness must prove no resurrection, no half-transactions, no provenance mixing, no authority leakage and no silent conflict loss under reorder/duplicate/offline schedules.

## 2. Canonical, durable collaboration, runtime, and transient state

Four planes remain separate.

### Canonical authored document

The materialized SplashMX document defined by SMX-005: stable Things/definitions/instances/ports/connections/assets and their current coherent authored state. It remains independently loadable without replaying collaboration history from genesis.

### Durable collaboration state

Optional authoring infrastructure may retain:

- semantic transaction IDs and operation payloads;
- causal dependencies/base revision evidence;
- actor/principal attribution suitable for history/audit, not host capability tokens;
- explicit unresolved conflict records and alternative proposals;
- resolution and compensating-undo relations;
- schema/version metadata required to migrate historical operations;
- tombstone/history retention needed to prevent accidental resurrection.

This state can be compacted/checkpointed later, provided the observable collaboration semantics and required tombstone/conflict evidence survive.

### Runtime multiplayer state

SMX-010 authority epochs, replication baselines, transient peer IDs, runtime input/event/state messages, prediction/interpolation and relevance remain outside the collaboration protocol. Shared authentication or transport infrastructure is allowed, but semantic message classes cannot be conflated.

### Transient collaboration presence

Cursor, current selection, viewport, typing indicator, pointer trail and presence heartbeat are explicitly ephemeral. They may use a low-latency awareness channel and may disappear when a session disconnects. Their loss cannot mutate the document or undo history.

## 3. Transaction, causality, and conflict model

A candidate collaboration transaction contains conceptually:

```text
TransactionId
Actor/author principal
Schema/feature epoch
Causal dependencies and/or base revision evidence
Permission-policy epoch evidence
Ordered semantic operations
Per-operation/transaction preconditions
Optional inverse-of / resolves relations
```

Operations reuse the SMX-005 ID/locus model. A storage implementation may internally encode changes as CRDT operations, OT operations, database rows or an append log, but collaboration-visible conflicts are expressed in SplashMX terms such as `ThingId + property`, `ThingId + parent`, definition element, stable port/connection, timeline keyframe, instance overlay, or complete asset revision bundle.

Two transactions are concurrent when neither causally contains the other. The semantic merge layer then classifies their operations. Independent loci can commute. Invariant-sensitive overlaps either use a deliberately narrow deterministic product rule (notably tombstone remove-wins) or become explicit conflicts.

A conflict record minimally identifies:

- participating transaction IDs;
- affected semantic loci;
- conflict class;
- current coherent materialized side;
- retained alternatives;
- resolution policy/available actions.

Resolution is itself a later semantic transaction causally aware of the proposals it resolves. History is not rewritten to pretend the conflict never happened.

## 4. Human-visible conflict corpus

These outcomes are defined **before** selecting implementation technology.

| Conflict case | Canonical/materialized outcome | Human-visible behavior |
|---|---|---|
| Alice deletes Thing X while Bob edits X | X remains tombstoned; Bob's edit does not recreate X. | Show deleted Thing + retained edit proposal; offer deliberate restore-as-new/copy/manual resolution where meaningful. |
| Concurrent edits to different fields | Both apply. | No conflict UI beyond ordinary history. |
| Concurrent incompatible edits to the same property | Keep last coherent value active; retain both proposals. | Show a focused value conflict with both authors/values; user chooses/edits a resolution. |
| Concurrent reparent to different groups | Keep prior legal parent until resolution. | Present both target parents; do not choose based on actor ID, network arrival or lexical ordering. |
| Definition base edit + compatible instance override | Both survive; instance override remains explicit. | Provenance inspector can show inherited change plus local override. |
| Definition removes element while instance edits/overrides it | Hold invalidating base change/affected reconciliation atomically. | Explicit definition/instance conflict; options can migrate, retarget, drop override, or reject update. |
| Structure moves while another author connects via stable unchanged port | Both apply. | No conflict; stable endpoint identity prevents path repair. |
| Structure removes/changes port while another author connects to it | Keep prior coherent interface; hold competing destructive/connection edits. | Explicit protected-interface conflict before destructive propagation. |
| Independent timeline/keyframe edits | Merge. | Timeline simply contains both edits. |
| Same key/time semantic locus edited incompatibly | Hold both proposals. | Timeline conflict marker with alternatives; never array-index last-writer accident. |
| Group A+B versus B+C | Neither partial group materializes. | Show overlapping atomic grouping commands; user selects/reconstructs intended grouping. |
| Compatible component version update + local overlay | Update and overlay survive. | Normal update, with local override/provenance still visible. |
| Component update invalidates concurrent local edit | Valid local edit remains; incompatible update is held. | Component-update conflict names invalidated semantic locus and migration choices. |
| Concurrent connection create/remove on same ID | Remove-wins for that historical ID. | Deleted connection stays deleted; deliberate new connection gets new identity or explicit resolution. |
| Offline independent edits then reconnect | Union causal changes and merge. | No "server copy won" behavior; valid independent local work remains. |
| Offline conflicting edits then reconnect | Same conflict semantics as online concurrency. | Conflicts appear after reunion; neither device silently discards the other's intent. |
| Asset rename + asset content replacement | Merge because label and revision bundle are distinct loci. | Stable `AssetId`; rename does not rewrite media identity. |
| Concurrent different asset replacements | Keep current coherent bundle; retain complete alternatives. | Resolve between complete versions. Never combine A's source with B's audio/provenance/licence fields. |
| Undo one local edit after remote edits | Emit compensating transaction if current preconditions still hold. | Undo names what it is reverting; unrelated remote edits remain. |
| Undo precondition no longer valid | No destructive rewind. | Show that the target evolved; offer contextual resolution instead of clobbering later work. |
| Permissions change while user is offline | Stale-authority edit does not enter shared materialization. | Explain permission change; retain recoverable local patch/export where allowed rather than claiming it synced. |

The general policy categories are therefore: automatic semantic merge, narrow remove-wins tombstone behavior, atomic hold + explicit conflict, precondition rejection, pending-known-unloaded, and explicit resolution transaction.

## 5. Offline-first authoring and reconnect

Offline-first means the local project remains editable without a permanently authoritative cloud document. A local replica appends semantic transactions against a locally known causal frontier/base. Reconnection exchanges missing transaction identities/causal history or an equivalent compact representation.

Required properties:

1. identical transaction replay is idempotent;
2. the same `TransactionId` with different content is corruption/identity collision, not a second edit;
3. arrival order does not change the semantic result for the same causal transaction set;
4. missing causal ancestors leave dependent work pending rather than guessed;
5. tombstone semantics prevent stale offline work from resurrecting a destroyed ID;
6. permission/capability policy is re-evaluated against current policy rather than serialized as an offline authority token;
7. current document checkpoints may compact history, but compaction cannot erase conflict/tombstone evidence still required to preserve semantics.

A hosted relay can improve discovery, durability, presence and multi-device synchronization without becoming the sole authority over the canonical project model. That is the model-level basis for H-017; real storage/outage/browser behavior remains SMX-018/019 work.

## 6. Undo, redo, resolution, and history

A collaborative document has no single globally meaningful linear undo stack. SplashMX therefore treats undo/redo as author intent expressed through new semantic transactions.

A selective undo records `inverse_of=<TransactionId>` and uses current semantic preconditions. If the target locus has evolved in a way that invalidates the inverse, undo becomes an explicit conflict rather than overwriting newer work.

Redo likewise emits a new edit based on the current document; it is not a time-machine operation that rewinds every collaborator.

Conflict resolution records `resolves={...}` and depends causally on the proposals being resolved. The resolver supplies the chosen/new semantic edit against the coherent materialized state. Alternative proposals remain inspectable history until retention/compaction policy safely summarizes them.

## 7. Schema migration, compatibility, and partial loading

Collaboration history can outlive one schema/IR version. Before an operation authored under another schema participates in reconciliation, SplashMX must either:

- deterministically migrate its semantic operation/locus into the current schema under SMX-005/018 migration rules; or
- quarantine/reject it with an explicit `schema_migration_required`-class outcome.

A CRDT's ability to merge bytes/maps is not evidence that the resulting SplashMX semantics are valid under a new schema.

Partial loading similarly cannot collapse absence states. An operation targeting `known_unloaded` content may remain pending until enough catalog/chunk state is available to validate its preconditions. A tombstoned target rejects ordinary edits without resurrection. Unknown/incompatible targets remain typed failures/conflicts. Collaboration infrastructure may index operation loci without loading all object payloads, but it cannot invent target meaning from paths.

## 8. Protected source/audio/provenance semantics

SMX-009/010 explicitly protect canonical source, audio identity, immutable source/blob digest, licensing/provenance and derivation records across target/network projection. Collaboration must not weaken that guarantee.

A logical `AssetId` can retain its identity while an edit installs a new **complete asset revision bundle** containing at least:

```text
immutable digest
logical source identity / exact source metadata
audio/media semantic metadata
provenance + licence + derivation lineage
```

Label/organizational metadata may be a separate semantic locus and can therefore merge with a replacement. But two concurrent replacement bundles are indivisible alternatives. Field-wise CRDT merge of replacement A and replacement B is forbidden because it can produce a synthetic asset revision that no author created and whose provenance/licensing no longer corresponds to the bytes.

This is the explicit SMX-011 preservation of source/audio/provenance semantics requested by the repair campaign.

## 9. Implementation-family comparison

The product semantics above were fixed first. Only then were implementation families compared.

### Structured CRDT / Automerge- or Yjs-style substrate

Strengths:

- excellent local-first replication and offline reunion properties;
- operation/update sets can converge under reorder/duplication;
- mature libraries provide useful storage/synchronization building blocks;
- separate awareness/presence channels are an established pattern.

Limitations against SplashMX requirements:

- a generic map/list merge can converge to a structurally illegal or semantically nonsensical multi-record state;
- deterministic same-key winner rules are not automatically acceptable human-visible policy;
- definition/instance reconciliation, protected ports, grouping atomicity, component migration and protected asset bundles require domain constraints above primitive fields;
- library document identity/actor IDs must not become SplashMX durable Thing/Asset/Port identity.

**Disposition:** strong candidate substrate, rejected as the public conflict semantics by itself.

### Operational Transformation / ShareDB-style operation transform

Strengths:

- proven collaboration family for ordered edit streams;
- central service models can provide history, acknowledgement and permissions cleanly;
- type-specific transformation can encode richer operations than raw text positions.

Limitations:

- correctness depends heavily on operation algebra and often central ordering assumptions;
- SplashMX contains heterogeneous graph/definition/asset/timeline transactions, not one text/list type;
- offline long-lived branching and partial loading complicate a purely server-linear transform model;
- semantic tombstones/definition migration still need SplashMX-level rules.

**Disposition:** useful comparison and possible specialized implementation beneath some editor surfaces; not selected as universal semantic model.

### Semantic operation log / transaction graph

Strengths:

- directly represents SMX-005 stable-ID operations, preconditions, atomic multi-object edits, provenance and conflict records;
- natural place for selective undo, schema migration and explicit resolution;
- human conflict UX can name domain concepts rather than storage deltas.

Limitations:

- a custom log alone does not solve efficient peer synchronization, compaction, causal indexing, offline storage, transport, or proven convergence;
- retaining every operation forever is unnecessary and undesirable;
- real multi-editor scheduling/failure behavior still needs SMX-018.

**Disposition:** necessary semantic layer, insufficient transport/storage algorithm by itself.

### Selected hybrid boundary

Use SplashMX semantic transactions/conflicts as the authoritative authoring meaning, with a replaceable causal replication/storage implementation below them. That implementation may be CRDT-based, OT-assisted, log/database-backed or mixed after SMX-018 evidence. Presence remains a separate ephemeral channel.

This boundary deliberately avoids selecting a fashionable dependency before its semantics are proven compatible with SplashMX.

## 10. Executable model and fixtures

`docs/research/SMX-011-COLLABORATION-FIXTURES.json` defines `CF-001` through `CF-028`. The disposable model in `experiments/smx-011-collaboration-model/` exercises:

- independent-locus order independence;
- same-locus conflict retention;
- delete/edit tombstone remove-wins;
- reparent/reparent structural conflicts;
- compatible and invalidating definition/instance combinations;
- stable-port connection behavior;
- timeline overlap semantics;
- atomic grouping;
- compatible/incompatible component update + local edit;
- connection remove/recreate identity;
- offline reunion convergence;
- atomic asset/source/audio/provenance replacement;
- selective undo/precondition failure;
- permission-epoch rejection;
- transient presence exclusion;
- runtime-multiplayer boundary rejection;
- idempotent replay and ID collision rejection;
- known-unloaded/tombstoned target handling;
- schema-version quarantine;
- explicit resolution transactions;
- complete arrival-order permutation equivalence.

Additional boundary tests attack mixed pairwise conflict policies inside one multi-operation transaction, incomplete asset revision bundles, and cyclic causal dependencies. The first is especially important: a transaction that would "win" a delete/edit conflict cannot partially apply if another operation in the same transaction is held by a different conflict.

This evidence is deterministic/model-level. It is not proof of a production CRDT, database, editor, server, storage engine or browser sync implementation.

## 11. SMX-018 executable conflict-corpus plan

SMX-018 should implement a real multi-replica destructive harness around the eventual candidate substrate rather than merely rerun this Python model. At minimum it must create 2–5 editor replicas plus optional relay/service and run scripted disconnect/reconnect/reorder/duplicate/partition schedules.

For each `CF-001`–`CF-028` scenario, assert both replica convergence **and** COL semantic outcomes after quiescence. Add randomized/property-based schedules around the deterministic corpus, keeping named seeds for regressions.

Required destructive dimensions:

- reordered, duplicated and delayed operation delivery;
- long offline branches followed by reunion;
- relay/server restart where the candidate architecture claims durability;
- checkpoint/compaction before and after tombstones/conflicts;
- schema migration while one editor remains offline on an older version;
- partial-loaded and unloaded targets;
- permission revocation while edits are offline;
- concurrent selective undo/resolution;
- delete/edit resurrection attempts after compaction;
- multi-operation transactions that overlap in only one constituent locus;
- definition/base update against local instance overlay;
- timeline/group/connection structural conflicts;
- complete asset replacement alternatives with deliberately incompatible source/audio/provenance bundles;
- presence loss/reconnect proving that absence of awareness state does not mutate canonical history;
- injection of SMX-010 runtime peer/authority/transport fields into collaboration ingress and vice versa.

SMX-018 must fail if replicas converge to the same **wrong** state: illegal structure, resurrected ID, half-applied transaction, lost user intent, mixed provenance bundle, silently accepted stale permission, or runtime-network authority leakage. Convergence is not enough.

The harness should record implementation/library versions, storage mode, process/browser versions, seeds, network schedule, operation corpus IDs and exact materialized/conflict snapshots. If no candidate substrate can satisfy these semantics without unreasonable complexity/performance, return to SMX-011 semantics rather than weakening them silently.

## 12. Hypothesis status

### H-013 — runtime multiplayer and collaboration are separate consistency layers

**Strengthened substantially.**

SMX-010 runtime replication uses authority/state/event/input/relevance semantics. SMX-011 independently requires causal persistent edit transactions, preconditions, tombstones, retained alternatives, explicit conflict resolution, schema-aware history and collaborative undo. The executable boundary rejects runtime peer/transport fields as collaboration data. Shared authentication/transport infrastructure remains possible without merging the consistency models.

### H-017 — offline-first authoring is compatible with cloud collaboration

**Strengthened at model level; real persistence/synchronization remains unproven.**

Independent offline replicas can author semantic transactions, exchange change sets later and converge for the deterministic corpus without a cloud service becoming canonical document authority. Current evidence does not prove browser storage durability, production compaction, relay outages, large histories or multi-device security; those remain SMX-018/019 work.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened narrowly and constrained at collaboration-history level.**

Historical collaboration operations carry schema/version context and must migrate deterministically or quarantine before reconciliation. A synchronization library's structural convergence cannot bypass SplashMX schema/feature validation. Real multi-version history migration/compaction remains SMX-018/020.

No other hypothesis receives a status change from SMX-011. Existing Thing identity, source/audio/provenance, security, lifecycle, streaming and runtime-network decisions remain intact.

## 13. Current primary/comparative sources

Checked 2026-09-19. These are implementation precedents, not selected SplashMX dependencies.

### Automerge

- https://automerge.org/docs/reference/documents/conflicts/
- https://automerge.org/docs/tutorial/conflicts/
- https://automerge.org/docs/hello/
- https://automerge.org/docs/reference/documents/doc-handles/

Current Automerge documentation demonstrates local-first document merge and explicit concurrent-value conflict inspection. Its deterministic ordinary read behavior for conflicting map values is useful substrate evidence, but SplashMX does not adopt that winner as product conflict policy.

### Yjs

- https://docs.yjs.dev/api/document-updates
- https://docs.yjs.dev/api/about-awareness
- https://docs.yjs.dev/getting-started/adding-awareness
- https://docs.yjs.dev/api/undo-manager

Yjs documents commutative/associative/idempotent document updates, a separate Awareness CRDT for presence state, and scoped selective undo facilities. These support COL-013/COL-017/COL-015 as comparative precedents without selecting Yjs semantics as the canonical model.

### ShareDB

- https://share.github.io/sharedb/
- https://share.github.io/sharedb/types/

ShareDB provides an operational-transformation comparison point with synchronization/history/offline support and pluggable OT types. It demonstrates why operation algebra and server/history architecture are separate choices from SplashMX's user-visible semantic conflicts.

### Semantic-invariant warning

- https://www.inkandswitch.com/essay/convergence-is-not-enough/

Ink & Switch's 2026 article **Convergence Is Not Enough** is a useful current warning for structured collaborative applications: replicas may converge while violating higher-level invariants. SplashMX independently reaches the same engineering requirement from its multi-record Thing/definition/connection/asset semantics: COL-024 requires semantic assertions in addition to replica equality.

## Research disposition

SMX-011 selects the collaboration **semantic boundary**, not a library. The current candidate is semantic transactions/conflicts above a replaceable causal substrate, transient awareness beside it, and runtime multiplayer beside—not inside—it. SMX-018 is responsible for trying to break this model with a real multi-editor implementation before Architecture v1.0 treats it as settled.
