# SMX-016 — Adversarial sandbox and malformed-content harness

Status: destructive pre-architecture security evidence; **not** an end-to-end sandbox certification

Issue: SMX-016 / #16

Established: 2026-09-19

This issue attacks the accepted SMX-004/005/006/008/009/010/013/014/015 boundaries instead of repeating broad threat discovery. The executable harness is intentionally hostile and deterministic. It asks whether malformed packages, canonical records, dependencies, IR, migrations, capabilities, network messages and target-private host surfaces can cross a boundary or consume unbounded work **before** ordinary execution.

The result is positive at the semantic/model boundary with four concrete enforcement clarifications, but it does not claim that Python fixtures prove a real Godot/browser/native process secure. Decoder vulnerabilities, production archive and signature libraries, browser permission/runtime behavior, process/origin isolation and production quota calibration remain residual work.

## Contents

| Section | Summary |
|---|---|
| 1. Result | Records what the attack campaign did and did not establish. |
| 2. Security invariants | Defines `ADV-001`–`ADV-028`. |
| 3. Attack matrix | Maps required attack classes to deterministic regressions. |
| 4. Corrective findings | Reconciles four boundary ambiguities with the accepted contracts. |
| 5. Target boundary | Separates semantic denial from web/native/headless TCB hardening. |
| 6. Resource containment | Records deterministic counters and fail-before-work ordering. |
| 7. Protected media | Preserves source/audio/provenance as an atomic revision bundle. |
| 8. Counterevidence and residual risk | States what remains unproven. |
| 9. Hypothesis effects | Updates H-006/H-009/H-011/H-014/H-015. |
| 10. Downstream handoff | Defines what SMX-017/018/019/020 may assume. |
| 11. Reproduction | Gives fixture/test commands and scope. |
| 12. Refreshed primary sources | Records current Godot security-sensitive facts. |

## 1. Result

The harness contains **38 deterministic adversarial/boundary tests** covering all attack classes required by #16. The tested model fails closed before host invocation or migration where the input is unauthorized, malformed, substituted, over budget or target-incompatible.

Observed properties:

- package paths are normalized and collision-checked **before extraction**;
- archive work is bounded before expansion, and ordinary packages reject symlink/special/nested-archive entries in the candidate harness;
- canonical input is bounded recursively and rejects capability/host/engine/session authority fields at any depth;
- package activation consumes one exact `PackageId + revision + digest + byte-size` lock and rejects substitution before migration;
- dependency traversal is bounded and rejects cycles/missing nodes;
- raw JavaScript/Godot/PCK/GDExtension/process/filesystem/socket APIs are outside the ordinary-content service vocabulary on every target;
- parent containment and package provenance/signature do not grant child authority;
- capability delegation is scope/lifetime narrowing, depth/count bounded and cycle-safe;
- revocation is rechecked immediately before a staged host service actually crosses the adapter;
- instruction, allocation, emitted-work, timer, queue and service-request amplification have deterministic counters rather than wall-clock thresholds;
- malformed/over-budget/exact-lock-invalid input is rejected before migration, and migration has no host-service operation;
- network ingress recursively rejects authority/host tokens and independently validates authenticated sender, world/room, authority epoch, size/tree/rate/queue budgets;
- web/native/headless have different physical TCB surfaces, but ordinary-content semantic authority does not expand when a target exposes a lower-level host API;
- asset decode metadata is bounded before the decoder boundary;
- `AssetId` replacement remains an all-or-nothing protected revision bundle.

No attack in the modeled ordinary-content path reached `HostRecorder` after a denial. The tests deliberately record host-call and decoder-call counts to distinguish “raised an error eventually” from “blocked before the privileged/unsafe boundary”.

The harness is non-normative. Production code must preserve these invariants with real parsers, transports, runtime adapters and sandboxing.

## 2. Security invariants

- **ADV-001 — canonical package paths are host-independent:** reject traversal, absolute/drive/device paths, control characters and native filename ambiguities before extraction.
- **ADV-002 — archive namespace collisions/special entries fail closed:** Unicode normalization/case collisions, symlink/special entries and nested archives are rejected by the ordinary-package candidate.
- **ADV-003 — package expansion is pre-budgeted:** entry count, compressed bytes, expanded bytes, single-entry size and expansion ratio are checked before expansion/allocation.
- **ADV-004 — canonical logical IDs are unique:** duplicate durable record IDs fail before migration/execution.
- **ADV-005 — canonical structured input is recursively bounded:** depth, nodes, collection items, strings and record count have independent ceilings.
- **ADV-006 — canonical data cannot serialize ambient authority:** live grants, host/native/browser/Godot handles, peer IDs, sockets and authority tokens are rejected recursively.
- **ADV-007 — runtime/package acquisition is exact:** `PackageId`, immutable revision, digest and byte size must all match the resolved lock before later stages.
- **ADV-008 — dependency discovery is bounded and acyclic:** missing nodes, cycles, depth, package count and aggregate declared bytes are typed failures.
- **ADV-009 — raw host APIs are not capabilities:** ordinary content cannot invoke JavaScriptBridge/eval, GDScript, PCK/ResourceLoader execution, GDExtension, process/shell, raw filesystem or raw sockets.
- **ADV-010 — authenticity is not authority:** signature/publisher/provenance information never creates a capability grant.
- **ADV-011 — containment is not privilege inheritance:** service authorization uses the originating principal unless an explicit trusted proxy validates and intentionally changes principal.
- **ADV-012 — delegation narrows and is bounded:** delegated scope/lifetime cannot widen; chain depth and total grant count are enforced before grant allocation.
- **ADV-013 — grant ancestry is cycle-safe and revocable:** corrupt/cyclic ancestry is invalid, and revocation/expiry of any ancestor makes descendants non-live.
- **ADV-014 — service admission is resource bounded:** per-principal request budgets apply independently of whether the capability itself is granted.
- **ADV-015 — capability is checked at use time:** a staged service request is re-authorized immediately before host invocation, so mid-flight revocation fails before the adapter crosses the boundary.
- **ADV-016 — IR work is metered structurally:** instructions/repetition, events, timers and service requests consume non-bypassable counters.
- **ADV-017 — IR allocation amplification is bounded:** authored allocation/cell growth consumes a separate budget rather than being hidden inside instruction cost.
- **ADV-018 — emitted/timer work cannot grow an unbounded queue:** emit, timer and queue ceilings fail the activation deterministically.
- **ADV-019 — migration is after validation, capability-free and bounded:** exact acquisition/dependency/canonical checks precede migration; migration cost/output/chain have ceilings and no host-service instruction.
- **ADV-020 — network messages cannot mint local authority:** forbidden authority/host/package-loader/code fields are rejected recursively.
- **ADV-021 — network sender scope is authenticated context:** payload claims cannot override the authenticated principal, room or world.
- **ADV-022 — runtime authority is epoch-scoped:** stale/forged authority epochs fail rather than becoming current after reorder/replay.
- **ADV-023 — network ingress is independently resource bounded:** byte/tree/depth/rate/queue limits apply below semantic delivery.
- **ADV-024 — target substrate exposure does not grant content authority:** the same raw-host deny rule applies to web/native/headless even if the host binary contains the API.
- **ADV-025 — defence-in-depth differences remain explicit:** hardened web can omit JavaScriptBridge/eval; stock web/native/headless have different TCB surfaces and must not be described as equivalent isolation.
- **ADV-026 — protected media revisions are indivisible:** stable `AssetId` points to one complete digest/source/audio-or-media/provenance/licence/derivation revision; partial or field-mixed replacement fails atomically.
- **ADV-027 — decoder input is preflighted:** digest, compressed/decoded bytes, image pixels and audio frames are bounded before invoking the target decoder.
- **ADV-028 — model success is not sandbox certification:** process/origin isolation, production parsers/crypto, decoder vulnerabilities and calibrated quotas remain explicit residual risks.

## 3. Attack matrix

Companion machine-readable manifest: `docs/research/SMX-016-SECURITY-FIXTURES.json`.

| Fixture | Attack | Expected boundary | Observation |
|---|---|---|---|
| AT-001 | NFC/case-equivalent archive names | B1 package parser | collision rejected before extraction |
| AT-002 | ZIP-slip, absolute, drive/device, trailing dot/space | B1 | rejected before host path resolution |
| AT-003 | symlink/special/nested archive | B1 | rejected by ordinary package profile |
| AT-004 | zero-byte/ratio/count/byte amplification | B1 | deterministic resource fault before expansion |
| AT-005 | duplicate IDs / unknown required feature | B2 canonical validator | fail closed before migration |
| AT-006 | deep/wide/long canonical values | B2 | node/depth/string/record ceilings |
| AT-007 | nested grant/handle/RID/peer token | B2 | recursively rejected |
| AT-008 | revision/digest/size/package substitution | acquisition | exact lock mismatch before migration |
| AT-009 | dependency cycle/depth/count/bytes | resolver/acquisition | bounded typed failure |
| AT-010 | raw JS/Godot/PCK/native/process/fs/socket | B4/B5 | denied; host call count remains zero |
| AT-011 | “signed therefore privileged” | capability broker | no ambient grant exists |
| AT-012 | child uses parent grant | capability broker | origin principal denied |
| AT-013 | widened/deep delegation | broker | rejected before new grant allocation |
| AT-014 | forged cyclic grant ancestry | broker policy store | non-live without recursive blow-up |
| AT-015 | revoke after stage, before host use | B4 | second check denies; host call count zero |
| AT-016 | service flood | B4 | per-principal deterministic limit |
| AT-017 | confused-deputy proxy input | application proxy | unvalidated target rejected |
| AT-018 | recursive instruction/allocation amplification | B3 IR | instruction/allocation budgets |
| AT-019 | event/timer/queue storm and unknown opcode | B3 | emitted/timer/queue bounds; unknown op fails |
| AT-020 | malformed exact lock/dependency before migration | B1/B2→migration ordering | migration call count remains zero |
| AT-021 | migration service/cost/output abuse | migration | host operation absent; work/output bounded |
| AT-022 | nested remote grant injection | B6 network ingress | recursively rejected |
| AT-023 | forged sender/world/room/epoch | B6 | authenticated context/epoch checks |
| AT-024 | network bytes/tree/rate/queue amplification | B6 | independent deterministic limits |
| AT-025 | weaker target host surface | B4/B5 | exposure recorded, ordinary semantic denial unchanged |
| AT-026 | partial protected-media revision | asset transaction | replacement rejected; old bundle unchanged |
| AT-027 | huge pre-decode media dimensions | decoder ingress | rejected before decoder call |
| AT-028 | residual-risk assertion | evidence boundary | no absolute sandbox claim |

## 4. Corrective findings

SMX-016 found **four implementation/enforcement ambiguities** in the earlier positive security proof surface. None required weakening a constitution invariant or protected media semantics. The accepted direction was already deny-by-default; the repairs make the boundary executable and less assumption-dependent.

### R-016-01 — path normalization is a canonical security step

SMX-006 required normalization-collision rejection but did not make Unicode/case/native-device collapse explicit enough. The hostile harness therefore defines the ordinary archive namespace as collision-rejected after separator normalization + NFC + case folding, and rejects Windows device/trailing-dot/space ambiguities even when the current host is not Windows.

This does **not** make package semantic IDs case-insensitive. It prevents two archive names from mapping to the same or ambiguous host filename during target-specific extraction.

### R-016-02 — authority-token rejection is recursive

A top-level reserved-key check is insufficient because hostile content can nest `capability_grant`, host handles, peer IDs or code-loader requests under otherwise legitimate payload fields.

The security contract is refined: B2/B6 forbidden authority/host fields are rejected recursively within bounded structured input. Protocol-specific application fields remain allowlisted separately.

### R-016-03 — delegation bounds are pre-allocation enforcement

SMX-006 stated delegation depth/count must be bounded, but the positive proof model did not exercise a deep chain or corrupt ancestry. The hostile harness makes this observable:

- depth and total grant count are checked before allocation;
- ancestry traversal detects cycles/missing parents;
- corrupt ancestry is non-live and cannot authorize;
- source expiry/revocation still invalidates descendants.

### R-016-04 — revocation is checked immediately before host use

Checking a grant when a service request is staged is not enough if user/host policy changes before execution. The gateway now models both admission-time and **use-time** authorization. Revocation between those points prevents the host call.

This is a clarification of SEC-005/B4, not a new ambient-rights mechanism.

## 5. Target boundary

SMX-016 keeps two layers separate:

1. **semantic authority boundary** — ordinary content only sees named SplashMX services and can never name raw JavaScript/Godot/native APIs as a capability;
2. **physical TCB / defence in depth** — a runtime build may physically contain more dangerous APIs even though the semantic boundary denies them.

The disposable target profiles record:

| Target | Physical lower-level surface modeled | Ordinary-content result |
|---|---|---|
| `web_hardened` | JavaScriptBridge/eval omitted | raw host API denied |
| `web_official` | JavaScriptBridge/eval may exist in engine template | raw host API denied |
| `native` | process/filesystem/GDExtension facilities exist in trusted host | raw host API denied |
| `headless` | process/filesystem facilities may exist; presentation services absent | raw host API denied |

Therefore “works on all targets” does **not** mean “all targets provide identical isolation”. The hardened web build removes a class of bridge from the TCB. Native and headless still require platform sandbox/process/container policy appropriate to deployment. SMX-019 must exercise a real browser build; production server hardening remains an implementation concern beyond this Python model.

## 6. Resource containment

The harness intentionally avoids wall-clock thresholds. Every attack uses deterministic semantic counters:

- archive entry/compressed/expanded/single-entry/ratio;
- canonical tree depth/node/string/collection/record count;
- dependency depth/count/aggregate declared bytes;
- grant count/delegation depth;
- behaviour instruction/allocation/emitted/timer/queue/service request;
- migration chain/cost/output records;
- network encoded bytes/tree depth/nodes/messages-per-tick/queued messages;
- media compressed/decoded bytes, image pixels and audio frames.

The numeric defaults in `model.py` are **test values, not production policy**. The durable result is that the categories are independently enforceable and checked before their corresponding expensive/privileged work.

Ordering matters as much as the limit:

```text
archive/path bounds
    -> exact artifact lock
    -> dependency closure bounds
    -> canonical structural/security validation
    -> bounded capability-free migration
    -> current capability policy
    -> activation
```

A digest/dependency/canonical failure leaves the migration probe untouched. A raw host denial or mid-flight revocation leaves the host-call recorder untouched. An over-size media descriptor leaves the decoder recorder untouched.

## 7. Protected media

SMX-016 carries forward D-031/D-058/D-067/D-071/D-075 and SMX-013/014/015 without modification.

A stable `AssetId` selects exactly one complete immutable revision bundle:

- content digest;
- source identity;
- source metadata;
- audio/media semantics;
- provenance;
- licence expression;
- derivation lineage.

Security validation, package resolution, migration, network transport, target projection, decode caches and hostile recovery are **not allowed to field-mix these values across revisions**.

AT-026 attempts an incomplete replacement and verifies the old revision remains unchanged. AT-027 verifies decoder preflight operates on a descriptor without replacing canonical source/audio/provenance meaning. Target decoder/GPU/audio objects remain derived/private cache state.

## 8. Counterevidence and residual risk

Passing this harness is evidence for the **semantic boundary**, not proof of production sandbox resistance. The remaining real-runtime and decoder assurance gap is tracked as **O-025**.

Unresolved risks intentionally remain:

- real Godot/browser/native process/origin isolation and host integration mistakes;
- vulnerabilities in image/audio/font/mesh/video decoders after bounded input crosses the decoder;
- production ZIP/archive library handling of Unicode, symlinks, special files and platform path rules;
- production signature verification, key rotation/revocation and repository compromise;
- browser permission, lifecycle, background suspension and gesture behavior across engines;
- actual memory accounting for engine/GPU/audio resources rather than research “allocation units”;
- choosing safe production quota values without creating denial-of-service against legitimate creations;
- cryptographic network authentication/anti-replay details beyond the SMX-010 semantic epoch/principal model;
- trusted enterprise/native extension modes, which remain a separate trust domain and must never be serialized as ordinary package authority.

A future real implementation that exposes an escape, bypasses a budget, or reaches the host before validation must amend the authoritative boundary and gain a regression. It cannot be dismissed because this model passes.

## 9. Hypothesis effects

### H-006 — built-ins, visual rules and future text can target one constrained IR

**Strengthened at hostile model level.** Unknown/raw-host opcodes fail closed and recursive instruction, allocation, emitted-work, timer, queue and service-request amplification can be independently budgeted without introducing a privileged second execution path. Compiler completeness and real-runtime accounting remain later implementation work.

### H-009 — capability security can bound untrusted components

**Strengthened substantially, still not certified end-to-end.** The campaign directly exercises no ambient authority, principal attribution, narrowed/depth-bounded delegation, corrupt ancestry, live revocation, raw-host denial, recursive authority-token rejection and target-independent semantic mediation. Real Godot/browser/native escape resistance, decoder safety and process/origin hardening remain unresolved.

### H-011 — streaming can be object-centric rather than scene-centric

**Strengthened narrowly at hostile acquisition boundary.** Exact immutable package descriptors and bounded acyclic dependency closure reject substitution/confusion before migration/activation without requiring scene/PCK execution semantics. This adds security evidence, not streaming performance evidence.

### H-014 — Godot can remain a replaceable-enough substrate boundary

**Strengthened at semantic enforcement boundary; physical isolation remains target-specific.** The same raw-host deny rule holds even when a target profile physically exposes JavaScriptBridge/GDExtension/process/filesystem capabilities to trusted host code. The result depends on adapters never leaking those handles; real target integration remains SMX-019 evidence.

### H-015 — generic players are preferable to per-creation builds

**Strengthened from hostile-boundary centralization.** A versioned generic player is a coherent place to perform exact-lock, parser, migration, capability, target and decoder preflight before activation. This is a security architecture advantage, not evidence for browser startup/size/performance.

No other H-status changes are justified by SMX-016.

## 10. Downstream handoff

### SMX-017 — network topology equivalence

Must consume ADV-020–ADV-025. Real peer-hosted browser and dedicated-authoritative tests must not bypass recursive ingress validation, authenticated principal/world/room checks, authority epoch invalidation, or bounded queues merely because a transport is authenticated.

### SMX-018 — collaboration harness

Collaboration transport remains a separate consistency/security boundary. Canonical edit messages still cannot carry live grants, host handles, runtime peer authority tokens or raw package-loader/code authority. Stale permissions must be revalidated as already required by SMX-011.

### SMX-019 — browser vertical slice

Must exercise the real generic web runtime with the ordinary-content host surface closed. At minimum:

- record whether the build is hardened with JavaScriptBridge/eval omitted;
- prove ordinary content cannot reach JavaScriptBridge/DOM/eval regardless;
- exercise real parser/package limits and browser storage/network service mediation;
- exercise permission denial/revocation without leaking a host object;
- measure real memory/startup/frame/storage costs without converting this research model’s test quotas into product values;
- retain exact `AssetId` source/audio/provenance semantics across browser decode/cache paths.

### SMX-020 — Architecture v1.0

May treat ADV-001–ADV-027 as **security requirements supported by deterministic destructive-model evidence**, while keeping ADV-028 and the residual-risk list explicit. Architecture v1.0 must not use the word “sandboxed” as an absolute production assurance unless later real-runtime evidence justifies it.

## 11. Reproduction

Artifacts:

- `docs/research/SMX-016-SECURITY-FIXTURES.json`
- `docs/research/SMX-016-DECISION-EVIDENCE.md`
- `experiments/smx-016-security-harness/model.py`
- `experiments/smx-016-security-harness/test_harness.py`
- `experiments/smx-016-security-harness/README.md`

Commands:

```text
python tools/validate_smx016.py
python -m unittest discover -s experiments/smx-016-security-harness -p 'test_*.py'
python tools/validate_smx006.py
python -m unittest discover -s experiments/smx-006-security-model -p 'test_*.py'
python tools/validate_smx013.py
python -m unittest discover -s experiments/smx-013-package-model -p 'test_*.py'
python tools/validate_smx015.py
python -m unittest discover -s experiments/smx-015-object-fabric-harness -p 'test_*.py'
```

The repository CI runs the complete historical suite as well, so security corrections cannot silently regress the Object Fabric/package/publishing contracts.

## 12. Refreshed primary sources

Checked **2026-09-19**.

Godot’s official release archive still lists **4.7.2-stable (18 August 2026)** as the current stable Godot 4 release and **4.8-dev6 (15 September 2026)** as the newest development snapshot. The stable baseline therefore has not changed since SMX-009/014.

- https://godotengine.org/download/archive/

Current Godot web-compilation documentation still states that JavaScriptBridge is built into official/default web templates and can be omitted from a custom web build with `javascript_eval=no`. This remains defence in depth; ordinary user IR must not reach the bridge even when a host build contains it.

- https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

Current Godot PCK/mod documentation still warns that loading PCK content can become a security vulnerability when malicious code is supplied or a pack is replaced. SplashMX therefore continues to reject executable Godot PCK/mod semantics for ordinary community content.

- https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html

GDExtension remains native shared-library execution and stays outside ordinary package authority.

- https://docs.godotengine.org/en/latest/engine_details/engine_api/gdextension/what_is_gdextension.html
