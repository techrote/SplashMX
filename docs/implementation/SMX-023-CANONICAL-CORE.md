# SMX-023 production canonical semantic core

**Status:** production implementation for SMX-023 / issue #48  
**Architecture:** SplashMX Architecture v1.0 unchanged  
**Module:** `canonical.core`

## Scope and ownership

SMX-023 implements the logical Object Fabric beneath later serialization, storage, execution, Godot, collaboration and networking work. The production module is `src/splashmx/canonical/core.py`; it owns role-typed semantic identity, Thing/relationship/port/Connection records, local Definition/instance/overlay semantics, reference states, tombstones and whole-result authored-state transactions.

It deliberately does **not** select physical bytes or storage, execute Behaviour IR, materialize Godot objects, define collaboration transport, or expose browser UI. SMX-024 owns deterministic physical serialization and the complete immutable protected Asset revision representation; SMX-025 owns crash-consistent local persistence.

## Durable identity contract

The core exposes separate runtime types for `ThingId`, `DefinitionId`, `ElementId`, `BehaviourAttachmentId`, `PortId`, `ConnectionId`, `AssetId`, `ProjectId`, `ProjectRevisionId` and internal semantic `RelationId`. Their string tokens are path-independent and their Python types are non-interchangeable. Hierarchy paths, `NodePath`, RID, ResourceUID/resource paths, DOM/database/cache identities, URLs, peer/socket/session/connection/process handles are not canonical identity inputs.

`CanonicalDocument.reference_state()` distinguishes live/loaded, known-unloaded, tombstoned and unknown Things. `TransientContext` is a separate process/editor/network structure and is not a field of the canonical document.

## Thing and relationship model

A Thing carries only its semantic ID, author label/state, stable ports, Behaviour-attachment declarations and tombstone state. Containment, transform locality, references, observation, control, simulation authority, persistence and replication are independent explicit relationship kinds. `SetContainment` updates only the active containment relationship for the child; tests pin that reparenting does not rewrite Thing identity, control, authority, persistence or replication records.

Connections address `ThingId + PortId` endpoints and keep canonical `ConnectionId` distinct from any transport connection identity. Event-output→command-input and readable-value→writable-value compatibility is validated before publication.

## Definitions, instances and overlays

`PromoteGroup` converts an existing containment subgraph into a local `DefinitionRecord` plus first `InstanceRecord` without reconstructing the existing Things. Stable `ElementId` loci map to the original concrete `ThingId` values. `InstantiateDefinition` requires the caller to allocate explicit independent concrete Thing/Relation identities; it never derives durable identity from hierarchy paths.

Definitions expose stable public `PortId` values mapped to internal element ports. Sparse state and parent overlays live on instances. A conservative `ReplaceDefinition` supports compatible property/structural revisions and safe removals while rejecting operations that invalidate overlays, durable references, live Connections or connected public interfaces. Addition of new definition elements is deliberately typed as `canonical.definition_migration_required` until a later migration layer can supply explicit concrete identity allocation rather than inventing path-derived IDs.

R-018-01 is encoded directly: definition conflict/override loci include the actual `DefinitionId`, so identical `ElementId` tokens in unrelated definitions do not false-conflict.

## Transaction and tombstone semantics

`apply_transaction()` deep-stages a candidate document, applies every operation to the draft, validates the complete resulting semantic document and only then returns the new `ProjectRevisionId` state. The input document is never mutated. Operation failure or final-document validation failure discards the draft. This is the production R-018-03 boundary.

Thing deletion is a durable tombstone. R-018-04 is enforced by atomically tombstoning every incident live Connection in the same staged transaction. A later Connection targeting a tombstoned Thing fails closed, preserving R-018-02 remove-wins semantics at the canonical document boundary. Connection identities remain reserved after tombstone and cannot be reused to resurrect an old edge.

Whole-document validation rejects duplicate/reserved identity use, role mismatches, multiple containment parents, containment/definition cycles, dangling or incompatible Connection endpoints, invalid Definition exposures, invalid instance mappings/overlays and live edges against tombstones. Durable authored state also rejects nested transient host/session/capability-handle fields.

## Production fixture lineage

`tests/production/test_smx023.py` ports relevant semantic obligations rather than importing the disposable research model implementations: SMX-002 T-001/T-002/T-004/T-006/T-007; SMX-003 CT-001/002/003/004/005/006/008/009/010; SMX-005 DT-001/002/003/004/007; SMX-015 OH-001/002/003/004/005/006/012/019; and SMX-018 CH-002/005/007/009/010/011/016/024/028 plus R-018-01..04.

The production suite adds boundary/adversarial cases for role confusion, nested transient-handle injection, duplicate identity after an earlier staged mutation, containment cycles, dangling ports, ConnectionId reuse after tombstone, connected public-interface removal and incompatible definition overlay updates.

## Protected source/audio/provenance semantics

SMX-023 introduces only the role-typed `AssetId` reference. It intentionally exposes **no** API for independently editing digest, source identity, source metadata, audio/media semantics, provenance, licence/attribution or derivation fields. Therefore this layer cannot field-mix a protected media revision. SMX-024 must implement the complete immutable Asset revision bundle as one coherent serialization/migration unit and retain the Architecture-v1 protected source/audio/provenance invariant.

## Rejected alternatives and residual handoff

The implementation does not adopt the SMX-002/003 Python proof models as production code, use hierarchy strings as IDs, collapse control/authority/persistence into parentage, make a database/engine object canonical, or infer new concrete Thing identities during definition revision.

The core is an in-memory logical production boundary. It does not yet prove physical serialization, bounded hostile parsing, crash recovery, execution scheduling or collaboration convergence. SMX-024 should serialize these records and protected Assets without changing semantic IDs; SMX-025 should publish/recover revisions atomically; SMX-026 may build the common IR/scheduler against stable `ThingId` and `BehaviourAttachmentId` roles. No Architecture-v1 amendment was required.
