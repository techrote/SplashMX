# SMX-038 — production Godot adapters and runtime profiles

**Issue:** #63 / SMX-038  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`  
**Mechanism selection:** `docs/research/SMX-037-GODOT-BINDING-SELECTION.md`  
**Production modules:** `src/splashmx/runtime/godot.py`, `src/splashmx/runtime/godot_target/`  
**Godot baseline:** 4.7.2 stable

## Contents

| Section | Summary |
|---|---|
| 1. Production contract | Defines the production target-private binding and runtime-profile boundary. |
| 2. Binding lifecycle | Implements sparse prepare-before-publish Godot realization without semantic-identity leakage. |
| 3. Scheduler bridge | Keeps engine callback order subordinate to the SMX-026 logical scheduler. |
| 4. Trusted service adapters | Routes render/audio/input/physics effects through the SMX-027 capability boundary. |
| 5. Runtime profiles | Uses one semantic source for native, browser and headless capability profiles. |
| 6. Protected media derivatives | Keeps decode/import/cache products subordinate to exact protected Asset revisions. |
| 7. Save/load and recreation | Separates semantic WorldSave restoration from target binding reconstruction. |
| 8. Adversarial contract | Freezes GRT-001..032 at the production adapter boundary. |
| 9. Measured evidence | Defines reproducible named-environment startup/materialization/churn/save-load/frame/memory evidence. |
| 10. Compatibility and downstream boundary | Records what SMX-038 proves and what remains for later physical-security/network/distribution phases. |

## 1. Production contract

SMX-038 implements the first production Godot realization selected by SMX-037. The durable relationship remains:

`ThingId -> transient private binding entry -> zero / one / many Godot objects`

A canonical Thing does **not** acquire a Godot `Node`, `NodePath`, RID, `ResourceUID`, resource path, instance ID, process handle, transport peer, browser object or cache key as semantic identity. The target projection contains stable SplashMX identities, requested private target facets and exact protected-Asset revision references only. The production boundary recursively rejects transient-engine, transport, process and serialized-authority fields before target activation or trusted host use.

The implementation is deliberately split in two:

- `src/splashmx/runtime/godot.py` owns the production SplashMX-side contract: typed target profiles, fail-closed preparation, private binding lifecycle, normalized engine-event queue, capability-mediated host adapters and exact protected-media derivative-cache keys.
- `src/splashmx/runtime/godot_target/` is the generic Godot 4.7.2 target runtime used by native/headless execution and the exported Web/Linux builds. It materializes the same sparse facet strategy selected by SMX-037 and emits reproducible target evidence.

This is an implementation beneath Architecture v1. No frozen semantic amendment is required.

## 2. Binding lifecycle

`BindingTable` stages a complete candidate binding set before publication. Materialization is independently bounded by maximum semantic binding count and maximum private engine-object count. If a factory fails, a feature is incompatible, or a resource bound is exceeded, newly created private objects are cleaned up and the previous published table remains authoritative.

For the first production target profile:

- `render_2d` and `input` may share a private `Node2D`;
- `physics_2d` uses private `Area2D` plus `CollisionShape2D`/shape state;
- `audio_basic` uses private `AudioStreamPlayer`;
- a semantic-only Thing receives no engine object.

Binding recreation is keyed by stable `ThingId`. Destroying/replacing Godot objects changes only target-private generation/object state. `ThingId`, authored state, Behaviour identity, `WorldSave` meaning, package/publication identity and protected `AssetId` meaning remain unchanged. Safe diagnostic views expose only semantic IDs and active facet names; raw engine objects are available only through the trusted target-private interface.

## 3. Scheduler bridge

Godot callbacks do not execute Behaviour code and do not define author-visible order. `SemanticTurnBridge` captures normalized `EngineEvent` values and sorts them by explicit logical/author/source ordering fields before forwarding them to the existing production `ExecutionRuntime`.

The bridge has its own bounded pending-input queue, but it cannot bypass SMX-026 budgets. Queue admission into `ExecutionRuntime` still uses the production scheduler and therefore retains independent instruction, recursion, allocation, emitted-work, timer, service-request, queue and activation-run limits. A scheduler rejection preserves not-yet-forwarded normalized inputs rather than silently dropping or replaying already-forwarded work.

The production Godot target repeats the same ordering probe after reversing callback-arrival order. Engine `_process`, physics, signal or input callback order therefore remains an implementation detail rather than a public SplashMX scheduling contract.

## 4. Trusted service adapters

Render, audio, input and physics host effects are registered as distinct `HostServiceAdapter` families:

- `godot.render` -> `godot.render` capability;
- `godot.audio` -> `godot.audio` capability;
- `godot.input` -> `godot.input` capability;
- `godot.physics` -> `godot.physics` capability.

Ordinary Behaviour code can only emit the existing mediated `ServiceRequest`. SMX-038 resolves that request to a bounded typed target while SMX-027 remains the authority for principal attribution, scope, quotas, expiry, revocation and delegation. Host invocation occurs only through `TrustedHostServiceBoundary.execute`, which performs the R-016-04 final authorization recheck immediately before crossing to the target adapter.

The SMX-038 regressions demonstrate that admission does not itself invoke Godot, missing or cross-family capability fails closed, and revocation between admission and execution prevents the physical host effect. Service payloads recursively reject Godot/runtime handles, and returned values must also pass the existing SMX-027 untrusted-value boundary before they can flow back toward semantic execution.

## 5. Runtime profiles

Native, browser and headless execution use one target projection and one Godot runtime source. A profile declares available target facilities; the creation/runtime projection declares required and optional facilities.

Preparation is fail-closed:

- every required feature must be available before any binding is materialized;
- optional unavailable features are recorded as explicit degraded facilities;
- unknown features and undeclared Thing facets are rejected rather than reinterpreted.

The production acceptance fixture requires `physics_2d` and treats `render_2d`, `input` and `audio_basic` as optional. The current named headless profile therefore materializes physics while omitting optional presentation/input/audio. This is **not** a separate headless canonical format: if a future creation declares rendering or audio as required, that same headless profile produces a typed `godot.required_feature_unavailable` outcome before target activation.

Web and Linux are exported from the exact same generic Godot project. The real Chromium job executes the Web export; the Linux export is executed headlessly as an additional packaged-runtime check.

## 6. Protected media derivatives

The protected-media Architecture-v1 invariant is unchanged. Stable `AssetId` selects one complete immutable revision containing:

- digest/source digest;
- source identity;
- source metadata;
- audio/media semantics;
- provenance;
- licence/attribution metadata;
- derivation lineage.

The Godot target receives only exact `AssetId + revision_digest` references. `MediaDerivativeCache` keys every decoded/imported/transcoded/target-private product by the exact protected revision plus runtime profile and derivative kind. An unknown Asset or a competing digest for an existing `AssetId` is rejected. Evicting or replacing a derivative cannot change the canonical revision registry.

The target runtime exercises this boundary with a private `AudioStreamWAV` derivative and verifies that a competing protected revision is rejected and cache eviction is a semantic no-op. Source identity/metadata, audio/media semantics, provenance, licensing and derivation fields are never reconstructed from target cache entries and cannot be field-mixed by the adapter.

## 7. Save/load and recreation

SMX-038 does not serialize Godot bindings into `WorldSave`. `tools/export_smx038_fixture.py` constructs the production SMX-031 core, executes it, snapshots through SMX-029, serializes the snapshot, and records an exact semantic fingerprint. The target runtime then performs binding churn while verifying that this fingerprint remains unchanged.

`tools/measure_smx038.py` independently exercises production WorldSave snapshot -> serialization -> deserialization -> fresh runtime restore for repeated samples. It verifies public state, attachment-private state and lifecycle/reference state after restore. This freezes the required ordering: reconstruct and validate semantic state first; establish current-target bindings afterward. Surviving Node/RID/resource/process/browser handles are neither needed nor accepted.

## 8. Adversarial contract

`spec/production/smx038-godot-runtime-fixtures.json` freezes **GRT-001..032**. Production Python tests plus real-Godot/browser jobs cover:

- same semantic source across native/browser/headless profiles;
- required-feature rejection and optional-feature degradation;
- duplicate/undeclared semantic projection failures;
- protected-Asset competing revision rejection;
- recursive `NodePath`/RID/`ResourceUID`/transport/process/instance-handle rejection;
- sparse zero-binding semantic Things and prepare-before-publish rollback;
- independent binding/object/input/derivative bounds;
- callback capture without direct Behaviour execution;
- callback-arrival-order independence and retained SMX-026 scheduler budgets;
- four separate capability-mediated target service families;
- denial, confused-deputy and revoke-between-admit/use cases;
- unsafe target result rejection;
- exact media derivative keys, conflicting/unknown Asset rejection and semantic-no-op eviction; and
- exact protected reference preservation across all runtime profiles.

The SMX-038 workflow also retains the relevant SMX-026, SMX-027, SMX-029, SMX-031, SMX-036 and SMX-037 validators so the adapter cannot silently weaken its production dependencies.

## 9. Measured evidence

The CI campaign records two complementary evidence classes on the exact tested commit.

**Production semantic evidence** records Python/runtime/platform metadata and repeated SMX-031 startup plus production SMX-029 WorldSave serialize/restore/round-trip timings, serialized size, stable snapshot fingerprint, restored semantic probe and exact protected-Asset reference.

**Real Godot evidence** records Godot version, OS/architecture, target profile, available/active/degraded facilities, startup-to-ready, materialization time, forty binding-recreation cycles, repeated centralized scheduler ordering, adapter and derivative probes, private binding count, Godot node/object counts, static-memory observations and thirty engine-loop frame-delta samples. Native/headless source runs, an executed exported Linux runtime and a real Chromium Web-export run are all retained as artifacts.

These measurements are deliberately labelled as evidence for the named CI/browser/runtime environment. They are useful for detecting gross architecture regressions and proving that the selected mechanisms execute on real targets; they are **not** universal supported-hardware frame/audio/physics SLO certification. GATE-10 product target qualification remains broader than this one campaign.

## 10. Compatibility and downstream boundary

SMX-038 satisfies the Phase-6 production binding handoff without changing the canonical model or publishing contract. Immutable creations remain generic SplashMX data loaded by a separately deployed generic runtime; the target adapter does not introduce per-creation Godot compilation as an ordinary path.

The following remain downstream and are not overclaimed here:

- SMX-039..041 physical parser/archive/decoder/process/origin isolation, hardened Godot configuration and calibrated hostile resource-accounting certification;
- Phase-9 production networking transports, signalling/NAT/authentication/congestion/reconnect/failover;
- broad cross-browser/mobile/native hardware qualification and final product SLOs;
- Phase-10 hosted retention/CDN/native installer/update/recovery operations.

No SMX-038 evidence contradicts Architecture v1 or the SMX-037 selected mechanism. If later real-target evidence exposes such a contradiction, the project must use an explicit ADR/amendment plus regression rather than hiding the conflict in a target adapter.
