#!/usr/bin/env python3
"""Static production-contract validation for SMX-023."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "MODULES.json"
CORE = ROOT / "src" / "splashmx" / "canonical" / "core.py"
TESTS = ROOT / "tests" / "production" / "test_smx023.py"
DOC = ROOT / "docs" / "implementation" / "SMX-023-CANONICAL-CORE.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx023-canonical-core.yml"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, CORE, TESTS, DOC, WORKFLOW):
        require(path.is_file(), f"missing SMX-023 artefact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("canonical.core" in modules, "canonical.core missing from module manifest")
    module = modules["canonical.core"]
    require(module["owner_issue"] == "SMX-023", "canonical.core owner drifted")
    require(module["status"] == "implemented", "canonical.core is not implemented")
    require(module["gate_ids"] == ["GATE-01"], "canonical.core gate ownership drifted")
    for identity in (
        "ThingId", "DefinitionId", "ElementId", "BehaviourAttachmentId",
        "PortId", "ConnectionId", "AssetId", "ProjectId", "ProjectRevisionId",
    ):
        require(identity in module["canonical_identity_inputs"], f"missing identity role {identity}")

    core = CORE.read_text(encoding="utf-8")
    for marker in (
        "class ThingId", "class DefinitionId", "class ElementId",
        "class BehaviourAttachmentId", "class PortId", "class ConnectionId",
        "class AssetId", "class ProjectId", "class ProjectRevisionId",
        "class CanonicalDocument", "class TransientContext", "class PromoteGroup",
        "class InstantiateDefinition", "class ReplaceDefinition", "def apply_transaction",
        "def validate_document", "def definition_conflict_locus",
        "canonical.forbidden_transient_identity",
    ):
        require(marker in core, f"canonical core missing marker: {marker}")

    tests = TESTS.read_text(encoding="utf-8")
    for marker in (
        "test_reparent_changes_only_containment",
        "test_nested_transient_host_identity_is_rejected_before_commit",
        "test_duplicate_identity_rolls_back_earlier_operations",
        "test_r018_01_definition_conflict_locus_includes_definition_identity",
        "test_r018_02_new_connection_to_tombstone_fails_without_resurrection",
        "test_r018_04_thing_tombstone_atomically_tombstones_incident_connections",
        "test_final_document_validation_rejects_dangling_connection_and_rolls_back",
        "test_protected_asset_identity_is_role_typed_without_field_level_media_mutation",
    ):
        require(marker in tests, f"SMX-023 tests missing regression: {marker}")

    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "R-018-01", "R-018-02", "R-018-03", "R-018-04",
        "protected source/audio/provenance", "SMX-024", "Architecture v1.0 unchanged",
        "physical serialization", "transient host/session",
    ):
        require(marker.lower() in doc.lower(), f"SMX-023 documentation missing: {marker}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    require("python tools/validate_smx023.py" in workflow, "SMX-023 workflow lacks validator")
    require("test_smx023.py" in workflow, "SMX-023 workflow lacks production tests")

    print("SMX-023 canonical-core contract valid: module, docs, workflow and adversarial tests present.")


if __name__ == "__main__":
    main()
