# SplashMX Architecture v1 document set

Architecture v1.0 was frozen by SMX-020 on 2026-09-19 after the SMX-001–SMX-019 research and destructive-validation programme.

Read these files in order:

1. `ARCHITECTURE-V1.md` — the frozen durable semantic contract. This is the primary architecture authority beneath the project constitution.
2. `ADR-0001-ARCHITECTURE-V1-FREEZE.md` — why the freeze exists, precedence/supersession rules, and how a future contradiction must be handled.
3. `ARCHITECTURE-V1-AUDIT.json` — machine-readable H-001–H-018 closure, cross-domain contradiction audit, incorporated corrective findings, protected-media fields, and residual implementation-risk classes.
4. `IMPLEMENTATION-ROADMAP-V1.md` — dependency-ordered production handoff, research-code disposition, verification gates, and remaining implementation spikes.

For topic-specific evidence, use `../03-RAG-INDEX.md`. The exact pre-v1 roadmap, hypothesis chronology, RAG map, and decision/evidence log remain beside their active counterparts as `*.pre-v1.md`; they are retained evidence, not competing current authority.

The protected media rule is cross-cutting: stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence/attribution + derivation revision. No implementation layer may field-mix or replace that canonical meaning with target-private derivatives.