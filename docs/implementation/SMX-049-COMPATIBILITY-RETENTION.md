# SMX-049 — Historical compatibility and runtime-retention programme

**Status:** Phase-10 decision spike  
**Issue:** SMX-049 / #74  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md` §§5, 6, 9, 10  
**Depends on:** SMX-024 / #49 and SMX-036 / #61

SMX-049 defines the compatibility programme that SMX-050 distribution and
SMX-052 release qualification must implement and measure. It does not create a
new canonical format, package format, WorldSave format, or player. The selected
policy is **explicit-generation support with bounded migration and exact retained
runtime fallback**, rather than age-based "last N versions" compatibility or
silent reinterpretation by whatever runtime happens to be current.

## Decision

A historical artifact is supported only when all of the following are true:

1. its artifact class and semantic generation have an explicit programme rule;
2. that rule has an executable historical fixture;
3. all required semantics are understood by the selected migration/runtime path;
4. current integrity/trust/revocation policy still admits the bytes and runtime;
5. the complete result passes the same semantic/protected-asset validation that
   current content must pass.

The allowed outcomes are deliberately small:

- **direct** — the current semantic implementation natively understands the
  generation;
- **migrate** — a bounded, capability-free chain prepares a complete candidate,
  validates the complete result, and only then publishes a new immutable
  revision/state;
- **retained-runtime** — an immutable historical CreationRevision executes under
  the exact retained SplashMX runtime profile that understands it;
- **typed failure** — unsupported generation/required semantics, unavailable
  retained runtime, revocation, integrity failure, or incompatible WorldSave
  basis is reported explicitly. There is no best-effort reinterpretation.

Compatibility is defined by SplashMX schema/IR/feature/package/runtime identities,
not by equality of a Godot version. Godot remains a private substrate detail.

## Current supported generations

This is the baseline before a public installed base exists. It is intentionally
small and evidence-backed.

| Artifact class | Generation | Current action | Evidence |
|---|---|---|---|
| Canonical project | `splashmx.project-revision/schema-0` | bounded migrate to schema 1 | Real SMX-024 `0 -> 1` migration registry and SMX-049 historical fixture |
| Canonical project | `splashmx.project-revision/schema-1` | direct | Current SMX-024 production serializer |
| Package/component | `splashmx.package-manifest/1` + `splashmx.package-resolution-lock/1` | direct | Current SMX-035 exact package/lock boundary |
| CreationRevision | `splashmx.creation/1` | direct under `splashmx.generic-player/1` | Current SMX-036 immutable publication/generic player |
| WorldSave | `splashmx.world-save/1` | direct with explicit compatible creation/project basis | Current SMX-029 lifecycle/WorldSave boundary |

There is no invented pre-v1 package, CreationRevision, or WorldSave production
format. Research prototypes remain evidence, not a public compatibility promise.
Unknown older/future generations are typed unsupported until a later release PR
adds an explicit rule and fixture.

## Migration-retention rule

The project does **not** adopt an automatic "support the previous two" or
calendar-based window. Such a rule can discard a still-referenced immutable
creation merely because time passed. Instead, support is reference- and
evidence-based:

- adjacent migration steps remain available while a supported generation depends
  on them;
- a migration chain is bounded by the existing production limit (currently eight
  steps maximum) and may be shortened only by adding a tested direct/compacted
  migration;
- compaction creates and validates a **new** immutable revision; it never changes
  the bytes or identity of an existing `ProjectRevisionId`, `PackageRevisionId`,
  `CreationRevisionId`, or WorldSave revision in place;
- original immutable bytes remain available for audit/recovery for as long as the
  associated supported release/history-retention policy requires them;
- migration failure leaves the previous coherent revision/state untouched;
- if semantics cannot be preserved, the correct result is typed unsupported or
  export through the last compatible runtime, not fabricated migration success.

The executable `simulate_creation_v2_transition()` fixture demonstrates the
required rule for a future semantic break: before hypothetical `creation/2`
becomes current, `creation/1` moves to an exact `generic-player/1` retained-runtime
path unless a separately proven migration exists. The `creation/2` names are a
simulation only; this issue does not introduce those formats.

## Hosted runtime retention

SMX-050 must make hosted historical playback an exact two-part binding:

`immutable CreationRevisionId -> exact supported RuntimeProfileId/runtime digest`

A friendly URL/alias may move, but an immutable historical release cannot float
from one CreationRevision or runtime profile to another. Runtime artifacts are
content-addressed and retained by digest. A retained runtime is a generic
SplashMX runtime artifact, not a per-creation Godot build.

Runtime-profile identity is SplashMX-owned. The implementation may record Godot,
browser, OS, toolchain, sandbox and decoder versions as attestation/operational
metadata, but those values do not become the creation's compatibility identity.
A runtime may be rebuilt only when the new artifact is separately qualified as
compatible with the retained profile contract; the new bytes get a new runtime
artifact digest.

## Exact offline retention

Exact offline historical launch obeys the same semantic rule as hosted launch:

`exact CreationRevisionId + exact supported RuntimeProfileId + exact creation/package closure`

The local installer/library must never resolve a historical creation against a
new package catalog or silently run it with an arbitrary newer generic player.
SMX-050 may package the runtime bytes with an offline distribution or maintain a
content-addressed installed runtime store; either physical choice must make the
exact profile/digest requirement verifiable without network access.

If the required retained runtime or exact content closure is missing, launch
fails with a typed compatibility/offline-unavailable outcome. Network access is
not permission to float to a newer creation/package/runtime.

## Package/component history

Package history is immutable and exact at playback: a CreationRevision already
binds exact `PackageRevisionId` values and package bytes. Package SemVer/ranges
are authoring/update inputs, not historical playback compatibility.

For future package-manifest generations:

- the container/manifest generation must have an explicit support rule;
- exact old revision bytes are retained while referenced by supported creations;
- migrations/reconciliation produce a new package/project/creation revision and
  cannot mutate an existing locked historical closure;
- missing, revoked or semantically unsupported dependencies cause typed failure;
- source/remix/licence/provenance metadata never grants execution authority.

## WorldSave history

WorldSave is persistent runtime state, not a CreationRevision. Compatibility is
therefore a two-dimensional check: the WorldSave schema generation must be
supported **and** its explicit creation/project basis must be compatible with the
selected runtime/migration path.

A WorldSave is never attached to "whatever release an alias points at today".
If a future creation migration also migrates persistent runtime state, the
WorldSave migration is staged separately and publishes a new WorldSave revision
only after the whole result validates. Unknown state semantics fail typed; old
transport/session/capability/engine handles are not revived.

## Security, trust, and revocation precedence

Historical compatibility is not a security exemption. Current trust policy is
applied before historical activation and can make previously playable bytes or a
retained runtime ineligible. Revocation therefore wins over compatibility.

In particular:

- a retained runtime does not restore revoked signing trust or bypass package
  integrity checks;
- capability grants/leases/tokens are current authority state and are never
  resurrected as historical artifact state;
- migrations remain capability-free under the existing Architecture-v1 rule;
- current parser/container resource bounds apply before a migration/runtime is
  selected where the current boundary can inspect the artifact safely;
- a security-fixed retained runtime may replace vulnerable runtime bytes only
  after it is requalified against the same historical profile contract; otherwise
  the historical generation remains blocked until a safe compatible runtime
  exists;
- an unfixable historical runtime/profile is explicitly revoked rather than kept
  executable solely for compatibility statistics.

This gives security fixes and revocation a defined coexistence rule without
allowing old content to acquire stale ambient authority.

## Protected source/audio/provenance invariant

Compatibility paths do not create a weaker media contract. A stable `AssetId`
still selects one indivisible immutable revision containing all of:

- revision/content digest and source digest;
- source logical identity and exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution;
- derivation lineage.

A migration, retained runtime, historical package, hosted release, offline
installer, cache or target-private derivative may reference that complete
revision. None may field-mix competing revisions, replace canonical source
meaning with a derivative, or infer execution trust/capability from provenance
or licence data. SMX-049 directly re-runs the production protected-asset digest
regression for this reason.

## Storage and operational cost model

Runtime retention has a real but bounded cost. The programme measures it in
explicit terms rather than treating "keep old runtimes" as free:

`retained runtime bytes = sum(unique runtime profile+digest size * explicit deployment copies)`

Content-addressing deduplicates repeated references to the same runtime artifact;
regional/availability copies are counted explicitly. SMX-050 must extend the
model with actual browser/native/headless runtime sizes, CDN/object-store copies,
request volume, cache hit rate and operational/security maintenance cost.

The major non-byte cost is operational: each retained runtime profile requires
security patch evaluation, signing/attestation, target smoke coverage and an
explicit eligibility/revocation state. This is why the programme is
reference-based rather than promising indefinite execution of every historical
binary.

Migration retention also consumes test/maintenance budget. A migration step may
be compacted only after equivalence/protected-asset tests cover the resulting
direct path. Historical fixtures remain even when implementation steps are
compacted so semantic support cannot silently disappear.

## Alternatives rejected

**Always run old content on the newest runtime.** Rejected because an unknown
semantic break can silently reinterpret immutable creations and defeat exact
offline reproducibility.

**Keep every historical runtime forever regardless of security.** Rejected
because a known-vulnerable runtime would become a permanent ambient-authority
escape hatch. Retention is subordinate to current trust/revocation policy.

**Always migrate every artifact on access.** Rejected because immutable
CreationRevision identity/bytes must not be rewritten and not every semantic
change is losslessly migratable.

**Pin compatibility to Godot version.** Rejected by Architecture v1: Godot is a
replaceable private substrate and engine-version equality neither proves nor
disproves SplashMX semantic compatibility.

**Calendar/last-N generation support without reference evidence.** Rejected
because it can retire still-addressable historical releases unpredictably and
provides no executable proof that the retained window is semantically safe.

## Executable evidence

`spec/production/smx049-compatibility-fixtures.json` freezes CMP-001..CMP-020.
`experiments/smx-049-compatibility/model.py` makes direct/migrate/retained-runtime
selection, revocation precedence and retained-runtime storage accounting
executable. `tests/production/test_smx049.py` additionally exercises the real
SMX-024 schema-0 migration and future-version rejection, the current production
format/profile constants, protected-Asset atomicity, bounded migration policy,
missing retained runtimes and security revocation.

The dedicated SMX-049 workflow also reruns the production canonical,
WorldSave/package and generic-publishing suites so the programme cannot be made
green by drifting away from the actual boundaries it claims to preserve.

## Handoff to SMX-050 and SMX-052

SMX-050 must implement the physical retention/distribution machinery behind this
policy: content-addressed runtime artifacts, exact hosted release→runtime
binding, exact offline runtime closure/install behavior, historical artifact
availability, revocation/eligibility state, and measured operational/storage
costs. It must not weaken exact publication or protected media to make hosting
simpler.

SMX-052 release qualification must publish a supported-generation matrix with
at least the artifact generation, migration/runtime action, target eligibility,
runtime artifact digest, trust/revocation state and historical fixture result.
No generation is advertised as supported merely because one ad-hoc old file
happened to open.

## Architecture impact

No Architecture-v1 amendment is required. This programme instantiates the
already-frozen §5.5 rule: older content may be migrated, interpreted by retained
compatible runtimes, or rejected with a typed outcome. It preserves exact
publication, no ambient authority, path-independent semantic identity and the
complete protected-media revision contract.
