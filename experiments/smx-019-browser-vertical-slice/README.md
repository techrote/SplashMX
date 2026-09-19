# SMX-019 browser vertical-slice harness

Disposable research implementation for issue #19. It is intentionally small and non-production.

Run deterministic boundaries:

```bash
node --test test_model.mjs
```

Run the real browser campaign from repository root after installing the pinned research dependencies:

```bash
npm install --no-save playwright@1.55.0 ws@8.18.3
npx playwright install --with-deps chromium
node experiments/smx-019-browser-vertical-slice/browser_harness.mjs
```

The browser campaign writes `artifacts/smx019-browser-results.json`. The editor/player JavaScript, DOM, browser storage keys, service-worker cache keys and WebSocket connection IDs are trusted/disposable harness mechanisms, not public SplashMX contracts.

The protected media fixture deliberately carries a stable `AssetId` and one complete immutable digest/source/audio-media/provenance/licence/derivation revision. Do not simplify it into only a URL or decoded browser media object.
