# SMX-036 — Immutable publication, generic player, and exact offline closure

**Status:** production implementation  
**Issue:** SMX-036 / #61  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md` §§5, 6, 9, 10  
**Depends on:** SMX-029, SMX-033, SMX-035

SMX-036 implements Architecture-v1 publication without introducing a second
document model or per-creation engine build. The publication unit is immutable
SplashMX data consumed by a separately built generic player. Hosted location,
friendly names, offline placement, persistent WorldSave state, target-private
media derivatives, and future engine bindings remain separate roles.

## Production contract

Ordinary Publish is:

`validated authored project + exact ResolutionLock + every locked package byte sequence -> immutable CreationRevisionId`

It is **not**:

`authored project -> Godot export/compile -> per-creation executable`

`CreationId` is the stable creation lineage. `CreationRevisionId` is derived
from deterministic-CBOR publication metadata that exact-digest binds the
canonical project root, every project shard, the exact resolution lock, every
locked package revision, required features, and the generic-player profile.
Changing any semantically relevant member therefore creates another immutable
revision. A `HostedReleaseId` can bind an immutable revision; a friendly alias
can deliberately retarget between releases, but neither alias nor URL becomes
canonical identity.

The publication input surface accepts only `CanonicalProjectRevision`,
`ResolutionLock`, and exact package bytes. Editor/session state, collaboration
history, live runtime state, WorldSave contents, capability grants, engine
objects, browser objects, transport/session handles, and distribution URLs
have no publication field.

## Exact closure and no floating

Publication requires bytes for **every** `PackageRevisionId` named by the
resolution lock, including lazy packages. It refuses missing, extra, wrong-size
or wrong-digest package substitutions. Each bundle is parsed and checked against
its exact lock identity/version and exact dependency edges before a creation is
formed.

This is intentionally stronger than ordinary streaming residency: a package
may be lazy at runtime while still being part of the complete offline-capable
publication closure. Offline launch is keyed by exact `CreationRevisionId`.
There is no compatibility-range lookup or catalog re-solve on offline load and
there is **no runtime floating** to another package or creation revision.

The same immutable publication object is accepted by hosted and offline paths.
Caching or installation changes placement only; it does not mint another
creation identity.

## Generic player prepare-before-activate

`GenericPlayer.prepare()` follows the Architecture-v1 fail-closed order:

1. bounded deterministic-CBOR parse of the creation envelope;
2. recompute and verify `CreationRevisionId`;
3. reject unsupported required creation features;
4. require the blob map to equal the declared exact closure;
5. digest/length verify every declared blob;
6. reconstruct and validate the canonical project;
7. parse the exact package lock;
8. bind every package descriptor to the exact lock revision/digest/size;
9. parse and validate every package, including lazy package bytes;
10. enforce exact package dependency edges;
11. reject competing protected Asset revisions;
12. run the production package owner for active-package capability policy and
    component reconciliation;
13. return a `PreparedCreation`.

Only `GenericPlayer.activate()` crosses the later runtime-binding seam. A
failure in parse, integrity, compatibility, dependency validation, protected
media, or current capability policy therefore occurs **before activation**.
No fallback path converts unsupported ordinary content into privileged generated
code.

SMX-036 does not implement the Godot realization itself. SMX-038 owns the
web/native/headless engine adapters; they consume this prepared semantic result.

## Hosted identity

`HostedReleaseStore` deliberately exposes three roles:

- `CreationRevisionId`: immutable semantic publication identity;
- `HostedReleaseId`: immutable hosted release binding;
- friendly alias: mutable lookup convenience.

A release cannot be rebound to another creation revision. A friendly alias may
retarget. Direct access to an older immutable release/revision remains stable
after alias retargeting. This models future hosting without allowing CDN paths,
URLs, aliases, or cache keys to become canonical identity.

## Offline install and load

`OfflineLibrary.install()` verifies a complete publication through the same
generic-player preparation path before storing it. Installed data is keyed
solely by exact `CreationRevisionId`; missing exact content returns a typed
`publication.offline_unavailable` outcome.

Hosted and offline loading call the same `GenericPlayer.prepare()` and
`activate()` implementation. The execution substrate therefore does not fork
merely because bytes came from hosted distribution or a local install.

## WorldSave identity and basis

WorldSave remains the SMX-029 persistent runtime-state plane and is not embedded
inside a creation revision. `WorldSaveBasis` records an explicit relation:

`WorldSaveId -> CreationRevisionId + ProjectId + ProjectRevisionId`

The roles remain distinct types. Binding validates the authored project basis,
and restore/load code can reject a save that names another immutable creation
basis rather than guessing from a friendly alias or current hosted release.
SMX-036 does not revise the existing WorldSave physical schema.

## Protected source/audio/provenance boundary

The protected-media invariant is unchanged and is enforced across the complete
publication closure. A stable `AssetId` selects one indivisible immutable
revision containing:

- source digest and source identity;
- exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence and attribution;
- derivation lineage.

If the authored project and a package present competing revision digests for the
same `AssetId`, publication fails. The system **may not combine fields from
competing Asset revisions**.

Target-private stripping, decoding, transcoding, engine import, or cache
placement is represented only as a derivative that records the canonical Asset
revision it came from. A derivative can be discarded and recreated; it cannot
rewrite the protected canonical revision or acquire authority from provenance or
licensing metadata.

## Adversarial and boundary coverage

`spec/production/smx036-publishing-fixtures.json` freezes PUB-001..PUB-024.
Direct production tests cover:

- deterministic publication/revision derivation;
- hosted/offline equality for the same `CreationRevisionId`;
- mutable alias retargeting without immutable release mutation;
- exact missing-offline failure without floating;
- lazy-package inclusion in complete offline closure;
- tampered creation envelope, project shard and package bytes before activation;
- same-count/floating package revision substitution;
- unknown required creation features;
- unreferenced blob smuggling;
- protected-Asset cross-closure field-mixing attempts;
- WorldSave/creation identity separation and explicit basis validation;
- target-private derivative substitution attempts;
- immutable release and same-revision rebinding attempts.

The retained SMX-024, SMX-027, SMX-029, SMX-030, SMX-033 and SMX-035 tests
remain in the dedicated SMX-036 workflow so canonical serialization,
capabilities, lifecycle, exact streaming, browser runtime, package locking and
protected-media regressions are not weakened by publication.

## Scope boundary

Still deliberately outside SMX-036:

- per-target Godot realization and web/native/headless production profiles
  (SMX-038);
- decoder/process isolation and production trust/signature enforcement
  (SMX-040/041);
- CDN operations, broad hosting, runtime-retention operations, installers and
  backup/import/export distribution (SMX-050);
- marketplace/discovery UX.

Those later layers must consume `CreationRevisionId` and exact verified closure
semantics rather than replacing them.
