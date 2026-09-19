from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import publishing_model as pm


class BoundaryTests(unittest.TestCase):
    def test_release_id_collision_cannot_rebind_existing_immutable_release(self):
        reg = pm.ShareRegistry()
        reg.add_release(pm.HostedRelease("r:1", "c:1", "cr:1", "stable"))
        with self.assertRaisesRegex(pm.PublishError, "release_identity_collision"):
            reg.add_release(pm.HostedRelease("r:1", "c:1", "cr:2", "stable"))

    def test_invalid_runtime_target_rejected(self):
        with self.assertRaisesRegex(pm.PublishError, "invalid_runtime_target"):
            pm.GenericPlayer(pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "console-from-future", (1,), (1,), frozenset()))

    def test_corrupt_asset_bytes_fail_before_activate(self):
        blob = b"good"
        ar = pm.ProtectedAssetRevision("asset:a", pm.digest_bytes(blob), "src:a", "meta", "audio:mono", "prov", "CC0", "source-original")
        project = pm.EditableProject("p", "pr", "c", {}, 1, 1, assets=(pm.AssetUse(ar, "simulation_required"),))
        creation = pm.Publisher().publish(project)
        player = pm.GenericPlayer(pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "headless", (1,), (1,), frozenset()))
        with self.assertRaisesRegex(pm.PublishError, "blob_digest_mismatch"):
            player.prepare(creation, {ar.blob_digest: b"evil"})
        self.assertEqual(player.activation_count, 0)

    def test_dependency_size_amplification_is_rejected(self):
        expected = b"abc"
        lock = pm.LockedDependency("pkg:x", "rev:x", pm.digest_bytes(expected), len(expected))
        project = pm.EditableProject("p", "pr", "c", {}, 1, 1, dependencies=(lock,))
        creation = pm.Publisher().publish(project)
        player = pm.GenericPlayer(pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "web", (1,), (1,), frozenset()))
        with self.assertRaisesRegex(pm.PublishError, "blob_size_mismatch"):
            player.prepare(creation, {lock.blob_digest: expected + b"amplified"})

    def test_required_extension_is_not_downgraded_to_optional(self):
        project = pm.EditableProject("p", "pr", "c", {}, 1, 1, required_extensions={"ext:must-understand": {"v": 1}})
        creation = pm.Publisher().publish(project)
        player = pm.GenericPlayer(pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "web", (1,), (1,), frozenset()))
        with self.assertRaisesRegex(pm.PublishError, "required_extension_unsupported"):
            player.prepare(creation, {})

    def test_migration_loop_is_bounded_and_rejected(self):
        project = pm.EditableProject("p", "pr", "c", {}, 1, 1)
        creation = pm.Publisher().publish(project)
        runtime = pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "web", (3,), (1,), frozenset())
        migrations = (
            pm.Migration(1, 2, True, lambda c: pm.replace(c, schema_version=2)),
            pm.Migration(2, 1, True, lambda c: pm.replace(c, schema_version=1)),
        )
        with self.assertRaisesRegex(pm.PublishError, "migration_cycle"):
            pm.GenericPlayer(runtime).prepare(creation, {}, migrations=migrations)

    def test_world_save_cannot_switch_creation_lineage(self):
        a = pm.Publisher().publish(pm.EditableProject("p1", "pr1", "c1", {}, 1, 1))
        b = pm.Publisher().publish(pm.EditableProject("p2", "pr2", "c2", {}, 1, 1))
        world = pm.WorldSave("w", "wr", a.creation_id, a.creation_revision_id, 1, {})
        with self.assertRaisesRegex(pm.PublishError, "world_creation_mismatch"):
            pm.validate_world_basis(world, b)

    def test_canonical_manifest_cannot_smuggle_capability_handle_nested(self):
        project = pm.EditableProject("p", "pr", "c", {"thing": {"state": {"capability_handle": "opaque"}}}, 1, 1)
        with self.assertRaisesRegex(pm.PublishError, "engine_identity_leak"):
            pm.Publisher().publish(project)

    def test_optional_presentation_asset_can_be_absent_without_affecting_semantic_digest(self):
        ar = pm.ProtectedAssetRevision("asset:fx", pm.digest_bytes(b"fx"), "src:fx", "meta", "visual", "prov", "CC0", "source-original")
        p = pm.EditableProject("p", "pr", "c", {}, 1, 1, assets=(pm.AssetUse(ar, "presentation_optional"),))
        creation = pm.Publisher().publish(p)
        runtime = pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "web", (1,), (1,), frozenset())
        plan = pm.GenericPlayer(runtime).prepare(creation, {})
        self.assertEqual(plan.omitted_assets, ("asset:fx",))
        self.assertEqual(plan.creation.semantic_digest, creation.semantic_digest)

    def test_headless_projection_does_not_strip_simulation_dependency(self):
        data = b"logic-package"
        lock = pm.LockedDependency("pkg:logic", "rev:1", pm.digest_bytes(data), len(data))
        p = pm.EditableProject("p", "pr", "c", {}, 1, 1, dependencies=(lock,))
        creation = pm.Publisher().publish(p)
        runtime = pm.RuntimeContract("r", "1", pm.digest_bytes(b"r"), "headless", (1,), (1,), frozenset())
        with self.assertRaisesRegex(pm.PublishError, "required_blob_missing"):
            pm.GenericPlayer(runtime).prepare(creation, {})


if __name__ == "__main__":
    unittest.main()
