from __future__ import annotations

import copy
import unittest

from model import BehaviorSpec, Port, Runtime, SwapError, Thing, ValidationError, compile_rule


class BehaviorExecutionTests(unittest.TestCase):
    def runtime(self, **kwargs) -> Runtime:
        return Runtime(seed=123, **kwargs)

    def test_commit_precedes_emitted_follow_on_activation(self) -> None:
        runtime = self.runtime()
        opener = BehaviorSpec(
            "opener",
            1,
            {
                "go": (
                    {"op": "set_state", "key": "open", "value": True},
                    {"op": "emit", "event": "opened"},
                )
            },
        )
        observer = BehaviorSpec(
            "observer",
            1,
            {
                "opened": (
                    {"op": "set_private", "key": "seen", "value": {"state": "open"}},
                )
            },
            {"seen": False},
            {"seen": "bool"},
        )
        for spec in (opener, observer):
            runtime.register_spec(spec)

        runtime.add_thing(Thing("door", {"open": False}))
        runtime.attach("door", "opener-slot", "opener", 1)
        observer_attachment = runtime.attach("door", "observer-slot", "observer", 1)

        runtime.dispatch("door", "go")
        runtime.run_until_idle()

        self.assertTrue(runtime.things["door"].state["open"])
        self.assertTrue(observer_attachment.private["seen"])

    def test_activation_fault_rolls_back_state_private_state_and_rng(self) -> None:
        runtime = self.runtime(instruction_budget=3)
        spec = BehaviorSpec(
            "rollback",
            1,
            {
                "go": (
                    {"op": "set_state", "key": "a", "value": 1},
                    {"op": "random_int", "key": "roll", "min": 1, "max": 100},
                    {"op": "set_private", "key": "x", "value": 2},
                    {"op": "set_state", "key": "b", "value": 3},
                ),
                "roll_only": (
                    {"op": "random_int", "key": "roll", "min": 1, "max": 100},
                ),
            },
            {"x": 0, "roll": 0},
            {"x": "int", "roll": "int"},
        )
        runtime.register_spec(spec)
        runtime.add_thing(Thing("thing", {"a": 0}))
        attachment = runtime.attach("thing", "slot", "rollback", 1)

        runtime.dispatch("thing", "go")
        runtime.run_until_idle()

        self.assertEqual(runtime.things["thing"].state, {"a": 0})
        self.assertEqual(attachment.private, {"x": 0, "roll": 0})
        self.assertEqual(runtime.faults[-1].kind, "instruction_budget_exceeded")

        runtime.instruction_budget = 10
        runtime.enqueue("thing", "slot", "roll_only")
        runtime.run_current_tick()
        first_after_rollback = attachment.private["roll"]

        fresh = self.runtime()
        fresh.register_spec(spec)
        fresh.add_thing(Thing("thing", {"a": 0}))
        fresh_attachment = fresh.attach("thing", "slot", "rollback", 1)
        fresh.enqueue("thing", "slot", "roll_only")
        fresh.run_current_tick()

        self.assertEqual(first_after_rollback, fresh_attachment.private["roll"])

    def test_logical_timer_is_deterministic(self) -> None:
        def run_once() -> tuple[dict[str, object], int]:
            runtime = self.runtime()
            spec = BehaviorSpec(
                "timer",
                1,
                {
                    "start": (
                        {"op": "schedule", "delay": 3, "handler": "later", "continuation_id": "wait-3"},
                    ),
                    "later": (
                        {"op": "set_state", "key": "done", "value": True},
                    ),
                },
            )
            runtime.register_spec(spec)
            runtime.add_thing(Thing("thing", {"done": False}))
            runtime.attach("thing", "slot", "timer", 1)
            runtime.dispatch("thing", "start")
            runtime.run_current_tick()
            self.assertFalse(runtime.things["thing"].state["done"])
            runtime.advance_to(3)
            return runtime.things["thing"].state.copy(), runtime.tick

        self.assertEqual(run_once(), run_once())

    def test_random_stream_is_deterministic_and_attachment_local(self) -> None:
        spec = BehaviorSpec(
            "roller",
            1,
            {"roll": ({"op": "random_int", "key": "roll", "min": 1, "max": 100},)},
            {"roll": 0},
            {"roll": "int"},
        )

        def run(extra_attachment: bool) -> int:
            runtime = self.runtime()
            runtime.register_spec(spec)
            runtime.add_thing(Thing("thing"))
            target = runtime.attach("thing", "target-slot", "roller", 1)
            if extra_attachment:
                runtime.attach("thing", "unrelated-slot", "roller", 1)
                runtime.enqueue("thing", "unrelated-slot", "roll")
                runtime.run_current_tick()
            runtime.enqueue("thing", "target-slot", "roll")
            runtime.run_current_tick()
            return target.private["roll"]

        self.assertEqual(run(False), run(True))

    def test_service_access_requires_capability_and_returns_asynchronously(self) -> None:
        runtime = self.runtime()
        spec = BehaviorSpec(
            "service-user",
            1,
            {
                "ask": (
                    {"op": "request_service", "service": "echo", "result_handler": "done", "payload": {"payload": "x"}},
                ),
                "done": (
                    {"op": "set_private", "key": "value", "value": {"payload": "value"}},
                ),
            },
            {"value": None},
            {"value": "any"},
        )
        runtime.register_spec(spec)
        runtime.register_service("echo", lambda value: {"value": value}, "service.echo")
        runtime.add_thing(Thing("thing"))
        attachment = runtime.attach("thing", "slot", "service-user", 1)

        runtime.enqueue("thing", "slot", "ask", {"x": 7})
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].kind, "capability_denied")
        self.assertIsNone(attachment.private["value"])

        runtime.grant("thing", "slot", "service.echo")
        runtime.enqueue("thing", "slot", "ask", {"x": 9})
        runtime.run_current_tick()
        self.assertIsNone(attachment.private["value"])
        runtime.advance_to(1)
        self.assertEqual(attachment.private["value"], 9)

    def test_optional_capability_can_fail_closed_without_disabling_behaviour(self) -> None:
        runtime = self.runtime()
        spec = BehaviorSpec(
            "optional",
            1,
            {
                "go": (
                    {
                        "op": "if",
                        "condition": {"has_capability": "clipboard.write"},
                        "then": ({"op": "set_state", "key": "mode", "value": "clipboard"},),
                        "else": ({"op": "set_state", "key": "mode", "value": "local"},),
                    },
                )
            },
        )
        runtime.register_spec(spec)
        runtime.add_thing(Thing("thing", {"mode": None}))
        runtime.attach("thing", "slot", "optional", 1)
        runtime.dispatch("thing", "go")
        runtime.run_current_tick()
        self.assertEqual(runtime.things["thing"].state["mode"], "local")

    def test_event_storm_is_contained_by_per_tick_budget(self) -> None:
        runtime = self.runtime(activation_budget_per_tick=5, emit_budget=2)
        spec = BehaviorSpec("storm", 1, {"ping": ({"op": "emit", "event": "ping"},)})
        runtime.register_spec(spec)
        runtime.add_thing(Thing("thing"))
        runtime.attach("thing", "slot", "storm", 1)
        runtime.dispatch("thing", "ping")
        runtime.run_current_tick()
        self.assertEqual(runtime.faults[-1].kind, "tick_activation_budget_exceeded")
        self.assertTrue(runtime.queue)

    def test_hot_swap_with_same_schema_preserves_private_state_and_thing_identity(self) -> None:
        runtime = self.runtime()
        version1 = BehaviorSpec(
            "move", 1, {"step": ({"op": "add_private", "key": "count", "value": 1},)}, {"count": 0}, {"count": "int"}
        )
        version2 = BehaviorSpec(
            "move", 2, {"step": ({"op": "add_private", "key": "count", "value": 2},)}, {"count": 0}, {"count": "int"}
        )
        for spec in (version1, version2):
            runtime.register_spec(spec)
        thing = Thing("player")
        runtime.add_thing(thing)
        attachment = runtime.attach("player", "movement-slot", "move", 1)
        runtime.enqueue("player", "movement-slot", "step")
        runtime.run_current_tick()
        self.assertEqual(attachment.private["count"], 1)
        runtime.swap_behavior("player", "movement-slot", "move", 2)
        runtime.enqueue("player", "movement-slot", "step")
        runtime.run_current_tick()
        self.assertEqual(thing.thing_id, "player")
        self.assertEqual(attachment.private["count"], 3)

    def test_hot_swap_can_migrate_state_and_remap_pending_continuation(self) -> None:
        runtime = self.runtime()
        version1 = BehaviorSpec(
            "worker",
            1,
            {
                "start": ({"op": "schedule", "delay": 2, "handler": "resume", "continuation_id": "pending-work"},),
                "resume": ({"op": "add_private", "key": "count", "value": 1},),
            },
            {"count": 4},
            {"count": "int"},
        )
        version2 = BehaviorSpec(
            "worker", 2, {"resume-v2": ({"op": "add_private", "key": "total", "value": 2},)}, {"total": 0}, {"total": "int"}
        )
        for spec in (version1, version2):
            runtime.register_spec(spec)
        runtime.add_thing(Thing("thing"))
        attachment = runtime.attach("thing", "slot", "worker", 1)
        runtime.enqueue("thing", "slot", "start")
        runtime.run_current_tick()
        runtime.swap_behavior(
            "thing", "slot", "worker", 2,
            migration={"total": {"private": "count"}},
            continuation_map={"resume": "resume-v2"},
        )
        runtime.advance_to(2)
        self.assertEqual(attachment.private["total"], 6)

    def test_incompatible_hot_swap_is_rejected_atomically(self) -> None:
        runtime = self.runtime()
        version1 = BehaviorSpec("worker", 1, {"later": ({"op": "noop"},)}, {"x": 1}, {"x": "int"})
        version2 = BehaviorSpec("worker", 2, {"other": ({"op": "noop"},)}, {"y": 0}, {"y": "int"})
        for spec in (version1, version2):
            runtime.register_spec(spec)
        runtime.add_thing(Thing("thing"))
        attachment = runtime.attach("thing", "slot", "worker", 1)
        runtime.enqueue("thing", "slot", "later", due_tick=2, continuation_id="pending")
        queue_before = copy.deepcopy(runtime.queue)
        with self.assertRaises(SwapError):
            runtime.swap_behavior("thing", "slot", "worker", 2)
        self.assertEqual(attachment.spec.version, 1)
        self.assertEqual(attachment.private, {"x": 1})
        self.assertEqual(runtime.queue, queue_before)

    def test_beginner_rule_and_advanced_behaviour_share_one_ir_type(self) -> None:
        beginner = compile_rule(
            "beginner-rule", 1, "clicked",
            [{"op": "send", "target": "door", "command": "open"}],
            ports={"clicked": Port("event", "in"), "open": Port("command", "out")},
        )
        advanced = BehaviorSpec(
            "platform-controller",
            1,
            {
                "tick": (
                    {
                        "op": "if",
                        "condition": {"eq": [{"state": "grounded"}, True]},
                        "then": ({"op": "add_state", "key": "x", "value": 1},),
                        "else": ({"op": "noop"},),
                    },
                )
            },
        )
        beginner.validate()
        advanced.validate()
        self.assertIsInstance(beginner, BehaviorSpec)
        self.assertIsInstance(advanced, BehaviorSpec)

    def test_validator_rejects_direct_foreign_state_mutation_opcode(self) -> None:
        invalid = BehaviorSpec(
            "bad",
            1,
            {"go": ({"op": "set_other_state", "target": "other", "key": "health", "value": 0},)},
        )
        with self.assertRaises(ValidationError):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
