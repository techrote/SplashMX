# SplashMX production implementation programme v1

**Status:** active execution decomposition of the Architecture-v1 production roadmap  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Roadmap authority:** `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md`  
**Issue range:** SMX-021 through SMX-052 / GitHub issues #46 through #77  
**Date:** 2026-09-19

This document turns the frozen implementation roadmap into merge-sized production work. It is an **execution and coordination map, not a new architecture layer**. If it conflicts with the constitution, Architecture v1, an accepted ADR, or the roadmap, the higher authority wins and this programme must be repaired.

## Contents

| Section | Summary |
|---|---|
| 1. Programme rules | Defines issue sizing, dependency, merge and architecture-change rules. |
| 2. Phase/issue index | Maps SMX-021–052 to roadmap phases and concrete GitHub issues. |
| 3. Dependency graph | Records the hard dependency edges used for autonomous scheduling. |
| 4. Concurrency windows | Identifies work that can safely overlap without bypassing gates. |
| 5. Structural critical path | Highlights the main serial spine to first product/release qualification. |
| 6. Spike policy | Defines how bounded mechanism-selection spikes interact with frozen semantics. |
| 7. Gate policy | Defines the phase gates that downstream production work may not bypass. |
| 8. Agent ownership and branch discipline | Prevents overlapping agents from silently owning the same implementation surface. |
| 9. Completion and handoff rules | Defines what must be recorded before an issue is considered complete. |
| 10. Immediate execution order | States what should start now and what opens next. |

## 1. Programme rules

1. Architecture v1 remains frozen. Implementation choices below its semantic boundary may vary; genuine semantic contradictions require the ADR/amendment procedure.
2. Every SMX-021–052 issue is intended to end in one independently reviewable PR with durable production or bounded-spike evidence.
3. Closed pre-v1 experiments are evidence contracts, not production code by inertia. Port semantic/adversarial fixtures to real boundaries.
4. Hard dependencies below are mandatory. A later issue may inspect or prepare around a dependency, but it may not merge production behavior that assumes an unmet gate.
5. Simple local/offline create → play → save/reload remains a continuous product gate as the system expands.
6. Security gates untrusted/public breadth. Collaboration/network/distribution may perform bounded preparatory spikes earlier, but production remote/untrusted-input implementations may not bypass SMX-041.
7. Protected media, path-independent identity, exact offline closure, runtime/collaboration separation, no ambient authority and generic publication remain cross-cutting release constraints.
8. Issue bodies are executable scopes. If implementation evidence changes a dependency or exposes a missing task, update this programme and the affected issue bodies rather than relying on chat-only coordination.

## 2. Phase/issue index

| Phase | SMX | GitHub | Work package | Hard dependencies |
|---|---|---:|---|---|
| P0 | SMX-021 | [#46](https://github.com/techrote/SplashMX/issues/46) | Bootstrap production conformance guardrails | — |
| P1 spike | SMX-022 | [#47](https://github.com/techrote/SplashMX/issues/47) | Select canonical physical encoding + crash-consistent local store | #46 |
| P1 | SMX-023 | [#48](https://github.com/techrote/SplashMX/issues/48) | Canonical semantic kernel, identities, relations + transactions | #46 |
| P1 | SMX-024 | [#49](https://github.com/techrote/SplashMX/issues/49) | Protected assets, canonical serialization + migration envelope | #47, #48 |
| P1 | SMX-025 | [#50](https://github.com/techrote/SplashMX/issues/50) | Crash-safe local project persistence | #49 |
| P2 | SMX-026 | [#51](https://github.com/techrote/SplashMX/issues/51) | Common IR, Rule compiler, scheduler + resource budgets | #48 |
| P2 | SMX-027 | [#52](https://github.com/techrote/SplashMX/issues/52) | Principal capabilities + trusted host-service boundary | #48, #51 |
| P2 | SMX-028 | [#53](https://github.com/techrote/SplashMX/issues/53) | Transactional Behaviour hot replacement + pending-work migration | #49, #51, #52 |
| P3 | SMX-029 | [#54](https://github.com/techrote/SplashMX/issues/54) | Lifecycle, WorldSave, snapshot + fresh-process restore | #50, #53 |
| P3 | SMX-030 | [#55](https://github.com/techrote/SplashMX/issues/55) | Logical streaming, exact acquisition + local immutable cache | #49, #50, #54 |
| P3 gate | SMX-031 | [#56](https://github.com/techrote/SplashMX/issues/56) | Production-core vertical conformance gate | #53, #54, #55 |
| P4 | SMX-032 | [#57](https://github.com/techrote/SplashMX/issues/57) | Minimal browser authoring shell over production core | #56 |
| P4 gate | SMX-033 | [#58](https://github.com/techrote/SplashMX/issues/58) | Browser play/save diagnostics, accessibility baseline + measured acceptance | #57 |
| P5 spike | SMX-034 | [#59](https://github.com/techrote/SplashMX/issues/59) | Select package resolver/container/distribution mechanisms | #49, #55, #52 |
| P5 | SMX-035 | [#60](https://github.com/techrote/SplashMX/issues/60) | Production package + portable-component system | #53, #55, #59, #52 |
| P5 gate | SMX-036 | [#61](https://github.com/techrote/SplashMX/issues/61) | Immutable publication, generic player + exact offline closure | #54, #58, #60 |
| P6 spike | SMX-037 | [#62](https://github.com/techrote/SplashMX/issues/62) | Select production Godot realization + scheduler integration | #56 |
| P6 | SMX-038 | [#63](https://github.com/techrote/SplashMX/issues/63) | Production Godot adapters + web/native/headless profiles | #61, #62 |
| P7 spike | SMX-039 | [#64](https://github.com/techrote/SplashMX/issues/64) | Select sandbox, decoder + cryptographic trust mechanisms | #60, #63 |
| P7 | SMX-040 | [#65](https://github.com/techrote/SplashMX/issues/65) | Harden parser, trust, runtime + decoder boundaries | #52, #60, #63, #64 |
| P7 gate | SMX-041 | [#66](https://github.com/techrote/SplashMX/issues/66) | Production untrusted-content security gate | #61, #65 |
| P8 spike | SMX-042 | [#67](https://github.com/techrote/SplashMX/issues/67) | Select collaboration sync/store substrate + compaction | #48, #50 |
| P8 | SMX-043 | [#68](https://github.com/techrote/SplashMX/issues/68) | Production collaboration sync/store/conflicts/history | #66, #67, #50, #48 |
| P8 gate | SMX-044 | [#69](https://github.com/techrote/SplashMX/issues/69) | Collaboration conformance + browser People workflow | #58, #68 |
| P9 spike | SMX-045 | [#70](https://github.com/techrote/SplashMX/issues/70) | Select network deployment/auth/signalling mechanisms | #63, #66 |
| P9 | SMX-046 | [#71](https://github.com/techrote/SplashMX/issues/71) | Production networking services/authority/reconnect/relevance | #55, #63, #66, #70 |
| P9 gate | SMX-047 | [#72](https://github.com/techrote/SplashMX/issues/72) | Topology-equivalence + hostile-network failure campaign | #71 |
| P10 spike | SMX-048 | [#73](https://github.com/techrote/SplashMX/issues/73) | Human usability + accessibility study | #58 |
| P10 spike | SMX-049 | [#74](https://github.com/techrote/SplashMX/issues/74) | Historical compatibility + runtime-retention programme | #49, #61 |
| P10 | SMX-050 | [#75](https://github.com/techrote/SplashMX/issues/75) | Distribution/hosting/runtime retention/native packaging | #61, #63, #66, #69, #72, #74 |
| P10 | SMX-051 | [#76](https://github.com/techrote/SplashMX/issues/76) | Product usability/accessibility/localization/recovery hardening | #69, #72, #73, #75 |
| P10 gate | SMX-052 | [#77](https://github.com/techrote/SplashMX/issues/77) | Final release qualification + supported-target matrix | #75, #76 |

## 3. Dependency graph

The hard graph is intentionally narrower than the roadmap prose so autonomous agents know exactly what must be complete before merge:

```text
#46 P0 guardrails
 ├─> #47 encoding/store spike ─┐
 └─> #48 semantic core ───────┼─> #49 serialization/assets ─> #50 local store
        └─> #51 IR/scheduler ─> #52 capabilities
                 └─────────────┬───────────────> #53 hot replacement
#49 ───────────────────────────┘
#50 + #53 ─> #54 lifecycle/WorldSave ─> #55 streaming/exact acquisition
#53 + #54 + #55 ─> #56 production-core gate

#56 ─> #57 browser shell ─> #58 browser gate
#49 + #55 + #52 ─> #59 package spike
#53 + #55 + #59 + #52 ─> #60 packages/components
#54 + #58 + #60 ─> #61 publish/generic player

#56 ─> #62 Godot spike
#61 + #62 ─> #63 production Godot profiles
#60 + #63 ─> #64 security-mechanism spike
#52 + #60 + #63 + #64 ─> #65 security hardening
#61 + #65 ─> #66 untrusted-content security gate

#48 + #50 ─> #67 collaboration spike
#66 + #67 + #50 + #48 ─> #68 collaboration implementation
#58 + #68 ─> #69 collaboration gate

#63 + #66 ─> #70 network-deployment spike
#55 + #63 + #66 + #70 ─> #71 production networking
#71 ─> #72 topology gate

#58 ─> #73 human study
#49 + #61 ─> #74 compatibility programme
#61 + #63 + #66 + #69 + #72 + #74 ─> #75 distribution/operations
#69 + #72 + #73 + #75 ─> #76 product hardening
#75 + #76 ─> #77 final qualification
```

## 4. Concurrency windows

**Window A — immediately after SMX-021/#46:** run SMX-022/#47 and SMX-023/#48 concurrently. Physical encoding/store selection must not stall logical semantic-kernel implementation.

**Window B — after the logical kernel:** SMX-026/#51 can begin once #48 lands while #47/#49/#50 continue. This deliberately overlaps bounded execution with persistence work where their contracts are already frozen.

**Window C — early long-horizon risk reduction:** SMX-042/#67 may start as soon as #48 and #50 are complete. It is a bounded collaboration-substrate spike only; production collaboration #68 still waits for the security gate #66.

**Window D — after the production-core gate #56:** browser authoring #57 and Godot-binding spike #62 can start together. Package mechanism selection #59 may also begin as soon as #49/#55/#52 are complete.

**Window E — after the minimal browser gate #58:** human study #73 should start early and run alongside package/Godot/security work. Its findings feed product hardening rather than unnecessarily serializing backend work.

**Window F — after publication and Godot/security foundations:** historical compatibility #74 may run alongside Phase 7–9; collaboration #68 and network-deployment spike #70 split after #66 and can proceed independently.

The graph intentionally keeps **implementation** of collaboration/network/distribution behind the relevant security/runtime gates while allowing bounded evidence-gathering spikes earlier where they cannot create public authority or semantic commitments.

## 5. Structural critical path

Without duration estimates, the principal serial spine is approximately:

`#46 → #48 → #51 → #52 → #53 → #54 → #55 → #56 → #57 → #58 → #60/#61 → #63 → #64 → #65 → #66 → (#68→#69 and #70→#71→#72) → #75 → #76 → #77`

#47/#49/#50 and #59 are also required joins into that spine. The highest-value schedule optimization is therefore **not** to start many late feature issues early; it is to run the explicitly safe spikes and logical/physical work in parallel so those joins are already resolved when the main spine reaches them.

## 6. Spike policy

The seven explicit mechanism/evidence spikes in this programme are:

- #47 canonical physical encoding/store;
- #59 package resolver/container/distribution;
- #62 Godot realization/performance;
- #64 sandbox/decoder/crypto;
- #67 collaboration substrate/compaction;
- #70 network deployment/auth/signalling;
- #73 human usability/accessibility;
- #74 historical compatibility/runtime retention.

A spike may create experiments, measurements and a decision handoff. It must not silently become the production implementation issue that follows it. If a spike selects a mechanism below the frozen boundary, record the selection and proceed. If it falsifies Architecture v1, stop normal implementation at the affected boundary and invoke the ADR/amendment procedure.

## 7. Gate policy

The programme has six explicit merge/release gates in addition to ordinary issue acceptance:

- **#56 production-core gate:** downstream UI/platform breadth must use the real production semantic/execution/persistence core.
- **#58 browser gate:** the real browser create→play→save/reload path and baseline accessibility/diagnostics must work.
- **#61 publishing gate:** immutable publication/generic player/exact offline closure must work before production target breadth.
- **#66 security gate:** remote/untrusted production breadth may not proceed as supported until the physical hostile-content boundary passes.
- **#69/#72 collaboration and multiplayer gates:** each distributed consistency system must independently pass its destructive production campaign.
- **#77 release gate:** all relevant Architecture-v1 conformance gates and supported-target evidence must be green on the release candidate.

Passing an earlier research harness does not satisfy these gates.

## 8. Agent ownership and branch discipline

One implementation agent should own one active SMX issue/branch at a time unless an issue explicitly delegates bounded sub-work. Agents may inspect overlapping branches but must not modify another issue's branch without explicit recovery/coordination.

When parallel issues touch a shared interface:

- the earlier dependency owns the interface contract until merged;
- downstream agents may prepare adapters/tests against current `main`, but must rebase/reconcile after the dependency lands;
- shared fixture/schema changes belong with the earliest issue that semantically owns them;
- do not copy a dependency's implementation into a downstream branch to avoid waiting;
- record any newly discovered dependency edge in both issue bodies and this programme document.

Spikes should prefer isolated experiment paths and decision documents. Production issues should prefer durable source/test locations established by SMX-021.

## 9. Completion and handoff rules

Every issue closes only after its PR is merged, required checks are green, the result is verified on `main`, and its acceptance criteria are actually satisfied. Each completion record should state:

- exact merged commit/result;
- production modules/interfaces now owned;
- conformance/adversarial fixtures ported or added;
- measured environment where relevant;
- residual risks or downstream assumptions;
- whether Architecture v1 remained unchanged;
- newly unlocked issues.

If a blocker is external rather than technical—for example human-study participants or unavailable target hardware—record the missing resource precisely and leave the affected issue open rather than weakening its gate.

## 10. Immediate execution order

The production programme starts with **SMX-021 / #46 only**. It establishes the production module/conformance substrate that every later implementation issue relies on.

When #46 is genuinely complete:

1. start **SMX-022 / #47** and **SMX-023 / #48** in parallel;
2. after #48, **SMX-026 / #51** may begin even if the physical-store path is still progressing;
3. converge the logical and physical branches at **SMX-024 / #49**, then drive to the first major programme checkpoint, **SMX-031 / #56**.

Do not start downstream production feature work merely because its research predecessor exists; use the dependency graph above.
