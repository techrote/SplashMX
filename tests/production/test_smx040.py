from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

from splashmx.canonical.core import AssetId, BehaviourAttachmentId, ThingId
from splashmx.execution.ir import ServiceRequest
from splashmx.packages.bundle import build_spb1
from splashmx.packages.model import PackageRevisionId
from splashmx.security.capabilities import (
    CapabilityBroker,
    CapabilityScope,
    TrustedHostServiceBoundary,
    principal_for_service_request,
)
from splashmx.security.physical import (
    BrowserIsolationProfile,
    BrowserWasmDecoder,
    CAP_MEDIA_DECODE,
    DecoderBroker,
    DecoderResult,
    LinuxProcessDecoder,
    MediaDescriptor,
    OpenSslEd25519Verifier,
    PhysicalLimits,
    PhysicalSecurityError,
    RepositoryTrust,
    RepositoryTrustState,
    RoleEnvelope,
    RolePolicy,
    RootMetadata,
    SecurityBoundary,
    Signature,
    encode_role_envelope,
    parse_role_envelope,
    preflight_media,
    preflight_spb1,
    probe_linux_sandbox,
    root_metadata_body,
    trust_signature_grants_capability,
    validate_protected_asset_candidate,
)


class StaticVerifier:
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return signature == public_key


KEYS = {
    "root-a": b"root-a-key",
    "targets-a": b"targets-a-key",
    "snapshot-a": b"snapshot-a-key",
    "timestamp-a": b"timestamp-a-key",
}


def root_v1() -> RootMetadata:
    return RootMetadata(
        1,
        10_000,
        KEYS,
        {
            "root": RolePolicy(frozenset({"root-a"}), 1),
            "targets": RolePolicy(frozenset({"targets-a"}), 1),
            "snapshot": RolePolicy(frozenset({"snapshot-a"}), 1),
            "timestamp": RolePolicy(frozenset({"timestamp-a"}), 1),
        },
    )


def env(role: str, version: int, body: dict, key_id: str, *, expires: int = 10_000) -> RoleEnvelope:
    return RoleEnvelope(role, version, expires, body, (Signature(key_id, KEYS.get(key_id, key_id.encode())),))


def metadata_digest(envelope: RoleEnvelope) -> str:
    return hashlib.sha256(encode_role_envelope(envelope)).hexdigest()


def coherent_metadata(package: bytes, revision: PackageRevisionId, *, version: int = 1):
    targets = env(
        "targets",
        version,
        {"targets": [{
            "package_revision_id": str(revision),
            "length": len(package),
            "sha256": hashlib.sha256(package).hexdigest(),
        }]},
        "targets-a",
    )
    snapshot = env(
        "snapshot",
        version,
        {"targets_version": targets.version, "targets_sha256": metadata_digest(targets)},
        "snapshot-a",
    )
    timestamp = env(
        "timestamp",
        version,
        {"snapshot_version": snapshot.version, "snapshot_sha256": metadata_digest(snapshot)},
        "timestamp-a",
    )
    return targets, snapshot, timestamp


def tiny_decoder(source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
    data = source[::-1]
    return DecoderResult(data, len(data), descriptor.image_pixels, descriptor.audio_frames, {"codec": "test"})


def media_payload(source: bytes = b"abcd", *, profile: str = "web-hardened") -> dict:
    return {
        "profile": profile,
        "asset_id": "asset.security",
        "revision_digest": "revision.security.1",
        "source_digest": hashlib.sha256(source).hexdigest(),
        "source": source,
        "predicted_decoded_bytes": len(source),
        "image_pixels": 0,
        "audio_frames": 0,
        "derivative_kind": "test",
        "derivative_version": "1",
        "metadata": {},
    }


def media_reference(source: bytes = b"abcd", *, profile: str = "web-hardened") -> dict:
    row = media_payload(source, profile=profile)
    row.pop("source")
    row["source_bytes"] = len(source)
    return row


class TestPhysicalSecurityBoundary(unittest.TestCase):
    def test_pathless_spb1_only(self):
        with self.assertRaises(PhysicalSecurityError) as cm:
            preflight_spb1(b"PK\x03\x04not-an-ordinary-package")
        self.assertEqual(cm.exception.code, "security.container_format")

    def test_spb1_executable_kind_rejected(self):
        with self.assertRaises(PhysicalSecurityError) as cm:
            preflight_spb1(build_spb1((("evil", "gdscript", b"print('no')"),)))
        self.assertEqual(cm.exception.code, "security.container_executable_kind")

    def test_spb1_total_limit_is_independent(self):
        bundle = build_spb1((("a", "data", b"1234"),))
        with self.assertRaises(PhysicalSecurityError) as cm:
            preflight_spb1(bundle, PhysicalLimits(max_bundle_bytes=len(bundle) - 1))
        self.assertEqual(cm.exception.code, "security.container_budget")

    def test_media_limits_exact_and_max_plus_one(self):
        limits = PhysicalLimits(max_source_bytes=4, max_decoded_bytes=8, max_image_pixels=16, max_audio_frames=32)
        good = MediaDescriptor(AssetId("asset.a"), "rev", "digest", 4, 8, 16, 32)
        preflight_media(good, limits)
        for field, value in (("source_bytes", 5), ("predicted_decoded_bytes", 9), ("image_pixels", 17), ("audio_frames", 33)):
            row = good.__dict__.copy(); row[field] = value
            with self.subTest(field=field), self.assertRaises(PhysicalSecurityError) as cm:
                preflight_media(MediaDescriptor(**row), limits)
            self.assertEqual(cm.exception.code, "security.decoder_budget")

    def test_recursive_serialized_authority_denied_before_worker(self):
        backend = BrowserWasmDecoder(tiny_decoder, BrowserIsolationProfile(decoder_module_pinned=True))
        broker = DecoderBroker({"web-hardened": backend})
        payload = media_payload(); payload["metadata"] = {"nested": [{"Capability_Grant": "forged"}]}
        with self.assertRaises(PhysicalSecurityError) as cm:
            broker.decode_bytes(payload)
        self.assertEqual(cm.exception.code, "security.serialized_authority")
        self.assertEqual(broker.worker_invocations, 0)

    def test_source_digest_mismatch_denied_before_worker(self):
        backend = BrowserWasmDecoder(tiny_decoder, BrowserIsolationProfile(decoder_module_pinned=True))
        broker = DecoderBroker({"web-hardened": backend})
        payload = media_payload(); payload["source_digest"] = "0" * 64
        with self.assertRaises(PhysicalSecurityError) as cm:
            broker.decode_bytes(payload)
        self.assertEqual(cm.exception.code, "security.source_digest")
        self.assertEqual(broker.worker_invocations, 0)

    def test_incomplete_web_isolation_has_no_fallback(self):
        backend = BrowserWasmDecoder(tiny_decoder, BrowserIsolationProfile(decoder_module_pinned=False))
        broker = DecoderBroker({"web-hardened": backend})
        with self.assertRaises(PhysicalSecurityError) as cm:
            broker.decode_bytes(media_payload())
        self.assertEqual(cm.exception.code, "security.isolation_unavailable")
        self.assertEqual(broker.worker_invocations, 0)

    def test_result_is_revalidated_before_derivative_cache_publish(self):
        def oversized(source, descriptor):
            return DecoderResult(b"12345", 5)
        backend = BrowserWasmDecoder(oversized, BrowserIsolationProfile(decoder_module_pinned=True))
        broker = DecoderBroker({"web-hardened": backend}, limits=PhysicalLimits(max_decoded_bytes=4))
        payload = media_payload(b"1234"); payload["predicted_decoded_bytes"] = 4
        with self.assertRaises(PhysicalSecurityError) as cm:
            broker.decode_bytes(payload)
        self.assertEqual(cm.exception.code, "security.decoder_result_budget")
        self.assertEqual(broker.cache.entry_count, 0)

    def test_derivative_cache_key_preserves_exact_asset_revision(self):
        backend = BrowserWasmDecoder(tiny_decoder, BrowserIsolationProfile(decoder_module_pinned=True))
        broker = DecoderBroker({"web-hardened": backend})
        result = broker.decode_bytes(media_payload())
        self.assertEqual((result["asset_id"], result["revision_digest"], result["target_profile"]), ("asset.security", "revision.security.1", "web-hardened"))
        self.assertEqual(broker.cache.entry_count, 1)
        self.assertEqual(len(broker.cache.get(result["cache_key"])), 4)

    def test_protected_asset_candidate_is_complete_or_rejected(self):
        complete = {
            "asset_id": "asset.a", "revision_digest": "r", "source_digest": "s",
            "source_identity": {}, "source_metadata": {}, "media_semantics": {},
            "provenance": {}, "licence_attribution": {}, "derivation_lineage": [],
        }
        validate_protected_asset_candidate(complete)
        partial = dict(complete); partial.pop("media_semantics")
        with self.assertRaises(PhysicalSecurityError) as cm:
            validate_protected_asset_candidate(partial)
        self.assertEqual(cm.exception.code, "security.protected_asset_partial")

    def test_signature_trust_never_grants_capability(self):
        self.assertFalse(trust_signature_grants_capability("publisher", "network"))

    def _mediated(self, source: bytes, suffix: str):
        backend = BrowserWasmDecoder(tiny_decoder, BrowserIsolationProfile(decoder_module_pinned=True))
        physical = DecoderBroker({"web-hardened": backend}, source_provider=lambda asset_id, revision, digest: source)
        request = ServiceRequest(
            ThingId(f"thing.security{suffix}"), BehaviourAttachmentId(f"beh.security{suffix}"),
            "security.media_decode", media_reference(source), f"request-{suffix}", 7,
        )
        principal = principal_for_service_request(request)
        grants = CapabilityBroker()
        grant = grants.issue_root_grant(
            grant_id=f"decode-root{suffix}", principal_id=principal, capability_id=CAP_MEDIA_DECODE,
            scope=CapabilityScope(frozenset({"asset.security"}), frozenset({"decode"}), 64),
            issuer_policy_id="test-policy", issued_at=1, expires_at=100,
        )
        return physical, request, grant, grants, TrustedHostServiceBoundary(grants, (physical.host_adapter(),))

    def test_r016_04_revocation_after_admission_stops_real_decoder_host_crossing(self):
        physical, request, grant, grants, host = self._mediated(b"abcd", "1")
        admitted = host.admit(request, now=10); grants.revoke(grant.grant_id)
        with self.assertRaises(Exception) as cm:
            host.execute(admitted, now=11)
        self.assertEqual(getattr(cm.exception, "code", None), "capability.revoked")
        self.assertEqual(physical.worker_invocations, 0)

    def test_successful_mediated_decode_crosses_only_after_authorization(self):
        physical, request, _grant, _grants, host = self._mediated(b"abcd", "2")
        result = host.execute(host.admit(request, now=10), now=11)
        self.assertEqual((result["asset_id"], result["decoded_bytes"]), ("asset.security", 4))
        self.assertEqual(physical.worker_invocations, 1)

    def test_linux_public_profile_requires_every_kernel_primitive(self):
        status = probe_linux_sandbox()
        self.assertEqual(status.ready, all(status.__dict__.values()))

    @unittest.skipUnless(os.name == "posix", "Linux sandbox test is target-specific")
    def test_linux_worker_runs_only_when_real_sandbox_is_ready(self):
        worker = LinuxProcessDecoder(tiny_decoder)
        if not worker.public_untrusted_ready:
            self.skipTest(f"runner is an explicit release-blocked profile: {worker.status}")
        descriptor = MediaDescriptor(AssetId("asset.linux"), "rev", hashlib.sha256(b"abc").hexdigest(), 3, 3)
        self.assertEqual(worker.decode(b"abc", descriptor).bytes, b"cba")

    @unittest.skipUnless(os.name == "posix", "Linux sandbox test is target-specific")
    def test_linux_worker_denies_filesystem_network_and_process_creation(self):
        def hostile(source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
            denied = []
            try: socket.socket()
            except OSError: denied.append("socket")
            try: open("/etc/passwd", "rb")
            except OSError: denied.append("file")
            try: os.fork()
            except OSError: denied.append("fork")
            text = "|".join(sorted(denied)).encode()
            return DecoderResult(text, len(text))
        worker = LinuxProcessDecoder(hostile)
        if not worker.public_untrusted_ready:
            self.skipTest(f"runner is an explicit release-blocked profile: {worker.status}")
        descriptor = MediaDescriptor(AssetId("asset.hostile"), "rev", hashlib.sha256(b"x").hexdigest(), 1, 64)
        self.assertEqual(set(worker.decode(b"x", descriptor).bytes.decode().split("|")), {"file", "fork", "socket"})


class TestRepositoryTrust(unittest.TestCase):
    def setUp(self):
        self.package = build_spb1((("manifest", "manifest", b"manifest"),))
        self.revision = PackageRevisionId("package.revision.1")
        self.targets, self.snapshot, self.timestamp = coherent_metadata(self.package, self.revision)
        self.trust = RepositoryTrust(RepositoryTrustState(root_v1(), 1), StaticVerifier())

    def test_bounded_role_metadata_round_trip_and_malformed_input(self):
        encoded = encode_role_envelope(self.targets)
        self.assertEqual(parse_role_envelope(encoded), self.targets)
        with self.assertRaises(PhysicalSecurityError): parse_role_envelope(encoded[:-1])

    def test_repository_metadata_rejects_serialized_authority(self):
        # Build a canonical safe envelope, then mutate an equal-length body key on
        # the wire. This exercises hostile external bytes rather than asking the
        # trusted canonical encoder to construct a forbidden durable field.
        safe = env("targets", 1, {"safe_key": "forged"}, "targets-a")
        raw = encode_role_envelope(safe)
        self.assertIn(b"safe_key", raw)
        hostile = raw.replace(b"safe_key", b"grant_id", 1)
        with self.assertRaises(PhysicalSecurityError) as cm:
            parse_role_envelope(hostile)
        self.assertIn(cm.exception.code, {"security.trust_parse", "security.serialized_authority"})

    def test_threshold_freshness_coherence_and_exact_target(self):
        self.trust.refresh(self.targets, self.snapshot, self.timestamp, now=10)
        self.trust.verify_target(self.targets, self.revision, self.package)
        with self.assertRaises(PhysicalSecurityError) as cm:
            self.trust.verify_target(self.targets, self.revision, self.package + b"tamper")
        self.assertEqual(cm.exception.code, "security.trust_target_mismatch")

    def test_snapshot_hash_prevents_same_version_mix_and_match(self):
        forged = env("targets", 1, {"targets": [{"package_revision_id": str(self.revision), "length": 1, "sha256": "00"}]}, "targets-a")
        with self.assertRaises(PhysicalSecurityError) as cm:
            self.trust.refresh(forged, self.snapshot, self.timestamp, now=10)
        self.assertEqual(cm.exception.code, "security.trust_mix_match")

    def test_rollback_and_expiry_fail_closed(self):
        self.trust.refresh(self.targets, self.snapshot, self.timestamp, now=10)
        old_targets, old_snapshot, old_timestamp = coherent_metadata(self.package, self.revision, version=1)
        self.trust.state = RepositoryTrustState(root_v1(), 1, 2, 2, 2, "x")
        with self.assertRaises(PhysicalSecurityError) as cm:
            self.trust.refresh(old_targets, old_snapshot, old_timestamp, now=10)
        self.assertEqual(cm.exception.code, "security.trust_rollback")
        expired = RoleEnvelope("timestamp", 3, 5, old_timestamp.body, old_timestamp.signatures)
        with self.assertRaises(PhysicalSecurityError) as cm2:
            RepositoryTrust(RepositoryTrustState(root_v1(), 1), StaticVerifier()).refresh(old_targets, old_snapshot, expired, now=10)
        self.assertEqual(cm2.exception.code, "security.trust_expired")

    def test_uncommitted_same_version_targets_cannot_replace_refreshed_metadata(self):
        self.trust.refresh(self.targets, self.snapshot, self.timestamp, now=10)
        forged = env("targets", 1, {"targets": [{"package_revision_id": str(self.revision), "length": len(self.package), "sha256": hashlib.sha256(self.package).hexdigest()}], "extra": []}, "targets-a")
        with self.assertRaises(PhysicalSecurityError) as cm:
            self.trust.verify_target(forged, self.revision, self.package)
        self.assertEqual(cm.exception.code, "security.trust_uncommitted_targets")

    def test_security_boundary_verifies_exact_target_before_spb1(self):
        self.trust.refresh(self.targets, self.snapshot, self.timestamp, now=10)
        boundary = SecurityBoundary()
        self.assertEqual(len(boundary.trusted_package(self.trust, self.targets, self.revision, self.package).entries), 1)
        with self.assertRaises(PhysicalSecurityError) as cm:
            boundary.trusted_package(self.trust, self.targets, self.revision, b"not-spb1")
        self.assertEqual(cm.exception.code, "security.trust_target_mismatch")

    def test_root_rotation_requires_old_and_new_threshold_and_exact_candidate(self):
        new_keys = dict(KEYS); new_keys["root-b"] = b"root-b-key"
        candidate = RootMetadata(2, 20_000, new_keys, {
            "root": RolePolicy(frozenset({"root-b"}), 1),
            "targets": RolePolicy(frozenset({"targets-a"}), 1),
            "snapshot": RolePolicy(frozenset({"snapshot-a"}), 1),
            "timestamp": RolePolicy(frozenset({"timestamp-a"}), 1),
        })
        envelope = RoleEnvelope("root", 2, 20_000, root_metadata_body(candidate), (Signature("root-a", KEYS["root-a"]), Signature("root-b", b"root-b-key")))
        self.trust.rotate_root(candidate, envelope, now=10)
        self.assertEqual(self.trust.state.root_version, 2)
        bad = RoleEnvelope("root", 3, 30_000, {"keys": {}, "roles": {}}, (Signature("root-b", b"root-b-key"),))
        with self.assertRaises(PhysicalSecurityError): self.trust.rotate_root(candidate, bad, now=10)

    def test_real_ed25519_verify_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); private = root / "private.pem"; public = root / "public.pem"; message = root / "message"; signature = root / "sig"
            subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            message.write_bytes(b"splashmx-security")
            subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(private), "-in", str(message), "-out", str(signature)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            verifier = OpenSslEd25519Verifier()
            self.assertTrue(verifier.verify(public.read_bytes(), b"splashmx-security", signature.read_bytes()))
            self.assertFalse(verifier.verify(public.read_bytes(), b"tampered", signature.read_bytes()))

    def test_malformed_metadata_campaign_fails_typed_not_raw(self):
        seed = encode_role_envelope(self.targets); rejected = 0
        for index in range(min(96, len(seed))):
            mutant = bytearray(seed); mutant[index] ^= 0x5A
            try: parse_role_envelope(bytes(mutant))
            except PhysicalSecurityError: rejected += 1
            except Exception as exc: self.fail(f"raw exception escaped malformed metadata parser: {type(exc).__name__}: {exc}")
        self.assertGreater(rejected, 0)


class TestFailureTelemetry(unittest.TestCase):
    def test_raw_decoder_exception_text_does_not_escape(self):
        secret = "host-secret-do-not-leak"
        def broken(source, descriptor): raise RuntimeError(secret)
        backend = BrowserWasmDecoder(broken, BrowserIsolationProfile(decoder_module_pinned=True))
        broker = DecoderBroker({"web-hardened": backend})
        with self.assertRaises(PhysicalSecurityError) as cm: broker.decode_bytes(media_payload())
        self.assertEqual(cm.exception.code, "security.decoder_failed")
        self.assertNotIn(secret, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
