# SMX-046 — production networking services, authority, reconnect and relevance

**Status:** production implementation for Phase 9  
**Issue:** SMX-046 / #71  
**Architecture:** Architecture v1.0; no amendment required  
**Primary code:** `src/splashmx/runtime/network.py`, `src/splashmx/runtime/web/network_transport.mjs`  
**Conformance:** `spec/production/smx046-networking-fixtures.json`, `tests/production/test_smx046.py`

## Production contract

`networking.runtime` is the service/adapter layer below the topology-independent SMX-010 semantic model and above selected physical transports. It implements the SMX-045 handoff without making WebRTC, WebSocket, ICE, TURN, Godot peer IDs, sockets, signalling handles or deployment endpoints canonical authoring concepts.

The identity domains are deliberately separate:

- `ThingId` is durable semantic identity;
- `principal_id` is authenticated user/service identity;
- `session_id` identifies one bounded runtime room membership;
- `transport_id` identifies one transient physical connection binding;
- `authority_epoch` is the semantic generation of current simulation authority.

Reconnect may replace `transport_id` while preserving a live principal/session and every Thing identity. Leaving or losing transport context does not destroy controlled Things, rewrite the project or transfer simulation authority by implication.

## Authentication, signalling and transport admission

Control-plane authentication remains authorization-code + PKCE. The runtime boundary verifies S256 PKCE integration and uses an opaque server-side runtime join ticket: the random bearer is hashed in the admission store, is single-use, has a hard maximum lifetime, and is scoped to room and audience. OAuth access tokens are not sent to peers and package/TUF signing keys are not reused as runtime identity roots.

SMX-045 transport selection is implemented as the adapter policy:

- browser peer-hosted primary: WebRTC DataChannel;
- ICE/STUN path discovery and TURN relay remain target/deployment-private;
- authenticated WSS relay is the bounded peer fallback and never becomes simulation authority;
- browser/native dedicated-authoritative baseline: authenticated WSS;
- insecure `ws://` dedicated transport is rejected at the browser adapter boundary.

Signalling is bounded independently from semantic ingress. Its schema may carry negotiation material and transient session/transport binding, but recursively rejects Thing, principal, authority-epoch, capability, engine, host, process, socket and filesystem authority injection.

`src/splashmx/runtime/web/network_transport.mjs` is the browser physical adapter used by the SMX-046 real-Chromium gate. It creates an ordered `splashmx-runtime` DataChannel, supports ICE restart, bounds semantic bytes before send/after receive, rejects recursive authority-bearing payload fields, and exposes only semantic envelopes to its caller. The dedicated WSS entry point requires `wss://` before any socket is constructed.

## Hostile production ingress

Every semantic message is hostile until the production `RuntimeNetworkingService.ingress()` boundary has independently checked:

1. canonical-JSON representability and the message byte budget;
2. recursive serialized-authority depth and forbidden capability/host/engine/session/transport fields;
3. an admitted, unexpired sender session with a currently bound transport;
4. the room/service boundary established at admission;
5. per-session rate budget;
6. target existence and tombstone state;
7. exact current authority epoch;
8. monotonic sequence and bounded sequence gap;
9. bounded replay/dedup history;
10. message-class-specific controller/authority and declared-locus rules;
11. declared numeric input bounds where present;
12. known-unloaded pending/coalescing queue budgets.

The failure is a stable typed `network.*` outcome. Rejection occurs before semantic mutation for the corresponding boundary. Rejection and accepted-class counters provide bounded operational observability without turning transport diagnostics into project state.

This closes the network-specific SMX-041 deferrals: AT-023 is exercised against the real production sender/session/room/epoch path, and AT-024 is exercised against production byte/tree/rate/queue limits rather than the pre-v1 model.

## Authority, control and migration

Controller binding and simulation authority are independent. Input is intent: a controller can submit only declared input kinds and bounded values, and that path never writes replicated state directly. State/event/baseline messages require the current authority session.

Peer-host migration is an explicit transaction:

1. capture a confirmed semantic checkpoint for one coherent authority epoch;
2. verify the destination is an admitted session with a live transport;
3. validate the complete checkpoint scope and protected Asset revisions before mutation;
4. stage all Thing and Asset data;
5. atomically replace authority binding for the scope and increment the epoch;
6. preserve state watermarks and reject prior-epoch traffic thereafter.

The portable `AuthorityCheckpoint` contains semantic state, watermarks, epoch and complete protected Asset revisions. It deliberately contains no old host session, transport, socket or process handle. Invalid/incomplete checkpoints fail before the existing authority is changed.

Dedicated-authoritative loss maps to `network.authority_lost`; ordinary clients are never self-promoted. Client authority migration is rejected in dedicated topology.

## Reconnect, baseline and lifecycle/relevance

Transport disconnect may preserve the authenticated runtime session for a bounded reconnect. A reconnect must bind a new transient transport identity; binding generation increases while principal/session and Thing identity remain unchanged. The reconnect baseline contains relevant semantic state, authority epochs and state watermarks but no transient transport/session handle.

Relevance is runtime replication context, not object existence:

- relevance leave does not unload, tombstone, reparent or transfer authority;
- `known_unloaded` remains a valid durable target;
- latest state for an unloaded Thing is coalesced per state locus;
- semantically reliable unloaded events use a bounded queue and dedup identity;
- restore exposes the bounded pending obligations;
- tombstoning drops pending work and future network delivery is rejected;
- a tombstoned Thing cannot be resurrected by changing network residency.

This preserves the SMX-030 logical-streaming contract instead of coupling network interest to containment or cache layout.

## Message classes and replay/order rules

The production layer preserves the SMX-010 message-class split:

- **input** — controller-authored intent; declared kind and bounds; never authoritative state;
- **state** — current-authority authored, locus-declared, watermark protected and supersedable/coalescible;
- **event** — current-authority authored discrete occurrence with bounded dedup/reliable pending behavior;
- **baseline** — current-authority semantic state initialization, restricted to declared state loci.

Replay IDs and sender/class sequence watermarks are bounded runtime state. They are not authored identity and are not serialized into the canonical project.

## Protected source/audio/provenance boundary

Networking carries or checkpoints a protected Asset revision only as the same complete immutable unit selected by stable `AssetId`. The required fields are revision/content digest, source digest and logical source identity, exact source metadata, audio/media semantic metadata, provenance, licence/attribution and derivation lineage.

Topology projection, WebRTC/WSS framing, reconnect, authority migration, relevance, baseline construction, transport fallback and target-private caches have no authority to combine fields from competing revisions or replace canonical meaning. An incomplete protected revision is rejected atomically before migration or insertion.

## Conformance and adversarial coverage

`tests/production/test_smx046.py` ports **TN-001..TN-028** to the production module. The suite also covers the deferred **AT-023** and **AT-024** production network-ingress attacks, single-use room/audience-scoped tickets, PKCE S256, transport-path restrictions, reconnect after physical loss, bounded unloaded-event queues, deep recursive authority injection, and typed failure without project rewriting.

The dedicated CI gate additionally runs the retained SMX-010/017 semantic validators/oracle, SMX-041/045 security/deployment validators and a pinned real-Chromium test over the production browser adapter. The browser evidence records DataChannel establishment/delivery, ICE-restart availability, rejection-before-send for hostile/oversized semantic envelopes and fail-closed rejection of insecure dedicated WebSocket URLs.

## Deliberate residual scope

SMX-046 does not claim public-Internet NAT/firewall coverage or final topology equivalence. TURN operations, WAN loss/reorder/latency, hostile-network certification, cross-browser/mobile lifecycle qualification and final end-to-end topology equivalence remain SMX-047 obligations. CI-local transport timings are mechanism evidence only and are not product SLOs.

The identity-provider vendor, deployment routing provider and TURN credential service are also operational choices below this contract. Changing them must preserve the same bounded admission and identity separation; it does not justify canonical-format changes.

## Architecture compatibility

No Architecture-v1 contradiction was found. The production implementation directly preserves NET-001..020, the non-droppable R-016 recursive-authority boundary, R-019-01 target-private runtime projection, path-independent identity and the protected-media revision contract. No ADR is required.
