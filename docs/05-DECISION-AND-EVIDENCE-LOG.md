# SplashMX decision and evidence log

This is a compact durable register. Detailed research belongs in issue-specific documents; this file records what the project currently believes, why, and where to retrieve the evidence.

## Status vocabulary

- **FACT** — current primary-source fact, version/date sensitive where applicable.
- **HYPOTHESIS** — proposition awaiting or undergoing falsification.
- **DECISION** — accepted project choice with current evidence; pre-Architecture-v1 decisions remain falsifiable by later destructive work.
- **OPEN** — unresolved question/blocker.
- **REJECTED** — considered direction that should not be silently reintroduced without new evidence.

## Project decisions

### D-001 — Research before production editor

**Status:** DECISION.

Research object/execution/document/security/lifecycle semantics before building the production Flash-style editor so familiar UI metaphors do not hard-code Flash/Godot assumptions.

### D-002 — Godot is substrate, not canonical public contract

**Status:** DECISION.

Godot is the intended runtime/rendering substrate; SplashMX owns durable author-facing object/document/package semantics.

### D-003 — Runtime multiplayer and collaborative editing are distinct consistency problems

**Status:** DECISION.

They may share infrastructure but are researched and specified separately.

### D-004 — No arbitrary GDScript as default community execution model

**Status:** DECISION.

Community/user-authored executable intent crosses a constrained, inspectable, budgetable boundary rather than receiving arbitrary engine code access.

### D-005 — Generic runtime/player is the preferred publishing hypothesis

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Ordinary creations should ideally be data + constrained logic consumed by versioned generic web/native/server players rather than independently compiled Godot projects.

**Tested by:** SMX-009/014/017/019.

### D-006 — Destructive prototypes precede Architecture v1.0

**Status:** DECISION.

Architecture freeze is gated by integrated object-fabric, sandbox, network, collaboration, and browser vertical-slice falsification.

### D-007 — Stable evaluation IDs and explicit not-evaluated state

**Status:** DECISION.

Use `C-###`, `A-###`, and `S-##`; omitted applicable cases remain `N/E`, never implicit pass.

### D-008 — Scorecards do not waive constitutional hard gates

**Status:** DECISION.

Per-criterion scores are evidence aids; a hard-gate failure cannot be averaged away.

### D-009 — Research harness results require reproducibility metadata

**Status:** DECISION.

Executable research records question, hypothesis/corpus IDs, source commit, versions, commands, fixtures/seeds, expected invariant, result, and environmental caveats.

### D-010 — Durable Thing identity is independent of hierarchy/engine handle

**Status:** DECISION at semantic-requirement level; exact encoding remains SMX-005 work.

Thing identity survives rename/reparent/control/authority transfer and is distinct from labels, paths, Godot handles, process identity, and peer IDs.

**Source:** SMX-002 K-001/K-002/K-010; T-001/T-007.

### D-011 — Containment, control, authority, observation, persistence, and replication are separate semantics

**Status:** DECISION at object-fabric semantic level.

One overloaded `owner`/parent field must not stand for these dimensions.

**Source:** SMX-002 K-003/K-004; T-001/T-002.

### D-012 — Intrinsic declaration and runtime/editor context are separate planes

**Status:** DECISION at semantic level.

Thing state/facets may declare requirements/policy; current capability grants, controller/authority, sessions/services, selection, residency, diagnostics, and engine handles remain context unless explicitly projected/persisted.

**Source:** SMX-002 K-005/K-006/K-010.

### D-013 — Command/event/value is the current port vocabulary; synchronous cross-Thing query is excluded

**Status:** DECISION at current pre-architecture semantic level; later network/destructive work may refine it.

Discrete intent uses commands, occurrences use events, and observable continuous/snapshot data uses directional values. Cross-Thing request/response is asynchronous command + correlated event (or a mediated service request); a synchronous query/method-call stack is not part of the current contract.

**Reason:** synchronous cross-Thing query creates re-entrancy, blocking/location coupling, and awkward streaming/network mediation. SMX-004 found command/event/value plus async response sufficient for tested execution cases.

**Source:** SMX-002 port candidate; SMX-004 section 6 / EXE-004/EXE-005/EXE-014.

### D-014 — Current kernel candidate is faceted Thing + explicit relation graph

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Stable Thing identity, intrinsic state namespaces, optional facets, explicit ports, typed relationships, and explicit context bindings form the current kernel candidate.

### D-015 — Local definitions use stable definition/element provenance distinct from concrete Thing identity

**Status:** DECISION at semantic-requirement level; canonical encoding remains open.

Reusable definitions have durable definition/element identity; concrete instances have their own Thing IDs plus explicit provenance. `instance-of` is provenance, not runtime ownership/control/authority.

**Source:** SMX-003 CMP-002–CMP-005; CT-001/CT-002.

### D-016 — Instance variation is sparse explicit overlay over an immutable base revision

**Status:** DECISION at semantic level.

Instances record intentional departures/local additions/suppressions. Compatible base changes propagate to unoverridden loci; valid explicit overrides remain authoritative.

**Source:** SMX-003 CMP-006/CMP-007/CMP-011; CT-003/CT-004/CT-007.

### D-017 — Definition updates reconcile transactionally and fail explicitly on invalidated targets

**Status:** DECISION at semantic level; canonical conflict format remains open.

Definition revision updates are planned before commit. Invalidated overrides/exposures/local attachments/protected destructive changes produce explicit conflicts and cannot leave half-migrated instances.

**Source:** SMX-003 CMP-008/CMP-009; CT-005/CT-006/CT-009.

### D-018 — Public group/component interfaces are stable indirections over internal element ports

**Status:** DECISION at semantic level.

External connections target stable public port IDs; compatible internal reparent/replacement may rebind the implementation endpoint without external path repair.

**Source:** SMX-003 CMP-010; CT-008/CT-009.

### D-019 — Behaviour executes as bounded transactional run-to-completion turns

**Status:** DECISION at candidate execution-semantic level; subject to SMX-015 destructive integration.

A behaviour activation reads committed state, makes provisional internal writes, stages follow-on work, and either atomically commits or rolls back. Events/commands/timers/service requests become observable only after successful state commit. Observable parallel implementations must remain equivalent to the specified serial order unless future explicit concurrency is introduced.

**Reason:** this makes event ordering, mutation visibility, rollback, budgets, replay, and hot replacement inspectable rather than incidental runtime behavior.

**Source:** `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md` EXE-001–EXE-003; ET-001/ET-002.

### D-020 — Long-lived work is explicit continuation/service state, not durable stackful coroutine state

**Status:** DECISION at candidate execution-semantic level.

`wait`/`await`-like author syntax lowers to explicit timers/continuations or asynchronous runtime-service requests. A suspended user stack is not the durable compatibility contract.

**Reason:** explicit continuations are inspectable, serializable, budgetable, cancellable, migratable, and hot-swap-reconcilable.

**Source:** SMX-004 EXE-005/EXE-007/EXE-013; ET-003/ET-005/ET-008.

### D-021 — Deterministic core execution is separated from explicit external nondeterminism

**Status:** DECISION at candidate execution-semantic level.

Given the same initial state, validated IR, ordered external inputs, logical time, and deterministic seed, core activation ordering/results must be reproducible. Default randomness uses stable scoped streams. Wall clock, entropy, network/service/sensor/host results enter as explicit ordered external inputs.

**Reason:** pretending external I/O is deterministic would make replay and multiplayer reasoning false; allowing hidden clock/random/host reads would make identical content semantically unstable.

**Source:** SMX-004 EXE-003/EXE-007/EXE-008/EXE-015; ET-003/ET-004/ET-005.

### D-022 — Behaviour-private state belongs to stable attachment identity; hot swap is quiescent and transactional

**Status:** DECISION at candidate execution-semantic level.

Private execution state belongs to the behaviour attachment, not the current code version. Replacement occurs between activations, preflights interfaces/state/capabilities/pending work, retains compatible state or uses explicit bounded pure migration, and maps/cancels/rejects pending continuations explicitly. Failed replacement leaves old code/state/queue/Thing identity unchanged.

**Source:** SMX-004 EXE-010–EXE-013; ET-007–ET-009.

### D-023 — Execution/resource budgets are part of behaviour semantics

**Status:** DECISION at execution-boundary level; exact quotas/policies remain SMX-006/016 work.

The runtime must be able to hard-cap activation instruction/cost units, emitted work, bounded iteration/allocation, timers/continuations/service requests, per-tick activation/cost totals, and per-object/package queued/private state. Ordinary user content cannot disable the hard caps.

**Reason:** A-004 and untrusted community execution cannot be safely retrofitted after the IR permits unbounded monopolization.

**Source:** SMX-004 EXE-001/EXE-009; ET-002/ET-006.

### D-024 — Privileged/host work crosses explicit asynchronous capability-mediated services

**Status:** DECISION at execution-boundary level; capability delegation/grant model remains SMX-006 work.

Ordinary behaviour IR has no ambient filesystem/network/browser/Godot/native operation. A named service request is capability-checked, issued after the internal activation commits, and returns success/error as a later activation. Optional capabilities may select an explicit reduced path.

**Source:** SMX-004 EXE-005/EXE-006/EXE-015; ET-005 plus optional-capability harness test.

## Primary-source and comparative evidence

### E-001 — Godot web editor export limitation

**Status:** FACT, time-sensitive; superseded in precision by E-007.

Source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

### E-002 — Godot web renderer/platform constraints

**Status:** FACT, time-sensitive; superseded by E-008/E-009.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-003 — Custom Godot web build can reduce JavaScript exposure

**Status:** FACT, time-sensitive; superseded by E-012.

Source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### E-004 — Godot runtime/package facilities are not automatically safe for untrusted executable content

**Status:** FACT/design input, time-sensitive; superseded by E-013.

### E-005 — Godot networking is candidate substrate, not settled SplashMX protocol

**Status:** FACT/design input, time-sensitive.

### E-006 — Godot release context checked 2026-09-17

**Status:** FACT, time-sensitive.

Official archive listed Godot 4.7.2 stable (2026-08-18) and 4.8-dev6 (2026-09-15).

Source: https://godotengine.org/download/archive/

### E-007 — Web editor remains preliminary/non-exporting

**Status:** FACT, time-sensitive, checked 2026-09-17.

Source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

### E-008 — Web export baseline is WebAssembly/WebGL 2 Compatibility

**Status:** FACT, time-sensitive, checked 2026-09-17.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-009 — Single-threaded web export is preferred/default; threading changes hosting requirements

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

### E-010 — Browser background suspension is architecturally relevant

**Status:** FACT, time-sensitive.

Current Godot web-export docs report inactive-tab pausing can affect network connections.

### E-011 — Browser networking surface is restricted

**Status:** FACT, time-sensitive.

Godot web builds expose browser-suitable HTTP/WebSocket/WebRTC paths rather than arbitrary low-level networking.

### E-012 — Custom web templates can omit JavaScriptBridge/eval support

**Status:** FACT, time-sensitive.

Source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### E-013 — Runtime file/ZIP loading exists; executable PCK/mod loading is security-sensitive

**Status:** FACT, time-sensitive.

Sources: Godot runtime I/O and exporting-PCK documentation.

### E-014 — Headless/dedicated execution and WebRTC substrate are available

**Status:** FACT, time-sensitive.

Sources: Godot dedicated-server and WebRTC documentation.

### E-015 — Godot core composition is scene/node-tree oriented

**Status:** FACT / conceptual comparison input.

Sources: Godot 4.7 key concepts and node/scene-instance documentation.

### E-016 — ECS precedent separates unique entities, optional components, and explicit relationships

**Status:** FACT / conceptual comparison input.

Sources: Bevy ECS guide and relationship example.

### E-017 — Actor precedent separates stable reference from encapsulated state/behaviour

**Status:** FACT / conceptual comparison input.

Sources: Akka actor-model documentation.

### E-018 — Prototype delegation is flexible but makes inherited lookup implicit

**Status:** FACT / conceptual comparison input.

Source: MDN prototype-chain guide.

### E-019 — Godot scene inheritance demonstrates base/local-modification trade-offs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Source: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html

### E-020 — Unity prefab precedent supports linked instances, nesting, and explicit overrides

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: Unity current prefab introduction/overrides and Unity 6 prefab variants documentation.

### E-021 — Self prototype/delegation precedent shows seamless reuse and implicit-role costs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: Self Handbook 2024.1 world organization/programming guide/glossary.

### E-022 — W3C SCXML specifies run-to-completion event processing

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

SCXML processes one external event and enabled internal follow-up microsteps before the next external event and specifies deterministic priority/order for a closed state machine.

Source: https://www.w3.org/TR/scxml/

**Implication:** strong precedent for SplashMX bounded-turn commit/follow-on ordering without requiring the SCXML document model.

### E-023 — WebAssembly separates validated core modules from host embedding/imports

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

The current WebAssembly specification separates core module validation/execution from embedding APIs; host functions are explicitly outside the core and may be nondeterministic.

Sources:
- https://webassembly.github.io/spec/
- https://webassembly.github.io/spec/core/valid/modules.html
- https://webassembly.github.io/spec/core/exec/instructions.html

**Implication:** validates the design principle of validate-before-run plus explicit host boundaries, but raw Wasm does not supply SplashMX object/event/state semantics.

### E-024 — Scratch separates visual authoring from VM program representation

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Scratch's current monorepo documents its VM as representing, running, and maintaining program state authored with Scratch Blocks.

Source: https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/README.md

**Implication:** beginner visual authoring can compile to a deeper common runtime representation without the UI itself becoming execution semantics.

### E-025 — CEL specifies deterministic expression evaluation and cost concerns for untrusted expressions

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

CEL documents deterministic evaluation for a given environment and explicitly treats time/space cost containment as central to untrusted expression execution.

Sources:
- https://cel.dev/
- https://github.com/cel-expr/cel-spec/blob/master/doc/langdef.md

**Implication:** useful precedent for a small pure expression layer and explicit cost accounting inside the SplashMX IR.

### E-026 — Starlark demonstrates deterministic/hermetic embedded-language restrictions

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Starlark specifies deterministic/hermetic execution, no ambient environment access by default, and deliberately restricted control flow (including no unbounded loops/recursion in its intended model).

Source: https://github.com/bazelbuild/starlark/blob/master/spec.md

**Implication:** language restriction can support reproducibility/safety without making the authoring system inherently toy-like; SplashMX does not adopt Starlark itself.

## Hypothesis review snapshots

### SMX-001

H-001–H-018: **unresolved**; baseline added corpus/scorecard only.

### SMX-002

- H-001: **strengthened**.
- H-002: **strengthened**.
- H-003: **strengthened, still provisional**.
- H-008: **strengthened**.

### SMX-003

- H-002: **strengthened further**.
- H-003: **strengthened**.
- H-004: **strengthened**; portable packaging still pending SMX-013.
- H-005: **unresolved / no direct status change**.

### SMX-004

- H-005: **strengthened** — executable hot-swap/state/continuation reconciliation now exists at model level.
- H-006: **strengthened** — beginner and advanced behaviours use one validated bounded-turn IR in the harness.
- H-009: **strengthened narrowly at execution boundary, still unresolved end-to-end** — validation, explicit services/capabilities, optional denial, and hard budgets are demonstrated; real sandbox attacks remain SMX-006/016.
- Others: no status change.

Detailed evidence: `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md` and companion fixture/harness artifacts.

## Open architectural questions

### O-001 — Minimal universal port vocabulary

**Status:** RESOLVED PROVISIONALLY by SMX-004.

Current candidate: command/event/directional-value. No first-class synchronous cross-Thing query; snapshot reads use values and request/response is asynchronous. Revisit only with evidence from SMX-010/015 showing the model cannot support required cases.

### O-002 — Where behaviour state lives

**Status:** RESOLVED at current execution-semantic level; persistence remains downstream.

Private runtime state belongs to stable behaviour attachment identity, not the code version. SMX-004 defines same-schema retention, explicit bounded migration, and continuation reconciliation. SMX-005/007 must encode/serialize/restore it.

### O-003 — Definition/instance model

**Status:** RESOLVED PROVISIONALLY by SMX-003.

Stable local-definition graph + concrete instance graph + sparse explicit overlay, with explicit reconciliation between immutable base revisions.

### O-004 — Canonical encoding

Human-readable, binary, database-like, or hybrid representation remains open. It must encode Thing/Definition/Revision/Element/Port/BehaviourAttachment identities, overlays, behaviour IR/version, private-state schemas, continuations, conflicts, partial loading, and migration.

Owner: SMX-005.

### O-005 — Runtime IR shape

**Status:** RESOLVED PROVISIONALLY by SMX-004 at semantic level.

Current candidate: validated bounded-turn handler IR with pure expressions, transactional own-Thing/private-state writes, command/event/value communication, explicit deterministic randomness, logical timers/continuations, asynchronous mediated services, and hard resource budgets. Production encoding/compiler/Godot mapping/performance remain open for later issues.

### O-006 — Multiplayer replication boundary

State/event/input/snapshot/hybrid replication must align with Thing authority and browser/server topology. SMX-004 supplies ordered external-input and async-service semantics but does not choose replication mechanics.

Owner: SMX-010/017.

### O-007 — Collaboration substrate

Stable base-revision/overlay/reconciliation loci are inputs, not a conflict-resolution algorithm. Desired user-visible concurrent-edit semantics remain open.

Owner: SMX-011/018.

### O-008 — Durable identity namespace and tombstones

Exact generation format, namespace scope, cross-package addressing, non-reuse, tombstone lifetime, and unresolved/destroyed reference representation remain open.

Owner: SMX-005/007.

### O-009 — Canonical reconciliation/conflict transaction model

Exact transaction/conflict schemas, revision ancestry, rollback, and collaboration interaction remain open.

Owner: SMX-005/011.

### O-010 — Executor-state serialization and restore semantics

Exact representation/lifecycle of behaviour-private state, attachment order, pending timers/continuations, deterministic PRNG state/draw position, pending service/network correlations, and fault/suspension state remains open.

Owner: SMX-005/007.

### O-011 — Hard-budget quota values and quarantine/throttling policy

SMX-004 requires enforceable hard limits but does not choose product/runtime quota values or whether broader package/tick overuse defers, suspends, quarantines, or terminates offending causal chains.

Owner: SMX-006/016 with performance evidence from SMX-009/019 where relevant.

## Maintenance rule

When an issue resolves or materially changes an entry here, update this file in the same PR or explicitly supersede it with an ADR referenced here. Do not allow stale early assumptions to remain indistinguishable from current decisions.
