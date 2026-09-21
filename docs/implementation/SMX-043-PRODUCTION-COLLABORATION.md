# SMX-043 production collaboration sync, store, conflicts and history

**Status:** production implementation contract for issue #68.  
**Authority:** Architecture v1 remains authoritative; this document implements the SMX-042 selected semantic transaction DAG + validated checkpoint + explicit causal-stability frontier substrate and does not amend Architecture v1.

## Boundary

Collaboration is a separate consistency/history plane above canonical authored state and separate from runtime multiplayer replication. `TransactionId` is an exact actor/sequence semantic history identity. SQLite row IDs, relay/store locations, transport/session/socket identities, presence, cursors and selections are private/transient mechanisms and cannot become authored identity.

A collaboration transaction carries complete deterministic-canonical snapshots for its exact base revision and candidate revision. That is intentionally conservative for the first production vertical: it provides an independently validated three-way semantic boundary without inventing a second patch language. History payload growth is controlled by the SMX-042 explicit causal-stability compaction boundary; exact receipts survive payload retirement so replay/collision evidence is not lost.

## Admission and causal rules

Production admission is prepare-before-publish. Exact transaction bytes are bounded and deterministic. The base and candidate are independently deserialized through SMX-024 and therefore pass complete canonical and protected-Asset validation before history admission. A transaction base must match an exact locally known `ProjectRevisionId` and bytes. When the base was produced by a prior collaboration transaction, that producer must also appear in the causal parents.

Missing ancestors remain pending. A transaction whose ancestor was quarantined/held-invalid cannot materialize state. Unsupported history versions are quarantined rather than guessed. Permission epochs are monotonic; stale or future-epoch work remains recoverable exact history but does not become active authorized state.

The remote relay/store is never canonical ownership. An authenticated relay envelope HMAC-binds exact transaction bytes to a principal and requires the principal to match the transaction actor, but authentication alone grants no capability or semantic edit authority. The same local SQLite head is authoritative with or without a relay.

## Merge and conflict semantics

Three-way merge is keyed by stable semantic identities. Disjoint stable-ID records can converge. Concurrent incompatible edits to one semantic record materialize an explicit conflict and retain both complete project alternatives rather than selecting by arrival timestamp. Definition conflicts use the actual stable `DefinitionId`, preserving **R-018-01**.

Thing/Connection/Relationship tombstones are remove-wins. A concurrent new Connection cannot resurrect a tombstoned Thing, preserving **R-018-02**, and every incident Connection/Relationship is tombstoned before publication, preserving **R-018-04**. After synchronization convergence the complete candidate document is independently validated through the canonical kernel; structural convergence is insufficient. An invalid merged whole result is retained as held conflict history while the previous coherent head remains active, preserving **R-018-03**.

Conflict resolution is itself a new validated semantic transaction. Conflict rows are marked resolved only inside the same SQLite transaction that publishes the valid new head. Selective undo is intentionally conservative: only the current leaf transaction may be inverted, only while its before-state remains retained and no unresolved conflict is attached; undo publishes a new semantic revision rather than rewinding history.

## Crash consistency and compaction

Native collaboration persistence uses SQLite WAL with `synchronous=FULL`. Receipt, exact payload, parent edges, candidate/merged revision records, explicit conflicts, undo state and head update publish in one `BEGIN IMMEDIATE` transaction. Deterministic fault hooks exercise interruption after receipt, payload, conflicts and head mutation and immediately before COMMIT; reopening yields the previous coherent head for every pre-commit interruption.

Compaction accepts only an explicit non-regressing causal-stability frontier. It may retire causally-stable `ordinary` and resolved-history payload/undo material while retaining receipts. `tombstone`, unresolved `conflict`, `quarantine` and `protected-alternative` payload classes are retained. The validated checkpoint records the coherent current project plus causal floor; wall-clock age, relay connectivity and "looks old" heuristics never imply stability.

## Protected source/audio/provenance contract

A stable `AssetId` continues to select one indivisible immutable protected revision containing **revision/content digest**, **source digest and logical source identity**, **exact source metadata**, **audio/media semantic metadata**, **provenance**, **licence/attribution**, and **derivation lineage**. Collaboration never merges those fields independently. Competing Asset replacements become complete protected alternatives; the prior active complete revision remains coherent until an explicit validated resolution transaction selects another complete revision. Target-private derivatives, caches, relay metadata and database placement cannot replace or field-mix canonical meaning.

## Production conformance

`spec/production/smx043-collaboration-fixtures.json` freezes PC-001..PC-024. `tests/production/test_smx043.py` exercises exact replay/collision, out-of-order causal delivery, offline divergence/reunion, explicit conflicts, R-018-01..04, permission/history quarantine, unknown-base denial, crash/reopen, explicit-frontier compaction, protected-Asset alternatives, transactional conflict resolution, selective undo, authenticated relay ingress, transient presence and independent bounds. The dedicated workflow also re-runs the SMX-018 semantic corpus, SMX-042 substrate spike, and inherited SMX-023/024/025 production tests.

No Architecture-v1 contradiction was found during this implementation, so no post-freeze ADR is required.
