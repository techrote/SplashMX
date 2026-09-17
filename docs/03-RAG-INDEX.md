# SplashMX RAG index

This file is a retrieval-oriented map for autonomous agents. It identifies which repository documents and external primary sources should be consulted for each class of question. It is intentionally concise and should point to durable source material rather than duplicate it.

## Always retrieve first

1. `AGENTS.md` — autonomous workflow, evidence discipline, security/compatibility stance.
2. `docs/00-PROJECT-CONSTITUTION.md` — immutable-until-amended product invariants and non-goals.
3. `docs/01-RESEARCH-ROADMAP.md` — research dependency order and gates.
4. `docs/02-ARCHITECTURE-HYPOTHESES.md` — propositions that must be tested rather than assumed.
5. `docs/04-ISSUE-EXECUTION-PROTOCOL.md` — branch/PR/CI/merge/closure requirements.
6. `docs/05-DECISION-AND-EVIDENCE-LOG.md` — accepted/rejected findings and source freshness notes.
7. The active GitHub issue, its dependency issues, and merged PRs for those dependencies.

## Retrieval map by topic

| Question/topic | Retrieve repository material | Also inspect |
|---|---|---|
| Product scope / “Flash successor” intent | Constitution, Roadmap | Current issue |
| Thing/object/kernel semantics | Hypotheses H-001–H-004, SMX-001/002 docs | Dependency PR evidence |
| Composition/local classes/instances | H-002–H-005 | SMX-003 outputs |
| Behaviour/rules/scripting/IR | H-005/H-006 | SMX-004 outputs |
| IDs/references/schema/canonical format | H-007/H-008/H-018 | SMX-005 outputs |
| Security/sandbox/capabilities | Constitution P9, H-009 | SMX-006/016 outputs; current platform primary docs |
| Lifecycle/serialization/determinism | H-008/H-010 | SMX-007/015 outputs |
| Streaming/hot swap | H-005/H-010/H-011 | SMX-008/015 outputs |
| Godot mapping/browser limits | H-007/H-014/H-015 | SMX-009 outputs; current Godot primary docs/source |
| Multiplayer | Constitution P7, H-012/H-013 | SMX-010/017 outputs; current browser/Godot transport docs |
| Collaborative editing | Constitution P8, H-013/H-017 | SMX-011/018 outputs; CRDT/OT/local-first primary material |
| Editor UX/progressive disclosure | P1–P3, H-016 | SMX-012/019 outputs |
| Component ecosystem | P9/P13, H-004/H-009 | SMX-013/016 outputs |
| Publishing/player/server | P10–P12, H-014/H-015/H-018 | SMX-014/017/019 outputs |
| Architecture freeze | Everything above | All merged research PRs and open blockers |

## Initial external primary-source anchors

These links are research starting points, not frozen truths. Relevant issues must re-check current upstream documentation/source and record date/version used.

### Godot web editor

- https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

Questions: browser editor limitations, IndexedDB/project storage, export capability, renderer support, debugging/GDExtension/C# limitations.

### Godot web export

- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

Questions: single-threaded versus threaded builds, cross-origin isolation, JavaScript bridge/eval hardening, WebAssembly/WebGL constraints, browser lifecycle behaviour.

### Godot runtime I/O and packaging

- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html

Questions: runtime asset loading, PCK/ZIP behaviour, untrusted-pack security implications, mod/pack semantics.

### Godot networking

- https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/stable/classes/class_websocketmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/classes/class_webrtcmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

Questions: SceneTree coupling, browser transports, WebRTC mesh properties, dedicated/headless execution, which layers are implementation substrate versus public contract.

### Browser/platform primary sources

Relevant issues should prefer current specifications or authoritative browser documentation for WebAssembly, WebRTC, WebSocket, IndexedDB, File System Access where applicable, CSP, cross-origin isolation, workers, storage quotas, and permissions.

### Collaboration research

Potential starting point, not a selected dependency:

- https://automerge.org/docs/

Relevant issues must compare desired SplashMX conflict semantics against multiple approaches rather than selecting a CRDT library first.

## RAG authoring rules

When adding research material:

- use stable headings and explicit IDs (`H-###`, `SMX-###`, `ADR-###`, `E-###`) so retrieval can target concepts precisely;
- keep conclusions close to evidence links/fixtures;
- record rejected alternatives and why, not only the chosen answer;
- avoid giant chronological notebooks as the only source of truth;
- promote durable conclusions into authoritative docs and keep experiments/prototypes separately identifiable;
- date/version external claims likely to change;
- distinguish current facts from hypotheses and decisions.

## Expected future retrieval artefacts

Research issues may add topic-specific documents under `docs/research/`, ADRs under `docs/adr/`, schemas under `spec/`, and disposable experiments under `experiments/`. When they do, update this index so later agents can retrieve the minimum complete authoritative set without reconstructing context from commit history.
