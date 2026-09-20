from __future__ import annotations

import unittest

from splashmx.packages.core import (
    CatalogSnapshot,
    DependencyKind,
    DependencySpec,
    MappingPackageSource,
    PackageError,
    PackageSystem,
    Requirement,
    ResolutionLock,
    resolve_packages,
)
from tests.production.test_smx035 import locked, manifest, package_bytes, row


class SMX035ExactDependencyLockTests(unittest.TestCase):
    def test_same_count_forged_child_revision_is_rejected_before_migration(self):
        child1 = manifest("pkg-child-lock", "rev-child-lock-1", "1.0.0")
        child2 = manifest("pkg-child-lock", "rev-child-lock-2", "1.1.0", comp=child1.root_component)
        dependency = DependencySpec(child1.package_id, Requirement.parse("^1.0.0"))
        parent = manifest("pkg-parent-lock", "rev-parent-lock", "1.0.0", deps=(dependency,))
        child1_bytes = package_bytes(child1)
        parent_bytes = package_bytes(parent)
        forged_parent = locked(parent, parent_bytes, children=(child2.package_revision_id,))
        lock = ResolutionLock(
            "cat-lock-forged",
            {
                parent.package_id: forged_parent,
                child1.package_id: locked(child1, child1_bytes),
            },
        )
        migration_called: list[bool] = []
        system = PackageSystem(
            source=MappingPackageSource(
                {
                    str(parent.package_revision_id): parent_bytes,
                    str(child1.package_revision_id): child1_bytes,
                }
            ),
            migration_prepare=lambda old, new: migration_called.append(True),
        )
        with self.assertRaises(PackageError) as cm:
            system.apply_lock(lock)
        self.assertEqual(cm.exception.code, "package.lock_dependency_mismatch")
        self.assertEqual(migration_called, [])
        self.assertEqual(system.state.lock.catalog_snapshot_id, "empty")

    def test_locked_child_version_must_satisfy_manifest_requirement(self):
        child1 = manifest("pkg-child-version", "rev-child-version-1", "1.0.0")
        child2 = manifest("pkg-child-version", "rev-child-version-2", "2.0.0", comp=child1.root_component)
        dependency = DependencySpec(child1.package_id, Requirement.parse("=1.0.0"))
        parent = manifest("pkg-parent-version", "rev-parent-version", "1.0.0", deps=(dependency,))
        child2_bytes = package_bytes(child2)
        parent_bytes = package_bytes(parent)
        lock = ResolutionLock(
            "cat-lock-version",
            {
                parent.package_id: locked(parent, parent_bytes, children=(child2.package_revision_id,)),
                child2.package_id: locked(child2, child2_bytes),
            },
        )
        system = PackageSystem(
            source=MappingPackageSource(
                {
                    str(parent.package_revision_id): parent_bytes,
                    str(child2.package_revision_id): child2_bytes,
                }
            )
        )
        with self.assertRaises(PackageError) as cm:
            system.apply_lock(lock)
        self.assertEqual(cm.exception.code, "package.lock_dependency_mismatch")
        self.assertEqual(system.state.lock.catalog_snapshot_id, "empty")


class SMX035DependencyModeBoundaryTests(unittest.TestCase):
    def test_manifest_declared_optional_dependency_is_resolved_when_available(self):
        optional = manifest("pkg-optional-nested", "rev-optional-nested", "1.0.0")
        optional_bytes = package_bytes(optional)
        optional_dep = DependencySpec(
            optional.package_id,
            Requirement.parse("=1.0.0"),
            DependencyKind.OPTIONAL,
            "without-optional",
        )
        parent = manifest("pkg-parent-optional", "rev-parent-optional", "1.0.0", deps=(optional_dep,))
        parent_bytes = package_bytes(parent)
        snapshot = CatalogSnapshot(
            "cat-nested-optional",
            (row(parent, parent_bytes), row(optional, optional_bytes)),
        )
        lock = resolve_packages(
            snapshot,
            (DependencySpec(parent.package_id, Requirement.parse("=1.0.0")),),
        )
        self.assertIn(optional.package_id, lock.packages)
        self.assertEqual(
            lock.require(optional.package_id).package_revision_id,
            optional.package_revision_id,
        )

    def test_manifest_declared_optional_failure_does_not_damage_required_closure(self):
        missing = DependencySpec(
            manifest("pkg-unused-template", "rev-unused-template", "1.0.0").package_id,
            Requirement.parse("=1.0.0"),
        )
        optional = manifest(
            "pkg-optional-broken",
            "rev-optional-broken",
            "1.0.0",
            deps=(missing,),
        )
        optional_bytes = package_bytes(optional)
        optional_dep = DependencySpec(
            optional.package_id,
            Requirement.parse("=1.0.0"),
            DependencyKind.OPTIONAL,
            "without-broken-optional",
        )
        parent = manifest("pkg-parent-stable", "rev-parent-stable", "1.0.0", deps=(optional_dep,))
        parent_bytes = package_bytes(parent)
        snapshot = CatalogSnapshot(
            "cat-nested-optional-failure",
            (row(parent, parent_bytes), row(optional, optional_bytes)),
        )
        lock = resolve_packages(
            snapshot,
            (DependencySpec(parent.package_id, Requirement.parse("=1.0.0")),),
        )
        self.assertIn(parent.package_id, lock.packages)
        self.assertNotIn(optional.package_id, lock.packages)
        self.assertEqual(lock.require(parent.package_id).package_revision_id, parent.package_revision_id)

    def test_required_plus_lazy_incoming_edges_are_never_order_dependent_lazy(self):
        child = manifest("pkg-shared-mode", "rev-shared-mode", "1.0.0")
        child_bytes = package_bytes(child)
        required_edge = DependencySpec(child.package_id, Requirement.parse("=1.0.0"), DependencyKind.REQUIRED)
        lazy_edge = DependencySpec(child.package_id, Requirement.parse("=1.0.0"), DependencyKind.LAZY)
        parent_required = manifest("pkg-a-required", "rev-a-required", "1.0.0", deps=(required_edge,))
        parent_lazy = manifest("pkg-z-lazy", "rev-z-lazy", "1.0.0", deps=(lazy_edge,))
        required_bytes = package_bytes(parent_required)
        lazy_bytes = package_bytes(parent_lazy)
        roots = (
            DependencySpec(parent_required.package_id, Requirement.parse("=1.0.0")),
            DependencySpec(parent_lazy.package_id, Requirement.parse("=1.0.0")),
        )
        for rows in (
            (row(parent_required, required_bytes), row(parent_lazy, lazy_bytes), row(child, child_bytes)),
            (row(parent_lazy, lazy_bytes), row(child, child_bytes), row(parent_required, required_bytes)),
        ):
            lock = resolve_packages(CatalogSnapshot("cat-mode-order", rows), roots)
            self.assertFalse(lock.require(child.package_id).lazy)


if __name__ == "__main__":
    unittest.main()
