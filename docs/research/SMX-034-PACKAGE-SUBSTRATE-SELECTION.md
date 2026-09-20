# SMX-034 — package resolver, bounded bundle and distribution selection

**Status:** selected production handoff for SMX-035; implementation spike, not the production package module  
**Issue:** SMX-034 / #59  
**Date:** 2026-09-20  
**Authority:** Architecture v1.0 + SMX-013 + SMX-016 + SMX-024 + SMX-027 + SMX-030  
**Executable evidence:** `experiments/smx-034-package-spike/` and `SMX-034-PACKAGE-SUBSTRATE-FIXTURES.json`

## Contents

| Section | Summary |
|---|---|
| 1. Result | Selects the v1 requirement grammar, resolver family, SPB1 bundle and catalog boundary. |
| 2. Frozen semantics inherited | States the package semantics this selection may not redefine. |
| 3. Version and requirement syntax | Chooses a deliberately small SemVer-based authoring surface. |
| 4. Resolver mechanism | Chooses a bounded deterministic PubGrub-family resolver for intentional resolve/update only. |
| 5. SPB1 package bundle | Chooses a pathless deterministic-CBOR index over tightly packed immutable blobs. |
| 6. Catalog/distribution/trust seam | Keeps repository discovery and trust transport out of package identity and runtime authority. |
| 7. Security and capability boundary | Defines parser/resource limits and forbids ambient install authority. |
| 8. Protected source/audio/provenance | Preserves the complete protected Asset revision invariant. |
| 9. Alternatives rejected | Records why generic archives, OCI images, SAT-first and naive DFS are not the v1 default. |
| 10. Falsification evidence | Maps adversarial cases to the spike and fixtures. |
| 11. SMX-035 handoff | Defines exactly what production implementation must build and what remains deferred. |

## 1. Result

SMX-034 selects the following production substrate for the first package implementation:

```text
human package requirement
  exact: =X.Y.Z
  caret: ^X.Y.Z
        |
        v
bounded deterministic PubGrub-family resolve
  - one exact PackageRevisionId per PackageId
  - highest compatible non-revoked release in a frozen CatalogSnapshot
  - hard package/depth/byte/solver-work limits
  - explicit required / optional fallback / lazy semantics
        |
        v
exact project resolution lock
  PackageId + PackageRevisionId + manifest digest
  + exact artifact digests/sizes/features/dependency descriptors
        |
        v
acquire exact descriptor through a trusted host repository adapter
        |
        v
SPB1 bounded package bundle
  fixed framing + deterministic-CBOR index + raw immutable blobs
  no paths, extraction, links, install scripts or v1 compression
        |
        v
verify -> bounded parse -> semantic validation -> capability policy
-> stage/migrate -> atomic publication
```

The **resolution lock, not the catalog, registry URL, cache contents or a version range, is the runtime dependency authority**. Streaming/offline/runtime code consumes exact locked descriptors only. Resolution occurs only during an explicit install/update/resolve transaction.

This is an implementation choice below Architecture v1. It does not amend the frozen object, package, capability, lifecycle, publishing or protected-media semantics.

## 2. Frozen semantics inherited

SMX-034 preserves the accepted SMX-013 `PKG-001`–`PKG-028` contract and the later production boundaries:

- `PackageId`, `PackageRevisionId`, human version, `DefinitionId`, `ThingId`, artifact digest and repository location remain different roles.
- A package is the distribution boundary around the ordinary Definition/Thing system; it is not a second runtime object model.
- Runtime/streaming/offline use never consumes a floating requirement.
- One exact revision per `PackageId` per creation remains the v1 rule; incompatible transitive requirements are an explicit conflict.
- Required closure is staged atomically. Optional failure uses only a declared fallback. Lazy dependencies never become hidden synchronous loads.
- Cache placement and package-container layout are non-semantic.
- Capability requests are declarations attributed to the requesting component principal. Packages do not serialize grants, delegation roots, host handles or ambient authority.
- Trust, publisher identity, source availability, remix policy, provenance and licence are policy/evidence inputs; none grants execution capability.
- Update/migration is prepare-before-publish and rollback-safe.
- SMX-030 exact acquisition and known-unloaded semantics remain authoritative once a lock exists.
- SMX-027 performs live grant/delegation/revocation checks and the final authorization recheck at trusted host use.

## 3. Version and requirement syntax

### Selected v1 surface

`human_version` uses the **SemVer 2.0.0 ordering model**, but the initial SplashMX package-author requirement language is intentionally smaller:

- `=X.Y.Z` — one exact normal release;
- `^X.Y.Z` — compatible release interval using the conventional left-most-nonzero boundary;
- normalized decimal triplets only for v1 package requirements;
- no wildcard, OR-set, free comparator chain, tag, branch, URL, path dependency or implicit `latest` syntax.

For the initial surface:

- `^1.2.3` means `>=1.2.3,<2.0.0`;
- `^0.2.3` means `>=0.2.3,<0.3.0`;
- `^0.0.3` means exactly the compatible interval below `0.0.4`.

SemVer prerelease/build labels are **not silently accepted by the v1 author requirement parser**. SMX-035 may add exact prerelease support only if it can do so without changing lock identity or compatibility semantics; otherwise it remains a later product extension. This restriction is deliberate: author-facing dependency syntax should not inherit the full accidental complexity of developer package managers before a real creative-component corpus demonstrates need.

SemVer version intent remains advisory. SplashMX semantic compatibility checks still validate stable ports/properties, required schema/IR/features, overlays, migrations, protected assets and capability closure. A publisher's `1.4.0` label cannot waive an incompatible SplashMX interface change.

Primary reference checked 2026-09-20: <https://semver.org/>. SemVer 2.0.0 also requires released version contents not be modified; SplashMX strengthens this with exact immutable revision and digest identity.

## 4. Resolver mechanism

### Selection: deterministic bounded PubGrub family

The production resolver should use a **PubGrub-family conflict-driven version-solving algorithm**, adapted to SplashMX's deliberately smaller requirement language and one-version-per-`PackageId` policy.

Rationale:

- PubGrub directly models package ranges and mutual exclusion of package versions.
- It learns from incompatibilities rather than repeatedly traversing the same naive-backtracking dead ends.
- Its derivation graph supports actionable conflict explanations in author vocabulary.
- The algorithm naturally matches the current one-version-per-package rule.
- Resolution remains a planning operation; no package code executes while solving.

The Dart pub design document explicitly describes the version-solving problem as NP-hard and explains PubGrub's conflict-driven learning and backtracking. That means **algorithm choice does not remove the need for hard work bounds**. SplashMX must enforce them independently.

Primary reference checked 2026-09-20: <https://github.com/dart-lang/pub/blob/master/doc/solver.md>.

### Deterministic policy

Given the same immutable `CatalogSnapshot`, root requirements and policy snapshot, resolution must produce the same result or the same typed failure. The selected policy is:

1. discard revisions quarantined/revoked for new activation by the supplied policy snapshot;
2. select the highest compatible normal release;
3. when choosing which unresolved package to decide next, prefer the narrowest candidate set then stable `PackageId` order;
4. permit only one selected exact revision per `PackageId`;
5. retain an explanation/derivation for conflicts;
6. freeze an exact lock only after the entire candidate closure validates.

Lexical `PackageId` here is only a deterministic **solver tie-break**. It is not Thing identity, runtime scheduling order, behavioural ownership or a network authority rule.

### Mandatory independent bounds

SMX-035 must make these configurable but finite:

- maximum dependency depth;
- maximum selected package count;
- maximum catalog rows inspected per package and total;
- maximum candidate manifest bytes and declared artifact bytes;
- maximum dependency/feature fanout;
- maximum solver decisions/incompatibilities/backtracks or equivalent work unit;
- maximum diagnostic derivation size.

Exceeding a bound produces typed `package.resource_exhausted`; it never disables the bound or falls back to an unbounded algorithm.

### Required / optional / lazy

- **required:** absence/incompatibility blocks the candidate lock;
- **optional:** absence/incompatibility selects only the manifest-declared fallback and cannot perturb another required revision into an incompatible selection;
- **lazy:** the dependency requirement remains explicit and is resolved/acquired through the same bounded mechanism when demanded; ordinary runtime code cannot perform a hidden synchronous registry lookup.

The spike uses bounded deterministic DFS only as a **reference/falsification implementation** for these observable outcomes. It is explicitly not the production algorithm selected by this section.

## 5. SPB1 package bundle

### Selection

The v1 transport/container is **SplashMX Package Bundle v1 (`SPB1`)**. It is deliberately not a filesystem archive.

Physical shape:

```text
fixed header
  magic = "SPB1"
  deterministic-CBOR index byte length
  payload byte length

canonical deterministic-CBOR index
  schema = splashmx.package-bundle/1
  entries[]
    kind
    offset
    length
    sha256 digest

payload
  exact immutable blob bytes, tightly packed in index order
```

The index reuses `splashmx.deterministic-cbor/1`, already implemented and adversarially tested by SMX-024. RFC 8949 remains the underlying CBOR standard; SplashMX's stricter profile rejects indefinite forms, duplicate map keys, unregistered tags, non-finite numbers and noncanonical encodings.

Primary reference checked 2026-09-20: RFC 8949, <https://www.rfc-editor.org/rfc/rfc8949>.

### Deliberately absent from SPB1 v1

There are no:

- filesystem paths or extraction roots;
- `..`, absolute path, drive-prefix or separator normalization questions;
- symlinks, hardlinks, devices or executable mode bits;
- nested archive semantics;
- install scripts/hooks;
- arbitrary native/GDScript/JavaScript execution metadata;
- compression methods in v1.

No-compression is an intentional initial security/complexity choice. Distribution-level HTTP/content encoding or a later independently bounded per-entry codec may optimize transfer, but decoded byte limits and digest verification must precede publication. Adding compression to SPB1 itself requires new decompression-bomb/resource tests and cannot weaken R-016-01.

### Parser invariants

Before any semantic activation, the parser must:

- bound total input before allocation;
- validate the fixed header and exact declared lengths;
- bound index bytes, item count, nesting and string sizes through the SMX-024 decoder;
- require the closed index schema;
- require tightly packed, non-overlapping, in-range entries;
- bound each entry and total payload bytes;
- reject duplicate/invalid digests;
- hash every entry and require exact digest equality;
- reject unindexed trailing payload bytes.

Because SPB1 has no path-bearing extraction semantics, the preferred design removes the dominant archive traversal/collision class rather than depending on platform-specific path normalization to save it later. R-016-01 still remains a required regression for any future external import format that does carry paths.

### Identity

`PackageRevisionId` is semantic package revision identity. SPB1 offsets, cache keys, repository URLs and a bundle transport digest are not substitutes for it. The exact resolution lock records semantic revision identity plus canonical manifest/artifact digests and byte bounds. Implementations may additionally record a bundle digest as an acquisition optimization, but changing repository/container placement cannot rewrite package/object identity.

Production publication should canonicalize SPB1 entry ordering (manifest first, then deterministic artifact order) so equivalent output is reproducible. Reproducibility is useful evidence; it is still not permission to derive `PackageId` from a file path or URL.

## 6. Catalog, distribution and trust seam

SMX-034 selects a **CatalogSnapshot interface**, not a public marketplace or hosted service.

A resolver input snapshot contains bounded immutable rows equivalent to:

```text
CatalogSnapshot
  catalog_schema
  repository/trust-domain descriptor        # policy context, not package identity
  snapshot version/freshness context
  rows
    PackageId
    human_version
    PackageRevisionId
    manifest digest + byte bound
    exact bundle/artifact acquisition descriptors
    revocation/quarantine/deprecation status
```

The repository adapter may be local, removable media, LAN, hosted HTTP, marketplace-backed or something else later. The resolver sees the frozen snapshot, not an ambient network handle. Friendly names/search rankings/registry URLs/CDN URLs are discovery/transport metadata and **must not enter canonical package identity**.

### Trust selection boundary

SMX-034 selects the requirement that remote catalog/update metadata support **authenticated snapshot/freshness/rollback/mix-and-match defenses** and exposes those outcomes as policy input. It deliberately does **not** select final root-key ceremony, signature algorithms, transparency service or revocation deployment: those are owned by SMX-039/040.

The Update Framework is the primary implementation precedent because it explicitly models versioned/fresh repository metadata and rollback/freeze/mix-and-match defenses. The current TUF specification index lists v1.0.33 as latest when checked 2026-09-20: <https://theupdateframework.io/spec/>. SMX-039 may select TUF directly or an equivalently evidenced mechanism; either choice remains outside `PackageId` and outside runtime capability authority.

## 7. Security and capability boundary

Package installation/resolution is a data-planning operation, not an execution privilege.

### No ambient install authority

A package manifest may declare dependencies, required features, capability **requests**, provenance/licence/remix data and exact artifacts. It may not carry or trigger:

- install/postinstall scripts;
- arbitrary shell/process execution;
- native extensions;
- GDScript/browser JavaScript execution;
- raw filesystem extraction;
- arbitrary URL fetches from package-controlled code;
- serialized capability grants/tokens/delegation roots;
- host/session/process handles.

Acquisition is a trusted host-service operation requested with an exact immutable descriptor under current repository/network policy. Parsing/migration is bounded and capability-free. Activation remains behind SMX-027 capability evaluation and final-use authorization.

### Trust is not capability

A valid signature, well-known publisher, included source, permissive licence or strong provenance may affect repository/update policy. None grants `network.http`, filesystem, device, process, native-code or any other host capability. The package principal still receives zero ambient authority.

## 8. Protected source/audio/provenance

SMX-034 retains the Architecture-v1 protected-media contract without modification.

A stable `AssetId` selects one complete immutable revision containing:

- revision/content digest;
- source digest and logical source identity;
- exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution;
- derivation lineage.

SPB1 may carry bytes representing that record and its exact source/artifact bytes, but container fields do not become canonical Asset meaning. Resolver, bundle parser, registry metadata, cache, package update, migration or target import/transcode may not combine fields from competing Asset revisions. A partial protected bundle is invalid; a replacement is another complete immutable alternative.

Source availability, provenance and licence remain orthogonal to execution trust. A sealed source does not become more trusted; an included source does not receive more capability.

## 9. Alternatives rejected

### Generic ZIP/TAR as the canonical v1 package container

Rejected for the default package boundary. Filesystem archives introduce path normalization, duplicate/case-collision, links, extraction-root and decompression concerns that SplashMX does not need for its content-addressed semantic records. Supporting them as future **import** formats would require a separately hardened pre-parser and R-016-01 evidence; they are not package identity.

### OCI image layout as the ordinary package format

Rejected. OCI is designed around container image/distribution/runtime use and filesystem-layer semantics. That is much broader than SplashMX's immutable semantic record bundle, and would invite runtime/filesystem concepts into a creative-component format. OCI remains useful precedent for digest-addressed distribution, not the product package abstraction. OCI currently maintains image, runtime and distribution specifications: <https://opencontainers.org/>.

### Naive unbounded DFS/backtracking

Rejected as production solver. It is simple enough for the falsification spike, but real dependency graphs can revisit equivalent dead ends and produce poor conflict explanations. PubGrub's conflict learning better matches the product need, while hard bounds remain mandatory because solving is still NP-hard.

### General SAT/SMT solver first

Not selected for v1. It can express the problem, but adds a larger implementation/dependency and explanation surface than the current exact/caret, one-version-per-package domain requires. Revisit only if corpus evidence demonstrates requirements PubGrub cannot express efficiently.

### Runtime floating resolution

Rejected categorically. It breaks offline exactness, reproducibility, rollback reasoning, streaming acquisition and compatibility guarantees. Runtime consumes the exact lock or produces typed unavailability/incompatibility.

### Registry URL/friendly name as identity

Rejected. Repositories can move, mirrors can change, names/search rankings can be mutable, and offline bundles must remain meaningful. Stable SplashMX IDs plus exact digests carry identity/integrity.

## 10. Falsification evidence

`docs/research/SMX-034-PACKAGE-SUBSTRATE-FIXTURES.json` defines `PS-001` onward. The spike and tests intentionally attack the selected seams:

- exact/caret boundary behavior including `0.x`;
- rejection of wildcard/comparator/OR grammar expansion;
- highest-compatible deterministic resolution;
- transitive exact closure and backtracking;
- one-version conflict;
- revoked/missing required revisions;
- optional fallback and explicit lazy marking;
- solver work and total-byte exhaustion;
- deterministic SPB1 framing;
- truncated/wrong-magic/oversized index input;
- digest substitution;
- path/extraction-field injection;
- overlapping/gapped/unindexed payload layout;
- duplicate digest and per-entry size bounds;
- recursive serialized authority/install-script injection;
- incomplete protected-Asset revision rejection;
- provenance/licence remaining non-capability metadata.

The spike deliberately imports the production SMX-024 deterministic-CBOR encoder/decoder so malformed/noncanonical index input traverses the real canonical parser boundary rather than a fresh package-only codec.

Passing this spike does **not** certify a production PubGrub implementation, public registry, cryptographic trust root, decompressor, marketplace, CDN, browser package UI or hostile production package parser. Those claims remain owned by SMX-035 and the later security/distribution issues.

## 11. SMX-035 production handoff

SMX-035 should implement the selected mechanisms without reopening broad selection unless contradictory evidence appears:

1. create production `packages.core` ownership with typed package IDs/revisions/requirements/locks and failure envelopes;
2. implement normalized exact/caret parsing and SemVer ordering with adversarial boundary tests;
3. implement or integrate a deterministic **bounded PubGrub-family** solver with derivation diagnostics and all independent resource ceilings;
4. preserve required/optional/lazy semantics and one-version-per-`PackageId`;
5. implement exact lock serialization through the existing canonical deterministic-CBOR boundary;
6. implement the SPB1 parser/writer against the production parser, including all bounds/digest/layout checks from this spike;
7. integrate exact acquisition with SMX-030 rather than inventing a second cache/streaming system;
8. integrate capability-request preflight with SMX-027; no grants are serialized in package/lock data;
9. port SMX-013 package fixtures plus `PS-*` cases to production tests;
10. retain protected Asset revisions whole through install/update/rollback;
11. keep catalog/repository access behind an injected snapshot/acquisition adapter with no ambient network use;
12. add dedicated CI and reconcile GATE-07 only after the real production parser/resolver passes.

Residual questions deliberately remain for later owners:

- SMX-039: exact cryptographic signature/trust-root/revocation implementation;
- SMX-040/041: physical sandbox/decoder/native-headless security and proof;
- SMX-036: generic publishing/runtime consumption of immutable creation closure;
- SMX-048+: broad product UX/performance hardening;
- public registry, marketplace, CDN topology and discovery ranking remain product/distribution work, not Architecture-v1 identity.
