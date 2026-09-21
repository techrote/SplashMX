# SMX-044 production collaboration conformance and People workflow

**Status:** production Phase-8 gate for issue #69.  
**Authority:** Architecture v1 remains authoritative. This document integrates the SMX-043 production collaboration plane into the production browser editor and does not amend runtime Together/network semantics.

## Production contract

**People is collaboration. Together is runtime networking.** The browser exposes them as separate surfaces and state planes. People may project local collaboration health, transient presence, exact history status and semantic conflicts. It cannot mint runtime authority, peer/session identity, transport identity or canonical SplashMX identity. Together/runtime network state cannot resolve or identify collaboration conflicts.

The browser has no collaboration shadow document. Ordinary authoring still mutates `AuthoringSession` through the SMX-023 semantic/canonical path. The People coordinator records the resulting complete validated revision into the SMX-043 local collaboration store. If collaboration-history persistence fails, the in-memory authored project remains available and is marked unsynced; a remote relay/cache copy is never substituted merely to make synchronization look healthy.

## Relay, outage and backpressure boundary

`PeopleSession` exposes a bounded relay-admission seam over the SMX-043 `RelayAuthenticator`. Relay envelopes are authenticated before consuming queue capacity. Authentication only binds an actor to exact transaction bytes; the production collaboration store independently rechecks history version, locally-known base/causal ancestry and monotonic permission epoch before materialization.

The in-memory relay queue is bounded at 64 verified transactions. Overflow produces typed `people.relay_backpressure` and leaves the local canonical head unchanged. An offline relay produces typed `people.relay_offline`; local editing and local collaboration recovery remain independent. If local collaboration history has an unsynced authored candidate, authenticated remote work stays queued until that local candidate is durably reconciled rather than silently replacing it.

## People browser workflow

The production browser state contains a `people` object with `plane=collaboration`, local-first head/status, permission epoch, bounded relay status, transient presence and unresolved semantic conflicts. It separately contains a `together` object with `plane=runtime-networking`. The DOM mirrors that separation using distinct People and Together sections.

The HTTP shell remains a `ThreadingHTTPServer`, but semantic browser operations are serialized at `BrowserBridge`. The persistent `SQLiteCollaborationStore` is deliberately **not** made cross-thread: `PeopleSession` is constructed, used and closed on one dedicated owner thread, retaining SQLite's default connection thread-affinity while arbitrary HTTP request threads synchronously hand collaboration work across that boundary. This prevents request scheduling from becoming collaboration/canonical ordering authority and makes concurrent state/action requests deterministic at the browser integration seam. Server shutdown explicitly closes the People store on its owner thread before the bridge executor is released.

People conflict inspection shows stable conflict ID, semantic locus/kind and complete alternative project revision identities. Resolution is explicit. `current`, `alternative-a` or `alternative-b` selection publishes a **new causal collaboration transaction**; it never rewrites proposal history. Whole-document invalid conflicts permit only `current` acknowledgement because choosing a structurally invalid whole alternative would violate R-018-03; the author must first make a valid semantic edit.

For stable record loci (`Thing`, `Relationship`, `Connection`, `Definition`, `Instance`, known-unloaded membership and protected `AssetId`) an alternative selection copies that one semantic record into the current coherent project, validates the whole candidate, then resolves transactionally. Unrelated current work is retained.

Presence/cursor/selection is process-local transient state in the collaboration store object. It is never written to SQLite history, canonical authored state, WorldSave, package/publication state or runtime Together declarations.

## CR-001..CR-028 production gate

`spec/production/smx044-collaboration-gate-fixtures.json` maps every CR-001..CR-028 class to its production evidence. The dedicated workflow runs:

- the SMX-043 production collaboration suite for stable-ID merge/conflict, replay/collision, pending ancestry, R-018-01..04, permission/history quarantine, crash/reopen, compaction, protected alternatives, undo, authenticated relay and transient presence;
- the inherited SMX-018 CR-001..028 semantic corpus so no accepted conflict class disappears;
- SMX-044 production People tests for relay outage, authentication, bounded backpressure, local-history failure/retry, permission-epoch quarantine, conflict resolution, compaction/reopen and protected-Asset atomicity;
- a threaded HTTP boundary regression that fans out concurrent state reads and semantic writes while asserting one coherent People/canonical head; and
- a real pinned Chromium People/Together projection check.

For each CR class, delivery/storage perturbations are retained as a matrix: opposite delivery order, duplicate replay, disconnect/reconnect, crash/restart and explicit-frontier compaction. Not every perturbation changes every semantic fixture; the gate requires that production history admission remain deterministic/idempotent, local state survive disconnect/storage failure, crash recovery expose only a coherent head, and compaction preserve required conflict/tombstone/quarantine/protected-alternative meaning.

## Migration and compaction

Collaboration history version is explicit. Unsupported/future history is retained as exact recoverable quarantine and cannot materialize until a deterministic migration exists. The gate does not invent a lossy migration solely to claim compatibility. Current-format reopen is deterministic, and causal-frontier compaction retains receipts plus non-compactable tombstone/conflict/quarantine/protected-alternative payload meaning. Schema compatibility therefore fails closed rather than reinterpreting historical intent.

## Protected source/audio/provenance boundary

A stable `AssetId` still selects one indivisible immutable protected revision containing **revision/content digest, source digest and logical source identity, exact source metadata, audio/media semantic metadata, provenance, licence/attribution and derivation lineage**. Collaboration conflict alternatives retain complete revisions. People resolution copies exactly one complete `ProtectedAssetRevision`; there is no field-wise merge path. Relay metadata, presence, SQLite placement, browser DOM state and runtime Together identities cannot replace or synthesize any part of that canonical bundle.

## Measured evidence

The browser campaign records build SHA, pinned browser/runtime versions, startup time, local-edit/People publication time and basic conflict/presence projection observations. These are named-environment observations, not product SLOs. History/compaction correctness is asserted independently of wall-clock timing.

No Architecture-v1 contradiction was found while implementing this gate, so no post-freeze ADR is required.
