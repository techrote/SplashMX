# SMX-037 — production Godot realization and scheduler-integration selection

**Status:** selected mechanism for SMX-038 handoff  
**Issue:** #62  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Godot baseline:** 4.7.2 stable  
**Scope:** bounded Phase-6 spike; not the production Godot adapter implementation

## Contents

| Section | Summary |
|---|---|
| 1. Decision | Selects sparse private facet bindings plus one centralized semantic scheduler bridge. |
| 2. Production-core workload | Defines how the spike projects the real SMX-031 core rather than a replacement semantic model. |
| 3. Candidates and falsification | Records compared realization layouts and why alternatives are not selected. |
| 4. Scheduler/event-loop boundary | Keeps observable ordering under SplashMX control rather than SceneTree callback order. |
| 5. Measured evidence | Defines reproducible real-Godot measurements and their deliberately narrow interpretation. |
| 6. Target profiles | Records browser/native/headless consequences as capabilities, not canonical forks. |
| 7. Identity, lifecycle and protected media | Freezes the non-leakage/recreation handoff to SMX-038. |
| 8. Adversarial and boundary evidence | Maps the executable GBS-001..024 corpus. |
| 9. Rejected alternatives | Records why Node-is-Thing and callback-owned semantics remain rejected. |
| 10. SMX-038 handoff | States exactly what production implementation may rely on and what remains open. |

## 1. Decision

Select a **sparse private facet-binding realization with a centralized SplashMX turn bridge** for the first production Godot adapter.

A canonical Thing does not receive a mandatory Godot owner merely because it exists. A Thing has a target-private binding entry keyed by stable `ThingId`; that entry may contain zero, one or several Godot objects according to the currently materialized presentation/physics/audio/input facets. Semantic-only and known-unloaded Things can therefore exist with zero Godot objects. Binding destruction/recreation does not mutate `ThingId`, authored state, WorldSave meaning, Behaviour identity, package/creation identity or protected-Asset meaning.

The event-loop integration is likewise deliberately asymmetric: Godot callbacks collect trusted adapter inputs and request work, but one centralized SplashMX bridge converts those inputs into explicit scheduler activations. The common IR scheduler remains authoritative for logical tick, author-visible attachment order, transaction boundaries, budgets, timers, continuations and service-request ordering. No `_process`, `_physics_process`, scene-tree order or per-Node callback order becomes a public execution rule.

This is an implementation selection below Architecture v1. It does not require an ADR or change any frozen semantic contract.

## 2. Production-core workload

`tools/export_smx037_fixture.py` imports the actual SMX-031 integration fixture and builds a target projection from the resulting production canonical project. The exporter first requires its projection table to cover exactly the current SMX-031 production `ThingId` set, so an obsolete hand-written object list fails rather than silently becoming a second model.

The projection contains only:

- stable `ThingId` plus a private requested-facet list used by the spike;
- deterministic scheduler events expressed in SplashMX semantic identity/order fields;
- exact `AssetId + protected revision digest` references;
- target capability profiles; and
- the forbidden runtime-handle vocabulary used by the adversarial gate.

It intentionally does **not** project source metadata, audio/media semantic fields, provenance, licence/attribution or derivation lineage into the Godot adapter. Those fields remain owned by the complete canonical protected Asset revision. The adapter may retain an exact reference to that revision; it cannot reconstruct or field-mix it.

This keeps the spike dependent on the production core without claiming that the spike itself is production runtime code.

## 3. Candidates and falsification

Three plausible layouts are implemented in real Godot 4.7.2:

1. **`node_per_thing`** — every Thing receives one private `Node2D`, with additional facet-specific children.
2. **`scene_subtree`** — every Thing receives one private owner `Node`, with render/input, physics and audio child objects.
3. **`facet_sparse`** — there is no mandatory per-Thing Node. Only target facets that need engine facilities receive private engine objects; render+input can share a `Node2D`, physics uses private `Area2D`/`CollisionShape2D`, and audio uses private `AudioStreamPlayer`.

All three are exercised with the same production-core-derived workload, exact protected Asset reference, deterministic scheduler trace and repeated worker binding churn. The selection algorithm refuses to compare performance until semantic/adversarial checks pass. It then selects `facet_sparse` only when its measured private engine-binding count is no greater than either mandatory-owner candidate. Timing and memory are recorded as secondary environment-specific evidence, not used to invent a universal SLO from one CI host.

The sparse selection is therefore not "fewer Nodes is always faster." It is narrower: mandatory owner objects provide no required semantic property, increase private object cardinality for semantic-only Things, and couple implementation shape to semantic object count without evidence that the coupling buys correctness. The sparse binding table preserves all required identity/lifecycle properties while leaving SMX-038 free to introduce optimized facet-specific realizations where measured workloads justify them.

## 4. Scheduler/event-loop boundary

The selected integration is **one semantic turn bridge**, not per-Thing semantic execution in engine callbacks.

The spike sorts activation requests by explicit `(logical_tick, author_order, sequence, ThingId, BehaviourAttachmentId)` fixture keys and repeatedly compares the trace after reversing arrival/insertion order. This is not a new execution contract: it is a platform-binding demonstration that SMX-026 ordering can remain authoritative even when engine callbacks arrive in an inconvenient order.

SMX-038 must preserve these rules:

- `_process`, `_physics_process`, input callbacks, audio callbacks and signal order may enqueue normalized external inputs/effects but do not directly define semantic Behaviour order;
- semantic activations continue through the production SMX-026 scheduler and its independent budgets;
- adapter effects occur only after the relevant semantic transaction has committed;
- timers/continuations remain SplashMX semantic work, not surviving Godot coroutine or Node lifetime;
- physics stepping may use Godot's physics cadence privately, but any author-visible ordering contract is translated at the bridge rather than inherited from undocumented engine callback order.

## 5. Measured evidence

`tools/measure_smx037.py` launches the real Godot binary and records `splashmx.benchmark-evidence/1` records for every candidate. The CI baseline is pinned to Godot **4.7.2** in `barichello/godot-ci:4.7.2` on `ubuntu-24.04`.

The campaign records:

- separate headless process launch-to-exit samples as startup evidence;
- candidate materialization time;
- repeated worker binding destruction/recreation time;
- repeated centralized-scheduler ordering time;
- Godot node/object deltas;
- debug/static memory delta where the runtime exposes it; and
- private engine-binding cardinality.

It also instantiates representative private render (`Node2D`), physics (`Area2D` + `CollisionShape2D`), audio (`AudioStreamPlayer`) and normalized input (`InputEventAction`) paths. The same spike project is exported to Web and Linux from one source tree to catch target-build incompatibilities before SMX-038 hardens the adapters.

The emitted evidence names runtime version, commit SHA, OS/architecture/hardware metadata, workload and sample count. It explicitly identifies the GPU field as headless/no-render-performance-claim. These numbers select a binding mechanism and reveal gross architecture overhead; they are **not GATE-10 supported-hardware certification**, real renderer/audio-device quality evidence, or a broad browser frame-time claim.

## 6. Target profiles

The same semantic fixture is evaluated under native, browser and headless capability profiles. Profiles are adapter policy; they are not different canonical project formats.

- **Native:** render/input/physics/basic-audio facilities are available for this spike profile. Production authority still remains capability-mediated.
- **Browser:** the same private realization strategy applies. Godot 4.7 web constraints such as Compatibility/WebGL2, browser lifecycle, storage and audio differences remain typed target policy. Unsupported **required** semantics fail before activation; optional facilities may degrade or be omitted explicitly.
- **Headless:** presentation/audio/input may have zero bindings. A semantic Thing is not removed merely because it has no presentation object. The spike keeps physics as the representative required facility only to exercise a live engine path; SMX-038 must derive actual omission from semantic usage/capability declarations rather than file type or a separate headless creation model.

Web and Linux exports in CI prove that the selected source layout is portable across those Godot target builds. Running and measuring production browser/native/headless profiles remains SMX-038 work.

## 7. Identity, lifecycle and protected media

The selected adapter contract is:

`ThingId -> transient private binding entry -> zero/one/many Godot Objects`

The arrow is one-way with respect to durable identity. Godot instance IDs, NodePaths, RIDs, ResourceUIDs, resource paths, transport peers, sockets, sessions and process handles may exist inside private adapters but cannot become canonical lookup authority or serialized creation/WorldSave fields.

The adversarial campaign repeatedly frees and recreates the worker binding and verifies the binding table still resolves the same `ThingId`. SMX-038 must perform restore/materialization in the Architecture-v1 order: reconstruct/validate semantic state first, then establish current-target bindings. Binding loss is therefore recoverable runtime state, not semantic destruction.

Protected media remains stricter. Stable `AssetId` selects one complete immutable revision containing content/source digest, source identity, source metadata, audio/media semantics, provenance, licence/attribution and derivation lineage. The Godot binding projection carries only exact `AssetId + revision_digest`. Decode/import/GPU/audio objects and target transcodes are derivatives/caches beneath that reference. Recreating a binding cannot rewrite or field-mix the protected revision.

## 8. Adversarial and boundary evidence

`spec/production/smx037-godot-binding-fixtures.json` freezes GBS-001..024. The real Godot campaign plus production Python boundary tests cover:

- duplicate/missing semantic identity rejection;
- recursive forbidden engine/runtime handle-field rejection;
- semantic-only zero-binding behavior;
- stable identity across repeated binding replacement;
- scheduler equivalence under reversed input arrival;
- fail-closed required target features and explicit optional degradation;
- representative render/physics/audio/input private paths;
- exact protected Asset revision-reference preservation;
- real Godot startup/materialization/churn/scheduler/object/memory evidence; and
- same-source Web/Linux exportability.

The campaign fails rather than selecting a candidate if any semantic/adversarial result is false.

## 9. Rejected alternatives

**Node is Thing** remains rejected. Neither `node_per_thing` nor `scene_subtree` is allowed to promote its private owner object into durable identity. They are retained as measured baselines only.

**Per-Node Behaviour execution from `_process`/signals** is rejected. It would make semantic ordering depend on engine callback/tree arrangement and would encourage behaviour ownership to follow hierarchy, contrary to P4/P5 and SMX-026.

**Direct RID/ResourceUID/NodePath serialization** is rejected. These are useful private implementation handles but fail the path-independent identity and restore contracts.

**One target-specific canonical project per browser/native/headless profile** is rejected. Target differences are capabilities/projections over the same semantic revision.

**Using timing alone to pick the layout** is rejected. Microbenchmark latency on one CI host is noisy and cannot justify semantic coupling. Correctness/non-leakage are hard gates and private object cardinality is the deterministic architecture-overhead discriminator; timings remain recorded evidence.

## 10. SMX-038 handoff

SMX-038 may now implement `runtime.godot` around these selected implementation rules:

- stable semantic identities index a private binding table;
- bindings are sparse and facet-driven, not mandatory Node ownership;
- binding entries support zero/one/many engine objects and independent destruction/recreation;
- one centralized bridge feeds normalized target inputs into the existing production scheduler;
- target unsupported-feature results are typed capability/compatibility outcomes;
- protected Asset revisions remain canonical and indivisible while Godot products remain derivatives;
- browser/native/headless profiles share the same semantic/runtime source and differ below the target capability boundary.

SMX-038 still owns the **production** binding lifecycle, trusted render/audio/input/physics service adapters, media decode/import derivative cache, actual generic web/native/headless player integration, real save/load/materialization and frame-time measurements, and production error/diagnostic plumbing. Phase 7 still owns decoder/process/origin/sandbox certification.

No Architecture-v1 semantic amendment was required by this selection.
