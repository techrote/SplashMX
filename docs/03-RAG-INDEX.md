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
13. The active GitHub issue, its dependency issues, and merged PRs for those dependencies.

## Retrieval map by topic

| Question/topic | Retrieve repository material | Also inspect |
|---|---|---|
| Product scope / “Flash successor” intent | Constitution, Roadmap | Current issue |
| Research terminology / evaluation method | SMX-001 research baseline | Corpus JSON; issue #1 merged PR |
| Thing/object/kernel semantics | SMX-002 Thing kernel, H-001/H-002/H-003/H-008 | SMX-002 fixtures/experiment; SMX-001 cases C-003/C-004/C-006/C-007/C-020/C-021/C-022/C-025 and A-001/A-014/A-016 |
| Composition/local classes/instances | SMX-003 composition research, H-002–H-005, CMP-001–CMP-012 | SMX-003 fixtures/experiment; C-002/C-006/C-007/C-011/C-017/C-018/C-021/C-027; A-001/A-008/A-016 |
| Behaviour/rules/scripting/IR | H-005/H-006, SMX-002 command/event/value candidate, SMX-003 behaviour-override handoff, cases C-025/A-004/A-006 | SMX-004 outputs |
| IDs/references/schema/canonical format | H-007/H-008/H-018, SMX-002 K-001/K-002/K-010/K-012, SMX-003 DefinitionId/RevisionId/ElementId/overlay requirements | SMX-005 outputs; C-006/C-012/C-023/C-024 |
| Security/sandbox/capabilities | Constitution P9, H-009, SMX-002 K-005/K-006, cases C-022/A-003/A-004/A-012/A-015 | SMX-006/016 outputs; current platform primary docs |
| Lifecycle/serialization/determinism | H-008/H-010, SMX-002 state/context taxonomy, SMX-003 protected-deletion/reconciliation requirements, cases C-024/A-002 | SMX-007/015 outputs |
| Streaming/hot swap | H-005/H-010/H-011, SMX-002 K-012, SMX-003 public-interface/provenance model, cases C-012/C-025/C-027 | SMX-008/015 outputs |
| Godot mapping/browser limits | H-007/H-014/H-015, SMX-002 K-010, SMX-001 evidence E-006–E-014 | SMX-009 outputs; current Godot primary docs/source |
| Multiplayer | Constitution P7, H-012/H-013, SMX-002 relationship/context split, SMX-003 CMP-012, cases C-013/C-014/C-020/C-021/A-009/A-011 | SMX-010/017 outputs; current browser/Godot transport docs |
| Collaborative editing | Constitution P8, H-013/H-017, SMX-003 base-revision/overlay/reconcile model, cases C-016–C-019/A-007/A-008 | SMX-011/018 outputs; CRDT/OT/local-first primary material |
| Editor UX/progressive disclosure | P1–P3, H-016, scorecard S-01/S-16, ordinary-group→local-definition promotion | SMX-012/019 outputs |
| Component ecosystem | P9/P13, H-004/H-009, SMX-003 local-definition/public-interface model, cases C-011/C-022/C-026 | SMX-013/016 outputs |
| Publishing/player/server | P10–P12, H-014/H-015/H-018, cases C-015/C-023 | SMX-014/017/019 outputs |
| Architecture freeze | Everything above | All merged research PRs and open blockers |

## SMX-001 baseline retrieval rules

Later research should cite stable corpus IDs rather than paraphrasing test cases inconsistently.

- `C-###` identifies representative cases.
- `A-###` identifies adversarial variants.
- `S-##` identifies architecture scorecard criteria.
- Applicable cases that were not exercised must remain explicitly `N/E` (not evaluated), not silently treated as passing.
- A hard-gate score of `0` cannot be averaged away by stronger scores elsewhere.

When adding or changing corpus cases, preserve existing IDs and update both the Markdown baseline and companion JSON in the same PR.

## SMX-002 kernel retrieval rules

SMX-002 introduces stable research references for the provisional Thing-kernel candidate:

- `K-001` through `K-012` identify candidate semantic invariants.
- `T-001` through `T-007` identify disposable executable fixture classes.
- The Python model in `experiments/smx-002-kernel-model/` is **non-normative**; do not infer storage layout or production runtime APIs from it.
- The durable conclusion is semantic: stable Thing identity + intrinsic state + optional facets + explicit interfaces + typed relationships, with runtime/editor grants/authority/handles in explicit context.
- Command/event/value is a **candidate** port vocabulary for SMX-004 to validate or reject.
- Definition/instance representation was intentionally left open and is refined by SMX-003.

## SMX-003 composition retrieval rules

SMX-003 adds stable research references for composition and local-definition semantics:

- `CMP-001` through `CMP-012` identify candidate composition/definition invariants.
- `CT-001` through `CT-010` identify disposable executable fixture classes.
- The Python model in `experiments/smx-003-composition-model/` is **non-normative**; do not infer canonical storage layout, production reconciliation APIs, or final ID encoding from it.
- The durable candidate is **stable local-definition graph + concrete instance graph + sparse explicit overlay**.
- `DefinitionId`, immutable revision identity, `ElementId`, concrete `ThingId`, and stable port IDs are distinct semantic roles; SMX-005 owns their concrete canonical encoding.
- `instance-of` is provenance, not control/authority/ownership.
- Compatible base changes propagate to unoverridden loci; explicit instance overrides continue to win while valid.
- Invalidated override/exposure targets and protected destructive changes become explicit reconciliation conflicts rather than silent reinterpretation.
- Public ports are stable indirections over internal `ElementId + PortId` endpoints so internal reparenting does not require external connection repair.
- Collaboration conflict resolution is not defined by the overlay model; SMX-011 owns concurrent-edit semantics.

## Initial external primary-source anchors

These links are research starting points, not frozen truths. Relevant issues must re-check current upstream documentation/source and record date/version used. The SMX-001 baseline contains the refreshed 2026-09-17 source snapshot and freshness rules.

### Godot release context

- https://godotengine.org/download/archive/

As checked 2026-09-17, Godot 4.7.2 is the current stable Godot 4 release and 4.8-dev6 is the newest development snapshot. `latest` docs can therefore describe unreleased behaviour and must be labelled accordingly.

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
- https://docs.godotengine.org/en/stable/tutorials/networking/webrtc.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

Questions: SceneTree coupling, browser transports, WebRTC signalling/mesh properties, dedicated/headless execution, which layers are implementation substrate versus public contract.

### Object-model comparison anchors

SMX-002 used these as conceptual F4 comparison material, not selected dependencies:

- Godot 4.7 key concepts: https://docs.godotengine.org/en/4.7/getting_started/introduction/key_concepts_overview.html
- Godot 4.7 node access: https://docs.godotengine.org/en/4.7/tutorials/scripting/nodes_and_scene_instances.html
- Bevy ECS: https://bevy.org/learn/quick-start/getting-started/ecs/
- Bevy relationship example: https://github.com/bevyengine/bevy/blob/main/examples/ecs/relationships.rs
- Akka actor model: https://doc.akka.io/libraries/guide/concepts/akka-actor.html
- Akka actor reference/behaviour detail: https://doc.akka.io/libraries/akka/snapshot/general/actors.html
- MDN prototype chain: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Inheritance_and_the_prototype_chain

### Composition/definition comparison anchors

SMX-003 adds comparative material for local-definition/override semantics:

- Godot stable imported-scene inheritance: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- Unity current prefab introduction: https://docs.unity3d.com/current/Manual/prefabs-introduction.html
- Unity current prefab overrides: https://docs.unity3d.com/current/Manual/prefabs-override.html
- Unity 6 prefab variants: https://docs.unity3d.com/6000.0/Manual/PrefabVariants.html
- Self Handbook 2024.1 world organization: https://handbook.selflanguage.org/2024.1/worldorg.html
- Self Handbook 2024.1 programming guide: https://handbook.selflanguage.org/2024.1/progguid.html
- Self Handbook 2024.1 glossary: https://handbook.selflanguage.org/2024.1/glossary.html

These are precedents/trade-off evidence, not selected dependencies or compatibility contracts.

### Browser/platform primary sources

Relevant issues should prefer current specifications or authoritative browser documentation for WebAssembly, WebRTC, WebSocket, IndexedDB, File System Access where applicable, CSP, cross-origin isolation, workers, storage quotas, lifecycle/background throttling, and permissions.

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

- use stable headings and explicit IDs (`H-###`, `SMX-###`, `ADR-###`, `E-###`, `C-###`, `A-###`, `S-##`, `K-###`, `T-###`, `CMP-###`, `CT-###`) so retrieval can target concepts precisely;
- keep conclusions close to evidence links/fixtures;
- record rejected alternatives and why, not only the chosen answer;
- avoid giant chronological notebooks as the only source of truth;
- promote durable conclusions into authoritative docs and keep experiments/prototypes separately identifiable;
- date/version external claims likely to change;
- distinguish current facts from hypotheses and decisions;
- state which corpus cases were actually exercised when making universal or cross-domain claims.

## Expected future retrieval artefacts

Research issues may add topic-specific documents under `docs/research/`, ADRs under `docs/adr/`, schemas under `spec/`, and disposable experiments under `experiments/`. When they do, update this index so later agents can retrieve the minimum complete authoritative set without reconstructing context from commit history.
