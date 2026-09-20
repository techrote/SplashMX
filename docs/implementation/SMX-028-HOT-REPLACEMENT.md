# SMX-028 — Transactional Behaviour hot replacement

Status: production implementation for issue #53. Architecture authority remains `docs/architecture/ARCHITECTURE-V1.md`; this document narrows implementation mechanics without amending Architecture v1.0.

## Production contract

A live Behaviour replacement is an explicit compatibility edge between one exact source `behaviour_revision` and one exact target `behaviour_revision`. The stable `ThingId` and `BehaviourAttachmentId` do not change. `ExecutionRuntime` remains a serial scheduler; replacement is a scheduler-boundary operation between activations, not an engine callback or coroutine mutation.

The publication sequence is:

`acquire exact target IR → validate target IR/revision → rebind/revalidate target capabilities → migrate private state → map/cancel/reject every live pending work item → validate complete staged result → publish runtime binding/state/work together`

All fallible validation happens before the live program binding, private state, timer table, activation heap or pending service-request outbox is changed. A rejected replacement therefore leaves the previous implementation, private/public state, RNG stream and pending work live.

The runtime hot-swap operation does **not** silently write a new Behaviour revision back into the editable canonical project. Persisting an authored revision change is a separate canonical transaction. This keeps Play/runtime state separate from editable authored state as required by Architecture v1.

## Private-state migration

`PrivateStateMigration(mode="preserve")` is an explicit statement that the complete existing private mapping is compatible and must be carried unchanged.

Schema-changing `mode="migrate"` is declarative. It begins from the target IR defaults, maps named old fields to named target fields, applies explicit literals, and requires every old field to be consumed or explicitly listed in `drop_source_keys`. An omitted old field rejects the replacement rather than disappearing by accident. Missing source fields and invalid/transient authority-like values also reject before publication.

No user Behaviour callback executes as a migration function. This prevents arbitrary replacement-time host authority and keeps migration deterministic and inspectable.

## Pending work

Live timers and queued non-timer activations are semantic pending work. Every affected old handler must have an explicit `HandlerMigration` outcome:

- `map` identifies the exact target handler, including an explicit same-name map when preservation is intended;
- `cancel` deliberately discards that work under the compatibility contract;
- absence of an outcome rejects the replacement.

Mapped timers preserve timer identity, due logical tick, sequence and payload. Stale heap entries remain non-semantic and are never revived. A map to a handler missing from the target exact IR is rejected.

Pending host-service requests have a separate explicit `preserve | cancel | reject` policy. They contain request data and stable origin identity, not grants. Preserved requests still cross the SMX-027 trusted boundary later and receive its final-use authorization recheck. Already committed emitted-event outbox entries are not pending Behaviour execution and are not retroactively rewritten by replacement.

WorldSave encoding/restoration of pending work remains SMX-029 scope.

## Capability rebinding

The principal is recomputed from the stable semantic pair `ThingId + BehaviourAttachmentId`, exactly matching SMX-027 request attribution. Target `CapabilityRequirement` declarations are resolved against the current live `CapabilityBroker` before publication. Required denial, expiry or revocation rejects the swap atomically; optional denial returns only the explicit reduced-mode plan.

Grant IDs, tokens, broker objects and host handles are never serialized into migrated private state or returned as replacement state. The migrated private mapping is independently checked by the execution value guard, including the recursive transient/capability-field prohibition. Replacement therefore rebinds authority policy; it does not smuggle an old lease through state migration.

## Adversarial and boundary coverage

`tests/production/test_smx028.py` ports the material SMX-004, SMX-008 and SMX-015 hot-replacement cases and adds production-boundary attacks:

- stable Thing/attachment identity and same-schema state preservation;
- explicit schema migration and explicit destructive drop;
- missing/incorrect migration input rollback;
- exact source/target revision mismatch and invalid target IR;
- timer/continuation map, cancellation, missing declaration and missing target handler;
- pending service request preserve/cancel/reject;
- capability denial, expiry, revocation and explicit optional reduced mode;
- rejection of authority-like private state during replacement;
- preservation of attachment-local RNG state and committed event output.

The machine-readable expectations are in `spec/production/smx028-hotswap-fixtures.json`; `tools/validate_smx028.py` binds the implementation, tests, module manifest, authority text and fixture IDs into the dedicated CI gate.

## Protected source/audio/provenance boundary

SMX-028 does not alter assets, canonical serialization or protected-media records. The Architecture-v1 invariant remains unchanged: a stable `AssetId` denotes one indivisible immutable revision containing content digest, source identity, source metadata, audio/media semantics, provenance, licence/attribution and derivation lineage. Behaviour replacement cannot field-mix those fields, replace them with decoded/transcoded/cache state, or reinterpret them as authority. Any future Behaviour-driven asset replacement still has to pass SMX-024 canonical protected-revision validation as one complete revision.

## Deliberate limits

This issue proves transactional replacement inside the production Python semantic runtime. It does not claim package solver/update behavior (Phase 5), durable WorldSave pending-work encoding (SMX-029), Godot object binding replacement (Phase 6), or physical sandbox certification (Phase 7). Those layers may implement private mechanics differently but must preserve this compatibility/rollback/pending-work contract.
