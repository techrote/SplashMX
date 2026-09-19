from __future__ import annotations
import unittest
from dataclasses import replace

from package_model import (
    AssetRevision, CapabilityPolicy, CapabilityRequest, DependencyRequirement,
    PackageError, PackageRepository, PackageRevision, Project, Resolver, Version,
    frozen_scope,
)


def pkg(pid, version, revision, digest, *, deps=(), caps=(), ports=("port:main",), props=("value",), schema=1):
    return PackageRevision(
        package_id=pid, version=Version.parse(version), revision_id=revision,
        content_digest=digest, byte_size=1000, root_definition_id=f"def:{pid[4:]}",
        root_definition_revision=f"defrev:{revision}", element_ids=(f"element:{pid[4:]}",),
        public_ports=ports, public_properties=props, dependencies=deps,
        capabilities=caps, assets=(), state_schema=schema, required_features=("ir:v1",),
        source_visibility="linked", remix_permission="restricted", license_expression="MIT",
        attribution=("fixture",), provenance=("fixture:smx013",), signature_key_ids=(),
    )


class BoundaryTests(unittest.TestCase):
    def test_conflicting_transitive_ranges_fail_instead_of_nondeterministic_multi_version_mix(self):
        repo = PackageRepository()
        repo.add(pkg("pkg:shared", "1.5.0", "rev:s15", "sha256:s15"))
        repo.add(pkg("pkg:shared", "2.1.0", "rev:s21", "sha256:s21"))
        repo.add(pkg("pkg:left", "1.0.0", "rev:l", "sha256:l",
                     deps=(DependencyRequirement("pkg:shared", "^1.0.0"),)))
        repo.add(pkg("pkg:right", "1.0.0", "rev:r", "sha256:r",
                     deps=(DependencyRequirement("pkg:shared", "^2.0.0"),)))
        repo.add(pkg("pkg:root", "1.0.0", "rev:root", "sha256:root",
                     deps=(DependencyRequirement("pkg:left", "^1.0.0"),
                           DependencyRequirement("pkg:right", "^1.0.0"))))
        with self.assertRaisesRegex(PackageError, "version_conflict"):
            Resolver(repo).resolve("pkg:root", "^1.0.0")

    def test_optional_dependency_without_fallback_is_manifest_error(self):
        repo = PackageRepository()
        with self.assertRaisesRegex(PackageError, "optional_dependency_requires_fallback"):
            repo.add(pkg("pkg:root", "1.0.0", "rev:r", "sha256:r",
                         deps=(DependencyRequirement("pkg:optional", "^1.0.0", "optional"),)))

    def test_malformed_version_range_fails_before_resolution(self):
        repo = PackageRepository()
        with self.assertRaisesRegex(PackageError, "invalid_version"):
            repo.add(pkg("pkg:root", "1.0.0", "rev:r", "sha256:r",
                         deps=(DependencyRequirement("pkg:x", ">=1"),)))

    def test_duplicate_dependency_identity_rejected(self):
        repo = PackageRepository()
        deps = (DependencyRequirement("pkg:x", "^1.0.0"),
                DependencyRequirement("pkg:x", "^1.1.0"))
        with self.assertRaisesRegex(PackageError, "duplicate_dependency"):
            repo.add(pkg("pkg:root", "1.0.0", "rev:r", "sha256:r", deps=deps))

    def test_required_dependency_revocation_is_not_downgraded_to_optional(self):
        repo = PackageRepository()
        repo.add(pkg("pkg:dep", "1.0.0", "rev:d", "sha256:d"))
        repo.add(pkg("pkg:root", "1.0.0", "rev:r", "sha256:r",
                     deps=(DependencyRequirement("pkg:dep", "^1.0.0"),)))
        with self.assertRaisesRegex(PackageError, "revoked_package"):
            Resolver(repo, revoked_revisions={("pkg:dep", "rev:d")}).resolve("pkg:root", "^1.0.0")

    def test_optional_dependency_revocation_uses_only_declared_fallback(self):
        repo = PackageRepository()
        repo.add(pkg("pkg:dep", "1.0.0", "rev:d", "sha256:d"))
        repo.add(pkg("pkg:root", "1.0.0", "rev:r", "sha256:r",
                     deps=(DependencyRequirement("pkg:dep", "^1.0.0", "optional", fallback="static"),)))
        resolution = Resolver(repo, revoked_revisions={("pkg:dep", "rev:d")}).resolve("pkg:root", "^1.0.0")
        self.assertEqual(resolution.optional_fallbacks[("pkg:root", "pkg:dep")], "static")

    def test_migration_exception_rolls_back_every_instance_and_lock(self):
        repo = PackageRepository(); repo.add(pkg("pkg:root", "1.0.0", "rev:1", "sha256:1", schema=1))
        policy = CapabilityPolicy(); project = Project()
        project.install(Resolver(repo).resolve("pkg:root", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:a", package_id="pkg:root", persistent_state={"n": 1})
        project.add_instance(thing_id="thing:b", package_id="pkg:root", persistent_state={"n": 2})
        repo.add(pkg("pkg:root", "1.1.0", "rev:11", "sha256:11", schema=2))
        def migrator(state):
            if state["n"] == 2:
                raise PackageError("migration_fixture_failure")
            return {"n": state["n"], "v": 2}
        before = {key: dict(inst.persistent_state) for key, inst in project.instances.items()}
        with self.assertRaisesRegex(PackageError, "migration_fixture_failure"):
            project.update(Resolver(repo).resolve("pkg:root", "^1.0.0"), policy,
                           state_migrators={("pkg:root", 1, 2): migrator})
        self.assertEqual(project.resolution.lock["pkg:root"].revision_id, "rev:1")
        self.assertEqual({key: inst.persistent_state for key, inst in project.instances.items()}, before)

    def test_new_dependency_capability_cannot_be_laundered_through_update(self):
        repo = PackageRepository(); repo.add(pkg("pkg:root", "1.0.0", "rev:1", "sha256:1"))
        policy = CapabilityPolicy(); policy.grant("pkg:root", "network.http", ["origin:https://api.example"])
        project = Project(); project.install(Resolver(repo).resolve("pkg:root", "^1.0.0"), policy)
        cap = CapabilityRequest("network.http", frozen_scope(["origin:https://api.example"]), required=True)
        repo.add(pkg("pkg:dep", "1.0.0", "rev:d", "sha256:d", caps=(cap,)))
        repo.add(pkg("pkg:root", "1.1.0", "rev:11", "sha256:11",
                     deps=(DependencyRequirement("pkg:dep", "^1.0.0"),)))
        with self.assertRaisesRegex(PackageError, "capability_denied.*pkg:dep"):
            project.update(Resolver(repo).resolve("pkg:root", "^1.0.0"), policy)
        self.assertEqual(project.resolution.lock["pkg:root"].revision_id, "rev:1")

    def test_live_grant_cannot_be_encoded_as_package_capability_request_shape(self):
        cap_fields = set(CapabilityRequest.__dataclass_fields__)
        forbidden = {"grant_id", "issuer", "token", "host_handle", "expires_at", "delegable"}
        self.assertTrue(cap_fields.isdisjoint(forbidden))

    def test_asset_bundle_requires_provenance_and_license_even_inside_package(self):
        broken = AssetRevision("asset:x", "sha256:x", "source:x", ("x.wav",),
                               ("audio",), (), "", ("none",))
        signed = pkg("pkg:root", "1.0.0", "rev:r", "sha256:r")
        with self.assertRaisesRegex(PackageError, "incomplete_asset_revision"):
            replace(signed, assets=(broken,)).validate()


if __name__ == "__main__":
    unittest.main()
