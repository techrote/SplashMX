# SMX-006 — Threat model and capability-based sandbox boundaries

Status: candidate pre-architecture security contract for adversarial falsification

Issue: SMX-006 / #6

Established: 2026-09-17

This document defines the current candidate security model for running **untrusted SplashMX creations and reusable components** above the SMX-004 bounded-turn executor and SMX-005 canonical document contract. It deliberately does **not** claim that SplashMX is sandboxed end-to-end yet. SMX-016 owns the later hostile-package/adversarial proof campaign.

The selected direction is **deny-by-default authority with explicit scoped capability leases, per-principal mediation, independent parser/executor/service/network boundaries, and hard resource ceilings**. A package signature may prove provenance, but it never grants ambient authority.

## Contents

| Section | Summary |
|---|---|
| 1. Security result | States the candidate trust model and invariants. |
| 2. Assets and threat actors | Defines what is hostile and what needs protection. |
| 3. Trust boundaries | Separates package parser, canonical validator/migrator, IR executor, runtime services, engine host, and network. |
| 4. Capability model | Defines grants, scopes, delegation, revocation, and principals. |
| 5. Capability vocabulary | Classifies safe operations, mediated services, optional capabilities, and forbidden ambient powers. |
| 6. Nested components | Prevents transitive privilege and confused-deputy behaviour. |
| 7. Runtime-service mediation | Defines service-call checks, correlation, cancellation, and revocation. |
| 8. Resource-exhaustion model | Carries SMX-004 budgets outward to packages, parsers, migrations, assets, queues, and services. |
| 9. Package/document parsing | Defines malformed-input and decompression/path/duplicate limits. |
| 10. Network boundary | Treats peers/messages as hostile and forbids remote authority injection. |
| 11. Godot boundary | Maps current Godot security-sensitive facilities into allow/forbid decisions. |
| 12. Browser permission boundary | Maps browser powerful-feature permissions into SplashMX capabilities without conflating them. |
| 13. Signed/trusted content | Defines what provenance may and may not change. |
| 14. User-visible permission semantics | Defines permission prompts, persistence, inspection, and revocation requirements. |
| 15. Corpus and executable evidence | Maps ST fixtures to the baseline corpus. |
| 16. Architecture scorecard | Records evidence-backed scores and N/E areas. |
| 17. SMX-016 adversarial plan | Defines concrete later attack campaigns. |
| 18. Downstream handoffs | Defines what later issues may assume. |
| 19. Hypothesis status | Updates H-006/H-009/H-014/H-015. |
| 20. Refreshed primary sources | Records current Godot/web facts used here. |

## 1. Security result

The current candidate is:

```text
Untrusted package/component/network input
        |
        v
bounded parser + canonical validator/migrator
        |
        v
validated authored records + validated bounded-turn IR
        |
        v
principal-scoped executor
        |
        +---- safe local semantics ------------------------+
        |                                                 |
        +---- explicit service request --------------------+
                    |
                    v
        capability broker / policy
                    |
          grant? scope? live? quota?
               /            \
             no              yes
             |                |
          deny/fault      named host service
                              |
                     OS/browser/Godot substrate
```

No ordinary creation/component receives an object reference that means “the engine”, “the browser”, “the filesystem”, “the OS”, or “the network”. User code can only express validated IR operations. Effects outside the deterministic object fabric cross named runtime services, and each request is evaluated against the **calling principal's live capability set and scope**.

### Security invariants

- **SEC-001 — no ambient authority:** ordinary authored content has no implicit filesystem, HTTP/socket, clipboard, sensor, browser-JS, native-code, engine-reflection, process, or unrestricted resource-loading authority.
- **SEC-002 — authority belongs to principals, not containment:** a parent/group/component possessing a capability does not make it ambient to descendants.
- **SEC-003 — grants are scoped leases:** every grant names capability, principal, scope, lifetime/revocation state, and whether further delegation is permitted.
- **SEC-004 — delegation is monotonic narrowing:** a principal may delegate only authority it currently holds, and delegated scope must be a subset/intersection of the source grant.
- **SEC-005 — revocation is live:** revocation invalidates future service checks and descendant delegated leases; revocation-sensitive active resources must terminate or enter an explicit revoked state.
- **SEC-006 — signatures prove origin, not privilege:** signed/trusted provenance never grants host authority by itself.
- **SEC-007 — parser, executor, services, and network are separate boundaries:** compromise/failure assumptions cannot collapse them into one “browser/WASM sandbox”.
- **SEC-008 — hard limits exist before allocation/work:** package size/count/depth, expansion ratio, migration steps, IR cost, queues, timers, service rates, response sizes, and dependency depth have non-bypassable limits.
- **SEC-009 — capability names are stable semantic contracts:** platform-specific APIs are adapters behind SplashMX services, not public creation semantics.
- **SEC-010 — capability denial is explicit and inspectable:** required capabilities fail attachment/start according to product policy; optional capabilities can select declared reduced behaviour.
- **SEC-011 — cross-principal deputying is explicit:** a service call is authorized as the originating principal, not whichever ancestor/coordinator happens to perform the call.
- **SEC-012 — remote peers cannot grant local host authority:** network payloads can carry application data/authority defined by multiplayer semantics, never capability leases for local host APIs.
- **SEC-013 — untrusted packages cannot cause engine-native code loading:** ordinary content may not introduce GDScript execution, GDExtension/native libraries, arbitrary WebAssembly host modules, or executable Godot PCK/mod semantics.
- **SEC-014 — migrations are non-privileged:** canonical migrations remain deterministic/bounded/capability-free by default; a format migration cannot become a host-service escape hatch.
- **SEC-015 — unrecognized required semantics fail closed:** unknown required feature/capability/record/IR constructs stop load before execution.
- **SEC-016 — ordinary sandbox and trusted deployment modes are distinct:** any future privileged deployment escape hatch is outside the ordinary community-content contract and must be visibly isolated.
- **SEC-017 — user/host policy can be stricter than package requests:** declaration never implies grant.
- **SEC-018 — browser/OS permission is necessary but not sufficient:** SplashMX checks its own capability before invoking the platform permission/API layer.

## 2. Assets and threat actors

### Protected assets

SplashMX must protect:

- local project documents and unpublished assets;
- user save/world data;
- filesystem and operating-system resources;
- browser storage/origin data;
- clipboard contents;
- microphone/camera streams;
- geolocation and device sensors;
- network credentials/session identifiers;
- multiplayer rooms and authoritative server state;
- CPU/GPU/memory/battery/network bandwidth;
- other packages/components loaded in the same runtime;
- editor/runtime integrity;
- package provenance/signing keys;
- user privacy and permission expectations.

### Threat actors / hostile inputs

Treat as hostile:

1. downloaded creation packages;
2. community components nested inside otherwise trusted projects;
3. canonical documents containing malformed records/IDs/references;
4. behaviour IR designed for CPU/memory/event amplification;
5. compressed archives/assets designed for decompression bombs;
6. migration payloads designed for algorithmic/resource abuse;
7. dependency graphs designed for cycles/depth/fanout abuse;
8. network peers/messages designed to forge identity/authority or exhaust queues;
9. packages attempting capability laundering through parent components;
10. compromised signed packages or authentic-but-malicious publishers;
11. local tampering with downloaded package files;
12. assets whose decoders exercise vulnerable engine/image/audio/font parsers.

A package being “valid” or “signed” therefore does not make its semantic behaviour trusted.

## 3. Trust boundaries

### B1 — package/container parser

Responsibilities:

- archive/container bounds;
- path normalization;
- file/entry count;
- compressed and expanded byte ceilings;
- expansion-ratio ceiling;
- duplicate normalized path rejection;
- symlink/special-file policy;
- hash/integrity verification;
- bounded manifest parsing.

It must not execute scripts/migrations during raw extraction.

### B2 — canonical document validator/migrator

Responsibilities:

- record-kind envelope validation;
- duplicate ID/key rejection;
- graph/reference validation;
- required-feature negotiation;
- bounded deterministic migration;
- semantic transaction validation;
- typed asset/blob metadata.

Migration receives no runtime-service capability by default.

### B3 — behaviour IR validator/executor

Responsibilities inherited from SMX-004:

- finite known opcode/intrinsic set;
- instruction/cost budgets;
- bounded iteration/allocation;
- no direct foreign-state mutation;
- no ambient host instruction;
- explicit async service requests;
- transactional activation commit/rollback;
- causal-chain/event/timer limits.

### B4 — capability broker/runtime services

This is the only ordinary path from user behaviour to privileged host facilities.

Every request carries at minimum:

- originating principal ID;
- service/capability name;
- requested operation;
- requested scope target;
- correlation/continuation identity;
- budget/quota accounting context.

The broker checks live grant, scope, revocation, rate/resource policy, and platform availability immediately before invoking the service.

### B5 — engine/platform host

Godot/browser/OS facilities are trusted computing base, but they are not exposed wholesale to content.

SplashMX adapters convert safe semantic requests into:

- renderer/audio/physics operations that do not require capabilities;
- platform “powerful feature” APIs where applicable;
- restricted file/storage/network services;
- user-mediated browser/OS actions.

### B6 — network ingress

All remote data is untrusted even when transport encryption/authentication succeeds.

Networking must validate:

- sender/session identity;
- message schema/version;
- authority/relevance policy;
- message/field size;
- rate and queue quotas;
- reference validity;
- no capability-grant records;
- no arbitrary canonical edit unless an explicit collaboration/runtime protocol permits it.

## 4. Capability model

### 4.1 Principal

A **principal** is the security identity to which a capability is granted.

Candidate principal granularity:

- whole creation/package root;
- reusable component instance;
- behaviour attachment when finer isolation is required;
- runtime/system principal for trusted built-ins.

The authoring hierarchy is not a security principal hierarchy by implication.

### 4.2 Grant / lease

Candidate semantic record:

```text
CapabilityGrant
  grant_id
  principal_id
  capability_name
  scope
  issuer_policy_id
  delegable: bool
  expires_at / session lifetime / persistent policy token
  revoked: bool
  parent_grant_id?    # only for delegated grants
```

Exact encoding belongs later.

### 4.3 Scope

Capabilities should be as narrow as product UX can reasonably express.

Examples:

```text
network.http:
  origins: [https://api.example.com]
  methods: [GET]
  path_prefixes: [/public/]
  max_response_bytes: 1048576

storage.save:
  namespace: current_creation
  max_bytes: 10 MiB

clipboard.write:
  mime_types: [text/plain]

media.camera:
  facing: user
  max_resolution: 1280x720

multiplayer.room:
  room_id: active_room
  actions: [send_application_message]
```

A scope is not an arbitrary user-program predicate. It is a typed structure validated by the host.

### 4.4 Delegation

Delegation rules:

1. caller must hold a live grant;
2. source grant must be marked delegable;
3. requested capability name must match;
4. delegated scope must be equal to or narrower than source scope;
5. delegated lifetime cannot exceed source lifetime;
6. revoking/expiring source invalidates descendants;
7. delegation depth/count is bounded;
8. further delegation requires the delegated grant itself to permit it;
9. package structure/containment never creates delegation implicitly.

### 4.5 Revocation

Revocation semantics are service-specific but must be explicit.

Examples:

- future HTTP requests: fail immediately;
- pending HTTP request: cancellation attempted; result after revocation is discarded or surfaced as revoked according to service contract;
- active microphone/camera stream: stop tracks/adapter and emit revoked status;
- clipboard: next operation denied;
- storage lease: further writes denied, existing saved data remains according to storage policy.

The browser/OS may independently revoke permission; the adapter must translate that into SplashMX capability/service failure even if the product grant record has not yet changed.

## 5. Capability vocabulary

This vocabulary is provisional; names are semantic categories, not browser API strings.

### 5.1 Safe default operations — no host capability

Subject to normal execution/resource limits:

- read/write own public state through allowed SMX semantics;
- read/write own attachment-private state;
- deterministic expressions/random/logical time;
- send commands/events and read values through declared connections;
- local transforms/layout/animation/timeline state;
- renderer/audio playback using already-authorized packaged assets;
- deterministic local physics/game logic;
- instantiate authored components already present/validated in the package, subject to count/memory limits;
- query declared capability availability as a boolean/state;
- local diagnostics explicitly exposed as non-sensitive.

These operations do not imply host access.

### 5.2 Mediated runtime services / optional capabilities

Candidate capabilities:

| Capability | Typical scope |
|---|---|
| `storage.save` | current creation namespace, byte quota |
| `storage.project` | editor-only project namespace, read/write mode |
| `file.open_user_selected` | user-picked handles only |
| `file.save_user_selected` | user-picked destination only |
| `network.http` | origin/method/path/response-byte allowlist |
| `multiplayer.session` | active room/session operations |
| `clipboard.read` | MIME types, foreground/user-gesture rules |
| `clipboard.write` | MIME types, user-gesture/policy rules |
| `media.camera` | device class/resolution/frame-rate scope |
| `media.microphone` | device class/sample-rate/channel scope |
| `geolocation.read` | precision/update-rate/lifetime scope |
| `notifications.show` | current creation, rate/content rules |
| `ui.fullscreen` | user-gesture + current surface |
| `ui.pointer_lock` | user-gesture + current surface |
| `external_url.open` | allowed schemes/domains, user mediation |
| `device.midi` | future explicit capability; absent by default |
| `device.serial` / `device.usb` | future expert capability; absent by default |

Networking for core multiplayer may ultimately use a distinct host-owned service rather than exposing `network.http`; ordinary components should not need raw transport access.

### 5.3 Permanently forbidden for ordinary user content

Ordinary community content must not receive:

- arbitrary GDScript/C#/engine scripting evaluation;
- `JavaScriptBridge` / browser `eval` / arbitrary DOM JS execution;
- GDExtension/native shared-library loading;
- OS process/shell execution;
- arbitrary dynamic library loading;
- unrestricted filesystem paths;
- unrestricted raw sockets/listeners;
- unrestricted local-network discovery;
- direct access to secrets/cookies/browser credential stores;
- direct Godot Object/SceneTree/RID reflection;
- arbitrary `ResourceLoader` or PCK/mod loading that can introduce executable Godot resources/scripts;
- arbitrary shader/native compute code without a future separately validated restricted shader contract;
- ability to disable runtime hard limits;
- ability to mint or mutate capability grants.

## 6. Nested components and confused deputy prevention

### 6.1 No transitive ambient privilege

Example:

```text
Game principal:
  network.http api.example.com

  └─ WeatherWidget principal:
       no network.http grant
```

The widget cannot cause the Game principal to perform arbitrary HTTP merely because it is contained by the Game.

### 6.2 Explicit delegated service facade

If the parent intentionally offers a safe service:

```text
WeatherWidget -> parent public command "request_weather"
Game -> validated fixed-origin weather service
Game -> event "weather_result"
```

That is application semantics, not capability inheritance. The parent implementation must validate the child's request according to the public interface contract.

Alternatively, the host may delegate a narrowed `network.http` grant explicitly.

### 6.3 Principal attribution

The runtime must retain causal origin across:

- command/event chains;
- service requests;
- continuations;
- nested component callbacks.

A service call triggered by child content is authorized as the child unless an explicit trusted proxy contract deliberately changes the principal and validates the input.

### 6.4 Capability laundering guards

Reject:

- child-supplied “grant objects”;
- serialization of live grant handles into canonical authored documents;
- copying another principal's grant ID;
- capability escalation through component import;
- “signed component therefore trusted” shortcuts.

## 7. Runtime-service mediation

A service adapter has a declared capability requirement and scope validator.

Candidate sequence:

```text
behaviour turn
  -> stage service_request(name, args)
  -> internal state commit
  -> scheduler emits request
  -> broker resolves originating principal
  -> broker checks live grant + scope + quota
  -> adapter invokes browser/OS/Godot host API
  -> bounded result/error
  -> ordered external activation back into behaviour
```

Rules:

- service invocation never occurs before the originating activation commits;
- service results have maximum byte/object/depth limits;
- service adapters do not return raw engine/browser/native objects to user IR;
- opaque handles are capability-scoped and type-checked if handles are needed;
- handles cannot be serialized as durable canonical authority;
- revocation invalidates handle use;
- service correlation IDs are not authority tokens.

## 8. Resource-exhaustion model

SMX-004 already requires execution budgets. SMX-006 extends limits across the full input pipeline.

### Package/container

Hard limits should include:

- compressed package bytes;
- total expanded bytes;
- maximum expansion ratio;
- entry count;
- maximum single entry size;
- maximum path length;
- no absolute/parent-traversal normalized paths;
- no special device files;
- symlink policy: reject ordinary community packages unless a compelling safe use appears.

### Canonical document

- record count;
- per-record byte size;
- nesting depth;
- string length;
- map/list element count;
- reference count/fanout;
- duplicate keys/IDs rejected;
- extension-record byte/count budget;
- chunk count;
- tombstone/catalog count;
- transaction operation count.

### Migration

- migration chain length;
- per-step work/cost units;
- input/output expansion ratio;
- output record count;
- no host service access;
- no network/filesystem access;
- deterministic memory/time ceilings.

### Dependencies

- maximum dependency depth;
- total package count;
- total transitive expanded bytes;
- duplicate/cycle handling;
- fetch count/rate;
- provenance/feature compatibility validation before activation.

### Executor/runtime

Inherited + extended:

- instructions/cost per activation;
- emitted work per activation;
- activations/cost per tick;
- continuation/timer count;
- queue depth;
- private-state bytes;
- instantiated Thing/component count;
- service requests per principal/time window;
- service response bytes;
- network ingress bytes/messages per peer/time window.

### Assets/decoders

Before passing bytes to engine/browser decoders:

- MIME/type allowlist;
- compressed and decoded-size bounds;
- image dimensions/pixel count;
- audio/video duration/bitrate/frame-dimension limits where knowable;
- font/shader/mesh complexity limits;
- digest validation.

Decoder vulnerabilities remain residual risk in the TCB and motivate process/origin isolation where practical.

## 9. Package/document parsing

### 9.1 Extraction rules

Reject normalized paths containing:

- `..` traversal;
- absolute paths;
- drive/device prefixes;
- NUL/control ambiguities;
- normalization collisions.

Do not “extract then validate” into sensitive host paths. Prefer streaming/virtual package access or extraction into an isolated runtime cache.

### 9.2 Canonical document rules

Carry forward SMX-005:

- duplicate IDs/keys fail;
- required unknown feature fails closed;
- optional opaque extension payload is preserved only under a bounded declared extension envelope;
- record kinds require typed envelopes;
- content digests are verified before use;
- catalog/chunk placement is not authority;
- unloaded targets remain typed unresolved references, not load-time code hooks.

### 9.3 Migration rules

A migration runs:

1. on already parse-bounded input;
2. in a deterministic restricted migration interpreter/function set;
3. with explicit source/target schema pair;
4. under work/output limits;
5. into a staging document;
6. followed by full target validation;
7. committed only after success.

A migration cannot request `network.http`, filesystem, clipboard, camera, browser JS, or other runtime capabilities.

## 10. Network boundary

Network peers are not package principals and cannot grant host capabilities.

Inbound runtime messages must be checked for:

- protocol/message kind;
- schema/version;
- sender identity and room membership;
- target Thing/port eligibility;
- authority/relevance rules from SMX-010;
- maximum payload depth/size/count;
- replay/sequence policy where relevant;
- per-peer/per-room rate/queue budget.

Explicitly forbidden over ordinary runtime network channels:

- capability grant/revocation records;
- host service handles/tokens;
- raw canonical package loader commands;
- engine object IDs;
- arbitrary script/IR definitions unless a later hot-code distribution protocol is separately authenticated/validated/capability-gated.

Collaboration transport in SMX-011/018 may carry canonical edit operations, but that remains a distinct consistency/security boundary.

## 11. Godot boundary — refreshed 2026-09-17

### 11.1 JavaScriptBridge / eval

Godot current web compilation documentation states official/default web templates include the JavaScriptBridge singleton and that builds can omit it with:

```text
javascript_eval=no
```

**Current direction:** ordinary SplashMX web players should evaluate a custom hardened template with JavaScriptBridge omitted if the product does not require it. Editor/host code needing browser integration should keep that integration outside user IR and expose only narrow runtime services.

Primary source:
https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### 11.2 GDExtension

Godot describes GDExtension as loading native shared libraries at runtime.

**Decision:** ordinary SplashMX packages/components cannot contain or activate GDExtension/native libraries. Trusted platform extensions, if any, are installed/compiled by the SplashMX host distribution and are not user-package capabilities.

Primary source:
https://docs.godotengine.org/en/latest/engine_details/engine_api/gdextension/what_is_gdextension.html

### 11.3 PCK/ZIP/mod loading

Godot's current PCK documentation states resource packs may contain scripts/scenes/shaders and explicitly warns about malicious-code risks from untrusted/replaced packs.

**Decision:** untrusted SplashMX packages are **not** loaded as executable Godot mod/PCK projects. SplashMX may use ZIP-like containers or Godot I/O internally, but content is parsed through the SplashMX schema/IR boundary and safe asset adapters.

Primary source:
https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html

### 11.4 Godot engine APIs

Godot nodes/resources/RIDs/SceneTree are implementation substrate. User IR receives no direct engine object references. Built-in adapters may use them internally.

### 11.5 Custom hardened runtime

A custom runtime appears justified for at least web security hardening because Godot exposes a build-time mechanism to omit JavaScriptBridge/eval. SMX-009/016 should measure maintenance/performance implications before requiring a custom build for every target.

This issue does **not** claim that a custom Godot build alone creates the SplashMX sandbox.

## 12. Browser permission boundary — refreshed 2026-09-17

The W3C Permissions specification models sensitive “powerful features” as user-agent permission states such as `granted`, `denied`, and `prompt`; permissions can expire/revoke, and many powerful features are also controlled by Permissions Policy.

Primary source:
https://www.w3.org/TR/permissions/

Permissions Policy can independently disable a feature even before user permission can be requested.

Primary source:
https://www.w3.org/TR/permissions-policy/

### Camera/microphone

Media Capture and Streams defines camera/microphone access as user-mediated powerful features and integrates with policy-controlled `camera`/`microphone`.

Primary source:
https://www.w3.org/TR/mediacapture-streams/

### Geolocation

The 2026 Geolocation Recommendation requires express user permission for location access.

Primary source:
https://www.w3.org/TR/2026/REC-geolocation-20260324/

### Clipboard

Current Clipboard API drafts integrate clipboard access with the permissions model; actual user-gesture/browser behaviour varies and must remain an adapter concern.

Primary source:
https://www.w3.org/TR/clipboard-apis/

### Notifications

The WHATWG Notifications standard requests permission via the `notifications` powerful feature.

Primary source:
https://notifications.spec.whatwg.org/

### Consequence for SplashMX

There are two distinct decisions:

1. **SplashMX grant:** is this creation/component allowed by product/user policy to request this semantic capability?
2. **platform grant:** will this browser/OS allow the specific API operation now?

Both must allow the operation. A browser permission grant must never automatically create a SplashMX grant, and a SplashMX grant cannot override browser denial/revocation.

## 13. Signed/trusted content

### Ordinary signed package

Signature may establish:

- publisher identity/provenance;
- package integrity;
- version/update lineage.

It does **not** automatically grant:

- filesystem;
- network;
- clipboard;
- camera/microphone;
- JS/native code;
- more CPU/memory;
- capability-delegation rights.

### Curated marketplace component

A curated/reviewed component may receive:

- reputation/UI badges;
- easier permission explanation;
- known publisher/update channel.

It still runs inside ordinary capability/budget rules.

### Privileged deployment extension

A future enterprise/local-developer/trusted-host mode may install native extensions or custom services. That is a **different trust domain** and must not be serializable into ordinary community packages or silently activate when a package moves to another host.

## 14. User-visible permission semantics

Product UX principles:

- show capabilities before first privileged use where practical;
- distinguish package-level request from nested component request;
- identify which component is asking and why;
- show scope in human terms (“Connect to api.example.com”, not “Network”);
- distinguish required vs optional;
- allow deny while preserving reduced functionality when declared;
- expose currently granted capabilities in project/player inspection UI;
- allow revoke;
- avoid repeated prompts by using host-managed leases where appropriate;
- never auto-grant solely because author marked capability “required”;
- show publisher/signature separately from permission choice;
- permission UI must not imply that a signed publisher makes the request safe.

Browser/OS prompts may still appear after SplashMX approval; UX should make that layering understandable.

## 15. Corpus and executable evidence

Companion manifest: `docs/research/SMX-006-SECURITY-FIXTURES.json`.

Direct executable coverage:

| Fixture | Cases | Observation |
|---|---|---|
| ST-001 | C-022/A-003 | Unprivileged principal cannot invoke HTTP; no ancestor/host ambient grant is consulted. |
| ST-002 | C-022 | HTTP scope restricts origin, method, path, and response-byte ceiling. |
| ST-003 | C-011/A-003 | Nested component receives no parent capability unless explicitly delegated. |
| ST-004 | A-003 | Delegation cannot widen scope/lifetime or use a non-delegable grant. |
| ST-005 | A-003 | Source-grant revocation invalidates descendant delegated leases. |
| ST-006 | C-022 | Optional denied capability can take explicit reduced path; required denial fails closed. |
| ST-007 | A-012 | Package parser rejects traversal, duplicate normalized paths, entry/size/expansion-ratio abuse. |
| ST-008 | A-012 | Dependency depth and migration-chain/work/output ceilings reject amplification. |
| ST-009 | C-026 | Package signature/provenance changes authenticity metadata only, never capability set. |
| ST-010 | A-015 | Network payload cannot introduce capability grants/host handles and is size/rate bounded. |
| ST-011 | A-004 | Per-principal service request quota prevents service-spam amplification. |
| ST-012 | A-012 | Unknown required service/capability semantics fail before execution. |

### Not proven here

- resistance to real Godot/browser/native sandbox escape;
- real decoder vulnerabilities;
- real ZIP implementation traversal/symlink corner cases;
- process/origin isolation;
- production cryptographic signature verification;
- precise performance-safe quota values;
- network protocol authentication/anti-replay;
- browser permission UX across engines;
- platform-specific native OS permission adapters.

These are deliberately handed to SMX-009/010/016/019 as appropriate.

## 16. Architecture scorecard

Candidate: deny-by-default principal capability model + bounded parser/executor/service/network boundaries

| Score | Assessment |
|---|---|
| S-01: 2 | Ordinary no-capability workflows remain simple; permission UX not user-tested. |
| S-02: 3 | Capability semantics compose with Thing/behaviour/document models without new object taxonomy. |
| S-03: 3 | Containment explicitly does not grant authority. |
| S-04: 3 | Security identity uses stable principals/IDs rather than hierarchy/engine refs. |
| S-05: 3 | Component capabilities are explicit, scoped, delegable only by rule, and revocable. |
| S-06: N/E | Full lifecycle persistence/revocation across save/restore belongs SMX-007. |
| S-07: N/E | Streamed capability leases/handles belong SMX-008. |
| S-08: 3 | Deny-default host boundary, parser limits, grants/scopes/delegation/revocation, and test fixtures are explicit. |
| S-09: 2 | Network boundary rejects host authority injection; full multiplayer security is SMX-010/017. |
| S-10: N/E | Collaboration authorization remains SMX-011/018. |
| S-11: 2 | Capability names and migrations are semantic/versioned; long-term compatibility unproven. |
| S-12: 3 | Ordinary content contract excludes Godot/JS/native APIs. |
| S-13: 3 | Deterministic fixtures exercise capability/limit invariants. |
| S-14: N/E | Production performance overhead not benchmarked. |
| S-15: 3 | Denial/revocation/quota/parser/network failures are fail-closed and explicit in candidate model. |
| S-16: 2 | Required/optional permission model supports progressive disclosure; UX remains later work. |

Hard-gate failures observed in SMX-006 scope: **none in the model**. End-to-end sandbox proof remains outstanding.

## 17. SMX-016 adversarial campaign

SMX-016 must not merely rerun these unit fixtures. It should attack real candidate implementations across at least these families.

### Package/container attacks

- ZIP-slip/path normalization variants;
- absolute/drive/device paths;
- duplicate normalized names;
- symlink/hardlink/special-file attempts;
- compressed bombs and nested archives;
- malformed UTF-8/Unicode normalization edge cases;
- huge file/entry counts;
- digest mismatch/substitution;
- manifest points outside package.

### Canonical parser/migration attacks

- duplicate IDs/keys;
- deeply nested extension records;
- huge strings/list/map fanout;
- cyclic reference/dependency graphs;
- unknown required features;
- malformed typed references;
- migration expansion bombs;
- migration chain cycles;
- migration attempts to invoke host services;
- transaction precondition race/confusion.

### IR/executor attacks

- infinite/bounded-loop edge cases;
- event/command feedback storms;
- timer/continuation floods;
- service-request floods;
- private-state/allocation amplification;
- crafted cost-model undercharging;
- hot-swap continuation corruption;
- correlation-ID collision/replay.

### Capability attacks

- forged grant IDs;
- copied handles between principals;
- nested child attempts parent-authority use;
- widened delegated scopes;
- delegation cycles/depth abuse;
- use-after-revoke;
- optional/required confusion;
- signed-package privilege assumption;
- confused-deputy requests via public ports;
- capability serialization into save/canonical data.

### Host/platform attacks

- user content attempts `JavaScriptBridge`/eval;
- arbitrary PCK/ResourceLoader script load;
- GDExtension/native library import;
- URL scheme abuse;
- clipboard/camera/mic/geolocation request without product grant;
- browser permission revoked mid-session;
- native path/UNC/device-name abuse;
- service adapter returning raw host object/oversized payload.

### Network attacks

- forged sender/authority;
- malformed/oversized messages;
- rate floods;
- replay/out-of-order abuse;
- remote capability-grant injection;
- network message causing arbitrary package load;
- cross-room/cross-world reference confusion.

### Required result

Each attack must record:

- exact fixture/payload;
- expected boundary;
- observed boundary;
- whether host API was reached;
- resource usage;
- failure mode;
- regression test if fixed.

## 18. Downstream handoffs

### SMX-007 lifecycle

Must define:

- whether capability grants persist across save/restore (default recommendation: product/user policy store, not authored/save-state authority token);
- what happens to active privileged resources on suspend/unload;
- continuation/service requests across revocation/restore;
- no serialization of live host handles.

### SMX-008 streaming

Must preserve principal identity and scoped grant association across stream-out/in without embedding ambient host handles in object chunks.

### SMX-009 Godot mapping

Must measure feasibility/maintenance of custom web template with `javascript_eval=no` and ensure user content cannot reach native engine loaders/reflection.

### SMX-010 multiplayer

Must define authenticated runtime authority separately from host capabilities. Remote authority can decide game-state ownership but cannot grant camera/filesystem/network-host capabilities.

### SMX-011 collaboration

Must define edit authorization separately from runtime capability authority.

### SMX-013 component ecosystem

Component manifests should declare requested capabilities and required/optional status; install/import cannot auto-grant.

### SMX-014 packaging

Package manifest must carry capability requests, feature requirements, signatures/provenance, and resource declarations without embedding live grants.

### SMX-016 adversarial harness

Execute the attack plan above against real loader/executor/runtime boundaries.

## 19. Hypothesis status

### H-006 — one constrained IR

**Strengthened indirectly.** The SMX-004 IR provides a finite service boundary where capabilities can be enforced without introducing a second execution engine. Actual hostile IR testing remains SMX-016.

### H-009 — capability security can bound untrusted components

**Strengthened substantially at model level, still unresolved end-to-end.** Explicit principals, narrowed delegation, revocation, no ambient authority, parser/service/network separation, and deterministic denial tests form a coherent security model. Real host/runtime escape resistance is not yet proven.

### H-014 — Godot can remain a replaceable-enough substrate boundary

**Strengthened narrowly.** Current Godot facilities can be kept behind adapters; JavaScriptBridge can be omitted in custom web builds and untrusted PCK/GDExtension paths can be excluded from ordinary content. Production mapping/performance remains SMX-009/019.

### H-015 — generic players preferable to per-creation builds

**Strengthened narrowly from security architecture.** A generic player centralizes validation, capability mediation, and hardening; this is a security advantage, but browser/native performance/publishing evidence remains SMX-014/019.

## 20. Refreshed primary sources — checked 2026-09-17

### Godot web hardening

Godot current `latest` compilation documentation states JavaScriptBridge is built into default/official web templates and can be omitted using `javascript_eval=no`.

https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### Godot untrusted packs

Godot current PCK/ZIP documentation states packs may contain scripts/scenes/shaders and explicitly identifies malicious/replaced PCKs as security vulnerabilities.

https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html

### Godot native extensions

Godot describes GDExtension as runtime interaction with native shared libraries.

https://docs.godotengine.org/en/latest/engine_details/engine_api/gdextension/what_is_gdextension.html

### W3C Permissions

The Permissions API defines user-mediated powerful-feature permission state, revocation/lifetime concepts, and interaction with Permissions Policy.

https://www.w3.org/TR/permissions/

### Permissions Policy

Permissions Policy provides developer/host-level selective enable/disable of browser features independent of user permission.

https://www.w3.org/TR/permissions-policy/

### Camera/microphone

https://www.w3.org/TR/mediacapture-streams/

### Geolocation — 2026 Recommendation

https://www.w3.org/TR/2026/REC-geolocation-20260324/

### Clipboard

https://www.w3.org/TR/clipboard-apis/

### Notifications

https://notifications.spec.whatwg.org/

These sources are evidence about the host platform. They are not the SplashMX public capability contract.

## SMX-016 hostile-proof reconciliation — 2026-09-19

SMX-016 executed the hostile attack plan above and keeps SEC-001–SEC-018 intact. The campaign found four enforcement ambiguities that are now part of the authoritative interpretation of this contract:

- **R-016-01 — host-independent archive normalization:** path validation occurs before extraction; separator normalization plus Unicode NFC and collision rejection must prevent Unicode/case/native-device/trailing-dot-space aliases from resolving ambiguously on a target filesystem. This does not change the case semantics of SplashMX logical IDs.
- **R-016-02 — recursive authority-field rejection:** canonical and network structured input must reject forbidden live capability, host/native/browser/Godot handle, peer/session authority, raw loader and code-authority fields **recursively** inside the bounded payload, not only in a top-level envelope.
- **R-016-03 — delegation bounds are pre-allocation:** delegation depth and total grant count are checked before adding a child grant; ancestry traversal is cycle-safe, and missing/cyclic/corrupt ancestry is non-live. Scope/lifetime monotonic narrowing and ancestor revocation/expiry remain mandatory.
- **R-016-04 — use-time reauthorization:** admission-time service authorization is insufficient for asynchronous staged requests. The broker rechecks the originating principal's live grant, scope and relevant policy **immediately before host invocation**, so revoke/expiry/policy change after staging fails closed before the adapter crosses the host boundary.

The hostile harness also confirms the required ordering: exact package lock, bounded dependency closure and bounded canonical/security validation all precede capability-free migration and activation. Resource limits remain independent deterministic semantic counters; specific numerical quotas are implementation policy and require real target calibration.

Target hardening is defence in depth, not an authority model. Ordinary user content has the same raw-host denial on web/native/headless even if trusted host code physically contains JavaScriptBridge, GDExtension, process or filesystem facilities. A hardened web template may remove JavaScriptBridge/eval from the TCB; native/headless still require separate OS/process/container hardening.

Protected source/audio/provenance semantics remain unchanged: stable `AssetId` selects one indivisible immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. Security failure, package resolution, migration, network transport, target projection and decode caches may not field-mix revisions.

The residual real-runtime/decoder assurance gap is tracked as **O-021**: a deterministic Python harness does not prove Godot/browser/native process/origin escape resistance, production archive/crypto correctness, third-party decoder safety, cross-browser permission/lifecycle behavior, or calibrated production quotas. SMX-019 owns the real browser/generic-player evidence; Architecture v1.0 must retain this residual risk unless later evidence closes it.
