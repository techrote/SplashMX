# SMX-026 — Common behaviour IR, Rule compiler, deterministic scheduler and budgets

**Status:** production implementation  
**Issue:** #51 / SMX-026  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md` section 4  
**Research evidence:** `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md`, `docs/research/SMX-016-SECURITY-FIXTURES.json`  
**Canonical identity dependency:** `src/splashmx/canonical/core.py` / SMX-023

SMX-026 implements the first production execution boundary shared by beginner Rules and advanced Behaviours. It does not change Architecture v1.0. It deliberately stops before capability grant policy/host invocation, behaviour hot replacement, durable lifecycle restore, target-specific Godot scheduling, or arbitrary scripting.

## Contents

| Section | Summary |
|---|---|
| 1. Production contract | Defines the common IR and what this module owns. |
| 2. Rule compiler and advanced Behaviour parity | Shows both authoring levels reach exactly one IR/executor. |
| 3. Activation and ordering semantics | Defines deterministic queue order and commit-before-effects. |
| 4. State, randomness and pending work | Defines runtime/public/private state, PRNG and explicit timers. |
| 5. Independent budgets | Defines each amplification class and typed failure. |
| 6. Service boundary and no ambient authority | Keeps requests mediated and host execution out of SMX-026. |
| 7. Fail-closed validation | Rejects unknown/privileged opcodes, transient authority and incompatible IR. |
| 8. Canonical identity and attachment order | Prevents physical map/UUID ordering becoming semantics. |
| 9. Protected media boundary | Confirms execution cannot rewrite protected source/audio/provenance records. |
| 10. Adversarial evidence | Maps the production tests to accepted research pressure. |
| 11. Residual scope | States the exact handoff to SMX-027–031 and later platform work. |

## 1. Production contract

`src/splashmx/execution/ir.py` owns:

- `splashmx.behaviour-ir/1`, a versioned validated constrained IR for ordinary user intent;
- the first beginner Rule compiler, which emits that exact `IRProgram` type;
- advanced Behaviour programs expressed directly as the same `IRProgram` type;
- deterministic run-to-completion activations over canonical `ThingId` + `BehaviourAttachmentId` identities;
- provisional public/private mutation with atomic per-activation commit;
- ordered staged events, logical timers and mediated service requests;
- attachment-local deterministic PRNG state; and
- independent deterministic resource budgets and typed fault outcomes.

The module does **not** provide a second advanced scripting route. GDScript, C#, JavaScript/eval, native calls, raw sockets/filesystem/process APIs, direct foreign-Thing mutation and extension loading are not IR opcodes and are rejected before launch.

Instruction-step accounting is the deterministic CPU proxy at this layer. It is intentionally not a wall-clock performance claim; calibrated process/engine/GPU/audio resource accounting remains a later physical security/performance gate.

## 2. Rule compiler and advanced Behaviour parity

`compile_rule()` accepts the first deliberately small beginner surface: trigger + optional condition + public/private state mutation and event emission. It lowers that surface into `IRInstruction` / `IRHandler` / `IRProgram` records and immediately validates the result.

An advanced Behaviour is authored directly as an `IRProgram`. Both therefore pass through the same:

```text
IRProgram validation
    ↓
canonical ThingId + BehaviourAttachmentId binding
    ↓
deterministic activation queue
    ↓
transactional public/private drafts
    ↓
preflight resource/effect validation
    ↓
commit state, then publish staged work
```

There is no Rule-only evaluator, privileged advanced evaluator, or hidden host-script escape hatch. `source_kind` is diagnostic/provenance metadata for a front end, not a different execution architecture.

The production test suite runs both a compiled beginner Rule and a materially nontrivial advanced Behaviour through the same `ExecutionRuntime`. The advanced case uses private state, bounded iteration, procedure calls, public mutation, a logical timer and a follow-on event.

## 3. Activation and ordering semantics

Every queued activation has:

- logical due tick;
- monotonic enqueue sequence;
- canonical `ThingId`;
- canonical `BehaviourAttachmentId`;
- stable handler identity;
- explicit payload; and
- optional explicit timer identity.

Queue ordering is `(logical due tick, enqueue sequence)`. External dispatch fans out in explicit semantic attachment order and then handler declaration order. Effects produced by one activation preserve instruction order when they are committed.

One activation begins from committed public Thing runtime state and the current attachment-private state. All writes, emitted events, timers, service requests, deterministic-random state and queue growth are staged. Before publication, the runtime checks the full effect set against pending timer, queue, outbox and pending-service limits. Only after that preflight succeeds are public/private state and PRNG state committed; only then are effects made visible.

Therefore a follow-on event activation sees the state committed by its cause. If execution, expression evaluation or effect preflight fails, the activation's public/private mutations, random draws, emitted work, timers and service requests do not leak.

## 4. State, randomness and pending work

`ExecutionRuntime.from_document()` copies canonical authored state into a runtime plane. Play-time mutation never writes back into the caller's `CanonicalDocument`; this preserves the Architecture-v1 authored/runtime plane split.

Behaviour-private state is namespaced by concrete `BehaviourAttachmentId`, not by Behaviour code revision. Two attachments of the same exact Behaviour revision therefore have independent private state.

Ordinary randomness uses a deterministic attachment-local PRNG seed derived from the runtime seed + `ThingId` + `BehaviourAttachmentId`. A failed activation uses a staged PRNG state and rolls it back, so unrelated scheduling/failure does not silently perturb later draws.

Timers are explicit `PendingTimer` records containing stable timer identity within the attachment, due logical tick, Thing/attachment identity, handler identity, payload and enqueue sequence. A timer can be cancelled explicitly. No Python/Godot coroutine, thread stack, Node handle, socket or browser object is required for the pending-work representation. SMX-029 may later serialize/restore this semantic record rather than a host coroutine.

## 5. Independent budgets

`BudgetLimits` does not collapse hostile amplification into one counter. It independently bounds:

- `instruction_steps` — deterministic instruction/expression/loop CPU proxy;
- `recursion_depth` — procedure-call ancestry;
- `allocations` — runtime value/container copying/construction;
- `emitted_work` — events staged by one activation;
- `timers_per_activation` — timer creation by one activation;
- `pending_timers` — live delayed-work population;
- `queue_entries` — live activation queue population;
- `service_requests` — mediated requests staged by one activation;
- `pending_service_requests` — pending mediated-request population;
- `outbox_entries` — emitted-work backlog; and
- `activations_per_run` — event/zero-delay self-storm containment across otherwise individually legal turns.

Each class has a distinct typed `execution.*_budget` failure. Per-activation budget faults discard the activation atomically. A run-level activation-storm fault stops further work with the remaining queue intact rather than hanging the host process.

These tests port the accepted SMX-004 A-004/EXE-009 pressure and SMX-016 AT-018/AT-019 amplification requirements into the production implementation without claiming calibrated physical sandbox limits.

## 6. Service boundary and no ambient authority

`request_service` does not call a host function. It stages a typed `ServiceRequest` into a mediated queue carrying the originating `ThingId` and `BehaviourAttachmentId`, service name, payload and request identity.

SMX-027 owns principal mapping, grants, delegation, revocation and the final authorization recheck immediately before a trusted host adapter. Until then, SMX-026 provides no API for IR content to register or invoke host callables. A successful `request_service` therefore proves only that bounded semantic work requested a named service; it confers no capability and performs no side effect by itself.

This separation preserves R-016-03/R-016-04 for the next layer instead of prematurely implementing a weaker half-capability model.

## 7. Fail-closed validation

IR is validated before binding/launch. The production validator rejects:

- unknown required IR versions;
- unknown expression or instruction opcodes;
- explicit host/foreign-state opcodes (`gdscript`, JavaScript/eval, host/native calls, raw filesystem/socket/network/process/extension paths, direct foreign mutation);
- malformed handler/procedure/timer/service structures;
- unbounded/non-integer repeat/timer declarations;
- unknown procedure or timer-handler references;
- NaN/infinity and unsupported literal types;
- excessive program/literal structural depth/count/size; and
- nested durable authority/runtime-locator fields such as transport peer/session/capability tokens.

External activation payloads pass the same recursive plain-data/authority-field screening before they enter the queue. Unknown future required semantics therefore fail closed instead of being guessed by an older runtime.

## 8. Canonical identity and attachment order

Execution binds only to canonical `ThingId` and `BehaviourAttachmentId`; it does not use NodePath, RID, ResourceUID/resource path, DOM identity, database row ID, cache key, transport peer ID, socket/session ID, process handle or capability token as durable identity.

SMX-024 deliberately canonicalizes behaviour-attachment map bytes by semantic ID. That physical ordering is **not** author-visible scheduling order. When a Thing has more than one Behaviour attachment, `ExecutionRuntime.from_document()` therefore requires an explicit semantic attachment-order sequence and verifies that it covers every attachment exactly once. It refuses to invent order from Python map iteration, hash order, canonical-CBOR list order or lexical/UUID identity.

This is an intentional enforcement boundary, not a second identity system. The production-core integration gate (SMX-031) must preserve/provide authored attachment order when it assembles the execution plan. Until then, callers with one attachment require no extra order record; callers with multiple attachments must provide it explicitly. This prevents a physical serialization detail from silently becoming public language semantics.

## 9. Protected media boundary

SMX-026 does not own canonical `AssetId` revisions and provides no opcode capable of mutating canonical assets. The protected revision remains the indivisible Architecture-v1 bundle of **source digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**.

Runtime IR may carry ordinary asset references or request a future mediated service, but execution cannot field-edit an Asset revision, substitute a decoded/transcoded derivative for canonical source meaning, or synthesize provenance. Asset publication and persistence continue through SMX-024/025 whole-revision validation. Later service/package/network/collaboration layers retain the same non-droppable invariant.

## 10. Adversarial evidence

`tests/production/test_smx026.py` covers:

- beginner Rule and nontrivial advanced Behaviour through one `IRProgram`/executor;
- optional Rule conditions compiled to common `if` IR;
- state commit before follow-on event observation;
- handler declaration ordering and non-lexical explicit attachment ordering;
- exact Behaviour revision binding and invalid order rejection;
- Play/runtime mutation isolation from canonical authored state;
- attachment-private-state isolation;
- random-state rollback and deterministic replay;
- independent instruction/CPU-proxy, recursion, allocation, emitted-work, timer, pending-timer, queue, service-request, pending-service and activation-storm boundaries;
- atomic rollback when queue/timer/service preflight would overflow;
- fail-closed unknown/host/foreign-state opcodes and incompatible IR versions;
- recursive transient-authority rejection in IR literals and external payloads;
- mediated service requests without host invocation;
- explicit timer representation, cancellation and duplicate-identity rollback; and
- same-input/same-seed deterministic trace reproduction.

The tests are deterministic production semantics evidence. They do not claim Godot scheduler throughput, browser responsiveness, OS/process isolation, host-service authorization or durable pending-work restore.

## 11. Residual scope

SMX-026 intentionally hands forward:

- principal capabilities, delegation/revocation and trusted host-service adapters — SMX-027 / #52;
- transactional Behaviour hot replacement and pending-work migration — SMX-028 / #53;
- durable timer/continuation snapshot + WorldSave/fresh-process restore — SMX-029 / #54;
- production-core cross-module vertical conformance, including carrying authored Behaviour attachment order into execution plans — SMX-031 / #56;
- Godot engine-loop realization/performance — SMX-037/038 / #62/#63; and
- calibrated hostile physical resource accounting and process/decoder isolation — SMX-039–041 / #64–#66.

Architecture v1.0 remains unchanged. No protected source/audio/provenance semantic is weakened, and no second privileged scripting architecture is introduced.
