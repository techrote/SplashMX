# SplashMX RAG index — Architecture v1.0

**Status:** post-freeze retrieval authority, 2026-09-19.  
**Exact pre-freeze research RAG index:** `docs/03-RAG-INDEX.pre-v1.md`

This file is intentionally compact after SMX-020. The full pre-Architecture-v1 retrieval map is preserved byte-for-byte at the historical path above. Future autonomous work should start from the frozen architecture rather than reconstructing the research campaign unless evidence detail is actually needed.

## Architecture v1.0 post-freeze retrieval rules

For **all** production implementation, architecture maintenance, compatibility, security, editor/player, package, networking, collaboration, publishing, or migration work, retrieve this minimum authority chain first:

1. `AGENTS.md` — autonomous workflow, evidence discipline, security and compatibility rules.
2. `docs/00-PROJECT-CONSTITUTION.md` — product invariants and non-goals.
3. `docs/architecture/ARCHITECTURE-V1.md` — frozen durable semantic architecture.
4. `docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md` — freeze decision, precedence/supersession and change rules.
5. `docs/architecture/ARCHITECTURE-V1-AUDIT.json` — machine-readable H-001–H-018 closure, contradiction audit, corrective findings, protected-media fields, and residual-risk classes.
6. `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md` — dependency-ordered production plan and conformance gates.
7. `docs/implementation/PRODUCTION-PROGRAMME-V1.md` — SMX-021–052 dependency/concurrency execution map for production work; it is subordinate to the roadmap and Architecture v1 and is **not** a live completion ledger. Verify current issue/PR state in GitHub before deciding what is complete or runnable.
8. `docs/implementation/PRODUCTION-CONFORMANCE-V1.md` — Phase-0 production gate/evidence ownership, typed failure/version/benchmark meta-contracts, and durable-identity guardrails.
9. `docs/04-ISSUE-EXECUTION-PROTOCOL.md` — branch/PR/CI/merge/closure workflow.
10. `docs/05-DECISION-AND-EVIDENCE-LOG.md` — compact post-freeze decision/evidence register and pointers to the full historical log.

Retrieve `docs/01-RESEARCH-ROADMAP.md` and `docs/02-ARCHITECTURE-HYPOTHESES.md` when reconstructing programme history or hypothesis disposition; both now contain post-freeze closure plus pointers to their exact pre-v1 versions.

## Pre-freeze research is evidence, not competing authority

The complete pre-v1 RAG map, hypothesis chronology, roadmap, and decision/evidence log are retained beside their active counterparts as `docs/*.pre-v1.md`. Research specifications, fixtures, experiments and syntheses remain under `docs/research/` and `experiments/`.

Historical snapshots preserve their original text verbatim, including unsuffixed repository paths that may now resolve to newer post-freeze documents. They are therefore historical evidence, **not a self-contained frozen path namespace**. When reconstructing pre-v1 context, prefer the explicit `.pre-v1.md` counterparts named by this active index and use commit-era evidence where exact historical dependency resolution matters.

Use those materials when the current task touches a frozen decision and needs the falsification evidence, exact fixture IDs, rejected alternatives, measurements, or residual-risk boundary. Do **not** let provisional early wording override the constitution, Architecture v1, or an accepted post-freeze ADR.

Disposable experiment implementations are not production architecture by inertia. Machine-readable fixtures and adversarial cases are expected to migrate into production conformance testing where their semantics remain applicable.

## Retrieval map by frozen domain

| Domain | Retrieve after the minimum authority chain | Key retained evidence |
|---|---|---|
| Product / authoring | `docs/research/SMX-012-AUTHORING-MODEL.md`, `docs/research/SMX-019-BROWSER-VERTICAL-SLICE.md` | AUTH/UX/UXG/BV fixtures; real Chromium flow; O-028 limits |
| Thing kernel / relationships | `SMX-002-THING-KERNEL.md`, `SMX-015-OBJECT-FABRIC-HARNESS.md` | universal Thing, explicit relationship taxonomy, destructive P0–P4 |
| Composition / definitions / overrides | `SMX-003-COMPOSITION-DEFINITIONS.md`, SMX-015, SMX-018 | group-as-Thing, stable definition loci, overlays, R-018-01 |
| Behaviour / IR / hot swap | `docs/implementation/SMX-026-EXECUTION-IR.md`, `SMX-004-BEHAVIOUR-EXECUTION.md`, `SMX-008-STREAMING-MIGRATION.md`, SMX-015/016 | production common IR/Rule compiler/scheduler/budgets; bounded turns; transactional replacement; hostile amplification |
| Canonical document / identity / migration | `SMX-005-CANONICAL-DOCUMENT.md`, SMX-007/008/015 | path-independent IDs, typed record graph, full-result validation, migrations |
| Production conformance / implementation guardrails | `docs/implementation/PRODUCTION-CONFORMANCE-V1.md`, `spec/production/conformance-registry.json`, `spec/production/*.schema.json`, `src/MODULES.json`, `tests/production/test_smx021.py` | SMX-021 gate/evidence ownership; typed failure/version/benchmark contracts; module ownership; forbidden durable identity classes |
| Canonical physical encoding / local persistence | `SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md`, `SMX-022-PHYSICAL-STORE-FIXTURES.json`, `SMX-022-NATIVE-EVIDENCE.json`, `SMX-022-BROWSER-EVIDENCE.json` | deterministic CBOR profile; stable-ID hash shards; IndexedDB/OPFS browser split; SQLite WAL/FULL native recovery; SMX-024/025 handoff |
| Security / capabilities | `SMX-006-CAPABILITY-SANDBOX.md`, `SMX-016-SECURITY-HARNESS.md` | ADV/AT fixtures, R-016-01..04, O-025 residual physical isolation |
| Lifecycle / restore | `SMX-007-LIFECYCLE-RESTORE.md`, SMX-015 | authored/runtime/save/context split, pending work, fresh-runtime restore |
| Streaming / exact acquisition | `SMX-008-STREAMING-MIGRATION.md`, SMX-013/015 | object-centric logical residency, exact descriptors/locks, rollback |
| Godot / browser / headless boundary | `SMX-009-GODOT-BOUNDARY.md`, SMX-017/019 | Godot 4.7.2 evidence, target-private bindings, real exported topology/browser evidence |
| Runtime multiplayer | `SMX-010-RUNTIME-MULTIPLAYER.md`, `SMX-017-NETWORK-HARNESS.md` | one creation across offline/peer/dedicated, authority epochs, reconnect/host loss |
| Collaboration | `SMX-011-COLLABORATION-SEMANTICS.md`, `SMX-018-COLLABORATION-HARNESS.md` | CH/CR corpus, offline reunion, R-018-01..04, O-026 production substrate limits |
| Components / packages | `SMX-013-COMPONENT-PACKAGES.md`, SMX-016 | local Definition→Package lineage, exact locks, capability attribution, hostile acquisition |
| Publishing / generic player / worlds | `SMX-014-PUBLISHING-RUNTIME.md`, SMX-017/019 | immutable `CreationRevisionId`, prepare-before-activate, exact offline closure, `WorldSave` separation |
| Browser editor/player projection | `SMX-019-BROWSER-VERTICAL-SLICE.md` plus SMX-012/014/017/018 | create→play→save/reload→publish/load, Together/People separation, R-019-01 |
| Architecture contradiction or change | `docs/architecture/ARCHITECTURE-V1-AUDIT.json`, relevant SMX evidence, latest accepted ADRs | correction rule: amend authority + add regression; never hide a contradiction in an adapter |

Paths in the table without a directory prefix refer to files under `docs/research/`.

## Cross-cutting non-negotiable retrieval rules

### Protected source/audio/provenance

Any work touching assets, media, import/decode/transcode, packages, collaboration, persistence, target projection, publishing, caches, networking, migration, or offline copies must retrieve the Architecture-v1 protected-media section and the relevant research fixture. Serialization or persistence work must additionally retrieve the SMX-022 decision/fixtures and retained native/browser evidence so physical publication cannot weaken the complete-revision rule.

A stable `AssetId` selects one complete immutable revision containing **digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**. Competing replacements remain complete alternatives. Target-private derivatives may not replace or field-mix canonical meaning. A database transaction, shard rewrite, OPFS write, cache fill, or migration may publish the whole coherent Asset revision or leave the prior coherent revision intact; it may not expose a field-mixed intermediate state.

### Identity

Any proposed use of hierarchy paths, NodePath, RID, ResourceUID/resource paths, DOM keys, database row IDs, cache keys, URLs, peer/socket/session IDs, or process handles as durable semantic identity must be treated as a likely Architecture-v1 violation and checked against SMX-005/009/010/019 evidence plus the SMX-021 production identity guardrails. Serialization/storage work must also retrieve SMX-022: shard prefixes, byte offsets, SQLite rows/pages, IndexedDB implementation keys, OPFS paths/file handles, store-internal locators and cache placement are physical mechanisms, not mutable SplashMX semantic identity.

### Runtime networking versus collaboration

If a task involves both multiplayer and multi-author editing, retrieve both SMX-017 and SMX-018 plus the Architecture-v1 networking/collaboration section. Runtime replication and document collaboration are intentionally separate consistency systems even if authentication or transport infrastructure is shared.

### Generic publishing

Ordinary publishing is immutable SplashMX data loaded by a separately deployed generic runtime. A per-creation Godot build is an exceptional trusted deployment class, not an ordinary compatibility fallback.

### Offline exactness

Offline playback/runtime uses an exact verified creation/dependency/runtime-compatible closure or reports typed unavailability/incompatibility. It does not silently float to a compatible substitute.

For browser/native persistence, also retrieve SMX-022. Canonical project ownership must remain distinct from disposable cache; browser permission, persistence, quota and eviction are fallible platform conditions that must produce explicit non-destructive outcomes rather than silently changing project meaning.

## Corrective findings that must remain visible

The post-freeze architecture incorporates and production tests should retain:

- R-016-01 through R-016-04 — host-independent path normalization, serialized authority rejection, delegation ancestry bounds, final host-boundary authorization recheck;
- R-018-01 through R-018-04 — DefinitionId-scoped conflicts, delete/new-Connection remove-wins, full semantic validation before commit, incident-Connection tombstoning;
- R-019-01 — semantic `ConnectionId` is distinct from transient transport connection identity.

## Post-freeze production retrieval anchors

### SMX-021 production-conformance retrieval rules

Retrieve `docs/implementation/PRODUCTION-CONFORMANCE-V1.md`, `spec/production/conformance-registry.json`, the production schemas under `spec/production/`, `src/MODULES.json`, `tests/production/test_smx021.py`, and `tools/validate_smx021.py` when work touches gate ownership, typed failures, version metadata, benchmark evidence, module ownership, or durable identity classes. Treat SMX-021 as guardrail infrastructure: it does not by itself activate later production modules or select their implementation mechanisms.

### SMX-022 physical encoding/store retrieval rules

Retrieve `docs/research/SMX-022-CANONICAL-ENCODING-STORE-SPIKE.md`, `SMX-022-PHYSICAL-STORE-FIXTURES.json`, `SMX-022-NATIVE-EVIDENCE.json`, `SMX-022-BROWSER-EVIDENCE.json`, `tools/validate_smx022.py`, and `.github/workflows/smx022-physical-store.yml` for canonical serialization, local persistence, partial access, migration-store interaction, browser storage, crash-recovery work, or evidence reproduction. The selected broad mechanism is deterministic CBOR records/revisions + bounded stable-ID hash shards, IndexedDB-owned browser revision/head publication with OPFS prepare-before-publish backing, and SQLite WAL/`synchronous=FULL` native revision/head publication. SMX-024/025 should implement and falsify within that selected boundary rather than silently re-run broad mechanism selection; contradictory evidence must be recorded explicitly.

### SMX-026 production execution retrieval rules

Retrieve `docs/implementation/SMX-026-EXECUTION-IR.md`, `src/splashmx/execution/ir.py`, `tests/production/test_smx026.py`, `tools/validate_smx026.py`, `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md`, and `docs/research/SMX-016-SECURITY-FIXTURES.json` for behaviour execution, Rule compilation, scheduler ordering, timers/continuations, service-request staging, resource budgets, hot-swap preparation, or runtime lifecycle integration. Preserve one `splashmx.behaviour-ir/1` path for beginner and advanced authoring, atomic activation commit-before-effects, attachment-private state, deterministic logical time/PRNG, independent amplification limits, fail-closed unknown/host opcodes and R-016-02 recursive authority rejection. `request_service` is a mediated request only; SMX-027 still owns grants/delegation/revocation and the final host-boundary authorization recheck. Multi-attachment execution requires explicit semantic attachment order and must never infer author-visible scheduling from map/hash/canonical-byte/lexical UUID order.

## Historical late-campaign retrieval anchors

The following compact anchors intentionally preserve phrases used by already-merged validators. Full pre-freeze retrieval prose is in `docs/03-RAG-INDEX.pre-v1.md`; these anchors do not create new competing contracts.

## SMX-015 Object Fabric destructive-harness retrieval rules

Retrieve `docs/research/SMX-015-OBJECT-FABRIC-HARNESS.md`, `docs/research/SMX-015-OBJECT-FABRIC-FIXTURES.json`, and `docs/research/SMX-015-DECISION-EVIDENCE.md`. Preserve OF-001 through OF-030, OH-001 through OH-020, and the protected source/audio/provenance boundary.

## SMX-016 adversarial-security retrieval rules

Retrieve `docs/research/SMX-016-SECURITY-HARNESS.md`, its fixtures, `SMX-016-DECISION-EVIDENCE.md`, and the SMX-006 capability contract. Preserve ADV-001 through ADV-028, AT-001 through AT-028, R-016-01 through R-016-04, and protected source/audio/provenance semantics.

## SMX-017 real-topology retrieval rules

Retrieve `docs/research/SMX-017-NETWORK-HARNESS.md`, `docs/research/SMX-017-NETWORK-HARNESS-FIXTURES.json`, and `docs/research/SMX-017-DECISION-EVIDENCE.md` for runtime-topology, reconnect, host-migration, browser-lifecycle, or dedicated-authority claims. Preserve the bounded evidence statement: the real campaign proves semantic topology equivalence on the tested Godot 4.7.2 + Chromium environment, not a production network stack, WAN/NAT/signalling design, cross-browser certification, or final transport choice. In the passing lifecycle campaign headless Chromium did **not** naturally drop the transport during the measured freeze path; reconnect was then exercised with the explicitly labelled deterministic relay fault. Do not restate that injected reconnect case as evidence of ordinary browser background-tab disconnection.

## SMX-018 collaboration-harness retrieval rules

Retrieve `docs/research/SMX-018-COLLABORATION-HARNESS.md`, `docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json`, `docs/research/SMX-018-DECISION-EVIDENCE.md`, and the SMX-011 collaboration contract. Preserve CH-001 through CH-028, CR-001 through CR-028, R-018-01 through R-018-04, and source/audio/provenance atomicity.

## SMX-019 browser vertical-slice retrieval rules

Retrieve `docs/research/SMX-019-BROWSER-VERTICAL-SLICE.md`, its fixture/evidence files, SMX-012/014 authoring/publishing contracts, and SMX-017/018 when topology/collaboration behavior is in scope. The research slice retained exactly **34 adversarial/boundary tests** and R-019-01. Treat its JavaScript/browser implementation as non-production reference evidence.

## Research-history retrieval

For archaeology, exact issue-era wording, old source lists, or legacy fixture-family lookup, start with:

- `docs/01-RESEARCH-ROADMAP.pre-v1.md`;
- `docs/02-ARCHITECTURE-HYPOTHESES.pre-v1.md`;
- `docs/03-RAG-INDEX.pre-v1.md`;
- `docs/05-DECISION-AND-EVIDENCE-LOG.pre-v1.md`.

Those files are historical evidence snapshots. Their presence is deliberate; they must not be edited to make later decisions look inevitable.

## Architecture-change rule

If production evidence falsifies a frozen semantic decision, retrieve the relevant historical evidence and current conformance fixtures, open an explicit ADR, state which Architecture-v1 decision is contradicted, reconcile dependent documents/contracts, and add an adversarial regression. Do not solve an architectural contradiction only by special-casing the implementation.
