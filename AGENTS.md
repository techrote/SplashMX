# SplashMX autonomous research and development protocol

This repository is research-first but has now completed its pre-Architecture-v1 campaign. Agents are expected to preserve the frozen semantic architecture, resolve implementation uncertainty with evidence and falsifiable prototypes, and amend architecture only when new evidence demonstrates a real contradiction.

## Authority and required reading

For every issue, read the issue body and all documents it names. Unless an issue explicitly narrows the work, the following project-wide documents remain authoritative:

1. `docs/00-PROJECT-CONSTITUTION.md`
2. `docs/architecture/ARCHITECTURE-V1.md`
3. `docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md`
4. `docs/architecture/ARCHITECTURE-V1-AUDIT.json`
5. `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md` for production implementation work
6. `docs/03-RAG-INDEX.md`
7. `docs/04-ISSUE-EXECUTION-PROTOCOL.md`
8. `docs/05-DECISION-AND-EVIDENCE-LOG.md`

`docs/01-RESEARCH-ROADMAP.md` and `docs/02-ARCHITECTURE-HYPOTHESES.md` now contain post-freeze closure and point to exact historical pre-v1 snapshots. Retrieve historical research/specifications/fixtures when a task touches their domain, but do not let provisional research wording override the constitution, Architecture v1, or a later accepted ADR.

An issue may refine an implementation or, with evidence, propose an architecture amendment, but must not silently weaken a product invariant or frozen semantic boundary. If evidence forces an architectural change, document the conflict explicitly, add the smallest justified ADR/amendment and regression, and reconcile all dependent contracts in the same PR.

## Research and implementation discipline

Distinguish these classes of statement in notes and PRs:

- **Fact** — supported by current primary evidence or reproducible measurement.
- **Hypothesis** — a design proposition that still requires testing.
- **Decision** — an accepted project choice with recorded rationale and consequences.
- **Open question** — important uncertainty not yet resolved.

Prefer primary sources: upstream Godot documentation/source, web-platform specifications, protocol specifications, and reproducible local experiments. Secondary commentary may identify questions but must not be the sole basis of an architectural contract.

Research and implementation spikes are expected to attempt to **disprove** the preferred design, not merely collect supporting evidence. Passing an old model-level harness does not certify a new production parser, runtime, sandbox, store, transport, or editor implementation; port the semantic/adversarial fixture to the real boundary.

## Product boundary

Godot is the intended first execution/rendering substrate. It is not the SplashMX public object model, package format, scripting contract, network protocol, or long-term compatibility boundary.

Do not expose Godot concepts to authors merely because they are convenient internally. In particular, do not assume that `Node`, `SceneTree`, `Resource`, `RID`, `ResourceUID`, GDScript, Godot RPC semantics, peer IDs, or Godot resource paths become public SplashMX contracts.

The frozen architectural rule is:

> **Hierarchy describes composition and locality, not behavioural ownership.**

Objects/groups/local classes carry or explicitly declare their own intent, state, behaviours, ports, capabilities, persistence, and network semantics. Containers may provide context and coordination without becoming the hidden owner of constituent meaning.

## Prototype discipline

Research prototypes may be ugly and disposable. Keep them narrow, instrumented, deterministic where relevant, and easy to remove. A prototype exists to answer a named question, with explicit pass/fail observations.

Do not turn a research harness into production architecture by inertia. `docs/architecture/IMPLEMENTATION-ROADMAP-V1.md` classifies the pre-v1 harness family as reusable conformance evidence, reference-only/disposable implementation, or work that must be rewritten/selected for production.

When performance is relevant, record hardware/browser/runtime/version, workload, sample size, and metric definition. When determinism is relevant, include fixed fixtures and exact expected results.

## Required issue workflow

For each implementation or research issue:

1. Start from current `main` and verify declared dependencies are complete.
2. Read the authoritative issue and referenced project documents, including Architecture v1 for production work.
3. Inspect existing decisions, open/closed issues, accepted work, and the relevant historical evidence to avoid contradiction or duplication.
4. Research current upstream facts required by the issue.
5. Implement the smallest production artefacts, tests, fixtures, documentation, or prototypes needed to satisfy the issue.
6. Reconcile all affected documentation; do not leave conclusions only in PR discussion.
7. Add or update automated checks for executable claims and frozen conformance boundaries where practical.
8. Open a PR referencing the issue and summarising evidence, rejected alternatives, residual uncertainty, and compatibility impact.
9. Repair CI if required. Do not merge while required automated checks are failing, cancelled, or still pending.
10. Merge only after required automated checks pass.
11. Verify the merge commit/result is present on `main` and required post-merge checks pass where they are part of the issue gate.
12. Close the issue only when every acceptance criterion is genuinely satisfied. If blocked, record precise evidence and leave the issue open.

Do not claim success based solely on compilation. Validate the behavioural/research claim the issue is actually about.

## Branch, commit, and PR conventions

Use issue-prefixed names where practical, e.g. `smx-021-canonical-core`.

PR descriptions should contain:

- issue and implementation/research question;
- what changed;
- evidence and tests;
- alternatives examined/rejected;
- new or changed decisions;
- residual risks/open questions;
- Architecture-v1 compatibility impact;
- exact validation commands or CI checks.

## Security stance

Assume community creations/components are untrusted. Never make arbitrary GDScript, native extensions, browser JavaScript access, filesystem access, arbitrary HTTP/raw networking, or ambient host authority part of the default user-content execution contract.

Security-sensitive work must include adversarial cases, resource-exhaustion cases, malformed packages/documents/IR/assets, authority-confusion cases, and target-specific boundary checks where relevant. Production security claims require evidence at the real parser/decoder/runtime/adapter boundary, not only the pre-v1 Python models.

## Compatibility stance

Prefer stable SplashMX-owned identifiers, schemas, IR, manifests, migrations and exact immutable revisions over Godot-internal identities whenever content is expected to survive engine upgrades. Old content longevity is a first-order requirement, not a packaging detail.

The protected media contract is cross-cutting: stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence/attribution + derivation revision. Storage, collaboration, packages, target transcodes/imports, caches, networking, publishing and migration must not field-mix or replace that canonical meaning.

## Post-freeze architecture-change rule

If implementation evidence contradicts Architecture v1, do not hide the contradiction in an adapter or weaken a regression. Retrieve the relevant pre-v1 evidence, identify the exact frozen decision affected, create an explicit ADR/amendment, reconcile downstream contracts, and add adversarial regression coverage. Implementation choices below the frozen semantic boundary do not require an architecture amendment merely because the selected library or physical encoding differs from a research prototype.