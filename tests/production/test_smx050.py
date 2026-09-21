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
from splashmx.distribution.runtime import (
    ContentAddressedCache,
    DistributionError,
    HostedDistribution,
    OfflineDistributionLibrary,
    RuntimeArtifact,
    RuntimeStore,
    ServiceHealth,
    build_native_package,
    export_recovery_archive,
    import_recovery_archive,
    protected_asset_disclosures,
    verify_native_package,
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
from splashmx.publishing.generic import CreationId, GenericPlayer, HostedReleaseId, publish_creation
from splashmx.runtime.lifecycle import WorldRuntime, WorldSaveId, serialize_world_save


def protected_asset() -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId("asset-song"),
        source_digest=digest(b"lossless-source"),
        source_identity={"filename": "song.wav", "logical_name": "theme"},
        source_metadata={"sample_rate": 48000, "channels": 2, "frames": 96000},
        media_semantics={"loop": True, "gain_db": -2, "cue": "intro"},
        provenance={"author": "fixture", "source": "recording"},
        licence_attribution={"licence": "CC0", "attribution": "fixture"},
        derivation_lineage=({"operation": "original-import", "parent": None},),
    )


def project(revision: str = "project-rev-1") -> CanonicalProjectRevision:
    asset = protected_asset()
    return CanonicalProjectRevision(
        CanonicalDocument(ProjectId("project-main"), ProjectRevisionId(revision)),
        {asset.asset_id: asset},
    )


def package() -> tuple[PackageManifest, bytes]:
    interface = digest(encode_canonical_cbor([]))
    component = PortableComponent(DefinitionId("def-clock"), 1, "root-clock", (), interface)
    manifest = PackageManifest(
        PackageId("pkg-clock"),
        PackageRevisionId("pkg-rev-clock-1"),
        SemVer.parse("1.0.0"),
        component,
        (), (), (), (),
        {"source": "fixture"},
        {"publisher": "fixture"},
        {"licence": "fixture"},
        {"remix": "allowed"},
        ({"parent": "fixture"},),
        (),
    )
    return manifest, package_bundle_for_manifest(manifest, {})


def published_creation(revision: str = "project-rev-1"):
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
    return publish_creation(
        CreationId("creation-main"),
        project(revision),
        lock,
        {manifest.package_revision_id: bundle},
    )


def runtime(payload: bytes = b"generic-player-runtime-v1", target: str = "native") -> RuntimeArtifact:
    return RuntimeArtifact(
        "splashmx.generic-player/1",
        target,
        payload,
        {"godot": "4.7.2", "qualification": "smx050-fixture"},
    )


class SMX050DistributionTests(unittest.TestCase):
    def test_hosted_release_binds_exact_creation_and_runtime_while_alias_moves(self):
        runtimes = RuntimeStore()
        first_runtime = runtime()
        second_runtime = runtime(b"generic-player-runtime-v1-patched")
        runtimes.qualify(first_runtime)
        runtimes.qualify(second_runtime)
        hosted = HostedDistribution(runtimes)
        first = published_creation("project-rev-1")
        second = published_creation("project-rev-2")
        first_binding = hosted.publish(
            HostedReleaseId("release-1"), first,
            runtime_profile=first_runtime.profile,
            runtime_digest=first_runtime.digest,
        )
        second_binding = hosted.publish(
            HostedReleaseId("release-2"), second,
            runtime_profile=second_runtime.profile,
            runtime_digest=second_runtime.digest,
        )
        hosted.retarget_alias("latest", HostedReleaseId("release-1"))
        self.assertEqual(hosted.resolve("latest"), first_binding)
        hosted.retarget_alias("latest", HostedReleaseId("release-2"))
        self.assertEqual(hosted.resolve("latest"), second_binding)
        self.assertEqual(hosted.resolve(HostedReleaseId("release-1")), first_binding)
        with self.assertRaises(DistributionError) as caught:
            hosted.publish(
                HostedReleaseId("release-1"), first,
                runtime_profile=second_runtime.profile,
                runtime_digest=second_runtime.digest,
            )
        self.assertEqual(caught.exception.code, "distribution.immutable_release")

    def test_cloud_service_loss_is_typed_and_does_not_break_exact_offline_install(self):
        artifact = runtime()
        services = ServiceHealth()
        runtimes = RuntimeStore()
        runtimes.qualify(artifact)
        hosted = HostedDistribution(runtimes, services=services)
        published = published_creation()
        binding = hosted.publish(
            HostedReleaseId("release-1"), published,
            runtime_profile=artifact.profile,
            runtime_digest=artifact.digest,
        )
        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)

        services.set("hosting", available=False, reason="object-store outage")
        services.set("collaboration", available=False, reason="relay outage")
        services.set("networking", available=False, reason="runtime relay outage")
        with self.assertRaises(DistributionError) as caught:
            hosted.fetch(binding.release_id)
        self.assertEqual(caught.exception.code, "distribution.service_unavailable")

        seen = []
        offline.launch(revision, lambda prepared: seen.append(prepared.manifest.creation_revision_id))
        self.assertEqual(seen, [revision])
        self.assertEqual(len(services.events), 3)

    def test_runtime_revocation_wins_over_hosted_and_local_compatibility(self):
        artifact = runtime()
        published = published_creation()
        runtimes = RuntimeStore()
        runtimes.qualify(artifact)
        hosted = HostedDistribution(runtimes)
        hosted.publish(
            HostedReleaseId("release-1"), published,
            runtime_profile=artifact.profile,
            runtime_digest=artifact.digest,
        )
        runtimes.revoke(artifact.digest)
        with self.assertRaises(DistributionError) as caught:
            hosted.fetch(HostedReleaseId("release-1"))
        self.assertEqual(caught.exception.code, "distribution.runtime_revoked")

        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)
        offline.revoke_runtime(artifact.digest)
        with self.assertRaises(DistributionError) as caught:
            offline.launch(revision, lambda prepared: None)
        self.assertEqual(caught.exception.code, "distribution.runtime_revoked")

    def test_recovery_roundtrip_preserves_project_creation_runtime_worldsave_and_asset(self):
        canonical = project()
        serialized = serialize_project(canonical)
        published = published_creation()
        artifact = runtime()
        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)
        install = offline.get(revision)
        world = WorldRuntime.create(canonical.document, {}, seed=7).snapshot(WorldSaveId("world-main"))

        archive = export_recovery_archive(
            project=serialized,
            installs=(install,),
            world_saves=(world,),
        )
        recovered = import_recovery_archive(archive)
        self.assertEqual(recovered.project, serialized)
        self.assertEqual(len(recovered.installs), 1)
        self.assertEqual(recovered.installs[0], install)
        self.assertEqual(serialize_world_save(recovered.world_saves[0]), serialize_world_save(world))
        before = GenericPlayer().prepare(published).protected_assets[AssetId("asset-song")]
        after = GenericPlayer().prepare(recovered.installs[0].published).protected_assets[AssetId("asset-song")]
        self.assertEqual(after, before)

    def test_recovery_rejects_tampered_runtime_bytes(self):
        published = published_creation()
        artifact = runtime()
        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)
        archive = export_recovery_archive(installs=(offline.get(revision),))
        root = decode_canonical_cbor(archive)
        chunks = root["installs"][0]["runtime_payload_chunks"]
        chunks[0] = bytes(chunks[0]) + b"tamper"
        tampered = encode_canonical_cbor(root)
        with self.assertRaises(DistributionError) as caught:
            import_recovery_archive(tampered)
        self.assertEqual(caught.exception.code, "distribution.runtime_integrity")

    def test_recovery_rejects_tampered_creation_blob(self):
        published = published_creation()
        artifact = runtime()
        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)
        archive = export_recovery_archive(installs=(offline.get(revision),))
        root = decode_canonical_cbor(archive)
        chunks = root["installs"][0]["creation_blobs"][0]["payload_chunks"]
        chunks[0] = bytes(chunks[0]) + b"tamper"
        tampered = encode_canonical_cbor(root)
        with self.assertRaises(DistributionError) as caught:
            import_recovery_archive(tampered)
        self.assertEqual(caught.exception.code, "distribution.creation_integrity")

    def test_protected_asset_disclosure_is_complete_and_indivisible(self):
        published = published_creation()
        expected = GenericPlayer().prepare(published).protected_assets[AssetId("asset-song")]
        rows = protected_asset_disclosures(published)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.asset_id, str(expected.asset_id))
        self.assertEqual(row.revision_digest, expected.revision_digest)
        self.assertEqual(row.source_digest, expected.source_digest)
        self.assertEqual(dict(row.source_identity), dict(expected.source_identity))
        self.assertEqual(dict(row.source_metadata), dict(expected.source_metadata))
        self.assertEqual(dict(row.media_semantics), dict(expected.media_semantics))
        self.assertEqual(dict(row.provenance), dict(expected.provenance))
        self.assertEqual(dict(row.licence_attribution), dict(expected.licence_attribution))
        self.assertEqual(tuple(row.derivation_lineage), tuple(expected.derivation_lineage))

    def test_native_package_preserves_exact_install_and_rejects_unsupported_target(self):
        published = published_creation()
        artifact = runtime(target="native")
        offline = OfflineDistributionLibrary()
        revision = offline.install(published, artifact)
        install = offline.get(revision)
        package = build_native_package(install, target="native")
        self.assertEqual(verify_native_package(package), install)

        with self.assertRaises(DistributionError) as caught:
            build_native_package(install, target="browser")
        self.assertEqual(caught.exception.code, "distribution.native_target_unsupported")

        forged = replace(package, runtime_digest="sha256:" + "0" * 64)
        with self.assertRaises(DistributionError) as caught:
            verify_native_package(forged)
        self.assertEqual(caught.exception.code, "distribution.invalid_native_package")

    def test_cache_eviction_cannot_change_creation_identity(self):
        published = published_creation()
        revision = GenericPlayer().prepare(published).manifest.creation_revision_id
        cache = ContentAddressedCache()
        digest_value = cache.put(published.manifest_bytes)
        self.assertEqual(cache.get(digest_value), published.manifest_bytes)
        cache.evict(digest_value)
        with self.assertRaises(DistributionError) as caught:
            cache.get(digest_value)
        self.assertEqual(caught.exception.code, "distribution.cache_miss")
        self.assertEqual(cache.put(published.manifest_bytes), digest_value)
        self.assertEqual(GenericPlayer().prepare(published).manifest.creation_revision_id, revision)

    def test_retained_runtime_storage_counts_unique_digest_and_explicit_copies(self):
        runtimes = RuntimeStore()
        artifact = runtime()
        runtimes.qualify(artifact)
        runtimes.qualify(artifact)
        self.assertEqual(runtimes.retained_bytes(), len(artifact.payload))
        self.assertEqual(
            runtimes.retained_bytes(copies={artifact.digest: 3}),
            len(artifact.payload) * 3,
        )
        with self.assertRaises(DistributionError) as caught:
            runtimes.retained_bytes(copies={artifact.digest: 0})
        self.assertEqual(caught.exception.code, "distribution.invalid_replica_count")


if __name__ == "__main__":
    unittest.main()
