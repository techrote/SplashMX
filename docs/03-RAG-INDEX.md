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
17. `docs/research/SMX-006-CAPABILITY-SANDBOX.md` — threat model, capability/principal/delegation/revocation semantics, parser/runtime/network boundaries, Godot/browser hardening evidence, and SMX-016 attack plan.
18. `docs/research/SMX-006-SECURITY-FIXTURES.json` — machine-addressable SEC-/ST-IDs and direct experimental coverage for SMX-006.
19. `docs/research/SMX-007-LIFECYCLE-RESTORE.md` — lifecycle axes, quiescent snapshot semantics, pending-work/timer classifications, staged restore, tombstones, and determinism/replay boundaries.
20. `docs/research/SMX-007-LIFECYCLE-FIXTURES.json` — machine-addressable LIF-/LT-IDs and direct experimental coverage for SMX-007.
21. `docs/research/SMX-008-STREAMING-MIGRATION.md` — logical/physical stream-unit separation, exact dependency descriptors, staged acquisition, cache/eviction, hot replacement, typed failures, and migration-capsule semantics.
22. `docs/research/SMX-008-STREAMING-FIXTURES.json` — machine-addressable STR-/SG-IDs and direct experimental coverage for SMX-008.
23. `docs/research/SMX-009-GODOT-BOUNDARY.md` and companion fixtures — current Godot/web/headless substrate boundary, target-private binding rules, and source/audio/provenance preservation.
24. `docs/research/SMX-010-RUNTIME-MULTIPLAYER.md` and companion fixtures — runtime authority/replication/relevance/topology semantics and the concrete SMX-017 equivalence handoff.
25. `docs/research/SMX-011-COLLABORATION-SEMANTICS.md` and companion fixtures — human-visible conflict semantics, causal semantic transactions, local-first reconciliation, undo/history, transient presence separation, and the concrete SMX-018 handoff.
26. `docs/research/SMX-012-AUTHORING-MODEL.md` and companion fixtures — progressive-disclosure author vocabulary, Stage/Timeline/Rules/Components responsibilities, simple/advanced multiplayer projection, People/collaboration separation, protected media authoring, and concrete SMX-019 gates.
27. `docs/research/SMX-013-COMPONENT-PACKAGES.md` and companion fixtures — portable component/package identity, exact dependency locks, update/migration rollback, transitive capability attribution, offline/cache, remix/licensing/provenance, and SMX-014/016/019 handoffs.
28. The active GitHub issue, its dependency issues, and merged PRs for those dependencies.

## Retrieval map by topic

| Question/topic | Retrieve repository material | Also inspect |
|---|---|---|
| Product scope / “Flash successor” intent | Constitution, Roadmap | Current issue |
| Research terminology / evaluation method | SMX-001 research baseline | Corpus JSON; issue #1 merged PR |
| Thing/object/kernel semantics | SMX-002 Thing kernel, H-001/H-002/H-003/H-008 | SMX-002 fixtures/experiment; C-003/C-004/C-006/C-007/C-020/C-021/C-022/C-025; A-001/A-014/A-016 |
| Composition/local classes/instances | SMX-003 composition research, H-002–H-005, CMP-001–CMP-012 | SMX-003 fixtures/experiment; C-002/C-006/C-007/C-011/C-017/C-018/C-021/C-027; A-001/A-008/A-016 |
| Behaviour/rules/scripting/IR | SMX-004 behaviour execution, H-005/H-006/H-009, EXE-001–EXE-015 | SMX-004 fixtures/experiment; C-003/C-004/C-005/C-009/C-022/C-024/C-025; A-003/A-004/A-006 |
| IDs/references/schema/canonical format | SMX-005 canonical document, H-007/H-008/H-018, DOC-001–DOC-016 | SMX-005 fixtures/experiment; C-006/C-011/C-012/C-018/C-023/C-025/C-026/C-027; A-001/A-002/A-008/A-010/A-012 |
| Security/sandbox/capabilities | SMX-006 capability sandbox, H-006/H-009/H-014/H-015, SEC-001–SEC-018, plus SMX-004 service/budget and SMX-005 parser/migration boundaries | SMX-006 fixtures/experiment; SMX-016 attack campaign; C-011/C-022/C-026; A-003/A-004/A-012/A-015; current platform primary docs |
| Lifecycle/serialization/determinism | SMX-007 lifecycle/restore, H-008/H-010/H-018, LIF-001–LIF-018, plus SMX-004 scheduler state and SMX-005 authored/runtime/save/context planes | SMX-007 fixtures/experiment; SMX-015 destructive integration; C-002/C-006/C-012/C-024/C-025/A-002 |
| Streaming/hot swap | SMX-008 streaming/migration, H-005/H-010/H-011/H-018, STR-001–STR-020, plus SMX-007 lifecycle and SMX-005 catalog/reference semantics | SMX-008 fixtures/experiment; SMX-015 destructive integration; C-006/C-011/C-012/C-015/C-024/C-025/C-026/C-027; A-006/A-012/A-015 |
| Godot mapping/browser limits | SMX-009 Godot boundary, H-007/H-014/H-015, SMX-005 engine-independent canonical contract, SMX-004 no-Godot execution contract | SMX-009 fixtures/experiment; current Godot 4.7 primary docs/source |
| Multiplayer | SMX-010 runtime multiplayer, Constitution P7, H-012/H-013, SMX-002 relationship/context split, SMX-006 network boundary, SMX-007/008 unload+migration, SMX-009 transport boundary | SMX-010 fixtures/experiment; SMX-012 authoring projection; SMX-017 topology-equivalence spec; C-007/C-012/C-013/C-014/C-020/C-021/C-022/C-023; A-002/A-003/A-004/A-009/A-011/A-016; current Godot/browser networking docs |
| Collaborative editing | SMX-011 collaboration semantics, Constitution P8, H-013/H-017/H-018, SMX-005 semantic transactions, SMX-003 definition/instance reconciliation, SMX-010 NET-019 separation | SMX-011 fixtures/experiment; SMX-012 People/conflict projection; SMX-018 destructive harness; C-016–C-019/A-007/A-008; CRDT/OT/local-first primary material |
| Editor UX/progressive disclosure | SMX-012 authoring model, AUTH-001–AUTH-028, UX-001–UX-028, P1–P3, H-016, ordinary-group→local-definition promotion, SMX-004 common beginner/advanced IR, SMX-010/011 network+collaboration semantics | SMX-012 experiment/fixtures; UXG-001–UXG-012; SMX-019 browser vertical slice |
| Component ecosystem | SMX-013 component/package research, PKG-001–PKG-028, P9/P13, H-004/H-009/H-011/H-018, SMX-003 local-definition/public-interface model, SMX-006 capability boundary, SMX-008 exact acquisition, SMX-012 group→reusable projection | SMX-013 fixtures/experiment; SMX-014 publishing; SMX-016 hostile package campaign; SMX-019 browser UX; C-011/C-022/C-026 |
| Publishing/player/server | P10–P12, H-014/H-015/H-018, SMX-005 feature/version/blob/chunk model, SMX-009 target profiles, SMX-010 topology-independent network declarations, SMX-012 Publish contract | SMX-013 exact package locks; SMX-014/017/019 outputs; C-015/C-023 |
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

## SMX-006 security retrieval rules

SMX-006 adds stable references for the provisional untrusted-content security contract:

- `SEC-001` through `SEC-018` identify capability/sandbox invariants.
- `ST-001` through `ST-012` identify disposable deterministic security fixture classes.
- The Python model in `experiments/smx-006-security-model/` is **non-normative**; do not infer production cryptography, OS/browser handles, quota values, or API layouts from it.
- Ordinary content has no ambient host authority. Host effects cross explicit asynchronous services authorized as the **originating principal**.
- Containment does not imply privilege. Delegation is explicit, scope/lifetime narrowing, bounded, and revocable.
- Package signatures establish provenance/integrity only; they do not grant capabilities.
- Browser/OS permission is a second independent gate beneath SplashMX capability policy.
- Ordinary community packages cannot introduce GDScript/C#/GDExtension/native code, JavaScriptBridge/eval, unrestricted ResourceLoader/PCK/mod semantics, shell/process access, unrestricted filesystem or raw sockets.
- Parser, canonical migration, IR executor, runtime services, and network ingress are separate trust boundaries with independent hard limits.
- SMX-016 must attack the real implementations; model-level passing tests are not an end-to-end sandbox proof.

### Security/platform primary-source anchors — refreshed 2026-09-17

- Godot web compilation / `javascript_eval=no`: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html
- Godot untrusted PCK/mod security warning: https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html
- Godot GDExtension native-library boundary: https://docs.godotengine.org/en/latest/engine_details/engine_api/gdextension/what_is_gdextension.html
- W3C Permissions: https://www.w3.org/TR/permissions/
- W3C Permissions Policy: https://www.w3.org/TR/permissions-policy/
- Media Capture and Streams: https://www.w3.org/TR/mediacapture-streams/
- Geolocation 2026 Recommendation: https://www.w3.org/TR/2026/REC-geolocation-20260324/
- Clipboard API: https://www.w3.org/TR/clipboard-apis/
- WHATWG Notifications: https://notifications.spec.whatwg.org/

## SMX-007 lifecycle retrieval rules

SMX-007 adds stable references for runtime lifecycle and save/restore semantics:

- `LIF-001` through `LIF-018` identify lifecycle/snapshot/restore invariants.
- `LT-001` through `LT-012` identify disposable deterministic lifecycle fixture classes.
- The Python model in `experiments/smx-007-lifecycle-model/` is **non-normative**; do not infer production snapshot bytes, scheduler data structures, Godot object layout, or final migration APIs from it.
- Lifecycle is modeled on orthogonal **existence**, **residency**, and **activity** axes; snapshot/save is an atomic operation, not a mutually exclusive Thing state.
- Semantic dormancy may pause active-time processing. Hidden implementation sleep/LOD must remain observationally equivalent and cannot silently alter authored timer/behaviour semantics.
- Snapshot cuts occur at bounded-turn quiescent boundaries and persist only explicitly selected runtime state; transient engine/network/capability context is rebound later.
- Durable internal pending work is explicit. Previously issued external side effects are **not** automatically replayed during restore.
- Clock domains remain explicit: `thing_active`, `world_logical`, and external wall-clock semantics are distinct.
- References to absent Things distinguish loaded, known-unloaded, tombstoned, unknown, incompatible, and dependency-unavailable states.
- Restore does not replay first-creation hooks by default and does not require a surviving Godot/process object.
- Deterministic restore means reconstruction of the same declared state before new external inputs; it does not claim future replay without the same external input stream.

## SMX-008 streaming retrieval rules

SMX-008 adds stable references for streaming, acquisition, and live replacement:

- `STR-001` through `STR-020` identify streaming/dependency/hot-replacement invariants.
- `SG-001` through `SG-012` identify disposable deterministic streaming fixture classes.
- The Python model in `experiments/smx-008-streaming-model/` is **non-normative**; do not infer production package/container/cache/CDN/version-solver/Godot-loader APIs from it.
- Logical identity/load targets are distinct from physical acquisition units. Object-centric streaming does **not** require one file/blob per Thing.
- Durable references do not imply residency; `known_unloaded` remains valid and I/O is policy/operation-driven.
- Required, optional, and lazy dependency edges are explicit. Runtime streaming consumes exact immutable resolved descriptors; version-range solving belongs SMX-013.
- Acquisition is staged and atomically published only after bounded fetch/digest/trust/schema/feature/migration validation of the required closure.
- Cache/prefetch/eviction are non-semantic. Active executable dependencies are pinned or execution is explicitly blocked/dormant.
- Behaviour/definition implementation artifacts and concrete instance/attachment state have independent residency.
- Hot replacement acquires the new artifact first, migrates at a quiescent boundary, maps stable interfaces/pending work explicitly, and rolls back to the old live version on failure.
- Missing, offline, denied, incompatible, invalid/malicious, resource-exhausted, cancelled, and transient failure states remain distinct.
- A portable host-migration capsule is a quiescent semantic snapshot + exact dependency requirements; it excludes peer IDs, authority tokens, live grants, and engine/native/browser handles.

### Streaming/dependency primary-source anchors — refreshed 2026-09-19

- Godot 4.7 ResourceLoader/threaded load/cache/dependency API: https://docs.godotengine.org/en/4.7/classes/class_resourceloader.html
- OCI Image Specification manifest/descriptors: https://specs.opencontainers.org/image-spec/manifest/
- The Update Framework specification: https://github.com/theupdateframework/specification/blob/master/tuf-spec.md
- Semantic Versioning 2.0.0: https://semver.org/

These are comparison precedents, not selected SplashMX public dependencies.

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

Current SMX-011 comparison anchors, not selected dependencies:

- https://automerge.org/docs/
- https://docs.yjs.dev/
- https://share.github.io/sharedb/
- https://www.inkandswitch.com/essay/convergence-is-not-enough/

Relevant issues must compare desired SplashMX conflict semantics against multiple approaches rather than selecting a CRDT/OT library first.

## Source freshness classes

The normative freshness rules are in `docs/research/SMX-001-RESEARCH-BASELINE.md`:

- **F1** — engine/security/runtime facts: refresh in every consuming issue and after relevant upstream releases during the issue.
- **F2** — web-platform/API facts: refresh in every consuming issue and validate target-browser behaviour when acceptance depends on it.
- **F3** — algorithm/library facts: pin version/commit and reproduce behaviour; refresh on dependency version change.
- **F4** — conceptual/historical material: prefer original/primary sources; freshness is secondary to correct attribution.

## RAG authoring rules

When adding research material:

- use stable headings and explicit IDs (`H-###`, `SMX-###`, `ADR-###`, `E-###`, `C-###`, `A-###`, `S-##`, `K-###`, `T-###`, `CMP-###`, `CT-###`, `EXE-###`, `ET-###`, `DOC-###`, `DT-###`, `SEC-###`, `ST-###`, `LIF-###`, `LT-###`, `STR-###`, `SG-###`, `GOD-###`, `GB-###`, `NET-###`, `NT-###`, `COL-###`, `CF-###`, `AUTH-###`, `UX-###`, `UXG-###`, `PKG-###`, `PK-###`) so retrieval can target concepts precisely;
- keep conclusions close to evidence links/fixtures;
- record rejected alternatives and why, not only the chosen answer;
- avoid giant chronological notebooks as the only source of truth;
- promote durable conclusions into authoritative docs and keep experiments/prototypes separately identifiable;
- date/version external claims likely to change;
- distinguish current facts from hypotheses and decisions;
- state which corpus cases were actually exercised when making universal or cross-domain claims.

## Expected future retrieval artefacts

Research issues may add topic-specific documents under `docs/research/`, ADRs under `docs/adr/`, schemas under `spec/`, and disposable experiments under `experiments/`. When they do, update this index so later agents can retrieve the minimum complete authoritative set without reconstructing context from commit history.

## SMX-009 Godot-boundary retrieval rules

SMX-009 adds the platform-boundary material that downstream network, publishing, sandbox, and browser work must retrieve before treating Godot APIs as architecture:

- `docs/research/SMX-009-GODOT-BOUNDARY.md` — the `SplashMX owns` versus `Godot supplies` map, 2026-09-19 Godot 4.7.2/web/headless facts, security mapping, generic-player result, source/audio/provenance preservation, rejected mappings, and downstream handoffs.
- `docs/research/SMX-009-GODOT-BOUNDARY-FIXTURES.json` — `GOD-001` through `GOD-018` and `GB-001` through `GB-012` machine-addressable candidate invariants/fixtures.
- `experiments/smx-009-godot-boundary-model/` — non-normative generic-player/target-profile model, hostile boundary tests, and identity-to-binding microbenchmark.
- Durable candidate: a SplashMX Thing is not a Godot Node; one Thing may have zero/one/many private substrate bindings, and bindings can be recreated without changing durable identity/state.
- Nodes, NodePaths, RIDs, ResourceUIDs, peer IDs, browser/OS handles, sockets, and JavaScript objects are transient adapter context and must not enter canonical documents, snapshots, or migration capsules.
- Ordinary content cannot request arbitrary GDScript/C#/GDExtension/JavaScriptBridge/eval/PCK/filesystem/raw-socket authority merely because a target build exposes those host facilities.
- Exact source assets, audio identity, provenance/licensing, and derivation records remain SplashMX-owned; Godot imported/decoded/transcoded resources and server placeholders are target-private derivatives/caches.
- Generic web/native/headless projection is supported at model level with explicit required/optional feature negotiation; real Godot frame/startup cost remains an SMX-015/019 measurement gate.
- Network transport selection (WebRTC/WebSocket/ENet/UDP) remains below SMX-010 authority/replication semantics. Browser background suspension and absence of low-level networking are mandatory downstream cases.

### SMX-009 primary-source anchors — refreshed 2026-09-19

- Godot release archive / 4.7.2 stable and 4.8-dev6 context: https://godotengine.org/download/archive/
- Godot 4.7 web export, renderer/thread/audio/storage/background/network limitations: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html
- Godot 4.7 web editor limitations/IndexedDB: https://docs.godotengine.org/en/4.7/tutorials/editor/using_the_web_editor.html
- Godot 4.7 ResourceLoader: https://docs.godotengine.org/en/4.7/classes/class_resourceloader.html
- Godot 4.7 WebSocket: https://docs.godotengine.org/en/4.7/tutorials/networking/websocket.html
- Godot 4.7 WebRTC: https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html
- Godot 4.7 dedicated-server export: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html
- Current web-template compilation / `javascript_eval=no`: https://docs.godotengine.org/en/stable/engine_details/development/compiling/compiling_for_web.html

`GOD-###` and `GB-###` now join the stable RAG identifier families for substrate-boundary research.

## SMX-010 runtime-multiplayer retrieval rules

SMX-010 adds the runtime network semantics that later collaboration, publishing, topology-harness, sandbox, and editor work must retrieve before treating a transport or Godot multiplayer API as the network model:

- `docs/research/SMX-010-RUNTIME-MULTIPLAYER.md` — `NET-001` through `NET-020`, authority/control/relevance/identity separation, message-class semantics, reconnect/host migration rules, security boundary, beginner projection, and the concrete SMX-017 topology-equivalence specification.
- `docs/research/SMX-010-RUNTIME-MULTIPLAYER-FIXTURES.json` — `NT-001` through `NT-020`, with explicit representative/adversarial corpus coverage.
- `experiments/smx-010-multiplayer-model/` — non-normative semantic model and hostile/boundary tests; it is not a wire protocol or production networking stack.
- Durable candidate: the same canonical Thing/network declaration is used for offline, peer-hosted, and dedicated-authoritative modes; topology changes runtime policy/context rather than object taxonomy.
- `ThingId`, authenticated principal/player, runtime session, transient peer/connection ID, controller binding, simulation authority, relevance, and persistence remain distinct semantic roles.
- State, discrete events, input/commands, baseline/snapshot, and derived prediction/interpolation are different message classes with different replay/supersession behavior.
- Authority transfer and peer-host migration are epoch-scoped; old-epoch queued/delayed traffic must not become authoritative after transfer.
- Relevance and `known_unloaded` state do not imply destruction. Coalescible state and reliable event obligations must remain bounded and lifecycle-aware.
- Reconnect rebinds transient peer identity rather than replacing the principal/Thing. Browser background suspension is therefore a required SMX-017 case.
- Transport names, peer IDs, sockets, Godot RPC annotations/NodePaths, and live capability grants remain outside canonical network data.
- Runtime multiplayer replication is not the collaboration edit protocol; retrieve SMX-011/018 for persistent concurrent edits.
- Network/topology work must preserve exact source/audio/provenance, immutable asset digest, licensing, and derivation semantics established by SMX-005/009.

### SMX-010 primary-source anchors — refreshed 2026-09-19

- Godot 4.7 high-level multiplayer / peers, RPC authority, transfer modes: https://docs.godotengine.org/en/4.7/tutorials/networking/high_level_multiplayer.html
- Godot 4.7 web networking/background lifecycle: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html
- Godot 4.7 WebSocket: https://docs.godotengine.org/en/4.7/tutorials/networking/websocket.html
- Godot 4.7 WebRTC: https://docs.godotengine.org/en/4.7/tutorials/networking/webrtc.html
- Godot 4.7 dedicated-server export: https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_dedicated_servers.html

`NET-###` and `NT-###` now join the stable RAG identifier families for runtime-multiplayer research.

## SMX-011 collaboration retrieval rules

SMX-011 adds the durable authoring-conflict semantics that editor, migration, package, security and destructive collaboration work must retrieve before choosing a CRDT/OT/database/sync library:

- `docs/research/SMX-011-COLLABORATION-SEMANTICS.md` — `COL-001` through `COL-024`, the full human-visible conflict table, local-first reconnect, selective undo/history, partial loading, schema migration, protected source/audio/provenance handling, implementation-family comparison, and concrete SMX-018 destructive plan.
- `docs/research/SMX-011-COLLABORATION-FIXTURES.json` — `CF-001` through `CF-028` with representative/adversarial corpus coverage.
- `experiments/smx-011-collaboration-model/` — non-normative deterministic semantic model and adversarial/boundary tests; it is not a production CRDT, OT engine, sync protocol or database.
- Durable candidate: **SplashMX semantic transaction/conflict layer above a replaceable causal synchronization/storage substrate**. Product conflict behavior is defined before implementation selection.
- Independent semantic loci auto-merge; incompatible same-locus or invariant-sensitive structural edits remain explicit conflicts unless a narrow rule such as tombstone/remove-wins is intentionally defined.
- Multi-object semantic transactions remain atomic. Convergence may never justify half-applied grouping/structure or illegal definition/interface state.
- Offline replicas may author without cloud document authority; duplicate/order-independent reconciliation is required, with permissions and schema compatibility revalidated on reunion.
- Collaborative undo is a new compensating semantic transaction with current preconditions, not a global history rewind.
- Presence/cursor/selection/typing/viewport state is transient awareness, outside canonical authored state and durable edit history.
- `known_unloaded`, tombstoned and unknown targets stay distinct during collaboration; unloaded work may remain pending rather than guessed.
- Asset replacement treats immutable digest + source/audio identity + provenance/licensing + derivation as one protected revision bundle. Concurrent replacements cannot field-mix them.
- Runtime multiplayer remains a separate consistency layer: SMX-010 peer/authority/replication/transport data is rejected from canonical collaboration transactions.
- SMX-018 must prove semantic invariants as well as replica equality under reorder, duplicate, partition, reconnect, compaction, schema migration and stale-permission schedules.

### SMX-011 primary/comparative anchors — refreshed 2026-09-19

- Automerge conflicts/local-first docs: https://automerge.org/docs/reference/documents/conflicts/ and https://automerge.org/docs/hello/
- Yjs document updates, Awareness and UndoManager: https://docs.yjs.dev/api/document-updates , https://docs.yjs.dev/api/about-awareness , https://docs.yjs.dev/api/undo-manager
- ShareDB OT/history/offline/types: https://share.github.io/sharedb/ and https://share.github.io/sharedb/types/
- Ink & Switch, *Convergence Is Not Enough* (2026): https://www.inkandswitch.com/essay/convergence-is-not-enough/

These are comparison precedents, not selected dependencies. `COL-###` and `CF-###` are stable RAG identifier families for collaboration semantics and fixtures.

## SMX-012 authoring-projection retrieval rules

SMX-012 adds the author-facing projection that component, publishing, multiplayer, collaboration, and browser vertical-slice work must retrieve before designing UI around lower-level implementation concepts:

- `docs/research/SMX-012-AUTHORING-MODEL.md` — the Things/Behaviours/Connections vocabulary, progressive disclosure levels, view responsibilities, multiplayer/collaboration split, diagnostics, protected media authoring, rejected metaphors, and the concrete SMX-019 handoff.
- `docs/research/SMX-012-AUTHORING-FIXTURES.json` — `AUTH-001` through `AUTH-028`, `UX-001` through `UX-028`, and `UXG-001` through `UXG-012` machine-addressable authoring invariants, corpus walkthroughs, and browser vertical-slice gates.
- `experiments/smx-012-authoring-model/` — non-normative progressive-disclosure/canonical-workspace model plus adversarial/boundary tests; it is not production editor architecture.
- Durable candidate: **Stage, Timeline, Behaviours, Rules, Connections, Components, Together, People, Publish and Inspect are progressively disclosed views over one SplashMX semantic fabric, not independent ownership systems.**
- Timeline is optional. It owns authored time-based values/cues; interaction may be primarily Behaviour/Rule/Connection-driven.
- An ordinary group can become a reusable local definition while preserving the first concrete instance Thing identities; SMX-013 must extend this path rather than invent a package-only component class.
- Beginner Rule and advanced Behaviour authoring target the same accepted execution semantics/IR and capability boundary.
- Runtime multiplayer presets (`local only`, `one per player`, `shared`, `authority controlled`) are projections of the same control/authority/replication/relevance declaration exposed by Advanced. Peer/session/transport/RPC details remain below the author contract.
- People/presence/history/conflicts are collaborative-editing semantics and remain visibly separate from runtime Together controls. Presence stays transient.
- Import/replacement preserves stable `AssetId` and the complete digest/source/audio/provenance revision bundle atomically; no authoring operation may synthesize mixed provenance.
- Ordinary diagnostics use SplashMX author vocabulary; requiring engine, schema, package-manager, transport or build-system concepts in the core workflow is an architectural leak.
- SMX-019 must execute all `UXG-###` gates and measure real discoverability/interaction friction rather than treating a cosmetically friendly mock-up as proof.

### SMX-012 creative-tool comparison anchors — checked 2026-09-19

- Adobe Animate time/Timeline: https://helpx.adobe.com/animate/desktop/using/time.html
- Adobe Animate symbols/instances: https://helpx.adobe.com/animate/desktop/multimedia-and-video/symbols.html
- Construct 3 events: https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/events/how-events-work
- Construct 3 families: https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/objects/families
- GameMaker object events: https://manual.gamemaker.io/lts/en/GameMaker_Language/GML_Reference/Asset_Management/Objects/Object_Events/Generating_Object_Events.htm

These are interaction precedents, not selected runtime/public-model dependencies. `AUTH-###`, `UX-###`, and `UXG-###` are stable RAG identifier families for authoring projection and vertical-slice acceptance.

## SMX-013 component/package retrieval rules

SMX-013 adds the portable-component/distribution contract that publishing, sandbox, browser-player, update, remix and final-architecture work must retrieve before selecting package bytes, a registry, or a dependency manager:

- `docs/research/SMX-013-COMPONENT-PACKAGES.md` — `PKG-001` through `PKG-028`, the local-definition→portable-package path, identity split, dependency/lock/offline rules, capability attribution, update/migration rollback, uninstall/cache semantics, source/remix/licensing/provenance policy, protected media contract, rejected alternatives, and downstream handoffs.
- `docs/research/SMX-013-PACKAGE-FIXTURES.json` — `PK-001` through `PK-020` machine-addressable package/component fixtures covering clean install, dependency update, local overrides, denied capability, missing dependency, incompatible migration and protected media boundaries.
- `experiments/smx-013-package-model/` — non-normative resolver/install/update/capability/provenance model plus adversarial tests; it is not a production registry, archive format, trust implementation or package manager.
- Durable candidate: an ordinary local reusable `DefinitionId` lineage becomes portable by adding a `PackageId` distribution namespace and immutable package revision; packaging does not create a second prefab/class/runtime object taxonomy and does not replace existing first-instance `ThingId` values.
- Human compatibility requirements are resolved intentionally into an **exact resolution lock** before runtime/streaming/publishing. Runtime and offline reacquisition consume the exact lock rather than floating ranges or “some cached compatible version”.
- Required, optional and lazy dependencies remain distinct; optional fallback is explicit. The current conservative candidate resolves one exact revision per `PackageId` per creation and reports incompatible transitive constraints rather than silently introducing ambiguous multi-version identities. Dependency cycles are rejected in this candidate and all resolution/acquisition work remains bounded.
- Capability requests remain declarations attributed to the requesting package/component principal. Parent package grants are not inherited, explicit live delegation may only narrow authority, and signatures/publisher identity/source availability/remix rights/provenance never grant host capability.
- Component/package update is acquire/verify/authorize/reconcile/migrate-before-commit. Concrete `ThingId`, valid sparse overlays, public interface identity and persistent state survive compatible updates; failed interface/overlay/migration/capability checks roll back to the old exact coherent lock/state.
- Uninstall is reference-aware while cache eviction is non-semantic. Offline operation requires the exact verified locked closure; residual persistent state is not silently erased by removing reconstructible package bytes.
- Source availability, remix permission, licence/attribution and derivation provenance are explicit distribution metadata. Sealed source is not DRM/trust; included source is not authority.
- Stable `AssetId` plus immutable digest/source/audio/media/provenance/licence/derivation metadata is an indivisible protected revision bundle. Package resolution, update, collaboration and publishing may not synthesize fields from different revisions.
- SMX-014 must package/deliver exact locks through generic players; SMX-016 must attack real archive/trust/dependency/capability boundaries; SMX-019 must prove group→reusable→portable→update/offline/publish usability without exposing package-manager complexity to ordinary authors.

### SMX-013 package-ecosystem primary/comparative anchors — checked 2026-09-19

- Cargo dependency requirements: https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html
- Cargo manifest versus exact lockfile: https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html
- npm 11 package-lock exact dependency tree/integrity precedent: https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/
- npm 11 package manifest precedent: https://docs.npmjs.com/cli/v11/configuring-npm/package-json/
- The Update Framework current specification: https://theupdateframework.io/specification/latest/
- SLSA 1.2 provenance: https://slsa.dev/spec/v1.2/provenance
- SPDX 3.0.1 licence expressions: https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/

These are implementation/security/provenance comparison inputs, not selected SplashMX dependencies or beginner product metaphors. `PKG-###` and `PK-###` are stable RAG identifier families for component/package semantics and fixtures.
