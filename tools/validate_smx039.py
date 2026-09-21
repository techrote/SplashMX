#!/usr/bin/env python3
"""Validate the durable SMX-039 physical security mechanism selection."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"SMX-039 contract drift: {needle!r} missing from {path}")


def main() -> None:
    require(
        "docs/research/SMX-039-SECURITY-MECHANISM-SELECTION.md",
        "bounded pathless SPB1 parser",
        "dedicated module Web Worker",
        "fixed maximum linear memory",
        "no_new_privs",
        "seccomp",
        "Landlock",
        "TUF-compatible repository metadata state machine",
        "Ed25519",
        "R-016-01",
        "R-016-02",
        "R-016-03",
        "R-016-04",
        "release-blocked",
        "protected Asset",
        "SMX-040",
        "No Architecture-v1 semantic amendment is required",
    )
    require(
        "src/splashmx/packages/bundle.py",
        'SPB1_MAGIC = b"SPB1"',
        "max_bundle_bytes",
        "max_index_bytes",
        "max_entries",
        "max_entry_bytes",
        "SPB1 payload must be tightly packed in index order",
        "SPB1 contains unindexed payload bytes",
    )
    require(
        "experiments/smx-039-security-mechanism-spike/spike.py",
        "FORBIDDEN_BUNDLE_KINDS",
        "FORBIDDEN_AUTHORITY_KEYS",
        "DecoderBroker",
        "public_untrusted_release_ready",
        "rotate_root",
        "verify_target_metadata",
        "verify_ed25519_with_openssl",
        "signature_trust_grants_capability",
        "PROTECTED_ASSET_FIELDS",
    )
    require(
        "experiments/smx-039-security-mechanism-spike/test_spike.py",
        "test_sec002_non_spb1_archive_is_rejected_before_extraction",
        "test_sec008_decoder_denial_happens_before_decoder_call",
        "test_sec012_memory_unsafe_web_decoder_is_release_blocked",
        "test_sec013_linux_native_requires_complete_worker_sandbox",
        "test_sec018_rollback_and_freeze_are_distinct_failures",
        "test_sec020_root_rotation_requires_old_and_new_thresholds",
        "test_sec021_real_ed25519_roundtrip_and_tamper_rejection",
        "test_sec023_protected_asset_revision_must_be_complete",
    )
    require(
        ".github/workflows/smx039-security-mechanisms.yml",
        "Validate inherited security/package/runtime contracts",
        "Run SMX-039 physical-boundary adversarial spike",
        "python tools/validate_smx039.py",
        "tests.production.test_smx035_adversarial",
        "tests.production.test_smx038",
    )

    corpus = json.loads((ROOT / "docs/research/SMX-039-SECURITY-MECHANISM-FIXTURES.json").read_text(encoding="utf-8"))
    if corpus.get("contract") != "splashmx.smx039-security-mechanism-fixtures/1":
        raise SystemExit("SMX-039 fixture contract drift")
    cases = corpus.get("cases", [])
    ids = [case.get("id") for case in cases]
    expected = [f"SEC-{index:03d}" for index in range(1, 25)]
    if ids != expected:
        raise SystemExit("SMX-039 SEC fixture sequence drift")
    if len({case.get("claim") for case in cases}) != len(cases):
        raise SystemExit("SMX-039 SEC fixture claims must be unique")

    print("SMX-039 selection contract: OK")


if __name__ == "__main__":
    main()
