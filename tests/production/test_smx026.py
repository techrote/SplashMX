from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ThingId,
    ThingRecord,
)
from splashmx.execution.ir import (  # noqa: E402
    BudgetLimits,
    ExecutionError,
    ExecutionRuntime,
    IRHandler,
    IRInstruction,
    IRProgram,
    compile_rule,
    literal,
    payload,
    private,
    public,
)


def tid(value: str) -> ThingId:
    return ThingId(value)


def aid(value: str) -> BehaviourAttachmentId:
    return BehaviourAttachmentId(value)


def ins(op: str, **args) -> IRInstruction:
    return IRInstruction(op, args)


def handler(handler_id: str, trigger: str, *rows: IRInstruction) -> IRHandler:
    return IRHandler(handler_id, trigger, tuple(rows))


def document_with(bindings: list[tuple[str, str]], state=None) -> CanonicalDocument:
    document = CanonicalDocument(ProjectId("project-execution"), ProjectRevisionId("r0"))
    behaviours = {
        aid(slot): BehaviourAttachmentRecord(aid(slot), revision)
        for slot, revision in bindings
    }
    document.things[tid("thing")] = ThingRecord(
        tid("thing"), "Thing", authored_state=state or {}, behaviours=behaviours
    )
    return document


def advanced_program(revision: str = "advanced:1") -> IRProgram:
    return IRProgram(
        revision,
        (
            handler(
                "start",
                "start",
                ins("set_private", key="count", value=literal(0)),
                ins("repeat", count=3, body=(ins("call", procedure="increment"),)),
                ins("set_public", key="result", value=private("count")),
                ins(
                    "schedule",
                    timer_id="finish",
                    delay=2,
                    handler="finish",
                    payload=public("result"),
                ),
            ),
            handler("finish", "finish", ins("emit", event="done", payload=payload())),
        ),
        procedures={
            "increment": (ins("add_private", key="count", value=literal(1)),)
        },
        private_defaults={"count": 0},
    )


class SMX026ExecutionTests(unittest.TestCase):
    def test_beginner_rule_and_advanced_behaviour_share_ir_program_and_executor(self):
        rule = compile_rule(
            "click",
            "clicked",
            [
                {"action": "add_public", "key": "clicks", "value": 1},
                {"action": "emit", "event": "changed", "payload": {"public": "clicks"}},
            ],
            behaviour_revision="rule:1",
        )
        advanced = advanced_program()
        self.assertIsInstance(rule, IRProgram)
        self.assertIsInstance(advanced, IRProgram)
        document = document_with(
            [("rule-slot", "rule:1"), ("advanced-slot", "advanced:1")],
            {"clicks": 0},
        )
        runtime = ExecutionRuntime.from_document(
            document,
            {"rule:1": rule, "advanced:1": advanced},
            attachment_order={
                tid("thing"): (aid("rule-slot"), aid("advanced-slot"))
            },
        )
        runtime.dispatch(tid("thing"), "clicked")
        runtime.run_current_tick()
        self.assertEqual(runtime.states[tid("thing")].public_state["clicks"], 1)
        runtime.dispatch(tid("thing"), "start")
        runtime.run_current_tick()
        self.assertEqual(runtime.states[tid("thing")].public_state["result"], 3)
        self.assertIn("thing:advanced-slot:finish", runtime.pending_timers)
        runtime.advance_to(2)
        self.assertIn("done", [row.event for row in runtime.emitted])

    def test_beginner_condition_compiles_to_common_if_ir(self):
        rule = compile_rule(
            "conditional",
            "tick",
            [{"action": "set_public", "key": "mode", "value": "active"}],
            condition={"eq": [{"public": "enabled"}, True]},
            behaviour_revision="rule:conditional:1",
        )
        self.assertEqual(rule.source_kind, "rule")
        self.assertEqual(rule.handlers[0].instructions[0].op, "if")
        document = document_with(
            [("slot", "rule:conditional:1")], {"enabled": False, "mode": "idle"}
        )
        runtime = ExecutionRuntime.from_document(
            document, {"rule:conditional:1": rule}
        )
        runtime.dispatch(tid("thing"), "tick")
        runtime.run_current_tick()
        self.assertEqual(runtime.states[tid("thing")].public_state["mode"], "idle")

    def test_commit_precedes_follow_on_event_activation(self):
        opener = IRProgram(
            "opener:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="open", value=literal(True)),
                    ins("emit", event="opened", payload=literal(None)),
                ),
            ),
        )
        observer = IRProgram(
            "observer:1",
            (
                handler(
                    "seen",
                    "opened",
                    ins("set_private", key="seen", value=public("open")),
                ),
            ),
            private_defaults={"seen": False},
        )
        document = document_with(
            [("opener", "opener:1"), ("observer", "observer:1")],
            {"open": False},
        )
        runtime = ExecutionRuntime.from_document(
            document,
            {"opener:1": opener, "observer:1": observer},
            attachment_order={tid("thing"): (aid("opener"), aid("observer"))},
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertTrue(
            runtime.states[tid("thing")].private_by_attachment[aid("observer")]["seen"]
        )

    def test_handler_declaration_order_is_observable_and_stable(self):
        program = IRProgram(
            "ordered:1",
            (
                handler("first", "go", ins("set_public", key="value", value=literal(7))),
                handler("second", "go", ins("set_private", key="seen", value=public("value"))),
            ),
            private_defaults={"seen": 0},
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "ordered:1")], {"value": 0}),
            {"ordered:1": program},
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(
            runtime.states[tid("thing")].private_by_attachment[aid("slot")]["seen"], 7
        )

    def test_attachment_order_must_be_explicit_and_is_not_uuid_or_lexical_order(self):
        first = IRProgram(
            "first:1", (handler("go", "go", ins("emit", event="one", payload=literal(1))),)
        )
        second = IRProgram(
            "second:1", (handler("go", "go", ins("emit", event="two", payload=literal(2))),)
        )
        document = document_with(
            [("z-first", "first:1"), ("a-second", "second:1")]
        )
        with self.assertRaises(ExecutionError) as caught:
            ExecutionRuntime.from_document(
                document, {"first:1": first, "second:1": second}
            )
        self.assertEqual(caught.exception.code, "execution.attachment_order_required")
        runtime = ExecutionRuntime.from_document(
            document,
            {"first:1": first, "second:1": second},
            attachment_order={
                tid("thing"): (aid("z-first"), aid("a-second"))
            },
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual([row.event for row in runtime.emitted[:2]], ["one", "two"])

    def test_invalid_attachment_order_is_rejected_before_launch(self):
        program = IRProgram("p:1", (handler("go", "go", ins("noop")),))
        document = document_with([("a", "p:1"), ("b", "p:1")])
        with self.assertRaises(ExecutionError) as caught:
            ExecutionRuntime.from_document(
                document,
                {"p:1": program},
                attachment_order={tid("thing"): (aid("a"), aid("a"))},
            )
        self.assertEqual(caught.exception.code, "execution.invalid_attachment_order")

    def test_exact_behaviour_revision_is_required(self):
        document = document_with([("slot", "missing:7")])
        with self.assertRaises(ExecutionError) as caught:
            ExecutionRuntime.from_document(document, {})
        self.assertEqual(caught.exception.code, "execution.missing_program")

    def test_runtime_play_state_does_not_mutate_canonical_authored_document(self):
        program = IRProgram(
            "p:1",
            (handler("go", "go", ins("set_public", key="x", value=literal(9))),),
        )
        document = document_with([("slot", "p:1")], {"x": 1})
        snapshot = copy.deepcopy(document)
        runtime = ExecutionRuntime.from_document(document, {"p:1": program})
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.states[tid("thing")].public_state["x"], 9)
        self.assertEqual(document, snapshot)

    def test_private_state_is_owned_by_attachment_not_shared_behaviour_revision(self):
        program = IRProgram(
            "counter:1",
            (handler("go", "go", ins("add_private", key="count", value=literal(1))),),
            private_defaults={"count": 0},
        )
        document = document_with(
            [("first", "counter:1"), ("second", "counter:1")]
        )
        runtime = ExecutionRuntime.from_document(
            document,
            {"counter:1": program},
            attachment_order={tid("thing"): (aid("first"), aid("second"))},
        )
        runtime.enqueue_handler(tid("thing"), aid("first"), "go")
        runtime.run_current_tick()
        private_state = runtime.states[tid("thing")].private_by_attachment
        self.assertEqual(private_state[aid("first")]["count"], 1)
        self.assertEqual(private_state[aid("second")]["count"], 0)

    def test_fault_rolls_back_public_private_effects_and_random_stream(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="x", value=literal(1)),
                    ins(
                        "set_private",
                        key="roll",
                        value={
                            "expr": "random_int",
                            "min": literal(1),
                            "max": literal(100),
                        },
                    ),
                    ins("emit", event="x", payload=literal(1)),
                    ins("repeat", count=100, body=(ins("noop"),)),
                ),
                handler(
                    "roll",
                    "roll",
                    ins(
                        "set_private",
                        key="roll",
                        value={
                            "expr": "random_int",
                            "min": literal(1),
                            "max": literal(100),
                        },
                    ),
                ),
            ),
            private_defaults={"roll": 0},
        )
        document = document_with([("slot", "p:1")], {"x": 0})
        runtime = ExecutionRuntime.from_document(
            document,
            {"p:1": program},
            budgets=BudgetLimits(instruction_steps=12),
            seed=7,
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.states[tid("thing")].public_state["x"], 0)
        self.assertEqual(runtime.emitted, [])
        self.assertEqual(runtime.faults[-1].code, "execution.instruction_budget")
        runtime.budgets = BudgetLimits(instruction_steps=100)
        runtime.dispatch(tid("thing"), "roll")
        runtime.run_current_tick()
        roll_after_fault = runtime.states[tid("thing")].private_by_attachment[aid("slot")]["roll"]
        fresh = ExecutionRuntime.from_document(
            document,
            {"p:1": program},
            budgets=BudgetLimits(instruction_steps=100),
            seed=7,
        )
        fresh.dispatch(tid("thing"), "roll")
        fresh.run_current_tick()
        self.assertEqual(
            roll_after_fault,
            fresh.states[tid("thing")].private_by_attachment[aid("slot")]["roll"],
        )

    def _fault_for(self, program: IRProgram, budgets: BudgetLimits) -> ExecutionRuntime:
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", program.behaviour_revision)]),
            {program.behaviour_revision: program},
            budgets=budgets,
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        return runtime

    def test_instruction_cpu_proxy_budget_is_independent(self):
        program = IRProgram(
            "p:1",
            (handler("go", "go", ins("repeat", count=100, body=(ins("noop"),))),),
        )
        runtime = self._fault_for(program, BudgetLimits(instruction_steps=8))
        self.assertEqual(runtime.faults[-1].code, "execution.instruction_budget")

    def test_recursion_budget_is_independent(self):
        program = IRProgram(
            "p:1",
            (handler("go", "go", ins("call", procedure="recurse")),),
            procedures={"recurse": (ins("call", procedure="recurse"),)},
        )
        runtime = self._fault_for(
            program, BudgetLimits(recursion_depth=3, instruction_steps=100)
        )
        self.assertEqual(runtime.faults[-1].code, "execution.recursion_budget")

    def test_allocation_budget_is_independent(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins(
                        "set_private",
                        key="value",
                        value={
                            "expr": "list",
                            "args": [literal("a"), literal("b"), literal("c")],
                        },
                    ),
                ),
            ),
        )
        runtime = self._fault_for(
            program, BudgetLimits(allocations=2, instruction_steps=100)
        )
        self.assertEqual(runtime.faults[-1].code, "execution.allocation_budget")

    def test_emitted_work_budget_is_independent_and_rolls_back_all_effects(self):
        rows = tuple(
            ins("emit", event=f"event-{index}", payload=literal(index))
            for index in range(3)
        )
        program = IRProgram("p:1", (IRHandler("go", "go", rows),))
        runtime = self._fault_for(
            program, BudgetLimits(emitted_work=2, instruction_steps=100)
        )
        self.assertEqual(runtime.faults[-1].code, "execution.emitted_work_budget")
        self.assertEqual(runtime.emitted, [])

    def test_timer_creation_budget_is_independent_and_rolls_back(self):
        rows = tuple(
            ins(
                "schedule",
                timer_id=f"timer-{index}",
                delay=1,
                handler="later",
                payload=literal(index),
            )
            for index in range(3)
        )
        program = IRProgram(
            "p:1", (IRHandler("go", "go", rows), handler("later", "later", ins("noop")))
        )
        runtime = self._fault_for(
            program, BudgetLimits(timers_per_activation=2, instruction_steps=100)
        )
        self.assertEqual(runtime.faults[-1].code, "execution.timer_budget")
        self.assertEqual(runtime.pending_timers, {})

    def test_pending_timer_budget_is_checked_before_state_commit(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="changed", value=literal(True)),
                    ins("schedule", timer_id="a", delay=1, handler="later", payload=literal(1)),
                    ins("schedule", timer_id="b", delay=1, handler="later", payload=literal(2)),
                ),
                handler("later", "later", ins("noop")),
            ),
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "p:1")], {"changed": False}),
            {"p:1": program},
            budgets=BudgetLimits(
                timers_per_activation=10, pending_timers=1, instruction_steps=100
            ),
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].code, "execution.pending_timer_budget")
        self.assertFalse(runtime.states[tid("thing")].public_state["changed"])
        self.assertEqual(runtime.pending_timers, {})

    def test_queue_budget_is_checked_before_state_commit(self):
        emitter = IRProgram(
            "emitter:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="x", value=literal(1)),
                    ins("emit", event="fan", payload=literal(None)),
                ),
                handler("fan-self", "fan", ins("noop")),
            ),
        )
        second = IRProgram(
            "second:1", (handler("fan-second", "fan", ins("noop")),)
        )
        third = IRProgram(
            "third:1", (handler("fan-third", "fan", ins("noop")),)
        )
        runtime = ExecutionRuntime.from_document(
            document_with(
                [("emitter", "emitter:1"), ("second", "second:1"), ("third", "third:1")],
                {"x": 0},
            ),
            {"emitter:1": emitter, "second:1": second, "third:1": third},
            attachment_order={
                tid("thing"): (aid("emitter"), aid("second"), aid("third"))
            },
            budgets=BudgetLimits(queue_entries=2, instruction_steps=100),
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].code, "execution.queue_budget")
        self.assertEqual(runtime.states[tid("thing")].public_state["x"], 0)

    def test_service_request_budget_is_independent(self):
        rows = tuple(
            ins(
                "request_service",
                service="echo",
                request_id=f"request-{index}",
                payload=literal(index),
            )
            for index in range(3)
        )
        runtime = self._fault_for(
            IRProgram("p:1", (IRHandler("go", "go", rows),)),
            BudgetLimits(service_requests=2, instruction_steps=100),
        )
        self.assertEqual(runtime.faults[-1].code, "execution.service_request_budget")
        self.assertEqual(runtime.service_requests, [])

    def test_pending_service_budget_rolls_back_before_publication(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="changed", value=literal(True)),
                    ins("request_service", service="echo", request_id="a", payload=literal(1)),
                    ins("request_service", service="echo", request_id="b", payload=literal(2)),
                ),
            ),
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "p:1")], {"changed": False}),
            {"p:1": program},
            budgets=BudgetLimits(
                service_requests=10, pending_service_requests=1, instruction_steps=100
            ),
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].code, "execution.pending_service_budget")
        self.assertFalse(runtime.states[tid("thing")].public_state["changed"])
        self.assertEqual(runtime.service_requests, [])

    def test_activation_event_storm_terminates_under_deterministic_run_budget(self):
        program = IRProgram(
            "storm:1",
            (handler("go", "go", ins("emit", event="go", payload=literal(None))),),
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "storm:1")]),
            {"storm:1": program},
            budgets=BudgetLimits(activations_per_run=5, instruction_steps=100),
        )
        runtime.dispatch(tid("thing"), "go")
        with self.assertRaises(ExecutionError) as caught:
            runtime.run_current_tick()
        self.assertEqual(caught.exception.code, "execution.activation_budget")
        self.assertGreater(runtime.queue_depth, 0)

    def test_unknown_required_opcode_fails_closed_before_launch(self):
        program = IRProgram(
            "p:1", (handler("go", "go", IRInstruction("future-op", {})),)
        )
        with self.assertRaises(ExecutionError) as caught:
            program.validate()
        self.assertEqual(caught.exception.code, "execution.unknown_opcode")

    def test_raw_host_and_foreign_state_opcodes_fail_closed_before_launch(self):
        for opcode in ("gdscript", "javascript", "host_call", "set_other_state", "raw_socket"):
            with self.subTest(opcode=opcode):
                program = IRProgram(
                    "p:1", (handler("go", "go", IRInstruction(opcode, {})),)
                )
                with self.assertRaises(ExecutionError) as caught:
                    program.validate()
                self.assertEqual(caught.exception.code, "execution.forbidden_opcode")

    def test_unknown_ir_version_is_typed_failure(self):
        program = IRProgram(
            "p:1",
            (handler("go", "go", ins("noop")),),
            ir_version="splashmx.behaviour-ir/999",
        )
        with self.assertRaises(ExecutionError) as caught:
            program.validate()
        self.assertEqual(caught.exception.code, "execution.unsupported_ir_version")

    def test_nested_transient_authority_literal_is_rejected(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins(
                        "set_public",
                        key="x",
                        value=literal({"safe": {"transport_peer_id": 7}}),
                    ),
                ),
            ),
        )
        with self.assertRaises(ExecutionError) as caught:
            program.validate()
        self.assertEqual(caught.exception.code, "execution.forbidden_transient_identity")

    def test_nested_transient_authority_external_payload_is_rejected(self):
        program = IRProgram("p:1", (handler("go", "go", ins("noop")),))
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "p:1")]), {"p:1": program}
        )
        with self.assertRaises(ExecutionError) as caught:
            runtime.dispatch(
                tid("thing"), "go", {"outer": {"capability_token": "forged"}}
            )
        self.assertEqual(caught.exception.code, "execution.forbidden_transient_identity")
        self.assertEqual(runtime.queue_depth, 0)

    def test_service_opcode_only_emits_mediated_request_and_never_invokes_host(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins(
                        "request_service",
                        service="clipboard.write",
                        request_id="copy",
                        payload=literal("hello"),
                    ),
                ),
            ),
        )
        runtime = self._fault_for(program, BudgetLimits(instruction_steps=100))
        self.assertFalse(runtime.faults)
        self.assertEqual(runtime.service_requests[0].service, "clipboard.write")
        self.assertEqual(runtime.service_requests[0].payload, "hello")

    def test_timer_is_explicit_pending_work_and_can_be_cancelled(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins(
                        "schedule",
                        timer_id="wake",
                        delay=3,
                        handler="later",
                        payload=literal({"v": 1}),
                    ),
                ),
                handler("cancel", "cancel", ins("cancel_timer", timer_id="wake")),
                handler(
                    "later",
                    "later",
                    ins("set_public", key="done", value=literal(True)),
                ),
            ),
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "p:1")], {"done": False}), {"p:1": program}
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        timer = runtime.pending_timers["thing:slot:wake"]
        self.assertEqual(
            (timer.due_tick, str(timer.thing_id), str(timer.attachment_id), timer.handler_id),
            (3, "thing", "slot", "later"),
        )
        runtime.dispatch(tid("thing"), "cancel")
        runtime.run_current_tick()
        self.assertEqual(runtime.pending_timers, {})
        runtime.advance_to(3)
        self.assertFalse(runtime.states[tid("thing")].public_state["done"])

    def test_duplicate_timer_identity_fault_is_atomic(self):
        program = IRProgram(
            "p:1",
            (
                handler(
                    "go",
                    "go",
                    ins("set_public", key="changed", value=literal(True)),
                    ins("schedule", timer_id="same", delay=1, handler="later", payload=literal(1)),
                    ins("schedule", timer_id="same", delay=2, handler="later", payload=literal(2)),
                ),
                handler("later", "later", ins("noop")),
            ),
        )
        runtime = ExecutionRuntime.from_document(
            document_with([("slot", "p:1")], {"changed": False}), {"p:1": program}
        )
        runtime.dispatch(tid("thing"), "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].code, "execution.duplicate_timer")
        self.assertFalse(runtime.states[tid("thing")].public_state["changed"])
        self.assertEqual(runtime.pending_timers, {})

    def test_same_inputs_seed_and_program_produce_same_trace(self):
        program = advanced_program()
        document = document_with([("slot", "advanced:1")], {"result": 0})

        def once():
            runtime = ExecutionRuntime.from_document(
                copy.deepcopy(document), {"advanced:1": program}, seed=99
            )
            runtime.dispatch(tid("thing"), "start", {"x": 1})
            runtime.run_until_idle()
            return (
                runtime.states,
                runtime.emitted,
                runtime.logical_tick,
                runtime.faults,
            )

        self.assertEqual(once(), once())


if __name__ == "__main__":
    unittest.main()
