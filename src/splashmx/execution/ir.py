"""Production bounded behaviour IR and deterministic scheduler for SplashMX.

SMX-026 owns the common execution boundary shared by beginner Rules and advanced
Behaviours. The module deliberately stops at mediated service *requests*: capability
issuance/authorization and host invocation belong to SMX-027.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import heapq
import math
import random
import re
from typing import Any, Mapping, Sequence

from splashmx.canonical.core import BehaviourAttachmentId, CanonicalDocument, ThingId

IR_VERSION = "splashmx.behaviour-ir/1"
MAX_PROGRAM_DEPTH = 64
MAX_PROGRAM_INSTRUCTIONS = 100_000
MAX_LITERAL_NODES = 100_000
MAX_LITERAL_STRING_BYTES = 8 * 1024 * 1024

_FORBIDDEN_FIELD_NAMES = {
    "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
    "databaserowid", "cachekey", "transportpeerid", "connectionhandle",
    "socketid", "sessionid", "processhandle", "capabilitytoken", "capabilitygrant",
}
_FORBIDDEN_OPCODES = {
    "eval", "javascript", "js", "gdscript", "csharp", "native_call", "host_call",
    "filesystem", "raw_socket", "raw_network", "set_foreign", "set_other_state",
    "spawn_process", "load_extension",
}
_ALLOWED_OPCODES = {
    "noop", "set_public", "set_private", "add_public", "add_private", "emit",
    "schedule", "cancel_timer", "request_service", "if", "repeat", "call",
}
_ALLOWED_EXPRESSIONS = {
    "literal", "public", "private", "payload", "logical_tick", "random_int",
    "add", "sub", "mul", "div", "eq", "ne", "lt", "le", "gt", "ge",
    "and", "or", "not", "list",
}


class ExecutionError(ValueError):
    """Typed execution/validation failure suitable for the production error envelope."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise ExecutionError(code, message)


def _normalise_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _validate_plain(
    value: Any, *, where: str = "value", depth: int = 0,
    counter: list[int] | None = None,
) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_LITERAL_NODES:
        _fail("execution.program_limit", f"{where} exceeds literal node limit")
    if depth > MAX_PROGRAM_DEPTH:
        _fail("execution.program_limit", f"{where} exceeds structural depth limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("execution.invalid_literal", f"{where} contains NaN or infinity")
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_LITERAL_STRING_BYTES:
            _fail("execution.program_limit", f"{where} string exceeds byte limit")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_plain(child, where=f"{where}[{index}]", depth=depth + 1, counter=counter)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("execution.invalid_literal", f"{where} map keys must be strings")
            if _normalise_field_name(key) in _FORBIDDEN_FIELD_NAMES:
                _fail(
                    "execution.forbidden_transient_identity",
                    f"{where} contains forbidden durable/authority field {key!r}",
                )
            _validate_plain(child, where=f"{where}.{key}", depth=depth + 1, counter=counter)
        return
    _fail("execution.invalid_literal", f"{where} contains unsupported type {type(value).__name__}")


def literal(value: Any) -> Mapping[str, Any]:
    return {"expr": "literal", "value": value}


def public(key: str) -> Mapping[str, Any]:
    return {"expr": "public", "key": key}


def private(key: str) -> Mapping[str, Any]:
    return {"expr": "private", "key": key}


def payload(key: str | None = None) -> Mapping[str, Any]:
    row: dict[str, Any] = {"expr": "payload"}
    if key is not None:
        row["key"] = key
    return row


def expression(op: str, *args: Any) -> Mapping[str, Any]:
    return {"expr": op, "args": list(args)}


@dataclass(frozen=True)
class IRInstruction:
    op: str
    args: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IRHandler:
    handler_id: str
    trigger: str
    instructions: tuple[IRInstruction, ...]


@dataclass(frozen=True)
class IRProgram:
    behaviour_revision: str
    handlers: tuple[IRHandler, ...]
    procedures: Mapping[str, tuple[IRInstruction, ...]] = field(default_factory=dict)
    private_defaults: Mapping[str, Any] = field(default_factory=dict)
    ir_version: str = IR_VERSION
    source_kind: str = "advanced"

    def validate(self) -> None:
        validate_program(self)


@dataclass(frozen=True)
class BudgetLimits:
    """Independent deterministic limits; instruction steps are the CPU proxy."""

    instruction_steps: int = 20_000
    recursion_depth: int = 32
    allocations: int = 10_000
    emitted_work: int = 1_000
    timers_per_activation: int = 256
    pending_timers: int = 4_096
    queue_entries: int = 8_192
    service_requests: int = 256
    pending_service_requests: int = 4_096
    outbox_entries: int = 8_192
    activations_per_run: int = 20_000

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                _fail("execution.invalid_budget", f"{name} must be a positive integer")


@dataclass
class RuntimeThingState:
    public_state: dict[str, Any]
    private_by_attachment: dict[BehaviourAttachmentId, dict[str, Any]]


@dataclass(frozen=True)
class Activation:
    due_tick: int
    sequence: int
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    handler_id: str
    payload: Any = None
    timer_id: str | None = None


@dataclass(frozen=True)
class PendingTimer:
    timer_id: str
    due_tick: int
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    handler_id: str
    payload: Any
    sequence: int = -1


@dataclass(frozen=True)
class EmittedWork:
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    event: str
    payload: Any
    source_activation_sequence: int


@dataclass(frozen=True)
class ServiceRequest:
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    service: str
    payload: Any
    request_id: str
    source_activation_sequence: int


@dataclass(frozen=True)
class ActivationFault:
    code: str
    message: str
    activation: Activation


@dataclass(frozen=True)
class _Effect:
    kind: str
    value: Any


class _BudgetTracker:
    def __init__(self, limits: BudgetLimits):
        self.limits = limits
        self.instructions = 0
        self.allocations = 0
        self.emitted = 0
        self.timers = 0
        self.services = 0

    def instruction(self, units: int = 1) -> None:
        self.instructions += units
        if self.instructions > self.limits.instruction_steps:
            _fail(
                "execution.instruction_budget",
                "activation exceeded deterministic instruction/CPU-proxy budget",
            )

    def allocation(self, units: int = 1) -> None:
        self.allocations += units
        if self.allocations > self.limits.allocations:
            _fail("execution.allocation_budget", "activation exceeded allocation budget")

    def emitted_work(self, units: int = 1) -> None:
        self.emitted += units
        if self.emitted > self.limits.emitted_work:
            _fail("execution.emitted_work_budget", "activation exceeded emitted-work budget")

    def timer(self, units: int = 1) -> None:
        self.timers += units
        if self.timers > self.limits.timers_per_activation:
            _fail("execution.timer_budget", "activation exceeded timer-creation budget")

    def service(self, units: int = 1) -> None:
        self.services += units
        if self.services > self.limits.service_requests:
            _fail("execution.service_request_budget", "activation exceeded service-request budget")


def _allocation_units(value: Any) -> int:
    if value is None or isinstance(value, (bool, int, float)):
        return 0
    if isinstance(value, str):
        return 1
    if isinstance(value, (list, tuple)):
        return 1 + sum(_allocation_units(child) for child in value)
    if isinstance(value, Mapping):
        return 1 + sum(_allocation_units(key) + _allocation_units(child) for key, child in value.items())
    return 1


def _clone_value(value: Any, tracker: _BudgetTracker) -> Any:
    tracker.allocation(_allocation_units(value))
    return deepcopy(value)


def _validate_expression(node: Any, *, depth: int = 0) -> int:
    if depth > MAX_PROGRAM_DEPTH:
        _fail("execution.program_limit", "expression exceeds structural depth limit")
    if not isinstance(node, Mapping) or not isinstance(node.get("expr"), str):
        _fail("execution.invalid_expression", "IR expressions require an explicit expr opcode")
    op = node["expr"]
    if op not in _ALLOWED_EXPRESSIONS:
        _fail("execution.unknown_expression", f"unknown IR expression {op!r}")
    count = 1
    if op == "literal":
        if set(node) != {"expr", "value"}:
            _fail("execution.invalid_expression", "literal expression has invalid fields")
        _validate_plain(node["value"], where="IR literal")
        return count
    if op in {"public", "private"}:
        if set(node) != {"expr", "key"} or not isinstance(node["key"], str) or not node["key"]:
            _fail("execution.invalid_expression", f"{op} expression requires a non-empty key")
        return count
    if op == "payload":
        if not set(node) <= {"expr", "key"} or ("key" in node and not isinstance(node["key"], str)):
            _fail("execution.invalid_expression", "payload expression has invalid key")
        return count
    if op == "logical_tick":
        if set(node) != {"expr"}:
            _fail("execution.invalid_expression", "logical_tick takes no fields")
        return count
    if op == "random_int":
        if set(node) != {"expr", "min", "max"}:
            _fail("execution.invalid_expression", "random_int requires min and max expressions")
        return count + _validate_expression(node["min"], depth=depth + 1) + _validate_expression(node["max"], depth=depth + 1)
    if op == "not":
        if set(node) != {"expr", "arg"}:
            _fail("execution.invalid_expression", "not requires arg")
        return count + _validate_expression(node["arg"], depth=depth + 1)
    if op == "list":
        if set(node) != {"expr", "args"} or not isinstance(node["args"], (list, tuple)):
            _fail("execution.invalid_expression", "list requires args")
        return count + sum(_validate_expression(child, depth=depth + 1) for child in node["args"])
    if set(node) != {"expr", "args"} or not isinstance(node["args"], (list, tuple)):
        _fail("execution.invalid_expression", f"{op} requires args")
    arity = len(node["args"])
    if op in {"add", "sub", "mul", "div", "eq", "ne", "lt", "le", "gt", "ge"} and arity != 2:
        _fail("execution.invalid_expression", f"{op} requires exactly two args")
    if op in {"and", "or"} and arity < 1:
        _fail("execution.invalid_expression", f"{op} requires at least one arg")
    return count + sum(_validate_expression(child, depth=depth + 1) for child in node["args"])


def _validate_block(
    block: Sequence[IRInstruction], procedures: Mapping[str, tuple[IRInstruction, ...]],
    handler_ids: set[str], *, depth: int = 0,
) -> int:
    if depth > MAX_PROGRAM_DEPTH:
        _fail("execution.program_limit", "IR block exceeds structural depth limit")
    count = 0
    for instruction in block:
        if not isinstance(instruction, IRInstruction):
            _fail("execution.invalid_instruction", "IR blocks may contain only IRInstruction values")
        count += 1
        if count > MAX_PROGRAM_INSTRUCTIONS:
            _fail("execution.program_limit", "IR program exceeds instruction count limit")
        op, args = instruction.op, instruction.args
        if op in _FORBIDDEN_OPCODES:
            _fail("execution.forbidden_opcode", f"forbidden host/foreign-state opcode {op!r}")
        if op not in _ALLOWED_OPCODES:
            _fail("execution.unknown_opcode", f"unknown required IR opcode {op!r}")
        if not isinstance(args, Mapping):
            _fail("execution.invalid_instruction", f"{op} args must be a mapping")
        if op == "noop":
            if args:
                _fail("execution.invalid_instruction", "noop takes no args")
        elif op in {"set_public", "set_private", "add_public", "add_private"}:
            if set(args) != {"key", "value"} or not isinstance(args["key"], str) or not args["key"]:
                _fail("execution.invalid_instruction", f"{op} requires key and value")
            count += _validate_expression(args["value"], depth=depth + 1)
        elif op == "emit":
            if set(args) != {"event", "payload"}:
                _fail("execution.invalid_instruction", "emit requires event and payload")
            if not isinstance(args["event"], str) or not args["event"]:
                _fail("execution.invalid_instruction", "emit event must be non-empty")
            count += _validate_expression(args["payload"], depth=depth + 1)
        elif op == "schedule":
            if set(args) != {"timer_id", "delay", "handler", "payload"}:
                _fail("execution.invalid_instruction", "schedule requires timer_id, delay, handler and payload")
            if not isinstance(args["timer_id"], str) or not args["timer_id"] or len(args["timer_id"]) > 128:
                _fail("execution.invalid_instruction", "schedule timer_id must be a bounded non-empty string")
            if not isinstance(args["delay"], int) or isinstance(args["delay"], bool) or args["delay"] < 0:
                _fail("execution.invalid_instruction", "schedule delay must be a non-negative logical-tick integer")
            if args["handler"] not in handler_ids:
                _fail("execution.unknown_handler", f"scheduled handler {args['handler']!r} does not exist")
            count += _validate_expression(args["payload"], depth=depth + 1)
        elif op == "cancel_timer":
            if set(args) != {"timer_id"} or not isinstance(args["timer_id"], str) or not args["timer_id"]:
                _fail("execution.invalid_instruction", "cancel_timer requires timer_id")
        elif op == "request_service":
            if set(args) != {"service", "request_id", "payload"}:
                _fail("execution.invalid_instruction", "request_service requires service, request_id and payload")
            if not isinstance(args["service"], str) or not args["service"]:
                _fail("execution.invalid_instruction", "service name must be non-empty")
            if not isinstance(args["request_id"], str) or not args["request_id"]:
                _fail("execution.invalid_instruction", "request_id must be non-empty")
            count += _validate_expression(args["payload"], depth=depth + 1)
        elif op == "if":
            if set(args) != {"condition", "then", "else"}:
                _fail("execution.invalid_instruction", "if requires condition, then and else")
            count += _validate_expression(args["condition"], depth=depth + 1)
            count += _validate_block(args["then"], procedures, handler_ids, depth=depth + 1)
            count += _validate_block(args["else"], procedures, handler_ids, depth=depth + 1)
        elif op == "repeat":
            if set(args) != {"count", "body"}:
                _fail("execution.invalid_instruction", "repeat requires count and body")
            if not isinstance(args["count"], int) or isinstance(args["count"], bool) or args["count"] < 0:
                _fail("execution.invalid_instruction", "repeat count must be a non-negative integer")
            count += _validate_block(args["body"], procedures, handler_ids, depth=depth + 1)
        elif op == "call":
            if set(args) != {"procedure"} or args["procedure"] not in procedures:
                _fail("execution.unknown_procedure", f"unknown procedure {args.get('procedure')!r}")
    return count


def validate_program(program: IRProgram) -> None:
    if program.ir_version != IR_VERSION:
        _fail("execution.unsupported_ir_version", f"unsupported IR version {program.ir_version!r}")
    if not isinstance(program.behaviour_revision, str) or not program.behaviour_revision:
        _fail("execution.invalid_program", "behaviour_revision must be non-empty")
    if program.source_kind not in {"rule", "advanced", "builtin", "visual", "text"}:
        _fail("execution.invalid_program", f"unknown source_kind {program.source_kind!r}")
    _validate_plain(program.private_defaults, where="private defaults")
    handler_ids = [handler.handler_id for handler in program.handlers]
    if len(handler_ids) != len(set(handler_ids)):
        _fail("execution.duplicate_handler", "handler IDs must be unique within one program")
    if any(not isinstance(name, str) or not name for name in handler_ids):
        _fail("execution.invalid_program", "handler IDs must be non-empty strings")
    if any(not isinstance(handler.trigger, str) or not handler.trigger for handler in program.handlers):
        _fail("execution.invalid_program", "handler triggers must be non-empty strings")
    if any(not isinstance(name, str) or not name for name in program.procedures):
        _fail("execution.invalid_program", "procedure names must be non-empty strings")
    total = 0
    ids = set(handler_ids)
    for handler in program.handlers:
        total += _validate_block(handler.instructions, program.procedures, ids)
    for block in program.procedures.values():
        total += _validate_block(block, program.procedures, ids)
    if total > MAX_PROGRAM_INSTRUCTIONS:
        _fail("execution.program_limit", "IR program exceeds instruction count limit")


def _friendly_expr(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return literal(value)
    if set(value) == {"public"}:
        return public(value["public"])
    if set(value) == {"private"}:
        return private(value["private"])
    if set(value) == {"payload"}:
        return payload(value["payload"])
    for op in ("add", "sub", "mul", "div", "eq", "ne", "lt", "le", "gt", "ge", "and", "or"):
        if set(value) == {op} and isinstance(value[op], (list, tuple)):
            return {"expr": op, "args": [_friendly_expr(child) for child in value[op]]}
    if set(value) == {"not"}:
        return {"expr": "not", "arg": _friendly_expr(value["not"])}
    return literal(dict(value))


def compile_rule(
    rule_id: str,
    trigger: str,
    actions: Sequence[Mapping[str, Any]],
    *,
    condition: Any | None = None,
    behaviour_revision: str | None = None,
) -> IRProgram:
    """Compile the first beginner Rule surface into the exact same IRProgram type."""
    if not isinstance(rule_id, str) or not rule_id or not isinstance(trigger, str) or not trigger:
        _fail("execution.invalid_rule", "rule_id and trigger must be non-empty strings")
    compiled: list[IRInstruction] = []
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            _fail("execution.invalid_rule", f"rule action {index} must be a mapping")
        kind = action.get("action")
        if kind in {"set_public", "set_private", "add_public", "add_private"}:
            if set(action) != {"action", "key", "value"}:
                _fail("execution.invalid_rule", f"{kind} rule action has invalid fields")
            compiled.append(
                IRInstruction(kind, {"key": action["key"], "value": _friendly_expr(action["value"])})
            )
        elif kind == "emit":
            if set(action) != {"action", "event", "payload"}:
                _fail("execution.invalid_rule", "emit rule action has invalid fields")
            compiled.append(
                IRInstruction("emit", {"event": action["event"], "payload": _friendly_expr(action["payload"])})
            )
        else:
            _fail(
                "execution.invalid_rule",
                f"beginner Rule action {kind!r} is unsupported; no privileged fallback exists",
            )
    body: tuple[IRInstruction, ...] = tuple(compiled)
    if condition is not None:
        body = (
            IRInstruction(
                "if", {"condition": _friendly_expr(condition), "then": body, "else": tuple()}
            ),
        )
    program = IRProgram(
        behaviour_revision=behaviour_revision or f"rule:{rule_id}:1",
        handlers=(IRHandler(f"rule:{rule_id}", trigger, body),),
        source_kind="rule",
    )
    validate_program(program)
    return program


class ExecutionRuntime:
    """Deterministic serial scheduler over canonical Thing/attachment identities."""

    def __init__(self, *, budgets: BudgetLimits | None = None, seed: int = 0):
        self.budgets = budgets or BudgetLimits()
        self.seed = int(seed)
        self.logical_tick = 0
        self.states: dict[ThingId, RuntimeThingState] = {}
        self.programs: dict[tuple[ThingId, BehaviourAttachmentId], IRProgram] = {}
        self.attachment_order: dict[ThingId, tuple[BehaviourAttachmentId, ...]] = {}
        self.pending_timers: dict[str, PendingTimer] = {}
        self.emitted: list[EmittedWork] = []
        self.service_requests: list[ServiceRequest] = []
        self.faults: list[ActivationFault] = []
        self._queue: list[tuple[int, int, Activation]] = []
        self._sequence = 0
        self._rng: dict[tuple[ThingId, BehaviourAttachmentId], random.Random] = {}

    @classmethod
    def from_document(
        cls,
        document: CanonicalDocument,
        program_registry: Mapping[str, IRProgram],
        *,
        attachment_order: Mapping[ThingId, Sequence[BehaviourAttachmentId]] | None = None,
        budgets: BudgetLimits | None = None,
        seed: int = 0,
    ) -> "ExecutionRuntime":
        runtime = cls(budgets=budgets, seed=seed)
        explicit = attachment_order or {}
        for thing_id, thing in document.things.items():
            if thing.tombstoned:
                continue
            attachments = dict(thing.behaviours)
            if thing_id in explicit:
                order = tuple(explicit[thing_id])
                if len(order) != len(set(order)) or set(order) != set(attachments):
                    _fail(
                        "execution.invalid_attachment_order",
                        f"explicit attachment order for {thing_id} must cover each attachment exactly once",
                    )
            elif len(attachments) <= 1:
                order = tuple(attachments)
            else:
                _fail(
                    "execution.attachment_order_required",
                    f"Thing {thing_id} has multiple behaviours; execution refuses map/hash/UUID lexical order and requires explicit semantic attachment order",
                )
            private_state: dict[BehaviourAttachmentId, dict[str, Any]] = {}
            runtime.attachment_order[thing_id] = order
            for attachment_id in order:
                attachment = attachments[attachment_id]
                program = program_registry.get(attachment.behaviour_revision)
                if program is None:
                    _fail(
                        "execution.missing_program",
                        f"no exact IR program for behaviour revision {attachment.behaviour_revision!r}",
                    )
                validate_program(program)
                if program.behaviour_revision != attachment.behaviour_revision:
                    _fail(
                        "execution.program_revision_mismatch",
                        "program registry key and Behaviour attachment revision differ",
                    )
                runtime.programs[(thing_id, attachment_id)] = program
                private_state[attachment_id] = deepcopy(dict(program.private_defaults))
                material = f"{runtime.seed}\0{thing_id}\0{attachment_id}".encode("utf-8")
                derived_seed = int.from_bytes(sha256(material).digest(), "big")
                runtime._rng[(thing_id, attachment_id)] = random.Random(derived_seed)
            runtime.states[thing_id] = RuntimeThingState(
                deepcopy(dict(thing.authored_state)), private_state
            )
        return runtime

    @property
    def queue_depth(self) -> int:
        return self._live_queue_count()

    def _live_queue_count(self) -> int:
        return sum(
            1 for _, _, activation in self._queue
            if activation.timer_id is None or activation.timer_id in self.pending_timers
        )

    def _next_sequence(self) -> int:
        value = self._sequence
        self._sequence += 1
        return value

    def _matching_handlers(
        self, thing_id: ThingId, trigger: str
    ) -> list[tuple[BehaviourAttachmentId, str]]:
        result: list[tuple[BehaviourAttachmentId, str]] = []
        if thing_id not in self.states:
            _fail("execution.unknown_thing", f"Thing {thing_id} is not a live execution target")
        for attachment_id in self.attachment_order.get(thing_id, ()):
            program = self.programs[(thing_id, attachment_id)]
            for handler in program.handlers:
                if handler.trigger == trigger:
                    result.append((attachment_id, handler.handler_id))
        return result

    def dispatch(
        self, thing_id: ThingId, trigger: str, payload_value: Any = None,
        *, due_tick: int | None = None,
    ) -> int:
        matches = self._matching_handlers(thing_id, trigger)
        if self._live_queue_count() + len(matches) > self.budgets.queue_entries:
            _fail("execution.queue_budget", "dispatch would exceed queue-entry budget")
        due = self.logical_tick if due_tick is None else due_tick
        if not isinstance(due, int) or isinstance(due, bool) or due < self.logical_tick:
            _fail(
                "execution.invalid_due_tick",
                "due_tick must be an integer at or after current logical time",
            )
        _validate_plain(payload_value, where="dispatch payload")
        for attachment_id, handler_id in matches:
            self._enqueue(
                Activation(
                    due, self._next_sequence(), thing_id, attachment_id,
                    handler_id, deepcopy(payload_value),
                )
            )
        return len(matches)

    def enqueue_handler(
        self, thing_id: ThingId, attachment_id: BehaviourAttachmentId,
        handler_id: str, payload_value: Any = None, *, due_tick: int | None = None,
    ) -> None:
        program = self.programs.get((thing_id, attachment_id))
        if program is None:
            _fail(
                "execution.unknown_attachment",
                f"unknown execution attachment {thing_id}/{attachment_id}",
            )
        if handler_id not in {handler.handler_id for handler in program.handlers}:
            _fail("execution.unknown_handler", f"unknown handler {handler_id!r}")
        if self._live_queue_count() + 1 > self.budgets.queue_entries:
            _fail("execution.queue_budget", "enqueue would exceed queue-entry budget")
        due = self.logical_tick if due_tick is None else due_tick
        if not isinstance(due, int) or isinstance(due, bool) or due < self.logical_tick:
            _fail(
                "execution.invalid_due_tick",
                "due_tick must be an integer at or after current logical time",
            )
        _validate_plain(payload_value, where="activation payload")
        self._enqueue(
            Activation(
                due, self._next_sequence(), thing_id, attachment_id,
                handler_id, deepcopy(payload_value),
            )
        )

    def _enqueue(self, activation: Activation) -> None:
        heapq.heappush(self._queue, (activation.due_tick, activation.sequence, activation))

    def _handler(self, program: IRProgram, handler_id: str) -> IRHandler:
        for handler in program.handlers:
            if handler.handler_id == handler_id:
                return handler
        _fail("execution.unknown_handler", f"handler {handler_id!r} no longer exists")

    def _eval(
        self, node: Mapping[str, Any], public_draft: dict[str, Any],
        private_draft: dict[str, Any], activation: Activation,
        tracker: _BudgetTracker, rng: random.Random,
    ) -> Any:
        tracker.instruction()
        op = node["expr"]
        if op == "literal":
            return _clone_value(node["value"], tracker)
        if op == "public":
            return _clone_value(public_draft.get(node["key"]), tracker)
        if op == "private":
            return _clone_value(private_draft.get(node["key"]), tracker)
        if op == "payload":
            value = activation.payload
            if "key" in node:
                if not isinstance(value, Mapping):
                    return None
                value = value.get(node["key"])
            return _clone_value(value, tracker)
        if op == "logical_tick":
            return self.logical_tick
        if op == "random_int":
            lower = self._eval(
                node["min"], public_draft, private_draft, activation, tracker, rng
            )
            upper = self._eval(
                node["max"], public_draft, private_draft, activation, tracker, rng
            )
            if (
                not isinstance(lower, int) or isinstance(lower, bool)
                or not isinstance(upper, int) or isinstance(upper, bool)
                or lower > upper
            ):
                _fail("execution.type_error", "random_int bounds must be ordered integers")
            return rng.randint(lower, upper)
        if op == "not":
            return not bool(
                self._eval(node["arg"], public_draft, private_draft, activation, tracker, rng)
            )
        if op == "list":
            values = [
                self._eval(child, public_draft, private_draft, activation, tracker, rng)
                for child in node["args"]
            ]
            tracker.allocation(1)
            return values
        values = [
            self._eval(child, public_draft, private_draft, activation, tracker, rng)
            for child in node["args"]
        ]
        try:
            if op == "add": return values[0] + values[1]
            if op == "sub": return values[0] - values[1]
            if op == "mul": return values[0] * values[1]
            if op == "div": return values[0] / values[1]
            if op == "eq": return values[0] == values[1]
            if op == "ne": return values[0] != values[1]
            if op == "lt": return values[0] < values[1]
            if op == "le": return values[0] <= values[1]
            if op == "gt": return values[0] > values[1]
            if op == "ge": return values[0] >= values[1]
            if op == "and": return all(bool(value) for value in values)
            if op == "or": return any(bool(value) for value in values)
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ExecutionError(
                "execution.expression_error", f"expression {op!r} failed: {exc}"
            ) from exc
        _fail("execution.unknown_expression", f"unknown expression {op!r}")

    def _execute_block(
        self, block: Sequence[IRInstruction], program: IRProgram,
        public_draft: dict[str, Any], private_draft: dict[str, Any],
        activation: Activation, tracker: _BudgetTracker, rng: random.Random,
        effects: list[_Effect], *, call_depth: int = 0,
    ) -> None:
        for instruction in block:
            tracker.instruction()
            op, args = instruction.op, instruction.args
            if op == "noop":
                continue
            if op in {"set_public", "set_private", "add_public", "add_private"}:
                value = self._eval(
                    args["value"], public_draft, private_draft, activation, tracker, rng
                )
                destination = public_draft if op.endswith("public") else private_draft
                if op.startswith("add_"):
                    try:
                        value = destination.get(args["key"], 0) + value
                    except TypeError as exc:
                        raise ExecutionError(
                            "execution.type_error", f"{op} requires addable values"
                        ) from exc
                destination[args["key"]] = _clone_value(value, tracker)
                continue
            if op == "emit":
                tracker.emitted_work()
                value = self._eval(
                    args["payload"], public_draft, private_draft, activation, tracker, rng
                )
                effects.append(
                    _Effect(
                        "emit",
                        EmittedWork(
                            activation.thing_id, activation.attachment_id,
                            args["event"], value, activation.sequence,
                        ),
                    )
                )
                continue
            if op == "schedule":
                tracker.timer()
                value = self._eval(
                    args["payload"], public_draft, private_draft, activation, tracker, rng
                )
                timer_id = f"{activation.thing_id}:{activation.attachment_id}:{args['timer_id']}"
                effects.append(
                    _Effect(
                        "schedule",
                        PendingTimer(
                            timer_id, self.logical_tick + args["delay"],
                            activation.thing_id, activation.attachment_id,
                            args["handler"], value,
                        ),
                    )
                )
                continue
            if op == "cancel_timer":
                timer_id = f"{activation.thing_id}:{activation.attachment_id}:{args['timer_id']}"
                effects.append(_Effect("cancel_timer", timer_id))
                continue
            if op == "request_service":
                tracker.service()
                value = self._eval(
                    args["payload"], public_draft, private_draft, activation, tracker, rng
                )
                request_id = (
                    f"{activation.thing_id}:{activation.attachment_id}:"
                    f"{args['request_id']}:{activation.sequence}"
                )
                effects.append(
                    _Effect(
                        "service",
                        ServiceRequest(
                            activation.thing_id, activation.attachment_id,
                            args["service"], value, request_id, activation.sequence,
                        ),
                    )
                )
                continue
            if op == "if":
                condition = self._eval(
                    args["condition"], public_draft, private_draft, activation, tracker, rng
                )
                branch = args["then"] if bool(condition) else args["else"]
                self._execute_block(
                    branch, program, public_draft, private_draft, activation,
                    tracker, rng, effects, call_depth=call_depth,
                )
                continue
            if op == "repeat":
                for _ in range(args["count"]):
                    tracker.instruction()
                    self._execute_block(
                        args["body"], program, public_draft, private_draft,
                        activation, tracker, rng, effects, call_depth=call_depth,
                    )
                continue
            if op == "call":
                if call_depth + 1 > self.budgets.recursion_depth:
                    _fail(
                        "execution.recursion_budget",
                        "procedure call exceeded recursion-depth budget",
                    )
                self._execute_block(
                    program.procedures[args["procedure"]], program,
                    public_draft, private_draft, activation, tracker, rng,
                    effects, call_depth=call_depth + 1,
                )
                continue
            _fail("execution.unknown_opcode", f"validated program reached unknown opcode {op!r}")

    def _preflight_effects(self, effects: Sequence[_Effect]) -> None:
        pending_ids = set(self.pending_timers)
        timer_count = len(pending_ids)
        queue_delta = 0
        emitted_delta = 0
        service_delta = 0
        for effect in effects:
            if effect.kind == "cancel_timer":
                timer_id = effect.value
                if timer_id not in pending_ids:
                    _fail(
                        "execution.unknown_timer",
                        f"cannot cancel unknown timer {timer_id!r}",
                    )
                pending_ids.remove(timer_id)
                timer_count -= 1
                queue_delta -= 1
            elif effect.kind == "schedule":
                timer = effect.value
                if timer.timer_id in pending_ids:
                    _fail(
                        "execution.duplicate_timer",
                        f"pending timer identity already exists: {timer.timer_id}",
                    )
                pending_ids.add(timer.timer_id)
                timer_count += 1
                queue_delta += 1
            elif effect.kind == "emit":
                emitted_delta += 1
                queue_delta += len(
                    self._matching_handlers(effect.value.thing_id, effect.value.event)
                )
            elif effect.kind == "service":
                service_delta += 1
        if timer_count > self.budgets.pending_timers:
            _fail(
                "execution.pending_timer_budget",
                "commit would exceed pending-timer budget",
            )
        if self._live_queue_count() + queue_delta > self.budgets.queue_entries:
            _fail("execution.queue_budget", "commit would exceed queue-entry budget")
        if len(self.emitted) + emitted_delta > self.budgets.outbox_entries:
            _fail(
                "execution.outbox_budget",
                "commit would exceed emitted-work outbox budget",
            )
        if len(self.service_requests) + service_delta > self.budgets.pending_service_requests:
            _fail(
                "execution.pending_service_budget",
                "commit would exceed pending service-request budget",
            )

    def _commit_effects(self, effects: Sequence[_Effect]) -> None:
        for effect in effects:
            if effect.kind == "cancel_timer":
                self.pending_timers.pop(effect.value, None)
            elif effect.kind == "schedule":
                timer = effect.value
                sequence = self._next_sequence()
                committed = PendingTimer(
                    timer.timer_id, timer.due_tick, timer.thing_id,
                    timer.attachment_id, timer.handler_id,
                    deepcopy(timer.payload), sequence,
                )
                self.pending_timers[committed.timer_id] = committed
                self._enqueue(
                    Activation(
                        committed.due_tick, sequence, committed.thing_id,
                        committed.attachment_id, committed.handler_id,
                        deepcopy(committed.payload), committed.timer_id,
                    )
                )
            elif effect.kind == "emit":
                emitted = effect.value
                self.emitted.append(emitted)
                for attachment_id, handler_id in self._matching_handlers(
                    emitted.thing_id, emitted.event
                ):
                    self._enqueue(
                        Activation(
                            self.logical_tick, self._next_sequence(), emitted.thing_id,
                            attachment_id, handler_id, deepcopy(emitted.payload),
                        )
                    )
            elif effect.kind == "service":
                self.service_requests.append(effect.value)

    def _run_activation(self, activation: Activation) -> None:
        state = self.states.get(activation.thing_id)
        program = self.programs.get((activation.thing_id, activation.attachment_id))
        if state is None or program is None:
            _fail("execution.stale_activation", "activation target no longer exists")
        handler = self._handler(program, activation.handler_id)
        public_draft = deepcopy(state.public_state)
        private_draft = deepcopy(state.private_by_attachment[activation.attachment_id])
        source_rng = self._rng[(activation.thing_id, activation.attachment_id)]
        staged_rng = random.Random()
        staged_rng.setstate(source_rng.getstate())
        tracker = _BudgetTracker(self.budgets)
        effects: list[_Effect] = []
        self._execute_block(
            handler.instructions, program, public_draft, private_draft,
            activation, tracker, staged_rng, effects,
        )
        self._preflight_effects(effects)
        state.public_state = public_draft
        state.private_by_attachment[activation.attachment_id] = private_draft
        source_rng.setstate(staged_rng.getstate())
        self._commit_effects(effects)

    def _pop_next_live(self, *, max_tick: int | None = None) -> Activation | None:
        while self._queue:
            due, _, activation = self._queue[0]
            if max_tick is not None and due > max_tick:
                return None
            heapq.heappop(self._queue)
            if activation.timer_id is not None:
                timer = self.pending_timers.get(activation.timer_id)
                if timer is None or timer.sequence != activation.sequence:
                    continue
                self.pending_timers.pop(activation.timer_id, None)
            self.logical_tick = max(self.logical_tick, due)
            return activation
        return None

    def _peek_live(self, *, max_tick: int | None) -> bool:
        while self._queue:
            due, _, activation = self._queue[0]
            if activation.timer_id is not None:
                timer = self.pending_timers.get(activation.timer_id)
                if timer is None or timer.sequence != activation.sequence:
                    heapq.heappop(self._queue)
                    continue
            return max_tick is None or due <= max_tick
        return False

    def _run(self, *, max_tick: int | None) -> int:
        completed = 0
        while True:
            if completed >= self.budgets.activations_per_run:
                if self._peek_live(max_tick=max_tick):
                    _fail(
                        "execution.activation_budget",
                        "run exceeded activation-count budget with work still pending",
                    )
                break
            activation = self._pop_next_live(max_tick=max_tick)
            if activation is None:
                break
            completed += 1
            try:
                self._run_activation(activation)
            except ExecutionError as exc:
                self.faults.append(ActivationFault(exc.code, str(exc), activation))
        return completed

    def run_current_tick(self) -> int:
        return self._run(max_tick=self.logical_tick)

    def advance_to(self, logical_tick: int) -> int:
        if (
            not isinstance(logical_tick, int) or isinstance(logical_tick, bool)
            or logical_tick < self.logical_tick
        ):
            _fail("execution.invalid_due_tick", "logical time cannot move backwards")
        completed = self._run(max_tick=logical_tick)
        self.logical_tick = logical_tick
        return completed

    def run_until_idle(self) -> int:
        return self._run(max_tick=None)

    def take_emitted(self) -> tuple[EmittedWork, ...]:
        rows = tuple(self.emitted)
        self.emitted.clear()
        return rows

    def take_service_requests(self) -> tuple[ServiceRequest, ...]:
        rows = tuple(self.service_requests)
        self.service_requests.clear()
        return rows
