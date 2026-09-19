# SMX-022 — Canonical physical encoding and crash-consistent local store spike

**Status:** mechanism selected; real-browser evidence remains a merge gate  
**Issue:** #47 / SMX-022  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Base:** `aa532c4cf19772dc352deca4426d7f6554f8ffdf` (SMX-021)

This is a bounded mechanism-selection spike beneath Architecture v1. It does not implement `canonical.core`, `canonical.serialization`, `storage.local`, the collaboration substrate, package distribution, or cloud storage. Code under `experiments/smx-022-storage-spike/` is disposable comparative evidence, not production code.

## Contents

| Section | Summary |
|---|---|
| 1. Decision | Selects deterministic CBOR records, stable-ID hash shards, IndexedDB + prepared OPFS in browsers, and SQLite + prepared blobs natively. |
| 2. Frozen requirements | Converts Architecture-v1 semantics into physical constraints. |
| 3. Candidate comparison | Records compared and rejected mechanisms. |
| 4. Canonical byte profile | Defines the selected serialization boundary for SMX-024. |
| 5. Indexing and partial access | Defines bounded sharding without making placement semantic. |
| 6. Browser persistence model | Defines transactions, OPFS staging, quota and eviction behavior. |
| 7. Native persistence model | Defines SQLite crash consistency and recovery. |
| 8. Reproducible evidence | Records fixtures and measured observations. |
| 9. Security, migration and corruption | Defines safety constraints around the selected mechanisms. |
| 10. Protected media / collaboration pressure | Preserves indivisible assets and semantic history loci. |
| 11. Rejected alternatives | Records falsified or deliberately deferred candidates. |
| 12. Exact handoff | Prevents SMX-024/025 from repeating broad selection. |

## 1. Decision

Select a deliberately layered physical design:

1. **Canonical bytes:** independently encoded semantic records and immutable revision metadata use a SplashMX-owned **deterministic CBOR** profile based on RFC 8949 core deterministic encoding requirements. Generic serializer output is never canonical by implication.
2. **Indexing/partial access:** semantic records are grouped into deterministic bounded **stable-semantic-ID hash shards**. A small immutable root revision manifest identifies shards by internal prefix plus digest/length. Each shard owns a deterministic local semantic-ID → byte-range/digest index and canonical record bytes. Shard, byte offset, digest and database location are non-semantic.
3. **Browser project ownership:** **IndexedDB** owns editable project records, revision metadata and the coherent current head. Publication is one read/write transaction, requesting `{ durability: "strict" }` where supported. **OPFS** is permitted for prepared immutable blobs/shard payloads before the IndexedDB publication transaction; it never independently owns the project head.
4. **Native project ownership:** **SQLite WAL with `synchronous=FULL`** owns records, revision metadata and the coherent head. Immutable large blobs/chunks may be prepared and fsync-verified before the SQLite transaction. Rollback-journal `FULL` is a supported fallback when WAL is unsuitable.
5. **Recovery invariant:** prepared immutable bytes may become orphan garbage after interruption, but cannot become live semantic state until the transaction publishes a fully validated revision. Failure leaves the previous coherent head.

No Architecture-v1 change is required.

## 2. Frozen requirements

The mechanism must preserve the following irrespective of physical implementation:

- durable semantic IDs remain path-independent and independent of byte position, shard placement, database row identity, URLs, engine handles, DOM identity, peers/sockets/sessions and processes;
- logical equality is independent of map insertion order and physical record order;
- physical canonical bytes exist only under an explicitly versioned canonicalization profile;
- every multi-record edit, migration and replacement validates the complete result before atomic publication;
- authored state, transient editor/runtime state, persistent WorldSave state, collaboration history/conflicts and immutable published revisions remain separate planes;
- `known_unloaded` is distinguishable from tombstoned, unknown and incompatible;
- physical chunking is locality/index policy, not semantic ownership;
- exact dependencies/artifacts remain explicit and cache eviction is non-semantic;
- migration is deterministic, bounded, capability-free by default, target-validated and rollback-safe;
- future collaboration/history may address semantic records/revisions/transactions without making a physical offset or database key a conflict locus;
- browser permission/quota/eviction outcomes are explicit typed failures rather than silent data loss or substitution;
- the protected `AssetId` revision remains an indivisible digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation-lineage bundle.

## 3. Candidate comparison

### 3.1 Canonical encoding

| Candidate | Strengths | Result |
|---|---|---|
| Deterministic CBOR application profile | Standards-defined deterministic base, compact binary/byte strings, portable across browser/native/headless | **Selected.** SplashMX narrows the profile and owns its version. |
| Canonical JSON projection | Ubiquitous and inspectable; excellent fixture/debug format | Retained as diagnostic/interchange projection; not canonical bytes. |
| Protobuf/schema-binary family | Strong schemas/generated tooling and compact messages | Rejected for canonical bytes because upstream explicitly states deterministic serialization is not canonical across languages/builds/schema evolution. |
| Engine/resource serialization | Convenient on the first Godot target | Rejected by Architecture v1 as a durable compatibility boundary. |

Primary facts refreshed 2026-09-19:
- RFC 8949 deterministic encoding: https://www.rfc-editor.org/rfc/rfc8949.html#section-4.2
- Protocol Buffers, “Proto Serialization Is Not Canonical”: https://protobuf.dev/programming-guides/serialization-not-canonical/

### 3.2 Indexing/chunking

| Candidate | Observation | Result |
|---|---|---|
| Monolithic JSON/CBOR project | Simple root but whole-document parse/rewrite for a tiny edit or lookup | Rejected as required physical form. |
| Flat global record manifest + chunks | Direct lookup works, but the prototype global index grew to roughly 600 KiB on the many-record fixture and every tiny edit rewrote it | Falsified as the default index. |
| Stable-ID hash shards + local indexes | One semantic ID deterministically selects a bounded shard; edit locality becomes one shard + a small root; direct partial reads avoid monolithic decode | **Selected.** Initial 32 KiB target; 16–64 KiB remains tunable. |

The shard key is derived from the semantic ID only to select physical placement. It is not Thing/Asset/Connection identity. Repacking or policy-version migration cannot rewrite semantic IDs or durable references.

### 3.3 Browser persistence

| Candidate | Strengths | Result |
|---|---|---|
| IndexedDB transactions | Native record/index model, multi-store transactions, partial reads, durability hint | **Selected as project transaction/head owner.** |
| OPFS revision/blob files | Efficient origin-private files; writable stream normally replaces target on close | Selected only for prepare-before-publish immutable blob/chunk backing. |
| SQLite/WASM over OPFS | Reuses SQLite semantics in-browser | Credible later optimization, but rejected as v1 default because VFS/worker/locking complexity adds platform risk without a frozen-semantic benefit over IndexedDB + OPFS staging. |
| localStorage/Web Storage | Simple | Rejected: string-only, small quota and no project-scale transactional/indexed model. |

Current platform facts:
- IndexedDB `IDBTransaction.durability` supports `"strict"`: https://developer.mozilla.org/en-US/docs/Web/API/IDBTransaction/durability
- OPFS is quota-managed origin-private storage: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system
- `createWritable()` generally stages replacement until close: https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable
- origin storage is best-effort by default; persistence can be requested and quota failure is `QuotaExceededError`: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
- SQLite WASM OPFS VFS/locking constraints: https://sqlite.org/wasm/doc/trunk/persistence.md

### 3.4 Native/local persistence

| Candidate | Strengths | Result |
|---|---|---|
| SQLite WAL + `synchronous=FULL` | Mature transactions, indexes, partial reads and crash recovery | **Selected.** |
| SQLite rollback journal + `FULL` | Mature atomic recovery with different sidecar/concurrency behavior | Supported fallback. |
| Whole immutable revision file + fsync + atomic HEAD replacement | Auditable and recovered coherently in the spike | Rejected as default working store due whole-revision rewrite amplification and separate index burden; useful for export/backup/checkpoint forms. |

SQLite primary sources:
- atomic commit and recovery: https://www.sqlite.org/atomiccommit.html
- synchronous durability modes: https://sqlite.org/pragma.html#pragma_synchronous

## 4. Canonical byte profile handed to SMX-024

SMX-024 should implement and version a deterministic-CBOR application profile with at least:

- RFC 8949 preferred shortest integer/length encodings and definite lengths;
- deterministic encoded-key byte ordering;
- string map keys for v1 canonical record maps;
- duplicate map keys rejected;
- strict UTF-8, with no implicit Unicode-normalization transform by the encoder;
- integer and floating-point schema types remain distinct;
- project records reject NaN and infinities; negative zero remains distinguishable when floats are permitted;
- no CBOR tag becomes meaningful unless registered by the SplashMX profile/schema version;
- omission/default behavior is schema-defined, not generic-encoder-defined;
- data remains inert until schema/features/integrity/migration and whole-result semantic validation succeed;
- diagnostic JSON may round-trip logical content, but its bytes are not canonical revision identity.

The Python encoder in this spike is only a narrow deterministic oracle. It is not a production CBOR library recommendation.

## 5. Indexing, chunking and partial access

Selected conceptual layout:

~~~text
ProjectRevision root manifest (deterministic CBOR)
  schema/features/project/revision metadata
  shard-policy version
  sorted shard descriptors -> immutable shard digest + length

Immutable shard
  deterministic local index:
    semantic ID -> offset + length + record digest
  canonical deterministic-CBOR record bytes

Immutable large blob
  content digest -> exact verified bytes
~~~

The prototype uses leading bits of SHA-256(semantic-ID UTF-8) and increases prefix depth until a target size bound is met. The exact hash algorithm and 32 KiB initial target are replaceable physical policy under a versioned shard-policy identifier.

A partial lookup needs the root manifest, one selected shard and one record. This supports confirming a valid `known_unloaded` identity without materializing unrelated subgraphs. Future streaming can repack physical units without altering semantic identity.

## 6. Browser persistence model handed to SMX-025

### IndexedDB owns the coherent head

A save transaction writes changed canonical records, revision metadata and the new project head in one IndexedDB `readwrite` transaction. Request `{ durability: "strict" }` where supported and record/report when the requested durability is unavailable.

Stores are keyed by SplashMX semantic IDs/revision IDs. Auto-generated database keys, DOM objects and implementation handles are never canonical identity.

### OPFS is prepare-before-publish backing

Large immutable blobs or shard payloads may be written under internal content-addressed names, closed, re-read/integrity-verified and only then referenced by the IndexedDB transaction. Interruption may leave an unreferenced immutable orphan, but cannot publish a head that refers to a partially written file.

GC determines liveness from coherent project revisions, not filesystem presence. Disposable cache OPFS bytes remain non-semantic.

### Quota, denial and eviction

SMX-025 must:
- use `navigator.storage.estimate()` as diagnostic/preflight information, not a semantic quota guarantee;
- request `navigator.storage.persist()` where appropriate and expose whether persistence was granted;
- map `QuotaExceededError`, unavailable APIs, write errors and transaction aborts to typed SplashMX failures;
- never advance the head after failed/quota-aborted publication;
- keep canonical project ownership distinct from disposable cache;
- provide explicit export/backup because browser site-data deletion cannot be claimed impossible;
- validate the stored revision before activation after reopen and report corruption/unavailability explicitly.

The dedicated real-Chromium workflow is a merge gate for this spike. It tests IndexedDB abort/page interruption and OPFS unclosed-writer behavior; one Chromium run is not represented as universal browser disk/power-loss certification.

## 7. Native persistence model handed to SMX-025

Recommended initial configuration:

~~~text
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
~~~

A native save:
1. canonicalizes and validates changed records;
2. writes/fsync-verifies new external immutable bytes before they can be referenced;
3. begins one SQLite write transaction;
4. writes changed records and immutable revision metadata;
5. advances the coherent project head inside that transaction;
6. commits;
7. reports the new revision live only after successful commit.

A pre-commit process interruption reopens the old head. An interruption after a completed durable commit reopens the new head. Prepared-but-unreferenced blobs are inert GC candidates.

Whole-revision atomic files remain suitable for export/backup/checkpoints rather than the editable working database.

## 8. Reproducible comparative evidence

Fixtures are declared in `docs/research/SMX-022-PHYSICAL-STORE-FIXTURES.json`. The disposable harness covers tiny/nested/many-record projects, protected assets, known-unloaded references, one-record edits, corrupted deterministic records, interrupted native commits, and real browser IndexedDB/OPFS interruptions.

Native evidence is retained in `docs/research/SMX-022-NATIVE-EVIDENCE.json` under the SMX-021 benchmark-evidence contract. Captured environment: CPython 3.13.5, Linux 6.18.44 x86_64, Intel Xeon Platinum 8573C, 6,236,913,664 bytes reported memory.

### Encoding size

| Fixture | Canonical JSON | deterministic CBOR oracle |
|---|---:|---:|
| tiny | 5,983 B | 4,807 B |
| nested | 54,449 B | 44,108 B |
| 1,500 Things + 3,000 Connections | 1,050,729 B | 858,578 B |

The pure-Python CBOR oracle is slower than CPython’s native JSON implementation. That is an implementation artifact, not evidence about a production CBOR library, and no threshold is inferred from it.

### Shard locality for a 238-byte edited record

| Target | Shards | Changed shard | Root | Write amplification | Median direct partial read | Median monolithic decode+lookup |
|---|---:|---:|---:|---:|---:|---:|
| 16 KiB | 128 | 9,366 B | 11,937 B | 89.5x | 0.058 ms | 49.1 ms |
| 32 KiB | 64 | 16,809 B | 5,985 B | 95.8x | 0.068 ms | 48.4 ms |
| 64 KiB | 32 | 33,672 B | 3,009 B | 154.1x | 0.090 ms | 48.3 ms |
| 256 KiB | 8 | 132,908 B | 808 B | 561.8x | 0.240 ms | 49.0 ms |

This falsifies 256 KiB as a sensible default for small-edit locality. The flat global index was separately discarded after the index itself approached roughly 600 KiB.

### Native recovery

SQLite WAL/FULL, SQLite rollback/FULL and fsync + atomic-HEAD revision files all reopened at the old head after a pre-publication abrupt process exit and the new head after completed publication. The whole-file candidate rewrote approximately 44,110 bytes for each nested-project commit.

Container latency values are retained for reproducibility only; recovery behavior and upstream durability guarantees carry more selection weight than uncalibrated container I/O timings.

### Browser evidence

`.github/workflows/smx022-physical-store.yml` runs pinned Playwright/Chromium and emits `artifacts/smx022-browser-results.json` including runtime/browser/OS/hardware, IndexedDB strict-transaction observations, OPFS write-close/read observations, storage persistence/estimate state, and interruption outcomes. The decision must not merge until this campaign passes and the result is reviewed.

## 9. Failure, security and migration implications

- Parsing must bound nesting, counts, string/byte lengths, total allocation and record/shard sizes.
- Duplicate keys, malformed UTF-8, invalid deterministic forms, digest mismatch, unsupported required tags/features and truncation fail explicitly.
- No activation occurs from merely decoded or partially verified bytes.
- Migration consumes validated semantic records and emits a new validated revision; it is bounded and capability-free by default.
- Migration never mutates the only coherent source before target validation/publication.
- Shard-policy/store migration may repack every record while preserving semantic identity and references.
- No database row ID, OPFS path, SQLite page number, shard prefix, byte offset, cache key or digest becomes author-visible identity.
- External blob names are internal content locators and remain subject to later path/archive hardening.

## 10. Protected media and future collaboration/diff pressure

A protected `AssetId` record is encoded and committed as one complete immutable revision containing all seven protected fields. Competing revisions are complete alternatives. Storage cannot field-mix a digest from one revision with source/provenance/licence/lineage from another.

Large source bytes may live in a separately content-addressed immutable blob, but the canonical Asset revision remains the indivisible semantic selector for the blob digest and its complete source/media/provenance meaning.

Future collaboration operates on stable semantic record/locus IDs and causal transactions. It may store history separately, but current materialized state remains independently valid. Physical shard movement, SQLite rows and IndexedDB implementation keys are not collaboration conflict loci.

## 11. Rejected alternatives and why

- **One giant JSON/CBOR document:** poor partial access and small-update locality.
- **Flat global record manifest:** prototype falsified it through global-index rewrite amplification.
- **256 KiB default shards:** markedly worse tiny-edit amplification than 16–64 KiB in the representative many-record fixture.
- **Protobuf bytes as canonical bytes:** upstream does not promise canonical serialization across languages/builds/evolution.
- **SQLite database file as public/interchange contract:** working-store schema/page layout must remain replaceable and browser/native stores may differ.
- **SQLite/WASM/OPFS as browser default:** credible later optimization, but current VFS/worker/locking complexity is additional platform risk without a frozen-semantic benefit.
- **OPFS files alone as project transaction owner:** file-safe replacement is not one native multi-record/head transaction across files.
- **Whole-revision native files as working store:** crash-safe with careful fsync/rename protocol but high rewrite amplification and indexing burden.
- **Content digest as mutable Thing/Asset identity:** contradicts stable path-independent identity across edits.

## 12. Exact handoff

### SMX-024 — canonical serialization and protected assets

Implement, rather than re-select:
- deterministic-CBOR v1 profile from section 4;
- strict bounded parser and canonical-form validation;
- canonical semantic record envelopes and complete protected Asset revisions;
- immutable root manifest plus stable-ID hash shards/local indexes;
- migration/version envelope and old-version golden fixtures;
- deterministic equivalence/golden-byte tests across independent implementations where practical.

Still open below the selected boundary: exact production CBOR library, exact field/schema layout, exact shard hash identifier, compression, and outer export/container wrapping.

### SMX-025 — crash-safe local project store

Implement, rather than re-select:
- browser IndexedDB records/revisions/head transaction adapter with strict durability request where supported;
- browser prepared OPFS immutable blob/shard backing and orphan GC;
- browser quota/persistence/eviction/denial typed failures plus export/backup contract;
- native SQLite WAL/FULL records/revisions/head adapter;
- native prepared immutable blob/shard files and orphan recovery/GC;
- corruption, reopen/recovery, interrupted migration and interrupted publication tests.

Still open below the selected boundary: table/object-store names, pooling, checkpoint cadence, GC cadence, backup UI and performance tuning.

Neither downstream issue may make database rows, DOM/FileSystem handles, paths, cache keys or physical chunk locations canonical identity.
