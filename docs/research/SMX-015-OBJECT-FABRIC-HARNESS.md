# SMX-015 — Destructive Object Fabric integration harness

**Status:** candidate research result, 2026-09-19  
**Scope:** disposable semantic falsification harness for P0–P4. It is **not** a production runtime, canonical byte format, Godot binding, package parser, security sandbox, performance benchmark, or Architecture v1.0.

## Question and result

SMX-015 asks whether the accepted Thing, composition, behaviour, canonical-state, lifecycle, streaming, and Godot-boundary contracts still cohere when exercised together rather than only in isolated proof models.

The integrated harness passes all five required experiments with **37 deterministic** adversarial/boundary tests:

- **P0 universal kernel:** one `Thing` semantic type covers materially different visual, UI, audio, gameplay/physics, procedural, and persistent cases. Containment remains independent from controller, simulation authority, persistence, replication, observation, and durable references.
- **P1 hot behaviour replacement:** live replacement preserves `ThingId` and `AttachmentId`; same-schema private state carries forward; schema change and pending work require explicit migration/remapping; dependency, migration, or continuation failure leaves previous live state coherent.
- **P2 nested composition/local definitions:** an ordinary authored group promotes into a Definition while the original concrete Things become the first Instance without identity replacement. Nested instances remain ordinary Things. Public interfaces are stable semantic indirections rather than hierarchy paths. Structural conflicts fail atomically.
- **P3 exact serialize/restore:** a JSON round trip into a fresh `FabricWorld` reconstructs tested Things, definitions/instances, references, behaviour-private state, durable pending work, residency, relationship maps, tombstones, and protected asset revisions from semantic data plus declared behaviour/artifact catalogs. Engine/session/capability context is absent.
- **P4 stream arbitrary subgraphs:** a resident inventory retains a reference to a door while the containing town and door unload; the door can reload without the town; dependency corruption/unavailability prevents partial publication; an unloaded Thing can undergo explicit compatible behaviour migration and rehydrate with the same `ThingId`.

No integrated experiment exposed a contradiction in accepted upstream semantics. Naive implementation failures found during review—publishing before exact dependency validation, partial instance creation after an ID collision, restoring invalid containment, silently dropping pending continuations, or field-merging protected media metadata—were already forbidden by earlier contracts and now have explicit regressions. **No upstream authoritative contract required semantic amendment** as a result of SMX-015.

This result strengthens the object-fabric hypotheses at integrated model level. It does not turn them into production proof. SMX-016 still owns hostile sandbox/resource work, SMX-017 real topology equivalence, SMX-018 collaboration-substrate proof, SMX-019 real Godot/browser/editor/player/performance evidence, and SMX-020 final Architecture v1.0 reconciliation.

## Authority carried into the harness

The disposable model re-expresses only the minimum overlapping contracts from SMX-002–009 and the protected distribution semantics from SMX-013/014:

- stable path-independent Thing identity with explicit state/facets/ports and independent relationships;
- group-as-Thing, Definition/Element/Instance identity, sparse overrides, stable public interfaces, conservative reconciliation;
- stable behaviour attachment identity, private state, transactional replacement, explicit continuation mapping and migration;
- engine-independent semantic records and fresh restore rather than engine/process serialization;
- capability authority as transient mediated context, never inferred from hierarchy, package provenance, signature, or source availability;
- loaded/known-unloaded/tombstoned/unknown reference states and object-centric residency;
- exact immutable artifact acquisition with validate-before-publish semantics;
- no `Node`, `NodePath`, `RID`, `ResourceUID`, peer ID, or decoded target resource as public identity;
- stable `AssetId` plus complete digest/source/audio/provenance/licence/derivation semantics as one protected revision bundle.

The harness contains no Godot API. That is deliberate for P0–P4 semantic falsification: a contract that only worked while a live Godot object survived would fail P3. Real binding and frame cost remains an empirical downstream question.

## Integrated boundary invariants

- `OF-001` — One universal Thing semantic type covers representative visual/UI/audio/gameplay/procedural/persistent cases without category-specific ownership managers.
- `OF-002` — `ThingId` is path-independent, unique within a lineage, and never silently reused after destruction.
- `OF-003` — Containment is independent from control, authority, persistence, replication, and observation relationships.
- `OF-004` — Reparenting cannot silently mutate non-containment relationships or durable references.
- `OF-005` — Group promotion creates a reusable Definition while preserving the original concrete Things as the first Instance.
- `OF-006` — `DefinitionId`, `ElementId`, `InstanceId`, `ThingId`, and public `PortId` remain distinct stable loci.
- `OF-007` — Public exposures are stable indirections over `ElementId + PortId`, not hierarchy paths.
- `OF-008` — Definition revision reconciliation preserves compatible concrete identities and explicit sparse overrides.
- `OF-009` — Invalidated overrides or connected public interfaces make reconciliation fail atomically.
- `OF-010` — Behaviour replacement preserves `ThingId` and `AttachmentId` and commits at an explicit semantic boundary.
- `OF-011` — Same-schema behaviour replacement preserves private state; schema changes require explicit bounded migration.
- `OF-012` — Pending durable work must remain valid, be explicitly remapped, or be explicitly cancelled; incompatible swaps fail without mutation.
- `OF-013` — Replacement dependencies are acquired and integrity-checked before migration/live publication.
- `OF-014` — Failed acquisition, continuation mapping, or private-state migration leaves the previous live semantics coherent.
- `OF-015` — Snapshot/save state is a semantic projection, not serialization of live engine/process objects.
- `OF-016` — Fresh-runtime restore reconstructs tested Things, definitions/instances, references, private state, durable pending work, and protected asset revisions from data plus declared catalogs.
- `OF-017` — Engine bindings, peer/session IDs, capability grants, decoded target resources, and other transient context are excluded from durable snapshot authority.
- `OF-018` — Restore validates identity, definition/revision, behaviour/private-schema, containment, and artifact compatibility before publishing resident state.
- `OF-019` — References distinguish `loaded`, `known_unloaded`, `tombstoned`, and `unknown` targets.
- `OF-020` — Arbitrary selected Things/subgraphs can cross residency boundaries without requiring their containment region to cross with them.
- `OF-021` — Loading stages required exact artifacts and publishes requested Things only after all dependencies validate.
- `OF-022` — Missing, denied, or corrupt dependencies fail without partially publishing requested Thing residency or creation.
- `OF-023` — Compatible behaviour migration can occur across an unloaded Thing record while retaining `ThingId` and explicit pending-work semantics.
- `OF-024` — Logical streaming/residency does not confer, inherit, or persist ambient host/capability authority.
- `OF-025` — Stable `AssetId` points to one complete immutable revision bundle: digest, source identity/metadata, media/audio semantics, provenance, licence, and derivation.
- `OF-026` — Protected asset revisions are replaced atomically; field-wise mixes or incomplete revisions are rejected without mutating the previous revision.
- `OF-027` — Snapshot/restore and stream-out/in preserve protected source/audio/provenance semantics exactly; target-private decoded/transcoded handles remain non-canonical.
- `OF-028` — No Godot `Node`/SceneTree/Resource/RID/NodePath identity enters the tested semantic contract; Godot remains a replaceable substrate for these paths.
- `OF-029` — The harness is disposable and non-normative; passing P0–P4 does not freeze physical encoding, production runtime, performance, or security implementation.
- `OF-030` — Future P0–P4 failures must be classified as harness defect versus architecture defect; architecture defects amend authoritative upstream contracts and gain regression coverage rather than being hidden by special cases.

## P0 universal kernel

Fixtures `OH-001`–`OH-003` pressure materially different corpus domains and simultaneous relationships. Visual, audio, UI, physics/gameplay, procedural, and persistent/networked records use the same `Thing` class. Reparenting a controlled/authoritative object does not rewrite controller, authority, persistence, replication, observer, or reference meaning. Duplicate IDs, tombstone reuse, and containment cycles fail closed.

**Finding:** H-001/H-002/H-003/H-008 are strengthened at integrated model level.

## P1 hot behaviour replacement

Fixtures `OH-007`–`OH-009` exercise same-schema replacement, schema migration, pending continuation mapping, missing/revoked replacement artifacts, and rollback. Replacement artifacts validate before the attachment mutates. A schema change requires an explicit mapping. A pending handler that the replacement cannot service must be explicitly mapped or cancelled; otherwise the swap fails. Semantic ports remain stable through implementation replacement.

**Finding:** H-005/H-008/H-018 are strengthened; no object reconstruction or hidden state loss is required for the tested cases.

## P2 nested composition/local definitions

Fixtures `OH-004`–`OH-006` promote an ordinary group into a Definition while keeping the original `ThingId` values as the first Instance, create a second instance from the same semantic kernel, and retain independent control/authority relationships. Public exposure is a stable `ElementId + PortId` indirection and survives internal reparenting. Definition update conflicts involving overridden elements or connected public endpoints reject atomically. Promotion and instantiation now preflight Definition/Instance/Thing identity collisions before any partial mutation.

**Finding:** H-002/H-003/H-004/H-008 are strengthened further.

## P3 exact serialize/restore

Fixtures `OH-010`/`OH-011` serialize semantic state through JSON and restore into a **fresh `FabricWorld`**. Tested restoration includes public state, references, behaviour attachment/private state, durable pending work, relationship maps, definitions/instances, residency, tombstones, and full protected asset revisions. Restore rejects duplicate live IDs, live/tombstone collisions, missing behaviour revisions, private-schema/artifact mismatches, unknown containment parents, containment cycles, invalid instance/definition revisions, and unavailable exact resident artifacts before resident publication.

The snapshot deliberately excludes transient `context`: Godot nodes/resources, decoded target media, peer/session IDs, sockets, live capability grants, browser handles, and editor presence/selection are rebound from current runtime policy.

**Finding:** H-007/H-008/H-010/H-014/H-018 are strengthened at integrated semantic level.

## P4 stream arbitrary subgraphs

Fixtures `OH-012`–`OH-016` use the required inventory-key/door/town pressure. The resident inventory keeps `refs["key_target"] == "door"` while `town` and `door` are unloaded. The door resolves as `known_unloaded`, can be loaded independently of its containment region, and changes to `tombstoned` only after destruction. Missing/offline/tampered artifacts leave residency unchanged. Creating a resident Thing with a missing hard artifact is also atomic: no half-created semantic object appears. An unloaded behaviour can migrate under the same exact-artifact/private-state/continuation rules and rehydrate with the same `ThingId`.

**Finding:** H-010/H-011/H-018 are strengthened substantially at integrated model level.

## Protected source/audio/provenance boundary

Fixtures `OH-017`/`OH-018` carry protected media semantics directly through snapshot and streaming tests. A stable `AssetId` identifies a whole immutable revision with digest, source identity, source metadata, audio/media semantics, provenance, licence, and derivation lineage. `replace_asset()` accepts only that complete field set. A partial revision is rejected without mutating the old revision; a competing valid revision replaces the entire bundle rather than field-merging. Unload/load and fresh restore preserve the exact canonical bundle, while a target-private decoded audio object exists only in transient context.

This explicitly preserves the source/audio/provenance semantics established by SMX-005/009/011/012/013/014.

## Failure classification and residual evidence boundary

The integrated review found implementation-level hazards, not a semantic contradiction: publish-before-validate, partial identity mutation, invalid containment restore, silent pending-work loss, and synthetic media provenance. Each now has an adversarial regression. If later work discovers that the accepted semantics themselves cannot satisfy a required case, `OF-030` requires the authoritative contract to be amended rather than patching around the failure locally.

Passing P0–P4 is **not** evidence for malicious parser/archive escape resistance, production resource limits, final package/container bytes, trust roots/signature rotation, real Godot render/physics/audio cost, WebAssembly startup/heap/frame cost, browser suspension/storage durability, real network loss/topology equivalence, collaboration compaction, or editor usability/accessibility.

### O-020 handling

O-020 remains **OPEN**. This issue supplies a semantic workload and integration boundary, not a named Godot/browser/hardware benchmark. Reporting CPython object timings as Godot object-fabric performance would be false evidence. SMX-019 must measure creation/binding, instance materialization, hot replacement, restore, and residency transitions against real Godot/browser builds with runtime/hardware metadata. This is an evidence boundary, not an unmet #15 acceptance criterion.

## Hypothesis effects

- H-001 strengthened further at integrated model level.
- H-002 strengthened further: hierarchy stays structural across P0/P2/P4.
- H-003 strengthened further: groups and leaves use the same Thing kernel.
- H-004 strengthened further at local-definition integration level.
- H-005 strengthened substantially across exact acquisition, migration, pending work, unload and rehydrate.
- H-006 unchanged; no new compiler/IR breadth evidence is claimed.
- H-007 strengthened further by fresh engine-independent semantic restore.
- H-008 strengthened further across promotion, restructure, restore, unload/reload and hot replacement.
- H-009 unchanged; the no-ambient-authority rule is preserved but hostile proof belongs to SMX-016.
- H-010 strengthened substantially at integrated model level.
- H-011 strengthened substantially by selective door loading independent of town containment.
- H-014 strengthened at semantic boundary only; performance remains O-020/SMX-019.
- H-018 strengthened substantially by explicit compatibility/migration/rollback behavior.

H-012/H-013/H-015/H-016/H-017 receive no direct status change from SMX-015.

## Downstream handoff

- **SMX-016:** attack real parser/package/IR/capability/resource boundaries; do not mistake this Python model for a sandbox.
- **SMX-017:** run one creation/network declaration through real offline/peer-hosted/dedicated failure schedules while preserving these identity/lifecycle/streaming rules.
- **SMX-018:** test SMX-011 collaboration semantics over stable document/definition/instance loci; do not reuse runtime replication as edit synchronization.
- **SMX-019:** own real Godot/browser object cost, storage, editor/player workflow, generic-player integration, and create→play→save/reload→publish/load usability/performance.
- **SMX-020:** carry P0–P4 evidence, explicit non-results, and O-020 residual risk into Architecture v1.0 reconciliation.

## Reproduction

```text
python tools/validate_smx015.py
python -m unittest discover -s experiments/smx-015-object-fabric-harness -p 'test_*.py'
```

Expected result: **37 tests pass**. The test count is descriptive; `OF-###`/`OH-###` IDs are the durable retrieval surface. CI runs on CPython on GitHub `ubuntu-latest`. No Godot/browser/native renderer is invoked, so no Godot/browser performance claim is made.
