"""SMX-025 production local project persistence.

The native store owns only canonical project revisions and the coherent project head.
It deliberately does not own WorldSave state, package/cache bytes, collaboration
history or cloud synchronization.  Canonical semantic validation stays in
``canonical.serialization``; this module provides the crash-consistent publication
boundary selected by SMX-022.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Callable

from splashmx.canonical.core import ProjectId, ProjectRevisionId
from splashmx.canonical.serialization import (
    DEFAULT_MIGRATIONS,
    CanonicalProjectRevision,
    MigrationRegistry,
    SerializationError,
    SerializedProjectRevision,
    deserialize_project,
    serialize_project,
)

STORE_SCHEMA = "splashmx.local-store/1"
STORE_FORMAT_VERSION = 1
COMMIT_STAGES = (
    "prepared",
    "revision_recorded",
    "shards_recorded",
    "candidate_verified",
    "head_advanced",
    "committed",
)

FaultHook = Callable[[str], None]


class StorageError(RuntimeError):
    """Typed local-persistence failure with a stable SplashMX code."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def _sqlite_failure(exc: sqlite3.Error, operation: str) -> StorageError:
    name = str(getattr(exc, "sqlite_errorname", "") or "").upper()
    message = str(exc).lower()
    if name.startswith("SQLITE_FULL") or "database or disk is full" in message:
        code = "storage.quota_exceeded"
    elif name.startswith(("SQLITE_READONLY", "SQLITE_PERM", "SQLITE_AUTH")) or "readonly" in message:
        code = "storage.permission_denied"
    elif name.startswith(("SQLITE_CORRUPT", "SQLITE_NOTADB")) or "malformed" in message or "not a database" in message:
        code = "storage.corrupt_store"
    elif name.startswith(("SQLITE_CANTOPEN", "SQLITE_BUSY", "SQLITE_LOCKED")):
        code = "storage.unavailable"
    elif name.startswith("SQLITE_IOERR"):
        code = "storage.io_failure"
    else:
        code = "storage.database_error"
    return StorageError(code, f"{operation} failed", cause=exc)


def _serialization_failure(exc: SerializationError) -> StorageError:
    if exc.code in {
        "serialization.unsupported_version",
        "serialization.unsupported_feature",
        "serialization.incompatible_profile",
    }:
        code = "storage.incompatible_revision"
    else:
        code = "storage.corrupt_store"
    return StorageError(code, "stored project revision failed canonical validation", cause=exc)


class SQLiteProjectStore:
    """Crash-consistent native/local project store.

    SQLite WAL + ``synchronous=FULL`` owns revision rows and the project head.  A
    revision is prepared and fully canonical-validated before the write transaction.
    During publication the immutable revision, all shards, verification readback and
    head update occur in one transaction.  Therefore an interruption before COMMIT
    reopens the previous head; an interruption after COMMIT reopens the new head.

    ``fault_hook`` is a deterministic test boundary.  Production callers normally
    omit it.  A hook may raise at any value in :data:`COMMIT_STAGES` to simulate an
    interrupted process at that publication boundary.
    """

    def __init__(self, path: str | Path, *, timeout: float = 5.0):
        self.path = str(path)
        try:
            self._db = sqlite3.connect(self.path, timeout=timeout, isolation_level=None)
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._ensure_schema()
        except sqlite3.Error as exc:
            try:
                self._db.close()
            except Exception:
                pass
            raise _sqlite_failure(exc, "opening local project store") from exc

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteProjectStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS revisions (
                project_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                root_manifest BLOB NOT NULL,
                root_digest TEXT NOT NULL,
                shard_count INTEGER NOT NULL,
                PRIMARY KEY (project_id, revision_id)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS shards (
                project_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                shard_key TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_digest TEXT NOT NULL,
                PRIMARY KEY (project_id, revision_id, shard_key),
                FOREIGN KEY (project_id, revision_id)
                    REFERENCES revisions(project_id, revision_id) ON DELETE CASCADE
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS heads (
                project_id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL,
                FOREIGN KEY (project_id, revision_id)
                    REFERENCES revisions(project_id, revision_id)
            )
            """
        )
        self._db.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('store_schema', ?)",
            (STORE_SCHEMA,),
        )
        self._db.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('store_format_version', ?)",
            (str(STORE_FORMAT_VERSION),),
        )
        self._assert_store_format()

    def _assert_store_format(self) -> None:
        try:
            rows = dict(self._db.execute(
                "SELECT key, value FROM metadata WHERE key IN ('store_schema','store_format_version')"
            ))
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading local-store format") from exc
        if rows.get("store_schema") != STORE_SCHEMA:
            raise StorageError("storage.unsupported_store_format", "local store schema is not supported")
        try:
            version = int(rows.get("store_format_version", "-1"))
        except (TypeError, ValueError) as exc:
            raise StorageError("storage.corrupt_store", "local store format version is malformed", cause=exc) from exc
        if version != STORE_FORMAT_VERSION:
            raise StorageError(
                "storage.unsupported_store_version",
                f"local store version {version} is not supported by version {STORE_FORMAT_VERSION}",
            )

    @staticmethod
    def _checkpoint(hook: FaultHook | None, stage: str) -> None:
        if hook is not None:
            hook(stage)

    @staticmethod
    def _candidate_ids(project: CanonicalProjectRevision) -> tuple[str, str]:
        return str(project.document.project_id), str(project.document.project_revision_id)

    def save(
        self,
        project: CanonicalProjectRevision,
        *,
        fault_hook: FaultHook | None = None,
    ) -> CanonicalProjectRevision:
        """Validate and atomically publish a current-schema canonical project revision."""
        serialized = serialize_project(project)
        return self.import_serialized(serialized, fault_hook=fault_hook)

    def import_serialized(
        self,
        serialized: SerializedProjectRevision,
        *,
        migrations: MigrationRegistry = DEFAULT_MIGRATIONS,
        fault_hook: FaultHook | None = None,
    ) -> CanonicalProjectRevision:
        """Validate/migrate inert bytes, then atomically publish their canonical result.

        Old physical schemas never become active directly.  The serialized input is
        first decoded/migrated and whole-project validated by SMX-024.  Its semantic
        result is then re-serialized using the current canonical profile before any
        store mutation begins.
        """
        try:
            candidate = deserialize_project(serialized, migrations=migrations)
            prepared = serialize_project(candidate)
        except SerializationError as exc:
            raise _serialization_failure(exc) from exc

        project_id, revision_id = self._candidate_ids(candidate)
        self._checkpoint(fault_hook, "prepared")
        self._assert_store_format()

        committed = False
        try:
            self._db.execute("BEGIN IMMEDIATE")
            existing = self._db.execute(
                "SELECT 1 FROM revisions WHERE project_id=? AND revision_id=?",
                (project_id, revision_id),
            ).fetchone()
            if existing is not None:
                prior = self._read_serialized(project_id, revision_id)
                if prior.root_manifest != prepared.root_manifest or dict(prior.shards) != dict(prepared.shards):
                    raise StorageError(
                        "storage.revision_conflict",
                        "the same ProjectRevisionId already names different canonical bytes",
                    )
            else:
                self._db.execute(
                    "INSERT INTO revisions(project_id,revision_id,root_manifest,root_digest,shard_count) VALUES (?,?,?,?,?)",
                    (
                        project_id,
                        revision_id,
                        sqlite3.Binary(prepared.root_manifest),
                        _digest(prepared.root_manifest),
                        len(prepared.shards),
                    ),
                )
            self._checkpoint(fault_hook, "revision_recorded")

            if existing is None:
                for shard_key in sorted(prepared.shards):
                    payload = bytes(prepared.shards[shard_key])
                    self._db.execute(
                        "INSERT INTO shards(project_id,revision_id,shard_key,payload,payload_digest) VALUES (?,?,?,?,?)",
                        (project_id, revision_id, shard_key, sqlite3.Binary(payload), _digest(payload)),
                    )
            self._checkpoint(fault_hook, "shards_recorded")

            verified = self._read_serialized(project_id, revision_id)
            try:
                verified_project = deserialize_project(verified)
            except SerializationError as exc:
                raise _serialization_failure(exc) from exc
            if self._candidate_ids(verified_project) != (project_id, revision_id) or verified_project != candidate:
                raise StorageError(
                    "storage.corrupt_store",
                    "transaction readback does not match the validated canonical candidate",
                )
            self._checkpoint(fault_hook, "candidate_verified")

            self._db.execute(
                "INSERT INTO heads(project_id,revision_id) VALUES (?,?) "
                "ON CONFLICT(project_id) DO UPDATE SET revision_id=excluded.revision_id",
                (project_id, revision_id),
            )
            self._checkpoint(fault_hook, "head_advanced")
            self._db.execute("COMMIT")
            committed = True
            self._checkpoint(fault_hook, "committed")
            return candidate
        except StorageError:
            if not committed and self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if not committed and self._db.in_transaction:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise _sqlite_failure(exc, "publishing project revision") from exc
        except BaseException:
            if not committed and self._db.in_transaction:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise

    def _read_serialized(self, project_id: str, revision_id: str) -> SerializedProjectRevision:
        try:
            row = self._db.execute(
                "SELECT root_manifest, root_digest, shard_count FROM revisions WHERE project_id=? AND revision_id=?",
                (project_id, revision_id),
            ).fetchone()
            if row is None:
                raise StorageError("storage.corrupt_store", "project head references a missing revision")
            root = bytes(row[0])
            if row[1] != _digest(root):
                raise StorageError("storage.corrupt_store", "stored root-manifest digest does not match its bytes")
            shard_rows = self._db.execute(
                "SELECT shard_key, payload, payload_digest FROM shards WHERE project_id=? AND revision_id=? ORDER BY shard_key",
                (project_id, revision_id),
            ).fetchall()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading project revision") from exc
        if len(shard_rows) != int(row[2]):
            raise StorageError("storage.corrupt_store", "stored revision shard count is incomplete")
        shards: dict[str, bytes] = {}
        for shard_key, raw, expected_digest in shard_rows:
            if shard_key in shards:
                raise StorageError("storage.corrupt_store", "stored revision contains a duplicate shard key")
            payload = bytes(raw)
            if expected_digest != _digest(payload):
                raise StorageError("storage.corrupt_store", f"stored shard {shard_key!r} failed digest verification")
            shards[str(shard_key)] = payload
        return SerializedProjectRevision(root, shards)

    def load(
        self,
        project_id: ProjectId | str,
        *,
        migrations: MigrationRegistry = DEFAULT_MIGRATIONS,
    ) -> CanonicalProjectRevision:
        """Return a fully validated head without mutating any caller-owned active state."""
        self._assert_store_format()
        project_text = str(project_id)
        try:
            row = self._db.execute(
                "SELECT revision_id FROM heads WHERE project_id=?",
                (project_text,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading project head") from exc
        if row is None:
            raise StorageError("storage.not_found", f"no local project head for {project_text!r}")
        revision_id = str(row[0])
        serialized = self._read_serialized(project_text, revision_id)
        try:
            candidate = deserialize_project(serialized, migrations=migrations)
        except SerializationError as exc:
            raise _serialization_failure(exc) from exc
        if self._candidate_ids(candidate) != (project_text, revision_id):
            raise StorageError("storage.corrupt_store", "physical head identity disagrees with canonical revision identity")
        return candidate

    def head_revision_id(self, project_id: ProjectId | str) -> ProjectRevisionId:
        self._assert_store_format()
        project_text = str(project_id)
        try:
            row = self._db.execute(
                "SELECT revision_id FROM heads WHERE project_id=?",
                (project_text,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading project head") from exc
        if row is None:
            raise StorageError("storage.not_found", f"no local project head for {project_text!r}")
        return ProjectRevisionId(str(row[0]))

    def diagnostics(self) -> dict[str, object]:
        """Return non-semantic physical diagnostics for support/tests."""
        try:
            journal_mode = str(self._db.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            synchronous = int(self._db.execute("PRAGMA synchronous").fetchone()[0])
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading storage diagnostics") from exc
        return {
            "store_schema": STORE_SCHEMA,
            "store_format_version": STORE_FORMAT_VERSION,
            "journal_mode": journal_mode,
            "synchronous": synchronous,
            "path": self.path,
        }
