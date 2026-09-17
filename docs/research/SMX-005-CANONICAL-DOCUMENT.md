# SMX-005 — Canonical document, identity, references, transactions, and migration

Status: candidate pre-architecture semantic contract for downstream lifecycle/security/collaboration falsification

Issue: SMX-005 / #5

Established: 2026-09-17

This document defines the current candidate for SplashMX's **engine-independent canonical authored-document model**. It deliberately does **not** freeze a production byte encoding, database implementation, package container, collaboration algorithm, Godot mapping, or final ID text representation.

The selected direction is a **typed logical record graph with stable semantic IDs, immutable revision/chunk lineage, sparse transactional patches, and content-addressed immutable blobs**. A human-readable JSON-shaped encoding is used only by the disposable SMX-005 harness. Future production encodings may be canonical CBOR, another binary schema, an embedded database working store, or a hybrid, provided they preserve this semantic contract.

The companion experiment under `experiments/smx-005-document-model/` and `SMX-005-DOCUMENT-FIXTURES.json` are non-normative evidence for the semantics below.

## Contents

| Section | Summary |
|---|---|
| 1. Research result | States the hybrid semantic document model and accepted invariants. |
| 2. Requirements inherited from SMX-001–004 | Extracts identity, composition, execution, migration, and security constraints. |
| 3. Compared representation families | Compares tree/JSON, schema-binary, embedded DB, content-addressed graph, and hybrid approaches. |
| 4. Canonical semantic planes | Separates authored document, live runtime state, persistent world/save state, and transient context. |
| 5. Identity domains and references | Defines which referents require durable IDs and how references remain path-independent. |
| 6. Record and chunk model | Defines logical records, catalogs, chunks, immutable revisions, and partial loading. |
| 7. Definitions, instances, behaviours, ports, and connections | Carries SMX-003/004 semantics into the canonical document. |
| 8. Assets and content addressing | Separates logical asset identity from immutable blob identity. |
| 9. Canonicalization and hashing | Defines semantic equality and deterministic-hash requirements without choosing final bytes. |
| 10. Validation and feature negotiation | Defines schema validation, required/optional features, and unknown data handling. |
| 11. Transactions, patches, and conflicts | Defines atomic ID-addressed edit transactions and preconditions. |
| 12. Versioning and migration | Defines pure staged migration, validation, rollback, and identity preservation. |
| 13. Partial loading and reference resolution | Distinguishes loaded, known-unloaded, tombstoned, and unknown targets. |
| 14. Security-sensitive parsing constraints | Defines parser/migration/resource limits handed to SMX-006. |
| 15. Corpus and executable evidence | Maps DT fixtures to the SMX-001 corpus. |
| 16. Architecture scorecard | Records evidence-backed scores and explicit N/E entries. |
| 17. Rejected/deferred alternatives | Records why no one encoding/store becomes the public contract. |
| 18. Downstream handoffs | Defines what SMX-006/007/008/011/013/014 may assume. |
| 19. Hypothesis status | Updates H-007/H-008/H-018. |
| 20. Comparative primary sources | Records external representation precedents used here. |

## 1. Research result

The current candidate separates the **semantic document contract** from any one physical encoding:

```text
SplashDocument[DocumentId]
├─ document schema/version + feature manifest
├─ catalog/index
│  ├─ durable record identity -> chunk/location/status
│  └─ immutable chunk/revision identity -> content digest
├─ authored logical records
│  ├─ Things
│  ├─ Definitions + immutable DefinitionRevisions
│  ├─ instance provenance + sparse overlays
│  ├─ BehaviourDefinitions + attachments/configuration
│  ├─ ports + connections + authored relations
│  ├─ asset metadata
│  └─ extension records
├─ immutable content-addressed blobs
│  └─ media/assets/large optional payloads
└─ optional edit history / transaction log
   └─ not required to reconstruct the current materialized document

Outside the authored document:
├─ live runtime state / executor queues
├─ persistent world/save state
└─ transient runtime/editor/network context
```

The central rule is:

> **Stable semantic identity belongs to logical authored entities; byte position, hierarchy path, database row number, chunk location, content hash, and engine handle do not.**

Content hashes are valuable for immutable blobs/revisions, but they do not replace logical identity for Things, definitions, ports, connections, attachments, or assets whose authored content can change while the entity remains conceptually the same.

### Canonical-document invariants

- **DOC-001 — identity is semantic and path-independent:** rename, regroup, reparent, chunk relocation, and encoding changes cannot alter durable logical identity.
- **DOC-002 — identity and content address are distinct:** mutable logical entities use stable IDs; immutable byte/content objects may additionally use digest identities.
- **DOC-003 — authored document, runtime state, world/save state, and transient context are separate planes:** projection between them is explicit.
- **DOC-004 — every durable cross-record reference targets a typed semantic ID/interface, never a hierarchy traversal path or physical offset.**
- **DOC-005 — definition/instance provenance and sparse overlays remain explicit:** materialization must not erase the base revision + authored override explanation.
- **DOC-006 — behaviour definitions/attachments are versioned authored records; live private state, PRNG position, timers, and continuations are runtime/save concerns unless explicitly snapshotted.**
- **DOC-007 — connections and exposed ports have stable identity independent of internal containment and chunk placement.**
- **DOC-008 — assets separate logical identity from immutable content identity:** an `AssetId` may point at a new verified blob without rewriting every authored reference.
- **DOC-009 — semantic equality is encoding-independent:** map/member order and physical record placement cannot change meaning.
- **DOC-010 — deterministic hashes/signatures require a specified canonicalization profile:** default serializer output is never assumed canonical.
- **DOC-011 — edits apply as atomic semantic transactions with explicit preconditions/conflicts; partial application is invalid.**
- **DOC-012 — migration is deterministic, staged, validated, and rollback-safe:** source remains intact until the target representation is fully valid.
- **DOC-013 — unknown required features fail closed; optional unknown extensions may be preserved opaquely only when their declared compatibility rules permit it.**
- **DOC-014 — partial loading is first-class:** a valid reference can target a known-but-unloaded record/chunk without becoming dangling or destroyed.
- **DOC-015 — absence states are distinguishable:** loaded, known-unloaded, tombstoned/deleted, unknown/missing, and incompatible are not conflated.
- **DOC-016 — parsers/migrations are resource-bounded and capability-free by default:** decoding data cannot itself acquire host authority.

## 2. Requirements inherited from SMX-001–004

SMX-005 must preserve accepted semantics from previous research.

### From SMX-002

- K-001/K-002/K-010 require identity independent of path, names, and engine handles.
- K-003/K-004 require containment and other relations to remain separate.
- K-005/K-006 require intrinsic declarations to remain separate from current runtime/editor grants/context.
- K-009 requires stable explicit interfaces.
- K-012 requires unresolved-but-valid references to absent/unloaded targets.

### From SMX-003

- `DefinitionId`, immutable definition revision, `ElementId`, concrete `ThingId`, and `PortId` are distinct semantic roles.
- instances retain base definition/revision provenance plus sparse explicit overlays.
- invalidated override/public-interface targets become explicit conflicts.
- public ports are stable indirections over internal element/port implementation endpoints.
- definition reconciliation is plan-before-commit and cannot leave half-migrated instances.

### From SMX-004

The document model must represent authored forms of:

- versioned behaviour definitions;
- stable behaviour attachment identity;
- private-state schema/version declarations;
- declared ports/capability requirements;
- validated bounded-turn IR or an independently addressable IR payload.

It must leave room for runtime/save representations of:

- live attachment private state;
- deterministic PRNG stream state/position;
- timers and continuations;
- ordered pending activations;
- service/network correlation state where lifecycle policy requires it.

Those runtime records are **not automatically part of the editable authored document**.

### Corpus pressure

Especially relevant cases:

- **C-006/C-012:** durable references survive reparenting and unloaded targets.
- **C-011/C-018/C-027:** nested reusable definitions, instance overrides, and exposed ports need stable semantic loci.
- **C-023/A-010/A-013:** old content and unknown future features require explicit version/migration policy.
- **C-024:** pending runtime work must not be confused with authored document state.
- **C-026:** missing/incompatible dependencies need explicit resolution states.
- **A-002:** unloaded and destroyed targets differ.
- **A-008:** definition structural update versus instance override requires transactional reconciliation.
- **A-012:** malformed/oversized input must fail safely.

## 3. Compared representation families

SMX-005 evaluates representation semantics first and encoding/storage second.

### 3.1 Human-readable JSON/tree document

Strengths:

- easy debugging, diffs, inspection, and tooling;
- natural fit for current semantic fixtures;
- JSON Schema can express substantial structural validation.

Weaknesses if used as the whole architecture:

- giant monolithic trees are poor partial-loading boundaries;
- references can tempt authors toward path traversal rather than IDs;
- duplicate/reordered maps and numeric edge cases complicate byte-level canonicalization;
- binary assets do not belong inline;
- naive generic JSON round-tripping may drop or reinterpret unknown typed extensions.

**Result:** useful author/debug/interchange projection; rejected as a reason to make the canonical semantic model one monolithic tree.

### 3.2 Schema-first binary messages (Protocol Buffers-like)

Strengths:

- compact, strongly schema-oriented records;
- good generated tooling;
- binary protobuf preserves unknown fields in ordinary binary parse/serialize flows.

Weaknesses as the public canonical contract:

- default protobuf serialization order/bytes are not a portable canonical hash contract;
- field-number evolution is an encoding concern, not the same as SplashMX semantic identity/versioning;
- binary message layout does not solve chunking, logical revisions, asset identity, edit transactions, or collaboration semantics;
- JSON/text conversion can lose protobuf unknown-field preservation guarantees.

**Result:** viable future record encoding candidate; rejected as the architecture itself.

### 3.3 Embedded database (SQLite-like application file)

Strengths:

- mature atomic transactions and crash recovery;
- indexing/querying suit large authoring documents;
- partial reads do not require parsing an entire monolithic tree;
- SQLite has a long-lived portable application-file format.

Weaknesses as the public semantic contract:

- table/row/schema layout would become accidental compatibility API if exposed directly;
- merge/diff/remix/share workflows need semantic records above SQL operations;
- browser/native implementation choices may differ;
- a working database file is awkward as the sole package/interchange representation.

**Result:** strong candidate for an editor working store/cache; rejected as the public semantic contract.

### 3.4 Content-addressed immutable graph

Strengths:

- immutable revisions/blobs are naturally deduplicated and integrity-checkable;
- hashes are useful package/cache/network distribution keys;
- partial fetching is natural when records/chunks are independently addressable.

Weaknesses if used for all identity:

- editing a Thing changes its content hash even when it remains the same logical Thing;
- every incoming reference would need rewriting or indirection on ordinary edits;
- user-facing identity/provenance becomes content-version identity;
- collaboration/tombstones need stable logical subjects across versions.

**Result:** selected for immutable blobs/chunks/revision payloads; rejected for mutable semantic identity.

### 3.5 Canonical CBOR or another deterministic binary encoding

CBOR is attractive because its standard explicitly separates generic data-model semantics from serialization choices and defines deterministic encoding requirements. It also supports binary byte strings directly.

Weaknesses/remaining questions:

- choosing CBOR now would still not answer the logical-record, transaction, migration, and partial-loading semantics;
- deterministic CBOR requires selecting and enforcing a profile rather than merely calling a generic encoder;
- human inspection/editing needs a diagnostic/projection path.

**Result:** strong future package/chunk encoding candidate; intentionally not frozen by SMX-005.

### 3.6 Selected hybrid semantic model

The candidate combines:

- stable typed logical IDs for mutable semantic records;
- immutable revision IDs for definition/document lineage;
- independently loadable chunks with a catalog;
- content-addressed immutable blobs for media/large payloads;
- semantic transactions/patches above physical storage;
- a versioned validation/feature envelope;
- encoding-specific canonicalization only where byte hashes/signatures are required.

**Result:** selected for downstream falsification.

## 4. Canonical semantic planes

A recurring source of corruption would be treating all project/runtime/save/editor data as one document. SMX-005 therefore makes four planes explicit.

### 4.1 Authored document

What creators intentionally authored and what must travel with the editable creation:

- Things and authored intrinsic/default state;
- definitions/revisions/elements;
- instance provenance/overlays/local additions/suppressions;
- authored facets and behaviour attachments/configuration;
- behaviour definitions/validated IR references;
- ports, connections, authored relations;
- asset metadata/references;
- capability requirements/policy declarations;
- editor metadata explicitly defined as portable authored metadata;
- format/schema/feature declarations.

### 4.2 Live runtime state

Current execution state created by playing the authored document:

- live mutable Thing state;
- behaviour-private state;
- PRNG state/position;
- timers/continuations/queues;
- active physics/simulation state;
- runtime-generated Things where the simulation owns them.

This may be snapshot-able, but it is not the authoring document by default.

### 4.3 Persistent world/save state

A policy-selected projection of runtime state intended to survive sessions:

- selected live Thing values;
- persistent runtime-created entities;
- durable gameplay/world progress;
- resumable pending work only when the lifecycle contract explicitly permits it.

A save references the authored creation/schema it belongs to and is a separate artefact.

### 4.4 Transient context

Never canonical authored state unless explicitly projected:

- current Godot Node/RID/resource handles;
- editor selection/hover/gizmo/cursor presence;
- active user/peer/controller/authority binding;
- current replication recipients/relevance;
- capability grants;
- cache/stream residency;
- active storage/network service handles;
- diagnostics/profiling counters.

## 5. Identity domains and references

### 5.1 IDs required by current semantics

The exact binary/text encoding remains open, but the following semantic identity domains are required.

| Identity | Purpose | Mutable content under same ID? |
|---|---|---|
| `DocumentId` | editable creation lineage | yes |
| `DocumentRevisionId` | immutable authored revision/transaction result | no |
| `ThingId` | concrete authored/logical Thing | yes |
| `DefinitionId` | reusable definition lineage | yes |
| `DefinitionRevisionId` | immutable definition revision | no |
| `ElementId` | stable semantic member inside definition lineage | yes across definition revisions |
| `PortId` | stable interface endpoint within its owning semantic scope | yes, subject to compatibility rules |
| `RelationId` | authored relationship identity when independently editable/referenced | yes |
| `ConnectionId` | durable authored port connection | yes |
| `BehaviorDefinitionId` | behaviour definition lineage | yes |
| `BehaviorRevisionId` | immutable behaviour definition/IR revision | no |
| `AttachmentId` | behaviour attachment on a concrete Thing/element | yes |
| `AssetId` | logical authored asset entry | yes |
| `BlobDigest` | immutable content bytes | no |
| `ChunkId` / `ChunkDigest` | logical/immutable independently loadable payload identity as chosen by implementation | depends on role |
| `TransactionId` | durable edit transaction/audit subject when history retained | no |
| `WorldSaveId` | persistent runtime/save artefact lineage | yes by new revisions, not in-place identity semantics |

Not every temporary implementation object requires a durable ID. IDs are justified when another durable record, history entry, collaboration operation, migration, package, or external reference must name the semantic subject independently of location/path.

### 5.2 ID properties

Durable IDs must:

- be opaque to ordinary authors;
- never derive from labels or containment paths;
- not be reused for a semantically different entity within the same identity namespace;
- survive physical chunk/database-row relocation;
- survive encoding change;
- survive rename/reparent/regroup where logical identity remains the same;
- remain distinct from content digests and engine/runtime handles.

SMX-005 does not choose UUID, ULID, integer, random 128-bit, namespaced hash, or another concrete encoding.

### 5.3 Typed durable references

A reference is conceptually:

```text
Reference
├─ target-kind / namespace
├─ target-id
├─ optional document/package qualification
└─ optional endpoint-id (for a port/interface reference)
```

A path may exist as UI/debug information but cannot be the durable locator.

### 5.4 Cross-document/package qualification

Local references may omit qualification only inside a scope where `DocumentId` is unambiguous. Portable components/packages need an explicit package/document dependency identity + target semantic ID. The final package/dependency addressing syntax belongs to SMX-013/014.

## 6. Record and chunk model

### 6.1 Logical records

Canonical semantics are described as typed records keyed by semantic IDs, not as required physical files/tables.

Examples:

- `ThingRecord[ThingId]`;
- `DefinitionRecord[DefinitionId]` + immutable `DefinitionRevisionRecord`;
- `InstanceRecord[root ThingId]`;
- `BehaviorRecord[BehaviorDefinitionId]` + immutable revisions;
- `ConnectionRecord[ConnectionId]`;
- `AssetRecord[AssetId]`;
- extension records.

### 6.2 Catalog

A document catalog/index must be able to answer, without loading every record:

- does this semantic ID exist in this document/revision?
- what type is it?
- which chunk/payload contains it?
- is it intentionally tombstoned/deleted?
- which schema/features are required to decode the containing chunk?
- what integrity digest is expected where applicable?

The catalog itself can be implemented as a small manifest, DB index, package table, or another structure.

### 6.3 Chunks

A chunk is an independently loadable group of authored records chosen for locality/performance/packaging. Chunk placement is **not semantic identity**.

Moving a Thing from `chunk:town-a` to `chunk:town-b` cannot alter its `ThingId` or incoming references.

Chunk boundaries may follow scenes/regions/components for convenience, but they are not required to equal those author-facing concepts.

### 6.4 Immutable revisions

`DocumentRevisionId`, `DefinitionRevisionId`, and `BehaviorRevisionId` identify immutable revision results. A revision may optionally have a content digest for cache/integrity purposes. The semantic revision ID and digest need not be the same mechanism.

This lets collaboration/migration/history refer to a stable revision subject without making the whole mutable document content-addressed.

## 7. Definitions, instances, behaviours, ports, and connections

### 7.1 Definition representation

A definition revision contains stable `ElementId` keyed authored elements plus relations/ports expressed with element/port IDs. Definition records point to revision lineage/head according to authoring/history policy.

### 7.2 Instance representation

An instance retains:

```text
root ThingId
base DefinitionId
base DefinitionRevisionId
ElementId -> ThingId provenance map
OverlaySet
local additions/suppressions
```

A materialized player form may cache inherited values, but the canonical editable form cannot erase the provenance/overlay explanation.

### 7.3 Overlay operations

Overlay loci are semantic, for example:

- `(ElementId, state-key)`;
- `(ElementId, facet-attachment-id, property-key)`;
- `(RelationId or relation semantic key)`;
- public-interface binding;
- local addition/suppression.

They are not JSON Pointer/file offsets/tree paths by contract. A physical JSON projection may encode those loci however it likes.

### 7.4 Behaviour definitions and attachments

Authored document records include:

- behaviour definition lineage/revision ID;
- validated bounded-turn IR payload or independently referenced IR chunk;
- declared public/private state schema;
- required/provided ports;
- capability requirements;
- stable attachment IDs and authored attachment configuration.

Live private state/timers/continuations are runtime or save/snapshot records, not silently embedded into the authored attachment record.

### 7.5 Ports/connections

`PortId` is stable within its semantic owner. `ConnectionId` records source/target semantic endpoints. A connection survives internal reparenting and chunk relocation; a definition public port may rebind compatible internal implementation while preserving the external endpoint ID.

## 8. Assets and content addressing

Large immutable bytes are where content addressing is most valuable.

### 8.1 Logical asset record

```text
AssetRecord[AssetId]
├─ media/type metadata
├─ author-facing label/import metadata
├─ BlobDigest
├─ byte length
├─ optional dimensions/duration/etc.
└─ compatibility/processing metadata
```

Things reference `AssetId`, not a filename or raw digest directly by default.

### 8.2 Immutable blob

`BlobDigest` addresses exact bytes. It supports:

- integrity verification;
- deduplication;
- cache/CDN distribution;
- package reuse;
- streaming.

Updating the image/sound behind the same authored logical asset can create a new blob and transactionally update the `AssetRecord` without rewriting every Thing reference.

### 8.3 Security

Digest verification does not make content safe to decode. Media parsers still need normal sandbox/resource constraints. Declared byte length/compression limits must be checked before unbounded allocation/decompression.

## 9. Canonicalization and hashing

### 9.1 Semantic canonicalization

The semantic model treats map/member order and physical record order as non-semantic unless a specific field is explicitly an ordered sequence.

A semantically equivalent document encoded with different map insertion order must compare equal after decoding/validation.

### 9.2 Byte canonicalization

When bytes are hashed/signed/deduplicated as a canonical object, the encoding profile must define at least:

- map-key ordering;
- integer representation/range;
- floating-point handling including NaN/Infinity/negative zero policy;
- Unicode normalization policy if any;
- duplicate-key rejection;
- string/binary distinction;
- omission/default rules;
- extension/tag encoding;
- numeric type preservation.

Generic serializer output is not enough.

The research harness uses a deliberately narrow deterministic JSON projection (`UTF-8`, sorted keys, compact separators, finite JSON-compatible values) to test the concept. It is **not** the selected production encoding.

### 9.3 Why protobuf bytes are not logical IDs

Protocol Buffers explicitly warns that field serialization order/default bytes are not a portable stable contract. Therefore SplashMX must never derive logical entity/revision identity merely from unspecified protobuf serializer bytes.

### 9.4 CBOR candidate

RFC 8949 defines deterministic CBOR encoding requirements, making a constrained CBOR profile a credible future chunk/package canonicalization option. Selection remains SMX-014/Architecture-v1 work after browser/runtime measurements.

## 10. Validation and feature negotiation

### 10.1 Validation layers

Loading proceeds conceptually through:

1. **container/framing validation** — size, integrity, decompression/path safety;
2. **syntactic decoding** — valid chosen encoding;
3. **structural schema validation** — required record shapes/types/ID syntax constraints;
4. **referential validation** — namespace/type/endpoint consistency;
5. **feature negotiation** — supported required/optional features;
6. **semantic validation** — definition/overlay/IR/capability contracts;
7. **migration if required**;
8. **post-migration validation** before materialization/execution.

No executable behaviour runs during parsing/migration validation.

### 10.2 Schema/version envelope

A document/revision declares at least conceptually:

```text
format_family = "SplashMX"
schema_version = <semantic version/monotonic schema ID>
required_features = {...}
optional_features = {...}
extensions = {...}
```

Exact version numbering is not frozen here.

### 10.3 Unknown fields versus unknown features

Unknown bytes/fields and unknown semantics are different problems.

- Unknown **optional extension data** may be preserved opaquely when its envelope says it is safe to ignore for current semantics.
- Unknown **required feature semantics** must reject normal editable/play execution rather than being silently ignored.
- Unknown data in a record whose meaning affects identity, security, migration, execution, or relationships cannot be assumed optional merely because the decoder can skip it.

### 10.4 Preservation

An editor that opens a document in a compatibility/read-only/preserve mode should retain unrecognized optional extension records byte-for-byte or semantically losslessly where the encoding permits. A read-modify-write operation must not silently strip them.

## 11. Transactions, patches, and conflicts

### 11.1 Transaction is semantic, not storage-specific

A `Transaction` conceptually contains:

```text
TransactionId
base DocumentRevisionId / relevant base revisions
ordered semantic operations
preconditions
optional author/time/history metadata
```

The physical store may implement the commit with SQLite, an append log, file replacement, CRDT integration, or another mechanism.

### 11.2 Operation targets

Operations address stable semantic subjects/loci, e.g.:

- create/remove/tombstone record by typed ID;
- set authored state/facet property on `ThingId`/`ElementId`;
- add/remove/update typed relation by ID;
- bind/rebind stable public port;
- update an `AssetRecord` to a new blob digest;
- add/update instance overlay operation;
- advance definition/behaviour revision with explicit reconciliation;
- change feature/extension declaration.

File paths, JSON offsets, array indices, and DB row IDs are not the semantic patch language.

### 11.3 Preconditions

Operations may require facts such as:

- record exists/does-not-exist;
- current record revision/hash equals expected;
- base definition revision equals expected;
- port type/interface signature remains compatible;
- no protected inbound references exist before deletion.

If a precondition fails, the transaction conflicts/rejects rather than partially applying.

### 11.4 Atomicity

Plan/validate all operations first. Commit all or none. This directly carries SMX-003 reconciliation semantics into the document layer.

### 11.5 Patch versus current state

A patch/transaction log is useful for history/collaboration but is not required to be replayed from genesis to understand the current document. The materialized canonical state remains independently valid/checkpointable.

SMX-011 decides how concurrent transactions merge/rebase/transform. It may reuse these semantic operation loci rather than inventing path-based edits.

## 12. Versioning and migration

### 12.1 Migration contract

A schema/IR migration is a versioned deterministic transformation:

```text
(source schema/features, validated source records)
    -> migrated records + migration report
    -> validate target schema/features
    -> atomic commit to new revision/package
```

### 12.2 Required properties

Migration must:

- never mutate the only source copy before success;
- be capability-free/pure by default;
- have explicit source and target version ranges;
- be deterministic for the same input;
- preserve durable semantic IDs unless the migration explicitly declares an unavoidable ID remap;
- rewrite all affected references atomically if an ID remap is required;
- preserve compatible optional unknown extensions;
- reject unsupported required features explicitly;
- be resource-bounded;
- produce diagnostics/reporting for changed/dropped/unsupported semantics;
- validate the complete target before replacing/advancing the source revision.

### 12.3 Migration chaining

A runtime/editor may chain migrations across multiple versions. The migration graph must avoid ambiguous competing paths without explicit precedence/version rules. Tests should retain golden fixtures for old supported versions.

### 12.4 Behaviour IR migration

Document schema migration and behaviour-IR migration are related but distinct. A document migrator may invoke a pure versioned IR migrator when a `BehaviorRevision` encoding/semantics change. It cannot execute arbitrary behaviour code as part of migration.

### 12.5 Engine upgrades

Because the canonical model does not use Godot Node/resource IDs as public semantics, an underlying Godot upgrade should ordinarily require a runtime adapter change, not a content rewrite. When semantics genuinely change, an explicit SplashMX migration handles it. SMX-009/015/020 must test this assumption.

## 13. Partial loading and reference resolution

### 13.1 Catalog-first resolution

A loader may know an ID exists and which chunk contains it without loading that chunk. This supports C-012 directly.

### 13.2 Reference states

A resolved/reference API must be able to distinguish at least:

- `loaded` — target materialized and compatible;
- `known_unloaded` — catalog confirms the target exists but its chunk is absent/not loaded;
- `tombstoned` — target identity is known to have been intentionally deleted/destroyed in the relevant lineage;
- `unknown` — no catalog/tombstone evidence for the ID;
- `incompatible` — target exists but required schema/feature/type/interface cannot be used;
- `dependency_unavailable` — target lies in an external package/dependency not currently available.

Exact product-facing names remain open.

### 13.3 Unloaded references are valid

`known_unloaded` is not a validation error. The caller may request streaming, wait, display a placeholder, or perform a logic path defined for absent residency.

### 13.4 Tombstones

SMX-005 requires the canonical model to *support* a durable tombstone/deletion marker where history/collaboration/lifecycle requires it, but SMX-007/011 decide when tombstones are created, retained, compacted, or considered terminal runtime destruction.

## 14. Security-sensitive parsing constraints

SMX-006 may assume SMX-005 requires these parser/migration hooks.

### 14.1 Before allocation/decoding

Enforce configured bounds on:

- container/package total size;
- compressed and expanded size;
- record/chunk count;
- string/binary field size;
- nesting/depth;
- map/array lengths;
- integer/numeric ranges;
- declared asset size;
- migration steps/chains.

### 14.2 Strict decoding

- reject malformed encodings;
- reject duplicate semantic IDs;
- reject duplicate map keys where the encoding permits ambiguity;
- reject type/namespace mismatches;
- never interpret filenames/labels/IDs as filesystem paths;
- validate digests before trusting blob identity;
- do not resolve external URLs during mere document validation;
- do not execute behaviour or host services while parsing/migrating.

### 14.3 Migration sandbox

Migration code must use a constrained pure transformation API or equivalent trusted runtime implementation. User/community documents cannot inject migration code that gains host authority.

### 14.4 Resource exhaustion

Referential validation must not follow unbounded recursive graphs naively. Cycle/depth-safe indexes and bounded passes are required. Unknown extension preservation must also be size-bounded.

## 15. Corpus and executable evidence

The companion fixture manifest is `docs/research/SMX-005-DOCUMENT-FIXTURES.json`.

Direct executable coverage:

| Fixture | Cases | Observation |
|---|---|---|
| DT-001 | C-006/A-001 | rename/reparent/chunk relocation preserve ThingId and durable reference target. |
| DT-002 | C-012/A-002 | catalog resolves a referenced target as `known_unloaded`, distinct from tombstone/unknown. |
| DT-003 | C-018/A-008 | definition revision, provenance map, and sparse instance overlay round-trip intact. |
| DT-004 | C-011/C-027 | stable public PortId/ConnectionId survives internal containment/chunk restructure. |
| DT-005 | C-025 | behaviour definition revision + attachment identity round-trip independently of live private state. |
| DT-006 | C-023/A-010 | schema v1 -> v2 deterministic migration preserves IDs/references and optional extension payload. |
| DT-007 | A-008 | semantic transaction precondition failure rolls back every planned edit. |
| DT-008 | C-023/A-010 | unknown required feature is rejected; unknown optional extension is preserved. |
| DT-009 | C-026/A-002 | dependency-unavailable reference remains distinct from local unknown/tombstoned target. |
| DT-010 | C-023 | deterministic research canonicalization produces identical bytes for semantically identical map orderings. |
| DT-011 | C-011 | AssetId remains stable while verified BlobDigest changes transactionally. |
| DT-012 | A-012 | duplicate IDs, digest mismatch, oversized declared payload, and invalid record kinds fail validation. |

### Not proven here

- final production byte encoding;
- browser/native performance of a selected encoding/store;
- collaboration convergence/CRDT/OT semantics;
- lifecycle tombstone retention/destruction policy;
- streaming scheduler/relevance policy;
- package signing/distribution format;
- end-to-end old-Godot-to-new-Godot compatibility;
- hostile parser implementation memory-safety.

## 16. Architecture scorecard

Candidate: typed logical record graph + immutable revision/chunk lineage + content-addressed blobs

Direct cases exercised: C-006, C-011, C-012, C-018, C-023, C-025, C-026, C-027

Adversarial variants: A-001, A-002, A-008, A-010, A-012

| Score | Assessment |
|---|---|
| S-01: 2 | Stable IDs/records can remain hidden from beginners; editor UX not yet tested. |
| S-02: 3 | One semantic record/reference model covers object/media/definition/behaviour/assets. |
| S-03: 3 | Identity/reference/transactions do not derive meaning from hierarchy. |
| S-04: 3 | Rename/reparent/chunk relocation/unloaded-target cases use stable typed IDs. |
| S-05: 2 | Behaviour definitions/attachments represented coherently; execution proven separately in SMX-004. |
| S-06: 2 | Runtime/save/document planes are explicit; full lifecycle restore remains SMX-007. |
| S-07: 3 | Catalog/chunk model represents known-unloaded targets and partial loading. |
| S-08: 2 | Strict parsing/migration/resource hooks are specified; hostile implementation testing remains SMX-006/016. |
| S-09: N/E | Network topology not tested. |
| S-10: 2 | Semantic transaction loci/base revisions are collaboration-ready inputs; convergence not tested. |
| S-11: 3 | Version/features/migration/unknown-required handling are explicit and executable in research harness. |
| S-12: 3 | Canonical semantics contain no Godot Node/resource/path contract. |
| S-13: 3 | Dependency-free deterministic fixtures test round-trip/reference/transaction/migration invariants. |
| S-14: N/E | Encoding/store performance is intentionally not selected/benchmarked. |
| S-15: 3 | unloaded/tombstoned/unknown/incompatible/dependency-unavailable and feature failures are explicit. |
| S-16: 2 | semantic model can project to simple authoring but editor continuity remains SMX-012/019. |

Hard-gate failures observed in SMX-005 scope: **none**.

## 17. Rejected or deferred alternatives

### Godot `.tscn`/Resource/PCK as canonical authored semantics

Rejected as the public compatibility contract.

They remain useful substrate/packaging implementation facilities, but using Godot node/resource identity/paths as canonical SplashMX identity would contradict D-002/D-010 and make migration/partial loading/collaboration engine-version coupled.

### One giant JSON file

Rejected as an architectural requirement.

A JSON projection is useful for debugging/fixtures, but a monolith would make independent streaming, large assets, record-level transactions, and editor working-set management unnecessarily difficult.

### Protobuf message bytes as universal revision/content identity

Rejected.

Protobuf is a viable future encoding, but its documented default serialization is not a globally stable canonical byte contract, and a message schema does not define SplashMX logical identity/transaction semantics.

### SQLite file as the interchange/public contract

Rejected as the semantic contract, retained as a possible working-store implementation.

Editor-local transactional/indexing benefits are substantial, but package/web/native portability and semantic diffs must remain above SQL/table layout.

### Entire mutable document as content-addressed DAG

Rejected for logical identity.

Content addressing is selected for immutable blobs/chunks/revisions, not for the mutable Thing/definition/asset identities that incoming references must survive across edits.

### Path-addressed JSON Patch as canonical edit language

Rejected.

A physical JSON patch may be used inside one encoder implementation, but stable semantic edit operations target IDs/loci; tree paths/array indices cannot be the durable collaboration/migration contract.

## 18. Downstream handoffs

### SMX-006 — security/capability sandbox

May assume:

- staged validation layers before execution;
- explicit required/optional feature negotiation;
- parser/migration size/depth/count hooks;
- no behaviour execution during parse/migration;
- content digest verification hooks;
- strict duplicate ID/type/reference validation;
- migration code must not come from untrusted document-native arbitrary code.

Must decide/enforce exact quotas, package/container attack handling, signature/trust policy, parser implementation hardening, capability grants/delegation, and host sandboxing.

### SMX-007 — lifecycle/save/restore

May assume distinct authored document/runtime/save planes and stable semantic IDs. Must define which runtime state is projected to snapshots/saves, tombstone lifetime/destruction semantics, pending continuation persistence, restore side effects, and save/document version coupling.

### SMX-008 — streaming

May assume catalog/chunk location is non-semantic and `known_unloaded` is a valid reference state. Must choose streaming granularity, dependency acquisition, eviction/residency, reference callbacks, and hot component/chunk replacement policy.

### SMX-011 — collaboration

May reuse semantic Transaction/operation loci, stable IDs, immutable base revisions, and explicit conflicts. Must define concurrent merge/rebase/CRDT/OT behavior and user-visible conflict semantics rather than treating sequential transaction semantics as convergence.

### SMX-013/014 — components/packages/publishing

May use logical IDs + immutable blob/chunk digests + feature manifests. Must choose package/dependency namespace, signatures, distribution addressing, final byte/container encoding, and generic-player negotiation.

## 19. Hypothesis status

### H-007 — SplashMX should own the canonical document format

**Strengthened.**

SMX-005 maps Things, definitions/revisions/elements, overlays, behaviour definitions/attachments, ports/connections, transactions, migration, partial loading, and assets into an engine-independent semantic record model. No tested requirement benefits from making Godot scene/resource serialization the public contract.

This remains subject to SMX-009 Godot mapping and SMX-015 destructive integration.

### H-008 — stable identity must be path-independent

**Strengthened further.**

The document/transaction/partial-load harness exercises rename, reparent, chunk relocation, unloaded target resolution, instance provenance, and public-interface stability without path repair. Exact final ID encoding remains intentionally open.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened at the schema/document layer; unresolved end-to-end.**

Deterministic staged schema migration with source/target validation, identity/reference preservation, unknown optional extension retention, and required-feature rejection is executable in the research harness. Actual migration across future Godot/runtime semantic changes remains for SMX-009/015/020.

No other hypothesis receives a status change from SMX-005.

## 20. Comparative primary sources

These are comparison inputs, not selected dependencies or final format choices.

### JSON Schema

- https://json-schema.org/specification

The current published family is Draft 2020-12. JSON Schema demonstrates a useful separation between a generic document representation and explicit structural/semantic validation metadata.

### Protocol Buffers

- https://protobuf.dev/programming-guides/editions/
- https://protobuf.dev/programming-guides/encoding/

Protobuf preserves unknown fields in ordinary binary message workflows, but its documentation explicitly warns not to assume stable/default serialization byte ordering across implementations/versions. This supports separating schema evolution from canonical hash identity.

### SQLite application-file/transaction precedent

- https://sqlite.org/appfileformat.html
- https://sqlite.org/fileformat.html

SQLite demonstrates durable cross-platform application files and atomic transactions/crash recovery, making it a credible editor working-store candidate without making SQL table layout SplashMX semantics.

### CBOR

- https://www.rfc-editor.org/rfc/rfc8949.html

RFC 8949 defines a generic data model, extensibility, validity/evolution layers, streaming considerations, and deterministic encoding requirements. A constrained deterministic CBOR profile is therefore a credible future package/chunk encoding candidate.

## Research disposition

SMX-005 **does not select a final byte encoding**. It selects the semantic compatibility boundary that any future JSON/CBOR/Protobuf/database/hybrid implementation must preserve.
