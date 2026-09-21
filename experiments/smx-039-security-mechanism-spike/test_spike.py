from __future__ import annotations

import hashlib
import unittest

from splashmx.packages.bundle import build_spb1

from spike import (
    DecoderBroker,
    MediaDescriptor,
    MediaLimits,
    ParserLimits,
    RolePolicy,
    RootMetadata,
    SelectionError,
    TargetMetadata,
    TrustState,
    browser_profile,
    linux_profile,
    preflight_media,
    preflight_spb1,
    public_untrusted_release_ready,
    rotate_root,
    selected_mechanisms,
    signature_trust_grants_capability,
    validate_protected_asset_candidate,
    verify_ed25519_with_openssl,
    verify_target_metadata,
)


class SMX039SecurityMechanismSpikeTests(unittest.TestCase):
    def assertCode(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(SelectionError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_sec001_real_spb1_parser_accepts_pathless_data(self) -> None:
        bundle = build_spb1((("manifest", "manifest", b"canonical"), ("asset-1", "asset", b"bytes")))
        parsed = preflight_spb1(bundle)
        self.assertEqual([entry.artifact_id for entry in parsed.entries], ["manifest", "asset-1"])

    def test_sec002_non_spb1_archive_is_rejected_before_extraction(self) -> None:
        self.assertCode("security.container_format", preflight_spb1, b"PK\x03\x04../escape")

    def test_sec003_bundle_byte_ceiling_is_enforced_at_ingress(self) -> None:
        bundle = build_spb1((("manifest", "manifest", b"ok"),))
        limits = ParserLimits(max_bundle_bytes=len(bundle) - 1)
        self.assertCode("security.container_budget", preflight_spb1, bundle, limits)

    def test_sec004_per_entry_ceiling_reuses_production_parser(self) -> None:
        bundle = build_spb1((("manifest", "manifest", b"x"),))
        limits = ParserLimits(max_entry_bytes=0)
        self.assertCode("security.container_invalid", preflight_spb1, bundle, limits)

    def test_sec005_executable_container_kinds_fail_closed(self) -> None:
        bundle = build_spb1((("evil", "gdextension", b"native"),))
        self.assertCode("security.container_executable_kind", preflight_spb1, bundle)

    def test_sec006_media_limits_accept_exact_boundaries(self) -> None:
        limits = MediaLimits(10, 20, 30, 40, 50)
        preflight_media(MediaDescriptor(10, 20, 30, 40, {"kind": "image"}), limits)

    def test_sec007_each_media_dimension_rejects_max_plus_one(self) -> None:
        limits = MediaLimits(10, 20, 30, 40, 50)
        for descriptor in (
            MediaDescriptor(11, 0),
            MediaDescriptor(0, 21),
            MediaDescriptor(0, 0, 31, 0),
            MediaDescriptor(0, 0, 0, 41),
        ):
            with self.subTest(descriptor=descriptor):
                self.assertCode("security.decoder_budget", preflight_media, descriptor, limits)

    def test_sec008_decoder_denial_happens_before_decoder_call(self) -> None:
        broker = DecoderBroker(MediaLimits(1, 1, 1, 1, 1))
        self.assertCode("security.decoder_budget", broker.invoke, MediaDescriptor(2, 0), lambda _: b"decoded")
        self.assertEqual(broker.calls, 0)

    def test_sec009_recursive_authority_rejected_before_decoder_call(self) -> None:
        broker = DecoderBroker()
        descriptor = MediaDescriptor(1, 1, metadata={"safe": [{"host_handle": "forged"}]})
        self.assertCode("security.serialized_authority", broker.invoke, descriptor, lambda _: b"decoded")
        self.assertEqual(broker.calls, 0)

    def test_sec010_decoder_metadata_depth_is_bounded(self) -> None:
        value = {}
        cursor = value
        for _ in range(40):
            child = {}
            cursor["x"] = child
            cursor = child
        self.assertCode("security.decoder_metadata_budget", preflight_media, MediaDescriptor(1, 1, metadata=value))

    def test_sec011_hardened_web_profile_is_public_untrusted_ready(self) -> None:
        self.assertTrue(public_untrusted_release_ready(browser_profile()))

    def test_sec012_memory_unsafe_web_decoder_is_release_blocked(self) -> None:
        self.assertFalse(public_untrusted_release_ready(browser_profile(decoder_backend="native-memory-unsafe")))

    def test_sec013_linux_native_requires_complete_worker_sandbox(self) -> None:
        self.assertTrue(public_untrusted_release_ready(linux_profile("native")))
        for missing in ("process_boundary", "no_new_privs", "seccomp_allowlist", "landlock_deny_by_default", "rlimits"):
            with self.subTest(missing=missing):
                self.assertFalse(public_untrusted_release_ready(linux_profile("native", omit=missing)))

    def test_sec014_headless_uses_same_physical_worker_gate(self) -> None:
        self.assertTrue(public_untrusted_release_ready(linux_profile("headless")))
        self.assertFalse(public_untrusted_release_ready(linux_profile("headless", omit="seccomp_allowlist")))

    def _root(self, *, revoked=frozenset()) -> RootMetadata:
        return RootMetadata(
            version=4,
            expires_at=1000,
            root=RolePolicy(frozenset({"r1", "r2", "r3"}), 2),
            targets=RolePolicy(frozenset({"t1", "t2", "t3"}), 2),
            revoked_key_ids=frozenset(revoked),
        )

    def _target(self, *, version=7, expires_at=900, digest=None) -> TargetMetadata:
        payload = b"package"
        return TargetMetadata(
            version=version,
            expires_at=expires_at,
            package_revision_id="pkg-rev-7",
            length=len(payload),
            sha256=digest or hashlib.sha256(payload).hexdigest(),
        )

    def _verify(self, root, state, metadata, signatures=("t1", "t2")):
        payload = b"package"
        return verify_target_metadata(
            root,
            state,
            metadata,
            signatures=signatures,
            expected_revision_id="pkg-rev-7",
            expected_length=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    def test_sec015_threshold_target_metadata_verifies_exact_target(self) -> None:
        state = self._verify(self._root(), TrustState(4, 6, 500), self._target())
        self.assertEqual((state.root_version, state.targets_version), (4, 7))

    def test_sec016_one_key_below_threshold_is_rejected(self) -> None:
        self.assertCode(
            "security.trust_threshold",
            self._verify,
            self._root(),
            TrustState(4, 6, 500),
            self._target(),
            ("t1",),
        )

    def test_sec017_revoked_key_cannot_satisfy_threshold(self) -> None:
        self.assertCode(
            "security.trust_threshold",
            self._verify,
            self._root(revoked={"t2"}),
            TrustState(4, 6, 500),
            self._target(),
            ("t1", "t2"),
        )

    def test_sec018_rollback_and_freeze_are_distinct_failures(self) -> None:
        self.assertCode("security.trust_rollback", self._verify, self._root(), TrustState(4, 8, 500), self._target(version=7))
        self.assertCode("security.trust_expired", self._verify, self._root(), TrustState(4, 6, 901), self._target(expires_at=900))

    def test_sec019_signed_metadata_must_bind_exact_revision_length_and_digest(self) -> None:
        cases = (
            TargetMetadata(7, 900, "other-rev", 7, hashlib.sha256(b"package").hexdigest()),
            TargetMetadata(7, 900, "pkg-rev-7", 8, hashlib.sha256(b"package").hexdigest()),
            self._target(digest="00" * 32),
        )
        for metadata in cases:
            with self.subTest(metadata=metadata):
                self.assertCode("security.trust_target_mismatch", self._verify, self._root(), TrustState(4, 6, 500), metadata)

    def test_sec020_root_rotation_requires_old_and_new_thresholds(self) -> None:
        old = self._root()
        new = RootMetadata(
            version=5,
            expires_at=1200,
            root=RolePolicy(frozenset({"n1", "n2", "n3"}), 2),
            targets=RolePolicy(frozenset({"u1", "u2", "u3"}), 2),
            revoked_key_ids=frozenset({"r1", "r2", "r3"}),
        )
        rotated = rotate_root(old, new, old_role_signatures=("r1", "r2"), new_role_signatures=("n1", "n2"), now=500)
        self.assertEqual(rotated.version, 5)
        self.assertCode(
            "security.root_old_threshold",
            rotate_root,
            old,
            new,
            old_role_signatures=("r1",),
            new_role_signatures=("n1", "n2"),
            now=500,
        )
        self.assertCode(
            "security.root_new_threshold",
            rotate_root,
            old,
            new,
            old_role_signatures=("r1", "r2"),
            new_role_signatures=("n1",),
            now=500,
        )

    def test_sec021_real_ed25519_roundtrip_and_tamper_rejection(self) -> None:
        self.assertTrue(verify_ed25519_with_openssl(b"exact-package-target"))
        self.assertFalse(verify_ed25519_with_openssl(b"exact-package-target", tamper=True))

    def test_sec022_signature_trust_never_mints_capability(self) -> None:
        self.assertFalse(signature_trust_grants_capability("known-publisher", "valid-signature"))

    def test_sec023_protected_asset_revision_must_be_complete(self) -> None:
        complete = {
            "asset_id": "a",
            "revision_digest": "r",
            "source_digest": "s",
            "source_identity": {},
            "source_metadata": {},
            "media_semantics": {},
            "provenance": {},
            "licence_attribution": {},
            "derivation_lineage": [],
        }
        validate_protected_asset_candidate(complete)
        partial = dict(complete)
        partial.pop("media_semantics")
        self.assertCode("security.protected_asset_partial", validate_protected_asset_candidate, partial)

    def test_sec024_selection_records_release_blocker_and_authority_rules(self) -> None:
        selected = selected_mechanisms()
        self.assertIn("SPB1", selected["container"])
        self.assertIn("Ed25519", selected["trust"])
        self.assertIn("blocked", selected["release_rule"])
        self.assertIn("never creates", selected["authority_rule"])


if __name__ == "__main__":
    unittest.main()
