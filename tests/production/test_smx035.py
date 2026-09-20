from __future__ import annotations

from dataclasses import replace
import struct
import unittest

from splashmx.canonical.core import (
    AssetId, DefinitionElementRecord, DefinitionExposure, DefinitionId, DefinitionRecord,
    ElementId, PortDirection, PortId, PortKind, PortRecord,
)
from splashmx.canonical.serialization import ProtectedAssetRevision, decode_canonical_cbor, encode_canonical_cbor
from splashmx.runtime.streaming import ImmutableArtifactCache
from splashmx.security.capabilities import (
    CapabilityBroker, CapabilityError, CapabilityGrant, CapabilityId, CapabilityScope,
)
from splashmx.packages.core import (
    ArtifactSpec, CatalogRow, CatalogSnapshot, DependencyKind, DependencySpec, LockedPackage,
    MappingPackageSource, PackageCapabilityRequest, PackageError, PackageId, PackageManifest,
    PackageRevisionId, PackageRuntimeState, PackageSystem, PortableComponent, Requirement,
    ResolutionLock, SemVer, SolverLimits, build_spb1, decode_lock, decode_manifest, digest,
    encode_lock, encode_manifest, package_bundle_for_manifest, parse_spb1, principal_for_component,
    promote_definition, resolve_packages, validate_locked_bundle,
)


def D(data: bytes) -> str:
    return digest(data)


def definition(name: str = "clock") -> DefinitionRecord:
    eid = ElementId(f"el-{name}")
    internal = PortId(f"internal-{name}")
    public = PortId(f"public-{name}")
    element = DefinitionElementRecord(
        eid, name, {}, {internal: PortRecord(internal, "tick", PortKind.EVENT, PortDirection.OUT)}
    )
    return DefinitionRecord(
        DefinitionId(f"def-{name}"), 1, eid, {eid: element},
        {public: DefinitionExposure(public, eid, internal)},
    )


def component(name: str = "clock") -> PortableComponent:
    return promote_definition(definition(name))


def manifest(
    pid: str = "pkg-clock", rev: str = "rev-clock-1", version: str = "1.0.0", *,
    deps=(), artifacts=(), requests=(), assets=(), comp: PortableComponent | None = None,
    source_metadata=None,
) -> PackageManifest:
    return PackageManifest(
        PackageId(pid), PackageRevisionId(rev), SemVer.parse(version), comp or component(pid.replace("pkg-", "")),
        tuple(deps), tuple(artifacts), tuple(requests), tuple(assets),
        source_metadata or {"availability": "included"}, {"publisher": "fixture"},
        {"licence": "fixture", "attribution": "fixture"}, {"remix": "allowed"},
        ({"parent": "local-definition"},), (),
    )


def package_bytes(m: PackageManifest, payloads=None) -> bytes:
    return package_bundle_for_manifest(m, payloads or {})


def row(m: PackageManifest, payload: bytes, deps=None, *, revoked=False) -> CatalogRow:
    return CatalogRow(m.package_id, m.package_revision_id, m.human_version, D(payload), len(payload), tuple(m.dependencies if deps is None else deps), revoked)


def locked(m: PackageManifest, payload: bytes, *, children=(), lazy=False) -> LockedPackage:
    return LockedPackage(m.package_id, m.package_revision_id, m.human_version, D(payload), len(payload), tuple(children), lazy)


class SMX035VersionAndResolverTests(unittest.TestCase):
    def test_exact_and_caret_boundaries(self):
        self.assertTrue(Requirement.parse("=1.2.3").matches(SemVer.parse("1.2.3")))
        self.assertFalse(Requirement.parse("=1.2.3").matches(SemVer.parse("1.2.4")))
        caret = Requirement.parse("^1.2.3")
        self.assertTrue(caret.matches(SemVer.parse("1.9.9")))
        self.assertFalse(caret.matches(SemVer.parse("2.0.0")))
        zero = Requirement.parse("^0.2.3")
        self.assertTrue(zero.matches(SemVer.parse("0.2.9")))
        self.assertFalse(zero.matches(SemVer.parse("0.3.0")))

    def test_deterministic_highest_compatible_non_revoked(self):
        m1 = manifest(rev="rev-a-1", version="1.0.0"); b1 = package_bytes(m1)
        m2 = manifest(rev="rev-a-2", version="1.5.0"); b2 = package_bytes(m2)
        m3 = manifest(rev="rev-a-3", version="1.6.0"); b3 = package_bytes(m3)
        snap = CatalogSnapshot("cat-a", (row(m1,b1), row(m3,b3,revoked=True), row(m2,b2)))
        lock = resolve_packages(snap, (DependencySpec(m1.package_id, Requirement.parse("^1.0.0")),))
        self.assertEqual(lock.require(m1.package_id).package_revision_id, m2.package_revision_id)

    def test_conflict_driven_backtracking_finds_coherent_closure(self):
        child1 = manifest("pkg-child","rev-child-1","1.0.0"); bc1 = package_bytes(child1)
        child2 = manifest("pkg-child","rev-child-2","2.0.0"); bc2 = package_bytes(child2)
        p_old_dep = DependencySpec(child1.package_id, Requirement.parse("^1.0.0"))
        p_new_dep = DependencySpec(child1.package_id, Requirement.parse("^2.0.0"))
        parent1 = manifest("pkg-parent","rev-parent-1","1.0.0",deps=(p_old_dep,)); bp1 = package_bytes(parent1)
        parent2 = manifest("pkg-parent","rev-parent-2","1.1.0",deps=(p_new_dep,)); bp2 = package_bytes(parent2)
        snap = CatalogSnapshot("cat-b", (row(parent2,bp2), row(parent1,bp1), row(child1,bc1), row(child2,bc2)))
        roots = (
            DependencySpec(parent1.package_id, Requirement.parse("^1.0.0")),
            DependencySpec(child1.package_id, Requirement.parse("^1.0.0")),
        )
        result = resolve_packages(snap, roots)
        self.assertEqual(result.require(parent1.package_id).package_revision_id, parent1.package_revision_id)
        self.assertEqual(result.require(child1.package_id).package_revision_id, child1.package_revision_id)

    def test_one_revision_per_package_conflict_is_typed(self):
        child1 = manifest("pkg-x","rev-x-1","1.0.0"); b1 = package_bytes(child1)
        child2 = manifest("pkg-x","rev-x-2","2.0.0"); b2 = package_bytes(child2)
        snap = CatalogSnapshot("cat-c", (row(child1,b1), row(child2,b2)))
        roots = (
            DependencySpec(child1.package_id, Requirement.parse("=1.0.0")),
            DependencySpec(child1.package_id, Requirement.parse("=2.0.0")),
        )
        with self.assertRaises(PackageError) as cm:
            resolve_packages(snap, roots)
        self.assertEqual(cm.exception.code, "package.version_conflict")

    def test_optional_conflict_cannot_perturb_required_revision(self):
        required = manifest("pkg-shared","rev-shared-1","1.0.0"); b1 = package_bytes(required)
        newer = manifest("pkg-shared","rev-shared-2","2.0.0"); b2 = package_bytes(newer)
        snap = CatalogSnapshot("cat-d", (row(required,b1), row(newer,b2)))
        roots = (
            DependencySpec(required.package_id, Requirement.parse("=1.0.0")),
            DependencySpec(required.package_id, Requirement.parse("=2.0.0"), DependencyKind.OPTIONAL, "without-feature"),
        )
        lock = resolve_packages(snap, roots)
        self.assertEqual(lock.require(required.package_id).package_revision_id, required.package_revision_id)

    def test_optional_transitive_failure_uses_fallback_without_leaking_subtree(self):
        missing = DependencySpec(PackageId("pkg-missing"), Requirement.parse("=1.0.0"))
        optional = manifest("pkg-optional","rev-optional","1.0.0",deps=(missing,)); bo = package_bytes(optional)
        root = manifest("pkg-root","rev-root","1.0.0"); br = package_bytes(root)
        snap = CatalogSnapshot("cat-e", (row(root,br), row(optional,bo)))
        roots = (
            DependencySpec(root.package_id, Requirement.parse("=1.0.0")),
            DependencySpec(optional.package_id, Requirement.parse("=1.0.0"), DependencyKind.OPTIONAL, "disabled"),
        )
        lock = resolve_packages(snap, roots)
        self.assertIn(root.package_id, lock.packages)
        self.assertNotIn(optional.package_id, lock.packages)
        self.assertNotIn(missing.package_id, lock.packages)

    def test_solver_work_limit_fails_closed(self):
        m = manifest(); b = package_bytes(m)
        snap = CatalogSnapshot("cat-f", (row(m,b),))
        with self.assertRaises(PackageError) as cm:
            resolve_packages(snap, (DependencySpec(m.package_id, Requirement.parse("=1.0.0")),), limits=SolverLimits(max_decisions=1))
        self.assertEqual(cm.exception.code, "package.solver_work_limit")

    def test_same_version_ambiguity_is_rejected(self):
        m1 = manifest(rev="rev-amb-1"); m2 = manifest(rev="rev-amb-2")
        with self.assertRaises(PackageError) as cm:
            CatalogSnapshot("cat-g", (row(m1,package_bytes(m1)), row(m2,package_bytes(m2))))
        self.assertEqual(cm.exception.code, "package.ambiguous_version")


class SMX035CodecBoundaryTests(unittest.TestCase):
    def test_manifest_and_lock_roundtrip_deterministically(self):
        m = manifest(); b = package_bytes(m); l = ResolutionLock("cat", {m.package_id: locked(m,b)})
        self.assertEqual(encode_manifest(decode_manifest(encode_manifest(m))), encode_manifest(m))
        self.assertEqual(encode_lock(decode_lock(encode_lock(l))), encode_lock(l))

    def test_spb1_roundtrip_is_pathless_tight_and_digest_verified(self):
        data = build_spb1((("manifest","manifest",b"abc"),("ir","behaviour-ir",b"xyz")))
        parsed = parse_spb1(data)
        self.assertEqual(parsed.payloads["ir"], b"xyz")
        index_len = struct.unpack(">4sIQ", data[:16])[1]
        index = decode_canonical_cbor(data[16:16 + index_len])
        self.assertNotIn("path", repr(index).lower())
        damaged = bytearray(data); damaged[-1] ^= 1
        with self.assertRaises(PackageError) as cm:
            parse_spb1(bytes(damaged))
        self.assertEqual(cm.exception.code, "package.bundle_digest")

    def test_trailing_chaff_and_truncation_rejected(self):
        data = build_spb1((("manifest","manifest",b"abc"),))
        for bad in (data + b"x", data[:-1]):
            with self.assertRaises(PackageError):
                parse_spb1(bad)

    def test_serialized_capability_grant_rejected_recursively(self):
        with self.assertRaises(PackageError) as cm:
            manifest(source_metadata={"nested": [{"capability_grant": "forged"}]})
        self.assertEqual(cm.exception.code, "package.serialized_authority")

    def test_protected_asset_field_mixing_surface_is_closed(self):
        asset = ProtectedAssetRevision.create(
            AssetId("asset-song"), source_digest=D(b"source"),
            source_identity={"name":"song.wav"}, source_metadata={"rate":48000},
            media_semantics={"loop":True}, provenance={"author":"a"},
            licence_attribution={"licence":"CC0"}, derivation_lineage=({"from":"recording"},),
        )
        m = manifest(assets=(asset,))
        decoded = decode_manifest(encode_manifest(m))
        self.assertEqual(decoded.protected_assets[0].revision_digest, asset.revision_digest)
        obj = decode_canonical_cbor(encode_manifest(m))
        obj["protected_assets"][0]["media_semantics"] = {"loop":False}
        with self.assertRaises(Exception):
            decode_manifest(encode_canonical_cbor(obj))

    def test_package_artifact_set_must_match_manifest_exactly(self):
        payload = b"program"
        spec = ArtifactSpec("behaviour-main","behaviour-ir",D(payload),len(payload))
        m = manifest(artifacts=(spec,)); good = package_bytes(m,{"behaviour-main":payload})
        validate_locked_bundle(locked(m,good), good)
        bad = build_spb1((("manifest","manifest",encode_manifest(m)),))
        with self.assertRaises(PackageError) as cm:
            validate_locked_bundle(locked(m,bad), bad)
        self.assertEqual(cm.exception.code, "package.artifact_set_mismatch")


class SMX035SemanticAndTransactionTests(unittest.TestCase):
    def test_definition_promotion_preserves_lineage_and_public_port_ids(self):
        source = definition("promoted")
        promoted = promote_definition(source)
        self.assertEqual(promoted.definition_id, source.definition_id)
        self.assertEqual({p.port_id for p in promoted.public_ports}, set(source.exposures))

    def test_corrupt_or_malformed_package_never_reaches_migration(self):
        called = []
        bad = b"not-an-spb1"
        m = manifest()
        lock = ResolutionLock("cat", {m.package_id: LockedPackage(m.package_id,m.package_revision_id,m.human_version,D(bad),len(bad))})
        system = PackageSystem(source=MappingPackageSource({str(m.package_revision_id):bad}), migration_prepare=lambda old,new: called.append(True))
        with self.assertRaises(PackageError):
            system.apply_lock(lock)
        self.assertEqual(called, [])

    def test_failed_migration_leaves_previous_exact_lock_and_live_state_coherent(self):
        oldm = manifest(rev="rev-old",version="1.0.0"); oldb = package_bytes(oldm)
        oldlock = ResolutionLock("old-cat", {oldm.package_id: locked(oldm,oldb)})
        source = MappingPackageSource({str(oldm.package_revision_id):oldb})
        system = PackageSystem(source=source)
        old_state = system.apply_lock(oldlock)
        newm = manifest(rev="rev-new",version="1.1.0",comp=oldm.root_component); newb = package_bytes(newm)
        newlock = ResolutionLock("new-cat", {newm.package_id: locked(newm,newb)})
        system.source = MappingPackageSource({str(newm.package_revision_id):newb})
        system.migration_prepare = lambda old,new: (_ for _ in ()).throw(RuntimeError("boom"))
        with self.assertRaises(PackageError) as cm:
            system.apply_lock(newlock)
        self.assertEqual(cm.exception.code, "package.migration_failed")
        self.assertIs(system.state, old_state)
        self.assertEqual(system.state.lock.catalog_snapshot_id, "old-cat")

    def test_public_interface_change_requires_explicit_reconciliation(self):
        oldm = manifest(rev="rev-iface-old"); oldb = package_bytes(oldm)
        system = PackageSystem(source=MappingPackageSource({str(oldm.package_revision_id):oldb}))
        system.apply_lock(ResolutionLock("cat1", {oldm.package_id: locked(oldm,oldb)}))
        changed = replace(oldm.root_component, public_interface_digest=D(b"different"))
        newm = manifest(rev="rev-iface-new",version="1.1.0",comp=changed); newb = package_bytes(newm)
        system.source = MappingPackageSource({str(newm.package_revision_id):newb})
        with self.assertRaises(PackageError) as cm:
            system.apply_lock(ResolutionLock("cat2", {newm.package_id: locked(newm,newb)}))
        self.assertEqual(cm.exception.code, "package.interface_incompatible")

    def test_dependency_principal_does_not_inherit_parent_grant(self):
        scope = CapabilityScope(frozenset({"clock"}), frozenset({"read"}), 64)
        parent = principal_for_component(PackageRevisionId("rev-parent"), DefinitionId("def-parent"))
        child = principal_for_component(PackageRevisionId("rev-child"), DefinitionId("def-child"))
        self.assertNotEqual(parent, child)
        broker = CapabilityBroker.from_trusted_grants((
            CapabilityGrant("grant-parent", parent, CapabilityId("time-read"), scope, "policy", 0),
        ))
        requirement = PackageCapabilityRequest(DefinitionId("def-child"), CapabilityId("time-read"), scope).requirement()
        with self.assertRaises(CapabilityError):
            broker.resolve_requirements(child, (requirement,), now=1)

    def test_lazy_dependency_materializes_only_exact_locked_revision(self):
        m = manifest("pkg-lazy","rev-lazy-1","1.0.0"); b = package_bytes(m)
        l = ResolutionLock("cat", {m.package_id: locked(m,b,lazy=True)})
        system = PackageSystem(source=MappingPackageSource({str(m.package_revision_id):b}))
        state = system.apply_lock(l)
        self.assertNotIn(m.package_id, state.packages)
        got = system.demand_lazy(m.package_id)
        self.assertEqual(got.locked.package_revision_id, m.package_revision_id)
        self.assertEqual(system.state.lock, l)

    def test_verified_cache_supports_exact_offline_reopen_but_never_floats(self):
        m = manifest("pkg-offline","rev-offline-1","1.0.0"); b = package_bytes(m)
        l = ResolutionLock("cat", {m.package_id: locked(m,b)})
        cache = ImmutableArtifactCache()
        online = PackageSystem(source=MappingPackageSource({str(m.package_revision_id):b}), cache=cache)
        online.apply_lock(l)
        offline = PackageSystem(source=MappingPackageSource({}), cache=cache)
        reopened = offline.apply_lock(l)
        self.assertEqual(reopened.packages[m.package_id].locked.package_revision_id, m.package_revision_id)
        other = manifest("pkg-offline","rev-offline-2","1.1.0"); otherb = package_bytes(other)
        missing_lock = ResolutionLock("cat2", {other.package_id: locked(other,otherb)})
        with self.assertRaises(PackageError) as cm:
            offline.apply_lock(missing_lock)
        self.assertEqual(cm.exception.code, "package.offline_unavailable")
        self.assertEqual(offline.state.lock, l)


if __name__ == "__main__":
    unittest.main()
