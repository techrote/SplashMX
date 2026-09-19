# SMX-017 — Decision and evidence record

Evidence date: **2026-09-19**  
Issue: **#17**  
Status: **candidate until final real-topology CI passes**

This file is the compact retrieval record for the SMX-017 destructive topology campaign. Detailed contracts and limits are in `SMX-017-NETWORK-HARNESS.md`; machine-readable invariants are in the companion fixture JSON.

## Decisions

### D-105 — Runtime topology remains policy/context, not canonical object taxonomy

The real integration harness uses the same canonical creation bytes, Thing/Definition/Attachment/Port identities and one Godot runtime implementation for offline, peer-hosted-browser and dedicated-authoritative execution. A topology may choose current authority, transient transport IDs, relay/signalling and reconnect policy, but may not rewrite the creation into topology-specific object classes.

### D-106 — Browser peer hosting may use transport relay infrastructure without transferring simulation authority to the relay

Because browser Web exports cannot accept raw WebSocket listening streams, the test browser room uses a trusted routing relay. The exported browser Godot runtime remains the peer simulation authority. The relay may assign connection identity, route/perturb envelopes, retain a confirmed checkpoint and choose a successor according to explicit peer-host policy; it does not become canonical simulation state or a public SplashMX network protocol.

### D-107 — Reconnect and host migration require semantic rebinding rather than identity replacement

A reconnect binds the same durable principal/Thing semantics to a new transient connection identity. Peer authority migration requires a confirmed checkpoint and strictly higher authority epoch. Old-epoch traffic fails closed. Missing confirmed migration state is an explicit unavailable result rather than implicit split-brain.

### D-108 — Dedicated authority loss and peer-host loss have intentionally different operational failure policies

A peer room may promote a surviving peer only from a confirmed checkpoint. A dedicated-authoritative room does not promote an ordinary browser client when the server disappears; it becomes explicitly unavailable. This is a trust/operations divergence, not a different Thing model.

### D-109 — Real browser lifecycle evidence must state the mechanism actually exercised

The harness first attempts an ordinary background-tab visibility transition. If headless Chromium does not expose that transition, it uses Chromium's real lifecycle freeze primitive through CDP and records `cdp-frozen-fallback`. That fallback demonstrates process/lifecycle suspension and reconnect handling but is not relabelled as proof of every real browser's timer/background policy.

### D-110 — Protected source/audio/provenance semantics are topology-invariant

Stable `AssetId` continues to select one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation bundle. Browser export, headless execution, replication, checkpointing, reconnect and authority migration may not synthesize field-mixed revisions or promote target-private decoded/transcoded resources to canonical source meaning.

## Evidence

### E-077 — Same canonical revision is cryptographically checked by every exported runtime

The canonical fixture SHA-256 is `dd5e7bb8b33ab447b4234fb8036453b248c5721e22b9f0e1c19cc57438e71580`. Both repository copies must be byte-identical; the Godot harness independently hashes `res://creation.json` and refuses a mismatched revision before scenario execution.

### E-078 — Twenty-eight deterministic adversarial/boundary tests define the semantic oracle

`TN-001` through `TN-028` cover accepted-sequence equivalence, controller/authority/containment separation, transient reconnect identity, duplicate/reordered input, epoch rejection, confirmed/unconfirmed migration, hostile state/input, recursive authority-handle injection, bounded ingress, unloaded/relevance semantics, event dedupe, stale-state rollback, exact identity and protected-media atomicity.

### E-079 — Exported Godot/Chromium/headless topology run is the acceptance gate

`.github/workflows/smx017-real-topologies.yml` exports one Godot 4.7.2 project to Web and Linux, runs the Linux export offline, runs exported Web instances as a peer-hosted browser room, runs the Linux export as dedicated authority with an exported Web client, destructively interrupts browser/server/peer lifecycle, and compares normalized semantic snapshots. The generated evidence JSON records exact runtime versions and measured observations.

### E-080 — Network inconvenience is injected below semantics

The trusted relay deterministically reorders selected state samples, duplicates a reliable application event, changes transient connection identity on reconnect, and injects host-loss boundaries. The runtime—not the relay—must reject stale/invalid traffic, deduplicate events, coalesce state and preserve authority epochs.

### E-081 — Real-runtime evidence is deliberately bounded

Even a green campaign establishes one Godot 4.7.2 + Playwright Chromium + local relay integration slice. It does not certify WebRTC/NAT/TLS/WAN behavior, Firefox/Safari/mobile lifecycle, large-room scaling, production authentication, congestion/MTU policy or broad runtime performance.

## Open question

### O-027 — Production transport, cross-browser lifecycle and network performance envelope

SMX-019/020 must retain the remaining production evidence boundary: transport adapter selection, signalling/NAT/relay/TLS, browser/OS lifecycle diversity, authentication/service deployment, prediction presets, large-room/congestion behavior and measured startup/frame/memory/network cost. SMX-017 must not close this question by converting one CI topology slice into a production-readiness claim.
