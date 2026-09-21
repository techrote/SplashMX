from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from splashmx.canonical.core import BehaviourAttachmentId, ThingId
from splashmx.canonical.serialization import (
    SerializationError,
    decode_canonical_cbor,
    encode_canonical_cbor,
)
from splashmx.execution.ir import (
    ExecutionError,
    IRHandler,
    IRInstruction,
    IRProgram,
    ServiceRequest,
    literal,
)
from splashmx.packages.bundle import build_spb1
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
    PhysicalSecurityError,
    probe_linux_sandbox,
    preflight_spb1,
)

ROOT = Path(__file__).resolve().parents[2]


def tiny_decoder(source: bytes, descriptor) -> DecoderResult:
    return DecoderResult(bytes(reversed(source)), len(source))


def media_payload(metadata=None) -> dict:
    source = b"smx041"
    return {
        "profile": "web-hardened",
        "asset_id": "asset.smx041",
        "revision_digest": "revision.smx041.1",
        "source_digest": hashlib.sha256(source).hexdigest(),
        "source": source,
        "predicted_decoded_bytes": len(source),
        "image_pixels": 0,
        "audio_frames": 0,
        "derivative_kind": "test",
        "derivative_version": "1",
        "metadata": metadata or {},
    }


class TestSMX041MalformedCampaigns(unittest.TestCase):
    def test_canonical_cbor_mutation_campaign_is_typed(self):
        seed = encode_canonical_cbor({
            "kind": "security-gate",
            "items": [1, 2, 3, {"nested": True}],
            "message": "bounded",
        })
        rejected = 0
        for index in range(min(96, len(seed))):
            mutant = bytearray(seed)
            mutant[index] ^= (0x41 + index) & 0xFF
            try:
                decode_canonical_cbor(bytes(mutant))
            except SerializationError:
                rejected += 1
            except Exception as exc:  # pragma: no cover - a gate failure
                self.fail(
                    f"raw exception escaped canonical parser: {type(exc).__name__}: {exc}"
                )
        self.assertGreater(rejected, 0)

    def test_spb1_mutation_campaign_never_escapes_typed_boundary(self):
        seed = build_spb1((
            ("manifest", "manifest", b"manifest"),
            ("payload", "data", b"payload"),
        ))
        rejected = 0
        for index in range(min(128, len(seed))):
            mutant = bytearray(seed)
            mutant[index] ^= (0x23 + index) & 0xFF
            try:
                preflight_spb1(bytes(mutant))
            except PhysicalSecurityError:
                rejected += 1
            except Exception as exc:  # pragma: no cover
                self.fail(
                    f"raw exception escaped SPB1 boundary: {type(exc).__name__}: {exc}"
                )
        self.assertGreater(rejected, 0)

    def test_ir_host_opcode_and_authority_campaign_fails_closed(self):
        forbidden_ops = (
            "javascript", "gdscript", "native_call", "filesystem",
            "raw_socket", "raw_network", "spawn_process", "load_extension",
        )
        for op in forbidden_ops:
            with self.subTest(op=op), self.assertRaises(ExecutionError):
                IRProgram(
                    "hostile:1",
                    (IRHandler("go", "go", (IRInstruction(op, {}),)),),
                ).validate()

        forbidden_fields = (
            "NodePath", "ResourceUID", "transport_peer_id",
            "connection_handle", "Capability_Grant",
        )
        for field in forbidden_fields:
            with self.subTest(field=field), self.assertRaises(ExecutionError):
                IRProgram(
                    "hostile-fields:1",
                    (IRHandler(
                        "go",
                        "go",
                        (IRInstruction(
                            "set_private",
                            {"key": "x", "value": literal({field: "forged"})},
                        ),),
                    ),),
                ).validate()

    def test_media_authority_mutations_never_invoke_worker(self):
        forbidden_fields = (
            "Capability_Grant", "NodePath", "ResourceUID", "session_id",
            "process_handle", "javascript_bridge", "loader_authority",
        )
        for field in forbidden_fields:
            backend = BrowserWasmDecoder(
                tiny_decoder,
                BrowserIsolationProfile(decoder_module_pinned=True),
            )
            broker = DecoderBroker({"web-hardened": backend})
            payload = media_payload(
                {"nested": [{"still_nested": {field: "forged"}}]}
            )
            with self.subTest(field=field), self.assertRaises(PhysicalSecurityError) as cm:
                broker.decode_bytes(payload)
            self.assertEqual(cm.exception.code, "security.serialized_authority")
            self.assertEqual(broker.worker_invocations, 0)


class TestSMX041CapabilityRace(unittest.TestCase):
    def test_expiry_after_admission_wins_at_final_real_adapter_boundary(self):
        source = b"smx041"
        backend = BrowserWasmDecoder(
            tiny_decoder,
            BrowserIsolationProfile(decoder_module_pinned=True),
        )
        physical = DecoderBroker(
            {"web-hardened": backend},
            source_provider=lambda asset_id, revision, digest: source,
        )
        payload = media_payload()
        payload.pop("source")
        payload["source_bytes"] = len(source)
        request = ServiceRequest(
            ThingId("thing.smx041"),
            BehaviourAttachmentId("behaviour.smx041"),
            "security.media_decode",
            payload,
            "request.smx041",
            1,
        )
        principal = principal_for_service_request(request)
        grants = CapabilityBroker()
        grants.issue_root_grant(
            grant_id="smx041-expiring",
            principal_id=principal,
            capability_id=CAP_MEDIA_DECODE,
            scope=CapabilityScope(
                frozenset({"asset.smx041"}),
                frozenset({"decode"}),
                len(source),
            ),
            issuer_policy_id="smx041-policy",
            issued_at=1,
            expires_at=12,
        )
        host = TrustedHostServiceBoundary(grants, (physical.host_adapter(),))
        admitted = host.admit(request, now=10)
        with self.assertRaises(Exception) as cm:
            host.execute(admitted, now=12)
        self.assertEqual(getattr(cm.exception, "code", None), "capability.expired")
        self.assertEqual(physical.worker_invocations, 0)


class TestSMX041GateRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(
            (ROOT / "spec/production/smx041-security-gate-fixtures.json").read_text(
                encoding="utf-8"
            )
        )

    def test_full_historical_attack_matrix_is_accounted_for(self):
        coverage = self.record["coverage"]
        self.assertEqual(
            [row["id"] for row in coverage],
            [f"AT-{index:03d}" for index in range(1, 29)],
        )
        represented = {
            attack
            for row in coverage
            for attack in row["attack_classes"]
        }
        self.assertEqual(
            represented,
            {f"ADV-{index:03d}" for index in range(1, 29)},
        )
        deferred = {
            row["id"]
            for row in coverage
            if row["status"] != "pass"
        }
        self.assertEqual(deferred, {"AT-023", "AT-024"})
        self.assertTrue(all(
            next(row for row in coverage if row["id"] == attack_id)["status"]
            == "deferred-no-runtime-network-surface"
            for attack_id in deferred
        ))

    def test_current_target_release_decisions_are_fail_closed(self):
        decisions = {
            row["target"]: row["decision"]
            for row in self.record["target_decisions"]
        }
        self.assertEqual(
            decisions["web"],
            "release-blocked-public-untrusted-decode",
        )
        self.assertEqual(decisions["linux-native"], "conditionally-eligible")
        self.assertEqual(decisions["linux-headless"], "conditionally-eligible")
        for target in ("windows-native", "macos-native", "mobile"):
            self.assertEqual(
                decisions[target],
                "release-blocked-public-untrusted-decode",
            )

        status = probe_linux_sandbox()
        self.assertEqual(status.ready, all(status.__dict__.values()))

    def test_security_gate_is_a_durable_downstream_prerequisite(self):
        self.assertEqual(
            self.record["downstream_security_prerequisites"],
            ["SMX-043", "SMX-045", "SMX-046", "SMX-050"],
        )


if __name__ == "__main__":
    unittest.main()
