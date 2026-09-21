# SMX-050 — Production distribution, runtime retention and recovery

**Status:** Phase-10 production implementation  
**Issue:** SMX-050 / #75  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Depends on:** SMX-036, SMX-038, SMX-041, SMX-044, SMX-047 and SMX-049

SMX-050 implements the physical distribution machinery required by the SMX-049
compatibility programme without changing canonical project/package/creation/
WorldSave meaning. Distribution is placement, availability and recovery. URLs,
CDN keys, aliases, installer state, runtime artifact digests and service health
remain operational identities and never replace SplashMX semantic identities.

## Exact hosted release and runtime retention

Every immutable hosted release binds all of the following as one immutable
operational record:

`HostedReleaseId -> exact CreationRevisionId + exact runtime profile + exact runtime digest`

The creation remains the SMX-036 immutable creation closure. The runtime is a
separately content-addressed generic SplashMX runtime artifact. A later runtime
with compatible behaviour receives its own artifact digest and must be separately
qualified; an existing immutable release is never silently floated to it.

Friendly aliases may retarget between immutable HostedReleaseIds. CDN/cache
objects are addressed by byte digest and may be evicted or re-populated. **Aliases
and CDN/cache keys are non-canonical**: neither can become a ProjectRevisionId,
PackageRevisionId, CreationRevisionId, WorldSaveId, AssetId or ThingId, and cache
invalidation cannot alter semantic identity.

Retained runtimes have explicit eligibility/revocation state. Current security
policy wins over historical compatibility: a revoked retained runtime is not made
executable merely because an old creation references it. Storage accounting is
explicitly `sum(unique runtime digest bytes * deployment copies)` rather than an
implicit promise that retention is free.

## Exact offline ownership and cloud/service loss

An offline installation contains the exact verified PublishedCreation plus the
exact runtime profile, target, digest and runtime bytes required to execute it.
It is keyed by CreationRevisionId and is prepared through the same SMX-036
GenericPlayer verification boundary before installation.

**Cloud/service loss does not invalidate local project ownership or an already
installed exact offline creation/runtime closure.** Hosting, collaboration and
runtime-networking outages produce typed operational outcomes and append
operational health evidence, but that state is not serialized into canonical
projects, WorldSaves or publication data. Offline launch requires neither alias
resolution nor CDN/service availability.

Local revocation policy still applies to installed runtime bytes. This is not a
back door around SMX-049 security precedence: exact offline means network
independence, not immunity from an administrator/user security decision.

## Recovery, backup, export and import

The production recovery archive is deterministic bounded canonical CBOR and can
carry three independently validated planes:

- one serialized canonical ProjectRevision;
- exact offline creation/runtime installations;
- exact WorldSave revisions.

Large byte strings are physically chunked only to stay inside the existing
bounded deterministic-CBOR byte-string limit. Chunking is transport-private and
does not change any digest or semantic identity.

Export validates the project, creation/package closure, runtime digest and each
WorldSave before constructing the archive. Import is prepare-before-publish:
canonical project deserialization, CreationRevision/package verification, runtime
digest verification and WorldSave deserialization all complete before the
returned recovery bundle can be installed. Duplicate semantic revisions and
creation/runtime tampering fail typed. Transient process/browser/network/session/
capability authority is never synthesized by recovery.

## Native packaging evidence boundary

The current production evidence justifies an exact portable native/headless
payload that embeds one verified offline creation/runtime install. The payload is
self-verifying and preserves the same CreationRevision and runtime binding as the
normal offline library.

**No OS-specific installer technology is selected by SMX-050.** There is not yet
product evidence that an MSI, MSIX, DMG, PKG, DEB, RPM, Flatpak, AppImage or other
platform installer should become a required production mechanism. Inventing one
would violate the issue's requirement to implement native installers only where
product evidence justifies them. Unsupported targets therefore fail typed rather
than receiving an improvised weaker path. Browser distribution remains hosted/
offline web content, not a "native installer".

## Operational resilience

`ServiceHealth` records availability and reason events for hosting,
collaboration and networking service planes. It is deliberately observational:
it cannot mint capabilities, alter projects, rewrite WorldSaves, change
CreationRevision identity, promote a client to authority, or recover collaboration
history by fabricating semantic transactions. The collaboration and networking
modules continue to own their respective semantic recovery rules.

The immutable cache abstraction similarly models CDN/object-cache placement only.
A cache miss is a delivery failure, not permission to resolve another creation,
package or runtime. Re-populating identical bytes produces the same cache digest.

## Protected source/audio/provenance invariant

Distribution exposes provenance/licence/source information by reading the same
complete `ProtectedAssetRevision` already validated by SMX-024/035/036. The
public disclosure contains the complete protected revision fields together:

- stable AssetId and revision/content digest;
- source digest, source logical identity and exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution;
- derivation lineage.

No hosted release, alias, CDN object, recovery archive, offline install, native
payload or retained runtime may field-mix competing revisions. Target/runtime
placement does not replace the canonical source with a derivative, and provenance
or licence information does not grant execution authority.

## Adversarial and boundary coverage

`spec/production/smx050-distribution-fixtures.json` freezes DST-001..DST-024.
The production tests cover immutable release/runtime binding, alias movement,
cloud/service outage with local offline survival, runtime revocation, exact
recovery round trips, creation/runtime tampering, complete protected-Asset
disclosure, native target rejection, cache eviction and explicit runtime-copy
storage accounting.

The dedicated CI gate additionally retains SMX-036 exact publication, SMX-041
untrusted-content security, SMX-044 collaboration, SMX-047 production topology
and SMX-049 compatibility contracts. This prevents distribution shortcuts from
quietly reintroducing ambient authority or semantic floating.

## Cost and claim boundary

The implementation measures retained runtime storage in explicit bytes and copy
counts. It does not claim Internet-wide CDN latency, availability, request cost,
native installer adoption or hardware coverage from CI-local evidence. Those are
release/operations qualification inputs. Content addressing deduplicates identical
runtime bytes; each intentional independent deployment copy must still be counted.

## Downstream handoff

SMX-051 may build recovery/export/import user workflows on these primitives after
its required human evidence is available; it must not create a second recovery
format. SMX-052 must qualify the supported release matrix and attach real target,
historical-generation, runtime-digest, trust/revocation and hardware/performance
evidence rather than treating this implementation as universal release approval.

## Architecture impact

No Architecture-v1 amendment is required. SMX-050 realizes already-frozen
separation between semantic identity and physical placement, exact immutable
publication, bounded historical runtime retention, no ambient authority,
path-independent identity and the complete protected-media revision contract.
