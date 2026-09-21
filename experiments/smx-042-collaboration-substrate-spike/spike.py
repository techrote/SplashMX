#!/usr/bin/env python3
"""SMX-042 disposable collaboration substrate/compaction selection oracle."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Mapping, Sequence

PROTECTED_ASSET_FIELDS = frozenset({
    "asset_id", "revision_digest", "source_digest", "source_identity",
    "source_metadata", "media_semantics", "provenance",
    "licence_attribution", "derivation_lineage",
})
RETAINED_CLASSES = frozenset({"tombstone", "conflict", "quarantine", "protected_alternative"})
COMPACTABLE_CLASSES = frozenset({"ordinary", "resolution"})


class CollaborationStoreError(RuntimeError):
    pass


class TransactionCollision(CollaborationStoreError):
    pass


class MissingAncestor(CollaborationStoreError):
    pass


class InvalidAssetRevision(CollaborationStoreError):
    pass


class SimulatedCrash(CollaborationStoreError):
    pass


@dataclass(frozen=True)
class Candidate:
    name: str
    semantic_transactions: bool
    explicit_prior_active_conflicts: bool
    atomic_multi_record_validation: bool
    offline_without_server_authority: bool
    causal_pending: bool
    selective_history: bool
    protected_alternatives_atomic: bool
    bounded_compaction_possible: bool
    note: str

    @property
    def architecture_compatible(self) -> bool:
        return all((self.semantic_transactions, self.explicit_prior_active_conflicts,
                    self.atomic_multi_record_validation, self.offline_without_server_authority,
                    self.causal_pending, self.selective_history,
                    self.protected_alternatives_atomic, self.bounded_compaction_possible))


CANDIDATES = (
    Candidate("document_crdt_direct", False, False, False, True, True, True, False, True,
              "Credible sync engine, but direct document merge would become a second authoring model."),
    Candidate("server_ordered_ot_direct", False, False, False, False, False, True, False, True,
              "Hosted order is a poor fit for long offline branches and explicit held conflicts."),
    Candidate("bare_semantic_oplog", True, True, True, True, True, True, True, False,
              "Represents frozen semantics but has no bounded replay/compaction contract."),
    Candidate("semantic_tx_dag_checkpoint_store", True, True, True, True, True, True, True, True,
              "Selected semantic transaction DAG, exact receipts, validated checkpoint and conservative causal compaction."),
)


def selected_candidate() -> Candidate:
    compatible = [x for x in CANDIDATES if x.architecture_compatible]
    if [x.name for x in compatible] != ["semantic_tx_dag_checkpoint_store"]:
        raise AssertionError("selection unexpectedly ambiguous")
    return compatible[0]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class TxEnvelope:
    tx_id: str
    actor_id: str
    actor_seq: int
    parents: tuple[str, ...]
    schema_version: int
    permission_epoch: int
    semantic_class: str
    body: Mapping[str, object]

    def canonical_content(self) -> str:
        value = asdict(self)
        value["parents"] = list(self.parents)
        return canonical_json(value)

    @property
    def digest(self) -> str:
        return sha256_text(self.canonical_content())


def tx_id(actor_id: str, actor_seq: int) -> str:
    if not actor_id or ":" in actor_id or actor_seq < 1:
        raise ValueError("invalid actor/sequence")
    return f"{actor_id}:{actor_seq}"


def validate_protected_asset_revision(value: Mapping[str, object]) -> None:
    keys = set(value)
    missing = PROTECTED_ASSET_FIELDS - keys
    extra = keys - PROTECTED_ASSET_FIELDS
    if missing:
        raise InvalidAssetRevision(f"incomplete protected Asset revision: {sorted(missing)}")
    if extra:
        raise InvalidAssetRevision(f"unexpected protected Asset fields: {sorted(extra)}")
    for key in PROTECTED_ASSET_FIELDS:
        if value[key] in (None, "", [], {}):
            raise InvalidAssetRevision(f"empty protected Asset field: {key}")
    if not isinstance(value["source_metadata"], Mapping) or not isinstance(value["media_semantics"], Mapping):
        raise InvalidAssetRevision("protected metadata/semantics must remain exact mappings")


def validate_protected_alternatives(values: Sequence[Mapping[str, object]]) -> None:
    if not values:
        raise InvalidAssetRevision("at least one complete alternative is required")
    asset_id = None
    digests = set()
    for value in values:
        validate_protected_asset_revision(value)
        asset_id = value["asset_id"] if asset_id is None else asset_id
        if value["asset_id"] != asset_id:
            raise InvalidAssetRevision("alternatives must refer to one stable AssetId")
        if value["revision_digest"] in digests:
            raise InvalidAssetRevision("duplicate protected Asset revision alternative")
        digests.add(value["revision_digest"])


class SemanticDagStore:
    """SQLite oracle; row/page identity is deliberately non-semantic."""

    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS receipts(
                    tx_id TEXT PRIMARY KEY, digest TEXT NOT NULL, actor_id TEXT NOT NULL,
                    actor_seq INTEGER NOT NULL, final_status TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS receipts_actor_seq ON receipts(actor_id, actor_seq);
                CREATE TABLE IF NOT EXISTS tx_payloads(
                    tx_id TEXT PRIMARY KEY REFERENCES receipts(tx_id) ON DELETE CASCADE,
                    schema_version INTEGER NOT NULL, permission_epoch INTEGER NOT NULL,
                    semantic_class TEXT NOT NULL, body_json TEXT NOT NULL, parents_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pending(
                    tx_id TEXT PRIMARY KEY, digest TEXT NOT NULL, envelope_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS checkpoint(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), snapshot_digest TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL, causal_floor_json TEXT NOT NULL);
            """)
            if self.db.execute("SELECT 1 FROM checkpoint WHERE singleton=1").fetchone() is None:
                empty = canonical_json({})
                self.db.execute("INSERT INTO checkpoint VALUES(1,?,?,?)", (sha256_text(empty), empty, empty))

    def close(self) -> None:
        self.db.close()

    def checkpoint_floor(self) -> dict[str, int]:
        raw = self.db.execute("SELECT causal_floor_json FROM checkpoint WHERE singleton=1").fetchone()[0]
        return {str(k): int(v) for k, v in json.loads(raw).items()}

    def _parent_is_satisfied(self, parent_id: str) -> bool:
        if self.db.execute("SELECT 1 FROM receipts WHERE tx_id=?", (parent_id,)).fetchone():
            return True
        try:
            actor, raw_seq = parent_id.rsplit(":", 1)
            seq = int(raw_seq)
        except (ValueError, TypeError):
            return False
        return seq <= self.checkpoint_floor().get(actor, 0)

    def append(self, envelope: TxEnvelope, *, final_status: str = "applied", crash_stage: str | None = None) -> str:
        if envelope.tx_id != tx_id(envelope.actor_id, envelope.actor_seq):
            raise CollaborationStoreError("transaction identity must bind actor_id + actor_seq")
        if envelope.semantic_class not in COMPACTABLE_CLASSES | RETAINED_CLASSES:
            raise CollaborationStoreError("unknown semantic retention class")
        if final_status not in {"applied", "held", "quarantined", "rejected"}:
            raise CollaborationStoreError("unknown final status")
        previous = self.db.execute("SELECT digest FROM receipts WHERE tx_id=?", (envelope.tx_id,)).fetchone()
        if previous:
            if previous[0] != envelope.digest:
                raise TransactionCollision(envelope.tx_id)
            return "duplicate"
        missing = [p for p in envelope.parents if not self._parent_is_satisfied(p)]
        if missing:
            with self.db:
                prior = self.db.execute("SELECT digest FROM pending WHERE tx_id=?", (envelope.tx_id,)).fetchone()
                if prior and prior[0] != envelope.digest:
                    raise TransactionCollision(envelope.tx_id)
                self.db.execute("INSERT OR REPLACE INTO pending VALUES(?,?,?)",
                                (envelope.tx_id, envelope.digest, envelope.canonical_content()))
            raise MissingAncestor(",".join(missing))
        with self.db:
            self.db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",
                            (envelope.tx_id, envelope.digest, envelope.actor_id, envelope.actor_seq, final_status))
            if crash_stage == "after_receipt":
                raise SimulatedCrash(crash_stage)
            self.db.execute("INSERT INTO tx_payloads VALUES(?,?,?,?,?,?)",
                            (envelope.tx_id, envelope.schema_version, envelope.permission_epoch,
                             envelope.semantic_class, canonical_json(envelope.body), canonical_json(list(envelope.parents))))
            self.db.execute("DELETE FROM pending WHERE tx_id=?", (envelope.tx_id,))
            if crash_stage in {"after_payload", "before_commit"}:
                raise SimulatedCrash(crash_stage)
        return "applied"

    def retry_pending(self) -> tuple[str, ...]:
        applied = []
        progress = True
        while progress:
            progress = False
            for (raw,) in self.db.execute("SELECT envelope_json FROM pending ORDER BY tx_id").fetchall():
                v = json.loads(raw)
                env = TxEnvelope(v["tx_id"], v["actor_id"], int(v["actor_seq"]), tuple(v["parents"]),
                                 int(v["schema_version"]), int(v["permission_epoch"]), v["semantic_class"], v["body"])
                if all(self._parent_is_satisfied(p) for p in env.parents):
                    self.append(env)
                    applied.append(env.tx_id)
                    progress = True
        return tuple(applied)

    def receipt_count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])

    def payload_count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM tx_payloads").fetchone()[0])

    def retained_payload_ids(self) -> tuple[str, ...]:
        return tuple(x[0] for x in self.db.execute("SELECT tx_id FROM tx_payloads ORDER BY tx_id").fetchall())

    def create_checkpoint_and_compact(self, *, snapshot: Mapping[str, object], stable_frontier: Mapping[str, int]) -> tuple[str, ...]:
        """Use only an explicit causal-stability frontier; never infer from time/relay/latest."""
        current = self.checkpoint_floor()
        for actor, seq in stable_frontier.items():
            if int(seq) < current.get(actor, 0):
                raise CollaborationStoreError("causal frontier cannot move backwards")
            seen = self.db.execute("SELECT COALESCE(MAX(actor_seq),0) FROM receipts WHERE actor_id=?", (actor,)).fetchone()[0]
            if int(seq) > int(seen):
                raise CollaborationStoreError("frontier cannot cover unseen transaction")
        snapshot_json = canonical_json(snapshot)
        retired = []
        with self.db:
            rows = self.db.execute("""SELECT p.tx_id,r.actor_id,r.actor_seq,p.semantic_class,r.final_status
                                      FROM tx_payloads p JOIN receipts r USING(tx_id) ORDER BY p.tx_id""").fetchall()
            for tx, actor, seq, semantic_class, status in rows:
                floor = int(stable_frontier.get(actor, current.get(actor, 0)))
                if semantic_class in COMPACTABLE_CLASSES and status == "applied" and int(seq) <= floor:
                    self.db.execute("DELETE FROM tx_payloads WHERE tx_id=?", (tx,))
                    retired.append(tx)
            merged_floor = dict(current)
            merged_floor.update({a: int(s) for a, s in stable_frontier.items()})
            self.db.execute("UPDATE checkpoint SET snapshot_digest=?,snapshot_json=?,causal_floor_json=? WHERE singleton=1",
                            (sha256_text(snapshot_json), snapshot_json, canonical_json(merged_floor)))
        return tuple(retired)

    def payload_bytes(self) -> int:
        return int(self.db.execute("SELECT COALESCE(SUM(length(body_json)+length(parents_json)+length(tx_id)+32),0) FROM tx_payloads").fetchone()[0])

    def receipt_bytes(self) -> int:
        return int(self.db.execute("SELECT COALESCE(SUM(length(tx_id)+length(digest)+length(actor_id)+24),0) FROM receipts").fetchone()[0])

    def checkpoint_bytes(self) -> int:
        return int(self.db.execute("SELECT length(snapshot_json)+length(causal_floor_json)+length(snapshot_digest) FROM checkpoint").fetchone()[0])


def fixture_envelope(cr_id: str, expected: Sequence[str], seq: int) -> TxEnvelope:
    if cr_id == "CR-027":
        semantic_class = "protected_alternative"
    elif cr_id in {"CR-003", "CR-010", "CR-017", "CR-024"}:
        semantic_class = "tombstone"
    elif cr_id in {"CR-002", "CR-004", "CR-006", "CR-009", "CR-013", "CR-014", "CR-016", "CR-025"}:
        semantic_class = "conflict"
    elif cr_id in {"CR-021", "CR-023", "CR-026"}:
        semantic_class = "quarantine"
    else:
        semantic_class = "ordinary"
    return TxEnvelope(tx_id("fixture", seq), "fixture", seq,
                      (() if seq == 1 else (tx_id("fixture", seq - 1),)), 1, 7,
                      semantic_class, {"fixture_id": cr_id, "expected_invariants": list(expected)})


def benchmark(edit_count: int = 1024) -> dict[str, float | int]:
    if edit_count < 16:
        raise ValueError("edit_count must be >= 16")
    with tempfile.TemporaryDirectory() as tmp:
        store = SemanticDagStore(Path(tmp) / "collab.sqlite3")
        start = time.perf_counter()
        parent: tuple[str, ...] = ()
        for seq in range(1, edit_count + 1):
            semantic_class = "conflict" if seq % 97 == 0 else "ordinary"
            env = TxEnvelope(tx_id("bench", seq), "bench", seq, parent, 1, 1, semantic_class,
                             {"locus": f"thing:{seq % 31}:property:x", "value": seq, "pad": "x" * 48})
            store.append(env, final_status="held" if semantic_class == "conflict" else "applied")
            parent = (env.tx_id,)
        ingest_ms = (time.perf_counter() - start) * 1000.0
        before, receipts = store.payload_bytes(), store.receipt_bytes()
        start = time.perf_counter()
        retired = store.create_checkpoint_and_compact(
            snapshot={"project_revision": "bench", "applied_edits": edit_count},
            stable_frontier={"bench": edit_count})
        compact_ms = (time.perf_counter() - start) * 1000.0
        result = {"edit_count": edit_count, "ingest_ms": round(ingest_ms, 3),
                  "compaction_ms": round(compact_ms, 3), "pre_payload_bytes": before,
                  "post_payload_bytes": store.payload_bytes(), "receipt_bytes": receipts,
                  "checkpoint_bytes": store.checkpoint_bytes(), "retired_payload_count": len(retired),
                  "retained_payload_count": store.payload_count()}
        store.close()
        return result


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
