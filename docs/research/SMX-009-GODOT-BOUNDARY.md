# SMX-009 — Godot substrate and browser/runtime boundary

Status: **research candidate / pre-Architecture-v1.0**  
Issue: SMX-009 / #9  
Evidence refresh: **2026-09-19**  
Godot baseline for current facts: **Godot 4.7.2 stable**, released 2026-08-18; 4.7 documentation branch. Godot 4.8-dev6 (2026-09-15) exists but is not used as the compatibility baseline.

This document answers one architectural question: **which semantics belong to SplashMX and which facilities may be delegated to Godot/platform adapters without making Godot the public compatibility contract?** It reconciles SMX-002 through SMX-008 and deliberately keeps engine objects, browser objects, transport handles, and host permissions below the canonical boundary.

The executable model and fixtures are disposable falsification tools. They do not freeze a Python API, a package encoding, a Godot scene layout, a renderer, an asset importer, or a network protocol.

## 1. Result in one sentence

Use Godot as a replaceable-enough **presentation/physics/input/audio/platform execution substrate** behind explicit SplashMX adapters; SplashMX continues to own Thing identity and state, object relationships, behaviour IR/scheduling semantics, canonical documents and migrations, capability policy, persistent-state meaning, streaming/dependency semantics, package/revision identity, source/audio/provenance semantics, and topology-independent networking declarations.

A SplashMX Thing is therefore **not a Godot Node**. A live Thing may have zero, one, or multiple private Godot bindings, and those bindings may be destroyed/recreated without changing Thing identity or durable state.

## 2. Authority chain carried forward

SMX-009 accepts and does not reopen these established candidate contracts:

- SMX-002: stable Thing identity, intrinsic state, optional facets, explicit ports/relationships; engine handles are transient context.
- SMX-003: containment is composition/locality, not control/authority/behavioural ownership; definitions/instances use stable semantic loci.
- SMX-004: bounded-turn behaviour IR and author-visible ordering are SplashMX semantics; host effects use named asynchronous capability-mediated services.
- SMX-005: canonical records, IDs, semantic transactions, references, assets, migrations, and compatibility envelopes are engine-independent.
- SMX-006: ordinary content receives no ambient GDScript/C#/GDExtension/JavaScriptBridge/eval/filesystem/raw-socket/PCK authority.
- SMX-007: snapshots exclude engine/network/capability handles and restore into a fresh runtime from semantic state.
- SMX-008: logical streaming identity is independent from physical chunks; exact artifacts are acquired/validated before atomic publication; migration capsules contain no host/peer/capability handles.

No existing source, audio, asset identity, provenance, licensing, or migration meaning is redefined by the adapter layer.

## 3. Current upstream facts — refreshed 2026-09-19

The following are current **platform facts**, not SplashMX public API contracts.

### 3.1 Version baseline

Godot's official release archive lists 4.7.2 as the current stable release (2026-08-18) and 4.8-dev6 as the current 4.8 development snapshot (2026-09-15). SMX-009 uses the stable 4.7 documentation branch for normative upstream observations.

Primary source: https://godotengine.org/download/archive/

### 3.2 Web rendering, threading, and export

Godot 4.7 web export requires WebAssembly and WebGL 2.0 and supports only the Compatibility rendering method; Forward+/Mobile are not supported on web and Godot 4.7 does not support WebGPU for those renderers. Since Godot 4.3, single-threaded web export is supported and is the preferred/default path; threaded exports require SharedArrayBuffer plus cross-origin isolation. C# Godot 4 projects still cannot export to web.

Primary source: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html

**Boundary consequence:** `render.compatibility`, thread availability, cross-origin isolation, and WebGL limitations are **target capabilities/policy**, never canonical Thing categories. SplashMX content may declare required semantic presentation capabilities, but not “must be a Godot Compatibility Node” or “must own a SharedArrayBuffer”.

### 3.3 Web audio is materially target-specific

Godot 4.7 documents Web Audio sample playback as the default web path. It offers low latency without thread support but currently omits AudioEffects, reverb/doppler, procedural audio, and has positional limitations; Godot stream playback restores more engine features with higher latency, particularly without threads.

Primary source: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#audio-playback

**Boundary consequence:** SplashMX owns audio asset identity, source/provenance metadata, author intent, buses/routing semantics eventually selected by the architecture, and graceful required/optional feature declarations. Godot supplies target playback/mixing implementation. A web projection may reject or approximate an unsupported **optional** effect without rewriting the source audio asset or its provenance; required unsupported semantics fail explicitly.

### 3.4 Browser persistence and lifecycle differ from native

Godot 4.7 web export persists `user://` through IndexedDB when browser policy permits; private/incognito usage can prevent persistence. The web editor stores projects in IndexedDB and cannot currently perform normal project export. Godot also documents browser suspension of processing in inactive tabs, which can break long-lived network sessions.

Primary sources:

- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#using-cookies-for-data-persistence
- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#background-processing
- https://docs.godotengine.org/en/4.7/tutorials/editor/using_the_web_editor.html

**Boundary consequence:** browser storage and page lifecycle are adapters beneath SMX-005/007 persistence and lifecycle semantics. “Save succeeded” cannot mean merely “Godot returned from a file call”; the adapter must report durability/availability status into SplashMX service semantics. Background-tab suspension is an external lifecycle/topology event for SMX-010/017, not an alternative clock definition.

### 3.5 Browser networking is a constrained subset

Godot 4.7 web export documents HTTP, WebSocket client, and WebRTC as supported while low-level networking is unavailable in browsers. WebRTC requires signalling/ICE/SDP coordination; WebSocket is available as a browser-compatible message transport. Godot high-level multiplayer APIs are useful implementation facilities but remain below SplashMX topology/authority/replication semantics.

Primary sources:

- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html#networking
- https://docs.godotengine.org/en/4.7/tutorials/networking/websocket.html
- https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html

**Boundary consequence:** SMX-010 must define authority, control, replication, relevance, reliability classes, reconnect, and topology independently. A transport adapter may select WebRTC/WebSocket/native ENet/etc.; it cannot mutate canonical Thing identity or silently change replication meaning.

### 3.6 Runtime resource loading is useful but not canonical identity

Godot 4.7 `ResourceLoader` exposes resource loading, dependency inspection, cache modes, and threaded loading. It remains filesystem/path/resource-oriented and requires imported resources for normal `load()` usage; runtime image/audio loading has format-specific routes.

Primary source: https://docs.godotengine.org/en/4.7/classes/class_resourceloader.html

**Boundary consequence:** use ResourceLoader/importers where useful **after** SMX-008 exact artifact acquisition/integrity/security validation. Godot resource paths, ResourceUIDs, cache entries, and imported-resource identities are private adapter data, not `AssetId`, `ThingId`, `DefinitionId`, package revision, or content provenance.

### 3.7 Headless/dedicated-server support is a good substrate fit

Godot 4.7 supports `--headless` and dedicated-server export. Dedicated-server export can strip visual resources or replace them with placeholders while preserving references needed by the Godot project.

Primary sources:

- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html
- https://docs.godotengine.org/en/4.7/tutorials/export/exporting_projects.html

**Boundary consequence:** this supports a headless adapter profile but does not define the SplashMX server package. SMX-014 owns creation/player/server artifact contracts. Required/optional semantic assets decide what a server package may omit; Godot's resource-strip list is an implementation optimization after that decision.

### 3.8 Hardened web builds can remove a dangerous bridge

Godot's current web compilation documentation states official/default web templates include JavaScriptBridge and a custom web template can be built with `javascript_eval=no`, removing that singleton. Threads can independently be disabled with `threads=no`.

Primary source: https://docs.godotengine.org/en/stable/engine_details/development/compiling/compiling_for_web.html

**Boundary consequence:** production SplashMX web players should prefer a hardened custom template that omits JavaScriptBridge/eval unless a trusted host shell explicitly requires a bridge. Even if a host build contains such a bridge, ordinary user IR cannot address it. Build-time removal is defence in depth beneath SMX-006 capability mediation, not the capability system itself.

## 4. Boundary map

| Facility | SplashMX owns | Godot supplies | Coupling / rule |
|---|---|---|---|
| Durable object identity | `ThingId`, definition/element/port/connection IDs, non-reuse/tombstone semantics | temporary Object/Node/RID/Resource handles | **Normative SplashMX boundary.** Never serialize or expose NodePath/RID/ResourceUID as identity. |
| Object state and relationships | intrinsic state, explicit containment/control/authority/observation/persistence/replication relations | private scene/node arrangement used to implement presentation/physics | Godot hierarchy may mirror a convenient projection but cannot become semantic ownership. |
| Behaviour | IR, turn ordering, transactions, continuations, budgets, service requests | scheduling hook/frame integration and adapter calls | GDScript/C# may implement trusted runtime internals; user content is not arbitrary engine script. |
| Rendering | semantic presentation properties/assets/features | 2D/3D renderer, canvas/viewport, shaders/material runtime | Renderer choice and Node types are target-private. |
| Audio | asset identity, source metadata, provenance/licensing, author-level audio intent and required/optional feature meaning | decode/playback/mixing/device backend | Web/native differences are capability negotiation, never destructive asset conversion. |
| Physics | author-facing body/query/material semantics once frozen | physics engine and collision solver implementation | Persist semantic state, not PhysicsServer RIDs. Engine-specific nondeterminism must be explicit. |
| Input | semantic actions/events and player/control relationships | keyboard/pointer/gamepad/touch/device polling | Device IDs/handles are transient context. Browser gesture restrictions surface as target policy. |
| Assets | stable `AssetId`, immutable digest descriptors, source/provenance/licensing, dependency graph | decoding/importing/GPU/audio objects/cache | Validate exact bytes before adapter publication. Godot imports are caches/derived artifacts. |
| Persistence | canonical project/save/world meaning, transactions, migrations, durability semantics | `user://`, FileAccess/storage adapters, IndexedDB-backed web storage | Adapter reports success/failure/durability; paths are not public references. |
| Streaming | logical residency, exact descriptors, acquisition state, migration | resource decoding and optional threaded loading | ResourceLoader does not replace SMX-008 resolver/security/atomic-publication semantics. |
| Security | principals, capability leases, validation, quotas, forbidden operations | hardened build, platform sandbox/permissions, process boundary | Both layers must pass. Host availability never grants user authority. |
| Networking | identity, authority/control distinction, replication declaration, relevance, event/state/input classes | WebSocket/WebRTC/ENet/UDP primitives and polling | Transport/topology adapter cannot redefine Thing/network semantics. |
| Web lifecycle | SMX lifecycle/clock semantics and reconnect policy | browser visibility/suspension, page storage, permission/gesture rules | Treat suspension/eviction as environmental events, never hidden semantic time. |
| Headless server | canonical creation/runtime state and server topology policy | headless process, dummy display/audio, resource stripping | Server projection can omit optional presentation while preserving canonical revision identity. |
| Publishing/versioning | package manifest, runtime/schema/IR negotiation, migrations, creation revision | exported generic runtime binaries/templates | Ordinary creations load as data + constrained logic; per-creation Godot build is not default. |

### Prominent two-column rule

**SplashMX owns:** identity, semantics, authoring contracts, canonical state, source/audio/provenance meaning, compatibility, security policy, package/revision identity, streaming meaning, network meaning.  
**Godot supplies:** rendering, audio/device backends, input polling, physics, low-level runtime facilities, resource decoding/import caches, web/native/headless process integrations, and transport implementations.

If a future implementation cannot move an item from one Godot object to another without changing its SplashMX durable identity, the adapter boundary is wrong.

## 5. Candidate invariants

- **GOD-001 — Thing identity is never a Godot identity.** `ThingId` is independent of Node instance IDs, NodePaths, RIDs, ResourceUIDs, scene paths, and object addresses.
- **GOD-002 — Binding cardinality is not object cardinality.** A Thing may have zero, one, or multiple private substrate bindings without splitting/merging the Thing.
- **GOD-003 — Binding lifetime is shorter than semantic lifetime.** Bindings may be replaced on reparent, renderer/device restart, stream-in, restore, or target migration without changing Thing identity/state.
- **GOD-004 — Generic runtime first.** Ordinary creation packages target a versioned generic SplashMX player; a per-creation Godot export is exceptional, not default publication semantics.
- **GOD-005 — Target projection cannot rewrite canonical meaning.** Web/native/headless adapters consume the same canonical revision; they may omit declared optional facilities or fail required unsupported features.
- **GOD-006 — Unsupported required features fail explicitly before activation.** No silent partial execution that changes creation meaning.
- **GOD-007 — Validate before binding.** Canonical schema/feature/security/dependency/digest checks complete before untrusted content obtains live substrate objects or services.
- **GOD-008 — Engine handles are transient context.** Snapshots, migration capsules, and authored documents exclude Nodes, RIDs, ResourceUIDs, peer IDs, OS permission objects, sockets, and JavaScript objects.
- **GOD-009 — Godot APIs are adapters, not public protocols.** Godot scene serialization, RPC annotations, Resource paths, and high-level multiplayer wire behaviour are replaceable implementation detail unless Architecture v1.0 explicitly promotes a narrowly justified dependency.
- **GOD-010 — Host availability does not imply capability.** A native/web build having filesystem/network/JavaScript/native-extension facilities does not make them addressable by ordinary content.
- **GOD-011 — Dangerous host bridges are reduced in the runtime build.** Hardened builds should remove unnecessary JavaScriptBridge/eval and exclude ordinary GDExtension/native-code/PCK execution paths while capability checks remain independently enforced.
- **GOD-012 — Exact asset integrity precedes decode/import.** Godot decoders/importers consume bytes selected by verified immutable descriptors; adapter cache identities cannot substitute for SplashMX `AssetId`/digest/provenance.
- **GOD-013 — Audio/source/provenance is preserved across target projection.** A target may change playback implementation or omit optional playback, never silently replace source identity, provenance, licence, or canonical audio reference.
- **GOD-014 — Derived/imported assets remain derived.** Godot import products, transcoded target assets, stripped server placeholders, and GPU/audio resources carry derivation links; they do not replace canonical source/provenance records.
- **GOD-015 — Headless is a projection, not a second creation model.** Headless execution uses the same Thing/IR/state/network contracts and may have zero presentation bindings.
- **GOD-016 — Restore recreates bindings after semantic state.** SMX-007 staged restore reconstructs canonical/runtime state first; Godot bindings are re-established from current target context afterward.
- **GOD-017 — Transport is policy beneath network semantics.** WebSocket/WebRTC/ENet/UDP selection must not change control, simulation authority, containment, replication declarations, or Thing identity.
- **GOD-018 — Browser limitations are explicit target capabilities.** Low-level sockets, tab suspension, persistence availability, gesture permissions, rendering/audio limits, and thread/isolation requirements surface as typed policy/capability outcomes.

## 6. Executable falsification slice

`experiments/smx-009-godot-boundary-model/` uses a tiny `GenericPlayer` and three coarse target profiles (`web`, `native`, `headless`). It intentionally creates fake private substrate bindings so tests can prove those bindings are not durable identity.

Machine-readable cases live in `docs/research/SMX-009-GODOT-BOUNDARY-FIXTURES.json`:

- **GB-001:** replace a live private binding; `ThingId` and semantic snapshot stay unchanged.
- **GB-002:** load exactly one canonical revision through web, native, and headless profiles; canonical digest is identical.
- **GB-003:** headless omits optional render/audio features without modifying the creation.
- **GB-004:** a required unsupported target feature fails closed before activation.
- **GB-005:** injected NodePath/RID/ResourceUID/peer/host-handle keys are rejected from canonical data.
- **GB-006:** user content requesting GDScript/GDExtension/JavaScriptBridge/raw host authority is denied even if the host could provide it.
- **GB-007:** digest-corrupted asset bytes fail before a runtime is published.
- **GB-008:** audio asset source and provenance metadata remain intact in a headless projection even though audio output is disabled.
- **GB-009:** semantic snapshot contains no private binding/host handles.
- **GB-010:** transport selection changes adapter state, not canonical network semantics.
- **GB-011:** web target rejects a required low-level networking assumption.
- **GB-012:** a Thing can have multiple private presentation/audio bindings while remaining one Thing.

These cover C-002/C-006/C-009/C-011/C-012/C-013/C-014/C-015/C-020/C-021/C-022/C-023/C-025/C-026 and A-001/A-002/A-003/A-009/A-010/A-012.

## 7. Generic-player feasibility conclusion

The model-level result is **positive but deliberately bounded**:

1. The same canonical package/revision can be accepted by multiple target adapters without embedding Godot identity or a per-target object schema.
2. Required/optional target features provide a clean failure/degradation point before runtime activation.
3. Exact assets and provenance can remain package-owned while target-private decoders/importers produce transient resources.
4. Headless execution naturally becomes a target projection with zero presentation bindings.
5. Network transport selection can remain independent of canonical authority/replication declarations.

This is enough for SMX-014 to design a generic player/package contract without assuming a per-creation Godot export. It is **not** proof that all future rendering/physics extensions can be runtime-loaded without a custom engine module, nor a measurement of production player startup size/latency. If a future component genuinely requires trusted engine-native code, it must be classified as a separate trusted runtime extension—not silently admitted as ordinary community content.

## 8. Performance observation and limit of evidence

A reproducible Python microbenchmark is included as `benchmark.py`. It creates private `ThingId -> ephemeral-binding` records and verifies lookup for 1k/10k/100k Things over seven rounds.

Observed in the research execution environment on 2026-09-19:

| Things | Median | Min | Max |
|---:|---:|---:|---:|
| 1,000 | 0.582 ms | 0.568 ms | 0.703 ms |
| 10,000 | 6.546 ms | 6.358 ms | 6.933 ms |
| 100,000 | 84.282 ms | 80.771 ms | 85.495 ms |

Environment: CPython 3.13.5, Linux 6.18.44 x86_64, glibc 2.41; processor identity was not reported by the container. Workload and timings are emitted by the benchmark itself.

**Interpretation:** explicit identity→binding indirection does not require super-linear bookkeeping in the disposable model. These numbers are **not Godot performance evidence**. They say nothing about Node creation, draw calls, physics, audio, GC/refcounting, browser/WASM overhead, or frame time. Real Godot object-fabric overhead must be measured in a later integration harness on named hardware/browser/builds; SMX-015/019 remain the correct gates for that claim.

## 9. Security mapping

SMX-006 remains authoritative. The Godot/platform layer adds defence in depth:

- Build ordinary web players without JavaScriptBridge/eval where practical (`javascript_eval=no`).
- Do not enable ordinary package execution through GDScript/C#/GDExtension/native libraries or arbitrary PCK/mod loading.
- Treat `ResourceLoader` and format decoders as post-validation adapter facilities; untrusted package structure/migrations are checked by SplashMX first.
- Keep OS/browser permissions independent from SplashMX grants: both must allow an operation.
- Never hand a capability service implementation object, Godot Object, browser JS object, socket, peer ID, filesystem path, or permission handle to user IR.
- Revalidate capability leases at service-use time; target migration/reload does not resurrect grants.

A hardened engine build reduces attack surface but **does not establish sandbox safety by itself**. SMX-016 remains the destructive adversarial proof gate.

## 10. Audio, source, asset, and provenance preservation

This boundary is intentionally conservative because target-specific asset pipelines are a common place for provenance loss.

1. `AssetId`, immutable source digest, logical source record, provenance/licensing metadata, and derivation relationships are SplashMX-owned.
2. Godot import products, runtime `Resource` objects, decoded AudioStreams/Textures, and server placeholders are target-private derivatives/cache entries.
3. A conversion/transcode must retain an explicit derivation edge to its source; it cannot overwrite source/provenance identity merely because the target prefers another encoding.
4. Headless/server packaging may omit optional audio/visual bytes, but canonical package/save state retains the same semantic asset references and provenance. A server-specific physical bundle is not a new canonical creation.
5. Web audio limitations are surfaced as target capability outcomes; they never justify replacing the source audio contract with “whatever AudioStreamPlayer supports”.

SMX-013/014 may add portable-package provenance/signature/remix fields, but must preserve this ownership direction.

## 11. Downstream contracts

### SMX-010 runtime multiplayer

May assume:

- transports are adapters below topology-independent authority/replication semantics;
- browser web target has HTTP/WebSocket-client/WebRTC but no low-level sockets;
- background-tab suspension is a required reconnect/failure test;
- Godot RPC/peer IDs cannot become canonical Thing/control/authority identity.

Must test WebRTC signalling/ICE, WebSocket fallback/policy, host migration/reconnect, and browser suspension rather than inferring equivalence from Godot's high-level multiplayer API.

### SMX-014 publishing/player/server

May assume a generic runtime can consume an engine-independent canonical package at model level. Must define manifest/runtime/schema/IR negotiation, physical asset selection, target feature negotiation, cache/offline behavior, and server bundle derivation. Ordinary publishing must not require authors to operate a Godot export toolchain.

### SMX-017 topology equivalence

Must run one canonical creation through offline/web peer-hosted/dedicated-authoritative target adapters and verify package semantic identity. It must treat browser suspension and WebRTC/WebSocket differences as topology/platform policy, not fork the creation model.

### SMX-019 browser vertical slice

Should use a prebuilt generic player/editor shell. It must expose target limitations in author language and keep Godot Node/SceneTree/Resource/RPC/build/export vocabulary out of the beginner flow. Browser persistence must be tested for actual availability, not assumed from a write call.

### SMX-015 destructive object-fabric harness

Should add a real-Godot binding adapter experiment and named-hardware object-count/frame-cost measurements. This is where model-level indirection must face real engine cost.

### SMX-016 adversarial sandbox

Must attempt host-bridge escape against the actual built player templates, including JavaScriptBridge presence/absence, malformed decoded resources, PCK/resource-loading paths, GDExtension/native extension attempts, and target-specific network ingress.

## 12. Hypothesis update

- **H-007 strengthened further.** Current Godot facilities are useful behind adapters but do not replace the engine-independent ID/document/migration requirements; the model rejects Godot identity leakage while loading the same package across targets.
- **H-009 strengthened further at the mapping layer, still not end-to-end.** Host facilities can remain below the capability boundary, and dangerous bridges can be omitted/denied. Real escape resistance remains SMX-016.
- **H-014 strengthened substantially at model/platform-boundary level.** Rendering/audio/input/physics/resource/network facilities can be mapped as replaceable implementation services without making Nodes/RIDs/ResourceUIDs/transport handles public semantics. Real production performance remains unproven.
- **H-015 strengthened at model/package-loading level.** One canonical revision loads through generic target profiles, including headless; current web/runtime facts do not require per-creation Godot builds for ordinary constrained content. Startup/performance/publishing UX remains SMX-014/019.
- **H-018 strengthened further.** Persisted/migrated state excludes engine handles, target projections preserve revision identity, and derived target resources remain below the compatibility boundary. Actual future cross-Godot-version migration remains unproven until destructive/integration testing.

No other hypothesis changes status in SMX-009.

## 13. Rejected mappings

### Node-is-Thing

Rejected. It couples durable identity/lifecycle to scene-tree/runtime object lifetime and cannot naturally represent headless zero-binding Things or multiple presentation bindings.

### Godot scene/resource serialization as the canonical format

Rejected as the public contract. It would contradict SMX-005 path-independent typed records/migrations/partial loading and expose engine format/version behavior as content compatibility semantics.

### Godot high-level multiplayer/RPC as SplashMX network semantics

Rejected as public semantics. Useful adapter implementation, but browser/native transports, authority models, reconnect, and future engine changes must not require document rewrites.

### PCK/mod/GDExtension as ordinary portable component mechanism

Rejected for untrusted content. These routes cross the SMX-006 host-code boundary. SMX-013 components must package canonical definitions/IR/assets/capability requests instead.

### Web editor as the production authoring architecture

Rejected. Godot documents the web editor as preliminary, missing export/debug/GDExtension/C# support, and tied to IndexedDB storage. SplashMX may borrow substrate pieces but needs its own browser-facing authoring shell/contract.

## 14. Residual risks and explicit non-claims

- No actual Godot 4.7.2 binary/browser was available in this research execution environment, so the executable evidence is **model-level**, backed by current primary documentation. Real binding/frame/startup measurements remain open.
- Godot web documentation changes over time. Recheck the 4.7/stable facts before SMX-017/019 measurements and whenever the runtime baseline moves to 4.8+.
- Renderer/physics/audio semantic mismatches may eventually require a narrower public baseline than Godot's full feature set. The adapter boundary makes such narrowing explicit rather than silently target-dependent.
- Browser storage eviction, private mode, autoplay/gesture policy, background suspension, WebRTC NAT/relay conditions, and cross-origin isolation are environmental realities that generic-player UX must handle.
- A hardened custom Godot build has maintenance cost. Architecture v1.0 should freeze the *security requirement* and adapter contract, not a permanent fork strategy unless SMX-016 evidence justifies it.
- Native engine plugins may be valuable for trusted platform features. They are a deployment/runtime concern and must not become installable ordinary component authority by accident.

## 15. Acceptance check

- [x] Current Godot/web facts refreshed against primary sources with date and 4.7.2/4.7 context.
- [x] Concrete `SplashMX owns` versus `Godot supplies` responsibility boundary recorded.
- [x] Public identity/schema/IR explicitly excludes NodePath/RID/ResourceUID and executable fixture rejects leaks.
- [x] Generic same-package web/native/headless model exercised with required/optional feature negotiation.
- [x] Browser/native/headless differences documented, including rendering, audio, persistence, background lifecycle, networking, and headless resource projection.
- [x] Security-sensitive host bridges mapped to SMX-006 and hostile capability fixtures added.
- [x] Reproducible mapping-bookkeeping microbenchmark records environment/workload and is correctly scoped as non-Godot evidence.
- [x] Source/audio/provenance meaning is explicitly preserved across target projection and derived resources.
- [x] H-007/H-009/H-014/H-015/H-018 and downstream SMX-010/014/015/016/017/019 handoffs reconciled.
- [x] Machine-readable fixtures, adversarial/boundary tests, validator, and CI integration are defined.

Architecture v1.0 must continue to treat these as evidence-backed candidate boundaries, not as proof that every future Godot feature is portable or that the sandbox is escape-proof.
