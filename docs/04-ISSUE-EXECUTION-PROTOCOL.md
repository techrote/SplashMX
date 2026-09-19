# SplashMX issue execution protocol

This document defines the required autonomous completion pattern for `SMX-###` production implementation, bounded spike/research, and architecture-maintenance issues after the Architecture v1.0 freeze.

## Before starting

1. Start from current `main` and verify repository identity, working state, and declared dependencies.
2. Read `AGENTS.md`, the active issue, and all documents named in its **Required context** section.
3. For production work, retrieve the minimum post-freeze authority chain from `docs/03-RAG-INDEX.md`, including the constitution, Architecture v1, ADR-0001, the Architecture-v1 audit, and the implementation roadmap.
4. Inspect dependency issues and merged PRs. Retrieve historical research/specifications/fixtures when the task touches their domain; do not reconstruct the entire pre-v1 campaign when the current authority chain is sufficient.
5. Search open and closed issues/PRs for overlapping work, known corrections, or newly discovered contradictions.
6. Refresh time-sensitive upstream facts from primary sources when they materially affect the task.

If a dependency is incomplete or contradictory, do not fake progress around it. Record the blocker precisely and leave the issue open unless the active issue explicitly authorises repairing the dependency.

## Work-product structure

### Production implementation issues

A production issue should produce, as applicable:

- the smallest implementation that satisfies the issue and the relevant Architecture-v1 boundary;
- explicit mapping from implementation modules to the Architecture-v1 responsibilities they own;
- production conformance tests ported from relevant research fixtures/adversarial cases;
- typed failure behaviour at semantic/security/platform boundaries;
- compatibility/version metadata required by the roadmap;
- measured evidence with named hardware/browser/runtime/version when performance is material;
- documentation of rejected implementation alternatives and residual risks;
- an explicit Architecture-v1 compatibility statement.

Passing a pre-v1 model harness does not certify a production parser, runtime, store, decoder, adapter, transport, or editor boundary. Port the relevant semantic/adversarial evidence to the real implementation.

### Bounded research or implementation spikes

A spike should produce, as applicable:

- explicit questions and decision boundary;
- evaluated alternatives;
- dated/versioned primary-source evidence;
- representative and adversarial fixtures;
- the smallest executable prototype needed to distinguish alternatives;
- measured observations and counterexamples;
- a clear conclusion about whether the result selects an implementation below Architecture v1 or exposes a genuine architectural contradiction;
- residual uncertainty and the exact downstream handoff.

A literature summary by itself is not completion when the issue asks whether a mechanism works in practice.

## Change discipline

Keep production code, durable conformance material, and disposable experiments visibly distinct.

Typical locations include:

- `docs/architecture/` — frozen architecture and accepted post-freeze ADRs/amendments;
- `docs/research/SMX-###-*.md` — retained research/spike synthesis and evidence;
- `experiments/smx-###-*` — disposable falsification or selection harnesses;
- `spec/` — production or candidate schemas/IR/contracts only when their stability is justified;
- `tests/` or implementation-local test suites — durable production conformance/regression coverage.

Do not productionize a research harness by inertia. Reuse semantic fixtures and invariants aggressively while independently reviewing prototype algorithms, storage layouts, APIs, and operational assumptions for production suitability.

## Automated checks

Every PR must run the repository's required automated checks. Work that adds or changes executable claims must add deterministic checks where practical.

Suitable checks include:

- schema/document validation;
- deterministic fixture equality and round trips;
- capability-denial and revocation/delegation tests;
- malformed/untrusted-input tests;
- migration/rollback and crash-consistency fixtures;
- protocol/IR conformance tests;
- browser/native/headless smoke or integration tests;
- compatibility tests against supported historical fixtures;
- static documentation/reference/Architecture-v1 validation.

Performance observations must not be converted to brittle CI thresholds unless the test environment makes that meaningful. Record hardware/runtime/workload/sample/metric metadata for performance claims.

## PR requirement

Every `SMX-###` issue is completed through a PR.

The PR must:

- reference the issue;
- list exact acceptance criteria and their status;
- summarise what changed and the evidence/tests;
- identify relevant rejected alternatives;
- state residual risks/open questions;
- state security and compatibility implications;
- state Architecture-v1 compatibility impact;
- list exact validation commands or CI checks;
- reconcile affected authoritative documentation in the same change.

Hypothesis-register edits are not routine post-freeze bookkeeping. Update historical hypothesis material only when a justified Architecture-v1 amendment changes its final disposition or evidence trail.

## Merge rule

The agent working an issue is authorised to merge its own PR **only after all required automated checks pass**.

Do not merge when:

- required checks are failing, cancelled, or still pending;
- a known acceptance criterion is unsatisfied;
- the PR contains an unresolved contradiction with the constitution or Architecture v1;
- a production security/performance/compatibility claim lacks the real-boundary evidence required by the issue.

Repair CI and rerun checks as necessary. Do not weaken a meaningful regression merely to obtain green CI without documenting and justifying the change.

## Post-merge verification

After merge:

1. verify the PR is actually merged;
2. verify the merge result is present on current `main`;
3. verify expected files/specs/tests are retrievable from `main`;
4. verify required post-merge workflows pass where the issue gate requires them;
5. close the issue only if every acceptance criterion is satisfied;
6. leave a precise blocker/follow-up record for any intentionally unresolved matter.

Issue closure is evidence of completion, not a project-management convenience.

## Architecture changes after the v1 freeze

Architecture v1.0 is frozen. Implementation choices below its semantic boundary may select different libraries, physical encodings, storage engines, transports, UI frameworks, or internal representations without reopening the architecture.

If implementation or new research evidence demonstrates a genuine contradiction with a frozen semantic decision:

1. identify the exact Architecture-v1 decision and relevant retained pre-v1 evidence;
2. reproduce the contradiction with the smallest credible fixture/harness;
3. create an explicit ADR/amendment rather than hiding the change in an adapter;
4. describe migration, compatibility, security, authoring, and downstream-contract impact;
5. reconcile Architecture v1, the machine-readable audit, RAG/decision registers, dependent specs, and roadmap as applicable;
6. add adversarial regression coverage so the contradiction cannot silently recur.

Do not weaken or delete a frozen regression merely because an implementation is inconvenient.

## Autonomous scope

Agents should make reasonable implementation/research decisions without asking for routine approval when those choices remain inside the constitution and Architecture-v1 boundaries.

Escalate when evidence exposes a genuinely product-defining or architecture-changing choice not resolved by current authority, or when indispensable external credentials/resources are unavailable.

When blocked, preserve the exact state, evidence, commands, errors, source versions, and next action so another agent can resume without rediscovery.
