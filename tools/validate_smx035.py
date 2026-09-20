#!/usr/bin/env python3
"""Validate SMX-035 production package handoff and non-droppable boundaries."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/implementation/SMX-035-PACKAGE-SYSTEM.md"
FIXTURES = ROOT / "spec/production/smx035-package-fixtures.json"
MODEL = ROOT / "src/splashmx/packages/model.py"
RESOLVER = ROOT / "src/splashmx/packages/resolver.py"
BUNDLE = ROOT / "src/splashmx/packages/bundle.py"
SYSTEM = ROOT / "src/splashmx/packages/system.py"
TESTS = ROOT / "tests/production/test_smx035.py"
ADVERSARIAL_TESTS = ROOT / "tests/production/test_smx035_adversarial.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (DOC, FIXTURES, MODEL, RESOLVER, BUNDLE, SYSTEM, TESTS, ADVERSARIAL_TESTS):
        require(path.is_file(), f"missing SMX-035 artifact: {path.relative_to(ROOT)}")
    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "Runtime authority is the exact ResolutionLock",
        "bounded deterministic PubGrub-family",
        "prepare-before-publish",
        "Dependency packages therefore do not inherit a parent package's grants",
        "Protected source/audio/provenance boundary",
        "may not combine fields from competing Asset revisions",
        "No runtime floating",
        "Hostile acquisition ordering",
        "same-count tuple with substituted child revisions",
        "every selected incoming edge is lazy",
    ):
        require(phrase in doc, f"SMX-035 contract lost required phrase: {phrase}")
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(data.get("schema") == "splashmx.smx035-production-package-fixtures/1", "wrong SMX-035 fixture schema")
    fixtures = data.get("fixtures")
    require(isinstance(fixtures, list), "SMX-035 fixtures must be a list")
    require([row.get("id") for row in fixtures] == [f"PPK-{n:03d}" for n in range(1,35)], "PPK fixture set must be contiguous PPK-001..PPK-034")
    classes = {row.get("class") for row in fixtures}
    require({"identity","resolution","lock","bundle","authority","component","update","cache","protected-media","provenance","artifact"}.issubset(classes), "SMX-035 fixture classes incomplete")
    source = "\n".join(path.read_text(encoding="utf-8") for path in (MODEL,RESOLVER,BUNDLE,SYSTEM))
    for token in (
        "ResolutionLock", "SPB1_MAGIC", "max_decisions", "_FORBIDDEN_MANIFEST_FIELDS",
        "ProtectedAssetRevision", "principal_for_component", "migration_prepare", "ExactAcquirer",
        "promote_definition", "package.version_conflict", "validate_lock_dependencies",
        "incoming_kinds", "_optional_dependencies",
    ):
        require(token in source, f"SMX-035 production boundary missing token: {token}")
    tests = TESTS.read_text(encoding="utf-8")
    for token in (
        "test_conflict_driven_backtracking_finds_coherent_closure",
        "test_optional_conflict_cannot_perturb_required_revision",
        "test_optional_transitive_failure_uses_fallback_without_leaking_subtree",
        "test_spb1_roundtrip_is_pathless_tight_and_digest_verified",
        "test_protected_asset_field_mixing_surface_is_closed",
        "test_corrupt_or_malformed_package_never_reaches_migration",
        "test_failed_migration_leaves_previous_exact_lock_and_live_state_coherent",
        "test_dependency_principal_does_not_inherit_parent_grant",
        "test_lazy_dependency_materializes_only_exact_locked_revision",
        "test_verified_cache_supports_exact_offline_reopen_but_never_floats",
    ):
        require(token in tests, f"SMX-035 adversarial regression missing: {token}")
    adversarial = ADVERSARIAL_TESTS.read_text(encoding="utf-8")
    for token in (
        "test_same_count_forged_child_revision_is_rejected_before_migration",
        "test_locked_child_version_must_satisfy_manifest_requirement",
        "test_manifest_declared_optional_dependency_is_resolved_when_available",
        "test_manifest_declared_optional_failure_does_not_damage_required_closure",
        "test_required_plus_lazy_incoming_edges_are_never_order_dependent_lazy",
    ):
        require(token in adversarial, f"SMX-035 corrective regression missing: {token}")
    print("SMX-035 production package contract: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMX-035 validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
