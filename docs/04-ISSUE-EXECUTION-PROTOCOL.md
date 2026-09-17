# SplashMX issue execution protocol

This document defines the required autonomous completion pattern for `SMX-###` issues.

## Before starting

1. Read `AGENTS.md` and all documents in the issue's **Required context** section.
2. Inspect the dependency issues and their merged PRs. Do not rely only on issue summaries when the merged artefacts contain the actual specification/evidence.
3. Confirm dependencies are genuinely complete on `main`.
4. Search open and closed issues for overlapping work or newly discovered contradictions.
5. Refresh time-sensitive upstream facts from primary sources.

If a dependency is incomplete or contradictory, do not fake progress around it. Record the blocker precisely in the issue/PR and stop with the issue open unless the active issue explicitly authorises repairing the dependency.

## Research issue structure

A research issue should produce, as applicable:

- explicit research questions;
- evaluated alternatives;
- source/evidence register with dates/versions;
- representative and adversarial fixtures;
- minimal executable prototype(s) where prose alone cannot resolve uncertainty;
- measured observations;
- failure cases and counterexamples;
- update to the hypothesis register;
- durable decision/ADR only where evidence justifies one;
- residual uncertainty and follow-on implications.

A literature summary by itself is not completion when the issue asks whether a mechanism works in practice.

## Change discipline

Keep production-like code separate from disposable experiments. Preferred locations:

- `docs/research/SMX-###-*.md` — research synthesis;
- `docs/adr/ADR-###-*.md` — accepted architectural decisions;
- `experiments/smx-###-*` — disposable falsification harnesses;
- `spec/` — candidate schemas/IR/contracts once sufficiently stable;
- `tests/` — durable fixtures and invariant checks.

Do not create a stable `spec/` contract merely because an experiment needs a data structure. Promote only after evidence warrants it.

## Automated checks

Every PR must run the repository's required automated checks. Issues that add executable claims should add deterministic checks for those claims where practical.

Suitable checks include:

- schema validation;
- deterministic fixture equality;
- serialization round trips;
- capability-denial tests;
- malformed-input tests;
- state migration fixtures;
- protocol/IR conformance tests;
- browser/headless smoke tests;
- static documentation/reference validation.

Performance observations must not be converted to brittle CI thresholds unless the test environment makes that meaningful.

## PR requirement

Every `SMX-###` issue is completed through a PR, even if the primary output is research documentation.

The PR must:

- reference the issue;
- list exact acceptance criteria and their status;
- summarise evidence and counterevidence;
- identify rejected alternatives;
- state which `H-###` hypotheses were strengthened/refined/weakened/rejected/unresolved;
- identify compatibility/security implications;
- list commands/checks used;
- reconcile affected authoritative docs.

## Merge rule

The agent working an issue is authorised to merge its own PR **only after all required automated checks pass**.

Do not merge when:

- required checks are failing;
- required checks are cancelled;
- required checks are still pending;
- a known acceptance criterion is unsatisfied;
- the PR contains an unresolved contradiction with an authoritative project invariant.

Repair CI and rerun checks as necessary. Do not weaken a meaningful test merely to obtain green CI without documenting and justifying the change.

## Post-merge verification

After merge:

1. verify the PR is actually merged;
2. verify the merge/head result is present on current `main`;
3. verify expected files/specs/tests are retrievable from `main`;
4. close the issue only if all acceptance criteria are satisfied;
5. leave a precise blocker/follow-up record for any intentionally unresolved matter.

Issue closure is evidence of completion, not a project-management convenience.

## Architecture changes

Before SMX-020, architecture remains provisional. Research may amend earlier conclusions when new evidence warrants it.

When changing an accepted decision:

- identify the prior decision explicitly;
- explain the new evidence;
- describe migration/compatibility implications;
- update dependent specifications and RAG references;
- do not leave mutually contradictory authoritative documents.

## Autonomous scope

Agents should make reasonable implementation/research decisions without asking for routine approval. Escalate only when the evidence exposes a genuinely product-defining choice not resolved by the constitution, or when external credentials/resources unavailable to the agent are indispensable.

When blocked, preserve the exact state, evidence, commands, errors, source versions, and next action so another agent can resume without rediscovery.
