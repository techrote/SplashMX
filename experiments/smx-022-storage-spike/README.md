# SMX-022 physical encoding/store spike

Disposable comparative harness for issue #47. Nothing in this directory is production serialization or persistence code.

Native comparison:

```bash
python spike.py --output artifacts/smx022-native-results.json
python -m unittest -v test_spike.py
```

Real browser comparison (after installing the pinned Playwright dependency used by CI):

```bash
npm install --no-save --no-package-lock playwright@1.55.0
npx playwright@1.55.0 install chromium
node browser_harness.mjs
```

The harness deliberately exercises complete protected-media revisions, stable semantic IDs, deterministic bytes, bounded ID-hash shards, partial lookup, interrupted native commits, IndexedDB transaction abort/interruption, OPFS unclosed writes, and browser storage persistence/quota observations.

The Python CBOR codec is deliberately tiny and slow. It exists to falsify byte/profile and chunking choices, not to become the production encoder. The browser harness likewise tests platform semantics rather than selecting a JavaScript persistence library.
