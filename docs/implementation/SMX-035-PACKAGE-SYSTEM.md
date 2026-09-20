# SMX-035 — production package and portable-component system

Status: implementation authority for issue #60 below Architecture v1.0 and the SMX-034 substrate selection.

## Production contract

SMX-035 makes package metadata a distribution layer around the existing canonical Definition/Thing model. `PackageId` names package lineage, `PackageRevisionId` names one immutable package revision, and a promoted portable component retains the original `DefinitionId` and public `PortId` identities. Package/container/cache/catalog identity never substitutes for canonical semantic identity.

The only authored version requirements accepted by the v1 resolver are exact `=X.Y.Z` and caret `^X.Y.Z`. Resolution is explicit. Runtime, streaming, offline reload and lazy activation consume an immutable `ResolutionLock`; they never consult floating ranges, a mutable catalog, repository location or cache membership to choose another revision.

## Resolver and exact lock

The production resolver is the bounded deterministic PubGrub-family handoff selected by SMX-034: accumulated constraints are propagated, exact candidate incompatibilities are learned on failed transitive closures, and deterministic backtracking searches the bounded catalog snapshot. Limits independently cover dependency depth, package count, catalog rows, solver decisions and aggregate locked bytes.

Required dependencies block resolution. Optional dependencies have a declared fallback and are solved as isolated extensions with the already-coherent required selection pinned, so an optional conflict or failed optional subtree cannot perturb a required revision or leak attempted state. Lazy dependencies are resolved to an exact revision at lock creation but may defer physical acquisition. Lazy demand materializes only that already-locked revision; it does not re-solve.

## SPB1 validation ordering

The selected SPB1 physical container is pathless: fixed framing, one deterministic-CBOR index and tightly packed digest-addressed immutable payloads. It has no extraction paths, links, install scripts or ambient install authority. Parsing bounds total/index/entry sizes and entry count, requires closed index schemas, exact framing, tight non-overlapping layout, no unindexed/trailing bytes, unique artifact/digest bindings and SHA-256 verification.

A package is inert until all of the following finish: exact bundle length/digest acquisition, SPB1 framing/index validation, manifest canonical-CBOR/schema validation, package/revision/version match against the lock, required-feature checks, exact artifact-set validation, and complete protected-asset reconstruction. No migration adapter, Behaviour IR, host service or capability use runs before that boundary.

## Promotion and transactional update

`promote_definition()` preserves local Definition lineage and public stable PortIds. Updates are prepare-before-publish: acquire and validate every non-lazy exact package; preflight capability declarations under each component principal; reconcile Definition lineage/public interface; prepare Behaviour/state migration; then replace the active package state in one publication step. A failed acquisition, parse, capability preflight, interface reconciliation or migration leaves the previous exact lock and live state coherent. Verified immutable cache population may survive because cache membership is explicitly non-semantic.

SMX-035 does not claim a generic arbitrary interface migration mechanism. A changed public interface is rejected unless the caller explicitly authorizes a reconciliation path; later product tooling may provide richer author-facing migration UX without weakening this invariant.

## Capability attribution

Manifest capability entries are declarations only. Live grants, tokens, host/session/process/socket handles, native-extension authority and install scripts are recursively rejected from package metadata. Every request is re-attributed to the exact `PackageRevisionId + DefinitionId` component principal and resolved through SMX-027. Dependency packages therefore do not inherit a parent package's grants. Trust, provenance, licensing, catalog presence and signature status are never capability.

## Protected source/audio/provenance boundary

A stable `AssetId` still selects one indivisible immutable protected revision containing revision/content digest, source digest and logical source identity, exact source metadata, audio/media semantic metadata, provenance, licence/attribution and derivation lineage. Package manifests carry complete `ProtectedAssetRevision` values; decoding reconstructs and revalidates the revision digest across all protected fields. Package solving, SPB1 layout, repository location, cache placement, component update or target-private decoding/transcoding may not combine fields from competing Asset revisions or replace canonical source meaning.

Package-level source metadata, provenance, licence/attribution, remix policy and derivation lineage are preserved as metadata and remain separate from execution trust/capability.

## Typed failure model

Production failures use stable `package.*` codes for invalid identities/versions/requirements, version conflicts and resource exhaustion, malformed/oversized/corrupt bundles, lock/manifest/artifact mismatch, unavailable exact offline bytes, unsupported features, serialized authority, denied capability requests, lineage/interface conflict and failed migration preparation. Unsupported or corrupt input fails closed rather than being silently reinterpreted.

## Acceptance mapping

1. **No runtime floating:** `ResolutionLock`, exact SMX-030 acquisition and lazy-demand tests prove that an unavailable locked revision is an error even if another compatible version exists elsewhere.
2. **Rollback:** package state is published only after full validation, capability/interface reconciliation and migration preparation; adversarial migration failure retains the previous lock/state.
3. **Semantic lineage:** Definition promotion retains `DefinitionId` and exposed `PortId` values and records a digest of the public interface.
4. **Hostile acquisition ordering:** malformed/corrupt package tests assert the migration callback is never entered before validation succeeds.
5. **No grant inheritance:** principals are derived independently from exact package revision plus Definition identity; a grant for a parent principal does not satisfy a dependent component principal.

## Verification

The dedicated `SMX-035 production package system` workflow retains SMX-013, SMX-016, SMX-024, SMX-027, SMX-028, SMX-030 and SMX-034 contracts, then runs the SMX-035 validator and production adversarial suite. The fixtures are `spec/production/smx035-package-fixtures.json`.

## Explicitly out of scope

Marketplace/discovery UX, generic Publish/player work (SMX-036), production cryptographic signature/trust infrastructure and physical decoder isolation (Phase 7) are not implemented here. SMX-035 does not weaken or pre-empt those owners.
