"""SMX-043 production collaboration history, merge, local store and relay boundary.

Collaboration is a separate history/consistency plane above the canonical document.
It transports complete validated canonical revisions; SQLite/relay/presence identities
never become durable SplashMX semantic identity.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
import hmac
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterable, Mapping, Sequence

from splashmx.canonical.core import CanonicalDocument, ProjectRevisionId, SemanticError
from splashmx.canonical.serialization import (
    CanonicalProjectRevision,
    SerializationError,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
    serialize_project,
    validate_project_revision,
)

COLLABORATION_FORMAT = "splashmx.collaboration-transaction/1"
STORE_SCHEMA = "splashmx.collaboration-store/1"
STORE_FORMAT_VERSION = 1
HISTORY_VERSION = 1
MAX_TRANSACTION_BYTES = 16 * 1024 * 1024
MAX_PROJECT_BLOB_BYTES = 64 * 1024 * 1024
MAX_PARENTS = 128
MAX_RESOLUTIONS = 128
MAX_CONFLICTS_PER_TRANSACTION = 2048
COMPACTABLE_RETENTION = frozenset({"ordinary", "resolution"})
MATERIALIZED_PARENT_STATUSES = frozenset({"applied", "applied-conflict", "resolution"})
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_TX_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]{0,63}):([1-9][0-9]{0,18})")
_MISSING = object()
FaultHook = Callable[[str], None]


class CollaborationError(RuntimeError):
    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


@dataclass(frozen=True, order=True)
class TransactionId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _TX_RE.fullmatch(self.value) is None:
            raise CollaborationError("collaboration.invalid_transaction_id", "TransactionId must be actor:positive-sequence")

    @property
    def actor_id(self) -> str:
        return self.value.rsplit(":", 1)[0]

    @property
    def actor_seq(self) -> int:
        return int(self.value.rsplit(":", 1)[1])

    def __str__(self) -> str:
        return self.value


def transaction_id(actor_id: str, actor_seq: int) -> TransactionId:
    if not isinstance(actor_id, str) or _ID_RE.fullmatch(actor_id) is None:
        raise CollaborationError("collaboration.invalid_actor", "actor_id must be a bounded path-independent token")
    if not isinstance(actor_seq, int) or isinstance(actor_seq, bool) or not 1 <= actor_seq <= 2**63 - 1:
        raise CollaborationError("collaboration.invalid_actor_sequence", "actor_seq must be a positive int64")
    return TransactionId(f"{actor_id}:{actor_seq}")


@dataclass(frozen=True)
class CollaborationTransaction:
    tx_id: TransactionId
    actor_id: str
    actor_seq: int
    parents: tuple[TransactionId, ...]
    history_version: int
    permission_epoch: int
    base_project: bytes
    candidate_project: bytes
    resolves: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestResult:
    tx_id: TransactionId
    status: str
    head_revision_id: str
    conflict_ids: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    tx_id: TransactionId
    locus: str
    kind: str
    alternative_a: CanonicalProjectRevision
    alternative_b: CanonicalProjectRevision
    resolved_by: TransactionId | None


@dataclass(frozen=True)
class PresenceRecord:
    principal_id: str
    cursor: str | None
    selections: tuple[str, ...]


@dataclass(frozen=True)
class RelayPacket:
    principal_id: str
    transaction_bytes: bytes
    mac_hex: str


class RelayAuthenticator:
    """Authenticated relay envelope. Authentication never grants edit authority."""

    _DOMAIN = b"SplashMX collaboration relay v1\x00"

    def __init__(self, principal_keys: Mapping[str, bytes]):
        self._keys: dict[str, bytes] = {}
        for principal, key in principal_keys.items():
            if not isinstance(principal, str) or _ID_RE.fullmatch(principal) is None:
                raise CollaborationError("collaboration.invalid_principal", "invalid relay principal")
            if not isinstance(key, bytes) or len(key) < 16:
                raise CollaborationError("collaboration.invalid_relay_key", "relay HMAC key must be at least 128 bits")
            self._keys[principal] = bytes(key)

    def sign(self, principal_id: str, transaction: CollaborationTransaction | bytes) -> RelayPacket:
        raw = encode_transaction(transaction) if isinstance(transaction, CollaborationTransaction) else bytes(transaction)
        key = self._keys.get(principal_id)
        if key is None:
            raise CollaborationError("collaboration.unknown_principal", "principal has no relay credential")
        mac = hmac.new(key, self._DOMAIN + principal_id.encode() + b"\x00" + raw, "sha256").hexdigest()
        return RelayPacket(principal_id, raw, mac)

    def verify(self, packet: RelayPacket) -> CollaborationTransaction:
        key = self._keys.get(packet.principal_id)
        if key is None:
            raise CollaborationError("collaboration.unauthenticated_relay", "unknown relay principal")
        expected = hmac.new(
            key, self._DOMAIN + packet.principal_id.encode() + b"\x00" + bytes(packet.transaction_bytes), "sha256"
        ).hexdigest()
        if not hmac.compare_digest(expected, packet.mac_hex):
            raise CollaborationError("collaboration.unauthenticated_relay", "relay authentication failed")
        tx = decode_transaction(packet.transaction_bytes)
        if tx.actor_id != packet.principal_id:
            raise CollaborationError("collaboration.principal_mismatch", "authenticated principal does not match transaction actor")
        return tx


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def pack_project(project: CanonicalProjectRevision) -> bytes:
    serialized = serialize_project(project)
    encoded = encode_canonical_cbor({
        "root_manifest": serialized.root_manifest,
        "shards": [{"key": k, "payload": serialized.shards[k]} for k in sorted(serialized.shards)],
    })
    if len(encoded) > MAX_PROJECT_BLOB_BYTES:
        raise CollaborationError("collaboration.project_too_large", "project snapshot exceeds collaboration bound")
    return encoded


def unpack_project(data: bytes) -> CanonicalProjectRevision:
    if not isinstance(data, bytes) or len(data) > MAX_PROJECT_BLOB_BYTES:
        raise CollaborationError("collaboration.project_too_large", "project snapshot exceeds collaboration bound")
    try:
        row = decode_canonical_cbor(data)
        if not isinstance(row, dict) or set(row) != {"root_manifest", "shards"}:
            raise CollaborationError("collaboration.invalid_project_snapshot", "invalid project snapshot envelope")
        shards: dict[str, bytes] = {}
        if not isinstance(row["root_manifest"], bytes) or not isinstance(row["shards"], list):
            raise CollaborationError("collaboration.invalid_project_snapshot", "invalid project snapshot types")
        for item in row["shards"]:
            if not isinstance(item, dict) or set(item) != {"key", "payload"}:
                raise CollaborationError("collaboration.invalid_project_snapshot", "invalid project shard envelope")
            key, payload = item["key"], item["payload"]
            if not isinstance(key, str) or not isinstance(payload, bytes) or key in shards:
                raise CollaborationError("collaboration.invalid_project_snapshot", "duplicate/invalid project shard")
            shards[key] = payload
        return deserialize_project(SerializedProjectRevision(row["root_manifest"], shards))
    except CollaborationError:
        raise
    except SerializationError as exc:
        raise CollaborationError("collaboration.invalid_project_snapshot", "project snapshot failed canonical validation", cause=exc) from exc


def create_transaction(*, actor_id: str, actor_seq: int, parents: Sequence[TransactionId | str], permission_epoch: int,
                       base: CanonicalProjectRevision, candidate: CanonicalProjectRevision,
                       resolves: Sequence[str] = (), history_version: int = HISTORY_VERSION) -> CollaborationTransaction:
    txid = transaction_id(actor_id, actor_seq)
    parent_ids = tuple(p if isinstance(p, TransactionId) else TransactionId(str(p)) for p in parents)
    resolve_ids = tuple(str(x) for x in resolves)
    if len(parent_ids) > MAX_PARENTS or len(set(parent_ids)) != len(parent_ids) or txid in parent_ids:
        raise CollaborationError("collaboration.invalid_parents", "invalid, duplicate, self-referential or excessive parent set")
    if len(resolve_ids) > MAX_RESOLUTIONS or len(set(resolve_ids)) != len(resolve_ids):
        raise CollaborationError("collaboration.invalid_resolution_set", "invalid or excessive resolution set")
    if not isinstance(permission_epoch, int) or isinstance(permission_epoch, bool) or permission_epoch < 0:
        raise CollaborationError("collaboration.invalid_permission_epoch", "permission_epoch must be non-negative")
    if not isinstance(history_version, int) or isinstance(history_version, bool) or history_version < 0:
        raise CollaborationError("collaboration.invalid_history_version", "history_version must be non-negative")
    validate_project_revision(base)
    validate_project_revision(candidate)
    if base.document.project_id != candidate.document.project_id:
        raise CollaborationError("collaboration.project_mismatch", "base and candidate belong to different projects")
    if base.document.project_revision_id == candidate.document.project_revision_id:
        raise CollaborationError("collaboration.duplicate_revision", "candidate must publish a new ProjectRevisionId")
    tx = CollaborationTransaction(txid, actor_id, actor_seq, parent_ids, history_version, permission_epoch,
                                  pack_project(base), pack_project(candidate), resolve_ids)
    encode_transaction(tx)
    return tx


def encode_transaction(transaction: CollaborationTransaction | bytes) -> bytes:
    if isinstance(transaction, bytes):
        raw = bytes(transaction)
    else:
        if transaction.tx_id != transaction_id(transaction.actor_id, transaction.actor_seq):
            raise CollaborationError("collaboration.transaction_identity_mismatch", "TransactionId must bind actor + sequence")
        if len(transaction.parents) > MAX_PARENTS or len(set(transaction.parents)) != len(transaction.parents):
            raise CollaborationError("collaboration.invalid_parents", "invalid transaction parents")
        raw = encode_canonical_cbor({
            "format": COLLABORATION_FORMAT,
            "tx_id": str(transaction.tx_id),
            "actor_id": transaction.actor_id,
            "actor_seq": transaction.actor_seq,
            "parents": [str(x) for x in transaction.parents],
            "history_version": transaction.history_version,
            "permission_epoch": transaction.permission_epoch,
            "base_project": transaction.base_project,
            "candidate_project": transaction.candidate_project,
            "resolves": list(transaction.resolves),
        })
    if len(raw) > MAX_TRANSACTION_BYTES:
        raise CollaborationError("collaboration.transaction_too_large", "transaction exceeds configured byte bound")
    return raw


def decode_transaction(data: bytes) -> CollaborationTransaction:
    raw = encode_transaction(bytes(data))
    try:
        row = decode_canonical_cbor(raw)
    except SerializationError as exc:
        raise CollaborationError("collaboration.invalid_transaction", "invalid transaction CBOR", cause=exc) from exc
    keys = {"format", "tx_id", "actor_id", "actor_seq", "parents", "history_version", "permission_epoch",
            "base_project", "candidate_project", "resolves"}
    if not isinstance(row, dict) or set(row) != keys or row["format"] != COLLABORATION_FORMAT:
        raise CollaborationError("collaboration.invalid_transaction", "invalid transaction profile/envelope")
    txid = TransactionId(row["tx_id"])
    if txid != transaction_id(row["actor_id"], row["actor_seq"]):
        raise CollaborationError("collaboration.transaction_identity_mismatch", "TransactionId must bind actor + sequence")
    if not isinstance(row["parents"], list) or len(row["parents"]) > MAX_PARENTS:
        raise CollaborationError("collaboration.invalid_parents", "invalid parent set")
    parents = tuple(TransactionId(x) for x in row["parents"])
    if len(set(parents)) != len(parents) or txid in parents:
        raise CollaborationError("collaboration.invalid_parents", "duplicate/self parent")
    if not isinstance(row["resolves"], list) or len(row["resolves"]) > MAX_RESOLUTIONS or any(not isinstance(x, str) for x in row["resolves"]):
        raise CollaborationError("collaboration.invalid_resolution_set", "invalid resolution set")
    resolves = tuple(row["resolves"])
    if len(set(resolves)) != len(resolves):
        raise CollaborationError("collaboration.invalid_resolution_set", "duplicate conflict resolution")
    for name in ("history_version", "permission_epoch"):
        value = row[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CollaborationError(f"collaboration.invalid_{name}", f"{name} must be non-negative")
    if not isinstance(row["base_project"], bytes) or not isinstance(row["candidate_project"], bytes):
        raise CollaborationError("collaboration.invalid_transaction", "project snapshots must be bytes")
    return CollaborationTransaction(txid, row["actor_id"], row["actor_seq"], parents, row["history_version"],
                                    row["permission_epoch"], row["base_project"], row["candidate_project"], resolves)


@dataclass(frozen=True)
class _ConflictSpec:
    locus: str
    kind: str


def _is_tombstoned(value: object) -> bool:
    return value is not _MISSING and bool(getattr(value, "tombstoned", False))


def _merge_map(base: Mapping, local: Mapping, incoming: Mapping, *, prefix: str, kind: str, remove_wins: bool = False):
    out, conflicts = {}, []
    for key in sorted(set(base) | set(local) | set(incoming), key=str):
        b, l, i = base.get(key, _MISSING), local.get(key, _MISSING), incoming.get(key, _MISSING)
        conflict = None
        if l == i:
            chosen = l
        elif l == b:
            chosen = i
        elif i == b:
            chosen = l
        elif remove_wins and (_is_tombstoned(l) or _is_tombstoned(i)):
            chosen = l if _is_tombstoned(l) else i
        else:
            chosen = l
            conflict = _ConflictSpec(f"{prefix}:{key}", kind)
        if chosen is not _MISSING:
            out[key] = deepcopy(chosen)
        if conflict:
            conflicts.append(conflict)
    return out, conflicts


def _merge_unloaded(base: set, local: set, incoming: set):
    out, conflicts = set(), []
    for key in sorted(base | local | incoming, key=str):
        b, l, i = key in base, key in local, key in incoming
        if l == i:
            chosen = l
        elif l == b:
            chosen = i
        elif i == b:
            chosen = l
        else:
            chosen = l
            conflicts.append(_ConflictSpec(f"known-unloaded:{key}", "known-unloaded"))
        if chosen:
            out.add(key)
    return out, conflicts


def _enforce_remove_wins(document: CanonicalDocument) -> None:
    tombstoned = {k for k, v in document.things.items() if v.tombstoned}
    for key, row in list(document.connections.items()):
        if not row.tombstoned and (row.source.thing_id in tombstoned or row.target.thing_id in tombstoned):
            document.connections[key] = replace(row, tombstoned=True)
    for key, row in list(document.relationships.items()):
        if not row.tombstoned and (row.source in tombstoned or row.target in tombstoned):
            document.relationships[key] = replace(row, tombstoned=True)


def merge_projects(*, base: CanonicalProjectRevision, local: CanonicalProjectRevision,
                   incoming: CanonicalProjectRevision, transaction_digest: str):
    if len({base.document.project_id, local.document.project_id, incoming.document.project_id}) != 1:
        raise CollaborationError("collaboration.project_mismatch", "three-way merge requires one ProjectId")
    merged = deepcopy(local.document)
    conflicts: list[_ConflictSpec] = []
    for attr, prefix, kind, remove in (
        ("things", "thing", "thing", True),
        ("relationships", "relationship", "relationship", True),
        ("connections", "connection", "connection", True),
        ("definitions", "definition", "definition", False),
        ("instances", "instance", "instance", False),
    ):
        value, rows = _merge_map(getattr(base.document, attr), getattr(local.document, attr), getattr(incoming.document, attr),
                                 prefix=prefix, kind=kind, remove_wins=remove)
        setattr(merged, attr, value)
        conflicts.extend(rows)
    merged.known_unloaded_things, rows = _merge_unloaded(base.document.known_unloaded_things,
                                                         local.document.known_unloaded_things,
                                                         incoming.document.known_unloaded_things)
    conflicts.extend(rows)
    assets, rows = _merge_map(base.assets, local.assets, incoming.assets, prefix="asset", kind="protected-asset")
    conflicts.extend(rows)
    _enforce_remove_wins(merged)
    seed = f"{local.document.project_revision_id}\0{incoming.document.project_revision_id}\0{transaction_digest}".encode()
    merged.project_revision_id = ProjectRevisionId("collab-" + sha256(seed).hexdigest())
    try:
        result = CanonicalProjectRevision(merged, assets)
        validate_project_revision(result)
    except (SemanticError, SerializationError) as exc:
        raise CollaborationError("collaboration.semantic_invalid", "merged state violates canonical document semantics", cause=exc) from exc
    if len(conflicts) > MAX_CONFLICTS_PER_TRANSACTION:
        raise CollaborationError("collaboration.conflict_limit", "too many explicit conflicts in one transaction")
    return result, tuple(conflicts)


def _conflict_id(spec: _ConflictSpec, a: bytes, b: bytes) -> str:
    seed = encode_canonical_cbor({"locus": spec.locus, "kind": spec.kind, "alternatives": sorted((_digest(a), _digest(b)))})
    return "conflict-" + sha256(seed).hexdigest()


def _has_new_tombstone(base: CanonicalProjectRevision, candidate: CanonicalProjectRevision) -> bool:
    for attr in ("things", "relationships", "connections"):
        before, after = getattr(base.document, attr), getattr(candidate.document, attr)
        if any(getattr(v, "tombstoned", False) and not getattr(before.get(k), "tombstoned", False) for k, v in after.items()):
            return True
    return False


class SQLiteCollaborationStore:
    """SQLite WAL/FULL local-first semantic transaction DAG and validated checkpoint store."""

    def __init__(self, path: str | Path, initial_project: CanonicalProjectRevision):
        validate_project_revision(initial_project)
        self.path = str(path)
        self._presence: dict[str, PresenceRecord] = {}
        self._db = sqlite3.connect(self.path, isolation_level=None)
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._ensure_schema(initial_project)

    def close(self) -> None:
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @staticmethod
    def _hook(hook: FaultHook | None, stage: str) -> None:
        if hook:
            hook(stage)

    def _ensure_schema(self, initial: CanonicalProjectRevision) -> None:
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(revision_id TEXT PRIMARY KEY,project_blob BLOB NOT NULL,project_digest TEXT NOT NULL,origin_tx TEXT NULL);
        CREATE TABLE IF NOT EXISTS head(singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision_id TEXT NOT NULL,head_tx_id TEXT NULL);
        CREATE TABLE IF NOT EXISTS receipts(tx_id TEXT PRIMARY KEY,digest TEXT NOT NULL,actor_id TEXT NOT NULL,actor_seq INTEGER NOT NULL,status TEXT NOT NULL,retention_class TEXT NOT NULL,base_revision_id TEXT NOT NULL,candidate_revision_id TEXT NOT NULL,UNIQUE(actor_id,actor_seq));
        CREATE TABLE IF NOT EXISTS payloads(tx_id TEXT PRIMARY KEY,transaction_bytes BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS parents(tx_id TEXT NOT NULL,parent_tx_id TEXT NOT NULL,PRIMARY KEY(tx_id,parent_tx_id));
        CREATE TABLE IF NOT EXISTS pending(tx_id TEXT PRIMARY KEY,digest TEXT NOT NULL,actor_id TEXT NOT NULL,actor_seq INTEGER NOT NULL,transaction_bytes BLOB NOT NULL,missing BLOB NOT NULL,UNIQUE(actor_id,actor_seq));
        CREATE TABLE IF NOT EXISTS conflicts(conflict_id TEXT PRIMARY KEY,tx_id TEXT NOT NULL,locus TEXT NOT NULL,kind TEXT NOT NULL,alternative_a BLOB NOT NULL,alternative_b BLOB NOT NULL,resolved_by TEXT NULL);
        CREATE TABLE IF NOT EXISTS applied_states(tx_id TEXT PRIMARY KEY,before_blob BLOB NOT NULL,after_blob BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS checkpoint(singleton INTEGER PRIMARY KEY CHECK(singleton=1),project_blob BLOB NOT NULL,causal_floor BLOB NOT NULL);
        """)
        self._db.execute("INSERT OR IGNORE INTO metadata VALUES('store_schema',?)", (STORE_SCHEMA,))
        self._db.execute("INSERT OR IGNORE INTO metadata VALUES('store_format_version',?)", (str(STORE_FORMAT_VERSION),))
        self._db.execute("INSERT OR IGNORE INTO metadata VALUES('permission_epoch','1')")
        meta = dict(self._db.execute("SELECT key,value FROM metadata"))
        if meta.get("store_schema") != STORE_SCHEMA or int(meta.get("store_format_version", "-1")) != STORE_FORMAT_VERSION:
            raise CollaborationError("collaboration.unsupported_store", "unsupported collaboration store format")
        if self._db.execute("SELECT 1 FROM head WHERE singleton=1").fetchone() is None:
            blob = pack_project(initial)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._insert_revision(initial, blob, None)
                self._db.execute("INSERT INTO head VALUES(1,?,NULL)", (str(initial.document.project_revision_id),))
                self._db.execute("INSERT INTO checkpoint VALUES(1,?,?)", (sqlite3.Binary(blob), sqlite3.Binary(encode_canonical_cbor({}))))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        elif self.head_project().document.project_id != initial.document.project_id:
            raise CollaborationError("collaboration.project_mismatch", "store belongs to another ProjectId")

    @property
    def permission_epoch(self) -> int:
        return int(self._db.execute("SELECT value FROM metadata WHERE key='permission_epoch'").fetchone()[0])

    def advance_permission_epoch(self, new_epoch: int) -> None:
        if not isinstance(new_epoch, int) or isinstance(new_epoch, bool) or new_epoch <= self.permission_epoch:
            raise CollaborationError("collaboration.permission_epoch_regression", "permission epoch must increase")
        self._db.execute("UPDATE metadata SET value=? WHERE key='permission_epoch'", (str(new_epoch),))

    def _head_row(self):
        row = self._db.execute("SELECT revision_id,head_tx_id FROM head WHERE singleton=1").fetchone()
        if row is None:
            raise CollaborationError("collaboration.corrupt_store", "missing collaboration head")
        return str(row[0]), row[1]

    def head_project(self) -> CanonicalProjectRevision:
        revision_id, _ = self._head_row()
        row = self._db.execute("SELECT project_blob FROM revisions WHERE revision_id=?", (revision_id,)).fetchone()
        if row is None:
            raise CollaborationError("collaboration.corrupt_store", "head revision missing")
        project = unpack_project(bytes(row[0]))
        if str(project.document.project_revision_id) != revision_id:
            raise CollaborationError("collaboration.corrupt_store", "head revision identity mismatch")
        return project

    def _insert_revision(self, project: CanonicalProjectRevision, blob: bytes, origin_tx: str | None) -> None:
        rid, digest = str(project.document.project_revision_id), _digest(blob)
        prior = self._db.execute("SELECT project_digest,project_blob FROM revisions WHERE revision_id=?", (rid,)).fetchone()
        if prior:
            if prior[0] != digest or bytes(prior[1]) != blob:
                raise CollaborationError("collaboration.revision_collision", "same ProjectRevisionId names different bytes")
            return
        self._db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (rid, sqlite3.Binary(blob), digest, origin_tx))

    def _known_revision(self, project: CanonicalProjectRevision, blob: bytes) -> bool:
        row = self._db.execute("SELECT project_digest,project_blob FROM revisions WHERE revision_id=?", (str(project.document.project_revision_id),)).fetchone()
        if row is None:
            return False
        if row[0] != _digest(blob) or bytes(row[1]) != blob:
            raise CollaborationError("collaboration.revision_collision", "same ProjectRevisionId names different bytes")
        return True

    def _floor(self) -> dict[str, int]:
        row = self._db.execute("SELECT causal_floor FROM checkpoint WHERE singleton=1").fetchone()
        value = decode_canonical_cbor(bytes(row[0]))
        return {str(k): int(v) for k, v in value.items()}

    def _parent_status(self, parent: TransactionId) -> str | None:
        row = self._db.execute("SELECT status FROM receipts WHERE tx_id=?", (str(parent),)).fetchone()
        if row:
            return str(row[0])
        return "checkpointed" if parent.actor_seq <= self._floor().get(parent.actor_id, 0) else None

    def history_status(self, tx_id: TransactionId | str) -> str | None:
        row = self._db.execute("SELECT status FROM receipts WHERE tx_id=?", (str(tx_id),)).fetchone()
        return None if row is None else str(row[0])

    def recover_transaction(self, tx_id: TransactionId | str) -> bytes | None:
        row = self._db.execute("SELECT transaction_bytes FROM payloads WHERE tx_id=?", (str(tx_id),)).fetchone()
        if row is None:
            row = self._db.execute("SELECT transaction_bytes FROM pending WHERE tx_id=?", (str(tx_id),)).fetchone()
        return None if row is None else bytes(row[0])

    def pending_ids(self):
        return tuple(TransactionId(x[0]) for x in self._db.execute("SELECT tx_id FROM pending ORDER BY tx_id"))

    def _collision_or_duplicate(self, tx: CollaborationTransaction, digest: str) -> IngestResult | None:
        row = self._db.execute("SELECT digest,status FROM receipts WHERE tx_id=?", (str(tx.tx_id),)).fetchone()
        if row:
            if row[0] != digest:
                raise CollaborationError("collaboration.transaction_collision", "same TransactionId names different content")
            return IngestResult(tx.tx_id, "duplicate", str(self.head_project().document.project_revision_id), reason=str(row[1]))
        row = self._db.execute("SELECT digest FROM pending WHERE tx_id=?", (str(tx.tx_id),)).fetchone()
        if row and row[0] != digest:
            raise CollaborationError("collaboration.transaction_collision", "same pending TransactionId names different content")
        return None

    def _pending(self, tx: CollaborationTransaction, raw: bytes, digest: str, missing: Sequence[TransactionId]):
        self._db.execute("INSERT OR REPLACE INTO pending VALUES(?,?,?,?,?,?)",
                         (str(tx.tx_id), digest, tx.actor_id, tx.actor_seq, sqlite3.Binary(raw), sqlite3.Binary(encode_canonical_cbor([str(x) for x in missing]))))
        return IngestResult(tx.tx_id, "pending", str(self.head_project().document.project_revision_id), reason="missing-ancestor")

    def _nonmaterialized(self, tx: CollaborationTransaction, raw: bytes, digest: str, *, status: str, reason: str,
                         retention: str = "quarantine", conflict: _ConflictSpec | None = None, a: bytes | None = None, b: bytes | None = None):
        base, candidate = unpack_project(tx.base_project), unpack_project(tx.candidate_project)
        ids: list[str] = []
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                             (str(tx.tx_id), digest, tx.actor_id, tx.actor_seq, status, retention,
                              str(base.document.project_revision_id), str(candidate.document.project_revision_id)))
            self._db.execute("INSERT INTO payloads VALUES(?,?)", (str(tx.tx_id), sqlite3.Binary(raw)))
            for parent in tx.parents:
                self._db.execute("INSERT INTO parents VALUES(?,?)", (str(tx.tx_id), str(parent)))
            if conflict and a is not None and b is not None:
                cid = _conflict_id(conflict, a, b)
                x, y = sorted((a, b), key=_digest)
                self._db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?,NULL)",
                                 (cid, str(tx.tx_id), conflict.locus, conflict.kind, sqlite3.Binary(x), sqlite3.Binary(y)))
                ids.append(cid)
            self._db.execute("DELETE FROM pending WHERE tx_id=?", (str(tx.tx_id),))
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        return IngestResult(tx.tx_id, status, str(self.head_project().document.project_revision_id), tuple(ids), reason)

    def _validate_resolutions(self, tx: CollaborationTransaction) -> None:
        for cid in tx.resolves:
            row = self._db.execute("SELECT resolved_by FROM conflicts WHERE conflict_id=?", (cid,)).fetchone()
            if row is None:
                raise CollaborationError("collaboration.unknown_conflict", f"unknown conflict {cid}")
            if row[0] is not None:
                raise CollaborationError("collaboration.conflict_already_resolved", f"conflict {cid} already resolved")

    def ingest(self, transaction: CollaborationTransaction | bytes, *, fault_hook: FaultHook | None = None) -> IngestResult:
        raw = encode_transaction(transaction) if isinstance(transaction, CollaborationTransaction) else encode_transaction(bytes(transaction))
        tx, digest = decode_transaction(raw), _digest(raw)
        duplicate = self._collision_or_duplicate(tx, digest)
        if duplicate:
            return duplicate
        missing, blocked = [], []
        for parent in tx.parents:
            status = self._parent_status(parent)
            if status is None:
                missing.append(parent)
            elif status not in MATERIALIZED_PARENT_STATUSES and status != "checkpointed":
                blocked.append(parent)
        if missing:
            return self._pending(tx, raw, digest, missing)

        base, candidate, current = unpack_project(tx.base_project), unpack_project(tx.candidate_project), self.head_project()
        if base.document.project_id != current.document.project_id or candidate.document.project_id != current.document.project_id:
            raise CollaborationError("collaboration.project_mismatch", "transaction belongs to another project")
        if base.document.project_revision_id == candidate.document.project_revision_id:
            raise CollaborationError("collaboration.duplicate_revision", "candidate must publish a new revision")
        if blocked:
            return self._nonmaterialized(tx, raw, digest, status="quarantined", reason="nonmaterialized-ancestor")
        if tx.history_version != HISTORY_VERSION:
            return self._nonmaterialized(tx, raw, digest, status="quarantined", reason="unsupported-history-version")
        if tx.permission_epoch != self.permission_epoch:
            return self._nonmaterialized(tx, raw, digest, status="quarantined", reason="permission-epoch-mismatch")
        if not self._known_revision(base, tx.base_project):
            return self._nonmaterialized(tx, raw, digest, status="quarantined", reason="unknown-base-revision")
        origin = self._db.execute("SELECT origin_tx FROM revisions WHERE revision_id=?", (str(base.document.project_revision_id),)).fetchone()[0]
        if origin is not None and TransactionId(str(origin)) not in tx.parents:
            return self._nonmaterialized(tx, raw, digest, status="quarantined", reason="base-parent-mismatch")
        self._validate_resolutions(tx)

        before_blob = pack_project(current)
        conflicts = ()
        if current.document.project_revision_id == base.document.project_revision_id:
            after = candidate
        else:
            try:
                after, conflicts = merge_projects(base=base, local=current, incoming=candidate, transaction_digest=digest)
            except CollaborationError as exc:
                if exc.code == "collaboration.semantic_invalid":
                    return self._nonmaterialized(tx, raw, digest, status="held-invalid", reason="canonical-validation-failed",
                                                 retention="conflict", conflict=_ConflictSpec("document", "document-invalid"),
                                                 a=before_blob, b=tx.candidate_project)
                raise
        after_blob = pack_project(after)
        if any(x.kind == "protected-asset" for x in conflicts):
            retention, status = "protected-alternative", "applied-conflict"
        elif conflicts:
            retention, status = "conflict", "applied-conflict"
        elif tx.resolves:
            retention, status = "resolution", "resolution"
        elif _has_new_tombstone(base, candidate):
            retention, status = "tombstone", "applied"
        else:
            retention, status = "ordinary", "applied"

        conflict_ids: list[str] = []
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._hook(fault_hook, "before_receipt")
            self._db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                             (str(tx.tx_id), digest, tx.actor_id, tx.actor_seq, status, retention,
                              str(base.document.project_revision_id), str(candidate.document.project_revision_id)))
            self._hook(fault_hook, "after_receipt")
            self._db.execute("INSERT INTO payloads VALUES(?,?)", (str(tx.tx_id), sqlite3.Binary(raw)))
            for parent in tx.parents:
                self._db.execute("INSERT INTO parents VALUES(?,?)", (str(tx.tx_id), str(parent)))
            self._hook(fault_hook, "after_payload")
            self._insert_revision(candidate, tx.candidate_project, str(tx.tx_id))
            self._insert_revision(after, after_blob, str(tx.tx_id))
            for spec in conflicts:
                cid = _conflict_id(spec, before_blob, tx.candidate_project)
                a, b = sorted((before_blob, tx.candidate_project), key=_digest)
                self._db.execute("INSERT OR IGNORE INTO conflicts VALUES(?,?,?,?,?,?,NULL)",
                                 (cid, str(tx.tx_id), spec.locus, spec.kind, sqlite3.Binary(a), sqlite3.Binary(b)))
                conflict_ids.append(cid)
            self._hook(fault_hook, "after_conflicts")
            self._db.execute("INSERT INTO applied_states VALUES(?,?,?)", (str(tx.tx_id), sqlite3.Binary(before_blob), sqlite3.Binary(after_blob)))
            self._db.execute("UPDATE head SET revision_id=?,head_tx_id=? WHERE singleton=1", (str(after.document.project_revision_id), str(tx.tx_id)))
            self._hook(fault_hook, "after_head")
            for cid in tx.resolves:
                self._db.execute("UPDATE conflicts SET resolved_by=? WHERE conflict_id=?", (str(tx.tx_id), cid))
            self._db.execute("DELETE FROM pending WHERE tx_id=?", (str(tx.tx_id),))
            self._hook(fault_hook, "before_commit")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        self._hook(fault_hook, "committed")
        return IngestResult(tx.tx_id, status, str(after.document.project_revision_id), tuple(sorted(set(conflict_ids))))

    def retry_pending(self):
        results, progress = [], True
        while progress:
            progress = False
            for (raw,) in self._db.execute("SELECT transaction_bytes FROM pending ORDER BY tx_id").fetchall():
                tx = decode_transaction(bytes(raw))
                if all(self._parent_status(p) is not None for p in tx.parents):
                    results.append(self.ingest(bytes(raw)))
                    progress = True
        return tuple(results)

    def _conflict_row(self, row) -> ConflictRecord:
        return ConflictRecord(str(row[0]), TransactionId(str(row[1])), str(row[2]), str(row[3]),
                              unpack_project(bytes(row[4])), unpack_project(bytes(row[5])),
                              None if row[6] is None else TransactionId(str(row[6])))

    def unresolved_conflicts(self):
        rows = self._db.execute("SELECT conflict_id,tx_id,locus,kind,alternative_a,alternative_b,resolved_by FROM conflicts WHERE resolved_by IS NULL ORDER BY conflict_id").fetchall()
        return tuple(self._conflict_row(row) for row in rows)

    def conflict(self, conflict_id: str):
        row = self._db.execute("SELECT conflict_id,tx_id,locus,kind,alternative_a,alternative_b,resolved_by FROM conflicts WHERE conflict_id=?", (conflict_id,)).fetchone()
        return None if row is None else self._conflict_row(row)

    def prepare_undo(self, target_tx_id: TransactionId | str, *, actor_id: str, actor_seq: int) -> CollaborationTransaction:
        target = TransactionId(str(target_tx_id))
        if self._head_row()[1] != str(target):
            raise CollaborationError("collaboration.undo_not_current", "only current leaf transaction can be undone")
        if self._db.execute("SELECT 1 FROM conflicts WHERE tx_id=? AND resolved_by IS NULL", (str(target),)).fetchone():
            raise CollaborationError("collaboration.undo_conflicted", "resolve conflicts explicitly before undo")
        row = self._db.execute("SELECT before_blob FROM applied_states WHERE tx_id=?", (str(target),)).fetchone()
        if row is None:
            raise CollaborationError("collaboration.undo_history_unavailable", "undo state was compacted/unavailable")
        current, previous = self.head_project(), unpack_project(bytes(row[0]))
        doc = deepcopy(previous.document)
        doc.project_revision_id = ProjectRevisionId("undo-" + sha256(f"{target}\0{actor_id}\0{actor_seq}".encode()).hexdigest())
        candidate = CanonicalProjectRevision(doc, deepcopy(dict(previous.assets)))
        return create_transaction(actor_id=actor_id, actor_seq=actor_seq, parents=(target,), permission_epoch=self.permission_epoch,
                                  base=current, candidate=candidate)

    def create_checkpoint_and_compact(self, stable_frontier: Mapping[str, int], *, fault_hook: FaultHook | None = None):
        floor = self._floor()
        for actor, seq in stable_frontier.items():
            if not isinstance(actor, str) or _ID_RE.fullmatch(actor) is None or not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
                raise CollaborationError("collaboration.invalid_frontier", "invalid causal frontier")
            if seq < floor.get(actor, 0):
                raise CollaborationError("collaboration.frontier_regression", "causal frontier cannot move backwards")
            seen = int(self._db.execute("SELECT COALESCE(MAX(actor_seq),0) FROM receipts WHERE actor_id=?", (actor,)).fetchone()[0])
            if seq > seen:
                raise CollaborationError("collaboration.frontier_unseen", "causal frontier cannot cover unseen work")
        new_floor = dict(floor)
        new_floor.update({a: int(s) for a, s in stable_frontier.items()})
        head_blob, head_revision = pack_project(self.head_project()), self._head_row()[0]
        retired: list[TransactionId] = []
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._hook(fault_hook, "before_checkpoint")
            rows = self._db.execute("SELECT tx_id,actor_id,actor_seq,status,retention_class,candidate_revision_id FROM receipts ORDER BY tx_id").fetchall()
            for txid, actor, seq, status, retention, candidate_revision in rows:
                if int(seq) <= new_floor.get(str(actor), floor.get(str(actor), 0)) and retention in COMPACTABLE_RETENTION and status in MATERIALIZED_PARENT_STATUSES:
                    self._db.execute("DELETE FROM payloads WHERE tx_id=?", (txid,))
                    self._db.execute("DELETE FROM applied_states WHERE tx_id=?", (txid,))
                    if candidate_revision != head_revision:
                        self._db.execute("DELETE FROM revisions WHERE revision_id=? AND origin_tx=?", (candidate_revision, txid))
                    retired.append(TransactionId(str(txid)))
            self._hook(fault_hook, "after_compaction")
            self._db.execute("UPDATE checkpoint SET project_blob=?,causal_floor=? WHERE singleton=1",
                             (sqlite3.Binary(head_blob), sqlite3.Binary(encode_canonical_cbor(new_floor))))
            self._hook(fault_hook, "before_checkpoint_commit")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        return tuple(retired)

    def ingest_relay(self, packet: RelayPacket, authenticator: RelayAuthenticator, *, fault_hook: FaultHook | None = None):
        return self.ingest(authenticator.verify(packet), fault_hook=fault_hook)

    def set_presence(self, principal_id: str, *, cursor: str | None = None, selections: Iterable[str] = ()) -> None:
        if not isinstance(principal_id, str) or _ID_RE.fullmatch(principal_id) is None:
            raise CollaborationError("collaboration.invalid_principal", "invalid presence principal")
        self._presence[principal_id] = PresenceRecord(principal_id, cursor, tuple(str(x) for x in selections))

    def clear_presence(self, principal_id: str) -> None:
        self._presence.pop(principal_id, None)

    def presence(self):
        return tuple(self._presence[k] for k in sorted(self._presence))
