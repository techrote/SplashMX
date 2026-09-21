# SMX-045 — production network deployment, authentication and signalling selection

**Status:** selected production handoff for SMX-046; bounded Phase-9 mechanism spike, not the production networking module  
**Issue:** SMX-045 / #70  
**Date:** 2026-09-21  
**Authority:** Architecture v1.0 + SMX-010 + SMX-017 + SMX-038/041  
**Executable evidence:** `experiments/smx-045-network-deployment-spike/`, `SMX-045-NETWORK-DEPLOYMENT-FIXTURES.json`, and the dedicated SMX-045 CI evidence artifacts

## Contents

| Section | Summary |
|---|---|
| 1. Result | Selects browser peer-hosting, dedicated-authority, authentication and fallback mechanisms. |
| 2. Frozen semantics | Restates identity, authority, hostile-ingress and protected-Asset boundaries. |
| 3. Candidate comparison | Records why WebRTC + WSS is selected and why ENet/WebTransport are not the v1 baseline. |
| 4. Authentication and session establishment | Defines control-plane login and short-lived runtime join binding. |
| 5. Signalling, NAT, TLS and failure mapping | Defines WSS signalling, ICE/STUN/TURN and typed outcomes. |
| 6. Suspension, reconnect and trust | Defines lifecycle rebinding and peer-vs-dedicated trust. |
| 7. Evidence and limitations | Records executable/browser evidence and rejects product-SLO overclaiming. |
| 8. SMX-046 handoff | Freezes the implementation contract for production networking. |

## 1. Result

SMX-045 selects a **split deployment substrate below SplashMX network semantics**:

- **Peer-hosted browser primary:** WebRTC DataChannel between participants. Session establishment/signalling uses authenticated WSS. ICE performs path selection, STUN discovers usable public mappings, and TURN is the production NAT/firewall relay path when direct connectivity cannot be established.
- **Peer-hosted browser fallback:** if the WebRTC path cannot be established after bounded ICE/TURN attempts, the runtime may use an authenticated **WSS routing relay**. The browser host remains simulation authority; the relay never becomes Thing, principal, persistence or simulation authority merely because it routes bytes.
- **Dedicated-authoritative baseline:** browser/native clients use **WSS** to the operated dedicated authority. This is the v1 baseline because Godot exposes WebSocket on both web and native targets without making the native WebRTC plugin a mandatory dependency. It is not a claim that TCP head-of-line behavior is optimal for every future workload.
- **Authentication/control plane:** user authentication uses standards-based OAuth 2.0 authorization-code flows with **PKCE**. Native public clients use the external system user-agent pattern. Successful control-plane authentication is exchanged for a **short-lived room/audience-bound runtime join ticket**; access tokens are not forwarded peer-to-peer.
- **Identity split:** durable/authenticated `principal_id`, runtime `session_id`, and transient `transport_id` are separate roles. Offers, answers, ICE candidates, sockets, Godot peer IDs, TLS state and relay connection IDs remain transient adapter context.
- **Security/failure rule:** TLS, signalling, ICE/TURN, suspension, reconnect and authority loss produce typed runtime outcomes. None rewrites the canonical creation or mints a SplashMX capability.

This is a mechanism selection below Architecture v1. It does not amend NET-001..020, R-016-01..04, R-018-01..04 or R-019-01.

## 2. Frozen semantics inherited

SMX-010 and Architecture v1 remain authoritative:

- one canonical creation/network declaration supports offline/local, peer-hosted browser and dedicated-authoritative execution;
- client input is intent, not authoritative state;
- simulation authority, input control, containment, relevance, persistence ownership and observation remain independent;
- reconnect may bind a new transport identity without replacing the authenticated principal, Thing identity or canonical creation;
- current authority uses explicit epochs; stale prior-authority traffic remains rejectable;
- runtime networking is separate from collaboration;
- raw sockets/WebRTC/WebSocket objects are not ordinary content authority;
- network ingress is hostile and independently bounded;
- a dedicated authority disappearing does not promote an ordinary client;
- a peer host may be current simulation authority while still being untrusted from another participant's fairness perspective.

### Protected source/audio/provenance invariant

A stable `AssetId` continues to select one indivisible immutable protected revision containing:

1. revision/content digest;
2. source digest and logical source identity;
3. exact source metadata;
4. audio/media semantic metadata;
5. provenance;
6. licence/attribution;
7. derivation lineage.

Topology, signalling, WebRTC negotiation, WSS routing, reconnect, authority migration and target-private decoding/caching may carry references to that revision but **may not combine fields from competing Asset revisions** or replace canonical meaning with a transport/cache derivative.

## 3. Candidate comparison

| Candidate | Browser | Native/headless | Peer-hosted | Dedicated-authoritative | Decision |
|---|---|---|---|---|---|
| WebRTC DataChannel | Built into the browser platform and Godot web export | Godot native requires the separately installed WebRTC GDExtension/plugin | Strong fit: direct/ICE-selected path with STUN/TURN relay | Possible, but would make native plugin deployment part of the baseline | **Selected peer primary; optional future dedicated/native adapter.** |
| WebSocket/WSS | Built-in client path; browser cannot act as raw listening WebSocket server | Built-in client/server support | Cannot directly make the browser a listener, but works as signalling and routing relay | Strong baseline for browser/native clients to an operated server | **Selected signalling, peer fallback and dedicated baseline.** |
| ENet/UDP | Browser low-level sockets unavailable | Built-in native/headless | Does not satisfy browser peer profile | Credible native-only optional adapter | **Rejected as v1 cross-target baseline.** |
| WebTransport/custom QUIC | Browser platform exists but support/deployment profile differs by target | No selected Godot 4.7 production path in the current programme | Additional stack and signalling work | Potential future low-latency adapter | **Deferred pending a concrete workload/target requirement.** |
| Raw TCP/UDP/custom socket | Browser unavailable | Native possible | Fails browser target and violates ordinary-content raw-network boundary if surfaced | Private adapter only | **Rejected as public/cross-target mechanism.** |

The selection intentionally does **not** claim one physical transport fits every future workload. SplashMX delivery classes remain above transport. WSS is a compatibility-focused dedicated baseline; a later adapter may be added if measured workload requirements justify it without changing canonical declarations.

Current upstream basis rechecked for this spike:

- Godot 4.7 high-level multiplayer exposes WebRTC, WebSocket and ENet implementations beneath `MultiplayerPeer`.
- Godot WebRTC is available automatically to Web exports but requires an external native WebRTC GDExtension/plugin on non-Web targets.
- Godot WebSocket is available on web and native targets.
- WebRTC requires a separate signalling path; ICE can use STUN/TURN and supports ICE restart after network change.
- Browser background/suspension can pause a Godot Web export long enough to break a network session; SMX-017 already observed and preserved this lifecycle uncertainty instead of assuming suspension always disconnects.
- RFC 9700 requires/strongly establishes PKCE for modern OAuth authorization-code clients, and RFC 8252 requires native applications to perform authorization through an external user-agent rather than an embedded credential surface.

Primary anchors:
- https://docs.godotengine.org/en/4.7/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html
- https://docs.godotengine.org/en/4.7/tutorials/networking/websocket.html
- https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Connectivity
- https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/restartIce
- https://www.rfc-editor.org/rfc/rfc9700
- https://www.rfc-editor.org/rfc/rfc8252

## 4. Authentication and session establishment

Authentication is a **control-plane service**, not a transport-peer convention and not a capability issuer.

The selected flow is:

1. browser/native client authenticates through an authorization-code + PKCE flow; a native client uses an external user-agent;
2. the trusted session service maps the authenticated account subject to SplashMX `principal_id` policy;
3. joining a room creates or resumes a runtime `session_id`;
4. the control plane issues a short-lived, bounded, audience/room-scoped runtime join ticket;
5. the signalling or dedicated service redeems that ticket and binds the authenticated `principal_id + session_id` to a new transient `transport_id`;
6. a reconnect may create a new `transport_id` while preserving the live principal/session binding;
7. expired/replayed/tampered/wrong-room tickets fail before transport admission.

The disposable spike uses HMAC only to exercise ticket scoping, expiry, tamper and replay semantics. **It is not a production key-management decision.** SMX-046 may implement opaque server-side tickets or a separately signed assertion as long as the same properties hold. Package-signing/TUF keys from SMX-039/040 must not be reused implicitly as runtime identity roots.

A runtime join ticket authenticates admission to a room/service. It does **not** grant filesystem, Godot, JavaScript, media-decoder, network-destination or any other SplashMX capability.

## 5. Signalling, NAT, TLS and failure mapping

### Peer-hosted browser

The control plane is an authenticated `wss://` signalling endpoint over ordinary service TLS. Signalling envelopes are bounded and carry only session-scoped negotiation material such as offer/answer/ICE candidate plus transient transport identity. They may not import `ThingId`, canonical identity, capability grants, host handles or Godot peer identity.

Production ICE policy for peer-hosted browser:

1. gather normal candidates and attempt a direct path;
2. use STUN as part of ICE public-address/path discovery;
3. provide short-lived TURN credentials and permit TURN relay when direct connectivity fails;
4. support TURN over deployment-appropriate UDP/TCP/TLS endpoints so restrictive networks do not silently become a semantic split;
5. if WebRTC still cannot establish, permit the explicitly selected authenticated WSS routing fallback;
6. if no selected path exists, fail with a typed network outcome instead of rewriting topology.

### Dedicated-authoritative

Clients establish authenticated `wss://` to the dedicated authority/service front door. TLS endpoint identity and runtime service authentication are deployment trust; neither becomes `ThingId` or creation identity. Dedicated server loss produces a server/authority failure; an ordinary client does not switch itself into authority.

### Typed outcomes

The production boundary must preserve at least these stable categories (presentation text may differ):

- `network.auth_required`
- `network.auth_expired`
- `network.auth_rejected`
- `network.tls_failed`
- `network.signalling_unavailable`
- `network.signalling_oversize`
- `network.ice_no_candidate`
- `network.turn_unavailable`
- `network.transport_unavailable`
- `network.transport_fallback`
- `network.suspended`
- `network.reconnect_required`
- `network.reconnect_failed`
- `network.server_unavailable`
- `network.authority_lost`

Adapter-specific browser/Godot/socket error strings remain diagnostics below these outcomes.

## 6. Suspension, reconnect and trust

### Browser lifecycle

The accepted SMX-017 Godot 4.7.2 + Playwright 1.55.0 real-runtime campaign already proves the semantic rule: lifecycle observation is recorded separately from transport-loss injection; a resume/reconnect changes transient connection identity while preserving the authenticated principal when the session is still valid.

SMX-045 adds a real Chromium WebRTC DataChannel loopback probe. CI records the exact Chromium user-agent/version at execution, confirms a DataChannel can establish and carry a semantic envelope, confirms `restartIce()` exists, and verifies that a relay-only configuration with no TURN service produces no relay candidate and maps to `network.ice_no_candidate`.

Production reconnect policy:

- on resume/network change, inspect transport state rather than assuming continuity;
- attempt ICE restart for a live WebRTC session where appropriate;
- if the transport is dead, establish a new transport binding using the still-live runtime session;
- if the runtime session/ticket has expired, require control-plane re-auth/session establishment rather than accepting stale transport identity;
- request the appropriate semantic baseline/watermark from SMX-010/017/046; transport resumption alone is not state authority.

### Trust distinction

**Peer-hosted:** the designated participant host is current simulation authority under the room policy, but is not trusted for fairness. The signalling service authenticates participants and routes negotiation; TURN/WSS relay infrastructure routes traffic and may enforce service abuse limits but does not decide canonical simulation state.

**Dedicated-authoritative:** the operated dedicated service is the declared simulation authority and has a stronger deployment trust role. Clients remain hostile input sources and submit allowed intent. Service TLS/authentication proves the endpoint/session relationship, not canonical content provenance or runtime capability.

## 7. Evidence, adversarial boundary and limitations

`SMX-045-NETWORK-DEPLOYMENT-FIXTURES.json` freezes ND-001..016 and NDF-001..016. The executable spike covers:

- principal/session/transport role separation and reconnect rebinding;
- short-lived scoped ticket success, expiry, tamper, wrong-room and single-use replay rejection;
- direct WebRTC, TURN-relayed WebRTC and WSS peer-relay fallback selection;
- explicit TLS, signalling, ICE, TURN, unavailable-transport and dedicated-authority failure mapping;
- bounded signalling and rejection of principal/Thing/capability/host/peer authority injection;
- dedicated server loss without client promotion;
- session expiry during reconnect;
- peer-versus-dedicated trust distinction;
- complete protected-Asset revision preservation and incomplete-revision rejection.

The real browser probe measures local DataChannel establishment time and loopback message RTT plus candidate counts. `spike.py` measures scoped-ticket issue/redeem cost and representative signalling-envelope size. Both record environment/version metadata and state explicitly that they are **CI-local mechanism evidence, not product latency/throughput SLOs**.

The retained `.github/workflows/smx017-real-topologies.yml` remains the real Godot/browser/headless topology and suspension/reconnect evidence. SMX-045 does not copy that harness into production or reinterpret its transport relay as final architecture.

Residual limitations deliberately handed to SMX-046/047:

- CI does not reproduce the public Internet's NAT/firewall diversity; production STUN/TURN deployment requires operational monitoring and later hostile-network/WAN qualification;
- TURN credential issuance/key rotation and service abuse controls are deployment implementation, not canonical semantics;
- the exact identity provider/vendor is intentionally not frozen;
- the native WebRTC plugin is not mandatory for the dedicated WSS baseline and must be pinned/reviewed if later enabled;
- WSS head-of-line behavior may be unsuitable for a future latency-sensitive delivery profile; that must be demonstrated by workload evidence rather than guessed now;
- cross-browser/mobile lifecycle policy remains a later supported-target qualification obligation.

No Architecture-v1 contradiction was found; no ADR is required.

## 8. SMX-046 production handoff

SMX-046 can proceed without reopening mechanism discovery. It must:

1. implement `networking.runtime` as an adapter/service layer below the topology-independent SMX-010 semantics;
2. keep principal, runtime session, transport connection and `ThingId` identities role-distinct;
3. implement authenticated WSS signalling/control with bounded envelopes and final admission checks;
4. implement browser peer-host WebRTC DataChannel with ICE/STUN/TURN, short-lived TURN credentials and bounded establishment/restart;
5. implement authenticated WSS peer-relay fallback without promoting the relay to simulation authority;
6. implement dedicated-authoritative WSS for browser/native clients and fail closed on dedicated authority loss;
7. implement authorization-code + PKCE control-plane integration and short-lived scoped runtime join admission without exposing account/access tokens to peers;
8. map physical TLS/signalling/ICE/TURN/suspension/reconnect/server errors to the typed outcomes above;
9. port TN-001..028 and the deferred network-ingress AT-023/AT-024 security cases to the **real production ingress**, including sender/session/epoch/replay/rate/queue bounds;
10. preserve authority epochs, relevance/unloaded semantics, baseline/watermark reconnect and no-client-promotion rules from SMX-010/017;
11. retain complete protected source/audio/provenance revisions without field mixing;
12. record mechanism measurements as named-target evidence without converting CI-local samples into product SLOs.

SMX-047 remains the destructive topology-equivalence and hostile-network gate over that production implementation.
