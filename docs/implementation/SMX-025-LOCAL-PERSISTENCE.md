# SMX-025 — Crash-safe local project persistence

**Status:** production implementation  
**Issue:** #50 / SMX-025  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Mechanism authority:** `docs/research/SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md`  
**Canonical-byte authority:** `docs/implementation/SMX-024-CANONICAL-SERIALIZATION.md`

SMX-025 implements the first production ownership boundary for editable local project revisions. It does not change Architecture v1.0 and does not absorb WorldSave, package/cache storage, collaboration history, cloud synchronization, publishing or runtime snapshots.

## Contents

| Section | Summary |
|---|---|
| 1. Production contract | Defines what `storage.local` owns and what it does not. |
| 2. Native store | Defines the SQLite WAL/FULL publication boundary. |
| 3. Browser store | Defines IndexedDB ownership and strict-durability behavior. |
| 4. Commit/recovery state machine | Defines the exact atomicity and interruption invariant. |
| 5. Validation and migration | Keeps incompatible/corrupt bytes inert until canonical validation succeeds. |
| 6. Typed failures | Records author-safe failure classes for native and browser storage. |
| 7. Protected media | Preserves the indivisible source/audio/provenance revision bundle. |
| 8. Cache and OPFS boundary | Keeps project ownership separate from disposable or prepared bytes. |
| 9. Adversarial evidence | Records deterministic native and real-browser tests. |
| 10. Residual scope | States what remains for downstream production issues. |

## 1. Production contract

`storage.local` owns two things only:

1. immutable canonical project-revision bytes produced by `canonical.serialization`; and
2. the coherent current head for each local `ProjectId`.

The store does **not** assign semantic IDs, infer project meaning from database keys, reinterpret unsupported schemas, expose partially loaded revisions as active state, or make physical row/file/cache identity canonical. `ProjectId` and `ProjectRevisionId` remain the only semantic identity inputs owned by this module.

Both adapters obey prepare-before-publish: canonical bytes are inert until the complete candidate has passed the SMX-024 decode/migration/integrity/whole-project validation boundary. The durable head advances only inside the same storage transaction that makes the complete revision reachable.

## 2. Native store

`src/splashmx/storage/local.py` implements `SQLiteProjectStore` using the SMX-022 selection:

```text
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
```

The database contains only version metadata, immutable revision rows, immutable canonical shards and project heads. There is deliberately no cache table and no generated row identity is used as a canonical reference.

A save performs this sequence:

1. serialize or deserialize/migrate the candidate entirely outside the write transaction;
2. re-serialize migrated input under the current SMX-024 canonical profile;
3. begin one `BEGIN IMMEDIATE` transaction;
4. insert the immutable revision envelope;
5. insert every canonical shard and physical SHA-256 integrity digest;
6. read the complete candidate back inside the transaction and pass it through SMX-024 deserialization/whole-project validation again;
7. advance the project head;
8. commit;
9. only then return the new revision as live.

A pre-existing `(ProjectId, ProjectRevisionId)` is idempotent only when its complete canonical bytes match. Rebinding the same revision identity to different root/shard bytes fails as `storage.revision_conflict`.

## 3. Browser store

`src/splashmx/storage/browser_indexeddb.mjs` implements the browser-local physical boundary selected by SMX-022. IndexedDB owns revision rows, shard rows and the coherent project head in one multi-store transaction. The adapter requests `{ durability: "strict" }` where the browser accepts the option and records whether strict durability was supported/reported.

The browser adapter additionally stores SHA-256 digests for its root/shard rows and verifies them on reopen. It treats canonical bytes as opaque because the canonical CBOR/schema implementation currently lives in `canonical.serialization`; callers must pass bytes through that canonical validation/migration boundary before save and after load, **before replacing active state**. This separation prevents the database adapter from becoming a second semantic parser.

`navigator.storage.estimate()` is exposed only as diagnostic information. `navigator.storage.persisted()` and an explicit persistence request can be surfaced to product UI, but neither becomes a semantic guarantee. Browser site-data deletion remains possible and must eventually be addressed by explicit export/backup UX.

## 4. Commit/recovery state machine

The deterministic fault boundary names these stages:

```text
prepared
revision_recorded
shards_recorded
candidate_verified
head_advanced
committed
```

The recovery invariant is intentionally binary:

- interruption at any stage before `committed` must reopen the previous complete head; and
- interruption after the durable commit may report an ambiguous caller outcome, but reopen must reveal the new complete head.

There is no state in which a head may resolve to half of one revision and half of another. Prepared/orphan immutable bytes are non-live until referenced by a committed head and may later be garbage-collected without semantic effect.

## 5. Validation and migration

`SQLiteProjectStore.import_serialized()` integrates directly with the SMX-024 migration envelope. Old physical input is decoded, bounded-migrated and whole-project validated before a database write begins, then re-serialized under the current physical profile for storage. A missing/failed migration therefore cannot partially modify the local store.

On reopen, physical row digests are checked first and the reconstructed `SerializedProjectRevision` is then passed through SMX-024. Unsupported schema/features/profile become `storage.incompatible_revision`; malformed/digest-invalid canonical data becomes `storage.corrupt_store`; migration failure becomes `storage.migration_failed`. None of these outcomes mutates caller-owned active state.

The store itself has an independent `splashmx.local-store/1` / format-version envelope. A newer or malformed store version fails explicitly instead of being rewritten or guessed.

## 6. Typed failures

The production boundary uses stable SplashMX storage codes rather than exposing host exception strings as application semantics. Current classes include:

- `storage.not_found` — no local head exists for the requested project;
- `storage.revision_conflict` — a semantic revision ID is already bound to different bytes;
- `storage.incompatible_revision` / `storage.migration_failed` — canonical version/features cannot be safely activated;
- `storage.corrupt_store` — physical or canonical integrity failed;
- `storage.unsupported_store_format` / `storage.unsupported_store_version` — the physical database envelope is incompatible;
- `storage.quota_exceeded` — host storage capacity/quota refused publication;
- `storage.permission_denied` — host policy/permissions refused access;
- `storage.unavailable` — the selected storage API/database cannot currently be opened;
- `storage.transaction_aborted` / `storage.io_failure` / `storage.database_error` — explicit host-level publication failure classes.

Browser `QuotaExceededError`, `SecurityError`/`NotAllowedError`, abort/inactive-transaction and unavailable-API outcomes are mapped explicitly. Native SQLite FULL, READONLY/PERM/AUTH, CORRUPT/NOTADB, CANTOPEN/BUSY/LOCKED and IOERR families are likewise mapped.

## 7. Protected media

Local persistence does not weaken the protected media/source contract established by SMX-024. A stable `AssetId` selects one immutable revision whose **source digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage** are indivisible.

Storage commits the already-validated canonical revision as a whole. A crash, quota error, migration failure, corrupt row or reopen cannot publish a field-mixed Asset: either the old complete project head remains live or the new complete project head does. Target-private decoded/transcoded/cache data remains non-canonical and cannot replace these source semantics.

## 8. Cache and OPFS boundary

SMX-022 permits OPFS for prepare-before-publish immutable large blobs/shards, but it does not require OPFS for every project revision. SMX-025 keeps the initial browser canonical working set entirely within the IndexedDB transaction so there is one unambiguous project-head owner.

Future large-blob optimization may stage content-addressed OPFS bytes, verify them, then reference them from the IndexedDB transaction. Such prepared bytes are not live solely because a file exists. Cache eviction remains non-semantic and is owned by later streaming/package work; it cannot delete or advance the canonical editable project head.

## 9. Adversarial evidence

`tests/production/test_smx025.py` exercises the native production adapter against every named commit boundary and reopens a fresh SQLite connection after interruption. Coverage includes:

- old-head recovery after each pre-commit stage;
- new-head recovery after a completed commit whose caller was interrupted;
- exact revision-identity conflict rejection;
- whole protected-Asset round-trip;
- damaged and missing shard rejection before activation;
- incompatible physical store version;
- v0 canonical migration into the current physical profile;
- failed migration before mutation;
- explicit missing-project behavior; and
- confirmation that canonical project ownership contains no cache table.

`tests/production/smx025_browser_harness.mjs` runs the production IndexedDB adapter in real headless Chromium. It repeats every pre-commit fault, post-commit reopen, physical-digest corruption, incompatible store version, strict-durability reporting, browser quota/permission/abort classification and unavailable-IndexedDB behavior. The fixture carries all protected media fields and asserts that reopen never field-mixes revisions.

The campaign is regression evidence for the tested Chromium/SQLite environments. It is not a universal hardware power-loss certification or a claim that browser origin storage cannot be externally deleted.

## 10. Residual scope

SMX-025 intentionally leaves the following to their recorded owners:

- WorldSave, dormant runtime state and fresh-process runtime restore — SMX-029 / #54;
- streaming acquisition and immutable disposable cache — SMX-030 / #55;
- browser authoring/save UX and user-facing recovery diagnostics — SMX-032/033 / #57/#58;
- package/component stores — SMX-035 / #60;
- collaboration history/compaction — SMX-043 / #68; and
- backup/distribution/runtime-retention product policy — SMX-050/051 / #75/#76.

No hosted control plane, account service or network connection is required to create, save, reopen or migrate a local canonical project revision.
