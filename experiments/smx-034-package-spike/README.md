# SMX-034 package-substrate spike

This directory is falsification evidence for issue #59. It is **not** the production package implementation; SMX-035 owns that work.

The spike pins observable selection semantics for the exact/caret v1 requirement surface, one-revision-per-`PackageId` bounded resolution, the pathless `SPB1` framing model, serialized-authority rejection, and complete protected Asset revisions. The reference resolver intentionally uses bounded deterministic DFS so the test corpus does not make a particular implementation library authoritative by inertia. The production handoff selects a bounded deterministic PubGrub-family resolver.

Run from repository root:

```bash
PYTHONPATH=src:experiments/smx-034-package-spike python -m unittest discover -s experiments/smx-034-package-spike -p 'test_*.py' -v
python tools/validate_smx034.py
```

The package bundle spike imports the production SMX-024 deterministic-CBOR encoder/decoder. That is intentional: hostile index input must exercise the already-selected canonical parser boundary rather than a fresh convenience codec.
