from __future__ import annotations

from dataclasses import replace
import unittest

from splashmx.canonical.core import AssetId, CanonicalDocument, DefinitionId, ProjectId, ProjectRevisionId
from splashmx.canonical.serialization import CanonicalProjectRevision, ProtectedAssetRevision, encode_canonical_cbor
from splashmx.packages.bundle import package_bundle_for_manifest
from splashmx.packages.model import (
    DependencySpec, LockedPackage, PackageId, PackageManifest, PackageRevisionId,
    PortableComponent, Requirement, ResolutionLock, SemVer, digest,
)
from splashmx.publishing.generic import (
    CreationId, CreationRevisionId, GenericPlayer, HostedReleaseId, HostedReleaseStore,
    OfflineLibrary, PublicationError, PublishedCreation, bind_world_save,
    decode_creation_manifest, derive_target_media, publish_creation, validate_target_media,
    validate_world_save_basis,
)
from splashmx.runtime.lifecycle import WorldRevisionId, WorldSaveId, WorldSaveSnapshot


def asset(name: str = "song", marker: bytes = b"source") -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId(f"asset-{name}"),
        source_digest=digest(marker),
        source_identity={"filename": f"{name}.wav"},
        source_metadata={"sample_rate": 48000, "channels": 2},
        media_semantics={"loop": True, "gain_db": 0},
        provenance={"author": "fixture"},
        licence_attribution={"licence": "CC0", "attribution": "fixture"},
        derivation_lineage=({"operation": "original-import"},),
    )


def project(revision: str = "project-rev-1", *, protected: ProtectedAssetRevision | None = None) -> CanonicalProjectRevision:
    doc = CanonicalDocument(ProjectId("project-main"), ProjectRevisionId(revision))
    assets = {} if protected is None else {protected.asset_id: protected}
    return CanonicalProjectRevision(doc, assets)


def component(name: str) -> PortableComponent:
    interface = digest(encode_canonical_cbor([]))
    return PortableComponent(DefinitionId(f"def-{name}"), 1, f"root-{name}", (), interface)


def package(name: str, *, deps=(), protected_assets=()) -> tuple[PackageManifest, bytes]:
    manifest = PackageManifest(
        PackageId(f"pkg-{name}"),
        PackageRevisionId(f"pkg-rev-{name}-1"),
        SemVer.parse("1.0.0"),
        component(name),
        tuple(deps),
        (),
        (),
        tuple(protected_assets),
        {"source": "fixture"},
        {"publisher": "fixture"},
        {"licence": "fixture"},
        {"remix": "allowed"},
        ({"parent": "fixture"},),
        (),
    )
    return manifest, package_bundle_for_manifest(manifest, {})


def one_package_creation(*, project_revision: str = "project-rev-1", protected=None, lazy=False):
    manifest, bundle = package("clock")
    locked = LockedPackage(
        manifest.package_id, manifest.package_revision_id, manifest.human_version,
        digest(bundle), len(bundle), (), lazy,
    )
    lock = ResolutionLock("catalog-1", {manifest.package_id: locked})
    published = publish_creation(
        CreationId("creation-main"),
        project(project_revision, protected=protected),
        lock,
        {manifest.package_revision_id: bundle},
    )
    return published, manifest, bundle, lock


class SMX036PublicationTests(unittest.TestCase):
    def test_publish_is_deterministic_immutable_data_not_a_build(self):
        published1, _, _, _ = one_package_creation()
        published2, _, _, _ = one_package_creation()
        self.assertEqual(published1.manifest_bytes, published2.manifest_bytes)
        self.assertEqual(dict(published1.blobs), dict(published2.blobs))
        manifest = decode_creation_manifest(published1.manifest_bytes)
        self.assertIsInstance(manifest.creation_revision_id, CreationRevisionId)
        self.assertEqual(manifest.player_profile, "splashmx.generic-player/1")

    def test_same_creation_revision_loads_hosted_and_exact_offline(self):
        published, _, _, _ = one_package_creation()
        player = GenericPlayer()
        hosted = HostedReleaseStore()
        revision = hosted.publish_release(HostedReleaseId("release-1"), published)
        hosted.retarget_alias("latest", HostedReleaseId("release-1"))
        offline = OfflineLibrary(GenericPlayer())
        self.assertEqual(offline.install(published), revision)

        hosted_seen = []
        offline_seen = []
        player.load_hosted(hosted, "latest", lambda prepared: hosted_seen.append(prepared.manifest.creation_revision_id))
        player.load_offline(offline, revision, lambda prepared: offline_seen.append(prepared.manifest.creation_revision_id))
        self.assertEqual(hosted_seen, [revision])
        self.assertEqual(offline_seen, [revision])

    def test_friendly_alias_can_retarget_without_mutating_immutable_releases(self):
        first, _, _, _ = one_package_creation(project_revision="project-rev-1")
        second, _, _, _ = one_package_creation(project_revision="project-rev-2")
        store = HostedReleaseStore()
        first_rev = store.publish_release(HostedReleaseId("release-1"), first)
        second_rev = store.publish_release(HostedReleaseId("release-2"), second)
        self.assertNotEqual(first_rev, second_rev)
        store.retarget_alias("play", HostedReleaseId("release-1"))
        self.assertEqual(store.resolve("play"), first_rev)
        store.retarget_alias("play", HostedReleaseId("release-2"))
        self.assertEqual(store.resolve("play"), second_rev)
        self.assertEqual(store.resolve(HostedReleaseId("release-1")), first_rev)
        self.assertEqual(decode_creation_manifest(store.get(first_rev).manifest_bytes).creation_revision_id, first_rev)

    def test_worldsave_creation_and_alias_roles_remain_distinct(self):
        published, _, _, _ = one_package_creation()
        prepared = GenericPlayer().prepare(published)
        snapshot = WorldSaveSnapshot(
            WorldSaveId("world-1"),
            WorldRevisionId("world-rev-1"),
            prepared.manifest.project_id,
            prepared.manifest.project_revision_id,
            0, 1, 7, (),
        )
        basis = bind_world_save(snapshot, prepared)
        self.assertNotEqual(type(basis.world_save_id), type(basis.creation_revision_id))
        self.assertEqual(basis.creation_revision_id, prepared.manifest.creation_revision_id)
        validate_world_save_basis(snapshot, basis, prepared)

        wrong = replace(basis, creation_revision_id=CreationRevisionId("sha256:" + "0" * 64))
        with self.assertRaises(PublicationError) as cm:
            validate_world_save_basis(snapshot, wrong, prepared)
        self.assertEqual(cm.exception.code, "publication.world_basis_mismatch")

    def test_target_derivative_is_private_and_cannot_rebind_asset_semantics(self):
        canonical_asset = asset()
        published, _, _, _ = one_package_creation(protected=canonical_asset)
        prepared = GenericPlayer().prepare(published)
        before = prepared.project.assets[canonical_asset.asset_id]
        derivative = derive_target_media(prepared, canonical_asset.asset_id, "web-opus", b"target-bytes")
        validate_target_media(prepared, derivative)
        self.assertEqual(derivative.canonical_asset_revision_digest, canonical_asset.revision_digest)
        self.assertEqual(prepared.project.assets[canonical_asset.asset_id], before)

        forged = replace(derivative, canonical_asset_revision_digest="sha256:" + "f" * 64)
        with self.assertRaises(PublicationError) as cm:
            validate_target_media(prepared, forged)
        self.assertEqual(cm.exception.code, "publication.target_media_basis_mismatch")

    def test_exact_offline_missing_revision_never_floats(self):
        published, _, _, _ = one_package_creation()
        library = OfflineLibrary(GenericPlayer())
        installed = library.install(published)
        self.assertIsNotNone(library.get(installed))
        with self.assertRaises(PublicationError) as cm:
            library.get(CreationRevisionId("sha256:" + "1" * 64))
        self.assertEqual(cm.exception.code, "publication.offline_unavailable")

    def test_lazy_package_is_still_part_of_exact_offline_publication_closure(self):
        manifest, bundle = package("lazy")
        lock = ResolutionLock(
            "catalog-lazy",
            {manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle), (), True,
            )},
        )
        with self.assertRaises(PublicationError) as cm:
            publish_creation(CreationId("creation-lazy"), project(), lock, {})
        self.assertEqual(cm.exception.code, "publication.incomplete_closure")


if __name__ == "__main__":
    unittest.main()
