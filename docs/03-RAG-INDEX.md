# SplashMX RAG index

This file is a retrieval-oriented map for autonomous agents. It identifies which repository documents and external primary sources should be consulted for each class of question. It is intentionally concise and should point to durable source material rather than duplicate it.

## Always retrieve first

1. `AGENTS.md` — autonomous workflow, evidence discipline, security/compatibility stance.
2. `docs/00-PROJECT-CONSTITUTION.md` — immutable-until-amended product invariants and non-goals.
3. `docs/01-RESEARCH-ROADMAP.md` — research dependency order and gates.
4. `docs/02-ARCHITECTURE-HYPOTHESES.md` — propositions that must be tested rather than assumed.
5. `docs/04-ISSUE-EXECUTION-PROTOCOL.md` — branch/PR/CI/merge/closure requirements.
6. `docs/05-DECISION-AND-EVIDENCE-LOG.md` — accepted/rejected findings and source freshness notes.
7. `docs/research/SMX-001-RESEARCH-BASELINE.md` — authoritative glossary, evaluation method, scorecard, failure conditions, source-freshness policy, and harness conventions.
8. `docs/research/SMX-001-EVALUATION-CORPUS.json` — machine-addressable C-/A-case corpus and scorecard IDs.
9. `docs/research/SMX-002-THING-KERNEL.md` — candidate universal Thing semantics, state/context/relationship taxonomy, port vocabulary, alternatives, corpus mapping, and downstream handoffs.
10. `docs/research/SMX-002-THING-KERNEL-FIXTURES.json` — machine-addressable K-/T-IDs and direct experimental coverage for SMX-002.
11. `docs/research/SMX-003-COMPOSITION-DEFINITIONS.md` — candidate local-definition/instance/overlay semantics, structural conflict policy, exposed interfaces, and downstream handoffs.
12. `docs/research/SMX-003-COMPOSITION-FIXTURES.json` — machine-addressable CMP-/CT-IDs and direct experimental coverage for SMX-003.
13. `docs/research/SMX-004-BEHAVIOUR-EXECUTION.md` — bounded-turn executor semantics, ordering, mutation visibility, determinism, continuations, budgets, and hot-swap contract.
14. `docs/research/SMX-004-BEHAVIOUR-FIXTURES.json` — machine-addressable EXE-/ET-IDs and direct experimental coverage for SMX-004.
15. `docs/research/SMX-005-CANONICAL-DOCUMENT.md` — canonical logical-record/identity/reference/chunk/transaction/migration semantics and encoding-family comparison.
16. `docs/research/SMX-005-DOCUMENT-FIXTURES.json` — machine-addressable DOC-/DT-IDs and direct experimental coverage for SMX-005.
17. The active GitHub issue, its dependency issues, and merged PRs for those dependencies.

## Retrieval map by topic

| Question/topic | Retrieve repository material | Also inspect |
|---|---|---|
| Product scope / “Flash successor” intent | Constitution, Roadmap | Current issue |
| Research terminology / evaluation method | SMX-001 research baseline | Corpus JSON; issue #1 merged PR |
| Thing/object/kernel semantics | SMX-002 Thing kernel, H-001/H-002/H-003/H-008 | SMX-002 fixtures/experiment; C-003/C-004/C-006/C-007/C-020/C-021/C-022/C-025; A-001/A-014/A-016 |
| Composition/local classes/instances | SMX-003 composition research, H-002–H-005, CMP-001–CMP-012 | SMX-003 fixtures/experiment; C-002/C-006/C-007/C-011/C-017/C-018/C-021/C-027; A-001/A-008/A-016 |
| Behaviour/rules/scripting/IR | SMX-004 behaviour execution, H-005/H-006/H-009, EXE-001–EXE-015 | SMX-004 fixtures/experiment; C-003/C-004/C-005/C-009/C-022/C-024/C-025; A-003/A-004/A-006 |
| IDs/references/schema/canonical format | SMX-005 canonical document, H-007/H-008/H-018, DOC-001–DOC-016 | SMX-005 fixtures/experiment; C-006/C-011/C-012/C-018/C-023/C-025/C-026/C-027; A-001/A-002/A-008/A-010/A-012 |
| Security/sandbox/capabilities | Constitution P9, H-009, SMX-002 K-005/K-006, SMX-004 EXE-005/006/009/015, SMX-005 DOC-013/DOC-016 | SMX-006/016 outputs; C-022/A-003/A-004/A-012/A-015; current platform primary docs |
| Lifecycle/serialization/determinism | H-008/H-010, SMX-005 document/runtime/save/context planes, SMX-004 continuation/PRNG/private-state handoff | SMX-007/015 outputs; C-024/A-002 |
| Streaming/hot swap | H-005/H-010/H-011, SMX-005 catalog/chunk/reference-resolution model, SMX-003 public-interface/provenance model, SMX-004 EXE-010–EXE-013 | SMX-008/015 outputs; C-012/C-025/C-027 |
| Godot mapping/browser limits | H-007/H-014/H-015, SMX-005 engine-independent canonical contract, SMX-004 no-Godot execution contract, SMX-001 E-006–E-014 | SMX-009 outputs; current Godot primary docs/source |
| Multiplayer | Constitution P7, H-012/H-013, SMX-002 relationship/context split, SMX-003 CMP-012, SMX-004 ordered external-input/service boundary, SMX-005 runtime/document separation | SMX-010/017 outputs; C-013/C-014/C-020/C-021/A-009/A-011; current browser/Godot transport docs |
| Collaborative editing | Constitution P8, H-013/H-017, SMX-005 semantic transaction/base-revision model, SMX-003 base-revision/overlay/reconcile model | SMX-011/018 outputs; C-016–C-019/A-007/A-008; CRDT/OT/local-first primary material |
| Editor UX/progressive disclosure | P1–P3, H-016, scorecard S-01/S-16, ordinary-group→local-definition promotion, SMX-004 common beginner/advanced IR | SMX-012/019 outputs |
| Component ecosystem | P9/P13, H-004/H-009, SMX-003 local-definition/public-interface model, SMX-004 capability/service/budget hooks, SMX-005 cross-document qualification/assets | SMX-013/016 outputs; C-011/C-022/C-026 |
| Publishing/player/server | P10–P12, H-014/H-015/H-018, SMX-005 feature/version/blob/chunk model | SMX-014/017/019 outputs; C-015/C-023 |
| Architecture freeze | Everything above | All merged research PRs and open blockers |

## SMX-001 baseline retrieval rules

Later research should cite stable corpus IDs rather than paraphrasing test cases inconsistently.

- `C-###` identifies representative cases.
- `A-###` identifies adversarial variants.
- `S-##` identifies architecture scorecard criteria.
- Applicable cases that were not exercised remain explicitly `N/E`, not implicitly passing.
- A hard-gate score of `0` cannot be averaged away by stronger scores elsewhere.

When adding or changing corpus cases, preserve existing IDs and update both baseline Markdown and companion JSON in the same PR.

## SMX-002 kernel retrieval rules

- `K-001` through `K-012` identify candidate semantic invariants.
- `T-001` through `T-007` identify disposable executable fixture classes.
- The Python model in `experiments/smx-002-kernel-model/` is **non-normative**.
- Durable conclusion: stable Thing identity + intrinsic state + optional facets + explicit interfaces + typed relationships, with current grants/authority/engine handles in context.
- Command/event/value was refined by SMX-004: no synchronous cross-Thing query; snapshot values or async request/response are preferred.

## SMX-003 composition retrieval rules

- `CMP-001` through `CMP-012` identify candidate composition/definition invariants.
- `CT-001` through `CT-010` identify disposable executable fixture classes.
- The Python model in `experiments/smx-003-composition-model/` is **non-normative**.
- Durable candidate: **stable local-definition graph + concrete instance graph + sparse explicit overlay**.
- `DefinitionId`, immutable revision identity, `ElementId`, concrete `ThingId`, and stable port IDs are distinct semantic roles.
- `instance-of` is provenance, not control/authority/ownership.
- Compatible base changes propagate to unoverridden loci; valid explicit instance overrides remain authoritative.
- Invalidated override/exposure targets and protected destructive changes are explicit reconciliation conflicts.
- Public ports are stable indirections over internal `ElementId + PortId` endpoints.
- Collaboration conflict resolution remains SMX-011 work.

## SMX-004 execution retrieval rules

- `EXE-001` through `EXE-015` identify candidate execution invariants.
- `ET-001` through `ET-011` identify disposable executable fixture classes.
- The Python model in `experiments/smx-004-behaviour-model/` is **non-normative**.
- One activation is a bounded transactional run-to-completion turn: state commits atomically, then staged follow-on work is enqueued.
- Direct foreign-Thing state mutation is excluded; cross-Thing effects use explicit interfaces.
- Logical timers/long-lived work use explicit continuations, not durable stackful coroutine state.
- Default randomness is deterministic/scoped; host/network/time/entropy results are explicit external inputs.
- Host services are asynchronous named capability-mediated boundaries.
- Hard execution/resource budgets are semantic requirements.
- Hot swap is quiescent and transactional with explicit state/continuation migration rules.
- Beginner and advanced behaviour target the same semantic IR.

## SMX-005 canonical-document retrieval rules

- `DOC-001` through `DOC-016` identify canonical-document semantic invariants.
- `DT-001` through `DT-012` identify disposable executable fixture classes.
- The Python model in `experiments/smx-005-document-model/` and its sorted-key JSON projection are **non-normative**; do not infer final JSON/CBOR/Protobuf/SQLite/package choices from them.
- Durable candidate: **typed logical record graph + stable semantic IDs + immutable revision/chunk lineage + sparse semantic transactions + content-addressed immutable blobs**.
- Logical mutable entities use stable IDs; content digests identify immutable bytes/revision payloads and do not replace Thing/Definition/Port/Connection/Asset identity.
- Authored document, live runtime state, persistent world/save state, and transient runtime/editor/network context are separate planes.
- Partial loading is first-class: references distinguish `loaded`, `known_unloaded`, `tombstoned`, `unknown`, `incompatible`, and `dependency_unavailable` states.
- Instance provenance/overlays from SMX-003 and behaviour definitions/attachments from SMX-004 remain explicit canonical authored records; live behaviour private state/PRNG/timers/continuations are not silently authored state.
- Semantic transactions target typed IDs/loci with preconditions and all-or-nothing commit; physical JSON pointers, DB rows, and tree paths are not the canonical edit language.
- Migration is staged/deterministic/capability-free by default, validates target state before commit, preserves IDs/references unless explicitly remapped, and fails closed on unsupported required features.
- Unknown optional extension data may be preserved only through explicit compatibility envelopes; unknown required semantics are not silently ignored.

## Initial external primary-source anchors

These links are research starting points, not frozen truths. Relevant issues must re-check current upstream documentation/source and record date/version used. The SMX-001 baseline contains the refreshed 2026-09-17 source snapshot and freshness rules.

### Godot release context

- https://godotengine.org/download/archive/

As checked 2026-09-17, Godot 4.7.2 is the current stable Godot 4 release and 4.8-dev6 is the newest development snapshot. `latest` docs can therefore describe unreleased behaviour and must be labelled accordingly.

### Godot web editor

- https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

### Godot web export

- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
- https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

### Godot runtime I/O and packaging

- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html

### Godot networking

- https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/stable/classes/class_websocketmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/classes/class_webrtcmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/tutorials/networking/webrtc.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

### Object-model comparison anchors

- Godot 4.7 key concepts: https://docs.godotengine.org/en/4.7/getting_started/introduction/key_concepts_overview.html
- Godot 4.7 node access: https://docs.godotengine.org/en/4.7/tutorials/scripting/nodes_and_scene_instances.html
- Bevy ECS: https://bevy.org/learn/quick-start/getting-started/ecs/
- Bevy relationship example: https://github.com/bevyengine/bevy/blob/main/examples/ecs/relationships.rs
- Akka actor model: https://doc.akka.io/libraries/guide/concepts/akka-actor.html
- Akka actor reference/behaviour detail: https://doc.akka.io/libraries/akka/snapshot/general/actors.html
- MDN prototype chain: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Inheritance_and_the_prototype_chain

### Composition/definition comparison anchors

- Godot stable imported-scene inheritance: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- Unity current prefab introduction: https://docs.unity3d.com/current/Manual/prefabs-introduction.html
- Unity current prefab overrides: https://docs.unity3d.com/current/Manual/prefabs-override.html
- Unity 6 prefab variants: https://docs.unity3d.com/6000.0/Manual/PrefabVariants.html
- Self Handbook 2024.1 world organization: https://handbook.selflanguage.org/2024.1/worldorg.html
- Self Handbook 2024.1 programming guide: https://handbook.selflanguage.org/2024.1/progguid.html
- Self Handbook 2024.1 glossary: https://handbook.selflanguage.org/2024.1/glossary.html

### Behaviour/execution comparison anchors

- W3C SCXML: https://www.w3.org/TR/scxml/
- WebAssembly specifications: https://webassembly.github.io/spec/
- WebAssembly module validation: https://webassembly.github.io/spec/core/valid/modules.html
- WebAssembly host-function execution boundary: https://webassembly.github.io/spec/core/exec/instructions.html
- Scratch VM: https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/README.md
- CEL: https://cel.dev/
- CEL language definition/cost model: https://github.com/cel-expr/cel-spec/blob/master/doc/langdef.md
- Starlark specification: https://github.com/bazelbuild/starlark/blob/master/spec.md

### Canonical-document/encoding comparison anchors

SMX-005 uses these as representation/storage precedents, not selected dependencies:

- JSON Schema specification (Draft 2020-12 family): https://json-schema.org/specification
- Protocol Buffers Editions language guide / unknown fields: https://protobuf.dev/programming-guides/editions/
- Protocol Buffers encoding / non-guaranteed field serialization order: https://protobuf.dev/programming-guides/encoding/
- SQLite as application file format: https://sqlite.org/appfileformat.html
- SQLite database file format / transaction/WAL representation: https://sqlite.org/fileformat.html
- RFC 8949 CBOR / deterministic encoding: https://www.rfc-editor.org/rfc/rfc8949.html

These support the current conclusion that semantic identity, versioning, transactions, migration, and partial-loading rules must sit above a chosen byte/store technology.

### Browser/platform primary sources

Relevant issues should prefer current specifications or authoritative browser documentation for WebAssembly, WebRTC, WebSocket, IndexedDB, permissions, CSP, cross-origin isolation, workers, storage quotas, and lifecycle/background throttling.

### Collaboration research

Potential starting point, not a selected dependency:

- https://automerge.org/docs/

Relevant issues must compare desired SplashMX conflict semantics against multiple approaches rather than selecting a CRDT library first.

## Source freshness classes

The normative freshness rules are in `docs/research/SMX-001-RESEARCH-BASELINE.md`:

- **F1** — engine/security/runtime facts: refresh in every consuming issue and after relevant upstream releases during the issue.
- **F2** — web-platform/API facts: refresh in every consuming issue and validate target-browser behaviour when acceptance depends on it.
- **F3** — algorithm/library facts: pin version/commit and reproduce behaviour; refresh on dependency version change.
- **F4** — conceptual/historical material: prefer original/primary sources; freshness is secondary to correct attribution.

## RAG authoring rules

When adding research material:

- use stable headings and explicit IDs (`H-###`, `SMX-###`, `ADR-###`, `E-###`, `C-###`, `A-###`, `S-##`, `K-###`, `T-###`, `CMP-###`, `CT-###`, `EXE-###`, `ET-###`, `DOC-###`, `DT-###`) so retrieval can target concepts precisely;
- keep conclusions close to evidence links/fixtures;
- record rejected alternatives and why, not only the chosen answer;
- avoid giant chronological notebooks as the only source of truth;
- promote durable conclusions into authoritative docs and keep experiments/prototypes separately identifiable;
- date/version external claims likely to change;
- distinguish current facts from hypotheses and decisions;
- state which corpus cases were actually exercised when making universal or cross-domain claims.

## Expected future retrieval artefacts

Research issues may add topic-specific documents under `docs/research/`, ADRs under `docs/adr/`, schemas under `spec/`, and disposable experiments under `experiments/`. When they do, update this index so later agents can retrieve the minimum complete authoritative set without reconstructing context from commit history.
