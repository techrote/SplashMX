# SMX-042 — collaboration sync/store substrate and compaction selection

**Status:** selected production handoff for SMX-043; bounded mechanism spike, not the production collaboration module  
**Issue:** SMX-042 / #67  
**Date:** 2026-09-21  
**Authority:** Architecture v1.0 + SMX-011 + SMX-018 + SMX-022/025  
**Executable evidence:** `experiments/smx-042-collaboration-substrate-spike/`, `SMX-042-COLLABORATION-SUBSTRATE-FIXTURES.json`, and `SMX-042-COLLABORATION-SUBSTRATE-EVIDENCE.json`

## Contents

| Section | Summary |
|---|---|
| 1. Result | Selects a semantic transaction DAG, transactional local store and conservative checkpoint/compaction policy. |
| 2. Frozen semantics | Restates the CH/CR and protected-Asset contracts the substrate cannot redefine. |
| 3. Candidate comparison | Records why direct document CRDT, server-ordered OT and bare op-log are not the v1 authority. |
| 4. Selected logical substrate | Defines identity, causal ancestry, pending/replay and local ownership. |
| 5. Physical mapping | Reuses SQLite/native and IndexedDB/browser durability boundaries. |
| 6. Checkpoint and compaction | Defines explicit causal-stability frontiers and retained history. |
| 7. Evidence and residuals | Records adversarial coverage, measurements and operational risks. |
| 8. SMX-043 handoff | Freezes the production implementation contract. |

## 1. Result

SMX-042 selects a **SplashMX semantic transaction DAG over transactional local storage, with validated checkpoints and conservative causal-stability compaction**.

The selected logical record contains stable transaction identity, immutable content digest, causal parent identities, schema/history version, permission-policy epoch evidence, the exact SplashMX semantic edit body, materialization outcome and retention class. The substrate stores exact receipts and retained semantic payloads, pends missing ancestry, publishes validated checkpoints, and accepts compaction only against an **explicit causal-stability frontier**.

Native production maps the store to **SQLite WAL + `synchronous=FULL`**. Browser production maps the same logical records to **IndexedDB read/write transactions**, requesting strict durability where supported. OPFS remains prepared immutable blob/checkpoint backing only and cannot independently own or advance the collaboration head. **Relay/store copies are replicas**, never canonical document or merge authority.

This is a mechanism choice below Architecture v1. It does not amend collaboration semantics, canonical document semantics, permission policy, runtime multiplayer, protected-media meaning or local project ownership.

The critical negative rule is equally important: a CRDT field winner, OT server order, relay sequence, wall-clock timestamp, database row identity, cloud head, SQLite page, IndexedDB key, transport session or engine object never decides SplashMX semantic meaning.

## 2. Frozen semantics inherited

The substrate must preserve **CH-001 through CH-028**, **CR-001 through CR-028**, and **R-018-01 through R-018-04** from SMX-018. `SMX-042-COLLABORATION-SUBSTRATE-FIXTURES.json` repeats the CR mapping and `tools/validate_smx042.py` mechanically compares it with the authoritative SMX-018 fixture file so later edits cannot silently remap the corpus.

Required behavior remains:

- semantic transactions address stable SplashMX loci and validate as whole candidate documents before publication;
- independent concurrent loci may merge, while incompatible same-locus intent remains an explicit held conflict with the prior coherent value active;
- Thing and Connection tombstones remain remove-wins and stale work cannot resurrect identity;
- missing causal ancestors pend rather than being guessed, dropped or globally ordered by a relay;
- exact duplicate replay is idempotent and same-transaction-id/different-content is corruption;
- selective undo/redo and explicit conflict resolution are later causal semantic transactions, not history rewrites;
- stale permission-epoch or schema-incompatible work remains recoverable history but cannot materialize as authorized/current shared state;
- presence/cursors/selections remain transient;
- runtime multiplayer fields, session IDs, capability grants and host handles remain forbidden collaboration authority/data;
- local/offline work remains owned locally and can reunite later without a hosted copy silently becoming canonical;
- replica byte equality is insufficient unless the resulting canonical SplashMX document is semantically valid.

### Protected source/audio/provenance invariant

A stable `AssetId` selects one indivisible immutable revision containing:

1. revision/content digest;
2. source digest and logical source identity;
3. exact source metadata;
4. audio/media semantic metadata;
5. provenance;
6. licence/attribution;
7. derivation lineage.

Concurrent replacements remain complete alternatives. The collaboration substrate **may not combine fields from competing Asset revisions**. Incomplete protected revisions are rejected before history admission; later conflict resolution names a complete alternative/revision. Label/editor metadata may have independently defined semantic loci, but protected source/audio/provenance meaning is never field-wise reconstructed by the sync/store layer.

## 3. Candidate comparison

| Candidate | Long-offline/local ownership | Frozen SplashMX conflict/transaction semantics | Bounded compaction | Decision |
|---|---|---|---|---|
| Direct document CRDT (Automerge/Yjs-style family) | Strong | Not directly: generic document-level merge/winner policy would become a second authoring model unless SplashMX transactions are opaque above it | Mechanism-dependent, generally plausible | Rejected as canonical semantic authority. A CRDT may be reconsidered later only as opaque transport/storage machinery beneath SplashMX semantics. |
| Server-ordered OT | Weak fit | Not directly: transformation around hosted order pressures the design toward a server sequencing authority rather than explicit held graph-level conflicts | Plausible centrally | Rejected for v1 authoring authority. |
| Bare SplashMX semantic append-only op-log | Strong | Yes | No safe bounded replay/payload-retirement rule by itself | Rejected as complete production substrate. |
| SplashMX semantic transaction DAG + validated checkpoint + transactional local store | Strong | Yes | Yes, with explicit stability frontier and conservative retention | **Selected.** |

The direct-CRDT rejection is deliberately narrow. An offline-first CRDT is credible synchronization machinery, but SplashMX already owns semantic transactions, graph validation, prior-active explicit conflicts and indivisible protected revisions. Using generic document merge as the canonical authoring policy would redefine those frozen semantics; wrapping it in opaque SplashMX transactions makes its document merge policy non-authoritative by design.

No production dependency on a particular CRDT/OT library is selected here. The production handoff is the logical transaction-DAG/checkpoint contract, not a vendor/library commitment.

## 4. Selected logical substrate

### Transaction identity and exact replay

SMX-043 must bind each durable transaction to a stable `TransactionId`, actor/author identity and monotonic actor-local sequence or an equivalently collision-resistant stable scheme; immutable transaction content digest; zero or more causal parent identities; schema/history version; permission-policy epoch evidence; exact semantic edit body/locus information; final outcome such as applied, held-conflict, quarantined or rejected; and retention class.

Exact replay of the same `TransactionId` and digest is idempotent. The same identity with different immutable content is corruption and fails closed. Database keys, relay ordering or receipt time do not repair or override identity collisions.

### Missing ancestry and long-offline reunion

A transaction whose required parent is neither retained nor covered by the validated checkpoint causal floor remains pending. It does not receive a guessed parent, silently become concurrent, disappear, or rely on server arrival order. A long-offline replica may author and persist a local branch without an online sequencer, exchange exact transactions/checkpoint evidence later, and reunite through the same frozen semantic validation rules.

### Local ownership and relay/store role

The local project/collaboration store is sufficient to reopen coherent authored state and retained history without a relay. Relay/store copies are non-authoritative replicas that may retain exact transaction/checkpoint data, advertise causal availability and transport missing records. Their `latest`, timestamp, database identity or server order cannot become project authority.

## 5. Physical store mapping

SMX-042 deliberately reuses rather than reselects the durability mechanisms already chosen by SMX-022/025.

### Native

Use **SQLite WAL + `synchronous=FULL`** for collaboration receipts, retained payload/history, pending transactions, checkpoint metadata and causal-floor publication. Changes that must be coherent are committed in one SQLite transaction. The disposable spike exercises rollback/reopen under injected pre-commit failures. SQLite rowids, pages and WAL offsets remain physical implementation details rather than semantic identity.

References rechecked for this spike on 2026-09-21: SQLite WAL documentation and `PRAGMA synchronous` documentation.

### Browser

Use **IndexedDB read/write transactions** for equivalent logical records. Request strict durability where supported and preserve SMX-025 typed denial/quota/persistence outcomes. OPFS may hold prepared immutable checkpoint/blob bytes, but cannot independently advance the project/collaboration head.

This spike does not claim that its Python/SQLite oracle is browser-production evidence. SMX-043 owns the real IndexedDB implementation and browser crash/restart campaign.

## 6. Checkpoint and compaction

### Validated checkpoint

A checkpoint is a complete semantically validated canonical authored snapshot plus its digest, an explicit per-actor causal floor proving which prefix it incorporates, and retention metadata/state needed to preserve conflict/tombstone/quarantine semantics. Publishing the checkpoint and retiring eligible payload is atomic in the local store.

### Explicit causal-stability frontier

Compaction receives an **explicit causal-stability frontier** from the future authenticated collaboration membership/acknowledgement layer. It may not infer safety from wall-clock age, relay connectivity, relay `latest`, local receipt time, the set of replicas currently online, or cloud presence. The spike rejects a frontier that moves backwards or claims locally unseen actor sequence.

The exact authenticated acknowledgement/membership protocol is intentionally deferred to SMX-043. Unknown stability therefore means no compaction, not guessed stability.

### Conservative v1 retirement

After a validated checkpoint incorporates a causally stable prefix:

- applied ordinary transaction payloads may retire;
- applied explicit resolution transaction payloads may retire;
- compact **transaction receipts (`TransactionId` + digest + actor/sequence + final status) remain**, preserving duplicate/collision evidence;
- tombstone payloads remain;
- explicit held-conflict alternatives remain;
- schema/policy quarantine payloads remain;
- protected-Asset competing alternatives remain.

A later bounded receipt/tombstone retirement design is allowed only after proving equivalent replay/collision, non-resurrection, conflict-history and long-offline guarantees. This spike does not invent an archival/member-retirement rule absent from Architecture v1.

A compacted causal parent remains satisfied only because the validated checkpoint floor proves that parent is incorporated. The floor is semantic checkpoint evidence; deletion of a payload alone never proves ancestry.

## 7. Evidence, boundaries and operational risks

### Adversarial boundary

`CSF-001..013` and the executable spike cover missing-parent pend/retry, opposite independent arrival order, exact duplicate replay and same-ID/different-content corruption, crash injection after receipt and payload writes before commit, invalid/regressing stability frontiers, ancestry satisfaction through a compacted checkpoint floor, retained tombstone/conflict/quarantine/protected-alternative payloads, compact receipt preservation, local reopen without relay/cloud head, incomplete protected-Asset rejection, preservation of two complete competing Asset alternatives, and history/checkpoint/receipt measurements.

The dedicated CI gate reruns the inherited SMX-018 collaboration corpus plus SMX-023 canonical-core and SMX-025 persistence regressions, so the selection evidence does not become detached from the semantics and durability mechanisms it depends on.

### Bounded storage probe

A disposable native probe captured on 2026-09-21 used CPython 3.13.5 on Linux x86_64 / AMD EPYC 9V74. Exact metadata is in `SMX-042-COLLABORATION-SUBSTRATE-EVIDENCE.json` using the SMX-021 benchmark-evidence contract.

For 4,096 sequential transaction envelopes with every 97th retained as a held conflict, the observed single-run mechanism sample was 166.990 ms ingest, 17.108 ms compaction, 638,415 B payload before compaction, 6,546 B retained payload after compaction, 420,781 B compact receipt index, 127 B checkpoint representation, and 4,054 retired versus 42 retained payloads. These figures are mechanism-selection observations for that environment, **not product performance or storage SLOs**.

The important result is qualitative: checkpointing can remove most causally stable ordinary payload/replay burden while compact receipts and semantically retained records still grow. That residual growth is explicit input to SMX-043 rather than hidden through unsafe deletion.

### Residual risks

- compact receipt growth remains linear in accepted transaction count in this conservative v1 selection;
- retained tombstone/conflict/quarantine/protected-alternative history can grow until explicit archival/member-retirement semantics prove safe retirement;
- authenticated durable-replica membership and acknowledgement are not invented by this spike and must fail conservative when unknown;
- IndexedDB strict durability is a platform request/property, not a guarantee that browser site data can never be evicted; SMX-025 backup/export and typed failure rules remain;
- relay/backpressure/authentication and large-project conflict/history UX remain later production work;
- direct document CRDT, relay timestamps, cloud heads and last-writer shortcuts remain forbidden as canonical semantic authority.

No Architecture-v1 contradiction was found; no ADR is required.

## 8. SMX-043 production handoff

SMX-043 production handoff is now specific enough to implement without repeating broad substrate discovery:

1. implement the production semantic transaction envelope/receipt DAG above `canonical.core`;
2. port **CR-001 through CR-028** and retain R-018-01..04 at the production collaboration boundary;
3. implement SQLite/native and IndexedDB/browser transactional stores with pending ancestry, validated checkpoint publication and typed failures;
4. enforce bounded history/pending/ancestry/conflict/diagnostic resources and exact duplicate/collision checks;
5. implement authenticated replica/member acknowledgement sufficient to derive the explicit conservative stability frontier; unknown stability means no compaction;
6. compact only within the retirement rules frozen here before considering any broader retention reduction;
7. keep relay/store copies non-authoritative and prove long-offline branch/reunion without cloud canonical ownership;
8. preserve stale-permission/schema-incompatible work as recoverable history without authorized materialization;
9. preserve complete protected Asset revision alternatives and reject incomplete or field-mixed admission;
10. keep runtime multiplayer/session/capability/engine state out of collaboration history.

Production relay UX and final conflict/history UI remain later collaboration-gate work. The selected sync/store substrate is complete enough for SMX-043 to proceed without redefining Architecture v1 semantics.
