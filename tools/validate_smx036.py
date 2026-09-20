#!/usr/bin/env python3
"""Validate SMX-036 production publication/player handoff."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/implementation/SMX-036-GENERIC-PUBLISHING.md"
FIXTURES = ROOT / "spec/production/smx036-publishing-fixtures.json"
SOURCE = ROOT / "src/splashmx/publishing/generic.py"
MODULES = ROOT / "src/MODULES.json"
TESTS = ROOT / "tests/production/test_smx036.py"
ADVERSARIAL = ROOT / "tests/production/test_smx036_adversarial.py"
WORKFLOW = ROOT / ".github/workflows/smx036-generic-publishing.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, SOURCE, MODULES, TESTS, ADVERSARIAL, WORKFLOW):
        require(path.is_file(), f"missing SMX-036 artifact: {path.relative_to(ROOT)}")

    doc = DOC.read_text(encoding="utf-8")
    # Contract prose is wrapped for readability and may use Markdown emphasis;
    # validate semantic phrases rather than depending on physical line wrapping.
    doc_contract = " ".join(doc.replace("**", "").split())
    for phrase in (
        "Ordinary Publish",
        "per-creation engine build",
        "Exact closure and no floating",
        "Generic player prepare-before-activate",
        "WorldSave identity and basis",
        "Protected source/audio/provenance boundary",
        "may not combine fields from competing Asset revisions",
        "Target-private stripping",
        "no runtime floating",
    ):
        require(phrase in doc_contract, f"SMX-036 contract lost required phrase: {phrase}")

    fixture_data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(
        fixture_data.get("schema") == "splashmx.smx036-publishing-fixtures/1",
        "wrong SMX-036 fixture schema",
    )
    fixtures = fixture_data.get("fixtures")
    require(isinstance(fixtures, list), "SMX-036 fixtures must be a list")
    require(
        [row.get("id") for row in fixtures] == [f"PUB-{n:03d}" for n in range(1, 25)],
        "PUB fixture set must be contiguous PUB-001..PUB-024",
    )
    classes = {row.get("class") for row in fixtures}
    require(
        {
            "identity", "immutability", "closure", "dependency", "activation",
            "hosted", "offline", "worldsave", "protected-media", "authority", "build",
        }.issubset(classes),
        "SMX-036 fixture classes incomplete",
    )

    source = SOURCE.read_text(encoding="utf-8")
    for token in (
        "CreationRevisionId",
        "HostedReleaseStore",
        "OfflineLibrary",
        "GenericPlayer",
        "WorldSaveBasis",
        "publish_creation",
        "decode_creation_manifest",
        "validate_lock_dependencies",
        "ProtectedAssetRevision",
        "publication.floating_dependency",
        "publication.protected_asset_conflict",
        "publication.offline_unavailable",
    ):
        require(token in source, f"SMX-036 production boundary missing token: {token}")

    modules = json.loads(MODULES.read_text(encoding="utf-8"))
    publishing = next(
        (row for row in modules.get("modules", []) if row.get("module_id") == "publishing.generic"),
        None,
    )
    require(publishing is not None, "publishing.generic module missing")
    require(publishing.get("status") == "implemented", "publishing.generic must be implemented")
    require(
        {"CreationId", "CreationRevisionId", "WorldSaveId"}.issubset(
            set(publishing.get("canonical_identity_inputs", []))
        ),
        "publishing.generic identity inputs incomplete",
    )

    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_publish_is_deterministic_immutable_data_not_a_build",
        "test_same_creation_revision_loads_hosted_and_exact_offline",
        "test_friendly_alias_can_retarget_without_mutating_immutable_releases",
        "test_worldsave_creation_and_alias_roles_remain_distinct",
        "test_target_derivative_is_private_and_cannot_rebind_asset_semantics",
        "test_exact_offline_missing_revision_never_floats",
        "test_lazy_package_is_still_part_of_exact_offline_publication_closure",
    ):
        require(token in tests, f"SMX-036 production regression missing: {token}")

    adversarial = ADVERSARIAL.read_text(encoding="utf-8")
    for token in (
        "test_tampered_creation_manifest_fails_before_activation",
        "test_tampered_project_blob_fails_before_activation",
        "test_tampered_dependency_blob_fails_before_activation",
        "test_floating_dependency_substitution_is_rejected_at_publish",
        "test_unknown_required_creation_feature_fails_before_activation",
        "test_protected_asset_field_mixing_across_project_and_package_is_rejected",
        "test_unreferenced_extra_blob_is_rejected_before_activation",
        "test_creation_revision_and_release_cannot_be_rebound",
    ):
        require(token in adversarial, f"SMX-036 adversarial regression missing: {token}")

    print("SMX-036 generic publishing contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-036 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
