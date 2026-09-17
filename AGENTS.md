# SplashMX autonomous research and development protocol

This repository is intentionally research-first. Agents working here are expected to resolve uncertainty with evidence and small falsifiable prototypes before turning hypotheses into platform contracts.

## Authority and required reading

For every issue, read the issue body and all documents it names. Unless an issue explicitly narrows the work, the following project-wide documents remain authoritative:

1. `docs/00-PROJECT-CONSTITUTION.md`
2. `docs/01-RESEARCH-ROADMAP.md`
3. `docs/02-ARCHITECTURE-HYPOTHESES.md`
4. `docs/03-RAG-INDEX.md`
5. `docs/04-ISSUE-EXECUTION-PROTOCOL.md`
6. `docs/05-DECISION-AND-EVIDENCE-LOG.md`

An issue may refine a hypothesis but must not silently weaken a product invariant. If evidence forces a constitutional change, document the conflict explicitly and propose the smallest justified amendment in the same PR.

## Research discipline

Distinguish these classes of statement in notes and PRs:

- **Fact** — supported by current primary evidence or reproducible measurement.
- **Hypothesis** — a design proposition that still requires testing.
- **Decision** — an accepted project choice with recorded rationale and consequences.
- **Open question** — important uncertainty not yet resolved.

Prefer primary sources: upstream Godot documentation/source, web-platform specifications, protocol specifications, and reproducible local experiments. Secondary commentary may identify questions but must not be the sole basis of an architectural contract.

Research issues are expected to attempt to **disprove** the preferred design, not merely collect supporting evidence.

## Product boundary

Godot is presently the intended execution/rendering substrate. It is not automatically the SplashMX public object model, package format, scripting contract, network protocol, or long-term compatibility boundary.

Do not expose Godot concepts to authors merely because they are convenient internally. In particular, do not assume that `Node`, `SceneTree`, `Resource`, GDScript, Godot RPC semantics, or Godot resource paths become public SplashMX contracts.

The working architectural rule is:

> **Hierarchy describes composition and locality, not behavioural ownership.**

Objects/groups/local classes should carry or explicitly declare their own intent, state, behaviours, ports, capabilities, persistence, and network semantics. Containers may provide context and coordination without becoming the hidden owner of constituent meaning.

## Prototype discipline

Research prototypes may be ugly and disposable. Keep them narrow, instrumented, deterministic where relevant, and easy to remove. A prototype exists to answer a named question, with explicit pass/fail observations.

Do not turn a research harness into production architecture by inertia.

When performance is relevant, record hardware/browser/runtime/version, workload, sample size, and metric definition. When determinism is relevant, include fixed fixtures and exact expected results.

## Required issue workflow

For each implementation or research issue:

1. Start from current `main` and verify declared dependencies are complete.
2. Read the authoritative issue and referenced project documents.
3. Inspect existing decisions, open/closed issues, and accepted work to avoid contradiction or duplication.
4. Research current upstream facts required by the issue.
5. Implement the smallest research artefacts, tests, fixtures, documentation, or prototypes needed to resolve the issue.
6. Reconcile all affected documentation; do not leave conclusions only in PR discussion.
7. Add or update automated checks for executable claims where practical.
8. Open a PR referencing the issue and summarising evidence, rejected alternatives, residual uncertainty, and compatibility impact.
9. Repair CI if required. Do not merge while required automated checks are failing, cancelled, or still pending.
10. Merge only after required automated checks pass.
11. Verify the merge commit/result is present on `main`.
12. Close the issue only when every acceptance criterion is genuinely satisfied. If blocked, record precise evidence and leave the issue open.

Do not claim success based solely on compilation. Validate the behavioural/research claim the issue is actually about.

## Branch, commit, and PR conventions

Use issue-prefixed names where practical, e.g. `smx-004-behaviour-ir`.

PR descriptions should contain:

- issue and research question;
- what changed;
- evidence and tests;
- alternatives examined/rejected;
- new or changed decisions;
- residual risks/open questions;
- exact validation commands or CI checks.

## Security stance

Assume community creations/components are untrusted. Never make arbitrary GDScript, native extensions, browser JavaScript access, filesystem access, arbitrary HTTP, or ambient host authority part of the default user-content execution contract.

Security-sensitive research must include adversarial cases, resource-exhaustion cases, malformed packages, and authority-confusion cases where relevant.

## Compatibility stance

Prefer stable SplashMX-owned identifiers, schemas, IR, manifests, and migrations over Godot-internal identities whenever content is expected to survive engine upgrades. Old content longevity is a first-order requirement, not a packaging detail.
