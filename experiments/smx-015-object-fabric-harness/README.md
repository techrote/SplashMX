# SMX-015 disposable Object Fabric harness

This directory is a **non-production falsification harness** for issue SMX-015. It integrates the minimum accepted semantics needed to run the required P0–P4 destructive experiments together:

- P0 universal Thing kernel;
- P1 hot behaviour replacement;
- P2 nested groups/local definitions/instances;
- P3 fresh-runtime semantic snapshot/restore;
- P4 object-centric stream-out/in with exact dependency validation.

The model must not become Architecture v1.0 by inertia. It deliberately omits Godot bindings, a production parser/serializer, network transport, collaboration storage, and security enforcement. Those omissions are part of the evidence boundary documented in `docs/research/SMX-015-OBJECT-FABRIC-HARNESS.md`.

Run:

```text
python -m unittest discover -s experiments/smx-015-object-fabric-harness -p 'test_*.py'
```

The suite includes adversarial rollback, identity, reconciliation, restore, dependency-integrity, streaming, and protected source/audio/provenance boundary tests.
