from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
PRODUCTION = ROOT / "tests" / "production"
for path in (SRC, TOOLS, PRODUCTION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from export_smx037_fixture import (  # noqa: E402
    FACETS,
    FORBIDDEN_HANDLE_FIELDS,
    build_fixture,
    validate_fixture,
)
from smx031_harness import AUDIO, build_project  # noqa: E402


class SMX037GodotSelectionTests(unittest.TestCase):
    def test_projection_is_derived_from_exact_production_core_things(self):
        fixture = build_fixture()
        project = build_project()
        expected = {str(key) for key in project.document.things}
        self.assertEqual(expected, set(FACETS))
        self.assertEqual(expected, {row["thing_id"] for row in fixture["things"]})

    def test_projection_contains_no_forbidden_runtime_handle_fields(self):
        fixture = build_fixture()
        validate_fixture(fixture)

        def keys(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    yield str(key)
                    yield from keys(nested)
            elif isinstance(value, list):
                for nested in value:
                    yield from keys(nested)

        self.assertTrue(set(keys(fixture)).isdisjoint(FORBIDDEN_HANDLE_FIELDS))

    def test_semantic_only_things_exist_without_engine_facets(self):
        fixture = build_fixture()
        zero = {row["thing_id"] for row in fixture["things"] if not row["facets"]}
        self.assertEqual({"inventory", "budget-bomb"}, zero)

    def test_protected_asset_is_exact_reference_not_field_projection(self):
        fixture = build_fixture()
        project = build_project()
        protected = project.assets[AUDIO]
        self.assertEqual(
            fixture["protected_asset_refs"],
            [{"asset_id": str(AUDIO), "revision_digest": protected.revision_digest}],
        )
        serialized = json.dumps(fixture, sort_keys=True)
        for forbidden_semantic_field in (
            "source_metadata", "media_semantics", "provenance",
            "licence_attribution", "derivation_lineage",
        ):
            self.assertNotIn(forbidden_semantic_field, serialized)

    def test_target_profiles_are_policy_not_distinct_documents(self):
        fixture = build_fixture()
        self.assertEqual("splashmx.godot-binding-fixture/1", fixture["contract"])
        self.assertEqual({"native", "browser", "headless"}, set(fixture["target_profiles"]))
        self.assertEqual("physics_2d", fixture["target_profiles"]["headless"]["required"][0])
        self.assertIn("render_2d", fixture["target_profiles"]["headless"]["optional"])

    def test_fixture_corpus_is_complete_and_unique(self):
        corpus = json.loads((ROOT / "spec/production/smx037-godot-binding-fixtures.json").read_text())
        ids = [case["id"] for case in corpus["cases"]]
        self.assertEqual([f"GBS-{index:03d}" for index in range(1, 25)], ids)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
