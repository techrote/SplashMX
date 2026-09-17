# SMX-004 — Behaviour execution, scheduling, hot-swap, and constrained IR

Status: candidate pre-architecture semantics for downstream security/lifecycle falsification

Issue: SMX-004 / #4

Established: 2026-09-17

This document defines the current candidate for how SplashMX behaviour executes above the
SMX-002 Thing kernel and SMX-003 definition/instance model. It deliberately does **not**
freeze a production bytecode encoding, textual language, compiler implementation, Godot
executor mapping, or package format.

The selected candidate is a **validated bounded-turn behaviour IR** executed as
deterministic, transactional activations. Beginner rules, reusable behaviours, future
visual logic, and future textual syntax target the same semantic IR. Long-lived work is
represented by explicit timers/continuations and mediated services rather than arbitrary
blocking user threads.

The companion experiment under `experiments/smx-004-behaviour-model/` and
`SMX-004-BEHAVIOUR-FIXTURES.json` are non-normative evidence for these semantics.

## Contents

| Section | Summary |
|---|---|
| 1. Research result | States the bounded-turn execution model and the invariants SMX-004 accepts provisionally. |
| 2. Constraints inherited from SMX-001–003 | Extracts the object, relationship, definition, and security pressures the executor must respect. |
| 3. Compared execution families | Compares rule engines, statecharts, dataflow, general VMs, and constrained embedded languages. |
| 4. Candidate behaviour/IR envelope | Defines behaviours, attachments, handlers, ports, private state, and instruction classes. |
| 5. Scheduling and run-to-completion turns | Defines activation ordering, commit points, and observable serial semantics. |
| 6. State mutation and communication | Defines transactional writes, read visibility, and the prohibition on direct foreign-state mutation. |
| 7. Determinism boundary | Separates deterministic core execution from clocks, entropy, network/service results, and other external inputs. |
| 8. Timers, async work, and continuations | Replaces blocking coroutines with explicit continuation records and mediated service responses. |
| 9. Resource budgets and failure | Makes CPU/event/memory growth limits part of execution semantics rather than a later sandbox afterthought. |
| 10. Hot behaviour replacement | Defines quiescent, transactional swap, state migration, continuation handling, and rollback. |
| 11. One IR from beginner to advanced | Shows how simple rules and serious reusable behaviours use the same semantic substrate. |
| 12. Corpus and executable evidence | Maps direct SMX-001 cases/adversarial variants to ET-001–ET-011. |
| 13. Architecture scorecard | Records evidence-backed scores and explicit not-evaluated areas. |
| 14. Rejected/deferred alternatives | Records why familiar execution models are not adopted wholesale. |
| 15. Security and capability handoff | Defines what SMX-006 may assume and what is still unproven. |
| 16. Serialization/lifecycle handoff | Identifies executor state that SMX-005/007 must represent and restore. |
| 17. Hypothesis status | Updates H-005/H-006/H-009 without overclaiming downstream security. |
| 18. Comparative primary sources | Records external precedents used as evidence, not selected dependencies. |

## 1. Research result

The current candidate execution model is:

```text
Thing
├─ authored/live public state
├─ ordered behaviour attachments
│  ├─ stable attachment identity
│  ├─ behaviour definition/version
│  ├─ private-state namespace
│  ├─ declared required/provided ports
│  └─ capability requirements
└─ explicit object-fabric ports/relationships

Runtime scheduler
├─ ordered activation queue
├─ logical simulation clock
├─ per-attachment deterministic PRNG streams
├─ explicit timers/continuations
├─ capability/service bindings
└─ hard resource budgets
```

A **behaviour activation** is one bounded run-to-completion turn. It reads committed Thing
state and its own private state, may make provisional writes, and may stage follow-on
events/commands/timers/service requests. If the activation completes within its limits,
its internal state mutation commits atomically, after which staged work is enqueued. If it
faults or exhausts a hard activation budget, its internal writes and deterministic random
draws roll back and its staged effects are discarded.

This gives SplashMX a precise author-visible rule:

> **A behaviour turn either commits completely or does not happen; anything it causes is
> observed after that commit.**

The runtime may later parallelize independent work internally, but observable behaviour
must remain equivalent to the specified serial order unless a future explicit concurrent
primitive says otherwise.

### Candidate execution invariants

- **EXE-001 — activations are finite bounded turns.** User-authored work cannot remain on
  the runtime stack indefinitely; every activation either completes, explicitly suspends
  through a continuation/service boundary, or faults under a budget.
- **EXE-002 — state commit precedes follow-on effects.** Events, commands, timer
  continuations, and service requests generated by a turn become observable only after
  that turn's internal state mutation commits.
- **EXE-003 — observable activation order is deterministic given an ordered external input
  stream.** Same-tick follow-on work receives monotonically ordered queue positions.
- **EXE-004 — a behaviour cannot directly mutate another Thing's private or public state.**
  Cross-Thing effects go through declared ports/commands/value propagation.
- **EXE-005 — external/privileged work is an asynchronous runtime service.** It is not a
  hidden synchronous host call embedded inside expressions.
- **EXE-006 — service use is capability-mediated.** Missing grants fail closed; optional
  features can test capability presence and continue with reduced functionality.
- **EXE-007 — timers use explicit clock domains and continuation records.** Logical
  simulation time is distinct from external wall-clock time.
- **EXE-008 — ordinary randomness is explicit and deterministic.** Default random streams
  are seeded and scoped so unrelated behaviour scheduling does not silently perturb them.
- **EXE-009 — execution budgets are semantic.** Instruction, emitted-work, activation,
  iteration/state-growth, continuation/timer, and service-request limits must be enforceable
  before untrusted-content launch.
- **EXE-010 — behaviour-private state belongs to the attachment, not to the behaviour code
  version.** Version replacement can preserve or migrate that state while Thing identity
  remains unchanged.
- **EXE-011 — hot replacement occurs only at a quiescent boundary and is transactional.**
  The old behaviour remains fully active if validation/migration/reconciliation fails.
- **EXE-012 — private-state migration is explicit, bounded, and side-effect-free.** Silent
  reinterpretation of old private state is forbidden.
- **EXE-013 — pending continuations/responses are explicit swap obligations.** A
  replacement maps them, explicitly cancels them, or is rejected.
- **EXE-014 — beginner and advanced authoring target the same validated IR.** An easy-mode
  rule is not executed by a separate toy engine.
- **EXE-015 — nondeterministic inputs enter through explicit recorded boundaries.** Network
  messages, host-service results, external clocks, entropy, sensors, and similar values
  are ordered inputs that can be captured for replay where required.

## 2. Constraints inherited from SMX-001–003

The executor cannot undo earlier architectural work.

From SMX-002:

- Thing identity is independent of engine handles and hierarchy.
- behaviour is an optional facet/attachment, not the definition of Thing identity;
- control/authority/context are not inferred from containment;
- command/event/value is the provisional port vocabulary;
- capability requests are declarations while actual grants are runtime context.

From SMX-003:

- behaviour attachment/provenance may come from a local definition and instance overlay;
- the concrete Thing has its own identity regardless of the definition revision;
- definition reconciliation and runtime execution are separate operations;
- external connections target stable public interfaces rather than fragile internal paths.

The SMX-001 cases add specific execution pressure:

- **C-003/C-004:** discrete events and continuous/readable values both matter.
- **C-005:** game-like controller work needs repeated/tick-driven behaviour without a
  different engine.
- **C-009:** procedural work needs controlled randomness and bounded iteration.
- **C-022/A-003:** denied privileged features must fail closed.
- **C-024:** pending work must be representable for later serialization/lifecycle work.
- **C-025/A-006:** behaviour replacement must preserve identity and handle incompatible
  private state explicitly.
- **A-004:** event/timer storms are a normal hostile-input case, not an edge condition.

## 3. Compared execution families

### 3.1 Immediate condition/action rule engine

A simple model is:

```text
WHEN condition/event
THEN actions
```

This is excellent authoring vocabulary and should remain a first-class projection.

Advantages:

- approachable and visually obvious;
- naturally maps button/timeline/game-event workflows;
- easy to inspect.

Problems if made the entire execution contract:

- ordering among nested/follow-on rules is often underspecified;
- long-lived work tends to accrete hidden timers/coroutines;
- private reusable-behaviour state and version migration become ad hoc;
- resource containment is difficult if arbitrary actions can call host code.

Conclusion: **retain as authoring syntax, compile to the common IR.**

### 3.2 Statechart/run-to-completion model

W3C SCXML specifies run-to-completion behaviour: one external event is processed along
with its enabled internal follow-up work before the next external event. It also makes
ordering/priorities explicit enough to preserve deterministic observable behaviour for
closed machines.

This is a strong precedent for SplashMX activation semantics.

Advantages:

- clear event/microstep boundary;
- deterministic follow-up ordering;
- natural state-machine projection;
- no need for simultaneous hidden mutation.

Limitations:

- SplashMX needs value ports, media/tick work, procedural work, and ordinary behaviours
  that should not all be represented as explicit statecharts;
- SCXML's document/model is not our desired universal IR.

Conclusion: **adopt the run-to-completion lesson, not SCXML as the runtime format.**

### 3.3 Dataflow/reactive graph

A pure dataflow graph is attractive for sliders, animation values, shader-like logic, and
procedural media.

Advantages:

- continuous/value relationships are visual and composable;
- potentially parallel and incremental;
- easy to inspect for acyclic pure graphs.

Problems as the only execution model:

- discrete intent/events and stateful game interactions become awkward;
- cycles require special fixed-point or scheduling semantics;
- timers, external I/O, authority, and hot-swap are not solved by the graph alone.

Conclusion: **value connections may use dataflow-like authoring, but propagation enters the
same bounded activation semantics at stateful/effectful boundaries.**

### 3.4 General-purpose bytecode/VM

A conventional scripting VM or WebAssembly-like machine can express virtually anything.

WebAssembly is valuable precedent for:

- validate-before-execute;
- a core semantics separate from host embedding;
- explicit imports/exports rather than ambient host access.

Problems for SplashMX ordinary user content:

- general instruction sets expose much more machinery than the author model needs;
- deterministic scheduling, event semantics, timers, state transactions, and object-fabric
  ports would still need a higher-level contract;
- instruction metering alone does not make arbitrary host imports safe;
- a general VM encourages the advanced mode to become a separate programming world.

Conclusion: **retain validation/import-boundary lessons; do not adopt raw WebAssembly or a
general language VM as the canonical user-content IR.**

### 3.5 Constrained embedded expression/language models

CEL provides a useful precedent for deterministic expression evaluation with explicit
cost modelling. Starlark provides a useful precedent for deterministic/hermetic embedded
execution with environment access supplied by the host rather than ambient by default.

Advantages:

- predictable evaluation;
- straightforward validation;
- safe expression/transform subset;
- explicit host extension boundary.

Limitations:

- CEL is expression-oriented, not a reactive object runtime;
- Starlark is configuration-oriented and not designed around live event/timer semantics.

Conclusion: **use a small deterministic expression layer and cost accounting inside the
behaviour IR; do not adopt either language wholesale.**

### 3.6 Scratch VM precedent

Scratch separates visual blocks from the runtime representation/VM. The current
Scratch editor repository documents the VM as representing, running, and maintaining
program state for block-authored programs.

This supports a critical SplashMX product principle:

> The authoring surface does not have to be the execution representation.

SplashMX can therefore expose rules, state machines, visual blocks, and future text while
all target one validated semantic IR.

## 4. Candidate behaviour/IR envelope

A behaviour definition is conceptually:

```text
BehaviourDefinition
├─ BehaviourId + version
├─ declared provided/required ports
├─ private-state schema + defaults
├─ required/optional capability declarations
└─ handlers
   ├─ trigger
   ├─ parameter/payload schema
   └─ bounded instruction sequence
```

A concrete Thing carries a **behaviour attachment identity**. The attachment binds one
behaviour definition/version and owns the corresponding private-state namespace.

The production encoding remains open, but the semantic instruction families are:

### Pure expressions

- literals;
- reads of the current Thing's public state;
- reads of the current attachment's private state;
- event/command payload reads;
- capability-presence checks;
- deterministic arithmetic/comparison/boolean operations;
- bounded reads/transforms over explicitly limited collections.

Expressions have no hidden clock, random source, network call, filesystem access, or
foreign-Thing mutation.

### Internal state instructions

- set/update public Thing state;
- set/update own private state;
- bounded local collection transformation.

### Communication instructions

- emit an event;
- send a command through an explicit target port;
- publish/update an explicit value port.

No instruction directly writes another Thing's state.

### Scheduling instructions

- schedule a continuation on logical time;
- request next-tick/frame activation where appropriate;
- create/cancel an explicitly identified timer/continuation within allowed limits.

### Controlled randomness

- sample a deterministic PRNG stream associated with a stable execution scope;
- request external entropy only through an explicit capability/service.

### Runtime-service instructions

- issue an asynchronous request to a named mediated service;
- receive its completion/error as a later activation.

Examples include HTTP, clipboard, file-picker/storage, microphone, authoritative
multiplayer service, pathfinding services, or expensive host intrinsics.

### Control flow

The initial candidate permits conditionals and **bounded** iteration only.

There is no unbounded `while` and no unbounded recursion inside one activation. The system
as a whole can of course run indefinitely through events/ticks/continuations; finite turns
do not make SplashMX globally non-Turing-complete.

This distinction is intentional: complex long-lived algorithms are decomposed over turns,
while no one user activation can monopolize the player indefinitely.

## 5. Scheduling and run-to-completion turns

### 5.1 Input ordering

Every activation has at least:

```text
logical due time
ordered enqueue sequence
target ThingId
target behaviour attachment identity
handler/continuation identity
payload
causal metadata
```

Given the same ordered external inputs, initial state, runtime version, and deterministic
seed, the core scheduler must produce the same observable activation order.

The external-input adapter owns ordering when reality itself is nondeterministic. For
example, a server may sequence network inputs; a browser input adapter may record arrival
order. That recorded order is the reproducibility boundary rather than pretending
simultaneous external events have a universal natural order.

### 5.2 Fan-out order

When one Thing event/command targets several attached behaviours, handler activations are
enqueued in the Thing's stable **behaviour attachment order** after SMX-003 definition/
overlay reconciliation, then in stable handler declaration order where one behaviour
provides multiple handlers for the same trigger.

This ordering must be inspectable. Authors should not have to infer it from memory
addresses, hash-table order, Godot child order, or generated UUID lexical order.

### 5.3 One activation

An activation:

1. begins from committed public/private state;
2. evaluates pure expressions and provisional writes;
3. accumulates staged events/commands/timers/service requests;
4. may read its own provisional writes;
5. cannot expose those writes to another activation before commit;
6. commits all internal mutation atomically if successful;
7. only then enqueues staged follow-on work.

A later activation in the same logical tick sees the earlier committed result.

### 5.4 Internal parallelism

A future implementation may execute proven-independent activations in parallel, but the
result must be equivalent to the specified serial schedule. Parallel execution is therefore
an optimization below the compatibility boundary unless SplashMX later introduces an
explicit author-visible concurrent primitive.

## 6. State mutation and communication

### 6.1 Public Thing state

A behaviour may update public state of the Thing to which it is attached when its
interface/policy permits that field.

This is not permission to modify arbitrary Things.

### 6.2 Private state

Each behaviour attachment receives a private namespace. Private keys belong to the
attachment identity, not to the current code/version object.

This gives SMX-004 a stable semantic subject for:

- timers/counters;
- state-machine modes;
- cached local computation;
- hot-swap migration.

### 6.3 Read-your-writes, isolation to commit

Within one activation, a handler observes its own provisional writes. Other activations do
not observe them until successful commit.

### 6.4 Fault rollback

For a fault before commit:

- public writes roll back;
- private writes roll back;
- deterministic PRNG draw state rolls back;
- staged events/commands/timers/service requests are discarded.

A host service is therefore not invoked until after internal commit.

### 6.5 Cross-Thing communication

Direct foreign mutation is rejected from the IR. Cross-Thing intent is explicit:

```text
Button.clicked event
    -> Door.open command

Slider.value
    -> Audio.volume value connection
```

This preserves encapsulation, network mediation, validation, and future authority checks.

### 6.6 Query/request-response

SMX-004 does **not** add a first-class synchronous cross-Thing query primitive.

The current rule is:

- current readable values provide snapshot-style reads where an explicit value connection/
  observation is appropriate;
- request/response uses a command/request plus correlated response event;
- privileged/slow operations use runtime services and later result activations.

Reason: synchronous cross-Thing query stacks introduce re-entrancy, blocking, and location
coupling that conflict with streaming/networking and bounded-turn semantics.

SMX-010 may refine remote/request semantics, but it should not silently reintroduce
synchronous object calls.

## 7. Determinism boundary

Determinism is scoped, not magical.

### 7.1 Deterministic core inputs

The bounded-turn executor is deterministic from:

- initial committed state;
- validated behaviour IR/version;
- ordered external input sequence;
- logical-time sequence;
- deterministic seed/state.

### 7.2 Randomness

Ordinary `random` operations use explicit seeded streams. The research model scopes a
stream by:

```text
creation/runtime seed + ThingId + behaviour attachment identity
```

This prevents an unrelated behaviour's extra random draw from changing another
attachment's random sequence merely because scheduling changed.

Exact production stream derivation is a later format/runtime decision; the invariant is
scope isolation and reproducibility.

### 7.3 Time

Default timers use **logical simulation time**.

Wall clock, calendar time, high-resolution real time, or background-tab timing is external
runtime context/service input. Such values are not implicit instructions.

### 7.4 External I/O

HTTP results, multiplayer packets, sensors, files, clipboard, microphone, geolocation,
host errors, and entropy are externally nondeterministic inputs.

They enter execution as explicit ordered results/events with enough provenance to record
them where replay/audit is required.

### 7.5 Physics

Physics may be a host/runtime subsystem rather than behaviour-IR instructions. If a
behaviour consumes a physics result, that result must arrive through a defined deterministic
or recorded boundary. SMX-009/010/017 determine which parts can be replayed or predicted
consistently across Godot runtimes/topologies.

## 8. Timers, async work, and continuations

SplashMX should not expose an arbitrary stackful user coroutine as the durable semantic
contract.

Instead:

```text
handler starts work
    -> schedule continuation / request service
    -> activation ends and commits
    ...
continuation/result becomes a later activation
```

A continuation record needs stable semantic identity sufficient for later:

- cancellation;
- serialization;
- behaviour replacement;
- migration;
- diagnostics.

A future text language may allow:

```text
wait 0.5 seconds
result = await fetch(...)
```

but the compiler lowers those constructs into explicit continuation/service IR.

### Timer clock classes

At minimum distinguish:

- **simulation timer** — advances with the creation's logical simulation clock;
- **external/wall timer** — supplied by a runtime service and therefore an external input.

This matters for pause, replay, background tabs, multiplayer authority, and saved worlds.

### Awaiting host services

A host request is staged during the activation, issued after commit, and produces a later
result/error activation.

No ordinary service result can synchronously mutate the currently executing handler's
stack.

## 9. Resource budgets and failure

Resource containment belongs in the executor semantics.

At minimum SMX-006/016 must be able to enforce:

### Per activation

- instruction/cost units;
- nested expression depth;
- bounded iteration count;
- state allocation/growth;
- emitted command/event count;
- timer/continuation creation;
- service-request count.

### Per logical tick/frame

- total activations;
- total causal-chain emissions;
- aggregate instruction/cost units;
- newly allocated state/resources.

### Per behaviour/Thing/package

- private-state size;
- timer/continuation count;
- queued work;
- dependency/service usage according to later package policy.

Expensive host operations need declared cost classes or quotas outside the ordinary
instruction count.

### Failure semantics

A per-activation hard-budget fault:

- aborts that activation;
- rolls back its internal transaction;
- discards staged effects;
- records a privileged diagnostic inaccessible for tampering by the behaviour itself.

A broader tick/package budget may throttle, defer, suspend, or quarantine further work
according to host policy, but ordinary user code cannot disable the hard cap.

The research harness proves that a self-emitting event storm cannot execute unboundedly
within one tick. SMX-006/016 must decide final quarantine/termination policy and test
adversarial amplification across packages/network boundaries.

## 10. Hot behaviour replacement

Behaviour swapping is a first-order object-fabric operation, not code pointer mutation.

### 10.1 Quiescent boundary

Replacement occurs only between activations for the target attachment. No handler is
halfway through a turn when its code changes.

### 10.2 Preflight

Before any mutation, the runtime checks:

- replacement definition/version is valid;
- required/provided port compatibility;
- private-state schema compatibility or a supplied migration;
- capability requirement changes;
- pending timers/continuations/service-response handlers;
- any externally connected public interface obligations.

### 10.3 State transfer

Three ordinary cases exist:

1. **same compatible private schema** — retain attachment-private state;
2. **explicit migration** — run a bounded side-effect-free migration transform;
3. **incompatible without migration** — reject the swap.

Migration cannot perform network/host I/O or mutate unrelated Things.

### 10.4 Pending work

For every pending continuation/service response owned by the attachment, replacement must:

- preserve a compatible handler identity;
- explicitly map old continuation/handler identity to a new one;
- explicitly cancel it where product semantics allow cancellation; or
- reject the replacement.

Silent dropping or accidental delivery into a semantically different handler is forbidden.

### 10.5 Atomic commit/rollback

Only after all preflight/migration/continuation planning succeeds does the runtime commit
the new behaviour definition and migrated state.

Failure leaves:

- old behaviour version;
- old private state;
- pending queue;
- Thing identity

unchanged.

The SMX-004 experiment demonstrates same-schema state preservation, explicit migration,
continuation remapping, and atomic rejection.

## 11. One IR from beginner to advanced

H-006 only matters if the easy layer is not a dead end.

### Beginner rule

Authoring surface:

```text
WHEN Button is clicked
DO Door open
```

IR shape:

```text
handler clicked:
    send command Door.open
```

### Timer animation rule

```text
WHEN activated
WAIT 0.5 seconds
PLAY animation
```

becomes:

```text
handler activated:
    schedule continuation after 0.5 logical seconds

continuation:
    send Animation.play
```

### Reusable door behaviour

A reusable behaviour may have:

```text
private:
    locked: bool
    open: bool

command unlock
command open
event opened
```

Its conditions/state transitions are still bounded handlers using the same operations.

### Platform controller

A more advanced controller may use:

- repeated tick/input activations;
- private/public state;
- physics service/results;
- deterministic calculations;
- timers;
- several handlers.

It remains the same `BehaviourDefinition`/handler IR, not a GDScript escape hatch.

### Future textual language

A text frontend may add:

- local variables;
- functions/macros lowered at compile time;
- bounded loops;
- `wait`/`await` syntax lowered to continuations;
- structured state-machine syntax;
- richer typed expressions.

Its accepted output remains validated bounded-turn IR.

If advanced requirements later prove impossible without a second semantic engine, H-006
must be weakened/rejected explicitly rather than hiding the fork behind syntax.

## 12. Corpus and executable evidence

The companion fixture manifest is
`docs/research/SMX-004-BEHAVIOUR-FIXTURES.json`.

Direct executable coverage:

| Fixture | Cases | Observation |
|---|---|---|
| ET-001 | C-003/C-004 | Internal writes commit before emitted follow-on activation; same IR supports event/command/value-oriented rules. |
| ET-002 | A-004 | Budget fault rolls back public/private state and PRNG state. |
| ET-003 | C-024 | Logical timer creates explicit pending continuation and fires deterministically. |
| ET-004 | C-009 | Seeded per-attachment PRNG stream is deterministic and isolated from unrelated attachment draws. |
| ET-005 | C-022/A-003 | Host service fails closed without capability and returns only via a later result activation when granted. |
| ET-006 | A-004 | Self-emitting event storm is stopped by a per-tick activation cap. |
| ET-007 | C-025 | Same-schema hot replacement preserves private state and Thing identity. |
| ET-008 | C-025/A-006 | Replacement can explicitly migrate private state and remap pending continuation identity. |
| ET-009 | C-025/A-006 | Incompatible replacement is rejected atomically, retaining old code/state/queue. |
| ET-010 | C-005/C-025 | Beginner compiler output and advanced behaviour use the same `BehaviorSpec` IR type. |
| ET-011 | C-004 | Validator rejects a direct foreign-state mutation opcode. |

The experiment also checks an optional denied capability can select a reduced local path
rather than making the whole behaviour unusable.

### Not proven here

- canonical serialized IR encoding;
- compiler correctness from future visual/text syntax;
- Godot/browser executor performance;
- adversarial sandbox escape resistance;
- persistence/restore of executor queues;
- network-topology determinism;
- large-scale scheduling/parallel optimization;
- cross-version package migration.

## 13. Architecture scorecard

Candidate: validated bounded-turn behaviour IR

Direct cases exercised:
C-003, C-004, C-005, C-009, C-022, C-024, C-025

Adversarial variants:
A-003, A-004, A-006

| Score | Assessment |
|---|---|
| S-01: 2 | Beginner event/action rule compiles directly to the same IR; editor UX still untested. |
| S-02: 3 | Event, state, timer, service, and hot-swap semantics use one execution vocabulary. |
| S-03: 2 | Executor does not use hierarchy for behaviour ownership; broader integration remains SMX-015. |
| S-04: 2 | Hot swap preserves Thing identity; canonical IDs/serialization remain SMX-005. |
| S-05: 3 | Attachment-private state, explicit interfaces, quiescent swap, migration, and pending-work reconciliation are executable. |
| S-06: N/E | Full serialize/restore belongs to SMX-007. |
| S-07: N/E | Stream-out/in belongs to SMX-008/015. |
| S-08: 2 | Validate-before-run, no arbitrary opcode, explicit services/capabilities, and budgets are demonstrated; hostile sandbox testing remains SMX-006/016. |
| S-09: N/E | Multiplayer topology semantics are not tested here. |
| S-10: N/E | Collaborative document execution/merge is not tested here. |
| S-11: 2 | Behaviour version/state migration semantics exist, but package/schema migration remains SMX-005/013/018. |
| S-12: 3 | Candidate semantics contain no Godot node/script/RPC contract. |
| S-13: 3 | Twelve deterministic dependency-free tests exercise named invariants. |
| S-14: N/E | Performance proportionality is not benchmarked. |
| S-15: 3 | Budget, capability, service, and incompatible-swap failures are explicit and fail closed in tested cases. |
| S-16: 2 | Beginner/advanced IR continuity is demonstrated at model level; editor projection remains SMX-012/019. |

Hard-gate failures observed in SMX-004 scope: **none**.

This is not Architecture v1.0; N/E remains N/E.

## 14. Rejected or deferred alternatives

### Arbitrary GDScript as behaviour IR

Rejected by existing D-004 and reinforced here.

It would:

- leak engine APIs above the compatibility boundary;
- make capability inspection incomplete;
- make deterministic scheduling/state transactions advisory;
- make future browser/server alternate runtimes harder;
- turn beginner rules into a separate semantic tier.

### Raw WebAssembly as the ordinary IR

Deferred/rejected as the canonical high-level contract.

Wasm validation/imports are useful precedent, but raw Wasm does not itself specify
SplashMX object-state transactions, event ordering, timers, hot-swap migration, or
author-facing ports.

A future trusted/advanced extension might use Wasm below a mediated boundary, but it must
not silently bypass ordinary capability/budget/state semantics.

### Pure actor/mailbox model

Not adopted wholesale.

Stable references/messages are useful, but mandatory actor mailboxes are an unnecessary
commitment for media/value/dataflow cases, and supervision hierarchy must not become
SplashMX containment semantics.

### Pure statechart executor

Not adopted wholesale.

Run-to-completion semantics are valuable, but every SplashMX behaviour should not be
forced into state-machine notation.

### Pure dataflow runtime

Not adopted wholesale.

Excellent for pure value graphs, insufficient alone for discrete intent, private mutable
state, async services, and authoritative effects.

### General stackful coroutine semantics

Rejected as the durable contract.

Stackful suspension is awkward to inspect, serialize, migrate, budget, and hot-swap.
Authoring syntax may look coroutine-like, but the compiler lowers to explicit continuations.

### Synchronous cross-Thing method/query calls

Rejected from the current candidate.

They create re-entrant call stacks, blocking/location coupling, and difficult
stream/network mediation. Use explicit values or async request/response instead.

## 15. Security and capability handoff

SMX-006 may assume the **candidate** executor has these enforcement hooks:

1. IR validation before execution;
2. a finite known opcode/intrinsic vocabulary;
3. no ambient host API instruction;
4. runtime services named explicitly;
5. capability checks at service boundaries;
6. optional capability-presence branching;
7. per-activation and broader scheduling budgets;
8. transactional rollback for pre-commit faults;
9. asynchronous host results rather than re-entrant host calls;
10. privileged diagnostics outside mutable user state.

SMX-006 must still determine:

- exact capability grant/delegation model;
- nested-component confused-deputy rules;
- memory/allocation accounting;
- package validation limits;
- service quotas and revocation;
- whether Godot runtime builds must remove JavaScript/native bridges;
- target-specific browser/native/headless escape surfaces.

### Required-versus-optional capabilities

The behaviour manifest should distinguish:

- **required capability:** attachment/activation cannot perform its promised function unless
  the grant exists; load/attach policy must surface this clearly;
- **optional capability:** behaviour can test availability and continue with explicitly
  reduced functionality.

The research harness demonstrates the optional denied path and fail-closed service call,
not the final UX/policy.

## 16. Serialization/lifecycle handoff

SMX-005/007 must be able to represent enough executor state to reconstruct semantics after
save/load, sleep, or streaming.

Candidate durable/runtime records include, as applicable:

- behaviour definition/version identity;
- stable behaviour attachment identity;
- private-state schema/version + values;
- ordered attachment position;
- pending timer/continuation identity;
- logical due time / clock domain;
- target handler/continuation ID;
- payload where persistable;
- deterministic PRNG stream state **or** an equivalent seed + draw-position representation;
- fault/suspension state where product semantics require persistence;
- pending service/network request correlation if those operations survive save/unload.

Important separation:

- a **definition document** says what the behaviour is;
- **attachment private state** says current local execution state;
- **scheduler/context state** says what pending work exists now;
- **external inputs/results** are runtime history/context, not automatically canonical
  authored project state.

SMX-007 decides which of these survive each lifecycle transition.

### Restore side effects

Restore must not replay already-committed external effects merely because a continuation or
service result record is reconstructed.

Exactly-once/at-least-once host-service semantics are outside SMX-004 and must be made
explicit by the lifecycle/service layer.

## 17. Hypothesis status

### H-005 — Behaviour is safely composable and dynamically replaceable

**Strengthened.**

Evidence:

- stable attachment-private state;
- validated interfaces/state schema;
- Thing identity preserved across replacement;
- same-schema state preservation;
- explicit bounded migration;
- pending continuation remapping;
- atomic rejection on incompatibility.

Still unproven:

- production-scale performance;
- persistence across unload/restore;
- package/version compatibility;
- adversarial component sandboxing.

### H-006 — Built-ins, visual rules, and future text can target one IR

**Strengthened.**

Evidence:

- beginner-rule compiler and hand-authored advanced behaviour produce the same
  `BehaviorSpec`/handler instruction model;
- timers, conditions, state, service requests, and reusable behaviour do not require a
  second executor.

Still unproven:

- a full visual editor/compiler;
- a future textual language;
- very complex author workloads;
- performance sufficient for all media use cases.

### H-009 — Capability security can bound untrusted components

**Strengthened narrowly at the execution-boundary level; still unresolved end-to-end.**

Evidence:

- unknown opcodes are rejected;
- no direct arbitrary host-call opcode exists;
- host services are explicit;
- missing capability fails closed;
- optional capability can degrade cleanly;
- hard execution budgets are present.

SMX-006/016 must still attempt real sandbox escape, confused-deputy, package/parser, memory,
and target-specific attacks. SMX-004 does **not** claim the sandbox is complete.

No other hypothesis changes status from SMX-004.

## 18. Comparative primary sources

Checked 2026-09-17. These are design precedents/evidence, not SplashMX dependencies.

### W3C SCXML

- https://www.w3.org/TR/scxml/

Relevant precedent:

- run-to-completion external/internal event processing;
- deterministic ordering/priority in the closed machine model.

SplashMX adopts the run-to-completion lesson but not the SCXML document format.

### WebAssembly specification

- https://webassembly.github.io/spec/
- https://webassembly.github.io/spec/core/valid/modules.html
- https://webassembly.github.io/spec/core/exec/instructions.html

Relevant precedent:

- module validation before execution;
- core semantics separated from embedding;
- imports/host functions are explicit boundaries;
- host functions may be nondeterministic, reinforcing the need to treat host results as
  external inputs rather than pretend the whole runtime is deterministic.

SplashMX does not select raw Wasm as ordinary user IR.

### Scratch VM / Scratch editor

- https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/README.md

Relevant precedent:

- visual blocks are represented/run by a VM-level program representation rather than the
  UI itself being the execution semantics.

SplashMX uses this only as evidence that visual beginner authoring can compile to a deeper
common runtime representation.

### Common Expression Language (CEL)

- https://cel.dev/
- https://github.com/cel-expr/cel-spec/blob/master/doc/langdef.md

Relevant precedent:

- deterministic expression evaluation;
- cost/complexity treatment for untrusted expression execution;
- side-effect-free expression use.

SplashMX does not select CEL as the full behaviour language.

### Starlark

- https://github.com/bazelbuild/starlark/blob/master/spec.md

Relevant precedent:

- deterministic/hermetic embedded execution;
- no ambient filesystem/network/clock by default;
- deliberately restricted control-flow features.

SplashMX does not select Starlark as the live behaviour language; it is evidence that
restriction can be a feature of embedded user execution rather than a deficiency.
