from __future__ import annotations

from copy import deepcopy
import json
import unittest

from model import (
    BehaviorRuntime,
    CompatibilityError,
    IdentityReuseError,
    TimerRecord,
    World,
)


BEHAVIOR_CATALOG_V1 = {
    "behavior:walker": {"revision": 1, "private_schema": 1},
    "behavior:door": {"revision": 1, "private_schema": 1},
}


class LifecycleModelTests(unittest.TestCase):
    def make_world(self) -> World:
        world = World(authored_revision="doc-rev-1", world_tick=10)
        thing = world.create_thing(
            thing_id="thing:robot",
            authored_basis={
                "document_revision": "doc-rev-1",
                "definition_id": "def:robot",
                "definition_revision": "defrev:7",
            },
            public_state={"x": 12, "mode": "patrol"},
            provenance={
                "definition_id": "def:robot",
                "definition_revision": "defrev:7",
                "element_id": "element:root",
            },
        )
        world.attach_behavior(
            thing.thing_id,
            BehaviorRuntime(
                attachment_id="attach:walker",
                definition_id="behavior:walker",
                revision=1,
                private_schema=1,
                private_state={"phase": 3},
                prng_state=123456,
            ),
        )
        world.add_timer(
            thing.thing_id,
            TimerRecord(
                timer_id="timer:step",
                attachment_id="attach:walker",
                continuation_id="continue:step",
                clock_domain="thing_active",
                remaining_active_ticks=5,
                payload={"n": 1},
            ),
        )
        thing.refs["door"] = "thing:door"
        world.queue_work(
            work_id="work:committed",
            target_id=thing.thing_id,
            attachment_id="attach:walker",
            kind="event",
            payload={"event": "already_committed"},
            durable=True,
        )
        world.set_context(
            thing.thing_id,
            engine_handle="GodotNode@1234",
            peer_id=17,
            capability_grants=["grant:http"],
            service_handle="socket@99",
        )
        return world

    def round_trip_snapshot(self, world: World) -> dict:
        # JSON round-trip intentionally destroys Python object identity.
        return json.loads(json.dumps(world.snapshot(snapshot_id="snap:1")))

    def test_lt001_fresh_runtime_restore_preserves_declared_simulation_state(self) -> None:
        world = self.make_world()
        walker = world.things["thing:robot"].behaviors["attach:walker"]
        walker.draw_u32()
        expected_digest = world.deterministic_digest()
        snapshot = self.round_trip_snapshot(world)

        restored = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )

        self.assertIsNot(restored, world)
        self.assertEqual(restored.deterministic_digest(), expected_digest)
        robot = restored.things["thing:robot"]
        self.assertEqual(robot.public_state, {"x": 12, "mode": "patrol"})
        self.assertEqual(robot.behaviors["attach:walker"].private_state, {"phase": 3})
        self.assertEqual(
            robot.behaviors["attach:walker"].prng_state,
            walker.prng_state,
        )
        self.assertEqual(robot.timers[0].remaining_active_ticks, 5)
        self.assertEqual(restored.queue[0].work_id, "work:committed")

    def test_lt002_reference_to_unloaded_target_remains_known(self) -> None:
        world = self.make_world()
        world.create_thing(
            thing_id="thing:door",
            authored_basis={"document_revision": "doc-rev-1"},
            public_state={"open": False},
        )
        world.unload("thing:door")
        self.assertEqual(world.resolve_ref("thing:door"), "known_unloaded")

        restored = World.restore(
            self.round_trip_snapshot(world),
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertEqual(
            restored.things["thing:robot"].refs["door"],
            "thing:door",
        )
        self.assertEqual(restored.resolve_ref("thing:door"), "known_unloaded")

    def test_lt003_snapshot_does_not_change_activity_or_residency(self) -> None:
        world = self.make_world()
        before = (
            world.things["thing:robot"].residency,
            world.things["thing:robot"].activity,
        )
        world.snapshot(snapshot_id="snap:nonmutating")
        after = (
            world.things["thing:robot"].residency,
            world.things["thing:robot"].activity,
        )
        self.assertEqual(after, before)
        self.assertEqual(after, ("resident", "active"))

    def test_lt004_dormancy_freezes_active_clock_but_world_clock_continues(self) -> None:
        world = self.make_world()
        robot = world.things["thing:robot"]
        world.add_timer(
            robot.thing_id,
            TimerRecord(
                timer_id="timer:world",
                attachment_id="attach:walker",
                continuation_id="continue:world",
                clock_domain="world_logical",
                due_world_tick=12,
            ),
        )
        world.set_dormant(robot.thing_id, True)
        active_remaining = robot.timers[0].remaining_active_ticks
        world.advance(2)

        self.assertEqual(robot.active_ticks, 0)
        self.assertEqual(robot.timers[0].remaining_active_ticks, active_remaining)
        self.assertTrue(any(w.work_id == "timer:timer:world" for w in world.queue))
        self.assertFalse(any(t.timer_id == "timer:world" for t in robot.timers))

    def test_lt005_world_timer_for_unloaded_target_becomes_pending_delivery(self) -> None:
        world = self.make_world()
        robot = world.things["thing:robot"]
        world.add_timer(
            robot.thing_id,
            TimerRecord(
                timer_id="timer:offline-world",
                attachment_id="attach:walker",
                continuation_id="continue:offline",
                clock_domain="world_logical",
                due_world_tick=11,
                payload={"wake": True},
            ),
        )
        world.unload(robot.thing_id)
        world.advance(1)

        self.assertEqual(world.resolve_ref(robot.thing_id), "known_unloaded")
        self.assertTrue(
            any(w.work_id == "timer:timer:offline-world" for w in world.pending_deliveries)
        )

        restored = World.restore(
            self.round_trip_snapshot(world),
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertTrue(
            any(w.work_id == "timer:timer:offline-world" for w in restored.pending_deliveries)
        )

    def test_lt006_restore_does_not_reissue_external_service(self) -> None:
        world = self.make_world()
        world.issue_external_service(
            thing_id="thing:robot",
            attachment_id="attach:walker",
            wait_id="wait:http",
            service_name="network.http",
            correlation_id="corr:123",
            restore_policy="cancel_on_restore",
        )
        self.assertEqual(len(world.host_service_calls), 1)

        restored = World.restore(
            self.round_trip_snapshot(world),
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertEqual(restored.host_service_calls, [])
        self.assertEqual(len(restored.external_waits), 1)
        self.assertEqual(restored.external_waits[0].correlation_id, "corr:123")

    def test_lt007_transient_authority_and_engine_context_are_not_snapshotted(self) -> None:
        world = self.make_world()
        snapshot = self.round_trip_snapshot(world)
        encoded = json.dumps(snapshot)
        for forbidden in (
            "GodotNode@1234",
            "grant:http",
            "socket@99",
            '"peer_id"',
            '"capability_grants"',
        ):
            self.assertNotIn(forbidden, encoded)

        restored = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertEqual(restored.context, {})

    def test_lt008_behavior_schema_mismatch_requires_explicit_migration(self) -> None:
        world = self.make_world()
        snapshot = self.round_trip_snapshot(world)
        catalog_v2 = {
            "behavior:walker": {"revision": 2, "private_schema": 2},
        }

        with self.assertRaises(CompatibilityError):
            World.restore(
                snapshot,
                current_authored_revision="doc-rev-1",
                behavior_catalog=catalog_v2,
            )

        restored = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=catalog_v2,
            behavior_migrations={
                ("behavior:walker", 1, 2, 1, 2): lambda old: {
                    "phase_v2": old["phase"],
                    "migrated": True,
                }
            },
        )
        behavior = restored.things["thing:robot"].behaviors["attach:walker"]
        self.assertEqual(behavior.revision, 2)
        self.assertEqual(behavior.private_schema, 2)
        self.assertEqual(
            behavior.private_state,
            {"phase_v2": 3, "migrated": True},
        )

    def test_lt009_definition_instance_provenance_round_trips_independently(self) -> None:
        world = self.make_world()
        snapshot = self.round_trip_snapshot(world)
        # Paths/engine nodes are irrelevant: only stable provenance survives.
        restored = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertEqual(
            restored.things["thing:robot"].provenance,
            {
                "definition_id": "def:robot",
                "definition_revision": "defrev:7",
                "element_id": "element:root",
            },
        )
        self.assertEqual(restored.context, {})

    def test_lt010_restore_does_not_replay_creation_hook(self) -> None:
        world = self.make_world()
        self.assertEqual(world.creation_events, ["thing:robot"])
        snapshot = self.round_trip_snapshot(world)

        restored = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
            emit_restore_event=False,
        )
        self.assertEqual(restored.creation_events, [])
        self.assertEqual(restored.restore_events, [])

        restored_with_event = World.restore(
            snapshot,
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
            emit_restore_event=True,
        )
        self.assertEqual(restored_with_event.creation_events, [])
        self.assertEqual(restored_with_event.restore_events, ["thing:robot"])

    def test_lt011_destroyed_reference_is_tombstoned_and_id_is_not_reused(self) -> None:
        world = self.make_world()
        world.create_thing(
            thing_id="thing:door",
            authored_basis={"document_revision": "doc-rev-1"},
        )
        world.things["thing:robot"].refs["door"] = "thing:door"
        world.destroy("thing:door", reason="broken")

        self.assertEqual(world.resolve_ref("thing:door"), "tombstoned")
        with self.assertRaises(IdentityReuseError):
            world.create_thing(
                thing_id="thing:door",
                authored_basis={"document_revision": "doc-rev-1"},
            )

        replacement = world.create_thing(
            thing_id="thing:door-respawn-2",
            authored_basis={"document_revision": "doc-rev-1"},
        )
        self.assertEqual(replacement.thing_id, "thing:door-respawn-2")
        self.assertEqual(world.things["thing:robot"].refs["door"], "thing:door")

    def test_lt012_restore_is_deterministic_but_later_external_input_may_diverge(self) -> None:
        world = self.make_world()
        snapshot = self.round_trip_snapshot(world)

        a = World.restore(
            deepcopy(snapshot),
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        b = World.restore(
            deepcopy(snapshot),
            current_authored_revision="doc-rev-1",
            behavior_catalog=BEHAVIOR_CATALOG_V1,
        )
        self.assertEqual(a.deterministic_digest(), b.deterministic_digest())

        a.apply_external_input("thing:robot", "weather", "rain")
        b.apply_external_input("thing:robot", "weather", "sun")
        self.assertNotEqual(a.deterministic_digest(), b.deterministic_digest())


if __name__ == "__main__":
    unittest.main()
