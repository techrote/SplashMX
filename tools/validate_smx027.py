#!/usr/bin/env python3
"""Static production-contract validation for SMX-027."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "MODULES.json"
REGISTRY = ROOT / "spec" / "production" / "conformance-registry.json"
SOURCE = ROOT / "src" / "splashmx" / "security" / "capabilities.py"
INIT = ROOT / "src" / "splashmx" / "security" / "__init__.py"
TESTS = ROOT / "tests" / "production" / "test_smx027.py"
FIXTURES = ROOT / "spec" / "production" / "smx027-capability-fixtures.json"
DOC = ROOT / "docs" / "implementation" / "SMX-027-CAPABILITY-BOUNDARY.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx027-capabilities.yml"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, REGISTRY, SOURCE, INIT, TESTS, FIXTURES, DOC, WORKFLOW):
        require(path.is_file(), f"missing SMX-027 artefact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    module = modules.get("security.capabilities")
    require(module is not None, "security.capabilities missing from module manifest")
    require(module["owner_issue"] == "SMX-027", "security.capabilities owner drifted")
    require(module["status"] == "implemented", "security.capabilities is not implemented")
    require(module["gate_ids"] == ["GATE-02", "GATE-03"], "security.capabilities gate ownership drifted")
    for identity in ("PrincipalId", "CapabilityId"):
        require(identity in module["canonical_identity_inputs"], f"missing capability identity role {identity}")
    for responsibility in (
        "principal-attributed capability grants and declarations",
        "bounded narrowing delegation, expiry and revocation",
        "trusted host-service admission and final-use authorization",
        "per-principal host-service quotas and typed failures",
    ):
        require(responsibility in module["responsibilities"], f"missing responsibility: {responsibility}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for gate_id in ("GATE-02", "GATE-03", "GATE-07"):
        gate = next(row for row in registry["gate_entries"] if row["id"] == gate_id)
        for current in ("tools/validate_smx027.py", "tests/production/test_smx027.py"):
            require(current in gate["current_tests"], f"{gate_id} missing SMX-027 production evidence: {current}")
        require("SMX-027" not in gate["future_issue_codes"], f"{gate_id} still treats completed SMX-027 as future")
        require(
            any(row["path"] == "docs/implementation/SMX-027-CAPABILITY-BOUNDARY.md" for row in gate["evidence"]),
            f"{gate_id} missing SMX-027 implementation evidence",
        )
    for repair in ("R-016-02", "R-016-03", "R-016-04"):
        row = next(row for row in registry["non_droppable_regressions"] if row["id"] == repair)
        require(
            "docs/implementation/SMX-027-CAPABILITY-BOUNDARY.md" in row["evidence_paths"],
            f"{repair} missing SMX-027 production evidence",
        )
        require("SMX-027" not in row["future_issue_codes"], f"{repair} still treats SMX-027 as future")

    source = SOURCE.read_text(encoding="utf-8")
    for marker in (
        "class PrincipalId", "class CapabilityId", "class CapabilityScope", "class CapabilityGrant",
        "class CapabilityBroker", "from_trusted_grants", "max_delegation_depth",
        "max_descendants_per_root", "def delegate", "def revoke", "def authorize_grant",
        "class CapabilityRequirement", "class CapabilityPlan", "def resolve_requirements",
        "def principal_for_service_request", "def validate_untrusted_service_value",
        "class HostServiceAdapter", "class TrustedHostServiceBoundary", "def admit", "def execute",
        "capability.serialized_authority", "capability.cyclic_ancestry", "capability.missing_ancestry",
        "capability.delegation_depth", "capability.delegation_count", "capability.required_denied",
        "capability.host_service_failed", "R-016-04",
    ):
        require(marker in source, f"capability source missing contract marker: {marker}")
    for forbidden in ("capabilitytoken", "capabilitygrant", "grantid", "javascriptbridge", "processhandle", "sessionid"):
        require(forbidden in source, f"host-service recursive authority denial missing: {forbidden}")

    tests = TESTS.read_text(encoding="utf-8")
    for marker in (
        "test_no_ambient_authority_and_signing_provenance_never_create_grant",
        "test_parent_or_containment_grant_does_not_authorize_child_principal",
        "test_scope_target_operation_and_byte_ceiling_are_all_enforced",
        "test_delegation_is_monotonic_and_lifetime_cannot_widen",
        "test_delegation_depth_and_count_fail_before_new_grant_is_allocated",
        "test_trusted_snapshot_rejects_missing_and_cyclic_ancestry_boundedly",
        "test_revocation_and_expiry_of_ancestor_invalidate_delegated_lease",
        "test_required_denial_fails_and_optional_denial_selects_explicit_reduced_mode",
        "test_service_request_principal_is_exact_thing_attachment_origin",
        "test_parent_grant_cannot_be_used_as_confused_deputy_for_child_request",
        "test_admission_never_invokes_host_and_execute_crosses_only_after_authorization",
        "test_revocation_between_admission_and_host_crossing_fails_closed",
        "test_expiry_between_admission_and_host_crossing_fails_closed",
        "test_recursive_serialized_authority_is_rejected_again_at_service_boundary",
        "test_copying_grant_id_in_payload_cannot_launder_authority",
        "test_service_request_quota_is_principal_scoped_and_checked_before_admission",
        "test_unknown_service_and_scope_violation_fail_before_host_use",
        "test_raw_host_object_result_is_not_returned_to_content",
        "test_raw_host_exception_is_wrapped_in_typed_failure",
        "test_untrusted_payload_cannot_smuggle_raw_engine_browser_or_session_handles",
    ):
        require(marker in tests, f"SMX-027 tests missing adversarial regression: {marker}")

    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(fixtures["schema"] == "splashmx-smx027-capability-fixtures-v1", "fixture schema drifted")
    require([row["id"] for row in fixtures["fixtures"]] == [f"CAP-{i:03d}" for i in range(1, 25)], "CAP fixture set must remain CAP-001..CAP-024")
    require(fixtures["corrective_repairs"] == ["R-016-02", "R-016-03", "R-016-04"], "repair lineage drifted")
    require(
        fixtures["protected_media"]["fields"] == [
            "digest", "source_identity", "source_metadata", "audio_or_media_semantics",
            "provenance", "licence_attribution", "derivation_lineage",
        ],
        "protected-media field set drifted",
    )

    doc = DOC.read_text(encoding="utf-8").lower()
    for marker in (
        "deny-by-default", "principalid(\"behaviour:<thingid>:<behaviourattachmentid>\")",
        "r-016-02", "r-016-03", "r-016-04", "final semantic operation before the trusted adapter call",
        "optional", "reduced_mode", "signing/provenance/licensing", "source digest", "source identity",
        "source metadata", "audio/media semantics", "provenance", "licence/attribution", "derivation lineage",
        "not end-to-end sandbox certification", "architecture v1.0 remains unchanged",
    ):
        require(marker in doc, f"SMX-027 documentation missing: {marker}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "python tools/validate_smx006.py", "python tools/validate_smx016.py",
        "experiments/smx-016-security-harness", "python tools/validate_smx026.py",
        "test_smx026.py", "python tools/validate_smx027.py", "test_smx027.py",
    ):
        require(marker in workflow, f"SMX-027 workflow missing: {marker}")

    print(
        "SMX-027 capability contract valid: exact principals, deny-by-default grants, bounded delegation, "
        "revocation/expiry, final-use host authorization, adversarial coverage and protected-media boundary present."
    )


if __name__ == "__main__":
    main()
