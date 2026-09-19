# SplashMX architecture hypotheses — Architecture v1.0 final closure

**Status:** hypothesis campaign closed by SMX-020 on 2026-09-19.  
**Frozen architecture:** `docs/architecture/ARCHITECTURE-V1.md`  
**Machine-readable closure:** `docs/architecture/ARCHITECTURE-V1-AUDIT.json`  
**Exact pre-freeze hypothesis/evidence chronology:** `docs/02-ARCHITECTURE-HYPOTHESES.pre-v1.md`

The H-001–H-018 register began as deliberately falsifiable propositions. SMX-001 through SMX-019 accumulated model, destructive, hostile, real-topology, collaboration, and browser evidence. SMX-020 reconciled that chronology and freezes the dispositions below.

The historical file remains the evidence trail for every intermediate `strengthened`, `refined`, `weakened`, or `unresolved` status. This post-freeze register is intentionally concise so a future agent cannot mistake an early provisional status for the Architecture-v1 result.

## Architecture v1.0 final closure — 2026-09-19

| Hypothesis | Final status | Architecture-v1 interpretation |
|---|---|---|
| H-001 | **accepted as decision** | One faceted Thing kernel is the canonical base semantic model. |
| H-002 | **accepted as decision** | Hierarchy is structural/local; behaviour, control, authority, persistence and replication remain explicit. |
| H-003 | **accepted as decision** | Groups and leaves share the Thing kernel. |
| H-004 | **accepted with narrowed/refined scope** | Ordinary authored structure can become a local Definition and portable package without changing semantic lineage; physical package/discovery UX is not frozen. |
| H-005 | **accepted with narrowed/refined scope** | Compatible Behaviour replacement is transactional with explicit state/pending-work migration and rollback; arbitrary compatibility is not promised. |
| H-006 | **accepted with narrowed/refined scope** | Built-ins, beginner Rules and advanced authoring share one constrained semantic IR boundary; final textual syntax/compiler/VM encoding is not frozen. |
| H-007 | **accepted as decision** | SplashMX owns canonical durable creation semantics above Godot serialization. |
| H-008 | **accepted as decision** | Durable semantic identity and references are path-independent. |
| H-009 | **accepted with narrowed/refined scope** | Principal-attributed capability semantics are accepted; real process/origin/decoder/crypto isolation still requires production hostile proof. |
| H-010 | **accepted as decision** | Thing meaning survives dormant/unloaded/rehydrated state without an always-resident process object. |
| H-011 | **accepted with narrowed/refined scope** | Logical streaming is object/subgraph-centric while physical chunks/packages/cache batches remain implementation policy. |
| H-012 | **accepted with narrowed/refined scope** | Offline, peer-hosted and dedicated-authoritative execution use one canonical network model primarily through topology/policy changes; transports/deployment remain private runtime concerns. |
| H-013 | **accepted as decision** | Runtime simulation networking and collaborative document editing are separate consistency systems. |
| H-014 | **accepted with narrowed/refined scope** | Godot is replaceable-enough at the durable semantic boundary, not cost-free to replace as the first production substrate. |
| H-015 | **accepted as decision** | Versioned generic runtimes loading immutable SplashMX creation data are the ordinary publication path; per-creation builds are exceptional trusted deployments. |
| H-016 | **accepted with narrowed/refined scope** | One semantic system projects into the simple browser workflow; novice comprehension, accessibility, localization and final terminology remain product evidence gates. |
| H-017 | **accepted with narrowed/refined scope** | Canonical authoring remains useful offline and can reconcile later; production collaboration persistence/compaction/relay remains implementation work. |
| H-018 | **accepted with narrowed/refined scope** | Compatibility is SplashMX schema/IR/required-feature/interface/migration driven rather than implicit Godot-version equality; indefinite lossless migration of every future semantic change is not promised. |

No hypothesis is rejected by the completed campaign and none remains a deferred/unresolved blocker to Architecture v1.0. The narrowed statuses are deliberate: model or integration viability is not overstated as production security, performance, human-usability, storage, distribution, or operational certification.

## Corrections incorporated into the final architecture

Destructive campaigns found boundary defects that are now part of the frozen contract rather than footnotes:

- **R-016-01** — package-path normalization/collision rejection is host-independent and pre-extraction;
- **R-016-02** — serialized authority/raw-host fields are rejected recursively;
- **R-016-03** — capability delegation depth/count and ancestry integrity are checked before allocation;
- **R-016-04** — capability authorization is rechecked immediately before the host adapter is crossed;
- **R-018-01** — definition/instance conflicts are scoped by actual `DefinitionId`;
- **R-018-02** — Thing deletion remove-wins over a concurrent new Connection naming it;
- **R-018-03** — complete resulting document semantics validate before a transaction publishes;
- **R-018-04** — tombstoning a Thing atomically tombstones incident live Connections;
- **R-019-01** — canonical `ConnectionId` is distinct from transient transport connection identity.

## Historical late-campaign regression anchors

These headings and IDs are retained so the already-merged SMX-016/018/019 validators can continue proving that their research-era review records were not lost during the freeze. The detailed text remains in `docs/02-ARCHITECTURE-HYPOTHESES.pre-v1.md`; these anchors do not supersede the final table above.

### SMX-016

## SMX-016 review

H-006 · H-009 · H-011 · H-014 · H-015 · O-025.

### SMX-018

## SMX-018 review record

H-013 · H-017 · H-018 · O-026 · R-018-01 · R-018-04.

### SMX-019

## SMX-019 review record

The browser vertical slice supplied the final pre-freeze H-014/H-015/H-016 projectability evidence while preserving H-013/H-017 separation and R-019-01.

## Evidence retrieval

Use `docs/architecture/ARCHITECTURE-V1-AUDIT.json` for the final machine-addressable evidence mapping and contradiction seams. Use the historical pre-v1 register for the chronological status evolution, then retrieve the named SMX research documents/fixtures for substantive evidence.

A future implementation finding may amend Architecture v1 only through an explicit ADR plus regression evidence. It must not silently revert one of these final decisions to an early hypothesis wording.