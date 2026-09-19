from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from production_contracts import (  # noqa: E402
    ContractError,
    FORBIDDEN_CANONICAL_IDENTITY_CLASSES,
    assert_supported_schema,
    load_json,
    validate,
    validate_module_identity_policy,
)

SPEC = ROOT / "spec" / "production"
REGISTRY = load_json(SPEC / "conformance-registry.json")
MANIFEST = load_json(ROOT / "src" / "MODULES.json")
AUDIT = load_json(
    ROOT / "docs" / "architecture" / "ARCHITECTURE-V1-AUDIT.json"
)
SCHEMAS = {
    "failure": load_json(SPEC / "failure-envelope.schema.json"),
    "artifact": load_json(SPEC / "artifact-version.schema.json"),
    "benchmark": load_json(SPEC / "benchmark-evidence.schema.json"),
    "modules": load_json(SPEC / "module-manifest.schema.json"),
}


class SMX021GuardrailTests(unittest.TestCase):
    def test_all_ten_architecture_gates_are_registered(self) -> None:
        self.assertEqual(
            [row["id"] for row in REGISTRY["gate_entries"]],
            [f"GATE-{index:02d}" for index in range(1, 11)],
        )
        for row in REGISTRY["gate_entries"]:
            self.assertTrue(row["evidence"])
            self.assertTrue(row["owner_modules"])
            self.assertTrue(row["current_tests"])
            self.assertTrue(row["future_issue_codes"])

    def test_evidence_and_current_test_lineage_exists(self) -> None:
        for gate in REGISTRY["gate_entries"]:
            for source in gate["evidence"]:
                self.assertTrue(
                    (ROOT / source["path"]).is_file(),
                    source["path"],
                )
                self.assertTrue(source["anchors"])
            for path in gate["current_tests"]:
                self.assertTrue((ROOT / path).is_file(), path)

    def test_corrections_and_protected_media_are_non_droppable(self) -> None:
        expected = {
            "R-016-01", "R-016-02", "R-016-03", "R-016-04",
            "R-018-01", "R-018-02", "R-018-03", "R-018-04",
            "R-019-01", "XREG-PROTECTED-MEDIA",
        }
        rows = {
            row["id"]: row
            for row in REGISTRY["non_droppable_regressions"]
        }
        self.assertEqual(set(rows), expected)
        self.assertTrue(
            all(row["non_droppable"] for row in rows.values())
        )
        self.assertEqual(
            REGISTRY["protected_media_fields"],
            AUDIT["protected_media_fields"],
        )

    def test_contract_schemas_accept_valid_examples(self) -> None:
        for schema in SCHEMAS.values():
            assert_supported_schema(schema)

        failure = {
            "contract": "splashmx.failure/1",
            "code": "compatibility.required_feature_unsupported",
            "category": "compatibility",
            "author_message_key":
                "error.compatibility.required_feature_unsupported",
            "severity": "error",
            "retryable": False,
            "public_details": [
                {"name": "feature", "value": "future.feature"}
            ],
        }
        artifact = {
            "contract": "splashmx.artifact-version/1",
            "artifact_kind": "project",
            "schema_family": "splashmx.project",
            "schema_version": "1.0",
            "required_features": [],
            "producer": {
                "name": "fixture",
                "version": "0",
                "build_id": "fixture",
            },
        }
        benchmark = {
            "contract": "splashmx.benchmark-evidence/1",
            "evidence_id": "fixture",
            "captured_at_utc": "2026-09-19T00:00:00Z",
            "target_profile": "headless",
            "runtime": {
                "name": "fixture",
                "version": "0",
                "build_id": "fixture",
            },
            "environment": {
                "os": "fixture",
                "arch": "x86_64",
                "hardware": {
                    "cpu": "fixture",
                    "gpu": "none",
                    "memory_bytes": 1024,
                },
            },
            "workload": {
                "id": "fixture",
                "description": "fixture workload",
            },
            "sample_count": 3,
            "metrics": [
                {
                    "name": "duration",
                    "unit": "ms",
                    "statistic": "median",
                    "value": 1.0,
                }
            ],
        }

        validate(failure, SCHEMAS["failure"])
        validate(artifact, SCHEMAS["artifact"])
        validate(benchmark, SCHEMAS["benchmark"])
        validate(MANIFEST, SCHEMAS["modules"])

    def test_failure_envelope_rejects_raw_internal_cause(self) -> None:
        bad = {
            "contract": "splashmx.failure/1",
            "code": "storage.save_denied",
            "category": "storage",
            "author_message_key": "error.storage.save_denied",
            "severity": "error",
            "retryable": False,
            "public_details": [],
            "internal_cause": "Godot Resource path exploded",
        }
        with self.assertRaises(ContractError):
            validate(bad, SCHEMAS["failure"])

    def test_module_identity_policy_rejects_host_identity(self) -> None:
        bad = copy.deepcopy(MANIFEST)
        bad["modules"][0]["canonical_identity_inputs"] = ["NodePath"]
        with self.assertRaises(ContractError):
            validate_module_identity_policy(bad)

    def test_r019_semantic_connection_id_allowed(self) -> None:
        good = copy.deepcopy(MANIFEST)
        good["modules"][0]["canonical_identity_inputs"] = [
            "ConnectionId"
        ]
        validate_module_identity_policy(good)

    def test_r019_transport_connection_handle_forbidden(self) -> None:
        bad = copy.deepcopy(MANIFEST)
        bad["modules"][0]["canonical_identity_inputs"] = [
            "connection_handle"
        ]
        with self.assertRaises(ContractError):
            validate_module_identity_policy(bad)

    def test_every_gate_owner_is_a_declared_module(self) -> None:
        module_ids = {
            row["module_id"]
            for row in MANIFEST["modules"]
        }
        for gate in REGISTRY["gate_entries"]:
            self.assertLessEqual(
                set(gate["owner_modules"]),
                module_ids,
            )

    def test_phase0_activates_only_conformance_contract_module(self) -> None:
        active = [
            row["module_id"]
            for row in MANIFEST["modules"]
            if row["status"] == "active"
        ]
        self.assertEqual(active, ["contracts.conformance"])
        planned = [
            row
            for row in MANIFEST["modules"]
            if row["status"] == "planned"
        ]
        self.assertGreaterEqual(len(planned), 10)

    def test_forbidden_identity_class_contract_is_exact(self) -> None:
        self.assertEqual(
            MANIFEST["forbidden_canonical_identity_classes"],
            list(FORBIDDEN_CANONICAL_IDENTITY_CLASSES),
        )


if __name__ == "__main__":
    unittest.main()
