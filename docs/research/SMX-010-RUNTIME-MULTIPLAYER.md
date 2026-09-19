# SMX-010 — Runtime multiplayer semantics, authority, replication, and topology independence

Status: **research candidate / pre-Architecture-v1.0**  
Issue: SMX-010 / #10  
Evidence refresh: **2026-09-19**  
Godot baseline: **Godot 4.7.2 stable**; browser constraints refreshed against the 4.7 documentation branch.

This document defines SplashMX runtime multiplayer above the Thing/document/execution/security/lifecycle/streaming/Godot boundaries established by SMX-002 through SMX-009. It does **not** freeze a wire protocol, matchmaking service, Godot RPC layout, transport, congestion-control implementation, prediction algorithm, or production server architecture.

## Contents

| Section | Summary |
|---|---|
| 1. Result | Defines the topology-independent network semantic layer. |
| 2. Carried-forward contracts | Records authoritative constraints that networking may not rewrite. |
| 3. Current platform evidence | Refreshes Godot/browser networking facts as of 2026-09-19. |
| 4. Identity and relationship model | Separates Thing, principal/player, session/peer, control, authority, replication, containment, and persistence. |
| 5. Message classes | Defines state, event, input/command, snapshot/baseline, and derived prediction classes. |
| 6. Authority and control transfer | Defines epochs, transfer, stale-message rejection, and host migration. |
| 7. Relevance and streaming | Integrates network interest with unloaded/tombstoned references. |
| 8. Join, leave, reconnect, migration | Defines transient session rebinding without replacing Things. |
| 9. Topology policies | Maps one creation model to offline, peer-hosted, and authoritative execution. |
| 10. Security and capability boundary | Treats peers as hostile and keeps raw transports below mediation. |
| 11. Determinism and latency compensation | Places network arrivals at the explicit external-input boundary. |
| 12. Beginner/editor projection | Shows simple author choices without exposing topology machinery. |
| 13. Executable falsification slice | Summarizes NET-### invariants and NT-### adversarial fixtures. |
| 14. SMX-017 equivalence specification | Gives the concrete destructive network harness contract. |
| 15. Rejected alternatives | Records designs that violate existing contracts. |
| 16. Hypothesis reconciliation | Updates H-012/H-013/H-014. |
| 17. Downstream handoffs and residual uncertainty | Defines SMX-012/014/017 obligations and what remains unproven. |

## 1. Result

The selected candidate is a **topology-independent network facet plus runtime policy/context**:

```text
Canonical Thing / authored declaration
├─ stable ThingId
├─ ordinary authored/runtime state
├─ declared network facet
│  ├─ replicated state loci
│  ├─ declared input/command kinds
│  ├─ declared event kinds
│  ├─ semantic delivery requirement
│  └─ relevance/authority policy hooks
└─ NO peer IDs, sockets, Godot RPC paths, live authority tokens, or transport handles

Runtime network context
├─ authenticated principal/player identity
├─ transient peer/connection identity
├─ controller binding
├─ simulation-authority binding + authority epoch
├─ session membership
├─ relevance set / replication cursors
├─ topology policy
└─ transport adapter
```

The critical rule is:

> **Topology chooses who currently performs authority/replication work and which adapter carries messages; it does not create a different kind of Thing.**

A networked Thing does not become a “network object” subclass. Offline execution uses the same declarations with local policy and no network transport.

### Candidate multiplayer invariants

- **NET-001 — canonical network declaration is topology-independent.** Authored semantics name replicated loci, inputs/events, and semantic delivery/relevance requirements; they do not name current peers, server addresses, Godot RPCs, sockets, or transports.
- **NET-002 — containment, input control, simulation authority, replication, persistence, and observation are independent relationships.** Mutating one does not silently mutate the others.
- **NET-003 — identity domains are distinct.** `ThingId`, durable user/principal identity, runtime session identity, and transient transport peer/connection identity are not interchangeable.
- **NET-004 — client input is intent, not authoritative state.** In authoritative policy, a client may submit declared inputs/commands; the authority validates and produces authoritative state/events.
- **NET-005 — state, event, input/command, baseline/snapshot, and derived prediction are distinct message classes.** They have different replay, persistence, ordering, and supersession rules.
- **NET-006 — semantic delivery requirement is above transport.** “latest state”, “reliable ordered occurrence”, “best-effort sample”, etc. may be mapped to WebRTC/WebSocket/ENet channels differently without changing authored meaning.
- **NET-007 — authority transfer is epoch-scoped.** Transfer preserves Thing identity, increments an authority generation/epoch, and rejects stale prior-authority messages.
- **NET-008 — replay/duplicate handling is explicit and bounded.** Inputs/state use monotonic sequence/watermarks as appropriate; semantically reliable events carry deduplication identity where retry/reconnect can duplicate delivery.
- **NET-009 — relevance is runtime context, not existence or containment.** Removing a Thing from one peer's interest set does not destroy, unload, reparent, or transfer authority by implication.
- **NET-010 — network delivery respects lifecycle absence states.** `known_unloaded`, `tombstoned`, `unknown`, and `dependency_unavailable` remain distinct; a valid unloaded target may receive a bounded/coalesced delivery obligation.
- **NET-011 — reconnect rebinds transient peer/session context.** Reconnection may bind the same authenticated principal to a new peer ID while preserving Thing IDs and policy-selected controller relationships.
- **NET-012 — peer-host migration is an explicit topology operation.** It requires a coherent checkpoint/watermark and authority-epoch transition; failure to establish one is explicit rather than silent split-brain.
- **NET-013 — offline uses the same creation semantics.** Local policy supplies controller/authority and performs no wire replication; network declarations remain inert/locally resolved rather than rewritten.
- **NET-014 — prediction/interpolation/reconciliation are optional derived presentation/simulation techniques.** Predicted/interpolated values are not canonical authored state and do not silently become persistent truth.
- **NET-015 — network arrival is explicit external nondeterminism.** Authoritative sequencing may make a simulation reproducible; deterministic replay requires the same ordered network/input stream, not merely the same save.
- **NET-016 — multiplayer is capability/service mediated and network ingress is hostile.** Ordinary IR does not receive raw sockets or transport objects; schema, sender, authority, relevance, size, rate, queue and reference checks apply independently.
- **NET-017 — peer-hosted rooms do not imply trusted peers.** A host can be the room's simulation authority while still being untrusted from another participant's fairness/security perspective; security claims must state the trust model.
- **NET-018 — persistent-world/server state excludes live session handles.** Persistent simulation snapshots can retain semantic state and authority-policy requirements, but current peer IDs, sockets, capability grants and transport handles are rebound.
- **NET-019 — runtime replication is not collaborative editing.** Runtime state/input/event protocol cannot apply canonical document transactions merely because both systems exchange messages.
- **NET-020 — networking cannot rewrite protected source/audio/provenance semantics.** Topology projection, headless execution, replication, migration and reconnect preserve canonical asset/source/audio identity, immutable digests, provenance/licensing and derivation records.

## 2. Carried-forward contracts

SMX-010 accepts these merged constraints rather than reopening them:

- **SMX-002/003:** Thing identity is path-independent; containment, control, authority, persistence and replication are separate; definitions/instances do not own current network context.
- **SMX-004:** network arrivals/service responses are explicit external inputs into bounded transactional turns; cross-Thing effects use declared interfaces, not direct foreign-state writes.
- **SMX-005:** authored document, runtime state, persistent save/world state and transient network context are separate planes; durable references use semantic IDs.
- **SMX-006:** network ingress is an independent hostile boundary; remote messages cannot mint local host capabilities; queues/rates/message sizes are hard-bounded.
- **SMX-007:** controller/authority/session/transport state is rebound on restore; peer/socket handles are not save authority.
- **SMX-008:** known-unloaded references remain valid; portable host-migration capsules contain semantic state + exact dependencies, not peer/session/host handles.
- **SMX-009:** Godot/network transports are adapters below SplashMX authority/replication meaning; source/audio/provenance semantics are protected across web/native/headless projection.

## 3. Current platform evidence — refreshed 2026-09-19

These are implementation facts, not SplashMX public protocol.

### Godot high-level multiplayer

Godot high-level networking is configured through `MultiplayerAPI`/`MultiplayerPeer` and the SceneTree. Current documentation assigns transient peer IDs (server ID `1`, clients positive IDs), exposes authority/`any_peer` RPC modes, and maps calls to transfer modes including reliable, unreliable, and unreliable-ordered channels. These are useful substrate concepts but are too Godot/scene/RPC-specific to be the SplashMX compatibility contract.

Primary source:
- https://docs.godotengine.org/en/4.7/tutorials/networking/high_level_multiplayer.html

The current high-level multiplayer guidance also explicitly treats client input as untrusted for server-authoritative/competitive or persistent games and recommends validating client intent instead of accepting client-authored critical state. This supports NET-004/016 but does not require every SplashMX game to use dedicated authority.

### Browser networking

Godot 4.7 web export supports HTTP, WebSocket client and WebRTC; low-level networking is unavailable in the browser target. WebSocket is available on native and web. WebRTC is built into web exports but native Godot requires the separately installed native WebRTC implementation/plugin.

Primary sources:
- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#networking
- https://docs.godotengine.org/en/4.7/tutorials/networking/websocket.html
- https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html

**Consequence:** a creation that semantically needs “reliable ordered event” or “latest supersedable state” must not encode `WebSocket`, `WebRTC`, ENet, UDP or a Godot channel number. Target/topology policy chooses an adapter that can satisfy the declaration.

### Browser lifecycle

Godot 4.7 documents that an inactive browser tab can pause processing and disconnect a networked game after a long enough suspension.

Primary source:
- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#background-processing

**Consequence:** reconnect/rejoin is a first-class runtime transition, not an exceptional implementation bug. SMX-017 must include tab suspension.

### Headless/dedicated server

Godot supports `--headless` and dedicated-server exports without requiring a distinct SplashMX creation model.

Primary source:
- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html

**Consequence:** authoritative server policy may run the same canonical Thing/IR/network declarations without presentation bindings.

## 4. Identity and relationship model

### 4.1 Identity domains

SplashMX requires at least these distinct roles:

| Identity | Lifetime / role | Canonical? |
|---|---|---|
| `ThingId` | durable logical Thing | yes |
| authenticated principal/user/player identity | durable/account/session-policy subject | external/context; only durable references when explicitly needed |
| runtime session/room identity | one multiplayer execution context | runtime/service state |
| transport peer/connection ID | one current connection | transient context only |
| authority epoch | generation of authority for a Thing/scope | runtime semantic state; persist only when required by persistent-world protocol |
| event/input IDs/sequences | dedup/order within a declared scope | runtime protocol state |

Godot peer ID `1` is therefore not “the server identity” in durable SplashMX semantics. A reconnect may yield a different transport peer while referring to the same authenticated principal.

### 4.2 Independent relationships

For one Thing the following may all point to different subjects:

```text
contains(parent, thing)
controlled_by(thing, principal)
authority_at(thing/scope, authority principal)
replicated_to(thing, session/relevance set)
persisted_via(thing, world service)
observed_by(thing, observer)
```

A passenger can be structurally inside a vehicle, controlled by one player, simulated by a server, observed by many peers, persisted by a world service, and locally hidden from an irrelevant client. None of those facts is the semantic owner of the others.

## 5. Message classes

### 5.1 Replicated state

Represents current authoritative value at a declared locus. Typical semantics:

- authority-authored;
- latest value may supersede older value;
- sequence/watermark prevents stale rollback;
- baseline/snapshot can initialize a joining/rejoining peer;
- may be coalesced while a Thing is unloaded or irrelevant;
- persistent only if the state locus itself is selected by persistence policy.

### 5.2 Events

Represent discrete occurrences such as `hit`, `door_opened`, or `timeline_marker`.

If an event is semantically “reliable occurrence”, reconnect/retry can duplicate packets; the runtime therefore needs a bounded event ID/dedup window. A transport's “reliable” flag is insufficient as the public semantic definition.

### 5.3 Inputs / commands

Represent participant intent. They identify sender principal/session, target, input kind, sequence and applicable authority epoch. They do **not** directly assert final authoritative state.

### 5.4 Baseline / snapshot

A joining peer may need a coherent authority-produced baseline plus sequence watermark before deltas/events are admitted. The baseline is a network projection of runtime state, not the editable canonical document and not a Godot scene snapshot.

### 5.5 Derived prediction/interpolation

Prediction/interpolation/reconciliation caches are reconstructible runtime context. A client can present predicted movement while authoritative state remains unchanged. A project may opt into a reconciliation policy, but prediction is not mandatory for static/shared media or low-frequency state.

## 6. Authority and control transfer

### Authority transfer

Candidate safe transition:

1. reach a quiescent/defined replication cut;
2. capture authoritative state baseline + accepted-input/event watermarks;
3. choose/authenticate the new authority according to topology policy;
4. increment authority epoch;
5. publish the new authority binding and baseline atomically for the scope;
6. reject messages from prior epochs;
7. resume input admission.

Thing identity, containment, behaviour attachment IDs, source/provenance, and persistent state identity are unchanged.

### Control transfer

Changing the user/controller relationship is separate. A server may remain simulation authority while control moves from human A to human B or to AI. Controller change does not require reconstructing the Thing.

### Host migration

Peer-hosted migration is only safe when the room can establish one coherent checkpoint/watermark. If the old host disappeared before peers agree on a sufficiently authoritative baseline, policy may:

- elect a new host from the last confirmed checkpoint and explicitly roll back;
- resume from a durable room service checkpoint;
- terminate/recreate the runtime session.

It must not merge contradictory peer snapshots implicitly or accept two concurrent authority epochs.

## 7. Relevance and streaming

Interest/relevance answers “which network state does this peer presently need?” It does not answer “does the Thing exist?”

- `relevant + resident`: normal replication.
- `irrelevant + resident`: replication may pause/coalesce; local Thing can remain resident.
- `known_unloaded`: durable reference remains valid. Latest state can be coalesced; semantically reliable events may become bounded pending-delivery records if policy requires them.
- `tombstoned`: new state/event delivery is rejected; tombstone/removal information may replicate as its own lifecycle protocol.
- `dependency_unavailable/incompatible`: do not activate a half-valid Thing; surface typed failure.

SMX-008 acquisition remains authoritative: receiving a network reference is not permission to bypass dependency/capability/security validation.

## 8. Join, leave, reconnect, and migration

### Join

A participant joins by establishing authenticated principal/session context, negotiating protocol/runtime feature compatibility, receiving relevant entity catalog/baseline data, then beginning deltas/events after the baseline watermark.

### Leave/disconnect

Disconnect removes transient peer/transport context. It does not automatically destroy controlled Things. Topology policy decides whether control transfers, AI takes over, the Thing becomes dormant, or a grace/reconnect interval applies.

### Reconnect

Reconnect binds the authenticated principal to a new connection/peer identity, negotiates the last accepted watermark, and sends missing baseline/delta/event state. Live host capability grants are re-evaluated; they are not received over the network.

### Execution-host/server migration

Use the SMX-008 migration-capsule direction: quiescent semantic state, exact artifact requirements, durable pending work and stable references transfer; destination creates new transport/session/host handles under current security policy.

## 9. Topology policies

| Semantic layer | Offline/local | Peer-hosted room | Dedicated authoritative |
|---|---|---|---|
| Canonical Thing/network declarations | same | same | same |
| Thing IDs / ports / behaviours | same | same | same |
| current authority | local runtime | elected/designated host or distributed per explicit policy | server/runtime service |
| client/player inputs | local ordered input | remote intent validated by current authority policy | untrusted intent validated by server |
| replication | no wire; local projection | peer/host dissemination | server-to-client dissemination |
| reconnect | usually N/A/local resume | host/session rejoin; host loss may require migration | reconnect to server/service |
| transport | none | target policy, often WebRTC or relay/WebSocket | target policy, e.g. WebSocket/ENet/custom adapter |
| trust model | local content sandbox still applies | peers/host not inherently trustworthy | server trusted for simulation truth; clients hostile |
| persistence | local save/world policy | local/host/service policy | server/world service policy |

This table strengthens H-012 at model level: no tested topology requires a different Thing type or canonical creation.

## 10. Security and capability boundary

Networking carries forward SEC-007/012 and D-038/D-039/D-040:

- ordinary behaviour does not receive a `WebSocket`, `WebRTCPeerConnection`, ENet peer, raw socket or Godot `MultiplayerAPI`;
- a `multiplayer.session`/equivalent mediated service may expose safe semantic operations;
- every ingress message validates protocol/schema/version, sender/session identity, authority epoch, declared target/input/event/state locus, reference state, size, rate and queue budget;
- client input never bypasses behaviour/game validation merely because it came through an authenticated connection;
- remote messages cannot carry live local capability grants;
- causal attribution survives mediated command/event chains;
- network-created load/acquisition work remains subject to SMX-006/008 byte/dependency limits;
- signatures/encryption/authentication prove properties of origin/channel; they do not make application payloads semantically trusted.

Peer-hosted topology is therefore a *deployment trust trade-off*, not a security guarantee equivalent to dedicated authority.

## 11. Determinism and latency compensation

Network packets are external nondeterministic inputs under EXE-015/LIF-015. The authoritative runtime may assign a stable accepted-input order and record it for replay/debugging. Exact future replay requires that same accepted stream.

Prediction/interpolation are derived optimizations:

- no requirement for every Thing;
- never grant the predicting peer authority;
- reconciliation uses authoritative sequence/epoch;
- derived caches may be discarded on unload/reconnect;
- authoritative state remains the persistence source unless an explicit persistence policy says otherwise.

Physics nondeterminism across engines/platforms means SplashMX must not assume “send inputs only and every peer will deterministically simulate identical Godot physics” as a universal strategy. Lockstep can be an optional specialised policy only after SMX-017 evidence.

## 12. Beginner/editor projection

The editor should project internal declarations into choices that preserve correct semantics, for example:

- **Only on this device** → local/offline, no wire replication.
- **Shared with everyone** → replicated authoritative/shared state according to room policy.
- **One per player** → runtime creation/control template, not a new network subclass.
- **Controlled by its player** → input-controller relationship.
- **Server decides** → authoritative policy for critical state.
- **Nearby players only** → relevance policy.
- **Smooth remote movement** → optional interpolation/prediction policy.

Advanced panels may reveal delivery/relevance/reconciliation details, but authors should not need to select a Godot RPC annotation or network peer ID.

## 13. Executable falsification slice

`experiments/smx-010-multiplayer-model/` is non-production. It models one canonical creation under offline, peer-hosted and authoritative topology profiles and directly exercises `NT-001` through `NT-020`.

High-value adversarial checks include:

- `NT-001`: canonical digest is identical across all three topologies.
- `NT-002`: reparenting cannot mutate controller, authority or network declaration.
- `NT-004`/`NT-006`: non-controller input and non-authority state forgery are rejected.
- `NT-005`/`NT-007`: duplicate inputs and stale authority epochs fail.
- `NT-009`: reconnect changes peer ID without changing principal/controller/Thing identity.
- `NT-010`–`NT-013`: unloaded delivery is bounded/coalesced; tombstones reject new state.
- `NT-014`: peer-host migration preserves Thing IDs and bumps authority epoch.
- `NT-015`: `peer_id`, WebSocket/WebRTC/ENet/UDP/RPC/NodePath-style transport/runtime identifiers are rejected from canonical network data.
- `NT-016`: topology activity leaves source/audio/provenance metadata unchanged.
- `NT-017`: non-offline multiplayer requires mediated capability/service admission.
- `NT-018`: collaboration transaction vocabulary is absent from runtime replication declarations.
- `NT-019`/`NT-020`: undeclared network loci and unsupported host migration are rejected.

Passing these tests is evidence for semantic separability, not proof of packet-loss/latency/security performance in a real browser/Godot implementation.

## 14. Concrete SMX-017 topology-equivalence specification

SMX-017 must load **the exact same canonical revision** into these modes:

1. offline/local;
2. peer-hosted browser room;
3. dedicated authoritative server + browser client.

It must then run one scripted scenario corpus with stable expected semantic outcomes:

- create/activate the same Things and verify IDs/network declarations are unchanged;
- bind a player/controller, move/control a Thing, and verify containment remains unchanged;
- replicate state + at least one discrete reliable event;
- exercise relevance enter/leave without destruction/unload conflation;
- unload a referenced Thing, deliver coalescible state + reliable event, restore, verify outcome;
- transfer control independently from authority;
- transfer/migrate authority and inject stale prior-epoch packets;
- disconnect/reconnect with a new transport peer identity;
- for peer-hosted mode, migrate host from a confirmed checkpoint and separately test unrecoverable host-loss policy;
- suspend a browser tab long enough to force pause/disconnect behavior, then exercise reconnect/resync;
- inject duplicate, reordered, oversized, undeclared and forged-authority messages and verify bounded failure;
- verify capability grants/host handles cannot arrive through network messages;
- compare semantic snapshots after authoritative quiescent cuts;
- verify source/audio/provenance/asset identities and digests are byte/semantic-equivalent across topology projections;
- record latency/prediction differences separately from authoritative semantic outcomes.

### Required equivalence assertions

- same canonical creation digest/revision;
- same Thing/Definition/Attachment/Port identities;
- no topology-specific object subclasses or authored document rewrite;
- same authoritative state after equivalent accepted input sequence, modulo explicitly declared nondeterministic external inputs;
- same lifecycle/reference distinctions;
- same capability/security boundary;
- same protected source/audio/provenance semantics.

### Required divergence record

SMX-017 must explicitly list acceptable topology-specific differences:

- transport/peer IDs;
- latency, packetization and channel selection;
- which runtime currently hosts authority;
- connection/reconnect mechanics;
- prediction/interpolation caches;
- presentation omission on headless;
- operational deployment/scaling policy.

Any additional semantic divergence is a candidate H-012 failure and must amend this document/upstream contracts rather than being hidden in harness code.

## 15. Rejected alternatives

### Network-object subclass hierarchy

Rejected. It violates P7/H-012 and creates conversion/rewrite pressure between offline and networked objects.

### Godot RPC annotations as the canonical protocol

Rejected. They bind public meaning to Node paths/SceneTree authority, Godot peer IDs and engine transfer modes, conflicting with GOD-009/GOD-017.

### Parent/owner implies network authority

Rejected. It violates P5/P6, K-003/K-004, CMP-012 and the executable reparent adversary.

### Client writes replicated state directly

Rejected as a universal model. It is unsafe for authoritative/persistent games and prevents a clean distinction between intent and truth. Peer/shared experiences may choose permissive authority policy explicitly, but that is policy rather than a different object type.

### “Reliable transport means exactly-once event”

Rejected. Reconnect/retry/application replay can duplicate logical deliveries; event IDs/dedup/watermarks are semantic obligations where exactly-once-like observation matters.

### Universal deterministic lockstep

Rejected as the baseline. Browser suspension, physics/platform nondeterminism, heterogeneous frame cadence, late joins and streaming make it unsuitable as the universal model. It remains a possible specialised policy.

### Collaboration transactions over runtime replication

Rejected. Persistent multi-author conflict semantics are SMX-011/018 and remain separate from live simulation authority.

## 16. Hypothesis reconciliation

Evidence: this document, `docs/research/SMX-010-RUNTIME-MULTIPLAYER-FIXTURES.json`, and `experiments/smx-010-multiplayer-model/`.

- **H-012 strengthened substantially at model level, still awaiting real topology harness.** One canonical creation and Thing/network declaration is exercised unchanged under offline, peer-hosted and dedicated-authoritative policies. Authority/control/relevance/reconnect/host migration are contextual transitions, not object subclasses. SMX-017 must still test real browser/server transports, latency, suspension and failure.
- **H-013 strengthened.** Runtime replication declarations contain state/event/input/relevance/authority semantics but deliberately contain no canonical edit transaction/base-revision/conflict vocabulary. Collaboration remains a separate consistency layer even if it later shares authenticated sessions/transports.
- **H-014 strengthened further at network boundary.** Godot peer IDs, SceneTree authority, RPC annotations and transfer channels remain adapter data. Current WebSocket/WebRTC/headless facilities can implement policy without entering canonical identity. Real production performance/feature gaps remain SMX-017/019.

No evidence from SMX-010 weakens source/audio/provenance, lifecycle, migration, security or canonical-document decisions.

## 17. Downstream handoffs and residual uncertainty

### SMX-012 editor projection

Prototype the beginner choices in section 12. UX must explain “controlled by” versus “server decides/shared” without exposing peer IDs, authority epochs or transport selection in normal workflows.

### SMX-014 publish/player/server

Define package/runtime manifests that carry topology-independent network declarations and target feature requirements. Web/native/headless artifacts may select different adapters but cannot rewrite canonical network or source/audio/provenance meaning.

### SMX-017 network harness

Implement section 14 exactly, including browser tab suspension, stale-epoch injection, reconnect with changed peer ID, host-migration checkpoint failure, unloaded delivery budget, and semantic snapshot comparison.

### Remaining uncertainties

- production representation/encoding for network envelopes;
- congestion control, MTU/fragmentation and transport channel mapping;
- exact relevance algorithms and large-room scaling;
- authentication/account service design;
- NAT/relay/signalling service choice;
- persistent-world cluster leadership/failover;
- real Godot 4.7.2 browser/native/headless behavior under loss/latency;
- which prediction/reconciliation presets are understandable enough for authors.

These are intentionally not promoted into canonical semantics without SMX-017/019 evidence.
