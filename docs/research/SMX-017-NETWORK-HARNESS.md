# SMX-017 — Network topology equivalence harness

Status: **executed real-runtime evidence / pre-Architecture-v1.0**  
Issue: SMX-017 / #17  
Evidence date: **2026-09-19**  
Pinned runtime baseline: **Godot 4.7.2 stable**; Chromium is pinned through Playwright 1.55.0 and its exact runtime version is recorded by CI evidence.

SMX-017 turns the topology-independent multiplayer contract from SMX-010 into an actual exported Godot/browser/headless integration campaign. It uses one canonical creation revision and one Godot harness implementation in offline, peer-hosted-browser, and dedicated-authoritative execution. The transport relay is deliberately below simulation authority and canonical semantics.

The research claim is intentionally narrow: this harness tests **semantic topology equivalence and failure/reconnect boundaries on one current Godot + Chromium CI environment**. It is not a production network stack, WAN benchmark, NAT/signalling design, cross-browser certification, or proof that WebSocket is the final transport.

## Contents

| Section | Summary |
|---|---|
| 1. Result | States the falsifiable topology-equivalence claim. |
| 2. Carried-forward contracts | Lists semantics this issue may not rewrite. |
| 3. Current platform evidence | Refreshes Godot/browser facts that shape the harness. |
| 4. Canonical fixture and identity | Defines the exact revision/digest and protected bundle. |
| 5. Harness architecture | Separates canonical runtime, transport relay, browser orchestration and oracle. |
| 6. Executed scenario | Maps the SMX-010 section-14 campaign into real runs. |
| 7. Adversarial and boundary pressure | Records hostile ingress, ordering, lifecycle and host-loss cases. |
| 8. Browser lifecycle and reconnect | Separates measured browser behavior from explicit reconnect fault injection. |
| 9. Peer versus dedicated trust | Records the security/trust distinction without object-model divergence. |
| 10. Allowed divergences | Lists topology-specific data excluded from semantic equivalence. |
| 11. Protected media | Reasserts indivisible source/audio/provenance semantics. |
| 12. Evidence and reproducibility | Defines CI outputs, pinned versions and measured result. |
| 13. Hypothesis effects | Reconciles H-012/H-014/H-015. |
| 14. Residual limits | Keeps production/network/browser performance questions open. |

## 1. Result

The executed result is:

> **One canonical SplashMX creation executes under offline/local, peer-hosted-browser and dedicated-authoritative policies without changing its Thing/Definition/Attachment/Port identities, authored network declaration, protected asset revision, or accepted-input semantic outcome.**

Topology selects current simulation authority, transient transport/session identities, connection/reconnect mechanics and adapter policy. It does not introduce a network-only Thing subclass, rewrite containment, or turn peer IDs/sockets/Godot nodes into durable identity.

The real-runtime campaign fails if any of the following appear:

- a topology-specific canonical document rewrite;
- different Thing/Definition/Attachment/Port identities for a topology;
- client-authored critical state accepted in place of declared input intent;
- control transfer implicitly mutating containment or authority;
- relevance leave being treated as destruction/unload;
- reconnect replacing the durable principal or Thing identity;
- peer authority migration without a confirmed checkpoint/epoch transition;
- a dedicated client silently promoting itself after server loss;
- old-epoch traffic becoming authoritative after migration;
- a network message importing a capability grant, host handle or Godot identity;
- a protected media revision being field-mixed or target-rewritten.

The first fully passing exported-runtime campaign after CI repair was workflow run `35440902457` on commit `736f71a57cd95c76d00ac887b0c10ec2ec575c3e`. Later PR-head and post-merge runs remain required merge/closure gates so documentation-only or diagnostic changes cannot bypass the same campaign.

## 2. Carried-forward contracts

SMX-017 consumes rather than reopens these merged contracts:

- **SMX-005:** stable logical identity and canonical authored semantics are above physical store/transport; `AssetId` is distinct from immutable content digest.
- **SMX-006/016:** network ingress is independently hostile and cannot mint host authority; recursive host/capability injection and oversized input fail closed.
- **SMX-007/008:** `known_unloaded`, tombstoned and unknown are distinct; reconnect/restore rebind transient context; host migration requires portable semantic state rather than engine/socket identity.
- **SMX-009:** Godot Nodes/NodePaths/RIDs/ResourceUIDs/peer IDs/sockets are target-private runtime bindings; web/native/headless projection preserves canonical source/audio/provenance semantics.
- **SMX-010:** NET-001–NET-020 are the authoritative topology-independent network semantics; section 14 is this issue's required destructive scenario.
- **SMX-014:** one immutable creation revision is consumed by generic runtime profiles rather than rebuilt into topology-specific project semantics.
- **SMX-015:** Object Fabric identity/lifecycle/streaming behavior and protected-media atomicity remain invariant under destructive integration.

No accepted source/audio/provenance, lifecycle, collaboration, migration, package, capability or canonical-document semantic was weakened to make a topology pass.

## 3. Current platform evidence — refreshed 2026-09-19

The runtime baseline is Godot **4.7.2 stable**. Current Godot documentation establishes the implementation facts used here:

- Web exports support HTTP, WebSocket clients and WebRTC, while low-level networking interfaces are unavailable in the browser target.
- `WebSocketPeer` can connect as a client in Web export, but accepting/listening via a raw WebSocket stream is not available in browser export.
- Godot WebRTC is built into web exports while native Godot needs the separately installed native WebRTC implementation/plugin.
- Inactive browser tabs can pause process callbacks; a sufficiently long pause can disconnect a networked game.
- Godot supports headless/dedicated-server execution.
- Web export uses the Compatibility/WebGL renderer path.

Primary anchors:

- Godot 4.7 web export: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html
- Godot 4.7 `WebSocketPeer`: https://docs.godotengine.org/en/4.7/classes/class_websocketpeer.html
- Godot 4.7 WebRTC: https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html
- Godot 4.7 dedicated servers: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html
- Godot 4.7.2 release artifacts: https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable

### Why the peer harness uses a relay

A browser-hosted Godot peer cannot simply listen as a raw WebSocket server. The harness therefore uses a small trusted `ws` relay to connect exported browser runtimes. The **browser Godot runtime remains simulation authority** in peer mode; the relay assigns transient connection identity, routes envelopes, injects deterministic delay/duplication, retains a confirmed checkpoint for reconnect/migration, and applies the topology policy for selecting a replacement peer after host loss.

That relay is test infrastructure, not a SplashMX semantic owner and not a selected public protocol. WebRTC remains a possible production adapter; its signalling/NAT/relay behavior and native-plugin asymmetry are deliberately not smuggled into canonical network semantics.

## 4. Canonical fixture and identity

The same canonical bytes exist at:

- `experiments/smx-017-network-harness/creation.json`
- `experiments/smx-017-network-harness/godot/creation.json`

The validator requires byte-for-byte equality. The exact SHA-256 is:

`dd5e7bb8b33ab447b4234fb8036453b248c5721e22b9f0e1c19cc57438e71580`

The immutable creation revision is `smx017-topology-equivalence-v1` and includes:

- Things: `world`, `avatar:alice`, `door`;
- Definition: `def:avatar`;
- Attachment: `beh:avatar-motion`;
- stable public port identities;
- topology-independent replicated-state/input/event/delivery/relevance declarations;
- one complete protected audio asset revision.

Canonical bytes contain no WebSocket/WebRTC/ENet/RPC/peer-ID/NodePath/ResourceUID identity. The exported runtime hashes the embedded fixture itself and refuses to start if it differs from the expected digest.

## 5. Harness architecture

```text
same canonical creation.json
            │
            ▼
 one Godot 4.7.2 harness runtime
 ├─ offline/local policy ───────────── no transport
 ├─ peer policy ── exported Web ─────┐
 └─ dedicated policy ─ Linux headless│ + exported Web client
                                     │
                    trusted transport-only relay
                    ├─ transient conn IDs
                    ├─ authenticated test principal binding
                    ├─ reorder/delay/duplicate pressure
                    ├─ confirmed checkpoint retention
                    └─ topology failure policy
                                     │
                         Playwright Chromium orchestrator
                         ├─ lifecycle observation/reconnect fault
                         ├─ host/server failure
                         ├─ semantic snapshot comparison
                         └─ evidence JSON
```

`godot/main.gd` is one trusted integration runtime for all three modes. The script is substrate/test code, **not** ordinary SplashMX user IR and not a public wire API. Its use of `WebSocketPeer` and browser-only `JavaScriptBridge` query parsing is therefore instrumentation, not a grant of these APIs to community content.

`model.py`/`test_model.py` provide a deterministic semantic oracle with 28 boundary tests. They catch contract regressions cheaply but do not substitute for the exported runtime/browser campaign.

## 6. Executed scenario

The runtime scenario follows SMX-010 section 14:

1. load the exact creation revision and report canonical digest + Thing/Definition/Attachment/Port IDs;
2. bind controller `alice` separately from containment and current simulation authority;
3. accept the same declared input sequence in every topology: move `+1`, move `+2`, open door, move `+1`;
4. reach authoritative semantic state `avatar_x=4`, `door_open=true`;
5. replicate latest state and a discrete reliable `door_opened` event;
6. make `door` `known_unloaded`, deliver state/event obligations, restore and flush them;
7. remove/re-add avatar relevance while keeping lifecycle active and coalesce latest state;
8. transfer controller `alice → bob → alice` while proving authority and containment remain unchanged;
9. measure the browser lifecycle path, then verify reconnect semantics after the actually observed natural or explicitly injected transport-loss trigger, preserving principal while assigning a new transient connection ID;
10. close a peer authority after a confirmed checkpoint, promote the surviving peer with an incremented authority epoch, then inject an old-epoch input and reject it;
11. separately close a peer authority with no confirmed checkpoint and fail explicitly rather than creating split-brain;
12. run the same creation with a dedicated Linux/headless authority and browser client, then terminate the server and verify fail-closed behavior with no client promotion;
13. compare normalized semantic snapshots from offline, peer and dedicated outcomes.

The comparison intentionally excludes transport IDs, current authority host, post-migration epoch, packet timing and presentation-only differences listed in section 10.

Two CI repairs are themselves useful adversarial findings about the harness boundary. First, reconnect observation must search the live record stream rather than a precomputed array slice. Second, the `no_checkpoint` destructive fixture must suppress relay-requested baselines as well as periodic/initial checkpoints; otherwise a test labelled “unconfirmed host loss” silently becomes confirmed. Both conditions now have executable integration coverage.

## 7. Adversarial and boundary pressure

The real runtime and deterministic oracle jointly pressure:

- duplicate and reordered input sequences;
- intentionally reordered authoritative state samples;
- duplicate application-level reliable event delivery;
- undeclared input kinds and state loci;
- non-controller input;
- client remote-state forgery against an authority;
- stale authority epochs;
- oversized ingress;
- nested forged capability-token/host-handle fields;
- unloaded/relevance queue semantics;
- reconnect with a changed transport identity;
- confirmed and unconfirmed peer-host loss;
- dedicated authority loss;
- protected revision equality across every topology.

The relay is allowed to make delivery inconvenient. It is not allowed to repair invalid application semantics by inventing a second state owner.

## 8. Browser lifecycle and reconnect

The harness measures browser lifecycle without pretending that every lifecycle primitive reproduces real background-tab networking policy:

1. it creates a second real Chromium page and checks the exported Godot page's actual `document.visibilityState` after backgrounding;
2. if Chromium reports the Godot page as genuinely hidden, it keeps it backgrounded through the destructive interval;
3. if headless Chromium does **not** expose ordinary background visibility semantics, it records `cdp-frozen-fallback` and applies Chromium's `Page.setWebLifecycleState` freeze primitive for the same interval;
4. after resume it checks whether the original transport actually disappeared and whether a natural reconnect occurred;
5. if the measured lifecycle path leaves the transport bound, that negative result is preserved and the relay then performs an explicitly labelled deterministic transport disconnect solely to exercise the accepted reconnect semantics;
6. whichever trigger caused transport loss, the Godot runtime must reconnect with the same durable principal and a different transient connection ID.

The passing 2026-09-19 campaign measured **Chromium 140.0.7339.16** with `document.visibilityState == "visible"` in headless mode, used the `cdp-frozen-fallback` for **2200 ms**, and observed **no natural transport timeout** despite the test application's **1400 ms** watchdog. Reconnect was therefore triggered explicitly by `deterministic-relay-fault-after-no-lifecycle-timeout`; the transient connection changed from `conn-2` to `conn-3` while principal `alice` remained durable.

This is intentionally a negative browser-lifecycle observation, not evidence that ordinary visible/background tabs can never disconnect and not evidence that CDP freeze is equivalent to Chrome/Firefox/Safari background policy. The harness records the distinction instead of fabricating a browser-caused disconnect. Cross-browser/mobile/OS policy remains O-027.

## 9. Peer versus dedicated trust

Topology-independent **object semantics** do not imply identical trust models.

- In peer-hosted mode, the current host can be simulation authority and therefore can cheat or bias its own process from another participant's fairness perspective. The relay does not make that host trusted.
- In dedicated-authoritative mode, clients submit input intent to a separately operated authority. Server loss fails closed; a browser client is not silently promoted.
- In both modes ordinary content still has the same capability boundary, network ingress is hostile, and current authority is runtime context rather than canonical identity.

This distinction is operational/security policy, not justification for a different Thing taxonomy.

## 10. Allowed divergences

SMX-017 permits and records only these topology/runtime differences without treating them as H-012 failure:

- transient transport/connection IDs;
- packet timing, packetization, delay and channel/adapter selection;
- current runtime authority host/principal;
- authority epoch after migration/failure;
- connect/disconnect/reconnect mechanics;
- derived prediction/interpolation caches and observed latency;
- headless presentation omission;
- deployment, relay/signalling and scaling policy.

Any additional canonical/object/accepted-input semantic divergence is a contract defect and must be recorded rather than normalized away by the harness.

## 11. Protected media

The fixture's `asset:click` is one indivisible revision containing:

- immutable digest;
- source identity and source metadata;
- audio/media semantic metadata;
- provenance;
- licence;
- derivation lineage.

Offline policy, browser export, Linux/headless export, replication, reconnect, checkpoint restore and authority migration may not replace the source revision with a decoded/transcoded runtime cache and may not field-mix competing revisions. CI compares the complete protected bundle in each semantic snapshot.

The passing real-runtime snapshots retained `asset:click` and its complete bundle unchanged under offline, peer, migrated-peer and dedicated execution.

## 12. Evidence and reproducibility

The heavyweight workflow is `.github/workflows/smx017-real-topologies.yml`.

Pinned inputs:

- Godot: `4.7.2`;
- build image: `barichello/godot-ci:4.7.2` (build/export tooling only);
- Node: `22.19.0`;
- Playwright: `1.55.0`;
- `ws`: `8.18.3`.

The workflow exports Web and Linux artefacts from the same Godot project, runs all 28 deterministic TN boundary tests, then executes the exported browser/headless topology campaign. It stores `artifacts/smx017-integration-results.json`, containing exact Godot/Chromium/Node versions, lifecycle mechanism and natural-timeout result, reconnect trigger, normalized semantic snapshots, authority migration evidence and diagnostic client-to-authority timing samples.

The first repaired passing evidence recorded:

- Godot `4.7.2.stable.official.ed1daf0bf`;
- Chromium `140.0.7339.16`;
- Node `v22.19.0`;
- `equivalent: true` for normalized offline, peer and dedicated semantic snapshots;
- peer authority epoch `1 → 2` after confirmed host migration;
- stale prior-epoch input rejection after migration;
- explicit `checkpoint_unconfirmed` behavior for the deliberately checkpoint-free peer-host loss fixture;
- dedicated authority loss with no promoted browser authority;
- complete protected asset bundle equality.

Timing samples are diagnostic observations from a local CI relay, not a WAN/performance benchmark. The harness reports latency only for accepted inputs with a causal prediction timestamp at or before the authority acceptance record; rejected duplicate predictions are not misreported as negative latency.

The ordinary repository CI also runs the oracle and structural validator so contract/doc/fixture drift cannot bypass the heavyweight test definition. Merge requires a green heavyweight workflow and normal repository CI on the final PR head, followed by the corresponding post-merge `main` checks.

## 13. Hypothesis effects

The passing exported-runtime campaign provides the following bounded evidence:

- **H-012 strengthened from model-level to real integration evidence.** One actual canonical creation and one Godot runtime execute offline, as a browser peer authority, and under a dedicated headless authority while retaining canonical/object/protected semantics and the same accepted-input outcome. Evidence remains bounded to the tested adapter/environment.
- **H-014 strengthened at real web/headless network-boundary level.** Godot target/runtime transport facilities remain private adapters while SplashMX keeps durable authority/identity/reconnect meaning above them. This does not prove all future platform services stay equally replaceable.
- **H-015 strengthened at real generic-runtime topology level.** The same exported generic harness project consumes the same creation semantics under browser/headless profiles rather than needing a topology-specific creation build. Startup/size/editor UX/performance remain SMX-019.

The measured headless lifecycle non-timeout neither weakens nor artificially strengthens these hypotheses; it constrains the browser-lifecycle evidence boundary. No SMX-017 evidence weakens H-013 or rewrites source/audio/provenance, migration, collaboration or capability contracts.

## 14. Residual limits — O-027

SMX-017 deliberately does not claim production readiness for:

- WAN/NAT/relay/signalling or TLS deployment;
- WebRTC versus WebSocket production adapter selection;
- packet MTU/fragmentation/congestion control and large-room scaling;
- production authentication/account/session service;
- hostile Internet relay/service operation;
- long-running persistent-world cluster leadership/failover;
- mobile browsers, Firefox/Safari lifecycle behavior, or OS suspend/resume;
- browser-tab policy differences beyond the measured Chromium path;
- production prediction/reconciliation presets;
- broad frame/startup/memory/network throughput performance.

Those remain O-027, primarily feeding SMX-019's browser vertical slice/performance work and final SMX-020 reconciliation. A green SMX-017 run means **the required topology semantics survived this real destructive integration slice**, not that networking is finished.
