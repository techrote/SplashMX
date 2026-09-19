# SplashMX

SplashMX is a modern creative-computing environment for building, animating, programming, sharing, remixing, collaborating on, and playing interactive media with very low technical friction.

The pre-architecture research programme is complete. **Architecture v1.0 was frozen on 2026-09-19**, after the SMX-001 through SMX-020 research, destructive-harness, browser, and real-topology campaigns. The repository is now in the production-implementation phase: implementation work must preserve the frozen semantic architecture unless new evidence demonstrates a genuine contradiction.

## Start here

For production implementation or architecture maintenance, use this authority chain:

- [`AGENTS.md`](AGENTS.md) — autonomous work, evidence, security, compatibility, and architecture-change protocol.
- [`docs/00-PROJECT-CONSTITUTION.md`](docs/00-PROJECT-CONSTITUTION.md) — product invariants and non-goals.
- [`docs/architecture/ARCHITECTURE-V1.md`](docs/architecture/ARCHITECTURE-V1.md) — frozen durable semantic architecture.
- [`docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md`](docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md) — freeze, precedence, supersession, and amendment rules.
- [`docs/architecture/ARCHITECTURE-V1-AUDIT.json`](docs/architecture/ARCHITECTURE-V1-AUDIT.json) — machine-readable hypothesis closure, contradiction audit, retained corrections, and residual-risk classes.
- [`docs/architecture/IMPLEMENTATION-ROADMAP-V1.md`](docs/architecture/IMPLEMENTATION-ROADMAP-V1.md) — dependency-ordered production roadmap and conformance gates.
- [`docs/03-RAG-INDEX.md`](docs/03-RAG-INDEX.md) — retrieval map for the minimum current authority chain plus relevant research evidence.
- [`docs/04-ISSUE-EXECUTION-PROTOCOL.md`](docs/04-ISSUE-EXECUTION-PROTOCOL.md) — required issue/PR/CI/merge workflow.
- [`docs/05-DECISION-AND-EVIDENCE-LOG.md`](docs/05-DECISION-AND-EVIDENCE-LOG.md) — current decision/evidence register and historical pointers.

The completed pre-v1 research roadmap, hypothesis chronology, fixtures, experiments, and destructive-harness material remain evidence. They do not override the constitution, Architecture v1, or later accepted ADRs.

## Working principle

**Hierarchy describes composition and locality, not behavioural ownership.**

SplashMX Things carry or explicitly declare their own intent, state, behaviours, ports, capabilities, persistence semantics, and networking semantics across containers, projects, peers, packages, and streaming boundaries. Godot is the intended first private runtime/rendering substrate, not the public object model or long-term compatibility boundary.
