from __future__ import annotations

from dataclasses import replace
import unittest

from splashmx.canonical.core import AssetId, CanonicalDocument, DefinitionId, ProjectId, ProjectRevisionId
from splashmx.canonical.serialization import (
    CanonicalProjectRevision,
    ProtectedAssetRevision,
    decode_canonical_cbor,
    encode_canonical_cbor,
    serialize_project,
)
from splashmx.distribution.service import (
    DistributionError,
    DistributionService,
    OperationalHealth,
    RuntimeArtifact,
    RuntimeRegistry,
    build_protected_disclosure,
    build_recovery_archive,
    import_offline_bundle,
    import_recovery_archive,
    plan_native_package,
    validate_protected_disclosure,
)
from splashmx.packages.bundle import package_bundle_for_manifest
from splashmx.packages.model import (
    LockedPackage,
    PackageId,
    PackageManifest,
    PackageRevisionId,
    PortableComponent,
    ResolutionLock,
    SemVer,
    digest,
)
from splashmx.publishing.generic import CreationId, GenericPlayer, decode_creation_manifest, publish_creation
from splashmx.runtime.lifecycle import WorldSaveId, _with_computed_revision, serialize_world_save


def protected_asset(name: str = "song") -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId(f"asset-{name}"),
        source_digest=digest(f"source-{name}".encode()),
        source_identity={"filename": f"{name}.wav", "logical_name": name},
        source_metadata={"sample_rate": 48000, "channels": 2, "format": "wav"},
        media_semantics={"loop": True, "gain_db": 0},
        provenance={"author": "fixture", "origin": "recorded-source"},
        licence_attribution={"licence": "CC0", "attribution": "fixture"},
        derivation_lineage=({"operation": "original-import"},),
    )


def project(revision: str = "project-rev-1", *, asset: ProtectedAssetRevision | None = None) -> CanonicalProjectRevision:
    document = CanonicalDocument(ProjectId("project-main"), ProjectRevisionId(revision))
    return CanonicalProjectRevision(document, {} if asset is None else {asset.asset_id: asset})


def component(name: str) -> PortableComponent:
    return PortableComponent(
        DefinitionId(f"def-{name}"),
        1,
        f"root-{name}",
        (),
        digest(encode_canonical_cbor([])),
    )


def package(name: str = "clock") -> tuple[PackageManifest, bytes]:
    manifest = PackageManifest(
        PackageId(f"pkg-{name}"),
        PackageRevisionId(f"pkg-rev-{name}-1"),
        SemVer.parse("1.0.0"),
        component(name),
        (), (), (), (),
        {"source": "fixture"},
        {"publisher": "fixture"},
        {"licence": "fixture"},
        {"remix": "allowed"},
        ({"parent": "fixture"},),
        (),
    )
    return manifest, package_bundle_for_manifest(manifest, {})


def creation(*, project_revision: str = "project-rev-1", asset: ProtectedAssetRevision | None = None):
    manifest, bundle = package()
    locked = LockedPackage(
        manifest.package_id,
        manifest.package_revision_id,
        manifest.human_version,
        digest(bundle),
        len(bundle),
        (),
        False,
    )
    lock = ResolutionLock("catalog-1", {manifest.package_id: locked})
    authored = project(project_revision, asset=asset)
    published = publish_creation(
        CreationId("creation-main"),
        authored,
        lock,
        {manifest.package_revision_id: bundle},
    )
    return authored, published


def runtime(marker: bytes = b"generic-runtime-v1") -> RuntimeArtifact:
    return RuntimeArtifact.create("splashmx.generic-player/1", marker)


class SMX050DistributionTests(unittest.TestCase):
    def test_hosted_release_is_exact_creation_runtime_and_disclosure_not_alias_or_url(self):
        asset = protected_asset()
        _, published = creation(asset=asset)
        service = DistributionService()
        record = service.publish_release(published, runtime())
        before = record.release_id

        service.retarget_alias("play/latest", record.release_id)
        service.record_cdn_location(record.creation_manifest_digest, "https://cdn-a.example/creation")
        service.record_cdn_location(record.creation_manifest_digest, "https://cdn-b.example/creation")

        self.assertEqual(service.resolve_alias("play/latest").release_id, before)
        self.assertEqual(service.get_release(before).release_id, before)
        self.assertEqual(
            service.locations(record.creation_manifest_digest),
            ("https://cdn-a.example/creation", "https://cdn-b.example/creation"),
        )
        self.assertNotIn("cdn-a.example", str(before))
        self.assertNotIn("play/latest", str(before))

    def test_alias_retarget_does_not_rebind_immutable_releases(self):
        service = DistributionService()
        _, first = creation(project_revision="project-rev-1")
        _, second = creation(project_revision="project-rev-2")
        one = service.publish_release(first, runtime())
        two = service.publish_release(second, runtime())
        self.assertNotEqual(one.release_id, two.release_id)
        self.assertEqual(service.retarget_alias("play", one.release_id), 1)
        self.assertEqual(service.resolve_alias("play").release_id, one.release_id)
        self.assertEqual(service.retarget_alias("play", two.release_id), 2)
        self.assertEqual(service.resolve_alias("play").release_id, two.release_id)
        self.assertEqual(service.get_release(one.release_id), one)

    def test_cache_policy_separates_immutable_objects_from_mutable_aliases(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime())
        service.retarget_alias("play", record.release_id)
        immutable = service.immutable_cache_headers(record.creation_manifest_digest)
        alias = service.alias_cache_headers("play")
        self.assertIn("immutable", immutable["Cache-Control"])
        self.assertEqual(alias["Cache-Control"], "no-cache")
        old_etag = alias["ETag"]
        service.retarget_alias("play", record.release_id)
        self.assertNotEqual(service.alias_cache_headers("play")["ETag"], old_etag)

    def test_cloud_loss_cannot_invalidate_already_installed_exact_content_or_local_project(self):
        authored, published = creation(asset=protected_asset())
        serialized = serialize_project(authored)
        service = DistributionService()
        record = service.publish_release(published, runtime())
        bundle = service.export_offline_bundle(record.release_id)
        installed = import_offline_bundle(bundle)

        service.set_service_available(False, "simulated cloud outage")
        with self.assertRaises(DistributionError) as caught:
            service.resolve_alias("missing")
        self.assertEqual(caught.exception.code, "distribution.service_unavailable")

        # The exact install and authored project bytes are self-contained and do not
        # consult service state after acquisition.
        reloaded = import_offline_bundle(installed.bundle_bytes)
        self.assertEqual(reloaded.record.creation_revision_id, installed.record.creation_revision_id)
        self.assertEqual(serialize_project(authored).root_manifest, serialized.root_manifest)
        self.assertEqual(dict(serialize_project(authored).shards), dict(serialized.shards))

    def test_offline_bundle_tampered_blob_fails_before_install(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime())
        value = decode_canonical_cbor(service.export_offline_bundle(record.release_id))
        value["creation_blobs"][0]["payload"] += b"tamper"
        with self.assertRaises(DistributionError) as caught:
            import_offline_bundle(encode_canonical_cbor(value))
        self.assertEqual(caught.exception.code, "distribution.creation_integrity")

    def test_offline_bundle_tampered_runtime_fails_closed_without_newer_fallback(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime(b"runtime-old"))
        # A newer artifact existing in the registry is not permission to float.
        service.runtime_registry.register(runtime(b"runtime-new"))
        raw = service.export_offline_bundle(record.release_id)
        installed = import_offline_bundle(raw)
        self.assertEqual(installed.runtime.payload, b"runtime-old")

        value = decode_canonical_cbor(raw)
        value["runtime"]["payload"] = b"runtime-forged"
        with self.assertRaises(DistributionError) as caught:
            import_offline_bundle(encode_canonical_cbor(value))
        self.assertEqual(caught.exception.code, "distribution.runtime_integrity")

    def test_runtime_revocation_overrides_historical_distribution(self):
        service = DistributionService()
        _, published = creation()
        old_runtime = runtime(b"retained-runtime")
        record = service.publish_release(published, old_runtime)
        service.runtime_registry.revoke(old_runtime.digest)
        with self.assertRaises(DistributionError) as caught:
            service.export_offline_bundle(record.release_id)
        self.assertEqual(caught.exception.code, "distribution.runtime_revoked")

    def test_runtime_registry_never_resolves_wrong_profile_or_ineligible_artifact(self):
        registry = RuntimeRegistry()
        item = runtime()
        registry.register(item)
        with self.assertRaises(DistributionError) as wrong_profile:
            registry.resolve("splashmx.generic-player/other", item.digest)
        self.assertEqual(wrong_profile.exception.code, "distribution.runtime_unavailable")
        registry.set_eligible(item.digest, False)
        with self.assertRaises(DistributionError) as ineligible:
            registry.resolve(item.profile, item.digest)
        self.assertEqual(ineligible.exception.code, "distribution.runtime_ineligible")

    def test_protected_disclosure_is_complete_atomic_and_rejects_field_mixing(self):
        asset = protected_asset()
        raw = build_protected_disclosure((asset,))
        restored = validate_protected_disclosure(raw)
        self.assertEqual(restored, (asset,))

        value = decode_canonical_cbor(raw)
        value["assets"][0]["source_metadata"]["channels"] = 1
        with self.assertRaises(DistributionError) as caught:
            validate_protected_disclosure(encode_canonical_cbor(value))
        self.assertEqual(caught.exception.code, "distribution.invalid_disclosure")

    def test_offline_protected_disclosure_matches_exact_creation_and_cannot_substitute_revision(self):
        asset = protected_asset()
        service = DistributionService()
        _, published = creation(asset=asset)
        record = service.publish_release(published, runtime())
        value = decode_canonical_cbor(service.export_offline_bundle(record.release_id))
        disclosure = decode_canonical_cbor(value["protected_disclosure"])
        disclosure["assets"][0]["provenance"] = {"author": "attacker"}
        forged = encode_canonical_cbor(disclosure)
        value["protected_disclosure"] = forged
        value["disclosure_digest"] = digest(forged)
        # Re-signing only distribution metadata cannot create a different valid
        # protected Asset revision because the canonical revision digest is intact.
        with self.assertRaises(DistributionError):
            import_offline_bundle(encode_canonical_cbor(value))

    def test_recovery_archive_round_trip_preserves_project_offline_and_worldsave_bytes(self):
        asset = protected_asset()
        authored, published = creation(asset=asset)
        serialized = serialize_project(authored)
        service = DistributionService()
        record = service.publish_release(published, runtime())
        offline = service.export_offline_bundle(record.release_id)
        world = _with_computed_revision(
            WorldSaveId("world-backup"),
            authored.document.project_id,
            authored.document.project_revision_id,
            4,
            9,
            1234,
            (),
        )
        world_raw = serialize_world_save(world)

        archive = build_recovery_archive(
            projects=(serialized,),
            offline_bundles=(offline,),
            world_saves=(world,),
        )
        restored = import_recovery_archive(archive)
        self.assertEqual(restored.projects[0].root_manifest, serialized.root_manifest)
        self.assertEqual(dict(restored.projects[0].shards), dict(serialized.shards))
        self.assertEqual(restored.offline_installs[0].bundle_bytes, offline)
        self.assertEqual(restored.world_saves[0].raw, world_raw)
        self.assertEqual(restored.world_saves[0].snapshot.world_revision_id, world.world_revision_id)

    def test_recovery_archive_tamper_is_revalidated_by_production_boundaries(self):
        authored, published = creation()
        service = DistributionService()
        record = service.publish_release(published, runtime())
        archive = build_recovery_archive(
            projects=(serialize_project(authored),),
            offline_bundles=(service.export_offline_bundle(record.release_id),),
        )
        value = decode_canonical_cbor(archive)
        offline = decode_canonical_cbor(value["offline_bundles"][0])
        offline["runtime"]["payload"] += b"tamper"
        value["offline_bundles"][0] = encode_canonical_cbor(offline)
        with self.assertRaises(DistributionError):
            import_recovery_archive(encode_canonical_cbor(value))

    def test_native_package_plan_is_only_physical_wrapper_over_exact_install(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime())
        installed = import_offline_bundle(service.export_offline_bundle(record.release_id))
        plan = plan_native_package(installed, "linux-native")
        self.assertEqual(plan.creation_revision_id, record.creation_revision_id)
        self.assertEqual(plan.release_id, record.release_id)
        self.assertEqual(plan.runtime_digest, installed.runtime.digest)
        self.assertEqual(plan.offline_bundle_digest, digest(installed.bundle_bytes))

    def test_operational_outage_recovery_is_bounded_and_cannot_change_semantic_identity(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime())
        service.record_dependency_state("collaboration", "unavailable", "relay outage")
        service.record_dependency_state("network", "degraded", "TURN fallback")
        service.record_dependency_state("collaboration", "available", "recovered")
        self.assertEqual(service.health.state("collaboration"), "available")
        self.assertEqual(service.get_release(record.release_id).creation_revision_id, record.creation_revision_id)

        health = OperationalHealth(max_events=3)
        for index in range(5):
            health.record("hosting", "degraded", str(index))
        self.assertEqual(len(health.events), 3)
        self.assertEqual([row.detail for row in health.events], ["2", "3", "4"])

    def test_cache_location_and_alias_boundaries_fail_typed(self):
        service = DistributionService()
        _, published = creation()
        record = service.publish_release(published, runtime())
        with self.assertRaises(DistributionError) as alias:
            service.retarget_alias("a" * 257, record.release_id)
        self.assertEqual(alias.exception.code, "distribution.invalid_alias")
        with self.assertRaises(DistributionError) as location:
            service.record_cdn_location(record.creation_manifest_digest, "file:///tmp/object")
        self.assertEqual(location.exception.code, "distribution.invalid_location")

    def test_distribution_metrics_make_retention_cost_measurable_without_changing_identity(self):
        service = DistributionService()
        _, published = creation()
        item = runtime(b"runtime-cost-evidence")
        record = service.publish_release(published, item)
        service.retarget_alias("play", record.release_id)
        metrics = service.metrics()
        self.assertGreater(metrics.immutable_object_bytes, 0)
        self.assertEqual(metrics.retained_runtime_bytes, len(item.payload))
        self.assertEqual(metrics.release_count, 1)
        self.assertEqual(metrics.alias_count, 1)


if __name__ == "__main__":
    unittest.main()
