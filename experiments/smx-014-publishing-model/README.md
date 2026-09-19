# SMX-014 publishing-model falsification harness

This is a **non-production** Python model for SMX-014. It tests publication artefact separation, deterministic immutable creation revisions, generic-runtime compatibility negotiation, exact dependency/blob validation, target projection, offline/hosted identity, save/world separation, and the pre-execution security boundary.

It deliberately does **not** define production package bytes, a hosting service, a registry, a browser cache implementation, cryptography, a Godot scene layout, or a per-platform installer.

Run:

```bash
python -m unittest discover -s experiments/smx-014-publishing-model -p 'test_*.py'
```

The key falsification property is that `Publisher.publish()` contains no Godot export step and `GenericPlayer.prepare()` validates runtime/schema/IR/features, exact dependency and asset bytes, migrations, and capabilities before `activate()` can execute content. Web/native/headless players consume the same `PublishedCreation` semantic revision while selecting different target payloads.
