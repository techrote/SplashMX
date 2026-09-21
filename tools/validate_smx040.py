#!/usr/bin/env python3
"""Validate durable SMX-040 production security contracts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-040 contract drift: {needle!r} missing from {path}")


def main() -> None:
    require(
        "src/splashmx/security/physical.py",
        "class SecurityBoundary", "class DecoderBroker", "class LinuxProcessDecoder",
        "class RepositoryTrust", "class DerivativeCache", "preflight_spb1",
        "reject_transient_authority", "trust_signature_grants_capability",
        "security.trust_mix_match", "TrustedHostServiceBoundary.execute",
        "PR_SET_NO_NEW_PRIVS", "seccomp", "Landlock", "RLIMIT_NPROC",
        "PROTECTED_ASSET_FIELDS",
    )
    require(
        "src/splashmx/security/web/decoder_worker.mjs",
        "MAX_WASM_PAGES", "validateDecodeMessage", "instantiateDecoder",
        "WebAssembly.Memory", "security.decoder_codec_unregistered",
    )
    require(
        "src/splashmx/security/web/hardened-web-profile.json",
        "connect-src 'none'", "worker-src 'self'", '"javascript_bridge": false',
        "public-untrusted content is blocked",
    )
    require(
        "docs/implementation/SMX-040-PHYSICAL-SECURITY.md",
        "R-016-01", "R-016-02", "R-016-03", "R-016-04",
        "TUF-compatible", "Ed25519", "release-blocked", "protected Asset",
        "No Architecture-v1 semantic amendment is required",
    )
    require(
        "tests/production/test_smx040.py",
        "test_recursive_serialized_authority_denied_before_worker",
        "test_r016_04_revocation_after_admission_stops_real_decoder_host_crossing",
        "test_linux_worker_denies_filesystem_network_and_process_creation",
        "test_snapshot_hash_prevents_same_version_mix_and_match",
        "test_root_rotation_requires_old_and_new_threshold_and_exact_candidate",
        "test_real_ed25519_verify_and_tamper_rejection",
        "test_malformed_metadata_campaign_fails_typed_not_raw",
    )
    require(
        ".github/workflows/smx040-production-security.yml",
        "python tools/validate_smx040.py", "tests.production.test_smx040",
        "smx040_web_worker_test.mjs", "tools/measure_smx040.py",
    )

    corpus = json.loads((ROOT / "spec/production/smx040-security-fixtures.json").read_text(encoding="utf-8"))
    if corpus.get("contract") != "splashmx.smx040-production-security-fixtures/1":
        raise SystemExit("SMX-040 fixture contract drift")
    cases = corpus.get("cases", [])
    ids = [row.get("id") for row in cases]
    expected = [f"PSH-{index:03d}" for index in range(1, 33)]
    if ids != expected:
        raise SystemExit("SMX-040 PSH fixture sequence drift")
    if len({row.get("claim") for row in cases}) != 32:
        raise SystemExit("SMX-040 fixture claims must be unique")
    print("SMX-040 production security contract: OK")


if __name__ == "__main__":
    main()
