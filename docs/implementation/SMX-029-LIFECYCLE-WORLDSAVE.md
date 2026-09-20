# SMX-029 — Lifecycle, WorldSave, snapshot and fresh-process restore

**Status:** production implementation contract  
**Issue:** SMX-029 / #54  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`

SMX-029 ports the retained SMX-007 lifecycle evidence into the production runtime. It does not reopen Architecture v1, replace SMX-025 authored-project storage, implement SMX-030 streaming/acquisition, or claim final Godot/browser materialization.

## Production contract

`src/splashmx/runtime/lifecycle.py` owns the persistent-runtime semantic boundary. A `WorldRuntime` combines an exact authored `CanonicalDocument` basis with live `ExecutionRuntime` state while keeping those planes distinct. A `WorldSaveSnapshot` is a deterministic persistent projection of runtime state addressed by `WorldSaveId` and immutable content-derived `WorldRevisionId`.

Snapshots are taken only from the production scheduler's serial, committed state. The SMX-026 activation executor commits or rolls back one bounded activation before returning, and SMX-028 replacement is prepare-before-publish. SMX-029 therefore never serializes provisional activation or hot-replacement drafts.

Restore is prepare-before-publish. The complete save is validated, exact authored and Behaviour artefacts are checked, runtime shells/state/RNG/pending work are rebuilt, and current capability requirements are resolved before the caller receives a replacement world. A failed restore returns no partially hydrated live world and cannot mutate the source save or previous live runtime.

## Lifecycle and reference states

Production lifecycle exposes four runtime phases:

- `active` — resident and accepting new author-visible dispatch;
- `dormant` — resident with preserved runtime state but no new dispatch through the lifecycle boundary;
- `known-unloaded` — semantically present/known while no live runtime object is required;
- `tombstoned` — explicitly destroyed identity with no live behaviour or pending work.

Absence from the catalog is `unknown`; it is not equivalent to unload or destruction. `WorldRuntime.reference_state()` maps active/dormant to `loaded`, unloaded to `known_unloaded`, destruction to `tombstoned`, and true absence to `unknown`.

Unload first captures durable runtime meaning, then removes resident state, programs, RNG objects, live queue entries and process-local service-request objects. Rehydration reconstructs those semantics from the retained record and exact authored/Behaviour basis. Destruction produces a tombstone with bounded diagnostic metadata and removes live state/work rather than silently reusing the `ThingId`.

The current SMX-026 timer primitive is a world-logical timer. SMX-029 preserves its exact due tick and sequence; it does not invent unimplemented `thing_active` or `external_wall` timer semantics. Any future additional clock domain must be explicit and versioned rather than silently reinterpreting existing timers.

## WorldSave plane

A WorldSave is not the editable project and is not a published creation. It stores only selected persistent runtime semantics against an exact `ProjectId` + `ProjectRevisionId` authored basis. It contains:

- public runtime state;
- stable `ThingId` / `BehaviourAttachmentId` identity;
- exact current Behaviour revision for each live attachment;
- attachment-private state;
- deterministic attachment PRNG state;
- logical world tick and scheduler sequence;
- durable timers and queued internal work;
- lifecycle/catalog records including known-unloaded and tombstoned identities;
- bounded non-authoritative external-wait descriptors.

It deliberately does **not** serialize authored-project bytes, collaboration operations/history/presence, published creation state, Godot Nodes/RIDs/resources, DOM objects, database/cache locators, browser objects, socket/peer/session/process handles, file/native handles, live capability grants/leases/tokens, or host adapter objects.

The canonical WorldSave representation is bounded deterministic JSON for this first runtime-state schema (`splashmx.world-save/1`). Its physical encoding is owned by the WorldSave module and must not be confused with the SMX-024 canonical project CBOR contract. `WorldRevisionId` is SHA-256 over canonical semantic WorldSave bytes excluding its own revision field, so semantic tampering cannot retain the old revision identity.

## Pending work and side effects

Durable internal work is represented explicitly. For timers and queued activations the save records stable target identity, attachment, handler, payload, due logical tick and deterministic scheduler sequence. Validation requires every saved pending timer to have exactly one matching queued timer activation; mismatched handler/payload/due/sequence state fails before restore.

External host effects are different. An already-issued `ServiceRequest` is saved only as an `ExternalWaitSnapshot` carrying bounded request/correlation data and `restore_policy="reauthorize"`. Restore never places that descriptor back into the executable host-service request outbox and therefore never reissues HTTP/file/device/etc. work merely because a save was loaded. A later explicit runtime action may reauthorize/reissue according to product policy with a new current authority check.

Committed emitted-work outbox entries are likewise not replayed as pending work. First-creation hooks are not replayed during hydration. A future explicit `restored` lifecycle event, if introduced, must be a fresh post-commit input rather than replay of pre-save work.

## Fresh-process restore and capability rebinding

Fresh restore needs only the validated WorldSave, the exact authored `ProjectRevisionId`, and exact referenced Behaviour programmes. No old `ExecutionRuntime`, Python object, Godot Node, DOM node, network peer/session, socket, browser promise, native pointer or service adapter survives or is required.

The production test suite closes and reopens the SQLite WorldSave store in a new Python process, rebuilds the canonical authored basis and exact IR artefact registry, restores runtime public/private state and a durable timer, and verifies that no service request is implicitly recreated.

Capability authority is rebound rather than serialized. Callers supply the current `CapabilityBroker` and current per-attachment `CapabilityRequirement`s. SMX-029 resolves them against stable `ThingId + BehaviourAttachmentId` principals before publication. Required authority that is absent, expired or revoked fails closed. No grant ID or capability token occurs in WorldSave bytes, preserving SMX-027 and R-016-04.

Recursive runtime-state validation independently preserves R-016-02 by rejecting normalized transient/authority field names anywhere inside public/private state, pending-work payloads or external-wait payloads.

## Crash-safe persistence

`SQLiteWorldSaveStore` is a WorldSave-specific persistent-head store. It intentionally uses separate `world_metadata`, `world_revisions` and `world_heads` tables rather than borrowing SMX-025 project-head ownership. Authored-project persistence and persistent-runtime progression therefore remain separate semantic planes even if an embedding application elects to keep both stores in one SQLite database file.

The store uses SQLite WAL plus `synchronous=FULL`, immutable revision bytes with SHA-256 readback verification, and one transaction for revision publication plus head advancement. Deterministic fault injection covers:

`prepared → revision_recorded → candidate_verified → head_advanced → committed`

Every interruption before COMMIT reopens the previous coherent head. An interruption after COMMIT reopens the complete new head. Corrupt bytes, digest mismatch, unsupported store versions and invalid WorldSave semantics are typed failures; they do not fabricate a partial runtime or destroy the previously committed revision.

## Adversarial and boundary coverage

`spec/production/smx029-lifecycle-fixtures.json` defines WS-001–WS-028 and retains LIF-001–LIF-018 plus the applicable R-016-02/R-016-04 findings. `tests/production/test_smx029.py` covers deterministic/non-mutating snapshots; authored/save/runtime plane separation; dormancy/unload/rehydrate/tombstone/unknown boundaries; exact private/RNG/timer/queue restoration; no implicit service/emitted/creation replay; recursive transient-authority rejection; current capability rebinding and revocation; exact-artifact and authored-basis mismatch; canonical bytes and revision tamper detection; every persistent-head interruption stage; corruption; non-destructive failed restore; and a real fresh-process reopen/restore.

The retained SMX-007 research harness remains evidence lineage, not production certification. SMX-030 still owns object-centric streaming and exact dependency acquisition. Phase-6 runtime work still owns actual Godot materialization, engine-handle reconstruction and target-specific lifecycle adapters.

## Protected source/audio/provenance boundary

SMX-029 does not acquire a second asset-authority model. A stable `AssetId` continues to select one complete immutable protected revision containing **content digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**. Those fields remain an indivisible canonical revision owned by the canonical/project/publication asset layers.

WorldSave may persist gameplay/runtime values that refer to an `AssetId`, but it does not embed, rewrite, field-mix or partially replace that protected revision. Any future restore path requiring asset bytes must resolve the complete exact protected revision through the canonical/streaming contract; target-private decoded/transcoded/cache state remains reconstructible context rather than source meaning. A failed snapshot, store commit, restore or migration can therefore leave the prior coherent WorldSave intact without altering protected media authority.
