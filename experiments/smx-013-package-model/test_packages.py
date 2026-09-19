from __future__ import annotations
import unittest
from dataclasses import replace

from package_model import (
    AssetRevision, Cache, CapabilityPolicy, CapabilityRequest, DependencyRequirement,
    LocalDefinition, PackageError, PackageRepository, PackageRevision, Project, Resolver,
    Version, authorize, capability_plan, delegate_capability, frozen_scope,
    promote_local_definition, reconcile_concurrent_asset_replacements,
    replace_asset_revision, validate_offline, verify_observed_digest,
)


def asset(asset_id="asset:bell", digest="sha256:bell-v1", source="source:bell-v1"):
    return AssetRevision(
        asset_id=asset_id, digest=digest, source_identity=source,
        source_metadata=("original.wav", "48000Hz"), media_semantics=("audio", "mono"),
        provenance=("publisher:alice", "capture:field"), license_expression="CC-BY-4.0",
        derivation=("trim:none",),
    )


def package(package_id="pkg:lamp", version="1.0.0", revision="pkgrev:lamp-1",
            digest="sha256:lamp-1", definition="def:lamp", defrev="defrev:lamp-1",
            deps=(), caps=(), ports=("port:toggle",), props=("brightness",),
            elements=("element:bulb",), assets=(), schema=1, signed_by=(),
            source_visibility="included", remix_permission="allowed"):
    return PackageRevision(
        package_id=package_id, version=Version.parse(version), revision_id=revision,
        content_digest=digest, byte_size=2048, root_definition_id=definition,
        root_definition_revision=defrev, element_ids=elements, public_ports=ports,
        public_properties=props, dependencies=deps, capabilities=caps, assets=assets,
        state_schema=schema, required_features=("ir:v1",), source_visibility=source_visibility,
        remix_permission=remix_permission, license_expression="MIT", attribution=("Alice",),
        provenance=("source-repo:example",), signature_key_ids=signed_by,
    )


class PackageContractTests(unittest.TestCase):
    def test_local_definition_promotion_preserves_semantic_identities(self):
        local = LocalDefinition("def:lamp", "defrev:lamp-1",
                                ("element:bulb", "element:switch"),
                                ("port:toggle",), ("brightness",),
                                ("thing:lamp-root", "thing:bulb"))
        result = promote_local_definition(local, package_id="pkg:lamp", version="1.0.0",
                                          package_revision_id="pkgrev:lamp-1",
                                          content_digest="sha256:lamp-1")
        self.assertEqual(result.package.root_definition_id, local.definition_id)
        self.assertEqual(result.preserved_element_ids, local.element_ids)
        self.assertEqual(result.preserved_port_ids, local.public_ports)
        self.assertEqual(result.preserved_first_instance_thing_ids, local.first_instance_thing_ids)
        self.assertNotEqual(result.package.package_id, result.package.root_definition_id)

    def test_repository_rejects_same_version_with_different_revision(self):
        repo = PackageRepository(); repo.add(package())
        with self.assertRaisesRegex(PackageError, "ambiguous_version"):
            repo.add(package(revision="pkgrev:other", digest="sha256:other"))

    def test_repository_rejects_revision_identity_digest_collision(self):
        repo = PackageRepository(); repo.add(package())
        with self.assertRaisesRegex(PackageError, "revision_identity_collision"):
            repo.add(package(version="1.0.1", digest="sha256:evil"))

    def test_clean_resolution_selects_highest_compatible_then_locks_exact(self):
        repo = PackageRepository()
        repo.add(package(version="1.0.0", revision="pkgrev:1.0.0", digest="sha256:1"))
        repo.add(package(version="1.2.0", revision="pkgrev:1.2.0", digest="sha256:12"))
        repo.add(package(version="2.0.0", revision="pkgrev:2.0.0", digest="sha256:2"))
        entry = Resolver(repo).resolve("pkg:lamp", "^1.0.0").lock["pkg:lamp"]
        self.assertEqual((entry.version, entry.revision_id, entry.digest),
                         ("1.2.0", "pkgrev:1.2.0", "sha256:12"))

    def test_required_dependency_missing_blocks_resolution(self):
        repo = PackageRepository(); repo.add(package(deps=(DependencyRequirement("pkg:clock", "^1.0.0"),)))
        with self.assertRaisesRegex(PackageError, "missing_dependency"):
            Resolver(repo).resolve("pkg:lamp", "^1.0.0")

    def test_optional_dependency_missing_uses_declared_fallback(self):
        repo = PackageRepository()
        dep = DependencyRequirement("pkg:sparkles", "^1.0.0", "optional", fallback="no-sparkles")
        repo.add(package(deps=(dep,)))
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        self.assertEqual(resolution.optional_fallbacks[("pkg:lamp", "pkg:sparkles")], "no-sparkles")
        self.assertNotIn("pkg:sparkles", resolution.packages)

    def test_lazy_dependency_is_recorded_but_not_acquired(self):
        repo = PackageRepository(); dep = DependencyRequirement("pkg:inspector", "^1.0.0", "lazy")
        repo.add(package(deps=(dep,)))
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        self.assertEqual(resolution.lazy_requirements, [("pkg:lamp", dep)])
        self.assertNotIn("pkg:inspector", resolution.packages)

    def test_cycle_is_rejected_before_publication(self):
        repo = PackageRepository()
        repo.add(package(package_id="pkg:a", definition="def:a", revision="rev:a", digest="sha256:a",
                         deps=(DependencyRequirement("pkg:b", "^1.0.0"),)))
        repo.add(package(package_id="pkg:b", definition="def:b", revision="rev:b", digest="sha256:b",
                         deps=(DependencyRequirement("pkg:a", "^1.0.0"),)))
        with self.assertRaisesRegex(PackageError, "dependency_cycle"):
            Resolver(repo).resolve("pkg:a", "^1.0.0")

    def test_dependency_depth_is_bounded(self):
        repo = PackageRepository()
        repo.add(package(package_id="pkg:a", definition="def:a", revision="r:a", digest="sha256:a",
                         deps=(DependencyRequirement("pkg:b", "^1.0.0"),)))
        repo.add(package(package_id="pkg:b", definition="def:b", revision="r:b", digest="sha256:b",
                         deps=(DependencyRequirement("pkg:c", "^1.0.0"),)))
        repo.add(package(package_id="pkg:c", definition="def:c", revision="r:c", digest="sha256:c"))
        with self.assertRaisesRegex(PackageError, "dependency_depth_exceeded"):
            Resolver(repo, max_depth=2).resolve("pkg:a", "^1.0.0")

    def test_dependency_total_bytes_is_bounded(self):
        repo = PackageRepository(); repo.add(package())
        with self.assertRaisesRegex(PackageError, "dependency_bytes_exceeded"):
            Resolver(repo, max_total_bytes=100).resolve("pkg:lamp", "^1.0.0")

    def test_revoked_package_fails_even_when_version_matches(self):
        repo = PackageRepository(); repo.add(package())
        with self.assertRaisesRegex(PackageError, "revoked_package"):
            Resolver(repo, revoked_revisions={("pkg:lamp", "pkgrev:lamp-1")}).resolve("pkg:lamp", "^1.0.0")

    def test_offline_uses_exact_lock_and_cache(self):
        repo = PackageRepository(); repo.add(package())
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        cache = Cache(); cache.add_resolution(resolution); validate_offline(resolution, cache)
        cache.evict(resolution.lock["pkg:lamp"])
        with self.assertRaisesRegex(PackageError, "offline_unavailable"):
            validate_offline(resolution, cache)

    def test_offline_does_not_substitute_another_cached_version(self):
        repo = PackageRepository()
        repo.add(package(version="1.0.0", revision="rev:1", digest="sha256:1"))
        repo.add(package(version="1.2.0", revision="rev:12", digest="sha256:12"))
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        cache = Cache({("pkg:lamp", "rev:1", "sha256:1")})
        with self.assertRaisesRegex(PackageError, "offline_unavailable"):
            validate_offline(resolution, cache)

    def test_digest_substitution_is_rejected(self):
        repo = PackageRepository(); repo.add(package())
        entry = Resolver(repo).resolve("pkg:lamp", "^1.0.0").lock["pkg:lamp"]
        with self.assertRaisesRegex(PackageError, "digest_mismatch"):
            verify_observed_digest(entry, "sha256:attacker")

    def test_capability_plan_attributes_transitive_request(self):
        repo = PackageRepository()
        cap = CapabilityRequest("network.http", frozen_scope(["origin:https://weather.example"]), required=True)
        repo.add(package(package_id="pkg:weather", definition="def:weather", revision="rev:w",
                         digest="sha256:w", caps=(cap,)))
        repo.add(package(deps=(DependencyRequirement("pkg:weather", "^1.0.0"),)))
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        item = [item for item in capability_plan(resolution) if item.package_id == "pkg:weather"][0]
        self.assertEqual(item.attribution_path, ("pkg:lamp", "pkg:weather"))

    def test_parent_capability_grant_is_not_inherited_by_dependency(self):
        repo = PackageRepository()
        cap = CapabilityRequest("network.http", frozen_scope(["origin:https://weather.example"]), required=True)
        repo.add(package(package_id="pkg:weather", definition="def:weather", revision="rev:w",
                         digest="sha256:w", caps=(cap,)))
        repo.add(package(deps=(DependencyRequirement("pkg:weather", "^1.0.0"),)))
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        policy = CapabilityPolicy(); policy.grant("pkg:lamp", "network.http", ["origin:https://weather.example"])
        with self.assertRaisesRegex(PackageError, "capability_denied.*pkg:weather"):
            authorize(resolution, policy)

    def test_required_capability_denial_leaves_existing_project_unchanged(self):
        repo = PackageRepository(); repo.add(package())
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        cap = CapabilityRequest("media.camera", frozen_scope(["facing:user"]), required=True)
        repo.add(replace(package(version="1.1.0", revision="rev:camera", digest="sha256:camera"), capabilities=(cap,)))
        before = project.resolution.lock["pkg:lamp"].revision_id
        with self.assertRaisesRegex(PackageError, "capability_denied"):
            project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        self.assertEqual(project.resolution.lock["pkg:lamp"].revision_id, before)

    def test_optional_capability_can_degrade_without_grant(self):
        repo = PackageRepository()
        cap = CapabilityRequest("clipboard.write", frozen_scope(["mime:text/plain"]), required=False)
        repo.add(package(caps=(cap,)))
        self.assertEqual(authorize(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), CapabilityPolicy()),
                         (("pkg:lamp", "clipboard.write"),))

    def test_signatures_do_not_grant_runtime_capability(self):
        repo = PackageRepository()
        cap = CapabilityRequest("network.http", frozen_scope(["origin:https://example"]), required=True)
        repo.add(package(caps=(cap,), signed_by=("key:trusted-publisher",)))
        with self.assertRaisesRegex(PackageError, "capability_denied"):
            authorize(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), CapabilityPolicy())

    def test_delegation_must_narrow_scope(self):
        result = delegate_capability(source_principal="pkg:host", target_principal="pkg:child",
                                     capability="network.http",
                                     source_scope=frozen_scope(["origin:a", "path:/public"]),
                                     requested_scope=frozen_scope(["origin:a"]), delegable=True)
        self.assertEqual(result.principal, "pkg:child")
        with self.assertRaisesRegex(PackageError, "delegation_widens_scope"):
            delegate_capability(source_principal="pkg:host", target_principal="pkg:child",
                                capability="network.http", source_scope=frozen_scope(["origin:a"]),
                                requested_scope=frozen_scope(["origin:a", "origin:b"]), delegable=True)

    def test_sealed_source_and_remix_policy_do_not_change_execution_trust(self):
        repo = PackageRepository()
        cap = CapabilityRequest("network.http", frozen_scope(["origin:https://example"]), required=True)
        repo.add(package(caps=(cap,), source_visibility="sealed", remix_permission="forbidden",
                         signed_by=("key:publisher",)))
        with self.assertRaisesRegex(PackageError, "capability_denied"):
            authorize(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), CapabilityPolicy())

    def test_compatible_update_preserves_instance_identity_overlay_and_state(self):
        repo = PackageRepository(); repo.add(package())
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp",
                             overlays={"property:brightness": 0.5}, persistent_state={"cycles": 4},
                             protected_ports={"port:toggle"})
        repo.add(package(version="1.1.0", revision="rev:11", digest="sha256:11", defrev="defrev:lamp-2"))
        project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        instance = project.instances["thing:lamp-1"]
        self.assertEqual(instance.thing_id, "thing:lamp-1")
        self.assertEqual(instance.overlays, {"property:brightness": 0.5})
        self.assertEqual(instance.persistent_state, {"cycles": 4})
        self.assertEqual(instance.base_definition_revision, "defrev:lamp-2")

    def test_update_migrates_persistent_state_explicitly(self):
        repo = PackageRepository(); repo.add(package(schema=1))
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp", persistent_state={"count": 2})
        repo.add(package(version="1.1.0", revision="rev:11", digest="sha256:11", defrev="defrev:lamp-2", schema=2))
        project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy,
                       state_migrators={("pkg:lamp", 1, 2): lambda state: {"count": state["count"], "mode": "normal"}})
        self.assertEqual(project.instances["thing:lamp-1"].persistent_state, {"count": 2, "mode": "normal"})

    def test_incompatible_migration_rolls_back_lock_and_instance_state(self):
        repo = PackageRepository(); repo.add(package(schema=1))
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp", persistent_state={"count": 2})
        repo.add(package(version="1.1.0", revision="rev:11", digest="sha256:11", defrev="defrev:lamp-2", schema=2))
        before_lock = project.resolution.lock["pkg:lamp"].revision_id
        before_state = dict(project.instances["thing:lamp-1"].persistent_state)
        with self.assertRaisesRegex(PackageError, "migration_required"):
            project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        self.assertEqual(project.resolution.lock["pkg:lamp"].revision_id, before_lock)
        self.assertEqual(project.instances["thing:lamp-1"].persistent_state, before_state)

    def test_port_removal_conflict_rolls_back(self):
        repo = PackageRepository(); repo.add(package())
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp", protected_ports={"port:toggle"})
        repo.add(package(version="1.1.0", revision="rev:11", digest="sha256:11", defrev="defrev:lamp-2", ports=()))
        with self.assertRaisesRegex(PackageError, "interface_incompatible"):
            project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        self.assertIn("port:toggle", project.resolution.packages["pkg:lamp"].public_ports)

    def test_invalid_overlay_target_blocks_update(self):
        repo = PackageRepository(); repo.add(package(props=("brightness", "temperature")))
        project = Project(); policy = CapabilityPolicy(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp",
                             overlays={"property:temperature": 2700})
        repo.add(package(version="1.1.0", revision="rev:11", digest="sha256:11",
                         defrev="defrev:lamp-2", props=("brightness",)))
        with self.assertRaisesRegex(PackageError, "overlay_incompatible"):
            project.update(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), policy)
        self.assertEqual(project.instances["thing:lamp-1"].overlays["property:temperature"], 2700)

    def test_uninstall_is_blocked_while_instance_uses_package(self):
        repo = PackageRepository(); repo.add(package())
        project = Project(); project.install(Resolver(repo).resolve("pkg:lamp", "^1.0.0"), CapabilityPolicy())
        project.add_instance(thing_id="thing:lamp-1", package_id="pkg:lamp")
        with self.assertRaisesRegex(PackageError, "package_in_use"):
            project.remove_package("pkg:lamp")

    def test_cache_eviction_does_not_rewrite_project_lock_or_identity(self):
        repo = PackageRepository(); repo.add(package())
        resolution = Resolver(repo).resolve("pkg:lamp", "^1.0.0")
        project = Project(); project.install(resolution, CapabilityPolicy())
        cache = Cache(); cache.add_resolution(resolution); cache.evict(resolution.lock["pkg:lamp"])
        self.assertEqual(project.resolution.lock["pkg:lamp"].revision_id, "pkgrev:lamp-1")
        self.assertEqual(project.resolution.packages["pkg:lamp"].root_definition_id, "def:lamp")

    def test_complete_asset_replacement_preserves_asset_id(self):
        original = package(assets=(asset(),)); replacement = asset(digest="sha256:bell-v2", source="source:bell-v2")
        updated = replace_asset_revision(original, replacement)
        self.assertEqual(updated.assets[0].asset_id, "asset:bell")
        self.assertEqual(updated.assets[0].digest, "sha256:bell-v2")
        self.assertEqual(original.assets[0].digest, "sha256:bell-v1")

    def test_incomplete_asset_replacement_is_rejected_without_mutation(self):
        original = package(assets=(asset(),))
        broken = AssetRevision("asset:bell", "sha256:bell-v2", "source:bell-v2", (),
                               ("audio",), ("publisher:bob",), "CC-BY-4.0", ("edit",))
        with self.assertRaisesRegex(PackageError, "incomplete_asset_revision"):
            replace_asset_revision(original, broken)
        self.assertEqual(original.assets[0].digest, "sha256:bell-v1")

    def test_concurrent_asset_replacements_remain_complete_alternatives(self):
        left = asset(digest="sha256:left", source="source:left")
        right = asset(digest="sha256:right", source="source:right")
        alternatives = reconcile_concurrent_asset_replacements(left, right)
        self.assertEqual(alternatives, (left, right))
        self.assertNotEqual(alternatives[0].source_identity, alternatives[1].source_identity)
        self.assertNotEqual(alternatives[0].digest, alternatives[1].digest)


if __name__ == "__main__":
    unittest.main()
