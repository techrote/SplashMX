#!/usr/bin/env python3
"""Validate durable SMX-050 production distribution contracts."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/implementation/SMX-050-DISTRIBUTION.md"
FIXTURE = ROOT / "spec/production/smx050-distribution-fixtures.json"
MODULE = ROOT / "src/splashmx/distribution/runtime.py"
INIT = ROOT / "src/splashmx/distribution/__init__.py"
TEST = ROOT / "tests/production/test_smx050.py"
MODULES = ROOT / "src/MODULES.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMX-050 validation failed: {message}")


def main() -> None:
    for path in (DOC, FIXTURE, MODULE, INIT, TEST, MODULES):
        require(path.is_file(), f"missing {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    module_text = MODULE.read_text(encoding="utf-8")
    test_text = TEST.read_text(encoding="utf-8")
    ast.parse(module_text, filename=str(MODULE))
    ast.parse(test_text, filename=str(TEST))

    required_doc_anchors = (
        "exact CreationRevisionId + exact runtime profile + exact runtime digest",
        "Aliases and CDN/cache keys are non-canonical",
        "Cloud/service loss does not invalidate local project ownership",
        "No OS-specific installer technology is selected by SMX-050",
        "Protected source/audio/provenance invariant",
        "No Architecture-v1 amendment is required",
    )
    for anchor in required_doc_anchors:
        require(anchor in doc, f"distribution contract lost required statement: {anchor}")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    require(fixture.get("schema") == "splashmx.smx050-distribution/1", "fixture schema changed")
    policy = fixture.get("policy", {})
    require(policy.get("hosted_binding") == "exact-creation-revision-plus-runtime-digest", "hosted exact binding changed")
    require(policy.get("offline_binding") == "exact-creation-revision-plus-runtime-digest", "offline exact binding changed")
    require(policy.get("aliases_noncanonical") is True, "alias identity separation weakened")
    require(policy.get("cache_keys_noncanonical") is True, "cache identity separation weakened")
    require(policy.get("runtime_revocation_precedence") is True, "runtime revocation precedence weakened")
    require(policy.get("local_ownership_survives_cloud_loss") is True, "local ownership resilience weakened")
    require(policy.get("protected_asset_revision_atomic") is True, "protected Asset atomicity weakened")
    require(
        policy.get("native_packaging") == "exact-portable-payload-only-no-os-installer-selection-without-product-evidence",
        "native packaging evidence boundary changed",
    )
    ids = [row.get("id") for row in fixture.get("fixtures", [])]
    require(ids == [f"DST-{index:03d}" for index in range(1, 25)], "DST-001..024 fixture registry changed")
    require(len(ids) == len(set(ids)), "duplicate distribution fixture identity")

    required_module_anchors = (
        "class RuntimeStore",
        "class HostedDistribution",
        "class OfflineDistributionLibrary",
        "class ContentAddressedCache",
        "distribution.runtime_revoked",
        "export_recovery_archive",
        "import_recovery_archive",
        "protected_asset_disclosures",
        "distribution.native_target_unsupported",
        "ARCHIVE_CHUNK_BYTES",
    )
    for anchor in required_module_anchors:
        require(anchor in module_text, f"production distribution module lost {anchor}")

    required_test_anchors = (
        "distribution.immutable_release",
        "distribution.service_unavailable",
        "distribution.runtime_revoked",
        "distribution.runtime_integrity",
        "distribution.creation_integrity",
        "distribution.native_target_unsupported",
        "distribution.cache_miss",
        "distribution.invalid_replica_count",
    )
    for anchor in required_test_anchors:
        require(anchor in test_text, f"adversarial distribution test lost {anchor}")

    modules = json.loads(MODULES.read_text(encoding="utf-8"))
    entries = {row.get("module_id"): row for row in modules.get("modules", [])}
    distribution = entries.get("distribution.runtime")
    require(distribution is not None, "distribution.runtime missing from module manifest")
    require(distribution.get("owner_issue") == "SMX-050", "distribution.runtime ownership changed")
    require(distribution.get("status") == "implemented", "distribution.runtime not marked implemented")
    forbidden = set(distribution.get("forbidden_identity_classes", []))
    for role in ("url", "cache_key", "session_id", "process_handle"):
        require(role in forbidden, f"distribution.runtime lost forbidden physical identity {role}")

    print("SMX-050 production distribution validated: DST-001..024")


if __name__ == "__main__":
    main()
