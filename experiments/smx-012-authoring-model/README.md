# SMX-012 authoring projection model

Disposable falsification model for issue SMX-012. It tests whether one canonical SplashMX semantic model can be projected through progressively disclosed authoring surfaces without importing engine/toolchain vocabulary or splitting beginner and advanced authoring into different object/network models.

It is **not production editor code** and its Python/JSON shapes are non-normative.

Run:

```bash
python -m unittest discover -s experiments/smx-012-authoring-model -p 'test_*.py'
```

The boundary tests cover hierarchy independence, ordinary-group-to-definition promotion, shared beginner/advanced IR targeting, stable ports, timeline optionality, authored/runtime separation, multiplayer/collaboration separation, author-language diagnostics, and atomic preservation of `digest/source/audio/provenance` asset revision metadata.
