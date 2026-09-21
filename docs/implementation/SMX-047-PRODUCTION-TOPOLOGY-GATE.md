# SMX-047 — production topology-equivalence and hostile-network gate

**Status:** Phase-9 production gate implementation  
**Issue:** SMX-047 / #72  
**Depends on:** SMX-046 / #71  
**Architecture:** Architecture v1.0; no amendment required  
**Production boundaries:** `src/splashmx/runtime/network.py`, `src/splashmx/runtime/web/network_transport.mjs`  
**Gate fixtures:** `spec/production/smx047-topology-gate-fixtures.json`  
**Conformance:** `tests/production/test_smx047.py`, `tests/production/smx047_browser_harness.mjs`

## Gate question

SMX-047 does not reopen transport selection or rebuild the SMX-017 research harness. It asks whether the frozen topology-independent semantics now survive the **production** SMX-046 runtime and selected browser adapters under the topology and hostile/degraded conditions required by Architecture v1.

The retained SMX-017 canonical fixture at `experiments/smx-017-network-harness/creation.json` is loaded as the same `creation_revision_id` for offline/local, peer-hosted browser and dedicated-authoritative projections. The production gate never writes transport, session, WebRTC, WebSocket, Godot peer or engine identity into that fixture. The current complete protected-Asset contract is separately exercised through the production networking boundary so the historical fixture is not silently rewritten to manufacture newer protected fields.

## Production topology equivalence

`tests/production/test_smx047.py` builds all three topology profiles through `RuntimeNetworkingService`, using the same retained canonical Thing/network declarations and the same authoritative semantic workload.

The semantic comparison excludes only topology-private facts that Architecture v1 already declares non-canonical: physical transport path, transient connection identity and timing. The compared surface includes stable Thing identity, authority epoch, residency, replicated state and the complete protected Asset revision.

The canonical workload demonstrates:

- client input remains declared intent rather than authoritative state;
- the current authority publishes the same state/event semantics in all topologies;
- offline/local, peer-hosted and dedicated-authoritative execution converge on the same normalized semantic state;
- no topology projection mutates the retained canonical creation.

## Hostile and degraded network campaign

The deterministic production-runtime campaign exercises the real SMX-046 ingress and authority code rather than the pre-v1 model:

- dropped earlier state followed by a delayed newer state;
- duplicate and reordered messages;
- stale authority epochs;
- forged/unknown senders;
- recursively authority-bearing payloads;
- oversized messages and per-session rate exhaustion;
- delayed known-unloaded state and reliable events;
- relevance leave versus unload/destruction;
- tombstone remove-wins behavior;
- browser suspension followed by physical disconnect/reconnect;
- confirmed versus unconfirmed peer-host loss;
- dedicated-authority loss without client self-promotion;
- TLS, signalling, ICE, TURN, relay, server and runtime-admission failure mappings.

Every failure remains a typed `network.*` runtime outcome. The project/canonical creation is not rewritten to adapt to transport failure.

## Production browser adapter evidence and corrective repair

The SMX-047 real-browser harness uses **Playwright 1.55.0 pinned Chromium** and Node **22.19.0** against `BrowserRuntimeTransport`.

The gate exercises:

1. a real ordered WebRTC DataChannel;
2. bounded semantic round trips and an ordered burst;
3. ICE restart support;
4. physical disconnect followed by establishment of a new peer transport while semantic session/Thing identity in the envelope remains unchanged;
5. a real TLS WebSocket server for the selected dedicated-authoritative path;
6. runtime join framing and bidirectional semantic delivery;
7. malformed inbound WSS framing, which must make the browser adapter close the connection with application-private close code `4008`.

The first SMX-047 integration pass exposed two acceptance-relevant adapter defects in the SMX-046 implementation. First, `connectDedicatedWss()` could receive authoritative semantic frames, but `sendSemantic()` was hard-wired to the DataChannel and therefore could not send client intent over the selected dedicated WSS path. SMX-047 repairs `sendSemantic()` to use the open DataChannel **or** the open dedicated WSS socket, preserving the same bounded encoding and keeping the physical socket private. A disconnected adapter still returns `network.reconnect_required`.

Second, malformed dedicated WSS input attempted `WebSocket.close(1008, ...)`. Browser script may initiate a close only with code `1000` or an application-private code in `3000..4999`, so Chromium rejected that close request and left the hostile connection live. The production adapter now uses application-private code `4008` for semantic-policy rejection, and the real server waits for and verifies that close handshake.

These repairs change no canonical/network semantics; they make the already-selected physical dedicated adapter genuinely bidirectional and genuinely fail-closed in the browser API actually used in production.

## Identity and authority separation

The gate retains distinct roles for:

- durable `ThingId`;
- authenticated `principal_id`;
- bounded runtime `session_id`;
- transient `transport_id`;
- semantic `authority_epoch`.

Reconnect replaces physical transport while retaining the live principal/session and durable Thing identity. Authority migration is a separate, explicit semantic transaction and increments the epoch. Relevance changes do not infer residency, destruction, control or authority. Dedicated-authority loss never promotes an ordinary client.

Semantic snapshots/checkpoints remain free of transport/socket/Godot peer identity.

## Protected source/audio/provenance boundary

A stable `AssetId` continues to select one complete immutable revision containing:

- revision/content digest;
- source digest and logical source identity;
- exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution;
- derivation lineage.

The same complete revision is asserted across offline, peer and dedicated runtime projections and through confirmed peer-host migration. An incomplete revision is rejected. Packet scheduling, reconnect, ICE/TURN/WSS selection, authority transfer, relevance and browser/server framing have no authority to combine fields from different revisions or reinterpret canonical media meaning.

## Measurements and claim boundary

The browser evidence records the user agent/runtime versions, peer DataChannel establishment, multiple semantic round-trip samples, ordered burst count/payload size, reconnect establishment, dedicated WSS establishment and dedicated semantic round trip.

These are **CI-local mechanism observations**, not product latency/throughput SLOs and not a claim of Internet-wide NAT/firewall/TURN success. Reliable ordered DataChannel retransmission hides physical packet loss from JavaScript, so deterministic loss/reorder/duplicate policy is injected immediately above the physical adapter and exercised against the production `RuntimeNetworkingService`; it is not simulated by weakening WebRTC itself.

## Residual risk

This gate does not claim exhaustive public-Internet NAT populations, TURN operations, all browsers, mobile backgrounding behavior or production regional deployment. Those are target/deployment qualification concerns below the frozen semantic boundary. A future physical adapter may differ if it preserves the same typed failure, authority and identity contracts.

No unresolved topology-specific semantic contradiction was found. No Architecture-v1 ADR/amendment is required.

## Required automated evidence

The dedicated SMX-047 workflow runs:

- retained SMX-017, SMX-041, SMX-045 and SMX-046 validators;
- `tools/validate_smx047.py`;
- the retained SMX-017 semantic oracle;
- SMX-046 production networking regressions;
- SMX-047 production topology/adversarial regressions;
- the real Chromium WebRTC + dedicated-WSS topology harness.

Repository-wide required PR workflows remain independently required before merge. The issue may close only after the PR is merged, exact `main` is verified and the merge-triggered campaign is green.
