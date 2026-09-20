from __future__ import annotations

import copy
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    AddThing,
    AssetId,
    ProjectId,
    ProjectRevisionId,
    SemanticTransaction,
    ThingId,
    ThingRecord,
    apply_transaction,
    empty_document,
)
from splashmx.canonical.serialization import (  # noqa: E402
    CanonicalProjectRevision,
    MigrationRegistry,
    ProtectedAssetRevision,
    SerializedProjectRevision,
    decode_canonical_cbor,
    encode_canonical_cbor,
    serialize_project,
)
from splashmx.storage.local import (  # noqa: E402
    COMMIT_STAGES,
    STORE_FORMAT_VERSION,
    STORE_SCHEMA,
    SQLiteProjectStore,
    StorageError,
)


def pid(value: str = "project-local") -> ProjectId:
    return ProjectId(value)


def rev(value: str) -> ProjectRevisionId:
    return ProjectRevisionId(value)


def tid(value: str) -> ThingId:
    return ThingId(value)


def protected_asset(marker: str) -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId("music"),
        source_digest="sha256:" + marker * 64,
        source_identity={"kind": "author-import", "logical_name": "music.wav"},
        source_metadata={"bytes": 8192, "original_extension": "wav"},
        media_semantics={
            "kind": "audio",
            "channels": 2,
            "sample_rate": 48000,
            "loop": {"enabled": True, "start_frame": 64, "end_frame": 4096},
        },
        provenance={"creator": "fixture-author", "source": f"recording-{marker}"},
        licence_attribution={"licence": "CC0-1.0", "attribution": ""},
        derivation_lineage=(
            {"operation": "trim", "tool": "fixture", "parent_digest": "sha256:" + "f" * 64},
        ),
    )


def project0() -> CanonicalProjectRevision:
    return CanonicalProjectRevision(
        empty_document(pid(), rev("r0")),
        {AssetId("music"): protected_asset("a")},
    )


def project1() -> CanonicalProjectRevision:
    doc = apply_transaction(
        copy.deepcopy(project0().document),
        SemanticTransaction(
            rev("r1"),
            (AddThing(ThingRecord(tid("speaker"), "Speaker", authored_state={"gain": 0.75})),),
        ),
    )
    return CanonicalProjectRevision(doc, {AssetId("music"): protected_asset("b")})


def with_schema_version(serialized: SerializedProjectRevision, version: int) -> SerializedProjectRevision:
    manifest = decode_canonical_cbor(serialized.root_manifest)
    manifest["schema_version"] = version
    return SerializedProjectRevision(encode_canonical_cbor(manifest), dict(serialized.shards))


class InjectedInterruption(RuntimeError):
    pass


class SMX025NativePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "project-store.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def reopen(self) -> SQLiteProjectStore:
        return SQLiteProjectStore(self.db_path)

    def test_native_store_uses_selected_sqlite_wal_full_and_round_trips_without_control_plane(self):
        before = project0()
        with self.reopen() as store:
            saved = store.save(before)
            self.assertEqual(saved, before)
            self.assertEqual(store.load(pid()), before)
            diag = store.diagnostics()
            self.assertEqual(diag["store_schema"], STORE_SCHEMA)
            self.assertEqual(diag["store_format_version"], STORE_FORMAT_VERSION)
            self.assertEqual(diag["journal_mode"], "wal")
            self.assertEqual(diag["synchronous"], 2)  # SQLite FULL
        with self.reopen() as store:
            self.assertEqual(store.load(pid()), before)

    def test_every_precommit_interruption_stage_reopens_the_previous_coherent_revision(self):
        precommit = tuple(stage for stage in COMMIT_STAGES if stage != "committed")
        for stage in precommit:
            with self.subTest(stage=stage):
                db = Path(self.temp.name) / f"crash-{stage}.sqlite3"
                with SQLiteProjectStore(db) as store:
                    store.save(project0())
                    def crash(current: str, target: str = stage) -> None:
                        if current == target:
                            raise InjectedInterruption(target)
                    with self.assertRaises(InjectedInterruption):
                        store.save(project1(), fault_hook=crash)
                with SQLiteProjectStore(db) as reopened:
                    self.assertEqual(reopened.head_revision_id(pid()), rev("r0"))
                    self.assertEqual(reopened.load(pid()), project0())

    def test_interruption_after_completed_commit_reopens_the_new_coherent_revision(self):
        with self.reopen() as store:
            store.save(project0())
            def crash(stage: str) -> None:
                if stage == "committed":
                    raise InjectedInterruption(stage)
            with self.assertRaises(InjectedInterruption):
                store.save(project1(), fault_hook=crash)
        with self.reopen() as store:
            self.assertEqual(store.head_revision_id(pid()), rev("r1"))
            self.assertEqual(store.load(pid()), project1())

    def test_same_revision_identity_cannot_be_rebound_to_different_bytes(self):
        with self.reopen() as store:
            store.save(project0())
            competing = CanonicalProjectRevision(
                copy.deepcopy(project0().document),
                {AssetId("music"): protected_asset("c")},
            )
            with self.assertRaises(StorageError) as caught:
                store.save(competing)
            self.assertEqual(caught.exception.code, "storage.revision_conflict")
            self.assertEqual(store.load(pid()), project0())

    def test_protected_asset_bundle_survives_commit_and_reopen_as_one_revision(self):
        with self.reopen() as store:
            store.save(project1())
        with self.reopen() as store:
            loaded = store.load(pid())
        asset = loaded.assets[AssetId("music")]
        expected = protected_asset("b")
        self.assertEqual(asset, expected)
        self.assertEqual(asset.revision_digest, expected.revision_digest)
        self.assertEqual(asset.source_digest, expected.source_digest)
        self.assertEqual(asset.source_identity, expected.source_identity)
        self.assertEqual(asset.source_metadata, expected.source_metadata)
        self.assertEqual(asset.media_semantics, expected.media_semantics)
        self.assertEqual(asset.provenance, expected.provenance)
        self.assertEqual(asset.licence_attribution, expected.licence_attribution)
        self.assertEqual(asset.derivation_lineage, expected.derivation_lineage)

    def test_corrupt_shard_is_rejected_before_caller_can_replace_active_state(self):
        active = project0()
        with self.reopen() as store:
            store.save(active)
        raw = sqlite3.connect(self.db_path)
        raw.execute(
            "UPDATE shards SET payload=? WHERE rowid=(SELECT MIN(rowid) FROM shards)",
            (sqlite3.Binary(b"corrupt"),),
        )
        raw.commit()
        raw.close()
        with self.reopen() as store:
            with self.assertRaises(StorageError) as caught:
                candidate = store.load(pid())
                active = candidate
        self.assertEqual(caught.exception.code, "storage.corrupt_store")
        self.assertEqual(active, project0())

    def test_missing_shard_is_rejected_as_corrupt_without_head_reinterpretation(self):
        with self.reopen() as store:
            store.save(project0())
        raw = sqlite3.connect(self.db_path)
        raw.execute("DELETE FROM shards WHERE rowid=(SELECT MIN(rowid) FROM shards)")
        raw.commit()
        raw.close()
        with self.reopen() as store:
            with self.assertRaises(StorageError) as caught:
                store.load(pid())
        self.assertEqual(caught.exception.code, "storage.corrupt_store")

    def test_incompatible_store_version_is_typed_and_does_not_rewrite_the_store(self):
        with self.reopen() as store:
            store.save(project0())
        raw = sqlite3.connect(self.db_path)
        raw.execute("UPDATE metadata SET value='999' WHERE key='store_format_version'")
        raw.commit()
        raw.close()
        with self.assertRaises(StorageError) as caught:
            self.reopen()
        self.assertEqual(caught.exception.code, "storage.unsupported_store_version")
        raw = sqlite3.connect(self.db_path)
        value = raw.execute("SELECT value FROM metadata WHERE key='store_format_version'").fetchone()[0]
        raw.close()
        self.assertEqual(value, "999")

    def test_v0_serialized_import_migrates_and_publishes_current_semantics_atomically(self):
        legacy = with_schema_version(serialize_project(project0()), 0)
        with self.reopen() as store:
            candidate = store.import_serialized(legacy)
            self.assertEqual(candidate, project0())
            self.assertEqual(store.load(pid()), project0())

    def test_failed_migration_happens_before_store_mutation_and_preserves_old_head(self):
        legacy = with_schema_version(serialize_project(project1()), 0)
        registry = MigrationRegistry()
        def fail(_records):
            raise RuntimeError("injected migration failure")
        registry.register(0, 1, fail)
        with self.reopen() as store:
            store.save(project0())
            with self.assertRaises(StorageError) as caught:
                store.import_serialized(legacy, migrations=registry)
            self.assertEqual(caught.exception.code, "storage.migration_failed")
            self.assertEqual(store.head_revision_id(pid()), rev("r0"))
            self.assertEqual(store.load(pid()), project0())

    def test_unknown_project_is_explicit_not_found(self):
        with self.reopen() as store:
            with self.assertRaises(StorageError) as caught:
                store.load(pid("missing"))
        self.assertEqual(caught.exception.code, "storage.not_found")

    def test_store_schema_contains_no_cache_ownership_table(self):
        with self.reopen() as store:
            tables = {
                row[0] for row in store._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertEqual(tables, {"metadata", "revisions", "shards", "heads"})
        self.assertFalse(any("cache" in name.lower() for name in tables))


if __name__ == "__main__":
    unittest.main()
