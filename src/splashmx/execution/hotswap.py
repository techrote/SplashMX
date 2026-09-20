"""Transactional Behaviour hot replacement for the production execution runtime.

SMX-028 implements Architecture-v1 section 3.6 over the SMX-026 serial scheduler
and SMX-027 capability broker. Replacement is a quiescent scheduler operation:
the exact target program, private-state migration, every live pending-work outcome,
and target capability requirements are validated before any live runtime reference
is changed. Capability grants are never copied into Behaviour state.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
import heapq
import re
from typing import Any, Mapping

from splashmx.canonical.core import BehaviourAttachmentId, ThingId
from splashmx.execution.ir import (
    Activation,
    ExecutionError,
    ExecutionRuntime,
    IRProgram,
    PendingTimer,
    _validate_plain,
    validate_program,
)
from splashmx.security.capabilities import (
    CapabilityBroker,
    CapabilityError,
    CapabilityPlan,
    CapabilityRequirement,
    PrincipalId,
)


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class ReplacementError(ValueError):
    """Typed hot-replacement failure. A raised error guarantees no publication."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise ReplacementError(code, message)


def _semantic_token(value: str, role: str) -> None:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        _fail("replacement.invalid_contract", f"{role} must be a bounded semantic token")


@dataclass(frozen=True)
class PrivateStateMigration:
    """Explicit private-state treatment for one compatible replacement.

    ``preserve`` carries the complete old private mapping unchanged. ``migrate``
    starts from the target program defaults, copies named old fields into named
    target fields, applies explicit literal values, and requires every old source
    field to be either consumed or explicitly dropped. Thus schema change cannot
    silently forget private state.
    """

    mode: str = "preserve"
    field_map: Mapping[str, str] = field(default_factory=dict)
    literals: Mapping[str, Any] = field(default_factory=dict)
    drop_source_keys: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.mode not in {"preserve", "migrate"}:
            _fail("replacement.invalid_contract", "private-state mode must be preserve or migrate")
        if self.mode == "preserve" and (self.field_map or self.literals or self.drop_source_keys):
            _fail("replacement.invalid_contract", "preserve mode cannot also declare migration fields")
        for target, source in self.field_map.items():
            if not isinstance(target, str) or not target or not isinstance(source, str) or not source:
                _fail("replacement.invalid_contract", "state field_map requires non-empty string keys")
        for key in self.literals:
            if not isinstance(key, str) or not key:
                _fail("replacement.invalid_contract", "state literal keys must be non-empty strings")
        if set(self.field_map) & set(self.literals):
            _fail("replacement.invalid_contract", "state target field cannot be both mapped and literal")
        for key in self.drop_source_keys:
            if not isinstance(key, str) or not key:
                _fail("replacement.invalid_contract", "dropped source keys must be non-empty strings")
        _validate_plain(dict(self.literals), where="replacement state literals")


@dataclass(frozen=True)
class HandlerMigration:
    """Explicit outcome for queued/timer work owned by one old handler."""

    action: str
    target_handler: str | None = None

    def __post_init__(self) -> None:
        if self.action not in {"map", "cancel"}:
            _fail("replacement.invalid_contract", "pending-work action must be map or cancel")
        if self.action == "map":
            if not isinstance(self.target_handler, str) or not self.target_handler:
                _fail("replacement.invalid_contract", "mapped work requires a target handler")
        elif self.target_handler is not None:
            _fail("replacement.invalid_contract", "cancelled work cannot name a target handler")

    @classmethod
    def map_to(cls, handler_id: str) -> "HandlerMigration":
        return cls("map", handler_id)

    @classmethod
    def cancel(cls) -> "HandlerMigration":
        return cls("cancel")


@dataclass(frozen=True)
class PendingWorkMigration:
    """Complete policy for work that has committed but has not executed yet.

    Every live timer or queued activation owned by the replaced attachment must
    match a handler action. Already-emitted events are committed outputs and are
    intentionally not rewritten. Pending host-service requests require an explicit
    preserve/cancel decision; preserving them preserves data only, never grants.
    """

    handlers: Mapping[str, HandlerMigration] = field(default_factory=dict)
    service_requests: str = "reject"

    def __post_init__(self) -> None:
        if self.service_requests not in {"preserve", "cancel", "reject"}:
            _fail(
                "replacement.invalid_contract",
                "service_requests policy must be preserve, cancel or reject",
            )
        for handler_id, action in self.handlers.items():
            if not isinstance(handler_id, str) or not handler_id:
                _fail("replacement.invalid_contract", "pending handler keys must be non-empty strings")
            if not isinstance(action, HandlerMigration):
                _fail("replacement.invalid_contract", "pending handler values must be HandlerMigration")


@dataclass(frozen=True)
class ReplacementContract:
    """Trusted compatibility decision for one exact source-to-target revision edge."""

    contract_id: str
    from_revision: str
    to_revision: str
    private_state: PrivateStateMigration = field(default_factory=PrivateStateMigration)
    pending_work: PendingWorkMigration = field(default_factory=PendingWorkMigration)
    capability_requirements: tuple[CapabilityRequirement, ...] = ()

    def __post_init__(self) -> None:
        _semantic_token(self.contract_id, "contract_id")
        for role, value in (("from_revision", self.from_revision), ("to_revision", self.to_revision)):
            if not isinstance(value, str) or not value:
                _fail("replacement.invalid_contract", f"{role} must be non-empty")
        if not isinstance(self.private_state, PrivateStateMigration):
            _fail("replacement.invalid_contract", "private_state must be PrivateStateMigration")
        if not isinstance(self.pending_work, PendingWorkMigration):
            _fail("replacement.invalid_contract", "pending_work must be PendingWorkMigration")
        for requirement in self.capability_requirements:
            if not isinstance(requirement, CapabilityRequirement):
                _fail("replacement.invalid_contract", "capability requirements must be typed declarations")


@dataclass(frozen=True)
class ReplacementOutcome:
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    from_revision: str
    to_revision: str
    mapped_work: int
    cancelled_work: int
    preserved_service_requests: int
    cancelled_service_requests: int
    capability_plan: CapabilityPlan | None


def principal_for_attachment(
    thing_id: ThingId, attachment_id: BehaviourAttachmentId
) -> PrincipalId:
    """Derive the same stable Behaviour principal used by SMX-027 service requests."""
    return PrincipalId(f"behaviour:{thing_id}:{attachment_id}")


def _migrate_private_state(
    old_state: Mapping[str, Any], target: IRProgram, migration: PrivateStateMigration
) -> dict[str, Any]:
    try:
        _validate_plain(dict(old_state), where="pre-replacement private state")
    except ExecutionError as exc:
        raise ReplacementError("replacement.invalid_private_state", str(exc)) from exc

    if migration.mode == "preserve":
        result = deepcopy(dict(old_state))
    else:
        source_keys = set(old_state)
        mapped_sources = set(migration.field_map.values())
        declared = mapped_sources | set(migration.drop_source_keys)
        missing = source_keys - declared
        unknown_drop = set(migration.drop_source_keys) - source_keys
        unknown_source = mapped_sources - source_keys
        if missing:
            _fail(
                "replacement.unmapped_private_state",
                "migration leaves old private fields without preserve/drop semantics: "
                + ", ".join(sorted(missing)),
            )
        if unknown_drop:
            _fail(
                "replacement.invalid_state_migration",
                "migration drops absent old fields: " + ", ".join(sorted(unknown_drop)),
            )
        if unknown_source:
            _fail(
                "replacement.invalid_state_migration",
                "migration reads absent old fields: " + ", ".join(sorted(unknown_source)),
            )
        result = deepcopy(dict(target.private_defaults))
        for target_key, source_key in migration.field_map.items():
            result[target_key] = deepcopy(old_state[source_key])
        for target_key, value in migration.literals.items():
            result[target_key] = deepcopy(value)

    try:
        _validate_plain(result, where="post-replacement private state")
    except ExecutionError as exc:
        raise ReplacementError("replacement.invalid_private_state", str(exc)) from exc
    return result


def _handler_action(
    policy: PendingWorkMigration, old_handler: str, target_handlers: set[str]
) -> HandlerMigration:
    action = policy.handlers.get(old_handler)
    if action is None:
        _fail(
            "replacement.pending_work_undeclared",
            f"live pending handler {old_handler!r} has no explicit map/cancel outcome",
        )
    if action.action == "map" and action.target_handler not in target_handlers:
        _fail(
            "replacement.pending_target_missing",
            f"mapped target handler {action.target_handler!r} does not exist in target program",
        )
    return action


def _stage_pending_work(
    runtime: ExecutionRuntime,
    thing_id: ThingId,
    attachment_id: BehaviourAttachmentId,
    target: IRProgram,
    policy: PendingWorkMigration,
) -> tuple[dict[str, PendingTimer], list[tuple[int, int, Activation]], list[Any], int, int, int, int]:
    target_handlers = {handler.handler_id for handler in target.handlers}
    staged_timers = dict(runtime.pending_timers)
    cancelled_timer_ids: set[str] = set()
    timer_target_handlers: dict[str, str] = {}
    mapped_work = 0
    cancelled_work = 0

    for timer_id, timer in list(runtime.pending_timers.items()):
        if timer.thing_id != thing_id or timer.attachment_id != attachment_id:
            continue
        action = _handler_action(policy, timer.handler_id, target_handlers)
        if action.action == "cancel":
            staged_timers.pop(timer_id, None)
            cancelled_timer_ids.add(timer_id)
            cancelled_work += 1
        else:
            assert action.target_handler is not None
            timer_target_handlers[timer_id] = action.target_handler
            staged_timers[timer_id] = replace(timer, handler_id=action.target_handler)
            mapped_work += 1

    staged_queue: list[tuple[int, int, Activation]] = []
    for due_tick, sequence, activation in runtime._queue:
        if activation.thing_id != thing_id or activation.attachment_id != attachment_id:
            staged_queue.append((due_tick, sequence, activation))
            continue
        if activation.timer_id is not None:
            source_timer = runtime.pending_timers.get(activation.timer_id)
            if source_timer is None or source_timer.sequence != activation.sequence:
                staged_queue.append((due_tick, sequence, activation))
                continue
            if activation.timer_id in cancelled_timer_ids:
                continue
            target_handler = timer_target_handlers[activation.timer_id]
            staged_queue.append(
                (due_tick, sequence, replace(activation, handler_id=target_handler))
            )
            continue
        action = _handler_action(policy, activation.handler_id, target_handlers)
        if action.action == "cancel":
            cancelled_work += 1
            continue
        assert action.target_handler is not None
        staged_queue.append(
            (due_tick, sequence, replace(activation, handler_id=action.target_handler))
        )
        mapped_work += 1
    heapq.heapify(staged_queue)

    owned_services = [
        request
        for request in runtime.service_requests
        if request.thing_id == thing_id and request.attachment_id == attachment_id
    ]
    preserved_services = 0
    cancelled_services = 0
    if owned_services:
        if policy.service_requests == "reject":
            _fail(
                "replacement.pending_service_undeclared",
                "attachment has pending host-service requests without preserve/cancel semantics",
            )
        if policy.service_requests == "cancel":
            staged_services = [
                request
                for request in runtime.service_requests
                if request.thing_id != thing_id or request.attachment_id != attachment_id
            ]
            cancelled_services = len(owned_services)
        else:
            staged_services = list(runtime.service_requests)
            preserved_services = len(owned_services)
    else:
        staged_services = list(runtime.service_requests)

    return (
        staged_timers,
        staged_queue,
        staged_services,
        mapped_work,
        cancelled_work,
        preserved_services,
        cancelled_services,
    )


def replace_behaviour(
    runtime: ExecutionRuntime,
    thing_id: ThingId,
    attachment_id: BehaviourAttachmentId,
    target_program: IRProgram,
    contract: ReplacementContract,
    *,
    capability_broker: CapabilityBroker | None = None,
    policy_time: int = 0,
) -> ReplacementOutcome:
    """Validate, stage and atomically publish one live Behaviour replacement.

    ``ExecutionRuntime`` is a serial scheduler. This operation is intentionally a
    scheduler-boundary operation: it performs no user callback and does not run an
    activation while staging. Pending work may exist and is migrated explicitly.
    """
    if not isinstance(runtime, ExecutionRuntime):
        _fail("replacement.invalid_runtime", "replacement requires ExecutionRuntime")
    if not isinstance(thing_id, ThingId) or not isinstance(attachment_id, BehaviourAttachmentId):
        _fail("replacement.invalid_identity", "typed ThingId and BehaviourAttachmentId are required")
    if not isinstance(contract, ReplacementContract):
        _fail("replacement.invalid_contract", "typed ReplacementContract is required")

    key = (thing_id, attachment_id)
    state = runtime.states.get(thing_id)
    old_program = runtime.programs.get(key)
    if state is None:
        _fail("replacement.unknown_thing", f"Thing {thing_id} is not live")
    if old_program is None or attachment_id not in state.private_by_attachment:
        _fail("replacement.unknown_attachment", f"attachment {thing_id}/{attachment_id} is not live")
    if attachment_id not in runtime.attachment_order.get(thing_id, ()):
        _fail("replacement.identity_mismatch", "attachment is not present in the semantic execution order")
    if old_program.behaviour_revision != contract.from_revision:
        _fail(
            "replacement.source_revision_mismatch",
            "live Behaviour revision does not match compatibility contract source",
        )

    candidate = deepcopy(target_program)
    if not isinstance(candidate, IRProgram):
        _fail("replacement.invalid_target", "target artifact must contain an IRProgram")
    if candidate.behaviour_revision != contract.to_revision:
        _fail(
            "replacement.target_revision_mismatch",
            "target Behaviour revision does not match compatibility contract target",
        )
    try:
        validate_program(candidate)
    except ExecutionError as exc:
        raise ReplacementError("replacement.invalid_target", str(exc)) from exc

    capability_plan: CapabilityPlan | None = None
    if contract.capability_requirements:
        if capability_broker is None:
            _fail(
                "replacement.capability_broker_required",
                "target Behaviour declares capabilities but no trusted broker was supplied",
            )
        principal = principal_for_attachment(thing_id, attachment_id)
        try:
            capability_plan = capability_broker.resolve_requirements(
                principal, contract.capability_requirements, now=policy_time
            )
        except CapabilityError as exc:
            raise ReplacementError("replacement.capability_denied", str(exc)) from exc

    staged_private = _migrate_private_state(
        state.private_by_attachment[attachment_id], candidate, contract.private_state
    )
    (
        staged_timers,
        staged_queue,
        staged_services,
        mapped_work,
        cancelled_work,
        preserved_services,
        cancelled_services,
    ) = _stage_pending_work(
        runtime, thing_id, attachment_id, candidate, contract.pending_work
    )

    runtime.programs[key] = candidate
    state.private_by_attachment[attachment_id] = staged_private
    runtime.pending_timers = staged_timers
    runtime._queue = staged_queue
    runtime.service_requests = staged_services

    return ReplacementOutcome(
        thing_id=thing_id,
        attachment_id=attachment_id,
        from_revision=contract.from_revision,
        to_revision=contract.to_revision,
        mapped_work=mapped_work,
        cancelled_work=cancelled_work,
        preserved_service_requests=preserved_services,
        cancelled_service_requests=cancelled_services,
        capability_plan=capability_plan,
    )
