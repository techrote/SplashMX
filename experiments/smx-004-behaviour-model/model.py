"""Disposable SMX-004 behaviour-execution research model.

This is deliberately not production runtime code or a frozen IR encoding. It exists to
exercise the semantic invariants documented in docs/research/SMX-004-BEHAVIOUR-EXECUTION.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import copy
import hashlib
import heapq
import random
from typing import Any, Callable


class ValidationError(Exception):
    pass


class ExecutionFault(Exception):
    pass


class SwapError(Exception):
    pass


ALLOWED_OPS = {
    "set_state",
    "set_private",
    "add_state",
    "add_private",
    "emit",
    "send",
    "schedule",
    "random_int",
    "if",
    "request_service",
    "noop",
}


@dataclass(frozen=True)
class Port:
    kind: str  # command | event | value
    direction: str  # in | out | read | write | readwrite
    value_type: str = "any"


@dataclass(frozen=True)
class BehaviorSpec:
    behavior_id: str
    version: int
    handlers: dict[str, tuple[dict[str, Any], ...]]
    private_defaults: dict[str, Any] = field(default_factory=dict)
    private_schema: dict[str, str] = field(default_factory=dict)
    ports: dict[str, Port] = field(default_factory=dict)
    required_capabilities: frozenset[str] = frozenset()

    def validate(self) -> None:
        if set(self.private_defaults) - set(self.private_schema):
            raise ValidationError("private defaults must be declared by private_schema")
        for name, port in self.ports.items():
            if port.kind not in {"command", "event", "value"}:
                raise ValidationError(f"invalid port kind for {name}")
            if port.direction not in {"in", "out", "read", "write", "readwrite"}:
                raise ValidationError(f"invalid port direction for {name}")
        for handler, instructions in self.handlers.items():
            if not handler:
                raise ValidationError("handler name must be non-empty")
            if not isinstance(instructions, tuple):
                raise ValidationError("handler instructions must be tuples")
            self._validate_instructions(instructions)

    def _validate_instructions(self, instructions: tuple[dict[str, Any], ...]) -> None:
        for instruction in instructions:
            op = instruction.get("op")
            if op not in ALLOWED_OPS:
                raise ValidationError(f"unknown op {op!r}")
            if op == "if":
                self._validate_instructions(tuple(instruction.get("then", ())))
                self._validate_instructions(tuple(instruction.get("else", ())))


@dataclass
class Attachment:
    attachment_id: str
    spec: BehaviorSpec
    private: dict[str, Any]


@dataclass
class Thing:
    thing_id: str
    state: dict[str, Any] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(order=True)
class Activation:
    due_tick: int
    seq: int
    thing_id: str = field(compare=False)
    attachment_id: str = field(compare=False)
    handler: str = field(compare=False)
    payload: Any = field(compare=False, default=None)
    cause_depth: int = field(compare=False, default=0)
    continuation_id: str | None = field(compare=False, default=None)


@dataclass(frozen=True)
class Fault:
    kind: str
    thing_id: str
    attachment_id: str
    handler: str
    detail: str


class Runtime:
    def __init__(
        self,
        *,
        seed: int = 1,
        instruction_budget: int = 64,
        emit_budget: int = 16,
        activation_budget_per_tick: int = 128,
    ) -> None:
        self.seed = seed
        self.instruction_budget = instruction_budget
        self.emit_budget = emit_budget
        self.activation_budget_per_tick = activation_budget_per_tick
        self.things: dict[str, Thing] = {}
        self.specs: dict[tuple[str, int], BehaviorSpec] = {}
        self.queue: list[Activation] = []
        self.seq = 0
        self.tick = 0
        self.faults: list[Fault] = []
        self.capabilities: dict[tuple[str, str], set[str]] = {}
        self.services: dict[str, tuple[Callable[[Any], Any], str]] = {}
        self._rngs: dict[tuple[str, str], random.Random] = {}
        self._executing = False

    def register_spec(self, spec: BehaviorSpec) -> None:
        spec.validate()
        self.specs[(spec.behavior_id, spec.version)] = spec

    def add_thing(self, thing: Thing) -> None:
        self.things[thing.thing_id] = thing

    def attach(
        self,
        thing_id: str,
        attachment_id: str,
        behavior_id: str,
        version: int,
    ) -> Attachment:
        spec = self.specs[(behavior_id, version)]
        attachment = Attachment(
            attachment_id=attachment_id,
            spec=spec,
            private=copy.deepcopy(spec.private_defaults),
        )
        self.things[thing_id].attachments.append(attachment)
        return attachment

    def get_attachment(self, thing_id: str, attachment_id: str) -> Attachment:
        return next(
            item
            for item in self.things[thing_id].attachments
            if item.attachment_id == attachment_id
        )

    def grant(self, thing_id: str, attachment_id: str, capability: str) -> None:
        self.capabilities.setdefault((thing_id, attachment_id), set()).add(capability)

    def has_capability(
        self, thing_id: str, attachment_id: str, capability: str
    ) -> bool:
        return capability in self.capabilities.get((thing_id, attachment_id), set())

    def register_service(
        self,
        name: str,
        fn: Callable[[Any], Any],
        capability: str,
    ) -> None:
        self.services[name] = (fn, capability)

    def _rng(self, thing_id: str, attachment_id: str) -> random.Random:
        key = (thing_id, attachment_id)
        if key not in self._rngs:
            digest = hashlib.sha256(
                f"{self.seed}|{thing_id}|{attachment_id}".encode("utf-8")
            ).digest()
            self._rngs[key] = random.Random(int.from_bytes(digest[:8], "big"))
        return self._rngs[key]

    def enqueue(
        self,
        thing_id: str,
        attachment_id: str,
        handler: str,
        payload: Any = None,
        *,
        due_tick: int | None = None,
        depth: int = 0,
        continuation_id: str | None = None,
    ) -> None:
        self.seq += 1
        heapq.heappush(
            self.queue,
            Activation(
                self.tick if due_tick is None else due_tick,
                self.seq,
                thing_id,
                attachment_id,
                handler,
                payload,
                depth,
                continuation_id,
            ),
        )

    def dispatch(
        self,
        thing_id: str,
        handler: str,
        payload: Any = None,
        *,
        depth: int = 0,
    ) -> None:
        # Attachment order is author-visible/stable after definition/overlay reconciliation.
        for attachment in self.things[thing_id].attachments:
            if handler in attachment.spec.handlers:
                self.enqueue(
                    thing_id,
                    attachment.attachment_id,
                    handler,
                    payload,
                    depth=depth,
                )

    def _eval(
        self,
        expr: Any,
        thing: Thing,
        attachment: Attachment,
        payload: Any,
    ) -> Any:
        if not isinstance(expr, dict):
            return copy.deepcopy(expr)
        if "state" in expr:
            return thing.state.get(expr["state"])
        if "private" in expr:
            return attachment.private.get(expr["private"])
        if "payload" in expr:
            return payload.get(expr["payload"]) if isinstance(payload, dict) else None
        if "has_capability" in expr:
            return self.has_capability(
                thing.thing_id,
                attachment.attachment_id,
                expr["has_capability"],
            )
        if "eq" in expr:
            left, right = expr["eq"]
            return self._eval(left, thing, attachment, payload) == self._eval(
                right, thing, attachment, payload
            )
        if "add" in expr:
            return sum(
                self._eval(value, thing, attachment, payload)
                for value in expr["add"]
            )
        raise ExecutionFault(f"unknown expression {expr!r}")

    def _execute_activation(self, activation: Activation) -> None:
        thing = self.things[activation.thing_id]
        attachment = self.get_attachment(
            activation.thing_id, activation.attachment_id
        )
        if activation.handler not in attachment.spec.handlers:
            self.faults.append(
                Fault(
                    "missing_handler",
                    activation.thing_id,
                    activation.attachment_id,
                    activation.handler,
                    "handler unavailable",
                )
            )
            return

        state_before = copy.deepcopy(thing.state)
        private_before = copy.deepcopy(attachment.private)
        rng = self._rng(activation.thing_id, activation.attachment_id)
        rng_before = rng.getstate()
        staged: list[tuple[Any, ...]] = []
        instruction_count = 0
        emit_count = 0

        def run(instructions: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> None:
            nonlocal instruction_count, emit_count
            for instruction in instructions:
                instruction_count += 1
                if instruction_count > self.instruction_budget:
                    raise ExecutionFault("instruction_budget_exceeded")

                op = instruction["op"]
                if op == "set_state":
                    thing.state[instruction["key"]] = self._eval(
                        instruction["value"], thing, attachment, activation.payload
                    )
                elif op == "set_private":
                    attachment.private[instruction["key"]] = self._eval(
                        instruction["value"], thing, attachment, activation.payload
                    )
                elif op == "add_state":
                    thing.state[instruction["key"]] = thing.state.get(
                        instruction["key"], 0
                    ) + self._eval(
                        instruction["value"], thing, attachment, activation.payload
                    )
                elif op == "add_private":
                    attachment.private[instruction["key"]] = attachment.private.get(
                        instruction["key"], 0
                    ) + self._eval(
                        instruction["value"], thing, attachment, activation.payload
                    )
                elif op == "emit":
                    emit_count += 1
                    if emit_count > self.emit_budget:
                        raise ExecutionFault("emit_budget_exceeded")
                    staged.append(
                        (
                            "dispatch",
                            activation.thing_id,
                            instruction["event"],
                            self._eval(
                                instruction.get("payload"),
                                thing,
                                attachment,
                                activation.payload,
                            ),
                            activation.cause_depth + 1,
                        )
                    )
                elif op == "send":
                    emit_count += 1
                    if emit_count > self.emit_budget:
                        raise ExecutionFault("emit_budget_exceeded")
                    staged.append(
                        (
                            "dispatch",
                            instruction["target"],
                            instruction["command"],
                            self._eval(
                                instruction.get("payload"),
                                thing,
                                attachment,
                                activation.payload,
                            ),
                            activation.cause_depth + 1,
                        )
                    )
                elif op == "schedule":
                    staged.append(
                        (
                            "schedule",
                            activation.thing_id,
                            activation.attachment_id,
                            instruction["handler"],
                            self.tick + int(instruction["delay"]),
                            instruction.get("continuation_id"),
                            self._eval(
                                instruction.get("payload"),
                                thing,
                                attachment,
                                activation.payload,
                            ),
                            activation.cause_depth + 1,
                        )
                    )
                elif op == "random_int":
                    value = rng.randint(
                        int(instruction["min"]), int(instruction["max"])
                    )
                    target = (
                        attachment.private
                        if instruction.get("scope", "private") == "private"
                        else thing.state
                    )
                    target[instruction["key"]] = value
                elif op == "if":
                    branch = (
                        instruction.get("then", ())
                        if self._eval(
                            instruction["condition"],
                            thing,
                            attachment,
                            activation.payload,
                        )
                        else instruction.get("else", ())
                    )
                    run(branch)
                elif op == "request_service":
                    name = instruction["service"]
                    if name not in self.services:
                        raise ExecutionFault("unknown_service")
                    _, capability = self.services[name]
                    if not self.has_capability(
                        activation.thing_id,
                        activation.attachment_id,
                        capability,
                    ):
                        raise ExecutionFault("capability_denied")
                    # Host interaction is staged and occurs only after the internal
                    # activation commits. The result returns as a later activation.
                    staged.append(
                        (
                            "service_request",
                            activation.thing_id,
                            activation.attachment_id,
                            name,
                            instruction["result_handler"],
                            self._eval(
                                instruction.get("payload"),
                                thing,
                                attachment,
                                activation.payload,
                            ),
                            activation.cause_depth + 1,
                        )
                    )
                elif op == "noop":
                    pass
                else:  # Validation should make this unreachable.
                    raise ExecutionFault(f"unknown op {op!r}")

        try:
            run(attachment.spec.handlers[activation.handler])
        except ExecutionFault as exc:
            thing.state = state_before
            attachment.private = private_before
            rng.setstate(rng_before)
            self.faults.append(
                Fault(
                    str(exc),
                    activation.thing_id,
                    activation.attachment_id,
                    activation.handler,
                    str(exc),
                )
            )
            return

        # Internal writes are now committed. Observable follow-on work is enqueued
        # only after that commit, producing run-to-completion turn semantics.
        for item in staged:
            if item[0] == "dispatch":
                _, thing_id, handler, payload, depth = item
                self.dispatch(thing_id, handler, payload, depth=depth)
            elif item[0] == "schedule":
                (
                    _,
                    thing_id,
                    attachment_id,
                    handler,
                    due_tick,
                    continuation_id,
                    payload,
                    depth,
                ) = item
                self.enqueue(
                    thing_id,
                    attachment_id,
                    handler,
                    payload,
                    due_tick=due_tick,
                    depth=depth,
                    continuation_id=continuation_id,
                )
            elif item[0] == "service_request":
                (
                    _,
                    thing_id,
                    attachment_id,
                    service_name,
                    result_handler,
                    payload,
                    depth,
                ) = item
                fn, _ = self.services[service_name]
                try:
                    result = fn(payload)
                except Exception as exc:  # Host failure is an explicit external fault.
                    self.faults.append(
                        Fault(
                            "service_failure",
                            thing_id,
                            attachment_id,
                            result_handler,
                            repr(exc),
                        )
                    )
                else:
                    self.enqueue(
                        thing_id,
                        attachment_id,
                        result_handler,
                        result,
                        due_tick=self.tick + 1,
                        depth=depth,
                    )

    def run_current_tick(self) -> int:
        processed = 0
        self._executing = True
        try:
            while self.queue and self.queue[0].due_tick <= self.tick:
                if processed >= self.activation_budget_per_tick:
                    self.faults.append(
                        Fault(
                            "tick_activation_budget_exceeded",
                            "*",
                            "*",
                            "*",
                            f"tick {self.tick}",
                        )
                    )
                    break
                activation = heapq.heappop(self.queue)
                processed += 1
                self._execute_activation(activation)
        finally:
            self._executing = False
        return processed

    def advance_to(self, target_tick: int) -> None:
        while self.tick < target_tick:
            self.run_current_tick()
            self.tick += 1
        self.run_current_tick()

    def run_until_idle(self, *, max_ticks: int = 100) -> None:
        while self.queue and max_ticks > 0:
            next_tick = self.queue[0].due_tick
            if next_tick > self.tick:
                self.tick = next_tick
            before = len(self.queue)
            self.run_current_tick()
            max_ticks -= 1
            if (
                self.queue
                and self.queue[0].due_tick <= self.tick
                and len(self.queue) >= before
                and self.faults
                and self.faults[-1].kind == "tick_activation_budget_exceeded"
            ):
                break

    def swap_behavior(
        self,
        thing_id: str,
        attachment_id: str,
        new_behavior_id: str,
        new_version: int,
        *,
        migration: dict[str, Any] | None = None,
        continuation_map: dict[str, str] | None = None,
        cancel_pending: bool = False,
    ) -> None:
        """Plan and atomically commit a behaviour replacement at a quiescent point."""
        if self._executing:
            raise SwapError("swap only at a quiescent boundary")

        attachment = self.get_attachment(thing_id, attachment_id)
        new_spec = self.specs[(new_behavior_id, new_version)]
        old_spec = attachment.spec

        planned_queue: list[Activation] = []
        for queued in self.queue:
            candidate = queued
            if (
                queued.thing_id == thing_id
                and queued.attachment_id == attachment_id
                and queued.due_tick >= self.tick
            ):
                mapped = (continuation_map or {}).get(
                    queued.handler,
                    queued.handler if queued.handler in new_spec.handlers else None,
                )
                if mapped is None:
                    if cancel_pending:
                        continue
                    raise SwapError(
                        f"pending continuation {queued.handler!r} is incompatible"
                    )
                candidate = replace(queued, handler=mapped)
            planned_queue.append(candidate)

        if old_spec.private_schema == new_spec.private_schema:
            planned_private = copy.deepcopy(attachment.private)
            for key, value in new_spec.private_defaults.items():
                planned_private.setdefault(key, copy.deepcopy(value))
        elif migration is not None:
            planned_private = {
                key: self._eval(expr, self.things[thing_id], attachment, None)
                for key, expr in migration.items()
            }
            for key, value in new_spec.private_defaults.items():
                planned_private.setdefault(key, copy.deepcopy(value))
            if set(planned_private) != set(new_spec.private_schema):
                raise SwapError("migration does not produce the new private schema")
        else:
            raise SwapError("private state schema is incompatible")

        attachment.spec = new_spec
        attachment.private = planned_private
        self.queue = planned_queue
        heapq.heapify(self.queue)


def compile_rule(
    behavior_id: str,
    version: int,
    trigger: str,
    actions: list[dict[str, Any]],
    *,
    private_defaults: dict[str, Any] | None = None,
    private_schema: dict[str, str] | None = None,
    ports: dict[str, Port] | None = None,
) -> BehaviorSpec:
    """Compile a beginner rule into the same research IR used by advanced behaviours."""
    return BehaviorSpec(
        behavior_id=behavior_id,
        version=version,
        handlers={trigger: tuple(actions)},
        private_defaults=private_defaults or {},
        private_schema=private_schema or {},
        ports=ports or {},
    )
