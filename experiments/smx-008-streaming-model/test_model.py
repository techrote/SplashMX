from __future__ import annotations

from copy import deepcopy
import unittest

from model import (
    ArtifactManager,
    ArtifactRepository,
    BehaviorAttachment,
    DependencyEdge,
    PinnedArtifactError,
    ReplacementError,
    StreamingWorld,
    ThingRecord,
    canonical_capsule_roundtrip,
)


class StreamingModelTests(unittest.TestCase):
    def make_repo(self) -> tuple[ArtifactRepository, ArtifactManager]:
        repo = ArtifactRepository()
        repo.add(
            "behaviour:sword",
            kind="behaviour",
            revision="1",
            payload=b"sword-behaviour-v1",
            semantic={
                "revision": 1,
                "private_schema": 1,
                "default_private_state": {"swings": 0},
            },
        )
        repo.add(
            "behaviour:weather",
            kind="behaviour",
            revision="1",
            payload=b"weather-behaviour-v1",
            semantic={
                "revision": 1,
                "private_schema": 1,
                "default_private_state": {"ticks": 0},
            },
        )
        repo.add(
            "def:weather-clock",
            kind="definition",
            revision="7",
            payload=b"weather-clock-def-v7",
            dependencies=(DependencyEdge("behaviour:weather", "required"),),
            semantic={
                "behavior_id": "behaviour:weather",
                "default_state": {"format": "24h"},
            },
        )
        return repo, ArtifactManager(repo)

    def test_sg001_inventory_reference_survives_town_unload_and_sword_reload(self) -> None:
        repo, artifacts = self.make_repo()
        world = StreamingWorld(artifacts)

        sword = ThingRecord(
            thing_id="thing:sword-17",
            region="town-west",
            state={"durability": 81},
            behaviors={
                "attach:sword": BehaviorAttachment(
                    attachment_id="attach:sword",
                    implementation_id="behaviour:sword",
                    revision=1,
                    private_schema=1,
                    private_state={"swings": 4},
                )
            },
        )
        house = ThingRecord(
            thing_id="thing:house-1",
            region="town-west",
            state={"door": "closed"},
        )
        inventory = ThingRecord(
            thing_id="thing:inventory",
            refs={"slot_2": "thing:sword-17"},
            state={"owner": "player"},
        )
        world.create(sword)
        world.create(house)
        world.create(inventory)

        world.unload(["thing:sword-17", "thing:house-1"])

        self.assertEqual(world.status("thing:sword-17"), "known_unloaded")
        self.assertEqual(
            world.resident["thing:inventory"].refs["slot_2"],
            "thing:sword-17",
        )

        result = world.load(["thing:sword-17"])
        self.assertEqual(result.status, "published")
        self.assertEqual(world.status("thing:sword-17"), "loaded")
        self.assertEqual(world.status("thing:house-1"), "known_unloaded")
        self.assertEqual(
            world.resident["thing:sword-17"].state["durability"],
            81,
        )
        self.assertEqual(
            world.resident["thing:inventory"].refs["slot_2"],
            "thing:sword-17",
        )

    def test_sg002_component_definition_acquires_closure_before_instantiation(self) -> None:
        repo, artifacts = self.make_repo()
        world = StreamingWorld(artifacts)

        result = world.instantiate_component(
            definition_id="def:weather-clock",
            new_thing_id="thing:clock-1",
        )
        self.assertEqual(result.status, "published")
        self.assertTrue(artifacts.is_resident("def:weather-clock"))
        self.assertTrue(artifacts.is_resident("behaviour:weather"))
        self.assertIn("thing:clock-1", world.resident)
        clock = world.resident["thing:clock-1"]
        self.assertEqual(clock.state, {"format": "24h"})
        self.assertEqual(clock.provenance["definition_id"], "def:weather-clock")
        self.assertEqual(world.creation_events, ["thing:clock-1"])

    def test_sg003_required_dependency_failures_are_typed_and_atomic(self) -> None:
        for availability, expected in (
            ("denied", "denied"),
            ("incompatible", "incompatible"),
            ("offline", "offline_or_unreachable"),
        ):
            repo = ArtifactRepository()
            repo.add(
                "dep:bad",
                kind="behaviour",
                revision="1",
                payload=b"bad",
                availability=availability,
            )
            repo.add(
                "root",
                kind="definition",
                revision="1",
                payload=b"root",
                dependencies=(DependencyEdge("dep:bad", "required"),),
            )
            artifacts = ArtifactManager(repo)
            result = artifacts.acquire(["root"])
            self.assertEqual(result.status, expected)
            self.assertEqual(artifacts.resident_artifacts, set())

        repo = ArtifactRepository()
        repo.add("dep:tampered", kind="asset", revision="1", payload=b"good")
        repo.add(
            "root",
            kind="definition",
            revision="1",
            payload=b"root",
            dependencies=(DependencyEdge("dep:tampered", "required"),),
        )
        repo.tamper("dep:tampered", b"evil!")
        artifacts = ArtifactManager(repo)
        result = artifacts.acquire(["root"])
        self.assertEqual(result.status, "invalid_or_malicious")
        self.assertEqual(artifacts.resident_artifacts, set())

        repo = ArtifactRepository()
        repo.add(
            "root",
            kind="definition",
            revision="1",
            payload=b"root",
            dependencies=(DependencyEdge("dep:missing", "required"),),
        )
        artifacts = ArtifactManager(repo)
        result = artifacts.acquire(["root"])
        self.assertEqual(result.status, "missing")
        self.assertEqual(artifacts.resident_artifacts, set())

    def test_sg004_optional_dependency_uses_declared_fallback(self) -> None:
        repo = ArtifactRepository()
        repo.add(
            "root",
            kind="definition",
            revision="1",
            payload=b"root",
            dependencies=(
                DependencyEdge(
                    "asset:optional-hires",
                    "optional",
                    fallback="asset:placeholder",
                ),
            ),
        )
        artifacts = ArtifactManager(repo)
        result = artifacts.acquire(["root"])
        self.assertEqual(result.status, "published")
        self.assertEqual(result.optional_failures, {"asset:optional-hires": "missing"})
        self.assertEqual(artifacts.resident_artifacts, {"root"})

    def test_sg005_active_behaviour_pins_code_dormant_can_evict_and_wake_reacquires(self) -> None:
        repo, artifacts = self.make_repo()
        world = StreamingWorld(artifacts)
        thing = ThingRecord(
            thing_id="thing:sword",
            behaviors={
                "attach:sword": BehaviorAttachment(
                    attachment_id="attach:sword",
                    implementation_id="behaviour:sword",
                    revision=1,
                    private_schema=1,
                    private_state={"swings": 9},
                )
            },
        )
        world.create(thing)

        with self.assertRaises(PinnedArtifactError):
            artifacts.evict("behaviour:sword")

        world.set_dormant("thing:sword", True)
        self.assertTrue(artifacts.evict("behaviour:sword"))
        self.assertFalse(artifacts.is_resident("behaviour:sword"))
        self.assertEqual(
            world.resident["thing:sword"].behaviors["attach:sword"].private_state,
            {"swings": 9},
        )

        result = world.set_dormant("thing:sword", False)
        self.assertEqual(result.status, "published")
        self.assertTrue(artifacts.is_resident("behaviour:sword"))
        self.assertEqual(
            world.resident["thing:sword"].behaviors["attach:sword"].private_state,
            {"swings": 9},
        )

    def test_sg006_hot_replacement_migrates_state_and_continuation_atomically(self) -> None:
        repo, artifacts = self.make_repo()
        repo.add(
            "behaviour:sword-v2",
            kind="behaviour",
            revision="2",
            payload=b"sword-behaviour-v2",
            semantic={
                "revision": 2,
                "private_schema": 2,
            },
        )
        world = StreamingWorld(artifacts)
        thing = ThingRecord(
            thing_id="thing:sword",
            behaviors={
                "attach:sword": BehaviorAttachment(
                    attachment_id="attach:sword",
                    implementation_id="behaviour:sword",
                    revision=1,
                    private_schema=1,
                    private_state={"swings": 4},
                    continuations=["continue:cooldown-v1"],
                )
            },
        )
        world.create(thing)

        result = world.hot_replace_behavior(
            thing_id="thing:sword",
            attachment_id="attach:sword",
            new_implementation_id="behaviour:sword-v2",
            migration=lambda old: {"swing_count": old["swings"], "v": 2},
            continuation_map={"continue:cooldown-v1": "continue:cooldown-v2"},
        )
        self.assertEqual(result.status, "published")
        attachment = world.resident["thing:sword"].behaviors["attach:sword"]
        self.assertEqual(attachment.implementation_id, "behaviour:sword-v2")
        self.assertEqual(attachment.revision, 2)
        self.assertEqual(attachment.private_schema, 2)
        self.assertEqual(attachment.private_state, {"swing_count": 4, "v": 2})
        self.assertEqual(attachment.continuations, ["continue:cooldown-v2"])
        self.assertEqual(artifacts.pin_counts.get("behaviour:sword", 0), 0)
        self.assertEqual(artifacts.pin_counts.get("behaviour:sword-v2", 0), 1)

    def test_sg007_failed_replacement_keeps_old_live_state_and_work(self) -> None:
        repo, artifacts = self.make_repo()
        repo.add(
            "behaviour:sword-v2",
            kind="behaviour",
            revision="2",
            payload=b"sword-behaviour-v2",
            semantic={
                "revision": 2,
                "private_schema": 2,
            },
        )
        world = StreamingWorld(artifacts)
        thing = ThingRecord(
            thing_id="thing:sword",
            behaviors={
                "attach:sword": BehaviorAttachment(
                    attachment_id="attach:sword",
                    implementation_id="behaviour:sword",
                    revision=1,
                    private_schema=1,
                    private_state={"swings": 4},
                    continuations=["continue:cooldown-v1"],
                )
            },
        )
        world.create(thing)
        before = deepcopy(world.resident["thing:sword"].behaviors["attach:sword"])

        with self.assertRaises(ReplacementError):
            world.hot_replace_behavior(
                thing_id="thing:sword",
                attachment_id="attach:sword",
                new_implementation_id="behaviour:sword-v2",
                migration=lambda old: (_ for _ in ()).throw(ValueError("bad migration")),
                continuation_map={"continue:cooldown-v1": "continue:cooldown-v2"},
            )

        after = world.resident["thing:sword"].behaviors["attach:sword"]
        self.assertEqual(after, before)
        self.assertEqual(artifacts.pin_counts.get("behaviour:sword", 0), 1)
        self.assertEqual(artifacts.pin_counts.get("behaviour:sword-v2", 0), 0)

        with self.assertRaises(ReplacementError):
            world.hot_replace_behavior(
                thing_id="thing:sword",
                attachment_id="attach:sword",
                new_implementation_id="behaviour:sword-v2",
                migration=lambda old: {"swing_count": old["swings"]},
                continuation_map={},
            )
        self.assertEqual(world.resident["thing:sword"].behaviors["attach:sword"], before)

    def test_sg008_cancelled_load_has_no_live_visibility_and_retry_reuses_cache(self) -> None:
        repo = ArtifactRepository()
        repo.add("dep", kind="asset", revision="1", payload=b"dependency")
        repo.add(
            "root",
            kind="definition",
            revision="1",
            payload=b"root",
            dependencies=(DependencyEdge("dep", "required"),),
        )
        artifacts = ArtifactManager(repo)

        cancelled = artifacts.acquire(["root"], cancel_after_verifications=1)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(artifacts.resident_artifacts, set())
        fetches_after_cancel = sum(repo.fetch_count.values())
        self.assertEqual(fetches_after_cancel, 1)

        retried = artifacts.acquire(["root"])
        self.assertEqual(retried.status, "published")
        self.assertEqual(artifacts.resident_artifacts, {"dep", "root"})
        # The verified blob from the cancelled attempt was not downloaded again.
        self.assertEqual(sum(repo.fetch_count.values()), 2)

    def test_sg009_exact_declarative_dependency_cycle_publishes_as_closure(self) -> None:
        repo = ArtifactRepository()
        repo.add(
            "a",
            kind="definition",
            revision="1",
            payload=b"a",
            dependencies=(DependencyEdge("b", "required"),),
        )
        repo.add(
            "b",
            kind="definition",
            revision="1",
            payload=b"b",
            dependencies=(DependencyEdge("a", "required"),),
        )
        artifacts = ArtifactManager(repo)
        result = artifacts.acquire(["a"])
        self.assertEqual(result.status, "published")
        self.assertEqual(artifacts.resident_artifacts, {"a", "b"})

    def test_sg010_nested_public_interface_survives_unload_reload_and_rechunk(self) -> None:
        repo, artifacts = self.make_repo()
        world = StreamingWorld(artifacts)

        group = ThingRecord(
            thing_id="thing:door-group",
            physical_chunk="chunk:A",
            public_ports={"port:open": ("thing:door-leaf", "port:open-internal")},
        )
        leaf = ThingRecord(
            thing_id="thing:door-leaf",
            physical_chunk="chunk:A",
        )
        controller = ThingRecord(
            thing_id="thing:controller",
            connections={"door": ("thing:door-group", "port:open")},
        )
        world.create(group)
        world.create(leaf)
        world.create(controller)

        world.unload(["thing:door-group", "thing:door-leaf"])
        world.storage["thing:door-group"].physical_chunk = "chunk:Z"
        world.storage["thing:door-leaf"].physical_chunk = "chunk:Z"

        self.assertEqual(world.status("thing:door-group"), "known_unloaded")
        self.assertEqual(
            world.resident["thing:controller"].connections["door"],
            ("thing:door-group", "port:open"),
        )

        result = world.load(["thing:door-group", "thing:door-leaf"])
        self.assertEqual(result.status, "published")
        self.assertEqual(
            world.resident["thing:door-group"].public_ports["port:open"],
            ("thing:door-leaf", "port:open-internal"),
        )
        self.assertEqual(
            world.resident["thing:controller"].connections["door"],
            ("thing:door-group", "port:open"),
        )
        self.assertEqual(world.resident["thing:door-group"].physical_chunk, "chunk:Z")

    def test_sg011_semantic_detach_retains_or_discards_state_explicitly(self) -> None:
        repo, artifacts = self.make_repo()
        world = StreamingWorld(artifacts)
        thing = ThingRecord(
            thing_id="thing:tool",
            behaviors={
                "attach:one": BehaviorAttachment(
                    attachment_id="attach:one",
                    implementation_id="behaviour:sword",
                    revision=1,
                    private_schema=1,
                    private_state={"swings": 11},
                ),
                "attach:two": BehaviorAttachment(
                    attachment_id="attach:two",
                    implementation_id="behaviour:weather",
                    revision=1,
                    private_schema=1,
                    private_state={"ticks": 7},
                ),
            },
        )
        world.create(thing)

        world.detach_behavior("thing:tool", "attach:one", state_policy="retain_capsule")
        retained = world.resident["thing:tool"].detached_capsules["attach:one"]
        self.assertEqual(retained.private_state, {"swings": 11})
        self.assertNotIn("attach:one", world.resident["thing:tool"].behaviors)

        world.detach_behavior("thing:tool", "attach:two", state_policy="discard_state")
        self.assertNotIn("attach:two", world.resident["thing:tool"].behaviors)
        self.assertNotIn("attach:two", world.resident["thing:tool"].detached_capsules)

    def test_sg012_migration_capsule_reacquires_dependencies_without_host_context(self) -> None:
        repo, source_artifacts = self.make_repo()
        source = StreamingWorld(source_artifacts)
        source.create(
            ThingRecord(
                thing_id="thing:migrant",
                state={"hp": 42},
                context={
                    "peer_id": 19,
                    "capability_grants": ["grant:http"],
                    "engine_handle": "GodotNode@1",
                },
                behaviors={
                    "attach:sword": BehaviorAttachment(
                        attachment_id="attach:sword",
                        implementation_id="behaviour:sword",
                        revision=1,
                        private_schema=1,
                        private_state={"swings": 2},
                    )
                },
            )
        )

        capsule = canonical_capsule_roundtrip(
            source.export_migration_capsule(["thing:migrant"])
        )
        encoded = str(capsule)
        self.assertNotIn("grant:http", encoded)
        self.assertNotIn("GodotNode@1", encoded)
        self.assertNotIn("peer_id", encoded)

        destination_artifacts = ArtifactManager(repo)
        destination = StreamingWorld(destination_artifacts)
        result = destination.import_migration_capsule(capsule)

        self.assertEqual(result.status, "published")
        self.assertIn("thing:migrant", destination.resident)
        migrant = destination.resident["thing:migrant"]
        self.assertEqual(migrant.state, {"hp": 42})
        self.assertEqual(migrant.context, {})
        self.assertEqual(
            migrant.behaviors["attach:sword"].private_state,
            {"swings": 2},
        )
        self.assertTrue(destination_artifacts.is_resident("behaviour:sword"))


if __name__ == "__main__":
    unittest.main()
