# SMX-045 network deployment spike

This directory is disposable mechanism-selection evidence for issue #70. It is **not** the production `networking.runtime` implementation and does not define canonical network semantics.

`spike.py` models the selected physical deployment boundary: OAuth authorization-code + PKCE control-plane authentication, short-lived room/audience-bound runtime join tickets, role-distinct principal/session/transport identity, WebRTC DataChannel peer-hosting with ICE/STUN/TURN, WSS peer relay fallback, and WSS dedicated authority. It records small CI-local framing/ticket measurements.

`test_spike.py` is the adversarial/boundary corpus for ticket tamper/replay/expiry, signalling authority injection and bounds, transport fallback/failure mapping, suspension/reconnect identity rebinding, dedicated authority loss, trust separation, and protected-Asset atomicity.

`browser_probe.mjs` runs against pinned Playwright/Chromium in CI. It opens a real WebRTC DataChannel loopback, transmits a semantic envelope, records candidate/state/timing evidence, confirms ICE restart availability, and exercises a relay-only/no-TURN configuration that must yield the typed `network.ice_no_candidate` outcome. It does not claim to reproduce WAN/NAT diversity.

The existing SMX-017 workflow remains the real Godot 4.7.2 Web/Linux topology, browser lifecycle, reconnect, host-loss and dedicated-authority evidence. SMX-045 consumes that evidence rather than cloning the historical relay into production.

Reproduce the cheap spike:

```bash
PYTHONPATH=experiments/smx-045-network-deployment-spike \
python -m unittest discover -s experiments/smx-045-network-deployment-spike -p 'test_*.py' -v

python experiments/smx-045-network-deployment-spike/spike.py
```

The browser probe requires Node 22.19.0, Playwright 1.55.0 and its pinned Chromium runtime:

```bash
npm install --no-save --no-package-lock playwright@1.55.0
npx playwright@1.55.0 install --with-deps chromium
node experiments/smx-045-network-deployment-spike/browser_probe.mjs "$PWD"
```

Evidence under `artifacts/` is mechanism-selection evidence for the named CI environment, not a product SLO or supported-network certification.
