# SMX-017 real topology harness

This directory is disposable integration evidence for issue #17. It is **not** the SplashMX public network API or wire protocol.

The harness loads the exact same `creation.json` revision in three modes:

1. exported Linux/headless Godot running locally with no network transport;
2. exported Godot Web instances in Chromium, with one browser runtime acting as peer-room simulation authority through a transport-only relay;
3. the same exported Linux Godot runtime as a dedicated authority with an exported Godot Web client.

`godot/main.gd` is one runtime implementation for all three modes. Topology, role and transient connection data are runtime configuration. The canonical fixture contains no WebSocket/WebRTC/ENet/RPC/peer/NodePath identity.

`relay.mjs` is trusted test infrastructure. It assigns transport connection identity, delays/reorders selected state samples, duplicates an application event, retains confirmed checkpoints for reconnect/late-join/peer migration, refuses dedicated-client promotion, and times out an application heartbeat during the browser-lifecycle test. It is not simulation authority except for selecting the policy-defined current authority after a confirmed peer checkpoint.

`browser_harness.mjs` launches the exported browser runtime in Playwright Chromium and the exported Linux runtime headlessly. It checks canonical digest/identity, accepted-input equivalence, state/event handling, relevance and unloaded delivery, reconnect with a changed transient peer ID, browser suspension, confirmed and unconfirmed peer host loss, stale-epoch rejection, dedicated fail-closed behavior, hostile ingress and protected asset/source/audio/provenance preservation. The workflow writes measured evidence to `artifacts/smx017-integration-results.json`.

`model.py` and `test_model.py` are a deterministic semantic oracle and 28 boundary/adversarial tests. They do not replace the real browser/server campaign.

The CI workflow pins Godot `4.7.2`, `barichello/godot-ci:4.7.2`, Node `22.19.0`, Playwright `1.55.0` and `ws` `8.18.3`. The Docker image is build tooling only; the executed browser and Linux artifacts are ordinary Godot exports from the repository project.
