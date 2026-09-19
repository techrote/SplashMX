# SMX-009 disposable Godot-boundary model

This dependency-free Python model falsifies one narrow claim: SplashMX semantic identity, package/runtime state, source/audio/provenance metadata, and network declarations can remain independent of replaceable Godot/platform bindings while the same canonical creation is projected to web, native, or headless target profiles.

It is **non-normative research code**. `EphemeralBinding` strings are deliberately fake stand-ins for Godot Nodes/RIDs/resources; the target profiles are deliberately coarse. No Python class, JSON encoding, target-feature string, mapping layout, or benchmark number is a proposed production API.

The model exercises `GB-001`–`GB-012` from `docs/research/SMX-009-GODOT-BOUNDARY-FIXTURES.json`, including hostile canonical Godot identity leakage, forbidden host escapes, digest corruption, browser low-level-network assumptions, headless projection, transport changes, and preservation of audio/source/provenance metadata.

Run:

```bash
python -m unittest discover -s experiments/smx-009-godot-boundary-model -p 'test_*.py'
python experiments/smx-009-godot-boundary-model/benchmark.py
```

The benchmark only measures a Python `ThingId -> ephemeral binding` bookkeeping workload. It is useful for detecting accidental super-linear mapping logic; it is **not** evidence for Godot Node creation cost, rendering cost, physics cost, or frame-time budgets. Real Godot/browser integration and frame-cost measurement remain implementation/harness work.
