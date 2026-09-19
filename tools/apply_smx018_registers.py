#!/usr/bin/env python3
"""One-shot branch helper: append SMX-018 reconciliation to canonical registers.

The helper is deleted by its temporary workflow after applying the changes. It
exists only because the contents API exposed to the automation replaces whole
files rather than supporting safe append/patch operations.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECTIONS = {
    ROOT / "docs/02-ARCHITECTURE-HYPOTHESES.md": r'''## SMX-018 review record — 2026-09-19

Evidence: `docs/research/SMX-018-COLLABORATION-HARNESS.md`, `docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json`, `docs/research/SMX-018-DECISION-EVIDENCE.md`, and `experiments/smx-018-collaboration-harness/`.

- **H-013 strengthened further at destructive integration level.** The executable multi-replica path requires causal edit ancestry, explicit conflicts/resolutions, selective undo/redo, schema/history handling, permission revalidation and durable tombstones. Runtime peer/session IDs, authority epochs, replication traffic and capability grants are recursively rejected from collaboration data, reinforcing that runtime multiplayer and collaborative authoring are separate consistency layers.
- **H-017 strengthened substantially at destructive model level; production durability remains open.** Independent offline batches survive reunion under opposite delivery orders and duplicate delivery without a cloud document becoming canonical authority or a server copy silently winning. Missing causal ancestry pends; stale-permission work remains recoverable history but is rejected from shared materialization. O-026 retains real durable storage, relay failure, compaction and production sync evidence.
- **H-018 strengthened narrowly at collaboration-history level.** Schema-incompatible transactions are quarantined pending deterministic semantic migration rather than being merged merely because a transport/storage substrate converges. Production multi-version history migration and compaction remain O-026/SMX-020 work.

The destructive harness also records R-018-01 through R-018-04: DefinitionId-scoped definition/instance conflict detection; Thing-delete/new-connection endpoint remove-wins handling; whole-document semantic validation before transaction publication; and atomic tombstoning of incident live connections when a Thing is tombstoned. These refine the executable collaboration integrity boundary without changing hierarchy/control/authority ownership semantics.

No other hypothesis receives a status change from SMX-018. Protected source/audio/provenance semantics remain indivisible: stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. O-026 keeps production collaboration substrate, compaction, persistence, relay and UX evidence open.
''',
    ROOT / "docs/03-RAG-INDEX.md": r'''## SMX-018 collaboration-harness retrieval rules

SMX-018 is the destructive collaboration checkpoint for SMX-011. Browser/editor, migration, package, final-architecture and future collaboration work must retrieve it instead of treating replica equality or a CRDT/OT library's sync result as sufficient proof:

- `docs/research/SMX-018-COLLABORATION-HARNESS.md` — destructive synthesis, executable conflict corpus, R-018-01 through R-018-04, offline/reconnect results, footprint evidence, hypothesis effects and residual O-026 boundary.
- `docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json` — `CH-001` through `CH-028` semantic invariants and `CR-001` through `CR-028` machine-addressable conflict/reconnect traces.
- `docs/research/SMX-018-DECISION-EVIDENCE.md` — compact D-099–D-104/E-074–E-076/O-026 handoff.
- `experiments/smx-018-collaboration-harness/` — non-normative serialized causal-relay/materialization model, 39 deterministic adversarial/boundary tests and a reproducible research-model footprint probe. It is not a selected production CRDT, OT engine, database, relay or browser store.
- Durable result: semantic transaction/conflict meaning stays SplashMX-owned above a replaceable causal transport/store. Convergence and canonical document validity are separate gates.
- Offline edits can reunite under reorder/duplicate delivery without silent loss; missing ancestors pend; same-ID/different-content transactions are corruption; stale permission epochs cannot mint authority.
- Definition/instance conflict loci include actual `DefinitionId`; identically named elements in unrelated definitions must not false-conflict (R-018-01).
- Thing tombstones remove-win over concurrent new connection endpoints, and incident live connections tombstone atomically so no dangling active edge survives (R-018-02/R-018-04).
- Every transaction is staged and the complete resulting document is semantically validated before commit; invalid endpoint/port/overlay/structure cannot half-materialize (R-018-03).
- Presence remains transient. Runtime multiplayer/session/capability handles are forbidden collaboration data.
- Protected source/audio/provenance remains atomic: stable `AssetId` selects one complete digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision; concurrent replacements are complete alternatives, never field-mixed synthetic revisions.
- O-026 deliberately keeps production CRDT/OT/log/database selection, compaction/tombstone retention, browser/native crash-consistent storage, relay outage/backpressure/authentication, large-history performance and conflict UX open for SMX-019/020.

`CH-###` and `CR-###` join the stable RAG identifier families for destructive collaboration invariants and traces.
''',
    ROOT / "docs/05-DECISION-AND-EVIDENCE-LOG.md": r'''## SMX-018 decision/evidence register

### D-099 — Collaboration transport is subordinate to SplashMX semantic transactions

The destructive harness uses a content-checked serialized causal relay with no document merge policy. A future CRDT/OT/log/database may supply synchronization/storage, but cannot redefine SplashMX conflict, tombstone, undo, permission, schema or protected-media semantics.

### D-100 — Convergence and canonical document validity are independent gates

Every candidate transaction is staged atomically and the resulting SplashMX document is validated before publication. Mechanically equal replicas are not acceptable evidence if they converge on an invalid graph. This is the general enforcement form of R-018-03.

### D-101 — Definition/instance conflict loci include actual DefinitionId

R-018-01 corrects false conflicts caused by comparing coincident local element names without definition provenance. Definition-removal versus instance-overlay conflict applies only when the instance actually derives from the affected `DefinitionId` and element locus.

### D-102 — Thing tombstones have explicit connection referential-integrity semantics

R-018-02 makes concurrent new connections that name a deleted Thing participate in tombstone remove-wins. R-018-04 tombstones incident live ConnectionIds in the same atomic Thing-deletion transaction, retaining history while preventing dangling active edges or later accidental resurrection.

### D-103 — Offline permission evidence is not serialized authority

Reunion revalidates current permission policy. An edit authored under a stale permission epoch remains recoverable history but cannot enter shared canonical materialization. Peer/session IDs, runtime authority epochs, capability grants and host handles remain forbidden collaboration data.

### D-104 — Protected asset revisions remain indivisible collaboration alternatives

Stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. Label metadata may merge independently, but concurrent replacement revisions may not be field-mixed and incomplete replacements are rejected before history admission.

### E-074 — 39 deterministic multi-editor destructive tests execute the SMX-011 conflict corpus

CR-001–CR-028 plus eleven boundary/adversarial tests exercise offline partition/reunion, opposite arrival order, duplicate delivery, transaction-ID collision, missing causal ancestry, delete/edit, reparent, definitions/instances, stable ports/connections, timeline overlap, grouping, component update, selective undo/redo, stale permission, transient presence, schema mismatch, known-unloaded/tombstoned targets, explicit resolution, protected-media replacement, transaction atomicity and causal-cycle rejection.

### E-075 — Destructive execution produced four concrete collaboration-integrity repairs

R-018-01 through R-018-04 cover DefinitionId-scoped conflict detection, Thing-delete/new-connection interaction, whole-document validation before transaction commit, and atomic tombstoning of incident connections. They are regression-tested rather than hidden in topology/order-specific special cases.

### E-076 — Collaboration history footprint is observable but the Python model is not a production benchmark

The reproducible 256-edit research probe records exact serialized history and materialized snapshot sizes plus CPython rematerialization timing. The development reference run produced 53,394 bytes transaction history, 10,922 bytes persisted collaboration snapshot and 6,208 bytes canonical snapshot; median rematerialization was 139.8 ms across 15 runs on CPython 3.13.5/Linux x86_64. These numbers justify keeping production storage/index/compaction/performance work explicit, not selecting this O(n²)-class research materializer.

### O-026 — Production collaboration substrate, compaction and durable synchronization

**Status: OPEN after SMX-018.** Semantic conflict/offline behavior is destructively exercised, but final CRDT/OT/log/database choice, checkpoint/compaction and tombstone/conflict retention, browser/native crash-consistent persistence, relay outage/backpressure/authentication, production multi-version migration, large-project history performance and conflict/offline UX remain unproven.

Owner: SMX-019 for browser/editor integration and storage/latency/failure evidence where practical; SMX-020 for Architecture v1.0 reconciliation and any remaining research spike. Existing protected source/audio/provenance, capability, lifecycle, runtime-network and publishing contracts remain unchanged except for the explicit R-018-01–R-018-04 collaboration-integrity refinements above.
''',
    ROOT / "docs/research/SMX-011-COLLABORATION-SEMANTICS.md": r'''## SMX-018 destructive-harness reconciliation

SMX-018 executed this semantic contract through a serialized multi-replica causal relay and added four narrow integrity refinements. They supersede any looser behavior implied by the disposable SMX-011 Python model while preserving COL-001–COL-024's product intent:

- **R-018-01 — DefinitionId-scoped conflict loci.** A definition-removal/instance-overlay conflict requires the instance's actual `DefinitionId` plus element locus to match. Coincident element names in unrelated definitions do not conflict.
- **R-018-02 — Thing-delete versus new connection endpoint.** A concurrent connection creation naming a tombstoned Thing is held under the same remove-wins identity rule; a connection's different `ConnectionId` does not hide its semantic endpoint dependency.
- **R-018-03 — post-transaction canonical validation.** Causal convergence never bypasses SplashMX document validity. The complete candidate transaction is staged and validated; an invalid endpoint, port, overlay, structure or other canonical invariant holds the whole transaction rather than partially applying it.
- **R-018-04 — incident connection tombstones.** Tombstoning a Thing tombstones its incident live connections in the same atomic semantic transaction. Connection history/identity remains available, but no active edge may target a destroyed Thing.

The destructive harness also carries the later protected-media wording explicitly: stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. Concurrent replacements remain complete alternatives and cannot field-mix. See `docs/research/SMX-018-COLLABORATION-HARNESS.md` and its fixtures for executable evidence and O-026 production-substrate residuals.
''',
}

for path, section in SECTIONS.items():
    text = path.read_text(encoding="utf-8")
    marker = section.splitlines()[0]
    if marker not in text:
        path.write_text(text.rstrip() + "\n\n" + section.strip() + "\n", encoding="utf-8")
        print("updated", path.relative_to(ROOT))
    else:
        print("already present", path.relative_to(ROOT))
