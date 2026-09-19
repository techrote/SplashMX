#!/usr/bin/env python3
"""Validate SMX-021 production conformance guardrails."""
from __future__ import annotations

import re
from pathlib import Path

from production_contracts import (
    assert_supported_schema,
    load_json,
    validate,
    validate_module_identity_policy,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "production"
REGISTRY = SPEC / "conformance-registry.json"
MODULES = ROOT / "src" / "MODULES.json"
AUDIT = ROOT / "docs" / "architecture" / "ARCHITECTURE-V1-AUDIT.json"
CI = ROOT / ".github" / "workflows" / "ci.yml"

SCHEMAS = {
    "failure": SPEC / "failure-envelope.schema.json",
    "artifact": SPEC / "artifact-version.schema.json",
    "benchmark": SPEC / "benchmark-evidence.schema.json",
    "modules": SPEC / "module-manifest.schema.json",
}

REQUIRED_FILES = [
    REGISTRY,
    MODULES,
    ROOT / "src" / "README.md",
    ROOT / "tests" / "production" / "test_smx021.py",
    ROOT / "docs" / "implementation" / "PRODUCTION-CONFORMANCE-V1.md",
    SPEC / "README.md",
    *SCHEMAS.values(),
]

EXPECTED_GATES = [f"GATE-{index:02d}" for index in range(1, 11)]
EXPECTED_CORRECTIONS = {
    "R-016-01", "R-016-02", "R-016-03", "R-016-04",
    "R-018-01", "R-018-02", "R-018-03", "R-018-04",
    "R-019-01",
}
PROTECTED_ID = "XREG-PROTECTED-MEDIA"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sample_documents() -> dict[str, dict]:
    return {
        "failure": {
            "contract": "splashmx.failure/1",
            "code": "storage.save_denied",
            "category": "storage",
            "author_message_key": "error.storage.save_denied",
            "severity": "error",
            "retryable": False,
            "public_details": [
                {"name": "project_id", "value": "project-example"}
            ],
            "diagnostic_id": "diag:example",
        },
        "artifact": {
            "contract": "splashmx.artifact-version/1",
            "artifact_kind": "project",
            "schema_family": "splashmx.project",
            "schema_version": "1.0",
            "required_features": ["thing.kernel"],
            "producer": {
                "name": "splashmx-test",
                "version": "0.0.0",
                "build_id": "fixture",
            },
        },
        "benchmark": {
            "contract": "splashmx.benchmark-evidence/1",
            "evidence_id": "fixture:smx021",
            "captured_at_utc": "2026-09-19T00:00:00Z",
            "target_profile": "browser",
            "runtime": {
                "name": "fixture-runtime",
                "version": "0",
                "build_id": "fixture",
            },
            "browser": {
                "name": "fixture-browser",
                "version": "0",
            },
            "environment": {
                "os": "fixture-os",
                "arch": "x86_64",
                "hardware": {
                    "cpu": "fixture-cpu",
                    "gpu": "fixture-gpu",
                    "memory_bytes": 1,
                },
            },
            "workload": {
                "id": "fixture",
                "description": "schema validation fixture",
            },
            "sample_count": 1,
            "metrics": [
                {
                    "name": "duration",
                    "unit": "ms",
                    "statistic": "single",
                    "value": 1.0,
                }
            ],
        },
    }


def main() -> None:
    for path in REQUIRED_FILES:
        require(
            path.is_file(),
            f"missing SMX-021 required file: {path.relative_to(ROOT)}",
        )

    registry = load_json(REGISTRY)
    audit = load_json(AUDIT)
    manifest = load_json(MODULES)
    schemas = {
        name: load_json(path)
        for name, path in SCHEMAS.items()
    }

    require(
        registry.get("schema")
        == "splashmx.production-conformance-registry/1",
        "unexpected registry schema",
    )
    require(
        registry.get("architecture_version") == "1.0",
        "registry architecture version mismatch",
    )

    gate_entries = registry.get("gate_entries")
    require(
        isinstance(gate_entries, list),
        "registry gate_entries must be a list",
    )
    gate_ids = [entry.get("id") for entry in gate_entries]
    require(
        gate_ids == EXPECTED_GATES,
        f"registry must contain exactly {EXPECTED_GATES}; got {gate_ids}",
    )

    module_ids = {
        module["module_id"]
        for module in manifest.get("modules", [])
    }
    require(
        "contracts.conformance" in module_ids,
        "Phase-0 conformance module missing",
    )

    for entry in gate_entries:
        require(entry.get("requirement"), f"{entry['id']} lacks requirement")
        evidence = entry.get("evidence")
        require(
            isinstance(evidence, list) and evidence,
            f"{entry['id']} lacks evidence lineage",
        )
        for source in evidence:
            path = ROOT / source["path"]
            require(
                path.is_file(),
                f"{entry['id']} evidence path missing: {source['path']}",
            )
            require(
                source.get("anchors"),
                f"{entry['id']} evidence source lacks anchors",
            )

        owners = entry.get("owner_modules")
        require(
            isinstance(owners, list) and owners,
            f"{entry['id']} lacks owner modules",
        )
        unknown_owners = sorted(set(owners) - module_ids)
        require(
            not unknown_owners,
            f"{entry['id']} references unknown owner modules "
            f"{unknown_owners}",
        )

        current = entry.get("current_tests")
        future = entry.get("future_issue_codes")
        require(
            isinstance(current, list) and current,
            f"{entry['id']} lacks current test lineage",
        )
        require(
            isinstance(future, list) and future,
            f"{entry['id']} lacks future test/issue lineage",
        )
        for rel in current:
            require(
                (ROOT / rel).is_file(),
                f"{entry['id']} current test path missing: {rel}",
            )
        for issue in future:
            require(
                re.fullmatch(r"SMX-\d{3}", issue) is not None,
                f"{entry['id']} invalid future issue code {issue}",
            )

    regressions = registry.get("non_droppable_regressions")
    require(
        isinstance(regressions, list),
        "non_droppable_regressions must be a list",
    )
    regression_ids = {row.get("id") for row in regressions}
    require(
        EXPECTED_CORRECTIONS <= regression_ids,
        "registry missing corrections "
        f"{sorted(EXPECTED_CORRECTIONS - regression_ids)}",
    )
    require(
        PROTECTED_ID in regression_ids,
        "registry missing protected-media cross-cutting regression",
    )
    for row in regressions:
        require(
            row.get("non_droppable") is True,
            f"{row.get('id')} is not non-droppable",
        )
        for rel in row.get("evidence_paths", []):
            require(
                (ROOT / rel).is_file(),
                f"{row.get('id')} evidence path missing: {rel}",
            )
        require(
            set(row.get("owner_modules", [])) <= module_ids,
            f"{row.get('id')} has unknown owner module",
        )

    audit_corrections = set(
        audit.get("incorporated_corrective_findings", [])
    )
    require(
        EXPECTED_CORRECTIONS <= audit_corrections,
        "Architecture-v1 audit no longer contains required corrections",
    )
    require(
        registry.get("protected_media_fields")
        == audit.get("protected_media_fields"),
        "registry protected-media fields differ from Architecture-v1 audit",
    )

    for schema in schemas.values():
        assert_supported_schema(schema)

    samples = sample_documents()
    validate(samples["failure"], schemas["failure"])
    validate(samples["artifact"], schemas["artifact"])
    validate(samples["benchmark"], schemas["benchmark"])
    validate(manifest, schemas["modules"])
    validate_module_identity_policy(manifest)

    active = [
        module["module_id"]
        for module in manifest["modules"]
        if module["status"] == "active"
    ]
    require(
        active == ["contracts.conformance"],
        f"Phase-0 must activate only contracts.conformance; got {active}",
    )

    ci = CI.read_text(encoding="utf-8")
    for command in (
        "python tools/validate_smx021.py",
        "python -m unittest discover -s tests/production "
        "-p 'test_smx021.py' -v",
    ):
        require(command in ci, f"CI missing SMX-021 command: {command}")

    print(
        "SMX-021 production guardrails valid: "
        f"{len(gate_entries)} Architecture-v1 gates, "
        f"{len(regressions)} non-droppable regressions, "
        f"{len(manifest['modules'])} module ownership records."
    )


if __name__ == "__main__":
    main()
