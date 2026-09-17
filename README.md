# SplashMX

SplashMX is a research-first project exploring a modern creative-computing environment: the kind of integrated, approachable, web-native authoring/player/publishing platform that could have followed Flash, but designed around modern object composition, streaming, multiplayer, collaboration, sandboxing, portability, and long-term compatibility.

This repository begins as a pre-architecture research programme. The current goal is not to build a Flash clone or prematurely commit to a Godot-shaped editor. The goal is to discover and validate a coherent platform architecture before production implementation hardens the wrong abstractions.

## Start here

- [`AGENTS.md`](AGENTS.md) — autonomous work and evidence protocol.
- [`docs/00-PROJECT-CONSTITUTION.md`](docs/00-PROJECT-CONSTITUTION.md) — product invariants and non-goals.
- [`docs/01-RESEARCH-ROADMAP.md`](docs/01-RESEARCH-ROADMAP.md) — dependency-ordered research campaign.
- [`docs/02-ARCHITECTURE-HYPOTHESES.md`](docs/02-ARCHITECTURE-HYPOTHESES.md) — hypotheses to test rather than assumptions to preserve.
- [`docs/03-RAG-INDEX.md`](docs/03-RAG-INDEX.md) — retrieval-oriented map of authoritative material.
- [`docs/04-ISSUE-EXECUTION-PROTOCOL.md`](docs/04-ISSUE-EXECUTION-PROTOCOL.md) — required issue/PR/CI/merge workflow.
- [`docs/05-DECISION-AND-EVIDENCE-LOG.md`](docs/05-DECISION-AND-EVIDENCE-LOG.md) — durable record for accepted, rejected, and unresolved findings.

## Working principle

**Hierarchy describes composition and locality, not behavioural ownership.**

A SplashMX object should be able to carry its own intent, state, controls, capabilities, persistence semantics, and networking semantics across containers, scenes, peers, packages, and streaming boundaries. Godot is currently the intended runtime substrate, not the public object model or long-term interchange contract.
