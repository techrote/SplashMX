# SMX-011 collaboration-semantics model

This directory contains a **disposable, non-normative** model used to falsify the SMX-011 collaboration candidate. It is not a production CRDT, OT engine, wire protocol, database schema, or editor implementation.

The model starts from one coherent canonical document snapshot and an unordered set of causally annotated semantic transactions. Materialization deliberately holds invariant-sensitive concurrent proposals out of the canonical state until explicit resolution, while independent semantic loci merge automatically. Delete/edit and connection-remove/edit cases use tombstone/remove-wins semantics so stale offline edits cannot resurrect destroyed identity. Component updates that cannot absorb a concurrent local override are held while the local edit survives.

It also keeps transient presence/cursor/selection state outside persisted collaboration state, revalidates permission epochs after offline work, quarantines schema-mismatched operations for migration, preserves `AssetId` plus atomic source/audio/provenance replacement bundles, and rejects runtime-multiplayer keys/operations at the collaboration boundary.

Run from the repository root:

```bash
python -m unittest discover -s experiments/smx-011-collaboration-model -p 'test_*.py'
```

The tests are deterministic and dependency-free. They intentionally exercise conflict outcomes and convergence under operation-order permutations; broader real multi-editor/storage/network/destructive testing belongs to SMX-018.
