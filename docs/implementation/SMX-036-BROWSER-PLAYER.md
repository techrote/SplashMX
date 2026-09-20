# SMX-036 — Generic browser player evidence

**Status:** production implementation  
**Issue:** SMX-036 / #61  
**Parent contract:** `docs/implementation/SMX-036-GENERIC-PUBLISHING.md`

SMX-036 includes a real browser-facing generic-player shell, not a JavaScript shadow of canonical SplashMX semantics. `src/splashmx/publishing/browser_server.py` is a thin presentation/HTTP adapter over the production `HostedReleaseStore` and `GenericPlayer` path. The browser does not parse canonical projects, solve packages, interpret protected media, or decide capability policy itself.

## Prepare-before-activate browser path

The browser requests a locator with an explicit identity role: friendly alias, immutable `HostedReleaseId`, or exact `CreationRevisionId`. The server resolves that role and delegates to `GenericPlayer.load_hosted()`. The semantic sequence remains:

1. resolve the hosted locator to one immutable `CreationRevisionId`;
2. bounded-parse the publication envelope;
3. verify the complete exact digest/length closure;
4. reconstruct and validate the canonical project;
5. parse the exact `ResolutionLock` and bind every package descriptor to it;
6. validate all package bytes/dependency edges, including lazy offline content;
7. reject protected-Asset conflicts and unsupported required features;
8. run the production package/capability preparation path;
9. only then invoke the activation callback and publish browser-visible active state.

A failed preparation therefore cannot replace the previously active creation. The adapter has no fallback that converts hostile or unsupported content into generated host code.

## Real Chromium gate

`tests/production/smx036_browser_harness.mjs` launches pinned real Chromium through Playwright against the production browser adapter. It loads a valid immutable creation through a friendly alias, records the exact `CreationRevisionId`, then attempts a second creation carrying an unsupported required feature. The hostile/incompatible load must fail with `publication.unsupported_feature`, while both browser-visible and server-side active state remain bound to the first immutable revision.

The fixture server shutdown and browser readiness paths are deliberately non-racy: termination does not call `HTTPServer.shutdown()` from its own `serve_forever()` thread, and the browser waits for the actual immutable-revision readiness condition rather than merely for the already-present status node.

## Identity and offline semantics

Friendly aliases remain mutable lookup conveniences and never become canonical identity. `HostedReleaseId` and `CreationRevisionId` remain immutable roles. Offline installation and loading use the same `PublishedCreation` and `GenericPlayer.prepare()` path keyed by exact `CreationRevisionId`; there is no catalog re-solve or compatibility-range floating during load.

`WorldSaveId` remains a separate persistent-world identity. The publication layer only records and validates an explicit WorldSave-to-creation/project basis; it does not conflate a save, creation revision, hosted release, alias, URL, browser session, cache key, or transport handle.

## Protected source/audio/provenance boundary

The browser shell does not receive authority to rewrite protected canonical media. A stable `AssetId` continues to select one indivisible immutable revision containing source digest and identity, exact source metadata, audio/media semantic metadata, provenance, licence/attribution, and derivation lineage. Target-private decoding/transcoding/cache material may reference that revision but cannot field-mix competing revisions or replace canonical meaning.

## Scope boundary

This is the generic **web player handoff** required by Phase 5. It deliberately does not implement Godot realization, rendering/audio/input/physics adapters, or web/native/headless engine profiles; those remain SMX-038 responsibilities. It likewise does not absorb later physical trust/isolation or distribution-operations work.
