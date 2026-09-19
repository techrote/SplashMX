# SMX-013 — Portable components, packages, dependency resolution, updates, remix, and capability semantics

**Status:** pre-Architecture-v1 semantic contract candidate; package ecosystem model, not production registry/format/UI  
**Issue:** SMX-013 / #13  
**Date:** 2026-09-19  
**Evidence:** `SMX-013-PACKAGE-FIXTURES.json` and `experiments/smx-013-package-model/`

## Contents

| Section | Summary |
|---|---|
| 1. Result | States the selected package/component boundary and what remains open. |
| 2. Inherited constraints | Carries SMX-003/005/006/008/011/012 semantics forward without dilution. |
| 3. Promotion path | Defines group → local definition → portable component without a second object model. |
| 4. Manifest and identity | Separates PackageId, package revision, DefinitionId, version labels, digests, and concrete Thing identity. |
| 5. Dependencies and lock | Defines required/optional/lazy requirements, exact resolution, locks, cycles, bounds, and offline behavior. |
| 6. Capabilities | Keeps package requests declarative, principal-attributed, non-transitive, narrowed, and separate from live grants. |
| 7. Integrity, trust, provenance | Defines digest/signature/revocation roles without converting trust into privilege. |
| 8. Source, remix, and licensing | Makes source availability, remix rights, attribution, and derivation explicit without pretending to provide DRM. |
| 9. Install/update/migration | Defines staged clean install and transactional updates with override/state reconciliation and rollback. |
| 10. Removal and cache | Separates uninstall/reference semantics from cache eviction and residual save state. |
| 11. Protected media | Preserves atomic AssetId + digest/source/audio/provenance/licence/derivation revisions. |
| 12. Ecosystem comparisons | Extracts useful lessons from Cargo/npm/TUF/SLSA/SPDX without importing their user complexity. |
| 13. Executable evidence | Maps PK fixtures to the disposable model and adversarial suite. |
| 14. Rejected alternatives | Records designs that violate the one-system/security/compatibility constraints. |
| 15. Hypothesis effects | Updates H-004/H-009/H-011/H-018. |
| 16. Downstream handoffs | Defines exact obligations for SMX-014/016/019. |

## 1. Result

SplashMX should treat a portable component as **the same reusable Definition/Thing semantics placed behind a distribution boundary**, not as a package-specific object class. The selected candidate is:

```text
ordinary Things/group
  -> Make reusable
     local DefinitionId + stable ElementId/PortId semantics
  -> Make portable / publish component
     PackageId namespace + immutable PackageRevision
       ├─ same root DefinitionId lineage
       ├─ exact public ports/properties
       ├─ behaviour revisions
       ├─ exact protected asset revisions
       ├─ dependency requirements
       ├─ capability requests (declarations, never grants)
       ├─ source/remix/licence/provenance policy
       └─ integrity/signature/update metadata

project requirement
  -> resolver
  -> exact resolution lock
  -> bounded acquire/verify/validate
  -> capability-policy evaluation
  -> stage/reconcile/migrate
  -> atomic publication
```

The package layer therefore adds **namespace, distribution, dependency, update and provenance semantics** around the object fabric. It does not introduce a new prefab/module/runtime hierarchy.

The model intentionally does **not** freeze the final package bytes/container, registry protocol, signature/trust-root framework, marketplace, production version-range language, solver implementation, browser cache/store, or author-facing package-manager UI. Those choices require SMX-014/016/019 evidence.

### Package invariants

- **PKG-001 — portable reuse is the same object model.** Packaging a local reusable definition does not create a second base object, prefab, class, scene, or execution model.
- **PKG-002 — promotion preserves semantic identity.** Existing `DefinitionId`, `ElementId`, stable public `PortId`, and concrete first-instance `ThingId` values are not rewritten merely because a portable package is created.
- **PKG-003 — PackageId is a distribution namespace, not Thing identity.** Cross-project references may qualify a definition by `PackageId`, while `PackageId`, `PackageRevisionId`, `DefinitionId`, `ThingId`, human version, and content digest remain distinct roles.
- **PKG-004 — human version requirements resolve to exact immutable revisions before use.** Runtime/streaming never consumes a floating range.
- **PKG-005 — the project records an exact resolution lock.** The lock names exact package revision, digest, size/features/provenance context sufficient for deterministic reacquisition; it contains no live host grants.
- **PKG-006 — dependencies are explicit semantic edges.** They are not inferred from containment, filenames, Godot resource paths, or whatever happens to be present in a cache.
- **PKG-007 — required dependency closure is staged atomically.** Missing/incompatible/revoked required content blocks publication; no half-installed live graph is allowed.
- **PKG-008 — optional dependency failure uses only a declared fallback.** Absence cannot silently select unrelated behavior.
- **PKG-009 — lazy dependencies are declarations, not hidden synchronous loads.** They resolve/acquire when policy requests them and remain subject to the same exactness/security rules.
- **PKG-010 — resolution is bounded and deterministic for the same catalog/policy snapshot.** Depth, count, bytes and solver work have hard ceilings; cycles are rejected by the current candidate rather than relying on initialization order.
- **PKG-011 — one exact revision per PackageId per creation is the current candidate.** Incompatible transitive requirements surface a version conflict rather than silently loading ambiguous parallel identities. This can be revisited only with evidence that multi-version coexistence preserves simple semantics.
- **PKG-012 — immutable descriptor verification precedes publication.** Digest/size/revision mismatches and identity collisions fail closed.
- **PKG-013 — revocation/deprecation is policy metadata, not identity rewriting.** A revoked exact revision cannot be silently replaced by another compatible version; updates require an explicit new resolution/transaction.
- **PKG-014 — offline mode consumes the existing exact lock.** If required locked bytes are absent from the verified cache, the result is typed `offline_unavailable`; offline never re-solves to “some cached compatible version”.
- **PKG-015 — capability requests are attributed to the requesting package principal.** Transitive requests may be summarized for UX, but attribution paths remain visible and no parent/dependent grant is inherited automatically.
- **PKG-016 — capability delegation remains live, explicit and narrowing.** Packaging, dependency edges, signatures, publisher identity, containment, or installation do not mint or widen grants.
- **PKG-017 — trust metadata is not privilege.** A valid signature/provenance record can support origin/integrity/update policy and still receives zero host capability unless current host/user policy grants it.
- **PKG-018 — updates retain concrete instance identity and intentional overlays.** Compatible package/definition revision changes do not replace `ThingId` or erase sparse local variation.
- **PKG-019 — persistent/runtime state migration is explicit.** State-schema changes require bounded deterministic side-effect-free migration or a typed incompatibility.
- **PKG-020 — update is plan-before-commit and rollback-safe.** Dependency closure, capabilities, public interfaces, overlays, protected assets, pending state and migrations validate before any affected instance becomes new-version live.
- **PKG-021 — failed update leaves the old coherent state active.** Old exact package lock/revisions, instances, overlays, persistent state, public ports and pending work remain unchanged; newly verified immutable bytes may remain inert cache entries.
- **PKG-022 — public interface compatibility is semantic, not a version-number promise.** Removing/retyping a stable port/property/overlay locus creates a reconciliation conflict unless an explicit compatible migration/retarget exists.
- **PKG-023 — uninstall is reference-aware.** Package source cannot be removed from a project while authored instances or required dependency edges still depend on it without an explicit detach/materialize/migration operation.
- **PKG-024 — cache eviction is non-semantic.** Evicting reconstructible package bytes does not delete definitions/instances/history/save state or change stable IDs/locks; later use reacquires the exact locked artifact.
- **PKG-025 — source availability and remix rights are explicit metadata.** Included/linked/sealed source and allowed/restricted/forbidden remix declarations are author/distribution policy, not runtime authority.
- **PKG-026 — licensing, attribution, and derivation provenance survive publish/remix/update.** A derived component records its lineage and relevant licence obligations; sealing source does not erase provenance or grant execution trust.
- **PKG-027 — protected media revisions remain indivisible.** Stable `AssetId` points to a complete immutable revision bundle containing digest, source identity/metadata, audio/media semantics, provenance, licence and derivation; partial or cross-version field synthesis is forbidden.
- **PKG-028 — package distribution preserves canonical semantics.** Package/index/container/registry/cache representation may change, but Things, definitions, behaviours, ports, assets, source/audio/provenance, migrations and capabilities keep SplashMX meaning above that substrate.

## 2. Inherited constraints

SMX-013 is a continuation of accepted work, not a greenfield package-manager design.

From **SMX-003**, ordinary groups can become reusable local definitions without replacing the first concrete instance. Definitions have stable internal element/public-port identity; instances retain sparse overlays and explicit base provenance. Package promotion must preserve that path.

From **SMX-005**, logical IDs are distinct from content digests and storage location; packages must carry an engine-independent canonical semantic graph, atomic transactions, typed absence states and rollback-safe migrations. A package file or registry row cannot become object identity.

From **SMX-006**, community components are untrusted. Manifests declare capability requirements but cannot serialize live grants, host handles, authority tokens, GDScript/native/JavaScript privileges or arbitrary fetch rights. Dependency acquisition and migration are capability-free/bounded until validated host services deliberately act.

From **SMX-008**, package resolution feeds streaming an exact immutable descriptor. Acquisition is fetch → bound → verify → parse → validate/migrate → stage → publish. Required/optional/lazy dependencies are distinct, hot replacement is quiescent and transactional, and cache eviction does not destroy semantic identity.

From **SMX-011**, edits/updates must preserve coherent semantic transactions under collaboration. Package/component updates that invalidate instance overlays/interfaces are conflict-worthy author intent, not storage-level last-writer events. Protected media replacements remain indivisible alternatives.

From **SMX-012**, Components are a progressively disclosed view over Things/Behaviours/Connections. “Make reusable” and later “Make portable” must feel like an extension of ordinary composition. Beginner authors should not need registry/solver/lock/digest vocabulary for routine reuse; Inspect may expose those details.

## 3. Promotion path: local definition to portable component

The author path is deliberately incremental:

1. author ordinary Things and group them;
2. **Make reusable** records a local Definition lineage while preserving the selected concrete Things as the first instance;
3. author/confirm public ports and properties using the same stable interface semantics already used locally;
4. **Make portable** assigns a durable `PackageId` distribution namespace and creates an immutable package revision that references the same root `DefinitionId` lineage;
5. choose source/remix/licence/attribution policy and review dependency/capability declarations;
6. publish/share the immutable revision or keep it local/offline;
7. other projects resolve a package requirement, then instantiate normal concrete Things with fresh `ThingId` values and explicit provenance back to the exact Definition/package revision.

The source project's existing concrete first instance is not destroyed/recreated. `PackageId` qualification makes the definition portable across documents; it does not turn the package into a runtime owner.

A package may contain/reference multiple definition/behaviour/asset records for implementation purposes, but the author-visible reusable component has one declared root public interface. Nested reusable components remain explicit dependencies or included definitions according to packaging policy.

## 4. Manifest, stable identity, and public interface

Candidate semantic manifest shape:

```text
PackageManifest
  PackageId                         # mutable distribution lineage / namespace
  PackageRevisionId                 # immutable published revision identity
  human_version                     # ordering/compatibility declaration, not identity
  canonical_manifest_digest
  declared byte bound / artifact descriptors

  root
    DefinitionId                    # preserved from local reusable definition
    DefinitionRevisionId            # exact immutable base revision
    public PortIds + signatures
    public PropertyIds + schemas/default semantics

  included/referenced
    BehaviourDefinitionId + exact revision
    protected AssetId + exact asset revision bundle
    migration descriptors
    required feature/schema/IR declarations

  dependencies
    PackageId + compatibility requirement
    required | optional | lazy
    requested public features/interfaces
    explicit optional fallback

  capabilities
    requesting package/component principal
    semantic capability name + typed scope request
    required | optional
    rationale/presentation metadata

  distribution metadata
    source availability
    remix permission
    licence expression / custom licence reference
    attribution
    derivation/package lineage
    signatures/attestations/update metadata references
```

### Identity distinctions

A single component can legitimately have all of these at once:

- `PackageId = pkg:weather-clock` — distribution lineage/namespace;
- `PackageRevisionId = pkgrev:weather-clock:...` — exact immutable package revision;
- `human_version = 2.3.1` — author/publisher compatibility label;
- `DefinitionId = def:weather-clock` — reusable semantic definition lineage;
- `DefinitionRevisionId = defrev:...` — exact base definition revision;
- `ThingId = thing:weather-clock-17` — one concrete instance;
- `BlobDigest = sha256:...` — exact bytes for an immutable artifact.

These must never be aliases. A human version is particularly **not** enough to identify bytes: a repository must reject or quarantine same-version ambiguity rather than letting two different immutable revisions race behind one label.

### Public interface compatibility

A version label may communicate publisher intent, but compatibility is validated against stable SplashMX semantics. Update preflight checks at least:

- public PortIds, direction/kind/payload contract;
- public properties/state schema and stable semantic loci;
- required features/IR/schema;
- affected instance overlays/local additions/suppressions;
- behaviour/private-state migration requirements;
- persistent/save state compatibility;
- protected asset revision validity;
- dependency/capability closure.

A package claiming a compatible version while deleting a port used by a project is still incompatible for that project. SemVer-style labels are advisory inputs to resolution, not a waiver of semantic validation.

## 5. Dependencies, version resolution, locks, and offline cache

### 5.1 Requirement versus exact resolution

Authored/package dependency requirement:

```text
DependencyRequirement
  PackageId
  compatibility_requirement
  required | optional | lazy
  requested_features/interfaces
  explicit fallback?               # mandatory for optional in current candidate
```

Project resolution lock:

```text
ResolvedPackage
  PackageId
  human_version
  PackageRevisionId
  exact digest + byte bound
  required schema/IR/features
  provenance/trust metadata reference
  exact child dependency descriptors
```

The **requirement** is what may float during an intentional resolve/update operation. The **lock** is what playback, publish, streaming and offline reacquisition consume.

### 5.2 Candidate resolver rules

The research model deliberately uses a tiny version language (exact and caret-compatible forms) so semantic questions are not hidden by solver complexity. Production syntax remains open.

Current candidate rules:

- select a deterministic highest compatible non-revoked revision from the current catalog/policy snapshot;
- permit one exact resolved revision per `PackageId` in a creation;
- if transitive requirements for that identity cannot share one revision, report an explicit version conflict;
- required child failure blocks resolution;
- optional child failure uses only its declared fallback;
- lazy child is recorded and resolved/acquired when demanded;
- reject package dependency cycles for v1 candidate simplicity, despite SMX-008's ability to stage an already-exact declarative cycle;
- bound solver/dependency depth, package count, total bytes, metadata fanout and work;
- write/refresh the exact lock only after a complete coherent resolution exists.

The one-version-per-`PackageId` rule is deliberately conservative. Parallel incompatible versions would require namespaced runtime/public identities, duplicate capability prompts, migration/update rules and author diagnostics. It should be introduced only if real package-corpus evidence shows the simpler conflict model is inadequate.

### 5.3 Dependency disappears, is revoked, or becomes malicious

Different states remain typed:

- **missing/unpublished:** exact new acquisition unavailable;
- **offline/unreachable:** known exact artifact unavailable from transport;
- **revoked/quarantined:** policy says the exact revision must not newly activate/update;
- **digest/signature mismatch:** observed artifact is not the locked revision;
- **schema/feature incompatible:** valid bytes cannot run here;
- **malicious/invalid:** parser/IR/security validation fails;
- **resource exhausted:** declared/observed limits exceeded.

None authorizes silent version substitution. A safe update resolves a new exact closure and enters the normal staged update transaction.

### 5.4 Offline behavior

A creation is offline-capable when the exact required lock closure is present in verified local cache/store. Offline mode:

- does not consult a remote registry;
- does not upgrade/downgrade because another cached revision happens to satisfy a range;
- can use declared optional fallbacks for dependencies not in the resolved active closure;
- reports an actionable unavailable component when required locked content is absent;
- retains stable project/object identities even if reconstructible package bytes are evicted.

This keeps P14 meaningful without making cache contents canonical project state.

## 6. Capability requests and transitive dependencies

Packages declare what their behaviours may need; they never ship authority.

Example:

```text
pkg:dashboard
  -> depends on pkg:weather-widget
       requests network.http
         origin = https://weather.example
         method = GET
         required = true
```

The editor/player may present a useful summary such as “Dashboard includes Weather Widget, which wants to read weather.example”. Internally the request stays attributed to the **weather-widget principal**. Granting `network.http` to Dashboard does not satisfy Weather Widget's request.

### Capability rules

1. package manifests carry **requests/declarations**, not grant IDs/tokens/handles;
2. each dependency/component principal is checked independently at activation/service time;
3. transitive request summaries preserve the attribution path;
4. publisher signatures/source availability/remix rights/licence do not imply capability;
5. required denial blocks the affected activation/update before publication;
6. optional denial may select an explicitly declared reduced behavior;
7. parent→child service façades remain ordinary validated application interfaces;
8. explicit host capability delegation is a live runtime operation and can only narrow a currently held delegable lease;
9. update/reconnect/restore re-evaluates current policy; a package cannot persist an old grant as project data;
10. remote repositories/packages cannot mint local host authority.

This preserves SEC-001–SEC-018 and prevents package installation becoming a capability-laundering mechanism.

## 7. Integrity, signing, provenance, and revocation

### Digests

Every exact package/artifact descriptor used for acquisition carries a cryptographic digest and byte bound. Digest verification answers “are these the exact expected bytes?” It does **not** answer “is this media decoder safe?” or “may this code access the host?”

### Signatures/attestations

A package may carry signatures/attestations sufficient to establish some combination of:

- publisher identity;
- integrity of manifest/artifact index;
- update lineage/authorization;
- build/source provenance.

Those are policy inputs. **PKG-017/D-035 still applies:** signed content remains untrusted executable input and has no ambient capabilities.

### Revocation and rollback/freeze concerns

The package ecosystem needs a current policy layer capable of marking exact revisions/publisher keys/repositories as revoked or quarantined and resisting rollback/freeze/mix-and-match attacks. SMX-013 defines the semantic response — do not silently substitute; require an explicit new resolution/update — but deliberately does not select TUF, Sigstore, another signature system, or final trust-root UX. That destructive selection belongs to SMX-016.

An already-offline project creates a genuine policy tension: it may not know about a newly issued revocation. The architecture must not pretend otherwise. SMX-016/014 must decide freshness policy for online publish/install and how offline playback communicates stale trust metadata without making network connectivity mandatory for all local work.

## 8. Source availability, remix, licensing, attribution, and derivation

Portable components are creative artifacts, not just runtime dependencies. Their distribution record therefore needs authoring/remix semantics.

Candidate fields:

- **source availability:** `included`, `linked`, or `sealed`;
- **remix permission:** `allowed`, `restricted`, or `forbidden` according to declared licence/publisher policy;
- **licence expression/reference:** SPDX-compatible expression where applicable, with a custom licence reference when it is not;
- **attribution:** human/publisher notices that must travel with the package/derivatives;
- **derivation lineage:** source package/revision(s), remix transaction, imported source identities and transformations;
- **editable source references:** exact canonical source records/assets when included/linked.

`sealed` means “the package does not distribute editable source through the ordinary authoring surface.” It is **not** a promise of perfect secrecy/DRM and does not increase runtime trust. Conversely, `included` source does not grant host capabilities.

A remix creates a new package revision/lineage according to licence policy while retaining derivation/provenance links. Package promotion/publish must never replace canonical source records with Godot import artifacts or derived caches.

## 9. Clean install, update, instance overrides, persistent state, and rollback

### 9.1 Clean install/publication into a project

Candidate sequence:

1. resolve the root requirement plus bounded transitive requirements;
2. freeze an exact candidate lock;
3. acquire exact descriptors under repository/host policy;
4. verify digest/size/signature/provenance metadata as required;
5. parse/validate package/document/IR/assets under SMX-006 limits without executing user code;
6. validate public interfaces/features/schema;
7. compute attributed transitive capability request plan and evaluate current policy;
8. stage definitions/behaviours/assets and any required deterministic migration;
9. validate the complete closure;
10. atomically publish into project/runtime state;
11. only then may ordinary lifecycle/execution instantiate/run content.

Failure before step 10 leaves the pre-existing project live state unchanged. Verified immutable bytes may remain inert in cache.

### 9.2 Dependency update

An update is not “change a version string and hope”. It creates a new exact resolution and runs the same validation/security boundary before touching live instances. A transitive dependency update that introduces a new required capability, removes a stable port, changes schema incompatibly, is revoked, or cannot be acquired blocks the update transaction.

### 9.3 Locally overridden instance after update

For each affected instance:

- preserve concrete `ThingId`;
- retain its Definition/package provenance;
- compare new base revision using stable ElementId/PortId/property loci;
- propagate compatible unoverridden base changes;
- preserve explicit valid overlays/local additions;
- surface invalidated override/interface targets as conflicts;
- retain/reconcile stable public connections;
- migrate persistent/private state explicitly when schemas change.

The disposable model takes the strongest simple policy: one project update stages **all** affected instance migrations and commits only if all pass. A production editor may later support explicit per-instance pinning/mixed revisions, but each instance swap still must be atomic and the mixed state must be visible rather than accidental.

### 9.4 Incompatible migration and rollback

If migration is absent, throws/fails, exceeds budget, produces invalid state, or cannot reconcile an interface/overlay:

- old exact package/dependency lock remains active;
- old Definition/Behaviour revisions remain active/pinned as required;
- all affected concrete Thing identities stay unchanged;
- overlays and persistent/private state remain old-version coherent;
- public connections/pending durable work remain unchanged;
- no partial new-version instance becomes live;
- newly verified immutable bytes may remain cacheable but inert.

This is the package-level continuation of DOC-012, STR-013–STR-015 and the SMX-003 reconciliation contract.

## 10. Removal, uninstall, cache eviction, and residual state

Three operations must not be conflated.

### Remove from project

Removing a package dependency/source is blocked while:

- authored instances still cite that package/definition lineage;
- another installed package has a required dependency edge to it;
- an active update/migration needs it.

A future explicit **detach/materialize locally** command may replace package provenance with a local definition under a deliberately specified migration, but uninstall may not do that silently.

### Cache eviction

Verified reconstructible package/artifact bytes may be evicted under cache policy when not pinned. Eviction does not edit the canonical project, lock, `DefinitionId`, instance `ThingId`, collaboration history, save state or provenance. Later activation either reacquires the exact lock or reports offline/unavailable.

### Residual persistent state

Uninstall/removal does not implicitly erase world/save state that references a historical component revision. Such state remains an inert typed record until an explicit retention/purge/migration policy acts on it. This avoids “uninstall deleted my save” and preserves forensic/provenance information. Product retention UX remains SMX-019/020.

## 11. Protected source/audio/provenance semantics

SMX-013 preserves and tightens the media boundary established by SMX-005/009/011/012.

A package never reduces an asset to “filename + imported runtime resource”. It carries or exactly references a logical `AssetId` plus a complete immutable asset revision:

```text
AssetRevision
  AssetId                      # stable logical identity
  immutable digest
  logical source identity
  exact source metadata
  audio/media semantic metadata
  provenance
  licence
  derivation lineage
```

Rules:

- replacing media may retain `AssetId` while producing a new complete immutable revision;
- missing source/audio/provenance/licence/derivation fields make a replacement invalid;
- package signing cannot repair an incomplete protected revision;
- two competing asset replacements remain two complete alternatives;
- no resolver, collaboration merge, package update, Godot import or publishing step may combine digest/source/audio/provenance fields from different revisions;
- derived/transcoded/imported/cache resources remain target-private derivatives and cannot become canonical source identity.

The executable model includes complete replacement, partial-bundle rejection, and concurrent-alternative tests specifically to guard this contract.

## 12. Ecosystem comparisons and primary evidence

Checked 2026-09-19. These are precedents, not selected dependencies or author-facing models.

### Cargo

Current Cargo documentation separates dependency **version requirements** from exact resolutions recorded in `Cargo.lock`, supports registry/git/path sources, and documents compatible range forms. Useful lessons are the manifest-vs-lock distinction and explicit dependency constraints. SplashMX does not adopt Cargo's build-centric workflow or expose a TOML package manager to beginners.

Sources:
- https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html
- https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html

### npm

npm 11 documentation describes `package-lock.json` as an exact dependency-tree representation used to reproduce installs and records resolved locations/integrity metadata. npm also demonstrates the ecosystem cost of install scripts and deeply transitive package behavior; SplashMX explicitly excludes arbitrary package install scripts/native execution from ordinary components.

Sources:
- https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/
- https://docs.npmjs.com/cli/v11/configuring-npm/package-json/

### The Update Framework (TUF)

The current TUF specification is useful security precedent for signed repository metadata, version/freshness handling, bounded target metadata and rollback/freeze/mix-and-match threat classes. SplashMX adopts the need to defend those classes but does not select TUF's complete repository-role design in SMX-013.

Source: https://theupdateframework.io/specification/latest/

### SLSA provenance

SLSA 1.2 describes provenance as verifiable information tracing an artifact through how/where it was produced. That reinforces the separation between provenance evidence and runtime authority: provenance can inform trust/policy without becoming a capability grant.

Source: https://slsa.dev/spec/v1.2/provenance

### SPDX licence expressions

SPDX 3.0.1 defines a compact normative licence-expression grammar and custom licence references. SplashMX should carry machine-readable licence expressions where applicable while retaining custom licence text/reference paths for content that does not map cleanly.

Source: https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/

### Why no ecosystem is copied wholesale

Cargo/npm optimize developer dependency/build workflows. SplashMX needs a creative-author workflow where package complexity is mostly hidden, components remain ordinary Things/Definitions, no install script gets ambient host authority, protected source/media provenance survives remix, and a generic player can consume exact validated locks. Their mechanisms are comparative evidence, not the product metaphor.

## 13. Executable fixtures and adversarial evidence

`docs/research/SMX-013-PACKAGE-FIXTURES.json` defines `PK-001` through `PK-020` against `PKG-001` through `PKG-028`.

The disposable model in `experiments/smx-013-package-model/` has **41 deterministic tests** covering:

- local definition → package promotion with Definition/Element/Port/first-instance identity preservation;
- package/revision/version/digest identity separation and same-version ambiguity rejection;
- clean deterministic resolution into exact locks;
- required, optional and lazy dependencies;
- missing/revoked dependency behavior;
- cycles, depth/count/byte bounds and conflicting transitive ranges;
- offline exact-lock cache behavior and no cached-version substitution;
- digest substitution/revision collision rejection;
- transitive capability attribution, parent-grant non-inheritance, required/optional denial and narrowed delegation;
- signed/sealed/non-remixable content still receiving no ambient authority;
- compatible updates preserving concrete Thing identity, local overlays and persistent state;
- explicit state migration, whole-update rollback on missing/failing migration, invalid overlay and removed protected port;
- new transitive capability introduced by update cannot launder through a root package grant;
- uninstall guard and cache-eviction non-semantics;
- complete protected asset replacement, incomplete-bundle rejection and indivisible concurrent alternatives.

The required issue cases are directly represented: **clean install, dependency update, locally overridden instance after update, denied capability, missing dependency, and incompatible migration**.

Passing this model is not evidence for a production registry, hostile archive parser, cryptographic trust implementation, browser cache durability, solver performance, or usable component marketplace. Those are intentionally handed to SMX-014/016/019.

## 14. Rejected and deferred alternatives

### Separate package component class

Rejected. It would make local reuse and portable reuse different object systems, violating P3/AUTH-008/AUTH-009 and creating conversion/identity problems.

### Package/version string as object identity

Rejected. Mutable version labels and distribution namespace do not replace concrete Thing/Definition identity or immutable revision/digest identity.

### Floating dependency resolution at runtime

Rejected. Playback/streaming consumes an exact lock; uncontrolled registry state cannot redefine a creation between launches.

### Automatic transitive capabilities

Rejected. A dependency's requests remain attributed to that dependency principal. Trust/signature/containment/install cannot grant privilege.

### Arbitrary install/update scripts

Rejected for ordinary community content. Package validation/migration stays inside constrained deterministic SplashMX semantics; no npm-style arbitrary host script boundary.

### Silent “best effort” update

Rejected. Required dependency/capability/interface/migration failures roll back rather than leaving mixed/half-updated semantic state.

### Filename/path based component references

Rejected. Package/Definition/Port/Asset identities remain path-independent and survive repacking/cache movement.

### Field-wise media/provenance merge

Rejected. Protected asset revisions are atomic bundles and competing revisions remain alternatives.

### Package as physical streaming unit

Rejected as a semantic requirement. A package is distribution/provenance/resolution scope; SMX-008 may acquire/cache smaller or larger physical units while preserving exact descriptors.

### Final package bytes/registry/signature system

Deferred. Choosing archive/CBOR/database/registry protocol/TUF-like trust roots before SMX-014/016/019 would turn an implementation convenience into the long-term compatibility boundary without the required evidence.

## 15. Hypothesis effects

### H-004 — ordinary local classes/groups can become reusable portable components

**Strengthened substantially at semantic/package-model level.** The same Definition/Element/Port lineage moves from ordinary local reuse into a `PackageId` namespace without replacing existing concrete Things. Portable consumers create normal Things with explicit exact-package/definition provenance. A production package/editor/browser path remains unproven.

### H-009 — capability security can bound untrusted components

**Strengthened at the package/dependency layer.** Transitive dependency requests remain principal-attributed, parent grants are not inherited, delegation only narrows live leases, required denial blocks staged update/install, and signed/sealed/provenance-rich packages still receive no authority. Real archive/parser/signature/dependency-confusion attacks remain SMX-016.

### H-011 — streaming can be object-centric rather than scene-centric

**Strengthened at distribution/resolution level.** Package resolution produces exact immutable descriptors consumed by the existing object/artifact streamer, while package boundary and cache residency remain non-semantic. Offline exact-lock/cache behavior does not turn the package file into Thing identity.

### H-018 — compatibility can be migration-driven rather than engine-version-driven

**Strengthened at component-update level.** Version labels select candidate revisions, but actual compatibility is validated using stable public loci, required features, overlays and explicit state migrations. Failed updates roll back to the prior exact lock/state. Production multi-version migrations and long-term registry retention remain SMX-016/020.

No accepted source/audio/provenance, lifecycle, collaboration, multiplayer, Godot-boundary or authoring invariant is weakened.

## 16. Downstream handoffs

### SMX-014 — publishing and generic-player delivery

Must consume an **exact package resolution lock**, not floating ranges; package the canonical revision plus required exact dependency/artifact descriptors; validate features/capability declarations/protected asset revisions before generic-player publication; preserve source/remix/licence/provenance policy; and define online/offline hosting/cache/update metadata without making the author run a build toolchain.

### SMX-016 — hostile package and sandbox campaign

Must attack archive/container parsing, dependency count/depth/bytes, digest/signature substitution, repository/dependency confusion, rollback/freeze/mix-and-match, revoked publisher/revision handling, malformed manifests/version ranges, migration bombs, malicious media decoders, capability laundering through nested/transitive dependencies, forged source/licence/provenance records, and any selected trust-root/signature implementation. Passing the Python model is not security proof.

### SMX-019 — browser editor/player vertical slice

Must prove the author path **group → Make reusable → Make portable → use in another project → update with local override → work offline → publish/load** without requiring ordinary authors to understand solver/lock/digest/registry terminology. Capability/dependency/update/remix failures must use author vocabulary while Inspect retains exact diagnostics. Protected AssetId/source/audio/provenance must survive the real import/package/publish/player path.

Residual questions intentionally remain: final PackageId namespace encoding; final range language/solver; multiple incompatible revisions of one PackageId; repository discovery/federation; trust roots/signature rotation/revocation freshness; exact package/container/index format; vendoring/mirroring; source-sealing UX; licence-policy enforcement boundaries; cache/store durability; and explicit detach/materialize/uninstall-state UX.
