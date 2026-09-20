from __future__ import annotations

import copy
import unittest

from splashmx.canonical.core import (
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ThingId,
    ThingRecord,
)
from splashmx.execution.hotswap import (
    HandlerMigration,
    PendingWorkMigration,
    PrivateStateMigration,
    ReplacementContract,
    ReplacementError,
    principal_for_attachment,
    replace_behaviour,
)
from splashmx.execution.ir import (
    ExecutionRuntime,
    IRHandler,
    IRInstruction,
    IRProgram,
    expression,
    literal,
    private,
)
from splashmx.security.capabilities import (
    CapabilityBroker,
    CapabilityId,
    CapabilityRequirement,
    CapabilityScope,
)


def tid(value: str = "thing") -> ThingId:
    return ThingId(value)


def aid(value: str = "slot") -> BehaviourAttachmentId:
    return BehaviourAttachmentId(value)


def ins(op: str, **args) -> IRInstruction:
    return IRInstruction(op, args)


def handler(handler_id: str, trigger: str, *rows: IRInstruction) -> IRHandler:
    return IRHandler(handler_id, trigger, tuple(rows))


def old_program() -> IRProgram:
    return IRProgram(
        "worker:1",
        (
            handler("step", "step", ins("add_private", key="count", value=literal(1))),
            handler(
                "start",
                "start",
                ins("schedule", timer_id="wait", delay=2, handler="resume", payload=literal({"n": 1})),
            ),
            handler("resume", "resume", ins("add_private", key="count", value=literal(1))),
            handler(
                "ask",
                "ask",
                ins("request_service", service="network.http", request_id="r", payload=literal({"origin": "https://api.example.com"})),
            ),
            handler("emit", "emit", ins("emit", event="committed", payload=literal(7))),
            handler(
                "roll",
                "roll",
                ins(
                    "set_private",
                    key="roll",
                    value={"expr": "random_int", "min": literal(1), "max": literal(1000)},
                ),
            ),
        ),
        private_defaults={"count": 4, "roll": 0},
    )


def new_program() -> IRProgram:
    return IRProgram(
        "worker:2",
        (
            handler("step-v2", "step", ins("add_private", key="total", value=literal(2))),
            handler("resume-v2", "resume", ins("add_private", key="total", value=literal(2))),
            handler("ask-v2", "ask", ins("noop")),
            handler(
                "roll-v2",
                "roll",
                ins(
                    "set_private",
                    key="roll",
                    value={"expr": "random_int", "min": literal(1), "max": literal(1000)},
                ),
            ),
        ),
        private_defaults={"total": 0, "mode": "v2", "roll": 0},
    )


def runtime_for(program: IRProgram | None = None) -> ExecutionRuntime:
    program = program or old_program()
    document = CanonicalDocument(ProjectId("project"), ProjectRevisionId("r1"))
    document.things[tid()] = ThingRecord(
        tid(),
        "Thing",
        authored_state={"public": 9},
        behaviours={aid(): BehaviourAttachmentRecord(aid(), program.behaviour_revision)},
    )
    return ExecutionRuntime.from_document(document, {program.behaviour_revision: program}, seed=123)


def migrate_contract(*, pending: PendingWorkMigration | None = None, requirements=()) -> ReplacementContract:
    return ReplacementContract(
        "worker-1-to-2",
        "worker:1",
        "worker:2",
        private_state=PrivateStateMigration(
            "migrate",
            field_map={"total": "count", "roll": "roll"},
            literals={"mode": "v2"},
        ),
        pending_work=pending or PendingWorkMigration(),
        capability_requirements=tuple(requirements),
    )


def snapshot(runtime: ExecutionRuntime):
    key = (tid(), aid())
    return (
        runtime.programs[key].behaviour_revision,
        copy.deepcopy(runtime.states[tid()].public_state),
        copy.deepcopy(runtime.states[tid()].private_by_attachment[aid()]),
        copy.deepcopy(runtime.pending_timers),
        copy.deepcopy(runtime._queue),
        copy.deepcopy(runtime.service_requests),
        runtime._rng[key].getstate(),
    )


class SMX028HotReplacementTests(unittest.TestCase):
    def test_compatible_preserve_keeps_thing_attachment_state_object_and_private_state(self):
        runtime = runtime_for()
        state_object = runtime.states[tid()]
        private_before = copy.deepcopy(state_object.private_by_attachment[aid()])
        contract = ReplacementContract(
            "preserve-compatible", "worker:1", "worker:2",
            private_state=PrivateStateMigration("preserve"),
        )
        result = replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertIs(runtime.states[tid()], state_object)
        self.assertIn(aid(), runtime.attachment_order[tid()])
        self.assertEqual(runtime.states[tid()].private_by_attachment[aid()], private_before)
        self.assertEqual(runtime.states[tid()].public_state, {"public": 9})
        self.assertEqual(runtime.programs[(tid(), aid())].behaviour_revision, "worker:2")
        self.assertEqual((result.thing_id, result.attachment_id), (tid(), aid()))

    def test_schema_migration_is_explicit_and_uses_target_defaults(self):
        runtime = runtime_for()
        runtime.states[tid()].private_by_attachment[aid()]["count"] = 11
        replace_behaviour(runtime, tid(), aid(), new_program(), migrate_contract())
        self.assertEqual(
            runtime.states[tid()].private_by_attachment[aid()],
            {"total": 11, "mode": "v2", "roll": 0},
        )

    def test_unaccounted_old_private_field_rejects_atomically(self):
        runtime = runtime_for()
        runtime.states[tid()].private_by_attachment[aid()]["legacy"] = 99
        before = snapshot(runtime)
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), migrate_contract())
        self.assertEqual(caught.exception.code, "replacement.unmapped_private_state")
        self.assertEqual(snapshot(runtime), before)

    def test_explicit_private_drop_is_allowed_but_never_implicit(self):
        runtime = runtime_for()
        runtime.states[tid()].private_by_attachment[aid()]["legacy"] = 99
        contract = ReplacementContract(
            "drop-legacy", "worker:1", "worker:2",
            private_state=PrivateStateMigration(
                "migrate",
                field_map={"total": "count", "roll": "roll"},
                literals={"mode": "v2"},
                drop_source_keys=frozenset({"legacy"}),
            ),
        )
        replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertNotIn("legacy", runtime.states[tid()].private_by_attachment[aid()])

    def test_bad_migration_source_rejects_without_partial_publication(self):
        runtime = runtime_for()
        before = snapshot(runtime)
        contract = ReplacementContract(
            "bad-map", "worker:1", "worker:2",
            private_state=PrivateStateMigration(
                "migrate", field_map={"total": "missing", "roll": "roll"},
                literals={"mode": "v2"}, drop_source_keys=frozenset({"count"}),
            ),
        )
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertEqual(caught.exception.code, "replacement.invalid_state_migration")
        self.assertEqual(snapshot(runtime), before)

    def test_exact_source_and_target_revisions_are_required(self):
        runtime = runtime_for()
        before = snapshot(runtime)
        wrong_source = ReplacementContract("wrong-source", "worker:0", "worker:2")
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), wrong_source)
        self.assertEqual(caught.exception.code, "replacement.source_revision_mismatch")
        self.assertEqual(snapshot(runtime), before)

        wrong_target = ReplacementContract("wrong-target", "worker:1", "worker:3")
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), wrong_target)
        self.assertEqual(caught.exception.code, "replacement.target_revision_mismatch")
        self.assertEqual(snapshot(runtime), before)

    def test_invalid_target_ir_fails_before_state_migration(self):
        runtime = runtime_for()
        before = snapshot(runtime)
        bad = IRProgram(
            "worker:2",
            (handler("bad", "bad", ins("host_call", target="raw")),),
        )
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), bad, migrate_contract())
        self.assertEqual(caught.exception.code, "replacement.invalid_target")
        self.assertEqual(snapshot(runtime), before)

    def test_pending_timer_requires_explicit_map_or_cancel(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "start")
        runtime.run_current_tick()
        before = snapshot(runtime)
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), migrate_contract())
        self.assertEqual(caught.exception.code, "replacement.pending_work_undeclared")
        self.assertEqual(snapshot(runtime), before)

    def test_pending_timer_maps_handler_without_changing_due_identity_or_payload(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "start")
        runtime.run_current_tick()
        timer_before = next(iter(runtime.pending_timers.values()))
        contract = migrate_contract(
            pending=PendingWorkMigration({"resume": HandlerMigration.map_to("resume-v2")})
        )
        outcome = replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        timer_after = runtime.pending_timers[timer_before.timer_id]
        self.assertEqual(timer_after.timer_id, timer_before.timer_id)
        self.assertEqual(timer_after.due_tick, timer_before.due_tick)
        self.assertEqual(timer_after.sequence, timer_before.sequence)
        self.assertEqual(timer_after.payload, timer_before.payload)
        self.assertEqual(timer_after.handler_id, "resume-v2")
        self.assertEqual(outcome.mapped_work, 1)
        runtime.advance_to(2)
        self.assertEqual(runtime.states[tid()].private_by_attachment[aid()]["total"], 6)

    def test_pending_timer_can_be_explicitly_cancelled(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "start")
        runtime.run_current_tick()
        outcome = replace_behaviour(
            runtime, tid(), aid(), new_program(),
            migrate_contract(pending=PendingWorkMigration({"resume": HandlerMigration.cancel()})),
        )
        self.assertEqual(runtime.pending_timers, {})
        self.assertEqual(outcome.cancelled_work, 1)
        self.assertEqual(runtime.advance_to(2), 0)
        self.assertEqual(runtime.states[tid()].private_by_attachment[aid()]["total"], 4)

    def test_queued_non_timer_continuation_is_mapped_explicitly(self):
        runtime = runtime_for()
        runtime.enqueue_handler(tid(), aid(), "resume", {"k": 1}, due_tick=3)
        contract = migrate_contract(
            pending=PendingWorkMigration({"resume": HandlerMigration.map_to("resume-v2")})
        )
        replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        live = [row[2] for row in runtime._queue if row[2].timer_id is None]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0].handler_id, "resume-v2")
        self.assertEqual(live[0].due_tick, 3)
        runtime.advance_to(3)
        self.assertEqual(runtime.states[tid()].private_by_attachment[aid()]["total"], 6)

    def test_mapping_to_missing_target_handler_rejects_atomically(self):
        runtime = runtime_for()
        runtime.enqueue_handler(tid(), aid(), "resume", due_tick=3)
        before = snapshot(runtime)
        contract = migrate_contract(
            pending=PendingWorkMigration({"resume": HandlerMigration.map_to("does-not-exist")})
        )
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertEqual(caught.exception.code, "replacement.pending_target_missing")
        self.assertEqual(snapshot(runtime), before)

    def test_pending_service_request_requires_explicit_preserve_or_cancel(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "ask")
        runtime.run_current_tick()
        before = snapshot(runtime)
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), migrate_contract())
        self.assertEqual(caught.exception.code, "replacement.pending_service_undeclared")
        self.assertEqual(snapshot(runtime), before)

        preserve = migrate_contract(pending=PendingWorkMigration(service_requests="preserve"))
        outcome = replace_behaviour(runtime, tid(), aid(), new_program(), preserve)
        self.assertEqual(len(runtime.service_requests), 1)
        self.assertEqual(outcome.preserved_service_requests, 1)

    def test_pending_service_request_can_be_explicitly_cancelled(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "ask")
        runtime.run_current_tick()
        contract = migrate_contract(pending=PendingWorkMigration(service_requests="cancel"))
        outcome = replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertEqual(runtime.service_requests, [])
        self.assertEqual(outcome.cancelled_service_requests, 1)

    def test_required_capability_is_rebound_to_stable_principal_before_commit(self):
        runtime = runtime_for()
        cap = CapabilityId("network.http")
        scope = CapabilityScope(
            frozenset({"https://api.example.com"}), frozenset({"GET"}), 1024
        )
        requirement = CapabilityRequirement(cap, scope, required=True)
        contract = migrate_contract(requirements=(requirement,))
        broker = CapabilityBroker()
        before = snapshot(runtime)
        with self.assertRaises(ReplacementError) as denied:
            replace_behaviour(
                runtime, tid(), aid(), new_program(), contract,
                capability_broker=broker, policy_time=2,
            )
        self.assertEqual(denied.exception.code, "replacement.capability_denied")
        self.assertEqual(snapshot(runtime), before)

        principal = principal_for_attachment(tid(), aid())
        broker.issue_root_grant(
            grant_id="g", principal_id=principal, capability_id=cap, scope=scope,
            issuer_policy_id="policy", issued_at=1, expires_at=10,
        )
        outcome = replace_behaviour(
            runtime, tid(), aid(), new_program(), contract,
            capability_broker=broker, policy_time=2,
        )
        self.assertEqual(outcome.capability_plan.granted, (cap,))
        migrated = runtime.states[tid()].private_by_attachment[aid()]
        self.assertNotIn("grant_id", migrated)
        self.assertNotIn("capability_grant", migrated)

    def test_revoked_or_expired_capability_cannot_partially_replace(self):
        for revoke, now in ((True, 2), (False, 5)):
            runtime = runtime_for()
            cap = CapabilityId("network.http")
            scope = CapabilityScope(frozenset({"api"}), frozenset({"GET"}), 10)
            requirement = CapabilityRequirement(cap, scope, required=True)
            broker = CapabilityBroker()
            broker.issue_root_grant(
                grant_id="g", principal_id=principal_for_attachment(tid(), aid()),
                capability_id=cap, scope=scope, issuer_policy_id="policy",
                issued_at=1, expires_at=5,
            )
            if revoke:
                broker.revoke("g")
            before = snapshot(runtime)
            with self.assertRaises(ReplacementError):
                replace_behaviour(
                    runtime, tid(), aid(), new_program(),
                    migrate_contract(requirements=(requirement,)),
                    capability_broker=broker, policy_time=now,
                )
            self.assertEqual(snapshot(runtime), before)

    def test_authority_like_private_state_is_not_serialized_through_replacement(self):
        runtime = runtime_for()
        runtime.states[tid()].private_by_attachment[aid()]["capability_grant"] = "g"
        before = snapshot(runtime)
        contract = ReplacementContract("preserve-authority", "worker:1", "worker:2")
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertEqual(caught.exception.code, "replacement.invalid_private_state")
        self.assertEqual(snapshot(runtime), before)

    def test_attachment_rng_stream_is_preserved_not_reseeded(self):
        runtime = runtime_for()
        key = (tid(), aid())
        rng_before = runtime._rng[key].getstate()
        contract = migrate_contract()
        replace_behaviour(runtime, tid(), aid(), new_program(), contract)
        self.assertEqual(runtime._rng[key].getstate(), rng_before)

    def test_committed_emitted_work_is_not_retroactively_rewritten(self):
        runtime = runtime_for()
        runtime.dispatch(tid(), "emit")
        runtime.run_current_tick()
        emitted_before = copy.deepcopy(runtime.emitted)
        replace_behaviour(runtime, tid(), aid(), new_program(), migrate_contract())
        self.assertEqual(runtime.emitted, emitted_before)

    def test_optional_capability_denial_is_explicit_reduced_mode_not_ambient_grant(self):
        runtime = runtime_for()
        cap = CapabilityId("clipboard.write")
        scope = CapabilityScope(frozenset({"clipboard"}), frozenset({"write"}), 1024)
        requirement = CapabilityRequirement(
            cap, scope, required=False, reduced_mode="local-copy-only"
        )
        outcome = replace_behaviour(
            runtime, tid(), aid(), new_program(), migrate_contract(requirements=(requirement,)),
            capability_broker=CapabilityBroker(), policy_time=1,
        )
        self.assertEqual(outcome.capability_plan.optional_denied, (cap,))
        self.assertEqual(outcome.capability_plan.reduced_modes, ("local-copy-only",))


if __name__ == "__main__":
    unittest.main()
