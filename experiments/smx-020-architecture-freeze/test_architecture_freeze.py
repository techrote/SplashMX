from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "tools/validate_smx020.py"
AUDIT_PATH = ROOT / "docs/architecture/ARCHITECTURE-V1-AUDIT.json"

spec = importlib.util.spec_from_file_location("validate_smx020", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


class ArchitectureFreezeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    def mutated(self):
        return copy.deepcopy(self.baseline)

    def assert_rejected(self, audit, pattern: str) -> None:
        with self.assertRaisesRegex(AssertionError, pattern):
            validator.validate_audit(audit, check_paths=False)

    def test_baseline_audit_is_closed(self) -> None:
        hypotheses, seams = validator.validate_audit(self.baseline, check_paths=False)
        self.assertEqual(hypotheses, 18)
        self.assertGreaterEqual(seams, 20)

    def test_missing_hypothesis_cannot_freeze(self) -> None:
        audit = self.mutated()
        audit["hypotheses"].pop()
        self.assert_rejected(audit, "expected exactly")

    def test_unresolved_hypothesis_cannot_be_smuggled_into_freeze(self) -> None:
        audit = self.mutated()
        audit["hypotheses"][8]["status"] = "deferred_unresolved_blocker"
        self.assert_rejected(audit, "cannot freeze with unresolved hypothesis blockers")

    def test_hypothesis_without_evidence_is_rejected(self) -> None:
        audit = self.mutated()
        audit["hypotheses"][0]["evidence"] = []
        self.assert_rejected(audit, "lacks evidence references")

    def test_unresolved_cross_domain_seam_is_rejected(self) -> None:
        audit = self.mutated()
        audit["contradiction_audit"][3]["resolution_status"] = "open"
        self.assert_rejected(audit, "is not resolved")

    def test_duplicate_contradiction_identity_is_rejected(self) -> None:
        audit = self.mutated()
        audit["contradiction_audit"][1]["id"] = audit["contradiction_audit"][0]["id"]
        self.assert_rejected(audit, "duplicate contradiction-audit IDs")

    def test_protected_media_cannot_drop_source_metadata(self) -> None:
        audit = self.mutated()
        audit["protected_media_fields"].remove("source_metadata")
        self.assert_rejected(audit, "protected-media field set/order changed")

    def test_protected_media_cannot_reorder_into_an_ambiguous_contract(self) -> None:
        audit = self.mutated()
        fields = audit["protected_media_fields"]
        fields[0], fields[1] = fields[1], fields[0]
        self.assert_rejected(audit, "protected-media field set/order changed")

    def test_destructive_correction_cannot_disappear(self) -> None:
        audit = self.mutated()
        audit["incorporated_corrective_findings"].remove("R-019-01")
        self.assert_rejected(audit, "missing corrective findings")

    def test_authority_chain_cannot_point_at_old_hypothesis_register(self) -> None:
        audit = self.mutated()
        audit["authority"]["architecture"] = "docs/02-ARCHITECTURE-HYPOTHESES.md"
        self.assert_rejected(audit, "authority entry architecture changed")

    def test_residual_implementation_risks_cannot_be_erased_to_overclaim_completion(self) -> None:
        audit = self.mutated()
        audit["post_freeze_residual_classes"] = ["performance"]
        self.assert_rejected(audit, "residual implementation risks were collapsed or lost")

    def test_cross_domain_audit_cannot_be_reduced_below_required_breadth(self) -> None:
        audit = self.mutated()
        audit["contradiction_audit"] = audit["contradiction_audit"][:19]
        self.assert_rejected(audit, "at least 20 cross-domain seams")


if __name__ == "__main__":
    unittest.main()
