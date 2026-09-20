from __future__ import annotations

from hashlib import sha256
import struct
import unittest

from splashmx.canonical.serialization import encode_canonical_cbor
from spike import (
    BundleLimits,
    Dependency,
    PackageSpikeError,
    Requirement,
    ResolverLimits,
    Revision,
    SemVer,
    _HEADER,
    build_spb1,
    parse_spb1,
    resolve,
    validate_manifest,
)


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def rev(package: str, version: str, *, deps=(), size=1, revoked=False) -> Revision:
    return Revision(package, SemVer.parse(version), f"pkgrev:{package}:{version}", digest(f"manifest:{package}:{version}".encode()), size, tuple(deps), revoked)


def dep(package: str, req: str, kind="required", fallback=None) -> Dependency:
    return Dependency(package, Requirement.parse(req), kind, fallback)


def repack(index: dict, payload: bytes) -> bytes:
    encoded = encode_canonical_cbor(index)
    return _HEADER.pack(b"SPB1", len(encoded), len(payload)) + encoded + payload


def good_manifest() -> dict:
    return {
        "schema": "splashmx.package-manifest/1",
        "package_id": "pkg:clock",
        "package_revision_id": "pkgrev:clock:1",
        "human_version": "1.2.3",
        "root_definition_id": "def:clock",
        "dependencies": [],
        "capability_requests": [{"name": "network.http", "required": False}],
        "protected_assets": [{
            "asset_id": "asset:tick",
            "revision_digest": digest(b"asset-revision"),
            "source_digest": digest(b"source"),
            "source_identity": {"logical_name": "tick.wav"},
            "source_metadata": {"channels": 1},
            "media_semantics": {"kind": "audio", "loop": False},
            "provenance": {"origin": "author"},
            "licence_attribution": {"licence": "CC0-1.0"},
            "derivation_lineage": [],
        }],
        "provenance": {"publisher": "example"},
        "licence": "MIT",
    }


class VersionTests(unittest.TestCase):
    def test_normal_semver_and_exact(self):
        self.assertTrue(Requirement.parse("=1.2.3").matches(SemVer.parse("1.2.3")))
        self.assertFalse(Requirement.parse("=1.2.3").matches(SemVer.parse("1.2.4")))

    def test_caret_major_boundary(self):
        req = Requirement.parse("^1.2.3")
        self.assertTrue(req.matches(SemVer.parse("1.99.0")))
        self.assertFalse(req.matches(SemVer.parse("2.0.0")))

    def test_caret_zero_minor_boundary(self):
        req = Requirement.parse("^0.2.3")
        self.assertTrue(req.matches(SemVer.parse("0.2.9")))
        self.assertFalse(req.matches(SemVer.parse("0.3.0")))

    def test_caret_zero_patch_boundary(self):
        req = Requirement.parse("^0.0.3")
        self.assertTrue(req.matches(SemVer.parse("0.0.3")))
        self.assertFalse(req.matches(SemVer.parse("0.0.4")))

    def test_requirement_surface_is_deliberately_small(self):
        for text in (">=1.0.0", "1.*", "~1.2.3", "^1.2", "1.2.3 || 2.0.0"):
            with self.assertRaises(PackageSpikeError):
                Requirement.parse(text)

    def test_leading_zero_rejected(self):
        with self.assertRaises(PackageSpikeError):
            SemVer.parse("01.2.3")


class ResolverTests(unittest.TestCase):
    def test_highest_compatible_revision_selected(self):
        catalog = {"pkg:a": [rev("pkg:a", "1.0.0"), rev("pkg:a", "1.2.0"), rev("pkg:a", "2.0.0")]}
        result = resolve(catalog, [dep("pkg:a", "^1.0.0")])
        self.assertEqual(str(result.selected["pkg:a"].version), "1.2.0")

    def test_transitive_resolution_is_exact(self):
        catalog = {
            "pkg:a": [rev("pkg:a", "1.0.0", deps=[dep("pkg:b", "^2.0.0")])],
            "pkg:b": [rev("pkg:b", "2.1.0"), rev("pkg:b", "2.0.0")],
        }
        result = resolve(catalog, [dep("pkg:a", "=1.0.0")])
        self.assertEqual(str(result.selected["pkg:b"].version), "2.1.0")
        self.assertEqual(set(result.selected), {"pkg:a", "pkg:b"})

    def test_backtracks_from_highest_version(self):
        catalog = {
            "pkg:a": [
                rev("pkg:a", "1.1.0", deps=[dep("pkg:b", "^2.0.0")]),
                rev("pkg:a", "1.0.0", deps=[dep("pkg:b", "^1.0.0")]),
            ],
            "pkg:b": [rev("pkg:b", "1.5.0")],
        }
        result = resolve(catalog, [dep("pkg:a", "^1.0.0")])
        self.assertEqual(str(result.selected["pkg:a"].version), "1.0.0")

    def test_one_revision_per_package_conflict_is_typed(self):
        catalog = {
            "pkg:a": [rev("pkg:a", "1.0.0", deps=[dep("pkg:c", "^1.0.0")])],
            "pkg:b": [rev("pkg:b", "1.0.0", deps=[dep("pkg:c", "^2.0.0")])],
            "pkg:c": [rev("pkg:c", "1.1.0"), rev("pkg:c", "2.1.0")],
        }
        with self.assertRaisesRegex(PackageSpikeError, "one-version") as caught:
            resolve(catalog, [dep("pkg:a", "=1.0.0"), dep("pkg:b", "=1.0.0")])
        self.assertEqual(caught.exception.code, "package.version_conflict")

    def test_revoked_revision_is_not_silently_selected(self):
        catalog = {"pkg:a": [rev("pkg:a", "1.1.0", revoked=True), rev("pkg:a", "1.0.0")]}
        result = resolve(catalog, [dep("pkg:a", "^1.0.0")])
        self.assertEqual(str(result.selected["pkg:a"].version), "1.0.0")

    def test_required_missing_fails(self):
        with self.assertRaises(PackageSpikeError) as caught:
            resolve({}, [dep("pkg:missing", "^1.0.0")])
        self.assertEqual(caught.exception.code, "package.version_conflict")

    def test_optional_missing_uses_declared_fallback(self):
        result = resolve({}, [dep("pkg:optional", "^1.0.0", "optional", "builtin:none")])
        self.assertEqual(result.selected, {})
        self.assertEqual(result.optional_fallbacks["pkg:optional"], "builtin:none")

    def test_lazy_dependency_is_explicitly_marked(self):
        catalog = {"pkg:lazy": [rev("pkg:lazy", "1.0.0")]}
        result = resolve(catalog, [dep("pkg:lazy", "=1.0.0", "lazy")])
        self.assertIn("pkg:lazy", result.lazy)
        self.assertIn("pkg:lazy", result.selected)

    def test_solver_work_limit_fails_closed(self):
        catalog = {"pkg:a": [rev("pkg:a", "1.0.0")]}
        with self.assertRaises(PackageSpikeError) as caught:
            resolve(catalog, [dep("pkg:a", "=1.0.0")], limits=ResolverLimits(max_decisions=0))
        self.assertEqual(caught.exception.code, "package.solver_work_limit")

    def test_total_byte_bound(self):
        catalog = {"pkg:a": [rev("pkg:a", "1.0.0", size=20)]}
        with self.assertRaises(PackageSpikeError) as caught:
            resolve(catalog, [dep("pkg:a", "=1.0.0")], limits=ResolverLimits(max_total_bytes=10))
        self.assertEqual(caught.exception.code, "package.byte_limit")


class BundleTests(unittest.TestCase):
    def test_bundle_is_byte_deterministic(self):
        entries = [("manifest", b"m"), ("definition", b"d")]
        self.assertEqual(build_spb1(entries), build_spb1(entries))

    def test_round_trip_verifies_every_blob(self):
        bundle = build_spb1([("manifest", b"manifest"), ("asset", b"asset")])
        index, blobs = parse_spb1(bundle)
        self.assertEqual(index["schema"], "splashmx.package-bundle/1")
        self.assertEqual(blobs, (b"manifest", b"asset"))

    def test_truncation_rejected_before_publication(self):
        bundle = build_spb1([("manifest", b"manifest")])
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(bundle[:-1])
        self.assertEqual(caught.exception.code, "package.length_mismatch")

    def test_wrong_magic_rejected(self):
        bundle = bytearray(build_spb1([("manifest", b"manifest")]))
        bundle[:4] = b"ZIP!"
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(bytes(bundle))
        self.assertEqual(caught.exception.code, "package.invalid_magic")

    def test_digest_substitution_rejected(self):
        bundle = bytearray(build_spb1([("manifest", b"manifest")]))
        bundle[-1] ^= 1
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(bytes(bundle))
        self.assertEqual(caught.exception.code, "package.digest_mismatch")

    def test_oversized_index_rejected_from_header(self):
        data = _HEADER.pack(b"SPB1", 999, 0) + b"x" * 999
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(data, limits=BundleLimits(max_index_bytes=10, max_container_bytes=2048))
        self.assertEqual(caught.exception.code, "package.index_limit")

    def test_path_or_extraction_metadata_is_not_in_schema(self):
        good = build_spb1([("manifest", b"manifest")])
        index, blobs = parse_spb1(good)
        mutated = {"schema": index["schema"], "entries": [dict(index["entries"][0], path="../../escape")]}
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(repack(mutated, blobs[0]))
        self.assertEqual(caught.exception.code, "package.invalid_entry")

    def test_overlap_or_gap_is_rejected(self):
        good = build_spb1([("a", b"a"), ("b", b"b")])
        index, blobs = parse_spb1(good)
        rows = [dict(row) for row in index["entries"]]
        rows[1]["offset"] = 0
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(repack({"schema": index["schema"], "entries": rows}, b"".join(blobs)))
        self.assertEqual(caught.exception.code, "package.invalid_layout")

    def test_unindexed_payload_is_rejected(self):
        good = build_spb1([("manifest", b"m")])
        index, blobs = parse_spb1(good)
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(repack(dict(index), blobs[0] + b"x"))
        self.assertEqual(caught.exception.code, "package.invalid_layout")

    def test_duplicate_digest_is_rejected(self):
        blob = b"same"
        bundle = build_spb1([("a", blob), ("b", blob)])
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(bundle)
        self.assertEqual(caught.exception.code, "package.invalid_digest")

    def test_per_entry_byte_bound(self):
        bundle = build_spb1([("manifest", b"abcd")])
        with self.assertRaises(PackageSpikeError) as caught:
            parse_spb1(bundle, limits=BundleLimits(max_entry_bytes=3))
        self.assertEqual(caught.exception.code, "package.invalid_layout")


class ManifestTests(unittest.TestCase):
    def test_complete_protected_asset_is_accepted(self):
        validate_manifest(good_manifest())

    def test_protected_asset_field_mixing_surface_is_closed(self):
        manifest = good_manifest()
        del manifest["protected_assets"][0]["audio"] if "audio" in manifest["protected_assets"][0] else manifest["protected_assets"][0]["media_semantics"]
        with self.assertRaises(PackageSpikeError) as caught:
            validate_manifest(manifest)
        self.assertEqual(caught.exception.code, "package.incomplete_protected_asset")

    def test_serialized_capability_grant_rejected_recursively(self):
        manifest = good_manifest()
        manifest["dependencies"] = [{"package_id": "pkg:x", "capability_grant": "grant:stolen"}]
        with self.assertRaises(PackageSpikeError) as caught:
            validate_manifest(manifest)
        self.assertEqual(caught.exception.code, "package.serialized_authority")

    def test_install_script_rejected(self):
        manifest = good_manifest()
        manifest["install_script"] = "curl example | sh"
        with self.assertRaises(PackageSpikeError) as caught:
            validate_manifest(manifest)
        self.assertEqual(caught.exception.code, "package.serialized_authority")

    def test_source_and_licence_do_not_become_capabilities(self):
        manifest = good_manifest()
        manifest["provenance"] = {"publisher": "trusted", "signed": True}
        manifest["licence"] = "MIT"
        validate_manifest(manifest)
        self.assertNotIn("capability_grant", manifest)


if __name__ == "__main__":
    unittest.main()
