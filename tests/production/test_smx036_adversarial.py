from __future__ import annotations

from dataclasses import replace
import unittest

from splashmx.canonical.core import AssetId
from splashmx.canonical.serialization import ProtectedAssetRevision
from splashmx.packages.model import (
    DependencySpec, LockedPackage, PackageRevisionId, Requirement,
    ResolutionLock, digest,
)
from splashmx.publishing.generic import (
    CreationId, GenericPlayer, HostedReleaseId, HostedReleaseStore,
    PublicationError, PublishedCreation, decode_creation_manifest, publish_creation,
)

from tests.production.test_smx036 import asset, package, project


class SMX036AdversarialTests(unittest.TestCase):
    def test_tampered_creation_manifest_fails_before_activation(self):
        manifest, bundle = package("main")
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        published = publish_creation(CreationId("creation-a"), project(), lock, {manifest.package_revision_id: bundle})
        damaged = bytearray(published.manifest_bytes)
        damaged[-1] ^= 1
        called = []
        player = GenericPlayer()
        with self.assertRaises(PublicationError):
            prepared = player.prepare(PublishedCreation(bytes(damaged), published.blobs))
            player.activate(prepared, lambda _: called.append(True))
        self.assertEqual(called, [])
        self.assertIsNone(player.active)

    def test_tampered_project_blob_fails_before_activation(self):
        manifest, bundle = package("main")
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        published = publish_creation(CreationId("creation-b"), project(), lock, {manifest.package_revision_id: bundle})
        creation = decode_creation_manifest(published.manifest_bytes)
        blobs = dict(published.blobs)
        target = creation.project_manifest.digest
        damaged = bytearray(blobs[target]); damaged[-1] ^= 1
        blobs[target] = bytes(damaged)
        player = GenericPlayer()
        called = []
        with self.assertRaises(PublicationError) as cm:
            prepared = player.prepare(PublishedCreation(published.manifest_bytes, blobs))
            player.activate(prepared, lambda _: called.append(True))
        self.assertEqual(cm.exception.code, "publication.integrity_failure")
        self.assertEqual(called, [])

    def test_tampered_dependency_blob_fails_before_activation(self):
        child, child_bytes = package("child")
        root_dep = DependencySpec(child.package_id, Requirement.parse("=1.0.0"))
        root, root_bytes = package("root", deps=(root_dep,))
        lock = ResolutionLock("cat", {
            child.package_id: LockedPackage(
                child.package_id, child.package_revision_id, child.human_version,
                digest(child_bytes), len(child_bytes),
            ),
            root.package_id: LockedPackage(
                root.package_id, root.package_revision_id, root.human_version,
                digest(root_bytes), len(root_bytes), (child.package_revision_id,),
            ),
        })
        published = publish_creation(
            CreationId("creation-c"), project(), lock,
            {child.package_revision_id: child_bytes, root.package_revision_id: root_bytes},
        )
        creation = decode_creation_manifest(published.manifest_bytes)
        root_ref = next(row for row in creation.package_bundles if row.package_id == root.package_id)
        blobs = dict(published.blobs)
        damaged = bytearray(blobs[root_ref.blob.digest]); damaged[-1] ^= 1
        blobs[root_ref.blob.digest] = bytes(damaged)
        called = []
        player = GenericPlayer()
        with self.assertRaises(PublicationError) as cm:
            prepared = player.prepare(PublishedCreation(published.manifest_bytes, blobs))
            player.activate(prepared, lambda _: called.append(True))
        self.assertEqual(cm.exception.code, "publication.integrity_failure")
        self.assertEqual(called, [])

    def test_floating_dependency_substitution_is_rejected_at_publish(self):
        child, child_bytes = package("child")
        root_dep = DependencySpec(child.package_id, Requirement.parse("=1.0.0"))
        root, root_bytes = package("root", deps=(root_dep,))
        forged_child_revision = PackageRevisionId("pkg-rev-child-forged")
        lock = ResolutionLock("cat", {
            child.package_id: LockedPackage(
                child.package_id, forged_child_revision, child.human_version,
                digest(child_bytes), len(child_bytes),
            ),
            root.package_id: LockedPackage(
                root.package_id, root.package_revision_id, root.human_version,
                digest(root_bytes), len(root_bytes), (forged_child_revision,),
            ),
        })
        with self.assertRaises(PublicationError) as cm:
            publish_creation(
                CreationId("creation-d"), project(), lock,
                {forged_child_revision: child_bytes, root.package_revision_id: root_bytes},
            )
        self.assertEqual(cm.exception.code, "publication.invalid_dependency")

    def test_unknown_required_creation_feature_fails_before_activation(self):
        manifest, bundle = package("feature")
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        published = publish_creation(
            CreationId("creation-e"), project(), lock, {manifest.package_revision_id: bundle},
            required_features=("future-required-feature",),
        )
        player = GenericPlayer(supported_features=())
        called = []
        with self.assertRaises(PublicationError) as cm:
            prepared = player.prepare(published)
            player.activate(prepared, lambda _: called.append(True))
        self.assertEqual(cm.exception.code, "publication.unsupported_feature")
        self.assertEqual(called, [])

    def test_protected_asset_field_mixing_across_project_and_package_is_rejected(self):
        project_asset = asset("shared", b"one")
        competing = ProtectedAssetRevision.create(
            AssetId("asset-shared"),
            source_digest=digest(b"two"),
            source_identity={"filename": "shared.wav"},
            source_metadata={"sample_rate": 44100},
            media_semantics={"loop": False},
            provenance={"author": "other"},
            licence_attribution={"licence": "CC0"},
            derivation_lineage=({"operation": "other-import"},),
        )
        manifest, bundle = package("assetpkg", protected_assets=(competing,))
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        with self.assertRaises(PublicationError) as cm:
            publish_creation(
                CreationId("creation-f"), project(protected=project_asset), lock,
                {manifest.package_revision_id: bundle},
            )
        self.assertEqual(cm.exception.code, "publication.protected_asset_conflict")

    def test_unreferenced_extra_blob_is_rejected_before_activation(self):
        manifest, bundle = package("extra")
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        published = publish_creation(CreationId("creation-g"), project(), lock, {manifest.package_revision_id: bundle})
        blobs = dict(published.blobs)
        extra = b"smuggled"
        blobs[digest(extra)] = extra
        with self.assertRaises(PublicationError) as cm:
            GenericPlayer().prepare(PublishedCreation(published.manifest_bytes, blobs))
        self.assertEqual(cm.exception.code, "publication.unexpected_blob")

    def test_creation_revision_and_release_cannot_be_rebound(self):
        manifest, bundle = package("immut")
        lock = ResolutionLock("cat", {
            manifest.package_id: LockedPackage(
                manifest.package_id, manifest.package_revision_id, manifest.human_version,
                digest(bundle), len(bundle),
            )
        })
        first = publish_creation(CreationId("creation-h"), project("project-rev-1"), lock, {manifest.package_revision_id: bundle})
        second = publish_creation(CreationId("creation-h"), project("project-rev-2"), lock, {manifest.package_revision_id: bundle})
        store = HostedReleaseStore()
        store.publish_release(HostedReleaseId("release-fixed"), first)
        with self.assertRaises(PublicationError) as cm:
            store.publish_release(HostedReleaseId("release-fixed"), second)
        self.assertEqual(cm.exception.code, "publication.immutable_release")

        blobs = dict(first.blobs)
        any_digest = next(iter(blobs))
        blobs[any_digest] = blobs[any_digest] + b"x"
        forged_same_id = PublishedCreation(first.manifest_bytes, blobs)
        with self.assertRaises(PublicationError) as cm:
            store.publish_release(HostedReleaseId("release-copy"), forged_same_id)
        self.assertEqual(cm.exception.code, "publication.immutable_rebind")


if __name__ == "__main__":
    unittest.main()
