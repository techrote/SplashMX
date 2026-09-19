from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import publishing_model as pm


def asset(data: bytes = b"sprite", asset_id: str = "asset:hero", role: str = "presentation_required"):
    rev = pm.ProtectedAssetRevision(
        asset_id=asset_id,
        blob_digest=pm.digest_bytes(data),
        source_id="source:hero-original",
        source_metadata="image/png;640x480",
        media_semantics="visual:srgb:premultiplied",
        provenance="author-import:2026-09-19",
        licence="CC0-1.0",
        derivation="source-original",
    )
    return pm.AssetUse(rev, role)


def dependency(data: bytes = b"component"):
    return pm.LockedDependency("pkg:clock", "pkgrev:clock:1", pm.digest_bytes(data), len(data))


def project(**changes):
    base = dict(
        project_id="project:demo",
        project_revision_id="projectrev:demo:7",
        creation_id="creation:demo",
        canonical_records={"things": {"thing:hero": {"x": 10, "y": 20}}},
        schema_version=2,
        ir_version=3,
        required_features=("logic.bounded",),
        optional_features=("audio.reverb",),
        dependencies=(dependency(),),
        assets=(asset(),),
        capability_requests=(pm.CapabilityRequest("clipboard.write", False),),
        network_declaration={"mode": "topology-independent", "replicated": ["thing:hero.position"]},
        optional_extensions={"future.pretty_hint": {"v": 1}},
        required_extensions={},
    )
    base.update(changes)
    return pm.EditableProject(**base)


def runtime(target="web", *, schema=(2,), ir=(3,), features=frozenset({"logic.bounded", "render.2d"}), build=b"runtime", ext=frozenset()):
    return pm.RuntimeContract(
        runtime_id="runtime:splashmx-generic",
        runtime_version="0.14-test",
        build_digest=pm.digest_bytes(build),
        target=target,
        supported_schema_versions=tuple(schema),
        supported_ir_versions=tuple(ir),
        features=frozenset(features),
        understood_optional_extensions=frozenset(ext),
    )


def blobs_for(p):
    out = {p.dependencies[0].blob_digest: b"component"}
    for use in p.assets:
        data = b"sprite" if use.revision.asset_id == "asset:hero" else b"data"
        out[use.revision.blob_digest] = data
    return out


class PublishingTests(unittest.TestCase):
    def test_ordinary_publish_is_deterministic_and_invokes_no_export_tool(self):
        publisher = pm.Publisher()
        one = publisher.publish(project())
        two = publisher.publish(project())
        self.assertEqual(one, two)
        self.assertEqual(one.creation_revision_id, two.creation_revision_id)
        self.assertEqual(publisher.export_tool_invocations, 0)

    def test_mutable_project_revision_is_not_published_creation_revision(self):
        pub = pm.Publisher().publish(project())
        self.assertNotEqual(pub.source_project_revision_id, pub.creation_revision_id)
        self.assertEqual(pub.creation_id, "creation:demo")

    def test_web_native_headless_share_one_canonical_creation_revision(self):
        pub = pm.Publisher().publish(project())
        blob_store = blobs_for(project())
        plans = []
        for target in ("web", "native", "headless"):
            features = {"logic.bounded", "render.2d"} if target != "headless" else {"logic.bounded"}
            plan = pm.GenericPlayer(runtime(target, features=frozenset(features))).prepare(pub, blob_store)
            plans.append(plan)
        self.assertEqual({p.creation.creation_revision_id for p in plans}, {pub.creation_revision_id})
        self.assertIn("asset:hero", plans[2].omitted_assets)

    def test_required_future_feature_fails_before_activation(self):
        pub = pm.Publisher().publish(project(required_features=("logic.bounded", "render.xr.future")))
        player = pm.GenericPlayer(runtime())
        with self.assertRaisesRegex(pm.PublishError, "required_feature_unsupported"):
            player.prepare(pub, blobs_for(project()))
        self.assertEqual(player.activation_count, 0)

    def test_unknown_optional_feature_is_omitted_not_canonical_rewrite(self):
        pub = pm.Publisher().publish(project(optional_features=("audio.reverb", "render.sparkles.future")))
        player = pm.GenericPlayer(runtime())
        plan = player.prepare(pub, blobs_for(project()))
        self.assertIn("render.sparkles.future", plan.omitted_features)
        self.assertEqual(plan.creation.creation_revision_id, pub.creation_revision_id)

    def test_unknown_required_extension_fails_closed(self):
        pub = pm.Publisher().publish(project(required_extensions={"future.required": {"v": 1}}))
        player = pm.GenericPlayer(runtime())
        with self.assertRaisesRegex(pm.PublishError, "required_extension_unsupported"):
            player.prepare(pub, blobs_for(project()))
        self.assertEqual(player.activation_count, 0)

    def test_optional_extension_does_not_require_understanding(self):
        pub = pm.Publisher().publish(project(optional_extensions={"future.note": {"opaque": True}}))
        plan = pm.GenericPlayer(runtime()).prepare(pub, blobs_for(project()))
        self.assertEqual(plan.creation.optional_extensions["future.note"]["opaque"], True)

    def test_capability_free_schema_migration_can_stage_before_launch(self):
        pub = pm.Publisher().publish(project(schema_version=1))
        migration = pm.Migration(1, 2, True, lambda c: pm.replace(c, schema_version=2))
        player = pm.GenericPlayer(runtime(schema=(2,)))
        plan = player.prepare(pub, blobs_for(project()), migrations=(migration,))
        self.assertEqual(plan.migration_path, ((1, 2),))
        self.assertEqual(plan.creation.creation_revision_id, pub.creation_revision_id)

    def test_migration_cannot_require_capability(self):
        pub = pm.Publisher().publish(project(schema_version=1))
        migration = pm.Migration(1, 2, False, lambda c: pm.replace(c, schema_version=2))
        player = pm.GenericPlayer(runtime(schema=(2,)))
        with self.assertRaisesRegex(pm.PublishError, "migration_requires_capability"):
            player.prepare(pub, blobs_for(project()), migrations=(migration,))
        self.assertEqual(player.activation_count, 0)

    def test_migration_cannot_rewrite_creation_identity(self):
        pub = pm.Publisher().publish(project(schema_version=1))
        migration = pm.Migration(1, 2, True, lambda c: pm.replace(c, schema_version=2, creation_revision_id="evil"))
        with self.assertRaisesRegex(pm.PublishError, "migration_rewrites_creation_identity"):
            pm.GenericPlayer(runtime(schema=(2,))).prepare(pub, blobs_for(project()), migrations=(migration,))

    def test_exact_locked_dependency_is_verified_before_activation(self):
        pub = pm.Publisher().publish(project())
        player = pm.GenericPlayer(runtime())
        bad = blobs_for(project())
        bad[pub.dependencies[0].blob_digest] = b"different"
        with self.assertRaises(pm.PublishError) as ctx:
            player.prepare(pub, bad)
        self.assertIn(ctx.exception.code, {"blob_size_mismatch", "blob_digest_mismatch"})
        self.assertEqual(player.activation_count, 0)

    def test_no_floating_dependency_substitution(self):
        pub = pm.Publisher().publish(project())
        player = pm.GenericPlayer(runtime())
        other = {pm.digest_bytes(b"new-compatible-version"): b"new-compatible-version", pub.assets[0].revision.blob_digest: b"sprite"}
        with self.assertRaisesRegex(pm.PublishError, "required_blob_missing"):
            player.prepare(pub, other)

    def test_required_capability_denied_before_activation(self):
        pub = pm.Publisher().publish(project(capability_requests=(pm.CapabilityRequest("camera.capture", True),)))
        player = pm.GenericPlayer(runtime())
        with self.assertRaisesRegex(pm.PublishError, "required_capability_denied"):
            player.prepare(pub, blobs_for(project()))
        self.assertEqual(player.activation_count, 0)

    def test_optional_capability_denial_is_explicit(self):
        pub = pm.Publisher().publish(project())
        plan = pm.GenericPlayer(runtime()).prepare(pub, blobs_for(project()))
        self.assertEqual(plan.denied_optional_capabilities, ("clipboard.write",))

    def test_headless_omits_presentation_bytes_but_keeps_descriptor_and_identity(self):
        p = project()
        pub = pm.Publisher().publish(p)
        server = pm.GenericPlayer(runtime("headless", features=frozenset({"logic.bounded"})))
        blob_store = {p.dependencies[0].blob_digest: b"component"}
        plan = server.prepare(pub, blob_store)
        self.assertEqual(plan.omitted_assets, ("asset:hero",))
        self.assertEqual(pub.assets[0].revision.source_id, "source:hero-original")
        self.assertEqual(plan.creation.creation_revision_id, pub.creation_revision_id)

    def test_headless_cannot_strip_simulation_required_asset(self):
        sim = asset(data=b"data", asset_id="asset:navmesh", role="simulation_required")
        pub = pm.Publisher().publish(project(assets=(sim,)))
        blob_store = {dependency().blob_digest: b"component"}
        with self.assertRaisesRegex(pm.PublishError, "required_blob_missing"):
            pm.GenericPlayer(runtime("headless", features=frozenset({"logic.bounded"}))).prepare(pub, blob_store)

    def test_partial_protected_asset_revision_is_rejected(self):
        broken = pm.AssetUse(pm.ProtectedAssetRevision("asset:x", pm.digest_bytes(b"x"), "source:x", "meta", "audio:stereo", "", "CC0-1.0", "source-original"), "presentation_required")
        with self.assertRaisesRegex(pm.PublishError, "invalid_protected_asset_revision"):
            pm.Publisher().publish(project(assets=(broken,)))

    def test_target_projection_never_mutates_protected_source_audio_provenance(self):
        audio = pm.AssetUse(pm.ProtectedAssetRevision("asset:music", pm.digest_bytes(b"data"), "source:master.wav", "wav:48k24", "audio:stereo:48k", "recording-session:A", "CC-BY-4.0", "source-original"), "presentation_required")
        pub = pm.Publisher().publish(project(assets=(audio,)))
        before = pub.assets[0].revision.record()
        plan = pm.GenericPlayer(runtime("headless", features=frozenset({"logic.bounded"}))).prepare(pub, {dependency().blob_digest: b"component"})
        self.assertEqual(plan.creation.assets[0].revision.record(), before)

    def test_engine_identity_is_rejected_from_publish_manifest(self):
        with self.assertRaisesRegex(pm.PublishError, "engine_identity_leak"):
            pm.Publisher().publish(project(canonical_records={"thing:a": {"NodePath": "/root/A"}}))

    def test_world_save_is_separate_and_requires_explicit_basis_migration(self):
        pub = pm.Publisher().publish(project())
        world = pm.WorldSave("world:1", "worldrev:1", pub.creation_id, pub.creation_revision_id, 1, {"score": 7})
        pm.validate_world_basis(world, pub)
        pub2 = pm.Publisher().publish(project(project_revision_id="projectrev:8", canonical_records={"things": {"thing:hero": {"x": 11}}}))
        with self.assertRaisesRegex(pm.PublishError, "world_migration_required"):
            pm.validate_world_basis(world, pub2)

    def test_world_save_rejects_transient_peer_or_host_handles(self):
        pub = pm.Publisher().publish(project())
        world = pm.WorldSave("world:1", "worldrev:1", pub.creation_id, pub.creation_revision_id, 1, {"peer_id": 42})
        with self.assertRaisesRegex(pm.PublishError, "transient_context_in_world_save"):
            pm.validate_world_basis(world, pub)

    def test_hosted_alias_resolves_to_immutable_release_and_can_retarget_without_rewriting_old(self):
        registry = pm.ShareRegistry()
        a = pm.HostedRelease("release:a", "creation:demo", "creationrev:a", "stable")
        b = pm.HostedRelease("release:b", "creation:demo", "creationrev:b", "stable")
        registry.add_release(a); registry.add_release(b)
        registry.point_alias("play/demo", a.release_id)
        resolved_a = registry.resolve("play/demo")
        registry.point_alias("play/demo", b.release_id)
        self.assertEqual(resolved_a, a)
        self.assertEqual(registry.resolve("release:a"), a)
        self.assertEqual(registry.resolve("play/demo"), b)

    def test_offline_bundle_uses_exact_runtime_and_exact_cached_closure(self):
        p = project()
        pub = pm.Publisher().publish(p)
        contract = runtime()
        player = pm.GenericPlayer(contract)
        bundle = pm.OfflineBundle(pub, contract.build_digest, blobs_for(p))
        plan = player.launch_offline(bundle)
        self.assertEqual(plan.creation.creation_revision_id, pub.creation_revision_id)

    def test_offline_bundle_missing_locked_bytes_fails_without_resolve(self):
        p = project()
        pub = pm.Publisher().publish(p)
        contract = runtime()
        bundle = pm.OfflineBundle(pub, contract.build_digest, {pub.assets[0].revision.blob_digest: b"sprite"})
        with self.assertRaisesRegex(pm.PublishError, "required_blob_missing"):
            pm.GenericPlayer(contract).launch_offline(bundle)

    def test_offline_bundle_does_not_silently_use_different_runtime(self):
        p = project(); pub = pm.Publisher().publish(p)
        player = pm.GenericPlayer(runtime(build=b"runtime-A"))
        bundle = pm.OfflineBundle(pub, pm.digest_bytes(b"runtime-B"), blobs_for(p))
        with self.assertRaisesRegex(pm.PublishError, "offline_runtime_mismatch"):
            player.launch_offline(bundle)

    def test_reproducibility_record_pins_content_runtime_target_and_lock(self):
        p = project(); pub = pm.Publisher().publish(p)
        plan = pm.GenericPlayer(runtime()).prepare(pub, blobs_for(p))
        record = plan.reproducibility_record()
        self.assertEqual(record["creation_revision_id"], pub.creation_revision_id)
        self.assertEqual(record["runtime_build_digest"], runtime().build_digest)
        self.assertEqual(record["dependency_lock"][0]["package_revision_id"], "pkgrev:clock:1")

    def test_same_published_network_declaration_survives_topology_targets(self):
        p = project(); pub = pm.Publisher().publish(p)
        web = pm.GenericPlayer(runtime("web")).prepare(pub, blobs_for(p))
        server = pm.GenericPlayer(runtime("headless", features=frozenset({"logic.bounded"}))).prepare(pub, {p.dependencies[0].blob_digest: b"component"})
        self.assertEqual(web.creation.network_declaration, server.creation.network_declaration)

    def test_per_creation_build_is_not_ordinary_fallback(self):
        self.assertFalse(pm.per_creation_build_allowed(ordinary_content=True, trusted_extension_requirement=True))
        self.assertFalse(pm.per_creation_build_allowed(ordinary_content=False, trusted_extension_requirement=False))
        self.assertTrue(pm.per_creation_build_allowed(ordinary_content=False, trusted_extension_requirement=True))

    def test_activate_is_separate_from_prepare(self):
        p = project(); pub = pm.Publisher().publish(p)
        player = pm.GenericPlayer(runtime())
        plan = player.prepare(pub, blobs_for(p))
        self.assertEqual(player.activation_count, 0)
        result = player.activate(plan)
        self.assertTrue(result["active"])
        self.assertEqual(player.activation_count, 1)


if __name__ == "__main__":
    unittest.main()
