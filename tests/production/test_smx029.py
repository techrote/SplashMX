from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace

from splashmx.canonical.core import (
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ReferenceState,
    ThingId,
    ThingRecord,
)
from splashmx.execution.ir import (
    IRHandler,
    IRInstruction,
    IRProgram,
    literal,
    payload,
)
from splashmx.runtime.lifecycle import (
    LifecycleError,
    LifecyclePhase,
    SQLiteWorldSaveStore,
    WORLD_COMMIT_STAGES,
    WorldSaveId,
    deserialize_world_save,
    restore_world_save,
    serialize_world_save,
    WorldRuntime,
)
from splashmx.security.capabilities import (
    CapabilityBroker,
    CapabilityId,
    CapabilityRequirement,
    CapabilityScope,
    PrincipalId,
)


def tid(value: str = "thing") -> ThingId:
    return ThingId(value)


def aid(value: str = "slot") -> BehaviourAttachmentId:
    return BehaviourAttachmentId(value)


def ins(op: str, **args) -> IRInstruction:
    return IRInstruction(op, args)


def handler(handler_id: str, trigger: str, *rows: IRInstruction) -> IRHandler:
    return IRHandler(handler_id, trigger, tuple(rows))


def program(revision: str = "worker:1") -> IRProgram:
    return IRProgram(
        revision,
        (
            handler(
                "step",
                "step",
                ins("add_public", key="score", value=literal(1)),
                ins("add_private", key="count", value=literal(1)),
            ),
            handler(
                "start",
                "start",
                ins(
                    "schedule",
                    timer_id="later",
                    delay=5,
                    handler="resume",
                    payload=literal({"kind": "timer"}),
                ),
            ),
            handler(
                "resume",
                "resume",
                ins("add_private", key="count", value=literal(10)),
            ),
            handler(
                "mark",
                "mark",
                ins("set_private", key="last", value=payload("n")),
            ),
            handler(
                "roll",
                "roll",
                ins(
                    "set_private",
                    key="roll",
                    value={"expr": "random_int", "min": literal(1), "max": literal(1_000_000)},
                ),
            ),
            handler(
                "ask",
                "ask",
                ins(
                    "request_service",
                    service="network.http",
                    request_id="fetch",
                    payload=literal({"target": "https://api.example.com", "operation": "GET"}),
                ),
            ),
            handler(
                "signal",
                "signal",
                ins("emit", event="nobody-listens", payload=literal({"ok": True})),
            ),
            handler(
                "created",
                "created",
                ins("set_private", key="created_count", value=literal(99)),
            ),
        ),
        private_defaults={"count": 1, "last": 0, "roll": 0, "created_count": 0},
    )


def document(*, revision: str = "p1", include_behaviour: bool = True) -> CanonicalDocument:
    doc = CanonicalDocument(ProjectId("project"), ProjectRevisionId(revision))
    behaviours = (
        {aid(): BehaviourAttachmentRecord(aid(), "worker:1")}
        if include_behaviour
        else {}
    )
    doc.things[tid()] = ThingRecord(
        tid(),
        "Thing",
        authored_state={"score": 3},
        behaviours=behaviours,
    )
    return doc


def world(*, seed: int = 123) -> WorldRuntime:
    p = program()
    return WorldRuntime.create(document(), {p.behaviour_revision: p}, seed=seed)


def mutable_signature(value: WorldRuntime):
    state = value.runtime.states.get(tid())
    return (
        value.reference_state(tid()),
        copy.deepcopy(state.public_state) if state else None,
        copy.deepcopy(state.private_by_attachment) if state else None,
        copy.deepcopy(value.runtime.pending_timers),
        copy.deepcopy(value.runtime._queue),
        value.runtime.logical_tick,
        value.runtime._sequence,
        copy.deepcopy(value.runtime.service_requests),
        copy.deepcopy(value.runtime.emitted),
    )


class SMX029LifecycleWorldSaveTests(unittest.TestCase):
    def test_snapshot_is_non_mutating_and_deterministic(self):
        current = world()
        before = mutable_signature(current)
        one = current.snapshot(WorldSaveId("save"))
        two = current.snapshot(WorldSaveId("save"))
        self.assertEqual(mutable_signature(current), before)
        self.assertEqual(one, two)
        self.assertEqual(serialize_world_save(one), serialize_world_save(two))
        self.assertEqual(current.lifecycle[tid()], LifecyclePhase.ACTIVE)

    def test_authored_project_and_runtime_world_state_are_distinct(self):
        current = world()
        current.runtime.states[tid()].public_state["score"] = 77
        snap = current.snapshot("save")
        self.assertEqual(current.document.things[tid()].authored_state["score"], 3)
        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        self.assertEqual(restored.runtime.states[tid()].public_state["score"], 77)
        self.assertEqual(restored.document.things[tid()].authored_state["score"], 3)

    def test_dormancy_is_resident_but_blocks_new_author_dispatch(self):
        current = world()
        current.set_dormant(tid())
        self.assertEqual(current.reference_state(tid()), ReferenceState.LOADED)
        self.assertIn(tid(), current.runtime.states)
        with self.assertRaises(LifecycleError) as caught:
            current.dispatch(tid(), "step")
        self.assertEqual(caught.exception.code, "lifecycle.not_active")
        snap = current.snapshot("save")
        self.assertEqual(snap.things[0].phase, LifecyclePhase.DORMANT)
        current.activate(tid())
        self.assertEqual(current.lifecycle[tid()], LifecyclePhase.ACTIVE)

    def test_unload_preserves_identity_state_and_pending_work_without_residency(self):
        current = world()
        current.dispatch(tid(), "start")
        current.runtime.run_current_tick()
        self.assertEqual(len(current.runtime.pending_timers), 1)
        current.runtime.states[tid()].private_by_attachment[aid()]["count"] = 8
        current.unload(tid())
        self.assertEqual(current.reference_state(tid()), ReferenceState.KNOWN_UNLOADED)
        self.assertNotIn(tid(), current.runtime.states)
        self.assertEqual(current.runtime.pending_timers, {})
        snap = current.snapshot("save")
        row = snap.things[0]
        self.assertEqual(row.phase, LifecyclePhase.KNOWN_UNLOADED)
        self.assertEqual(row.attachments[0].private_state["count"], 8)
        self.assertEqual(len(row.timers), 1)
        self.assertEqual(len(row.queued_work), 1)

    def test_rehydrate_restores_unloaded_thing_and_pending_timer(self):
        current = world()
        current.dispatch(tid(), "start")
        current.runtime.run_current_tick()
        current.runtime.states[tid()].private_by_attachment[aid()]["count"] = 8
        current.unload(tid())
        current.rehydrate(tid())
        self.assertEqual(current.reference_state(tid()), ReferenceState.LOADED)
        self.assertEqual(current.runtime.states[tid()].private_by_attachment[aid()]["count"], 8)
        self.assertEqual(len(current.runtime.pending_timers), 1)
        current.runtime.advance_to(5)
        self.assertEqual(current.runtime.states[tid()].private_by_attachment[aid()]["count"], 18)

    def test_tombstoned_unknown_and_known_unloaded_are_distinct(self):
        current = world()
        remote = ThingId("remote")
        current.document.known_unloaded_things.add(remote)
        current.lifecycle[remote] = LifecyclePhase.KNOWN_UNLOADED
        from splashmx.runtime.lifecycle import ThingRuntimeSnapshot
        current._retained[remote] = ThingRuntimeSnapshot(remote, LifecyclePhase.KNOWN_UNLOADED)
        current.tombstone(tid(), reason="destroyed")
        self.assertEqual(current.reference_state(tid()), ReferenceState.TOMBSTONED)
        self.assertEqual(current.reference_state(remote), ReferenceState.KNOWN_UNLOADED)
        self.assertEqual(current.reference_state(ThingId("missing")), ReferenceState.UNKNOWN)
        with self.assertRaises(LifecycleError):
            current.rehydrate(tid())
        snap = current.snapshot("save")
        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        self.assertEqual(restored.reference_state(tid()), ReferenceState.TOMBSTONED)
        self.assertNotIn(tid(), restored.runtime.states)

    def test_known_unloaded_reference_without_local_basis_stays_known_not_unknown(self):
        doc = document()
        remote = ThingId("remote")
        doc.known_unloaded_things.add(remote)
        current = WorldRuntime.create(doc, {"worker:1": program()})
        snap = current.snapshot("save")
        restored = restore_world_save(snap, doc, {"worker:1": program()}).world
        self.assertEqual(restored.reference_state(remote), ReferenceState.KNOWN_UNLOADED)
        with self.assertRaises(LifecycleError) as caught:
            restored.rehydrate(remote)
        self.assertEqual(caught.exception.code, "lifecycle.dependency_unavailable")

    def test_timer_and_queue_order_restore_exactly_once(self):
        current = world()
        current.runtime.enqueue_handler(tid(), aid(), "mark", {"n": 1}, due_tick=4)
        current.runtime.enqueue_handler(tid(), aid(), "mark", {"n": 2}, due_tick=4)
        current.dispatch(tid(), "start")
        current.runtime.run_current_tick()
        snap = current.snapshot("save")
        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        sequences = [row[2].sequence for row in sorted(restored.runtime._queue)]
        self.assertEqual(sequences, sorted(sequences))
        restored.runtime.advance_to(4)
        self.assertEqual(restored.runtime.states[tid()].private_by_attachment[aid()]["last"], 2)
        restored.runtime.advance_to(5)
        self.assertEqual(restored.runtime.states[tid()].private_by_attachment[aid()]["count"], 11)
        self.assertEqual(restored.runtime.advance_to(5), 0)

    def test_rng_position_survives_fresh_runtime_restore(self):
        current = world(seed=9001)
        current.dispatch(tid(), "roll")
        current.runtime.run_current_tick()
        snap = current.snapshot("save")

        current.dispatch(tid(), "roll")
        current.runtime.run_current_tick()
        expected = current.runtime.states[tid()].private_by_attachment[aid()]["roll"]

        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        restored.dispatch(tid(), "roll")
        restored.runtime.run_current_tick()
        actual = restored.runtime.states[tid()].private_by_attachment[aid()]["roll"]
        self.assertEqual(actual, expected)

    def test_external_service_wait_is_persisted_but_never_implicitly_reissued(self):
        current = world()
        current.dispatch(tid(), "ask")
        current.runtime.run_current_tick()
        self.assertEqual(len(current.runtime.service_requests), 1)
        snap = current.snapshot("save")
        self.assertEqual(len(snap.things[0].external_waits), 1)
        restored_result = restore_world_save(
            snap, current.document, {"worker:1": program()}
        )
        self.assertEqual(restored_result.world.runtime.service_requests, [])
        self.assertEqual(len(restored_result.deferred_external_waits), 1)
        again = restored_result.world.snapshot("save-2")
        self.assertEqual(len(again.things[0].external_waits), 1)

    def test_committed_emitted_outbox_is_not_replayed_by_restore(self):
        current = world()
        current.dispatch(tid(), "signal")
        current.runtime.run_current_tick()
        self.assertEqual(len(current.runtime.emitted), 1)
        snap = current.snapshot("save")
        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        self.assertEqual(restored.runtime.emitted, [])

    def test_restore_does_not_replay_created_hook(self):
        current = world()
        snap = current.snapshot("save")
        restored = restore_world_save(snap, current.document, {"worker:1": program()}).world
        private = restored.runtime.states[tid()].private_by_attachment[aid()]
        self.assertEqual(private["created_count"], 0)
        self.assertEqual(restored.runtime.queue_depth, 0)

    def test_transient_session_or_capability_handles_cannot_enter_snapshot(self):
        for field in ("session_id", "process_handle", "capability_grant", "native_pointer"):
            with self.subTest(field=field):
                current = world()
                current.runtime.states[tid()].private_by_attachment[aid()][field] = "forbidden"
                with self.assertRaises(LifecycleError) as caught:
                    current.snapshot("save")
                self.assertEqual(caught.exception.code, "worldsave.forbidden_transient_state")

    def test_external_wait_payload_cannot_smuggle_serialized_authority(self):
        current = world()
        current.dispatch(tid(), "ask")
        current.runtime.run_current_tick()
        request = current.runtime.service_requests[0]
        current.runtime.service_requests[0] = replace(
            request, payload={"nested": {"capability_token": "secret"}}
        )
        with self.assertRaises(LifecycleError) as caught:
            current.snapshot("save")
        self.assertEqual(caught.exception.code, "worldsave.forbidden_transient_state")

    def test_required_capability_is_rebound_from_current_policy_not_save_bytes(self):
        current = world()
        snap = current.snapshot("save")
        cap = CapabilityId("network.http")
        scope = CapabilityScope(frozenset({"api"}), frozenset({"GET"}), 1024)
        requirement = CapabilityRequirement(cap, scope, required=True)
        requirements = {(tid(), aid()): (requirement,)}

        with self.assertRaises(LifecycleError) as denied:
            restore_world_save(
                snap,
                current.document,
                {"worker:1": program()},
                capability_requirements=requirements,
                policy_time=2,
            )
        self.assertEqual(denied.exception.code, "worldsave.capability_denied")

        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="grant-live",
            principal_id=PrincipalId("behaviour:thing:slot"),
            capability_id=cap,
            scope=scope,
            issuer_policy_id="policy",
            issued_at=1,
            expires_at=10,
        )
        result = restore_world_save(
            snap,
            current.document,
            {"worker:1": program()},
            capability_broker=broker,
            capability_requirements=requirements,
            policy_time=2,
        )
        self.assertEqual(result.capability_plans[(tid(), aid())].granted, (cap,))
        self.assertNotIn(b"grant-live", serialize_world_save(snap))

    def test_revoked_capability_cannot_be_resurrected_by_restore(self):
        current = world()
        snap = current.snapshot("save")
        cap = CapabilityId("network.http")
        scope = CapabilityScope(frozenset({"api"}), frozenset({"GET"}), 1024)
        requirements = {(tid(), aid()): (CapabilityRequirement(cap, scope),)}
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="g",
            principal_id=PrincipalId("behaviour:thing:slot"),
            capability_id=cap,
            scope=scope,
            issuer_policy_id="policy",
            issued_at=1,
            expires_at=10,
        )
        broker.revoke("g")
        with self.assertRaises(LifecycleError) as caught:
            restore_world_save(
                snap,
                current.document,
                {"worker:1": program()},
                capability_broker=broker,
                capability_requirements=requirements,
                policy_time=2,
            )
        self.assertEqual(caught.exception.code, "worldsave.capability_denied")

    def test_missing_exact_behaviour_artifact_rejects_before_publication(self):
        current = world()
        snap = current.snapshot("save")
        with self.assertRaises(LifecycleError) as caught:
            restore_world_save(snap, current.document, {})
        self.assertEqual(caught.exception.code, "worldsave.exact_artifact_unavailable")
        self.assertEqual(mutable_signature(current)[1]["score"], 3)

    def test_authored_revision_or_attachment_mismatch_rejects(self):
        current = world()
        snap = current.snapshot("save")
        wrong_revision = document(revision="p2")
        with self.assertRaises(LifecycleError) as caught:
            restore_world_save(snap, wrong_revision, {"worker:1": program()})
        self.assertEqual(caught.exception.code, "worldsave.authored_revision_mismatch")

        wrong_attachment = document(include_behaviour=False)
        with self.assertRaises(LifecycleError) as caught:
            restore_world_save(snap, wrong_attachment, {"worker:1": program()})
        self.assertEqual(caught.exception.code, "worldsave.attachment_mismatch")

    def test_canonical_worldsave_roundtrip_and_noncanonical_bytes_reject(self):
        snap = world().snapshot("save")
        raw = serialize_world_save(snap)
        self.assertEqual(deserialize_world_save(raw), snap)
        pretty = json.dumps(json.loads(raw), indent=2, sort_keys=True).encode()
        with self.assertRaises(LifecycleError) as caught:
            deserialize_world_save(pretty)
        self.assertEqual(caught.exception.code, "worldsave.noncanonical_encoding")

    def test_world_revision_digest_detects_semantic_tampering(self):
        snap = world().snapshot("save")
        tampered = replace(snap, logical_tick=snap.logical_tick + 1)
        with self.assertRaises(LifecycleError) as caught:
            serialize_world_save(tampered)
        self.assertEqual(caught.exception.code, "worldsave.revision_mismatch")

    def test_store_crash_boundaries_preserve_one_coherent_head(self):
        baseline_world = world()
        first = baseline_world.snapshot("save")
        baseline_world.runtime.states[tid()].public_state["score"] = 44
        second = baseline_world.snapshot("save")

        for stage in WORLD_COMMIT_STAGES:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "world.db"
                with SQLiteWorldSaveStore(path) as store:
                    store.save(first)

                    def fault(seen: str) -> None:
                        if seen == stage:
                            raise RuntimeError(stage)

                    with self.assertRaises(RuntimeError):
                        store.save(second, fault_hook=fault)
                with SQLiteWorldSaveStore(path) as reopened:
                    loaded = reopened.load("save")
                expected = second if stage == "committed" else first
                self.assertEqual(loaded.world_revision_id, expected.world_revision_id)
                self.assertEqual(loaded, expected)

    def test_corrupt_store_is_explicit_and_does_not_fabricate_state(self):
        snap = world().snapshot("save")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "world.db"
            with SQLiteWorldSaveStore(path) as store:
                store.save(snap)
                store._db.execute(
                    "UPDATE world_revisions SET payload=? WHERE world_save_id=?",
                    (b"{}", "save"),
                )
                with self.assertRaises(LifecycleError) as caught:
                    store.load("save")
                self.assertEqual(caught.exception.code, "worldsave.corrupt_store")

    def test_failed_restore_leaves_committed_worldsave_head_available(self):
        current = world()
        snap = current.snapshot("save")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "world.db"
            with SQLiteWorldSaveStore(path) as store:
                store.save(snap)
                loaded = store.load("save")
                with self.assertRaises(LifecycleError):
                    restore_world_save(
                        loaded,
                        document(revision="other"),
                        {"worker:1": program()},
                    )
                self.assertEqual(store.load("save"), snap)

    def test_fresh_process_restore_has_no_surviving_python_runtime_objects(self):
        current = world()
        current.runtime.states[tid()].public_state["score"] = 91
        current.dispatch(tid(), "start")
        current.runtime.run_current_tick()
        snap = current.snapshot("save")

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "world.db"
            with SQLiteWorldSaveStore(path) as store:
                store.save(snap)

            script = r'''\
import json, sys
from splashmx.canonical.core import BehaviourAttachmentId, BehaviourAttachmentRecord, CanonicalDocument, ProjectId, ProjectRevisionId, ThingId, ThingRecord
from splashmx.execution.ir import IRHandler, IRInstruction, IRProgram, literal
from splashmx.runtime.lifecycle import SQLiteWorldSaveStore, restore_world_save
tid=ThingId("thing"); aid=BehaviourAttachmentId("slot")
def ins(op, **args): return IRInstruction(op,args)
handlers=(
 IRHandler("step","step",(ins("add_public",key="score",value=literal(1)),ins("add_private",key="count",value=literal(1)))),
 IRHandler("start","start",(ins("schedule",timer_id="later",delay=5,handler="resume",payload=literal({"kind":"timer"})),)),
 IRHandler("resume","resume",(ins("add_private",key="count",value=literal(10)),)),
 IRHandler("mark","mark",(ins("set_private",key="last",value={"expr":"payload","key":"n"}),)),
 IRHandler("roll","roll",(ins("set_private",key="roll",value={"expr":"random_int","min":literal(1),"max":literal(1000000)}),)),
 IRHandler("ask","ask",(ins("request_service",service="network.http",request_id="fetch",payload=literal({"target":"https://api.example.com","operation":"GET"})),)),
 IRHandler("signal","signal",(ins("emit",event="nobody-listens",payload=literal({"ok":True})),)),
 IRHandler("created","created",(ins("set_private",key="created_count",value=literal(99)),)),
)
p=IRProgram("worker:1",handlers,private_defaults={"count":1,"last":0,"roll":0,"created_count":0})
doc=CanonicalDocument(ProjectId("project"),ProjectRevisionId("p1"))
doc.things[tid]=ThingRecord(tid,"Thing",authored_state={"score":3},behaviours={aid:BehaviourAttachmentRecord(aid,"worker:1")})
with SQLiteWorldSaveStore(sys.argv[1]) as store: snap=store.load("save")
result=restore_world_save(snap,doc,{"worker:1":p}).world
print(json.dumps({"score":result.runtime.states[tid].public_state["score"],"timers":len(result.runtime.pending_timers),"services":len(result.runtime.service_requests)}))
'''
            output = subprocess.check_output(
                [sys.executable, "-c", script, str(path)],
                text=True,
                env=os.environ.copy(),
            )
        self.assertEqual(json.loads(output), {"score": 91, "timers": 1, "services": 0})

    def test_worldsave_serialization_does_not_own_protected_asset_revision_bundles(self):
        raw = serialize_world_save(world().snapshot("save"))
        data = json.loads(raw)
        self.assertNotIn("assets", data)
        self.assertNotIn("protected_assets", data)
        self.assertNotIn("licence_attribution", data)
        self.assertNotIn("derivation_lineage", data)


if __name__ == "__main__":
    unittest.main()
