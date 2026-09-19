# SMX-010 runtime multiplayer model

This directory is a **non-normative disposable falsification harness** for SMX-010. It is not a production networking stack, wire protocol, prediction engine, authentication service, or Godot multiplayer implementation.

It tests a deliberately small question: can one canonical SplashMX creation retain the same Thing/network declarations while runtime policy switches between offline, peer-hosted, and dedicated-authoritative execution?

The model keeps `ThingId`, authored network declarations, asset/source/audio/provenance records, and semantic state above transient peer IDs, topology and transport. It exercises controller/authority separation, authority epochs, duplicate/stale message rejection, reconnect rebinding, relevance, unloaded delivery, tombstones, peer-host migration, capability mediation, and canonical transport-leak rejection.

Run:

```bash
python -m unittest discover -s experiments/smx-010-multiplayer-model -p 'test_*.py'
python tools/validate_smx010.py
```

`NT-001` through `NT-020` correspond to the machine-readable fixture manifest in `docs/research/SMX-010-RUNTIME-MULTIPLAYER-FIXTURES.json`.

Passing these tests does **not** prove real packet-loss behavior, WebRTC/WebSocket/ENet equivalence, browser suspension recovery, security against a hostile transport implementation, or production performance. Those are explicit SMX-017/019 obligations.
