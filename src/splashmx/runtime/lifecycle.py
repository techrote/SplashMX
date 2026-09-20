"""SMX-029 production lifecycle, WorldSave and fresh-runtime restore.

WorldSave is a persistent runtime-state plane, not the editable canonical project,
a publication artefact, capability authority, collaboration history, or a cache.
Snapshots contain only SplashMX semantic state and typed pending work.  Process,
engine, browser, network/session and capability handles are deliberately excluded.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
import heapq
import json
import math
from pathlib import Path
import random
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from splashmx.canonical.core import (
    BehaviourAttachmentId,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ReferenceState,
    SemanticId,
    ThingId,
)
from splashmx.execution.ir import (
    Activation,
    BudgetLimits,
    ExecutionRuntime,
    IRProgram,
    PendingTimer,
    RuntimeThingState,
    validate_program,
)
from splashmx.security.capabilities import (
    CapabilityBroker,
    CapabilityPlan,
    CapabilityRequirement,
    PrincipalId,
)

WORLD_SAVE_SCHEMA = "splashmx.world-save/1"
WORLD_STORE_SCHEMA = "splashmx.world-save-store/1"
WORLD_STORE_VERSION = 1
MAX_WORLD_SAVE_BYTES = 32 * 1024 * 1024
WORLD_COMMIT_STAGES = (
    "prepared",
    "revision_recorded",
    "candidate_verified",
    "head_advanced",
    "committed",
)

FaultHook = Callable[[str], None]

_FORBIDDEN_PERSISTED_FIELDS = {
    "nodepath",
    "rid",
    "resourceuid",
    "resourcepath",
    "domnodeidentity",
    "databaserowid",
    "cachekey",
    "transportpeerid",
    "connectionhandle",
    "socketid",
    "sessionid",
    "processhandle",
    "capabilitytoken",
    "capabilitygrant",
    "capabilitylease",
    "filehandle",
    "browserobject",
    "nativepointer",
}


def _normalise_field_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


class LifecycleError(ValueError):
    """Stable typed lifecycle/WorldSave failure."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _fail(code: str, message: str) -> None:
    raise LifecycleError(code, message)


class WorldSaveId(SemanticId):
    role = "WorldSaveId"


class WorldRevisionId(SemanticId):
    role = "WorldRevisionId"


class LifecyclePhase(str, Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    KNOWN_UNLOADED = "known-unloaded"
    TOMBSTONED = "tombstoned"


def _validate_plain(
    value: Any,
    *,
    where: str = "value",
    depth: int = 0,
    counter: list[int] | None = None,
) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > 100_000:
        _fail("worldsave.resource_limit", f"{where} exceeds value-node limit")
    if depth > 64:
        _fail("worldsave.resource_limit", f"{where} exceeds structural depth limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("worldsave.invalid_value", f"{where} contains NaN or infinity")
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > 8 * 1024 * 1024:
            _fail("worldsave.resource_limit", f"{where} string exceeds byte limit")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_plain(child, where=f"{where}[{index}]", depth=depth + 1, counter=counter)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("worldsave.invalid_value", f"{where} map keys must be strings")
            if _normalise_field_name(key) in _FORBIDDEN_PERSISTED_FIELDS:
                _fail(
                    "worldsave.forbidden_transient_state",
                    f"{where} contains forbidden transient/authority field {key!r}",
                )
            _validate_plain(child, where=f"{where}.{key}", depth=depth + 1, counter=counter)
        return
    _fail("worldsave.invalid_value", f"{where} contains unsupported type {type(value).__name__}")


def _listify(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_listify(child) for child in value]
    if isinstance(value, list):
        return [_listify(child) for child in value]
    return value


def _tupleify(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tupleify(child) for child in value)
    return value


@dataclass(frozen=True)
class AttachmentSnapshot:
    attachment_id: BehaviourAttachmentId
    behaviour_revision: str
    private_state: Mapping[str, Any]
    rng_state: Any


@dataclass(frozen=True)
class TimerSnapshot:
    timer_id: str
    due_tick: int
    attachment_id: BehaviourAttachmentId
    handler_id: str
    payload: Any
    sequence: int


@dataclass(frozen=True)
class QueuedWorkSnapshot:
    due_tick: int
    sequence: int
    attachment_id: BehaviourAttachmentId
    handler_id: str
    payload: Any
    timer_id: str | None = None


@dataclass(frozen=True)
class ExternalWaitSnapshot:
    thing_id: ThingId
    request_id: str
    attachment_id: BehaviourAttachmentId
    service: str
    payload: Any
    source_activation_sequence: int
    restore_policy: str = "reauthorize"


@dataclass(frozen=True)
class ThingRuntimeSnapshot:
    thing_id: ThingId
    phase: LifecyclePhase
    public_state: Mapping[str, Any] = field(default_factory=dict)
    attachment_order: tuple[BehaviourAttachmentId, ...] = ()
    attachments: tuple[AttachmentSnapshot, ...] = ()
    timers: tuple[TimerSnapshot, ...] = ()
    queued_work: tuple[QueuedWorkSnapshot, ...] = ()
    external_waits: tuple[ExternalWaitSnapshot, ...] = ()
    tombstone_tick: int | None = None
    tombstone_reason: str | None = None


@dataclass(frozen=True)
class WorldSaveSnapshot:
    world_save_id: WorldSaveId
    world_revision_id: WorldRevisionId
    project_id: ProjectId
    project_revision_id: ProjectRevisionId
    logical_tick: int
    next_sequence: int
    runtime_seed: int
    things: tuple[ThingRuntimeSnapshot, ...]
    schema: str = WORLD_SAVE_SCHEMA


@dataclass(frozen=True)
class RestoreResult:
    world: "WorldRuntime"
    capability_plans: Mapping[tuple[ThingId, BehaviourAttachmentId], CapabilityPlan]
    deferred_external_waits: tuple[ExternalWaitSnapshot, ...]


def _thing_to_data(row: ThingRuntimeSnapshot) -> dict[str, Any]:
    return {
        "thing_id": str(row.thing_id),
        "phase": row.phase.value,
        "public_state": deepcopy(dict(row.public_state)),
        "attachment_order": [str(value) for value in row.attachment_order],
        "attachments": [
            {
                "attachment_id": str(item.attachment_id),
                "behaviour_revision": item.behaviour_revision,
                "private_state": deepcopy(dict(item.private_state)),
                "rng_state": _listify(item.rng_state),
            }
            for item in row.attachments
        ],
        "timers": [
            {
                "timer_id": item.timer_id,
                "due_tick": item.due_tick,
                "attachment_id": str(item.attachment_id),
                "handler_id": item.handler_id,
                "payload": deepcopy(item.payload),
                "sequence": item.sequence,
            }
            for item in row.timers
        ],
        "queued_work": [
            {
                "due_tick": item.due_tick,
                "sequence": item.sequence,
                "attachment_id": str(item.attachment_id),
                "handler_id": item.handler_id,
                "payload": deepcopy(item.payload),
                "timer_id": item.timer_id,
            }
            for item in row.queued_work
        ],
        "external_waits": [
            {
                "thing_id": str(item.thing_id),
                "request_id": item.request_id,
                "attachment_id": str(item.attachment_id),
                "service": item.service,
                "payload": deepcopy(item.payload),
                "source_activation_sequence": item.source_activation_sequence,
                "restore_policy": item.restore_policy,
            }
            for item in row.external_waits
        ],
        "tombstone_tick": row.tombstone_tick,
        "tombstone_reason": row.tombstone_reason,
    }


def _semantic_data(snapshot: WorldSaveSnapshot, *, include_revision: bool) -> dict[str, Any]:
    data = {
        "schema": snapshot.schema,
        "world_save_id": str(snapshot.world_save_id),
        "project_id": str(snapshot.project_id),
        "project_revision_id": str(snapshot.project_revision_id),
        "logical_tick": snapshot.logical_tick,
        "next_sequence": snapshot.next_sequence,
        "runtime_seed": snapshot.runtime_seed,
        "things": [_thing_to_data(item) for item in snapshot.things],
    }
    if include_revision:
        data["world_revision_id"] = str(snapshot.world_revision_id)
    return data


def _canonical_json(data: Any) -> bytes:
    try:
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise LifecycleError("worldsave.invalid_value", "WorldSave cannot be encoded", cause=exc) from exc
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_WORLD_SAVE_BYTES:
        _fail("worldsave.resource_limit", "WorldSave exceeds byte limit")
    return encoded


def _revision_for_data(data: Mapping[str, Any]) -> WorldRevisionId:
    return WorldRevisionId("sha256:" + sha256(_canonical_json(data)).hexdigest())


def _with_computed_revision(
    world_save_id: WorldSaveId,
    project_id: ProjectId,
    project_revision_id: ProjectRevisionId,
    logical_tick: int,
    next_sequence: int,
    runtime_seed: int,
    things: Sequence[ThingRuntimeSnapshot],
) -> WorldSaveSnapshot:
    placeholder = WorldSaveSnapshot(
        world_save_id,
        WorldRevisionId("pending"),
        project_id,
        project_revision_id,
        logical_tick,
        next_sequence,
        runtime_seed,
        tuple(things),
    )
    revision = _revision_for_data(_semantic_data(placeholder, include_revision=False))
    return replace(placeholder, world_revision_id=revision)


def serialize_world_save(snapshot: WorldSaveSnapshot) -> bytes:
    _validate_snapshot(snapshot)
    expected = _revision_for_data(_semantic_data(snapshot, include_revision=False))
    if snapshot.world_revision_id != expected:
        _fail("worldsave.revision_mismatch", "WorldRevisionId does not match WorldSave semantic bytes")
    return _canonical_json(_semantic_data(snapshot, include_revision=True))


def _expect_fields(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    if not isinstance(value, Mapping):
        _fail("worldsave.invalid_format", f"{where} must be an object")
    if set(value) != expected:
        _fail("worldsave.invalid_format", f"{where} has unexpected or missing fields")


def deserialize_world_save(raw: bytes) -> WorldSaveSnapshot:
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_WORLD_SAVE_BYTES:
        _fail("worldsave.resource_limit", "WorldSave bytes are invalid or exceed byte limit")
    try:
        data = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise LifecycleError("worldsave.invalid_format", "WorldSave JSON is malformed", cause=exc) from exc
    if not isinstance(data, dict):
        _fail("worldsave.invalid_format", "WorldSave root must be an object")
    _expect_fields(
        data,
        {
            "schema", "world_save_id", "world_revision_id", "project_id",
            "project_revision_id", "logical_tick", "next_sequence", "runtime_seed", "things",
        },
        "WorldSave root",
    )
    if data["schema"] != WORLD_SAVE_SCHEMA:
        _fail("worldsave.unsupported_schema", f"unsupported WorldSave schema {data['schema']!r}")
    if not isinstance(data["things"], list):
        _fail("worldsave.invalid_format", "WorldSave things must be a list")

    things: list[ThingRuntimeSnapshot] = []
    for index, row in enumerate(data["things"]):
        if not isinstance(row, dict):
            _fail("worldsave.invalid_format", f"thing[{index}] must be an object")
        _expect_fields(
            row,
            {
                "thing_id", "phase", "public_state", "attachment_order", "attachments",
                "timers", "queued_work", "external_waits", "tombstone_tick", "tombstone_reason",
            },
            f"thing[{index}]",
        )
        try:
            phase = LifecyclePhase(row["phase"])
        except (TypeError, ValueError) as exc:
            raise LifecycleError("worldsave.invalid_lifecycle", "unknown lifecycle phase", cause=exc) from exc

        attachments: list[AttachmentSnapshot] = []
        if not isinstance(row["attachments"], list):
            _fail("worldsave.invalid_format", "attachments must be a list")
        for item in row["attachments"]:
            _expect_fields(item, {"attachment_id", "behaviour_revision", "private_state", "rng_state"}, "attachment")
            attachments.append(
                AttachmentSnapshot(
                    BehaviourAttachmentId(item["attachment_id"]),
                    item["behaviour_revision"],
                    item["private_state"],
                    _tupleify(item["rng_state"]),
                )
            )

        if not isinstance(row["timers"], list):
            _fail("worldsave.invalid_format", "timers must be a list")
        timers: list[TimerSnapshot] = []
        for item in row["timers"]:
            _expect_fields(
                item,
                {"timer_id", "due_tick", "attachment_id", "handler_id", "payload", "sequence"},
                "timer",
            )
            timers.append(
                TimerSnapshot(
                    item["timer_id"], item["due_tick"], BehaviourAttachmentId(item["attachment_id"]),
                    item["handler_id"], item["payload"], item["sequence"],
                )
            )

        if not isinstance(row["queued_work"], list):
            _fail("worldsave.invalid_format", "queued_work must be a list")
        queued: list[QueuedWorkSnapshot] = []
        for item in row["queued_work"]:
            _expect_fields(
                item,
                {"due_tick", "sequence", "attachment_id", "handler_id", "payload", "timer_id"},
                "queued work",
            )
            queued.append(
                QueuedWorkSnapshot(
                    item["due_tick"], item["sequence"], BehaviourAttachmentId(item["attachment_id"]),
                    item["handler_id"], item["payload"], item["timer_id"],
                )
            )

        if not isinstance(row["external_waits"], list):
            _fail("worldsave.invalid_format", "external_waits must be a list")
        waits: list[ExternalWaitSnapshot] = []
        for item in row["external_waits"]:
            _expect_fields(
                item,
                {
                    "thing_id", "request_id", "attachment_id", "service", "payload",
                    "source_activation_sequence", "restore_policy",
                },
                "external wait",
            )
            waits.append(
                ExternalWaitSnapshot(
                    ThingId(item["thing_id"]), item["request_id"], BehaviourAttachmentId(item["attachment_id"]),
                    item["service"], item["payload"], item["source_activation_sequence"],
                    item["restore_policy"],
                )
            )

        if not isinstance(row["attachment_order"], list):
            _fail("worldsave.invalid_format", "attachment_order must be a list")
        things.append(
            ThingRuntimeSnapshot(
                ThingId(row["thing_id"]),
                phase,
                row["public_state"],
                tuple(BehaviourAttachmentId(value) for value in row["attachment_order"]),
                tuple(attachments),
                tuple(timers),
                tuple(queued),
                tuple(waits),
                row["tombstone_tick"],
                row["tombstone_reason"],
            )
        )

    snapshot = WorldSaveSnapshot(
        WorldSaveId(data["world_save_id"]),
        WorldRevisionId(data["world_revision_id"]),
        ProjectId(data["project_id"]),
        ProjectRevisionId(data["project_revision_id"]),
        data["logical_tick"],
        data["next_sequence"],
        data["runtime_seed"],
        tuple(things),
        data["schema"],
    )
    _validate_snapshot(snapshot)
    expected = serialize_world_save(snapshot)
    if expected != bytes(raw):
        _fail("worldsave.noncanonical_encoding", "WorldSave bytes are not the canonical JSON encoding")
    return snapshot


def _handler_ids(program: IRProgram) -> set[str]:
    return {handler.handler_id for handler in program.handlers}


def _validate_snapshot(snapshot: WorldSaveSnapshot) -> None:
    if snapshot.schema != WORLD_SAVE_SCHEMA:
        _fail("worldsave.unsupported_schema", f"unsupported WorldSave schema {snapshot.schema!r}")
    if not isinstance(snapshot.logical_tick, int) or isinstance(snapshot.logical_tick, bool) or snapshot.logical_tick < 0:
        _fail("worldsave.invalid_clock", "logical_tick must be a non-negative integer")
    if not isinstance(snapshot.next_sequence, int) or isinstance(snapshot.next_sequence, bool) or snapshot.next_sequence < 0:
        _fail("worldsave.invalid_sequence", "next_sequence must be a non-negative integer")
    if not isinstance(snapshot.runtime_seed, int) or isinstance(snapshot.runtime_seed, bool):
        _fail("worldsave.invalid_seed", "runtime_seed must be an integer")

    thing_ids: set[ThingId] = set()
    queue_sequences: set[int] = set()
    timer_ids: set[str] = set()
    max_sequence = -1
    for thing in snapshot.things:
        if thing.thing_id in thing_ids:
            _fail("worldsave.duplicate_identity", f"duplicate ThingId {thing.thing_id}")
        thing_ids.add(thing.thing_id)
        if not isinstance(thing.public_state, Mapping):
            _fail("worldsave.invalid_value", f"{thing.thing_id}.public_state must be a mapping")
        _validate_plain(thing.public_state, where=f"{thing.thing_id}.public_state")

        if thing.phase is LifecyclePhase.TOMBSTONED:
            if (
                thing.public_state or thing.attachments or thing.attachment_order
                or thing.timers or thing.queued_work or thing.external_waits
            ):
                _fail("worldsave.invalid_tombstone", "tombstones may not retain live runtime state or work")
            if (
                not isinstance(thing.tombstone_tick, int)
                or isinstance(thing.tombstone_tick, bool)
                or thing.tombstone_tick < 0
            ):
                _fail("worldsave.invalid_tombstone", "tombstones require a non-negative destruction tick")
            if thing.tombstone_reason is not None and (
                not isinstance(thing.tombstone_reason, str)
                or len(thing.tombstone_reason.encode("utf-8")) > 4096
            ):
                _fail("worldsave.invalid_tombstone", "tombstone reason must be a bounded string")
            continue
        if thing.tombstone_tick is not None or thing.tombstone_reason is not None:
            _fail("worldsave.invalid_tombstone", "non-tombstoned Thing contains tombstone metadata")

        attachment_ids = [item.attachment_id for item in thing.attachments]
        if len(attachment_ids) != len(set(attachment_ids)):
            _fail("worldsave.duplicate_identity", f"duplicate attachment on {thing.thing_id}")
        if tuple(attachment_ids) != tuple(thing.attachment_order):
            _fail("worldsave.invalid_attachment_order", "attachment snapshots must match semantic attachment order")
        for attachment in thing.attachments:
            if not isinstance(attachment.behaviour_revision, str) or not attachment.behaviour_revision:
                _fail("worldsave.invalid_behaviour_revision", "behaviour revision must be non-empty")
            if not isinstance(attachment.private_state, Mapping):
                _fail("worldsave.invalid_value", "attachment private_state must be a mapping")
            _validate_plain(
                attachment.private_state,
                where=f"{thing.thing_id}/{attachment.attachment_id}.private_state",
            )
            try:
                probe = random.Random()
                probe.setstate(attachment.rng_state)
            except (TypeError, ValueError) as exc:
                raise LifecycleError("worldsave.invalid_rng_state", "invalid deterministic PRNG state", cause=exc) from exc

        attachment_set = set(attachment_ids)
        local_timer_ids: set[str] = set()
        for timer in thing.timers:
            if timer.attachment_id not in attachment_set:
                _fail("worldsave.invalid_pending_work", "timer targets unknown attachment")
            if not isinstance(timer.timer_id, str) or not timer.timer_id:
                _fail("worldsave.invalid_pending_work", "timer ID must be non-empty")
            if timer.timer_id in timer_ids:
                _fail("worldsave.duplicate_identity", f"duplicate timer ID {timer.timer_id}")
            timer_ids.add(timer.timer_id)
            local_timer_ids.add(timer.timer_id)
            if not isinstance(timer.due_tick, int) or isinstance(timer.due_tick, bool) or timer.due_tick < 0:
                _fail("worldsave.invalid_pending_work", "timer due_tick must be non-negative integer")
            if not isinstance(timer.sequence, int) or isinstance(timer.sequence, bool) or timer.sequence < 0:
                _fail("worldsave.invalid_pending_work", "timer sequence must be non-negative integer")
            _validate_plain(timer.payload, where=f"timer {timer.timer_id} payload")
            max_sequence = max(max_sequence, timer.sequence)

        queued_timer_ids: set[str] = set()
        for work in thing.queued_work:
            if work.attachment_id not in attachment_set:
                _fail("worldsave.invalid_pending_work", "queued work targets unknown attachment")
            if not isinstance(work.due_tick, int) or isinstance(work.due_tick, bool) or work.due_tick < 0:
                _fail("worldsave.invalid_pending_work", "queued due_tick must be non-negative integer")
            if not isinstance(work.sequence, int) or isinstance(work.sequence, bool) or work.sequence < 0:
                _fail("worldsave.invalid_pending_work", "queued sequence must be non-negative integer")
            if work.sequence in queue_sequences:
                _fail("worldsave.invalid_pending_work", "queue ordering sequence must be globally unique")
            queue_sequences.add(work.sequence)
            max_sequence = max(max_sequence, work.sequence)
            _validate_plain(work.payload, where="queued work payload")
            if work.timer_id is not None:
                if work.timer_id not in local_timer_ids:
                    _fail("worldsave.invalid_pending_work", "timer activation has no matching pending timer")
                timer = next(item for item in thing.timers if item.timer_id == work.timer_id)
                if (
                    timer.sequence != work.sequence
                    or timer.due_tick != work.due_tick
                    or timer.attachment_id != work.attachment_id
                    or timer.handler_id != work.handler_id
                    or timer.payload != work.payload
                ):
                    _fail("worldsave.invalid_pending_work", "timer activation and pending timer disagree")
                if work.timer_id in queued_timer_ids:
                    _fail("worldsave.invalid_pending_work", "timer has more than one queued activation")
                queued_timer_ids.add(work.timer_id)
        if queued_timer_ids != local_timer_ids:
            _fail("worldsave.invalid_pending_work", "every pending timer requires exactly one queued activation")

        wait_ids: set[str] = set()
        for wait in thing.external_waits:
            if wait.thing_id != thing.thing_id:
                _fail("worldsave.invalid_pending_work", "external wait ThingId does not match owning record")
            if wait.request_id in wait_ids:
                _fail("worldsave.duplicate_identity", f"duplicate external wait {wait.request_id}")
            wait_ids.add(wait.request_id)
            if wait.attachment_id not in attachment_set:
                _fail("worldsave.invalid_pending_work", "external wait targets unknown attachment")
            if wait.restore_policy != "reauthorize":
                _fail("worldsave.invalid_pending_work", "external waits must restore through explicit reauthorization")
            if not isinstance(wait.request_id, str) or not wait.request_id:
                _fail("worldsave.invalid_pending_work", "external wait request ID must be non-empty")
            _validate_plain(wait.payload, where=f"external wait {wait.request_id} payload")

    if snapshot.next_sequence <= max_sequence:
        _fail("worldsave.invalid_sequence", "next_sequence must be greater than every durable scheduler sequence")


def _capture_thing(runtime: ExecutionRuntime, thing_id: ThingId, phase: LifecyclePhase) -> ThingRuntimeSnapshot:
    state = runtime.states.get(thing_id)
    if state is None:
        _fail("lifecycle.not_resident", f"Thing {thing_id} has no resident runtime state")
    order = runtime.attachment_order.get(thing_id, ())
    attachments: list[AttachmentSnapshot] = []
    for attachment_id in order:
        program = runtime.programs.get((thing_id, attachment_id))
        rng = runtime._rng.get((thing_id, attachment_id))
        if program is None or rng is None or attachment_id not in state.private_by_attachment:
            _fail("lifecycle.incoherent_runtime", f"Thing {thing_id} attachment state is incomplete")
        attachments.append(
            AttachmentSnapshot(
                attachment_id,
                program.behaviour_revision,
                deepcopy(state.private_by_attachment[attachment_id]),
                deepcopy(rng.getstate()),
            )
        )

    timers = tuple(
        TimerSnapshot(
            timer.timer_id,
            timer.due_tick,
            timer.attachment_id,
            timer.handler_id,
            deepcopy(timer.payload),
            timer.sequence,
        )
        for timer in sorted(runtime.pending_timers.values(), key=lambda value: (value.due_tick, value.sequence))
        if timer.thing_id == thing_id
    )
    queued = tuple(
        QueuedWorkSnapshot(
            activation.due_tick,
            activation.sequence,
            activation.attachment_id,
            activation.handler_id,
            deepcopy(activation.payload),
            activation.timer_id,
        )
        for _, _, activation in sorted(runtime._queue)
        if activation.thing_id == thing_id
        and (
            activation.timer_id is None
            or (
                activation.timer_id in runtime.pending_timers
                and runtime.pending_timers[activation.timer_id].sequence == activation.sequence
            )
        )
    )
    waits = tuple(
        ExternalWaitSnapshot(
            request.thing_id,
            request.request_id,
            request.attachment_id,
            request.service,
            deepcopy(request.payload),
            request.source_activation_sequence,
        )
        for request in runtime.service_requests
        if request.thing_id == thing_id
    )
    return ThingRuntimeSnapshot(
        thing_id,
        phase,
        deepcopy(state.public_state),
        tuple(order),
        tuple(attachments),
        timers,
        queued,
        waits,
    )


def _drop_resident(runtime: ExecutionRuntime, thing_id: ThingId) -> None:
    order = runtime.attachment_order.pop(thing_id, ())
    runtime.states.pop(thing_id, None)
    for attachment_id in order:
        runtime.programs.pop((thing_id, attachment_id), None)
        runtime._rng.pop((thing_id, attachment_id), None)
    owned_timers = {
        timer_id for timer_id, timer in runtime.pending_timers.items()
        if timer.thing_id == thing_id
    }
    for timer_id in owned_timers:
        runtime.pending_timers.pop(timer_id, None)
    runtime._queue = [
        row for row in runtime._queue
        if row[2].thing_id != thing_id
    ]
    heapq.heapify(runtime._queue)
    runtime.service_requests = [
        request for request in runtime.service_requests
        if request.thing_id != thing_id
    ]


def _merge_external_waits(
    row: ThingRuntimeSnapshot,
    additional: Sequence[ExternalWaitSnapshot],
) -> ThingRuntimeSnapshot:
    by_id = {item.request_id: item for item in row.external_waits}
    for item in additional:
        if item.thing_id != row.thing_id:
            continue
        prior = by_id.get(item.request_id)
        if prior is not None and prior != item:
            _fail("worldsave.external_wait_conflict", f"conflicting external wait {item.request_id!r}")
        by_id[item.request_id] = deepcopy(item)
    return replace(
        row,
        external_waits=tuple(sorted(by_id.values(), key=lambda value: value.request_id)),
    )


class WorldRuntime:
    """Runtime plus explicit lifecycle/catalog state.

    The canonical document remains authored project data.  This object owns only live
    simulation state and the selected persistent-world projection.
    """

    def __init__(
        self,
        document: CanonicalDocument,
        runtime: ExecutionRuntime,
        program_registry: Mapping[str, IRProgram],
        lifecycle: Mapping[ThingId, LifecyclePhase],
        *,
        retained: Mapping[ThingId, ThingRuntimeSnapshot] | None = None,
        deferred_external_waits: Sequence[ExternalWaitSnapshot] = (),
    ):
        self.document = document
        self.runtime = runtime
        self.program_registry = dict(program_registry)
        self.lifecycle = dict(lifecycle)
        self._retained = dict(retained or {})
        self.deferred_external_waits = tuple(deferred_external_waits)

    @classmethod
    def create(
        cls,
        document: CanonicalDocument,
        program_registry: Mapping[str, IRProgram],
        *,
        attachment_order: Mapping[ThingId, Sequence[BehaviourAttachmentId]] | None = None,
        budgets: BudgetLimits | None = None,
        seed: int = 0,
    ) -> "WorldRuntime":
        runtime = ExecutionRuntime.from_document(
            document,
            program_registry,
            attachment_order=attachment_order,
            budgets=budgets,
            seed=seed,
        )
        lifecycle: dict[ThingId, LifecyclePhase] = {}
        retained: dict[ThingId, ThingRuntimeSnapshot] = {}
        for thing_id, thing in document.things.items():
            if thing.tombstoned:
                lifecycle[thing_id] = LifecyclePhase.TOMBSTONED
                retained[thing_id] = ThingRuntimeSnapshot(
                    thing_id,
                    LifecyclePhase.TOMBSTONED,
                    tombstone_tick=runtime.logical_tick,
                    tombstone_reason="authored-tombstone",
                )
            else:
                lifecycle[thing_id] = LifecyclePhase.ACTIVE
        for thing_id in document.known_unloaded_things:
            lifecycle.setdefault(thing_id, LifecyclePhase.KNOWN_UNLOADED)
            retained.setdefault(
                thing_id,
                ThingRuntimeSnapshot(thing_id, LifecyclePhase.KNOWN_UNLOADED),
            )
        return cls(document, runtime, program_registry, lifecycle, retained=retained)

    def reference_state(self, thing_id: ThingId) -> ReferenceState:
        phase = self.lifecycle.get(thing_id)
        if phase in {LifecyclePhase.ACTIVE, LifecyclePhase.DORMANT}:
            return ReferenceState.LOADED
        if phase is LifecyclePhase.KNOWN_UNLOADED:
            return ReferenceState.KNOWN_UNLOADED
        if phase is LifecyclePhase.TOMBSTONED:
            return ReferenceState.TOMBSTONED
        return ReferenceState.UNKNOWN

    def activate(self, thing_id: ThingId) -> None:
        phase = self.lifecycle.get(thing_id)
        if phase is LifecyclePhase.ACTIVE:
            return
        if phase is not LifecyclePhase.DORMANT:
            _fail("lifecycle.invalid_transition", f"cannot activate {phase or 'unknown'} Thing {thing_id}")
        self.lifecycle[thing_id] = LifecyclePhase.ACTIVE

    def set_dormant(self, thing_id: ThingId) -> None:
        phase = self.lifecycle.get(thing_id)
        if phase is LifecyclePhase.DORMANT:
            return
        if phase is not LifecyclePhase.ACTIVE:
            _fail("lifecycle.invalid_transition", f"cannot make {phase or 'unknown'} Thing dormant")
        self.lifecycle[thing_id] = LifecyclePhase.DORMANT

    def dispatch(
        self,
        thing_id: ThingId,
        trigger: str,
        payload: Any = None,
        *,
        due_tick: int | None = None,
    ) -> int:
        if self.lifecycle.get(thing_id) is not LifecyclePhase.ACTIVE:
            _fail("lifecycle.not_active", f"Thing {thing_id} is not active")
        return self.runtime.dispatch(thing_id, trigger, payload, due_tick=due_tick)

    def unload(self, thing_id: ThingId) -> None:
        phase = self.lifecycle.get(thing_id)
        if phase not in {LifecyclePhase.ACTIVE, LifecyclePhase.DORMANT}:
            _fail("lifecycle.invalid_transition", f"cannot unload {phase or 'unknown'} Thing {thing_id}")
        staged = _capture_thing(self.runtime, thing_id, phase)
        staged = _merge_external_waits(staged, self.deferred_external_waits)
        staged = replace(staged, phase=LifecyclePhase.KNOWN_UNLOADED)
        _validate_plain(_thing_to_data(staged), where=f"unload {thing_id}")
        _drop_resident(self.runtime, thing_id)
        self._retained[thing_id] = staged
        self.lifecycle[thing_id] = LifecyclePhase.KNOWN_UNLOADED

    def tombstone(self, thing_id: ThingId, *, reason: str | None = None) -> None:
        phase = self.lifecycle.get(thing_id)
        if phase is None:
            _fail("lifecycle.unknown_thing", f"cannot tombstone unknown Thing {thing_id}")
        if phase is LifecyclePhase.TOMBSTONED:
            return
        if phase in {LifecyclePhase.ACTIVE, LifecyclePhase.DORMANT}:
            _drop_resident(self.runtime, thing_id)
        self._retained[thing_id] = ThingRuntimeSnapshot(
            thing_id,
            LifecyclePhase.TOMBSTONED,
            tombstone_tick=self.runtime.logical_tick,
            tombstone_reason=reason,
        )
        self.lifecycle[thing_id] = LifecyclePhase.TOMBSTONED

    def snapshot(self, world_save_id: WorldSaveId | str) -> WorldSaveSnapshot:
        save_id = world_save_id if isinstance(world_save_id, WorldSaveId) else WorldSaveId(world_save_id)
        rows: list[ThingRuntimeSnapshot] = []
        for thing_id in sorted(self.lifecycle, key=str):
            phase = self.lifecycle[thing_id]
            if phase in {LifecyclePhase.ACTIVE, LifecyclePhase.DORMANT}:
                row = _capture_thing(self.runtime, thing_id, phase)
                row = _merge_external_waits(row, self.deferred_external_waits)
            else:
                row = self._retained.get(thing_id)
                if row is None:
                    _fail("lifecycle.incoherent_runtime", f"missing retained state for {thing_id}")
            rows.append(deepcopy(row))
        snapshot = _with_computed_revision(
            save_id,
            self.document.project_id,
            self.document.project_revision_id,
            self.runtime.logical_tick,
            self.runtime._sequence,
            self.runtime.seed,
            rows,
        )
        _validate_snapshot(snapshot)
        return snapshot

    def rehydrate(
        self,
        thing_id: ThingId,
        *,
        capability_broker: CapabilityBroker | None = None,
        capability_requirements: Mapping[
            tuple[ThingId, BehaviourAttachmentId], Sequence[CapabilityRequirement]
        ] | None = None,
        policy_time: int = 0,
    ) -> None:
        if self.lifecycle.get(thing_id) is not LifecyclePhase.KNOWN_UNLOADED:
            _fail("lifecycle.invalid_transition", f"Thing {thing_id} is not known-unloaded")
        retained = self._retained.get(thing_id)
        if retained is None or thing_id not in self.document.things:
            _fail("lifecycle.dependency_unavailable", f"no authored/runtime basis is available for {thing_id}")
        current = self.snapshot(WorldSaveId("rehydrate-staging"))
        rows = tuple(
            replace(row, phase=LifecyclePhase.ACTIVE) if row.thing_id == thing_id else row
            for row in current.things
        )
        candidate = _with_computed_revision(
            current.world_save_id,
            current.project_id,
            current.project_revision_id,
            current.logical_tick,
            current.next_sequence,
            current.runtime_seed,
            rows,
        )
        restored = restore_world_save(
            candidate,
            self.document,
            self.program_registry,
            capability_broker=capability_broker,
            capability_requirements=capability_requirements,
            policy_time=policy_time,
            budgets=self.runtime.budgets,
        )
        staged = restored.world
        self.runtime = staged.runtime
        self.lifecycle = staged.lifecycle
        self._retained = staged._retained
        self.deferred_external_waits = staged.deferred_external_waits


def _principal_for_attachment(thing_id: ThingId, attachment_id: BehaviourAttachmentId) -> PrincipalId:
    return PrincipalId(f"behaviour:{thing_id}:{attachment_id}")


def restore_world_save(
    snapshot: WorldSaveSnapshot,
    document: CanonicalDocument,
    program_registry: Mapping[str, IRProgram],
    *,
    capability_broker: CapabilityBroker | None = None,
    capability_requirements: Mapping[
        tuple[ThingId, BehaviourAttachmentId], Sequence[CapabilityRequirement]
    ] | None = None,
    policy_time: int = 0,
    budgets: BudgetLimits | None = None,
) -> RestoreResult:
    """Stage and return a fresh runtime without mutating the source world/save.

    No service request is automatically placed back in the executable outbox.  Saved
    external waits remain deferred descriptors.  Current capability policy is
    resolved afresh for declared attachment requirements before the result is
    published to the caller.
    """
    _validate_snapshot(snapshot)
    expected_revision = _revision_for_data(_semantic_data(snapshot, include_revision=False))
    if snapshot.world_revision_id != expected_revision:
        _fail("worldsave.revision_mismatch", "WorldSave revision digest is invalid")
    if snapshot.project_id != document.project_id:
        _fail("worldsave.project_mismatch", "WorldSave belongs to a different ProjectId")
    if snapshot.project_revision_id != document.project_revision_id:
        _fail("worldsave.authored_revision_mismatch", "WorldSave requires a different exact authored revision")

    runtime = ExecutionRuntime(budgets=budgets, seed=snapshot.runtime_seed)
    runtime.logical_tick = snapshot.logical_tick
    runtime._sequence = snapshot.next_sequence

    lifecycle: dict[ThingId, LifecyclePhase] = {}
    retained: dict[ThingId, ThingRuntimeSnapshot] = {}
    deferred: list[ExternalWaitSnapshot] = []
    used_sequences: set[int] = set()

    for row in snapshot.things:
        lifecycle[row.thing_id] = row.phase
        if row.phase in {LifecyclePhase.KNOWN_UNLOADED, LifecyclePhase.TOMBSTONED}:
            if row.phase is LifecyclePhase.KNOWN_UNLOADED:
                authored = document.things.get(row.thing_id)
                if authored is not None and not authored.tombstoned:
                    _validate_against_authored(row, document, program_registry)
            retained[row.thing_id] = deepcopy(row)
            deferred.extend(deepcopy(row.external_waits))
            continue

        _validate_against_authored(row, document, program_registry)
        authored = document.things.get(row.thing_id)
        if authored is None or authored.tombstoned:
            _fail("worldsave.authored_basis_missing", f"no live authored basis for {row.thing_id}")

        runtime.attachment_order[row.thing_id] = tuple(row.attachment_order)
        private: dict[BehaviourAttachmentId, dict[str, Any]] = {}
        for item in row.attachments:
            program = program_registry[item.behaviour_revision]
            runtime.programs[(row.thing_id, item.attachment_id)] = program
            private[item.attachment_id] = deepcopy(dict(item.private_state))
            rng = random.Random()
            try:
                rng.setstate(item.rng_state)
            except (TypeError, ValueError) as exc:
                raise LifecycleError("worldsave.invalid_rng_state", "invalid PRNG state", cause=exc) from exc
            runtime._rng[(row.thing_id, item.attachment_id)] = rng
        runtime.states[row.thing_id] = RuntimeThingState(
            deepcopy(dict(row.public_state)),
            private,
        )

        timers_by_id: dict[str, PendingTimer] = {}
        for timer in row.timers:
            program = runtime.programs[(row.thing_id, timer.attachment_id)]
            if timer.handler_id not in _handler_ids(program):
                _fail(
                    "worldsave.pending_handler_missing",
                    f"timer handler {timer.handler_id!r} is absent from exact Behaviour revision",
                )
            pending = PendingTimer(
                timer.timer_id,
                timer.due_tick,
                row.thing_id,
                timer.attachment_id,
                timer.handler_id,
                deepcopy(timer.payload),
                timer.sequence,
            )
            if timer.timer_id in runtime.pending_timers:
                _fail("worldsave.duplicate_identity", f"duplicate timer {timer.timer_id}")
            runtime.pending_timers[timer.timer_id] = pending
            timers_by_id[timer.timer_id] = pending

        for work in row.queued_work:
            if work.sequence in used_sequences:
                _fail("worldsave.invalid_pending_work", "queue sequence collision")
            used_sequences.add(work.sequence)
            program = runtime.programs[(row.thing_id, work.attachment_id)]
            if work.handler_id not in _handler_ids(program):
                _fail(
                    "worldsave.pending_handler_missing",
                    f"queued handler {work.handler_id!r} is absent from exact Behaviour revision",
                )
            if work.timer_id is not None:
                timer = timers_by_id.get(work.timer_id)
                if timer is None or timer.sequence != work.sequence:
                    _fail("worldsave.invalid_pending_work", "timer activation is not backed by pending timer")
            activation = Activation(
                work.due_tick,
                work.sequence,
                row.thing_id,
                work.attachment_id,
                work.handler_id,
                deepcopy(work.payload),
                work.timer_id,
            )
            heapq.heappush(runtime._queue, (work.due_tick, work.sequence, activation))
        deferred.extend(deepcopy(row.external_waits))

    requirements = capability_requirements or {}
    plans: dict[tuple[ThingId, BehaviourAttachmentId], CapabilityPlan] = {}
    for key, rows in requirements.items():
        thing_id, attachment_id = key
        if lifecycle.get(thing_id) not in {LifecyclePhase.ACTIVE, LifecyclePhase.DORMANT}:
            continue
        if (thing_id, attachment_id) not in runtime.programs:
            _fail("worldsave.capability_principal_missing", "capability requirements target an absent attachment")
        if capability_broker is None:
            if any(requirement.required for requirement in rows):
                _fail("worldsave.capability_denied", "required capability has no current policy broker")
            plans[key] = CapabilityPlan(
                (),
                tuple(requirement.capability_id for requirement in rows),
                tuple(
                    requirement.reduced_mode
                    for requirement in rows
                    if requirement.reduced_mode is not None
                ),
            )
            continue
        try:
            plans[key] = capability_broker.resolve_requirements(
                _principal_for_attachment(thing_id, attachment_id),
                tuple(rows),
                now=policy_time,
            )
        except Exception as exc:
            code = getattr(exc, "code", "capability_denied")
            raise LifecycleError(
                "worldsave.capability_denied",
                f"current capability policy rejected restored attachment ({code})",
                cause=exc,
            ) from exc

    world = WorldRuntime(
        document,
        runtime,
        program_registry,
        lifecycle,
        retained=retained,
        deferred_external_waits=tuple(deferred),
    )
    return RestoreResult(world, plans, tuple(deferred))


def _validate_against_authored(
    row: ThingRuntimeSnapshot,
    document: CanonicalDocument,
    program_registry: Mapping[str, IRProgram],
) -> None:
    authored = document.things.get(row.thing_id)
    if authored is None or authored.tombstoned:
        _fail("worldsave.authored_basis_missing", f"no live authored Thing for {row.thing_id}")
    authored_attachments = set(authored.behaviours)
    snapshot_attachments = {item.attachment_id for item in row.attachments}
    if authored_attachments != snapshot_attachments:
        _fail(
            "worldsave.attachment_mismatch",
            f"saved attachment identities for {row.thing_id} differ from authored basis",
        )
    if set(row.attachment_order) != snapshot_attachments:
        _fail("worldsave.invalid_attachment_order", "saved attachment order is incomplete")
    for item in row.attachments:
        program = program_registry.get(item.behaviour_revision)
        if program is None:
            _fail(
                "worldsave.exact_artifact_unavailable",
                f"exact Behaviour revision {item.behaviour_revision!r} is unavailable",
            )
        try:
            validate_program(program)
        except Exception as exc:
            raise LifecycleError("worldsave.invalid_artifact", "saved Behaviour revision is invalid", cause=exc) from exc
        if program.behaviour_revision != item.behaviour_revision:
            _fail("worldsave.exact_artifact_unavailable", "program registry key/revision mismatch")


def _sqlite_failure(exc: sqlite3.Error, operation: str) -> LifecycleError:
    name = str(getattr(exc, "sqlite_errorname", "") or "").upper()
    message = str(exc).lower()
    if name.startswith("SQLITE_FULL") or "database or disk is full" in message:
        code = "worldsave.quota_exceeded"
    elif name.startswith(("SQLITE_READONLY", "SQLITE_PERM", "SQLITE_AUTH")) or "readonly" in message:
        code = "worldsave.permission_denied"
    elif name.startswith(("SQLITE_CORRUPT", "SQLITE_NOTADB")) or "malformed" in message or "not a database" in message:
        code = "worldsave.corrupt_store"
    elif name.startswith(("SQLITE_CANTOPEN", "SQLITE_BUSY", "SQLITE_LOCKED")):
        code = "worldsave.unavailable"
    elif name.startswith("SQLITE_IOERR"):
        code = "worldsave.io_failure"
    else:
        code = "worldsave.database_error"
    return LifecycleError(code, f"{operation} failed", cause=exc)


class SQLiteWorldSaveStore:
    """Crash-consistent persistent-world head store.

    The tables are deliberately separate from SMX-025 project ownership, so authored
    project persistence and runtime WorldSave persistence remain different planes even
    when callers choose the same SQLite database file.
    """

    def __init__(self, path: str | Path, *, timeout: float = 5.0):
        self.path = str(path)
        try:
            self._db = sqlite3.connect(self.path, timeout=timeout, isolation_level=None)
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._ensure_schema()
        except sqlite3.Error as exc:
            try:
                self._db.close()
            except Exception:
                pass
            raise _sqlite_failure(exc, "opening WorldSave store") from exc

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteWorldSaveStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        try:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS world_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS world_revisions (
                    world_save_id TEXT NOT NULL,
                    world_revision_id TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    payload_digest TEXT NOT NULL,
                    PRIMARY KEY(world_save_id, world_revision_id)
                )"""
            )
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS world_heads (
                    world_save_id TEXT PRIMARY KEY,
                    world_revision_id TEXT NOT NULL,
                    FOREIGN KEY(world_save_id, world_revision_id)
                        REFERENCES world_revisions(world_save_id, world_revision_id)
                )"""
            )
            self._db.execute(
                "INSERT OR IGNORE INTO world_metadata(key,value) VALUES('schema',?)",
                (WORLD_STORE_SCHEMA,),
            )
            self._db.execute(
                "INSERT OR IGNORE INTO world_metadata(key,value) VALUES('version',?)",
                (str(WORLD_STORE_VERSION),),
            )
            self._assert_format()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "initializing WorldSave store") from exc

    def _assert_format(self) -> None:
        try:
            rows = dict(self._db.execute(
                "SELECT key,value FROM world_metadata WHERE key IN ('schema','version')"
            ))
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading WorldSave store format") from exc
        if rows.get("schema") != WORLD_STORE_SCHEMA:
            _fail("worldsave.unsupported_store_format", "WorldSave store schema is unsupported")
        try:
            version = int(rows.get("version", "-1"))
        except (TypeError, ValueError) as exc:
            raise LifecycleError("worldsave.corrupt_store", "WorldSave store version is malformed", cause=exc) from exc
        if version != WORLD_STORE_VERSION:
            _fail("worldsave.unsupported_store_version", f"WorldSave store version {version} is unsupported")

    @staticmethod
    def _checkpoint(hook: FaultHook | None, stage: str) -> None:
        if hook is not None:
            hook(stage)

    def save(
        self,
        snapshot: WorldSaveSnapshot,
        *,
        fault_hook: FaultHook | None = None,
    ) -> WorldSaveSnapshot:
        payload = serialize_world_save(snapshot)
        save_id = str(snapshot.world_save_id)
        revision_id = str(snapshot.world_revision_id)
        digest = "sha256:" + sha256(payload).hexdigest()
        self._checkpoint(fault_hook, "prepared")
        self._assert_format()
        committed = False
        try:
            self._db.execute("BEGIN IMMEDIATE")
            existing = self._db.execute(
                "SELECT payload,payload_digest FROM world_revisions WHERE world_save_id=? AND world_revision_id=?",
                (save_id, revision_id),
            ).fetchone()
            if existing is not None:
                if bytes(existing[0]) != payload or existing[1] != digest:
                    _fail(
                        "worldsave.revision_conflict",
                        "the same WorldRevisionId already names different bytes",
                    )
            else:
                self._db.execute(
                    "INSERT INTO world_revisions(world_save_id,world_revision_id,payload,payload_digest) VALUES(?,?,?,?)",
                    (save_id, revision_id, sqlite3.Binary(payload), digest),
                )
            self._checkpoint(fault_hook, "revision_recorded")

            checked = self._read_revision(save_id, revision_id)
            if checked != snapshot:
                _fail("worldsave.corrupt_store", "WorldSave readback differs from prepared candidate")
            self._checkpoint(fault_hook, "candidate_verified")

            self._db.execute(
                "INSERT INTO world_heads(world_save_id,world_revision_id) VALUES(?,?) "
                "ON CONFLICT(world_save_id) DO UPDATE SET world_revision_id=excluded.world_revision_id",
                (save_id, revision_id),
            )
            self._checkpoint(fault_hook, "head_advanced")
            self._db.execute("COMMIT")
            committed = True
            self._checkpoint(fault_hook, "committed")
            return snapshot
        except LifecycleError:
            if not committed and self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if not committed and self._db.in_transaction:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise _sqlite_failure(exc, "publishing WorldSave revision") from exc
        except BaseException:
            if not committed and self._db.in_transaction:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise

    def _read_revision(self, save_id: str, revision_id: str) -> WorldSaveSnapshot:
        try:
            row = self._db.execute(
                "SELECT payload,payload_digest FROM world_revisions WHERE world_save_id=? AND world_revision_id=?",
                (save_id, revision_id),
            ).fetchone()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading WorldSave revision") from exc
        if row is None:
            _fail("worldsave.corrupt_store", "WorldSave head references a missing revision")
        payload = bytes(row[0])
        if row[1] != "sha256:" + sha256(payload).hexdigest():
            _fail("worldsave.corrupt_store", "stored WorldSave payload digest mismatch")
        return deserialize_world_save(payload)

    def load(self, world_save_id: WorldSaveId | str) -> WorldSaveSnapshot:
        self._assert_format()
        save_id = str(world_save_id)
        try:
            row = self._db.execute(
                "SELECT world_revision_id FROM world_heads WHERE world_save_id=?",
                (save_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise _sqlite_failure(exc, "reading WorldSave head") from exc
        if row is None:
            _fail("worldsave.not_found", f"WorldSave {save_id!r} has no committed head")
        return self._read_revision(save_id, str(row[0]))
