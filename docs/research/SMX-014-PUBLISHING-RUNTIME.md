# SMX-014 — Publishing, generic player, server runtime, offline bundle, and compatibility contracts

**Status:** pre-Architecture-v1 publishing/runtime contract candidate; non-production package/hosting proof  
**Issue:** SMX-014 / #14  
**Evidence refresh:** 2026-09-19  
**Godot baseline:** 4.7.2 stable (2026-08-18); 4.8-dev6 is a development snapshot (2026-09-15)

This document defines the boundary between editable SplashMX projects and distributable/runtime artefacts. It continues the canonical-document, capability, lifecycle/streaming, Godot-substrate, multiplayer, authoring, and portable-package contracts from SMX-005–013. It does **not** select final package bytes, CDN/registry infrastructure, cryptographic trust roots, installer technology, browser cache implementation, or a production hosting architecture.

## Contents

| Section | Summary |
|---|---|
| 1. Result | Selects immutable published creation revisions consumed by precompiled generic runtimes. |
| 2. Authority chain | Lists prior contracts publishing may not weaken. |
| 3. Refreshed platform evidence | Records current Godot/export/runtime facts relevant to the boundary. |
| 4. Artefact taxonomy | Separates editable project, creation, component, world/save, runtimes, hosted release and offline bundle. |
| 5. Identity and manifest | Defines stable creation lineage, immutable revisions and runtime compatibility declarations. |
| 6. Generic-player launch pipeline | Requires negotiation, exact acquisition, validation and policy checks before activation. |
| 7. Compatibility and migration | Defines backward/forward handling and unsupported future content. |
| 8. Web/native/headless projection | Allows target payload differences without canonical semantic forks. |
| 9. Hosted/share/embed | Separates mutable discovery aliases from immutable resolved releases. |
| 10. Offline | Defines exact closed-cache/bundle expectations and failure semantics. |
| 11. Persistent worlds | Keeps runtime progress/server-owned state separate from creation distribution. |
| 12. Exceptional per-creation builds | Constrains trusted exceptional builds outside the ordinary content path. |
| 13. Invariants and executable evidence | Defines PUB-001–PUB-030 and PB-001–PB-020. |
| 14. SMX-017 handoff | Freezes concrete publication/runtime inputs for topology-equivalence testing. |
| 15. SMX-019 handoff | Freezes concrete browser create→publish→load/offline gates. |
| 16. Rejected alternatives and residual questions | Records boundaries deliberately left open. |
| 17. Hypothesis effects | Reconciles H-014/H-015/H-018 without overclaiming production proof. |

## 1. Result

The selected candidate is:

```text
EditableProject
  mutable canonical authoring revision/history
  + exact component/package resolution lock
  + protected source/audio/provenance records
  + authoring-only/editor context kept separate
        |
        | deterministic publish projection (NO Godot project export)
        v
PublishedCreationRevision   [immutable semantic/distribution revision]
  CreationId                [stable lineage]
  CreationRevisionId        [exact immutable revision]
  canonical semantic digest
  schema + IR compatibility requirements
  required/optional feature declarations
  exact package/component lock
  exact protected asset descriptors
  capability requests (never grants)
  topology-independent network declarations
  runtime entry points
        |
        +-------------------+-------------------+
        v                   v                   v
Generic Web Player      Generic Native      Generic Headless/
(precompiled trusted    Player              Server Runtime
runtime)                (precompiled)       (precompiled)
        |                   |                   |
        | target-private asset/runtime projection only
        +-------------------+-------------------+
                            |
                    live Runtime State
                            |
                            v
                  WorldSave / PersistentWorld
                  (separate revision lineage)

Distribution wrappers around the immutable creation revision:
  HostedRelease -> resolved immutable creation + compatible runtime policy
  Share/Embed alias -> may point to a HostedRelease
  OfflineBundle -> exact creation/dependency/blob closure + compatible runtime build/profile
```

The principal decision is:

> **Ordinary publishing creates an immutable SplashMX creation revision for a versioned generic player; it does not export or compile a new Godot project for each creation.**

A published creation contains **data plus constrained SplashMX logic**, not arbitrary Godot scripts/scenes/plugins. The trusted player binary may be built with Godot, but building that binary is platform engineering, not a normal author operation.

The narrow executable model under `experiments/smx-014-publishing-model/` strengthens this by separating `Publisher.publish()` from a precompiled `GenericPlayer`: publication deterministically creates one immutable semantic revision; web/native/headless runtime profiles negotiate and validate it before `activate()`; target-specific payload omission never changes the creation revision. Thirty-nine deterministic tests currently exercise that contract. The model remains non-production and is not real Godot startup/performance evidence.

## 2. Authority chain carried forward

SMX-014 accepts rather than reopens these merged semantics:

- **SMX-005:** editable authored records, runtime state, persistent save/world state and transient context are separate planes; IDs/references are SplashMX-owned; migrations are staged and rollback-safe.
- **SMX-006:** ordinary content receives no ambient Godot/GDScript/C#/native/JavaScript/filesystem/raw-network authority. Parsing, migration, runtime services and network ingress are independent hostile boundaries.
- **SMX-007:** persistent snapshots contain semantic state rather than process objects; engine/session/capability handles are rebound from current policy.
- **SMX-008:** runtime acquisition consumes exact immutable descriptors; required closure is verified/staged before atomic publication; cache is non-semantic.
- **SMX-009:** Godot is a private substrate; web/native/headless are target projections of one canonical revision; exact asset integrity precedes decode/import; source/audio/provenance is canonical and target-private derivatives never replace it.
- **SMX-010:** one topology-independent network declaration supports offline, peer-hosted and dedicated-authoritative policy; transport/peer IDs are context.
- **SMX-012:** Publish is a progressive-disclosure authoring surface over the same semantics, not a build-system mode.
- **SMX-013:** portable components are exact immutable package revisions resolved into an exact project lock; capability requests remain principal-attributed; package updates are staged; protected asset revision bundles are indivisible.

Publishing therefore cannot make a Godot scene path, PCK resource path, exported executable name, URL, browser cache key, peer ID, runtime build ID, or package digest substitute for a durable SplashMX semantic identity.

## 3. Current platform evidence — refreshed 2026-09-19

These are implementation facts and precedents, not public SplashMX contracts.

### 3.1 Godot release baseline remains 4.7.2 stable

Godot's release archive lists **4.7.2 stable, 18 August 2026** and **4.8-dev6, 15 September 2026**. Stable-runtime claims here therefore use the 4.7 documentation family; development snapshots are not treated as compatibility baselines.

Primary source: https://godotengine.org/download/archive/

### 3.2 Normal Godot project export is a build/package pipeline

Godot 4.7's export documentation describes platform export presets, installed export templates, playable project builds, PCK/ZIP export, command-line `--export-release`/`--export-pack`, and resource-selection modes. Dedicated-server export can remove visual resources and replace them with placeholders.

Primary source: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_projects.html

**Consequence:** this is useful for producing the **trusted generic SplashMX runtime builds**, but it is the wrong ordinary author-facing publication primitive. Making every creation a Godot export would violate P11, multiply executable artefacts/security surfaces, couple content compatibility to engine builds, and force the authoring product to understand presets/templates/platform packaging.

### 3.3 Runtime loading supports data/media without a per-user Godot editor export

Godot documents runtime loading of user-provided files/media, including images/audio and ZIP content, and notes runtime loading can be combined with HTTP requests. That is sufficient evidence that a trusted generic runtime can consume validated external bytes and create target-private decoded resources without requiring every content author to invoke the Godot editor exporter.

Primary source: https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html

**Consequence:** SplashMX should use its own validated package/asset descriptors and adapters, then hand verified bytes to appropriate runtime decoders. Godot's decoder/resource identities remain caches/derived objects below `AssetId` and source/provenance records.

### 3.4 Godot PCK/mod loading is explicitly not an untrusted-content security boundary

Godot's stable PCK/mod documentation states packs may contain scripts/scenes/shaders and warns that automatically loading malicious/replaced PCK files creates security vulnerabilities.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html

**Consequence:** an ordinary published SplashMX creation is **not** an arbitrary Godot PCK/mod project. The generic player parses SplashMX-owned canonical/package formats, validates constrained IR and assets, and exposes only capability-mediated services. A future internal pack format may physically use ZIP or another container, but it cannot acquire Godot script/native execution semantics by virtue of the container.

### 3.5 Headless Godot is a runtime target, not a second creation format

Godot supports `--headless` and dedicated-server export. Server export may omit visual resources. This supports a precompiled generic headless/server runtime, while the decision over which SplashMX assets are semantically required remains above Godot's resource-strip list.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

**Consequence:** a server target may omit presentation-only payload bytes, but must retain canonical descriptors/provenance and every asset/behaviour dependency required by simulation, collision, navigation, authoritative logic, world persistence or network semantics.

### 3.6 Browser persistence and lifecycle remain weaker than native

SMX-009 already established from Godot 4.7 web documentation that browser `user://` persistence is backed by IndexedDB when available, private/incognito/browser policy can make persistence unavailable, inactive tabs may suspend processing, and web/native audio/network/rendering capabilities differ.

Primary source: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html

**Consequence:** an offline web bundle/cache is an exact semantic closure with a **durability/availability status**, not a promise that browser storage can never evict it. Missing required cached bytes yield `offline_unavailable`; the runtime cannot silently re-resolve to another version.

## 4. Artefact taxonomy and relationships

The project needs explicit artefact roles because conflating them would make editing, reproducibility, security and persistent worlds ambiguous.

| Artefact | Mutable? | Contains/points to | Executes user content? | Identity role |
|---|---:|---|---:|---|
| **EditableProject** | yes, revisioned | canonical authored graph, editor metadata/history, package requirements + exact project lock, source records | no by itself | `ProjectId` + project revision |
| **PublishedCreationRevision** | immutable | runtime projection of one accepted project revision, exact package lock, protected asset descriptors, constrained IR, feature/capability/network declarations | only after generic-runtime validation | stable `CreationId` + immutable `CreationRevisionId` |
| **ComponentPackageRevision** | immutable | SMX-013 reusable Definition/behaviour/assets and dependency declarations | only as validated dependency | `PackageId` + immutable package revision; not creation identity |
| **WorldSave / PersistentWorldRevision** | revisioned/appendable by persistence policy | runtime progress/state against a declared creation basis and world schema | restored into a compatible runtime | `WorldId` + world revision, separate from creation |
| **GenericPlayerRuntime** | immutable build | trusted interpreter/scheduler/adapters/validators for web/native | yes, after prepare/validation | `RuntimeId` + runtime version + build digest |
| **GenericServerRuntime** | immutable build | trusted headless runtime/authority/persistence/network adapters | yes, after same semantic gates | runtime build identity; not creation identity |
| **HostedRelease** | immutable release record | exact creation revision + runtime-selection policy/channel | launches through generic runtime | `ReleaseId`; discovery wrapper only |
| **Share/Embed Alias** | intentionally mutable | points to one HostedRelease | no | human/discovery locator, never canonical content identity |
| **OfflineBundle** | immutable bundle/installed set | exact creation/dependency/asset closure + compatible runtime identity/build or locally installed runtime requirement | launches without re-resolution | distribution wrapper; does not replace creation identity |
| **Target payload/derived cache** | reconstructible | web/native/headless-selected/transcoded bytes | no independent semantics | digest/cache identity only |
| **Exceptional per-creation build** | immutable trusted build | creation plus explicitly trusted host integration | privileged path | separate security/product class, not ordinary publish |

### 4.1 Editable project versus published creation

An editable project may contain collaboration history, local branches/conflicts, thumbnails/previews, editor selections, pending unaccepted edits, package requirements, and other authoring state that is not needed for playback. Publication selects a coherent accepted project revision and deterministically projects only runtime-required semantic records plus distribution metadata.

`ProjectId` is not `CreationId`, and project revision is not `CreationRevisionId`. A project may publish multiple immutable creation revisions over time; a creation lineage may also be forked/remixed according to provenance/licence policy.

### 4.2 Creation versus component

A component package is reusable implementation/content that may appear in many projects or creations. A published creation is a launchable top-level semantic revision with entry points, target/runtime compatibility requirements and an exact dependency lock. Packaging a local definition does not turn it into a creation, and publishing a creation does not rewrite its component `PackageId`/Definition lineage.

### 4.3 Creation versus persistent world/save

The creation defines the executable authored basis. A world/save records selected runtime state and points to the compatible creation basis. Publishing a new creation revision never silently edits an existing world. A world may migrate only through an explicit, bounded, validated world/content migration path.

### 4.4 Runtime versus content

The player/server runtime is trusted executable platform code. The creation and its component packages are hostile **data + constrained logic**. A runtime build digest/version is needed for reproducibility and deployment, but it is never authored Thing/Asset/Creation identity.

## 5. Published creation identity and runtime manifest

### 5.1 Identity domains

At minimum:

```text
ProjectId / ProjectRevisionId        mutable authoring lineage/revision
CreationId                           stable published-creation lineage
CreationRevisionId                   exact immutable published semantic revision
PackageId / PackageRevisionId        reusable component distribution identity
AssetId / AssetRevision              protected media/source revision identity
WorldId / WorldRevisionId            persistent runtime-state lineage
RuntimeId / RuntimeVersion / digest  trusted player/server build identity
ReleaseId                            immutable hosted publication record
share/embed alias or URL             mutable locator only
blob digest                          immutable byte identity only
```

None are aliases for another role. In particular, a URL cannot become a `CreationId`, and a runtime build digest cannot become a `CreationRevisionId`.

### 5.2 Candidate publication manifest semantics

The physical encoding remains open, but a published creation must express equivalent semantics to:

```text
PublishedCreationManifest
  CreationId
  CreationRevisionId
  source ProjectRevisionId / derivation lineage
  canonical semantic digest

  compatibility
    canonical schema version/features
    behaviour IR version/features
    required semantic features
    optional semantic features + declared fallback/omission behaviour
    required/optional extension envelopes

  entry points
    startup/root Things or equivalent stable semantic IDs
    topology-independent network declarations

  exact dependencies
    exact SMX-013 resolution lock digest
    PackageId + exact PackageRevisionId + digest + size + requirements

  protected assets
    AssetId + complete immutable asset revision bundle
      digest
      source identity/metadata
      audio/media semantics
      provenance/licence/derivation
    usage role: simulation_required | presentation_required | presentation_optional
    target-private derivative descriptors, if any, with derivation links

  capability requests
    principal-attributed semantic capability requests
    required/optional + rationale/scope declaration
    NO live grant/handle

  migration/compatibility descriptors
    accepted source/target schema/IR/world migration identifiers
    no arbitrary install/migration host code
```

The manifest must contain enough stable information to produce a reproducibility record: exact creation revision, exact dependency lock, exact runtime build/profile, target, exact required payload digests, and applied migration chain.

### 5.3 Publication is transactional

A publish operation validates the selected authored revision, exact dependency closure, protected media bundles, interfaces, IR/schema features and publication policy before the new immutable `CreationRevisionId` becomes visible as a release. A failed publish leaves the previous hosted release/alias target unchanged. Verified inert cache bytes may remain, but no half-published creation becomes executable.

## 6. Generic-player launch pipeline

The generic player is valuable only if it is a **validation and compatibility boundary**, not a loader that activates first and discovers problems later.

Candidate launch sequence:

1. **Resolve a release/locator to an immutable `CreationRevisionId`.** Record the resolved identity; mutable alias lookup ends here.
2. **Parse with hard structural/size/depth/count limits.** Parsing success confers no trust.
3. **Verify manifest/revision integrity.** Validate exact revision/digest/size relationships and reject identity collisions.
4. **Negotiate runtime/schema/IR/required semantic features.** Unknown required semantics fail before activation. Optional semantics may be omitted only when the manifest explicitly allows it.
5. **Plan deterministic migrations in staging.** Migrations are bounded, capability-free by default, side-effect-free, identity preserving unless an explicit semantic remap is part of the transaction, and validated before commit.
6. **Acquire the exact locked dependency closure.** Playback does not run a floating dependency solver. Required package revisions/digests/sizes are exact SMX-013 locks; no “compatible cached substitute”.
7. **Verify protected asset descriptors and target-required bytes.** Digest/source/audio/provenance/licence/derivation records remain complete. Target-private transcodes/imports are linked derivatives.
8. **Evaluate capability requests against current host/user policy.** A package signature, publisher identity, hosted origin, paid status, containment or dependency edge never mints authority. Required denial blocks launch; optional denial takes only an explicitly declared degraded path.
9. **Build a target-private projection.** Select presentation/simulation payloads for web/native/headless without rewriting canonical semantic records.
10. **Create substrate bindings/services only after the semantic plan passes.** Godot Nodes/RIDs/resources/audio objects/transports remain transient.
11. **Atomically activate.** Only now can constrained user IR execute or capability-mediated services issue requests.

The disposable SMX-014 `GenericPlayer.prepare()`/`activate()` split directly tests the critical ordering: incompatible runtime/schema/IR/features, missing/corrupt locked blobs, invalid protected media, denied required capabilities and forbidden engine identity all fail while `activation_count == 0`.

## 7. Compatibility, migration, and unsupported future content

Compatibility is declared in SplashMX terms, not “the same Godot version”.

### 7.1 Older content on a newer runtime

A runtime may directly support the content's schema/IR/features or apply an explicit deterministic migration chain in staging. Successful migration does not replace the historical immutable publication; it produces a runtime materialization tied to the original `CreationRevisionId` plus a recorded migration path. Re-publishing migrated source as a new authored revision is a separate author operation.

### 7.2 Newer content on an older runtime

- Unknown **required** schema/IR/semantic feature/extension => typed incompatibility such as `runtime_upgrade_required` / `required_feature_unsupported`; no partial execution.
- Unknown **optional** extension => preserve/ignore only through an explicit optional compatibility envelope; omission is recorded.
- A runtime must not reinterpret an unknown field as “probably safe”, strip it from canonical source, or mark a different compatible package revision as equivalent.

### 7.3 IR compatibility

The runtime advertises supported IR versions/features. A migration/compiler from an older accepted IR may produce a validated target IR only if semantics are defined and bounded. Arbitrary user text/GDScript/C#/native code cannot become a migration escape hatch.

### 7.4 World/save compatibility is independent

A world records its basis `CreationId`/`CreationRevisionId` and its own world-state schema. Updating creation content can require world migration even when the new creation runs in the same generic player. Failing world migration leaves the old world revision intact and typed as requiring its prior basis/runtime or explicit conversion.

### 7.5 Runtime channels and longevity

A hosted service may use a runtime channel such as “stable-compatible”, but launch must resolve that channel to an exact runtime build/version before activation and log the build in the reproducibility record. A historical publication remains an immutable content revision even when the recommended runtime advances.

A future compatibility service may maintain old runtimes, migrations, or emulation policy, but runtime selection is deployment policy rather than content identity.

## 8. Web, native, and headless/server projection

All targets consume one canonical `PublishedCreationRevision`. They may differ in **runtime implementation and payload closure**, not in authored identity/meaning.

| Concern | Web generic player | Native generic player | Headless/server generic runtime |
|---|---|---|---|
| Canonical creation revision | same | same | same |
| Thing/Definition/Asset/Package IDs | same | same | same |
| Behaviour IR/network declaration | same | same | same |
| Rendering/audio substrate | browser/Godot web limits | native Godot/device | absent/dummy unless semantically required service |
| Storage | browser policy/IndexedDB adapter | native store adapter | server durable store adapter |
| Network transports | browser-safe adapters | native adapters | server adapters |
| Presentation asset bytes | include required; optional may be omitted/fallback | include required; optional may be omitted/fallback | presentation-only bytes may be omitted |
| Simulation/collision/nav/script-data bytes | required if semantics depend on them | required | **required** |
| Capability host permissions | browser policy + SplashMX policy | OS + SplashMX policy | service/operator + SplashMX policy |
| Target-private derived/transcoded assets | allowed with derivation link | allowed | usually omitted/optimized |

### 8.1 Asset stripping rule

Asset stripping is driven by SplashMX semantic usage, not Godot type names.

- `simulation_required`: cannot be stripped on any target that claims to execute the relevant semantics.
- `presentation_required`: required on a presentation target; may be omitted by a declared non-presentation headless profile when no simulation semantic depends on the decoded media.
- `presentation_optional`: may be omitted when the manifest defines the degraded presentation outcome.

If authoritative gameplay reads image dimensions/pixels, audio analysis, geometry, animation curves or other data, that data is **simulation-required** regardless of whether the original file looks “visual”. A server exporter cannot infer semantic dispensability from extension or Godot class alone.

### 8.2 Protected media across target projection

The canonical manifest continues to name the complete protected `AssetId` revision bundle even when a target payload omits source bytes. A web transcode, native import product, GPU texture, decoded audio stream or server placeholder is a derived/cache artefact and must not replace source identity, digest/provenance/licence or author-intended audio/media semantics.

## 9. Hosted releases, share links, and embeds

A hosted service needs two different concepts:

1. **immutable release record** — exact `ReleaseId`, `CreationRevisionId`, publication metadata and runtime-selection policy;
2. **mutable discovery alias** — friendly URL/share code/embed target that may be retargeted intentionally by the publisher.

Resolving `https://host/play/my-demo` may return release `R7`, but the active launch/reproducibility record captures `R7`, exact `CreationRevisionId`, exact dependency lock and resolved runtime build. If the alias later points to `R8`, existing `R7` remains retrievable/reproducible according to retention policy and is not silently rewritten.

An embed is the same launch contract in a host surface. It does not grant new capabilities. Embedding origin, browser permission and host policy remain additional gates below SplashMX capability policy.

Hosted URLs/CDN paths are distribution locators. They may change without changing canonical identity.

## 10. Offline bundle and cache contract

Offline is not “try the cache and hope”. An offline-capable launch has a known exact closure.

An `OfflineBundle`/installed offline set records or contains:

- exact `CreationRevisionId` and manifest;
- exact SMX-013 package/dependency lock;
- every target-required immutable asset/dependency byte digest;
- optional payloads/fallback declarations as selected;
- a compatible generic runtime build/profile **or** an exact runtime requirement satisfied by a locally installed trusted runtime;
- migration material required for that supported runtime path;
- no live capability grants/peer/session/host handles.

Offline launch:

- never contacts a registry merely to decide what version to use;
- never substitutes another “compatible” cached package/runtime when the exact closure is promised;
- verifies cached bytes before activation;
- re-evaluates capabilities against current device/user policy;
- reports `offline_unavailable`/`offline_runtime_mismatch`/typed incompatibility when closure is incomplete;
- can still deny or degrade a feature whose semantic capability intrinsically needs network/cloud access.

For browser storage, “installed offline” should expose durability status because IndexedDB/quota/private-mode policy can invalidate availability. Cache eviction remains non-semantic: it cannot mutate `CreationRevisionId`, package lock, `AssetId` or world state.

## 11. Persistent save/world and server-owned state

A persistent world is **not** an editable project and not a published creation package. It is selected runtime state anchored to an authored basis.

Candidate world header:

```text
WorldSave
  WorldId
  WorldRevisionId
  basis CreationId
  basis CreationRevisionId
  world-state schema/version
  selected persistent Thing/attachment/state records
  durable logical timers/pending work according to SMX-007
  exact dependency requirements necessary to restore
  provenance/branch/checkpoint metadata as needed
  NO live peer IDs, sockets, Godot objects, capability handles or host authority tokens
```

A dedicated server may own authoritative world revisions/checkpoints while clients possess only a published creation and session projections. Server ownership does not alter authored `ThingId`/AssetId/package/source/provenance meaning.

Changing server topology, migrating host, or moving a world checkpoint uses SMX-008/010 semantic migration/state rules; it does not convert the world into a Godot scene save.

## 12. Exceptional per-creation build path

SMX-014 finds no ordinary requirement that currently justifies per-creation Godot export. H-015 is therefore strengthened, not rejected.

An exceptional build may exist only where a creation deliberately enters a **different trusted product/security class**, for example an operator-controlled deployment requiring a reviewed native integration or platform feature that cannot be expressed by the ordinary capability/IR/runtime contract.

Rules:

- it is opt-in and visibly outside ordinary community-content trust;
- it cannot be triggered automatically by “unsupported required feature”; the normal result is typed incompatibility/runtime upgrade, not silent code generation;
- it cannot be used to smuggle arbitrary GDScript/C#/GDExtension/JavaScriptBridge authority into ordinary packages;
- it receives a distinct build identity, trust/review/deployment policy and compatibility statement;
- the canonical SplashMX creation remains separately identifiable so the privileged wrapper does not become semantic identity;
- beginner Publish UI need not expose Godot export presets/templates/toolchain.

If later SMX-015/019 measurements show the generic runtime materially fails core performance/startup/size requirements, H-015 must be refined with measured boundaries rather than broadening the exceptional path by convenience.

## 13. Candidate invariants and executable evidence

### 13.1 Publishing/runtime invariants

- **PUB-001 — artefact roles are explicit.** Editable project, published creation, component package, world/save, runtime, hosted release and offline bundle are not interchangeable.
- **PUB-002 — publication is an immutable projection.** Publishing selects one coherent project revision and creates an immutable `CreationRevisionId`; it does not make the mutable project itself the runtime package.
- **PUB-003 — identity domains remain distinct.** `ProjectId`, `CreationId`, `CreationRevisionId`, `PackageId`, `WorldId`, runtime build identity, release ID, URL and blob digest retain separate roles.
- **PUB-004 — generic runtime is the ordinary path.** Normal Publish does not invoke a per-creation Godot export/compile step or require author knowledge of export presets/templates/toolchains.
- **PUB-005 — targets share one canonical revision.** Web/native/headless launch the same `CreationRevisionId` and canonical network/object semantics.
- **PUB-006 — compatibility negotiation precedes activation.** Runtime/schema/IR/feature compatibility is checked before user IR executes or live substrate bindings/services become available.
- **PUB-007 — unknown required semantics fail closed.** Unknown required feature/extension/IR/schema cannot be silently ignored; explicitly optional semantics may be omitted only under declared fallback rules.
- **PUB-008 — migration is staged and capability-free by default.** Migration is deterministic/bounded/validated before commit and cannot gain ambient host authority.
- **PUB-009 — runtime consumes exact package locks.** Launch/stream/offline use SMX-013 exact immutable package revisions, not floating compatibility ranges.
- **PUB-010 — exact required closure is verified before activation.** Missing, size-mismatched, digest-mismatched, revoked/incompatible or otherwise invalid required dependencies/assets block launch.
- **PUB-011 — capability policy is evaluated before user execution.** Required denial blocks activation; optional denial follows only explicit degraded semantics.
- **PUB-012 — distribution trust does not grant authority.** Hosting origin, signature, publisher identity, package installation, purchase/source/remix/licence/provenance status cannot mint host capabilities.
- **PUB-013 — target payload variance is non-semantic.** Web/native/headless may use different cache/import/transcode/payload closures without forking creation identity.
- **PUB-014 — stripping follows semantic usage.** Headless may omit presentation-only payloads but never simulation-required data/dependencies merely because Godot classifies them as visual/audio resources.
- **PUB-015 — protected asset revisions remain indivisible.** Digest + source identity/metadata + audio/media semantics + provenance/licence/derivation remain one revision; partial/cross-version synthesis is rejected.
- **PUB-016 — target derivatives never replace canonical source meaning.** Transcodes/imports/placeholders/decoded objects retain derivation links and cannot rewrite `AssetId`, source/audio identity or provenance.
- **PUB-017 — world/save is a separate artefact lineage.** Runtime progress is not silently folded into published creation or editable authored data.
- **PUB-018 — persistent world excludes transient authority handles.** Peer/session/socket/Godot/capability handles are rebound from current runtime/security policy.
- **PUB-019 — content update does not silently update a world.** Basis mismatch requires an explicit world/content migration or continued execution against the prior compatible basis.
- **PUB-020 — hosted launch resolves to an immutable release before execution.** Friendly aliases/URLs end at exact release/content/runtime-policy inputs.
- **PUB-021 — mutable aliases do not mutate historical releases.** Retargeting a share alias leaves old immutable release/revision identity intact.
- **PUB-022 — offline launch uses a known exact closure.** It does not re-solve versions or require cloud authority for ordinary playback.
- **PUB-023 — incomplete offline closure fails typed.** Missing required cached bytes/runtime/migration material produces an explicit unavailable/incompatible outcome, never silent substitution.
- **PUB-024 — target limitations are typed runtime capabilities.** Web/native/headless differences surface through required/optional feature negotiation, not separate canonical creation classes.
- **PUB-025 — per-creation builds are exceptional trusted deployment.** They are not a fallback for ordinary unsupported untrusted content and do not redefine normal Publish.
- **PUB-026 — public manifests exclude engine/build identity.** Godot Nodes/NodePaths/RIDs/ResourceUIDs/scenes/PCK executable semantics/export presets and live host handles are not durable public creation contracts.
- **PUB-027 — hosted/share/embed/native launcher reference the same creation identity.** Distribution surface does not create separate content lineages unless an author intentionally publishes a different revision.
- **PUB-028 — reproducibility records pin both content and trusted runtime.** Exact creation revision, dependency lock, runtime build/profile, target payload digests and migration chain are recordable.
- **PUB-029 — server/headless remains a topology/target projection.** It consumes the same authored network declarations/Thing IDs while runtime authority/topology/context is selected separately.
- **PUB-030 — publication/activation are atomic state transitions.** Failed validation/migration/acquisition does not leave a half-published or half-active revision; the prior coherent release/runtime remains intact.

### 13.2 Machine-addressable fixtures

`docs/research/SMX-014-PUBLISHING-FIXTURES.json` defines `PB-001` through `PB-020`. Required acceptance cases include artefact taxonomy, generic-player/no-author-export, compatibility/future content, target projection, pre-execution security, offline/hosted modes, SMX-017/019 handoffs, and protected-media preservation.

### 13.3 Disposable executable proof

`experiments/smx-014-publishing-model/` contains:

- deterministic publish projection with stable `CreationId` and content-derived immutable revision;
- precompiled `RuntimeContract` profiles for web/native/headless;
- prepare-before-activate ordering;
- exact dependency/blob validation;
- required/optional feature/extension handling;
- bounded capability-free migration examples;
- capability denial before activation;
- presentation stripping versus simulation-required assets;
- complete protected media revision checks;
- separate world-basis compatibility;
- hosted immutable releases with retargetable aliases;
- exact offline bundle/runtime checks;
- exceptional per-creation-build policy;
- reproducibility records.

The 39 deterministic tests intentionally include adversarial cases for engine/capability-handle smuggling, digest/size corruption, missing exact dependencies, migration identity rewrite/loops, required-future semantics, release ID collisions, transient world handles, offline runtime mismatch, protected media incompleteness, and headless over-stripping.

This is sufficient to strengthen the **semantic feasibility** of generic players. It is not evidence for production browser startup size, Godot object count/frame time, CDN/cache throughput, cryptographic trust, installer UX, or long-term storage durability.

## 14. Concrete SMX-017 topology-equivalence handoff

SMX-017 must not invent a package/runtime shape independently. Its minimum input contract is:

### 14.1 One immutable publication fixture

Prepare one `PublishedCreationRevision` containing at least:

- stable `CreationId` + exact `CreationRevisionId`/manifest digest;
- one local-controlled Thing, one shared/authority-controlled Thing and one persistent/reconnect-relevant Thing;
- the same topology-independent SMX-010 network declarations for every mode;
- bounded validated IR;
- at least one exact component dependency from the SMX-013 lock;
- one simulation-required asset/data dependency;
- one presentation-only asset that headless is allowed to omit;
- complete protected source/audio/provenance records;
- zero Godot peer/Node/RPC/transport identities in canonical content.

### 14.2 Three launch envelopes over the same publication

Run **the exact same `CreationRevisionId`** as:

1. offline/local through a generic player;
2. peer-hosted browser through a generic web player + peer topology policy;
3. dedicated-authoritative through browser client generic player(s) + generic headless server runtime.

Each run records:

- `CreationRevisionId`/manifest digest;
- exact package-lock digest/revisions;
- player/server runtime versions + build digests;
- target profile(s);
- selected target payload digests/omissions;
- topology/session policy separately from canonical content;
- authority epochs and reconnect/host-migration watermarks from SMX-010;
- semantic output/event/state trace for equivalence comparison.

The headless target may have a different **payload digest set**, but canonical creation/package/source/provenance identity must match. A topology requiring a different authored creation package is a failure unless a previously declared target-required feature explains it and the architecture is explicitly amended.

### 14.3 Failure cases SMX-017 must include

- packet reorder/loss/duplicate where transports allow;
- browser suspension/reconnect with changed peer identity;
- stale authority epoch after transfer;
- host loss/checkpoint recovery outcome;
- missing/incompatible runtime or exact dependency on one target;
- denied capability on one target;
- headless stripping attempt of simulation-required content;
- source/audio/provenance equality across all target projections.

## 15. Concrete SMX-019 browser vertical-slice handoff

SMX-019 must demonstrate the product promise against this publication contract rather than bypass it with a development build.

Minimum end-to-end path:

```text
blank browser editor
 -> create Things
 -> add Rule/Behaviour + Connection
 -> Play immediately
 -> save/reload editable canonical project
 -> Publish
      [deterministic PublishedCreationRevision + exact package lock]
 -> hosted/share URL resolves immutable release
 -> generic browser player loads + validates + activates it
 -> install/cache exact offline closure
 -> reload same published revision offline
```

Required evidence/gates:

- the ordinary author path never exposes Godot project export, export preset/template, Node/SceneTree/Resource/PCK, package solver/lock syntax, runtime ABI, WebRTC/WebSocket channel numbers or build-system concepts;
- Inspect/advanced diagnostics can show stable SplashMX terms and exact revision/runtime information without making those concepts prerequisites for normal Publish;
- measure cold/warm player startup, publish projection time, manifest/package size, required download bytes, activation latency, memory/frame time at a stated workload, and browser storage/offline outcomes;
- exercise current browser storage failure/eviction/private-mode behavior with typed diagnostics;
- exercise required/optional capability denial;
- confirm source/audio/provenance bundle equality before and after publish/load/offline;
- confirm a hosted share and an offline copy resolve the same `CreationRevisionId`;
- if a runtime upgrade/migration is needed, show a comprehensible typed outcome rather than arbitrary failure;
- no per-creation Godot export may be substituted for the generic-player path while claiming the gate passed.

SMX-019 remains responsible for actual usability, accessibility, discoverability and browser deployment evidence; the SMX-014 Python model does not satisfy those gates.

## 16. Rejected alternatives and residual questions

### Rejected by this issue

**Per-creation Godot export as ordinary Publish.** Rejected because it exposes/builds platform-specific executables per content revision, expands trusted code/distribution surface, couples compatibility to Godot project/export machinery, and is unnecessary for the semantic cases tested by SMX-009/014.

**Godot PCK/mod as the ordinary untrusted creation contract.** Rejected because Godot packs may contain executable engine scripts/scenes and upstream documentation explicitly treats malicious replacement/mod code as a security concern. A SplashMX package must be parsed/validated under SplashMX's constrained execution boundary.

**One artefact for project + creation + save/world.** Rejected because authoring history, immutable publication and evolving runtime progress have different mutability, conflict, security and migration semantics.

**URL/path/runtime build as content identity.** Rejected because hosts, mirrors, aliases and runtimes must evolve without rewriting semantic creation identity.

**Floating dependency resolution at launch.** Rejected by SMX-013/014 reproducibility and offline requirements; intentional update is a separate resolve/update transaction.

**“Best effort” unknown required feature handling.** Rejected because silent omission can alter authored meaning. Required unknown semantics fail closed before activation.

**Server resource stripping by file type/Godot class alone.** Rejected because apparently visual/audio/media bytes can be simulation inputs; semantic use determines requiredness.

**Capability grants embedded in published/offline packages.** Rejected because grants are current host/user policy, not portable authority tokens.

### Still open / handed downstream

- final physical creation/package/container/index encoding and compression;
- CDN/repository/discovery/federation/mirroring design;
- signature/trust-root/rotation/revocation freshness implementation;
- exact runtime compatibility-range syntax/channel retention policy;
- browser/native cache/store journaling, quota/eviction durability and crash consistency;
- target transcode/build farm policy and provenance attestations;
- native installers/app-store wrappers and trusted host integration;
- real Godot/browser startup, memory, object-fabric and frame cost;
- package/download/activation performance and practical maximums;
- lifetime/retention policy for historical runtimes/releases/world migrations.

SMX-016 attacks concrete parser/trust/capability implementations; SMX-017 tests topology equivalence; SMX-019 tests the actual browser author/player/offline UX and performance; SMX-020 chooses/finalizes Architecture v1.0 based on those results.

## 17. Hypothesis reconciliation

### H-014 — Godot can remain a replaceable-enough substrate boundary

**Strengthened further at publishing/runtime-contract level, still subject to real integration/performance falsification.** Ordinary creation identity, package lock, compatibility/migration, hosted/offline distribution, protected source/audio/provenance and world/save semantics remain above Godot. Godot export tooling is needed to produce trusted generic runtime builds, not every creation. Runtime media loading and headless operation provide current substrate mechanisms without promoting Godot project/PCK identity to the public contract. Real startup/frame/object/storage cost remains for SMX-015/019.

### H-015 — Generic players are preferable to per-creation builds

**Strengthened substantially at semantic/proof-model level.** One immutable creation revision is deterministically loaded by precompiled web/native/headless runtime profiles; 39 tests exercise compatibility negotiation, exact dependencies/assets, migrations, capability denial, offline bundles, hosted releases, world separation and target stripping before activation. Current Godot capabilities do not expose a semantic requirement for a per-creation build. The hypothesis is **not production-proven** until SMX-017/019 exercise actual browser/server runtimes, startup/distribution size/performance and author experience.

### H-018 — Compatibility can be migration-driven rather than engine-version-driven

**Strengthened further at publication/runtime-negotiation level.** Runtime support is expressed as schema/IR/feature compatibility plus explicit migration paths and typed unsupported-future outcomes; world saves carry an explicit creation basis and separate migration. A historical content revision does not become “compatible” merely because Godot can deserialize something, nor “incompatible” merely because the trusted runtime build changes. Future real cross-version/runtime migrations remain destructive gates for SMX-015/019/020.

No prior source/audio/provenance, package/capability, lifecycle, multiplayer, collaboration or authoring decisions are weakened by SMX-014.
