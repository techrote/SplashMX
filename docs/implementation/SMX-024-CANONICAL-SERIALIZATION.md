# SMX-024 — Protected assets, canonical serialization and migration envelope

**Status:** production implementation for `canonical.serialization`  
**Issue:** #49 / SMX-024  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Mechanism selection:** `docs/research/SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md`

SMX-024 materializes the physical serialization boundary beneath the SMX-023 canonical semantic core. It does not reopen the SMX-022 mechanism comparison and it does not change Architecture v1.0. The physical representation remains subordinate to SplashMX semantic identity and validation.

## Production contract

`src/splashmx/canonical/serialization.py` implements:

- a SplashMX-owned deterministic-CBOR v1 subset following the SMX-022 profile: shortest integer/length forms, definite lengths, deterministic encoded-key ordering, strict UTF-8, distinct integer/float schema values, shortest exactly-representable finite float encoding, no unregistered tags, no NaN/infinity and preserved negative zero;
- strict bounded decoding with byte, nesting, item and string limits plus byte-for-byte canonical-form revalidation;
- independently canonical semantic records grouped into deterministic stable-semantic-ID SHA-256 prefix shards with local byte-range/digest indexes;
- an immutable root revision manifest containing project/revision IDs, physical profile IDs, required features and shard digests/lengths;
- a complete protected-asset revision selected by stable `AssetId`;
- a bounded migration registry which prepares and validates a complete candidate before any caller may publish it;
- typed `SerializationError.code` failures for incompatible versions/features/profiles, corruption, malformed/noncanonical CBOR, migration failure, identity mismatch and forbidden transient identity leakage.

The selected store mechanisms remain SMX-025 work. In particular, this module does **not** make a SQLite row, IndexedDB key, OPFS path, shard prefix, byte offset, digest, cache key, session/peer ID or engine handle into semantic identity.

## Protected source/audio/provenance boundary

A stable `AssetId` selects one complete immutable protected revision containing all seven Architecture-v1 fields:

1. source digest;
2. source identity;
3. source metadata;
4. audio/media semantics;
5. provenance;
6. licence/attribution;
7. derivation lineage.

`ProtectedAssetRevision` binds those fields and the `AssetId` to a deterministic revision digest. There is deliberately no field-level replacement API. A competing revision is a complete alternative and receives a different revision digest. Reusing an old revision digest while substituting a digest, media property, provenance record, licence field or derivation entry fails with `serialization.asset_revision_mismatch`.

The revision digest is an integrity binding for the canonical record, not a replacement for `AssetId`. A caller can author a genuinely new complete revision and obtain a new revision digest; that is an explicit semantic replacement, not permission to merge fields into an already identified revision.

Target-private decoded/transcoded/cache derivatives remain downstream artifacts. They may refer to the protected source revision but cannot replace its canonical source digest, source identity/metadata, audio/media semantics, provenance, licence/attribution or derivation lineage.

## Record and shard model

Each top-level semantic locus is independently encoded as a record envelope:

- `thing:<ThingId>`;
- `relationship:<RelationId>`;
- `connection:<ConnectionId>`;
- `definition:<DefinitionId>`;
- `instance:<root ThingId>`;
- `known-unloaded:<ThingId>`;
- `asset:<AssetId>`.

The record envelope repeats its semantic key and record type. Deserialization requires the key, the embedded role-typed identity and the local shard index to agree before the record is admitted.

Records are assigned by SHA-256 of the semantic key to a prefix tree which splits until the selected target payload is reached or the record is indivisible. The v1 default target is 32 KiB, matching the SMX-022 evidence. This hash prefix, shard descriptor, local byte offset and record/shard digest are physical placement/integrity metadata only. Repacking may change them without changing any `ThingId`, `AssetId`, `DefinitionId`, `ConnectionId` or other canonical identity.

A shard contains a deterministic semantic-key-sorted index with exact offset, length and SHA-256 record digest plus the concatenated canonical record bytes. The root manifest lists shard descriptors in deterministic prefix order and binds every shard by digest and length. Missing, extra, moved, corrupted or mismatched records fail before canonical materialization.

## Migration and version envelope

The v1 root carries:

- canonical profile ID;
- physical schema version;
- shard-policy version;
- required feature set;
- stable `ProjectId` and `ProjectRevisionId`;
- complete shard descriptor set.

A newer unsupported schema, unknown required feature or incompatible profile fails with a typed error rather than being reinterpreted. The accepted v0 golden-envelope fixture differs only in physical envelope version; its semantic records are unchanged and the built-in `0 -> 1` migration is intentionally semantic-no-op evidence rather than an invented architecture rewrite.

`MigrationRegistry` is deterministic and bounded by a maximum step count. Migration receives cloned inert record maps, has no capability/host-service parameter, and must return a complete record set. The result is scanned again for forbidden transient identity fields, materialized into the SMX-023 role-typed model and passed through whole-project validation. `prepare_migration()` returns a candidate only after every stage succeeds. Publication of that candidate is intentionally outside this module and must occur atomically in SMX-025; a thrown migration therefore has no API path to partially mutate the active project revision.

## Transient and host identity exclusion

Durable values reject the SMX-021/023 transient identity classes when presented as field names, including NodePath/RID/ResourceUID/resource path identity, DOM identity, database row identity, cache keys, transport peer/socket/session/process handles and serialized capability tokens/grants. URLs may still exist as ordinary authored/provenance data where semantically appropriate; a URL is simply never promoted into SplashMX durable identity.

This is in addition to SMX-023 whole-document validation. Serialization is not a bypass around the semantic core.

## Adversarial and boundary evidence

`tests/production/test_smx024.py` covers the production implementation directly, including:

- full Thing/Connection/Definition/Instance/known-unloaded/protected-asset round-trip with stable IDs;
- insertion-order independence of canonical bytes;
- protected audio/media/provenance/licence/derivation preservation;
- partial protected-asset field mixing and target-private derivative substitution rejection;
- whole-revision asset replacement;
- shard corruption and missing-shard fail-closed behavior;
- unsupported schema version, required feature and profile failures;
- successful bounded v0 migration;
- failed and missing migration paths with no active-state mutation;
- hostile migration injection of transport identity;
- noncanonical integer forms, duplicate map keys, indefinite CBOR, unregistered tags, non-finite floats, negative zero and parser limits.

`tools/validate_smx024.py` statically binds the implementation, test, workflow, documentation and module manifest. `.github/workflows/smx024-canonical-serialization.yml` executes both the validator and the adversarial production suite on PRs and `main`.

## Architecture and downstream boundary

No Architecture-v1 amendment or ADR is required: implementation matched the selected SMX-022 mechanism and the frozen protected-media/identity/migration rules.

SMX-025 remains responsible for crash-consistent browser/native project ownership and atomic head publication using IndexedDB + prepared OPFS and SQLite WAL/FULL + prepared blobs. SMX-030 may repack/stream immutable shards but cannot make their placement semantic. SMX-035/040 may wrap these records in package/security containers but cannot weaken the protected revision. Collaboration and publishing may address/select canonical revisions, never field-mix them.
