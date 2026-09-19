# SMX-018 collaboration harness

Disposable destructive prototype for issue #18. This directory executes the SMX-011 semantic transaction/conflict contract across multiple offline-capable replicas and a serialized, content-checked relay. It is intentionally **not** a production CRDT, OT engine, database, cloud service, or browser persistence layer.

Run from the repository root:

```bash
python -m unittest discover -s experiments/smx-018-collaboration-harness -p 'test_*.py'
python experiments/smx-018-collaboration-harness/measure.py
```

`test_harness.py` contains 39 deterministic tests. CR-001–CR-028 correspond to `docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json`; additional tests attack tombstones, causal cycles, transaction atomicity, replay/permutation, redo, protected media and a 256-edit offline batch.

The harness treats convergence and canonical validity as separate obligations. Transactions are staged and the complete resulting SplashMX document is validated before commit. Presence is never serialized. Runtime-multiplayer/session/capability fields are rejected. Asset replacement requires a complete indivisible digest/source/audio/provenance/licence/derivation revision for the stable `AssetId`.

The run found R-018-01 through R-018-04: DefinitionId-scoped definition/instance conflict detection; Thing-delete versus new connection endpoint remove-wins handling; whole-document validation before transaction publication; and atomic tombstoning of incident connections when a Thing is tombstoned. See `docs/research/SMX-018-COLLABORATION-HARNESS.md` for the authoritative synthesis and limitations. Production synchronization, persistence, compaction and conflict UX remain explicitly tracked by O-026 rather than being inferred from this model.
