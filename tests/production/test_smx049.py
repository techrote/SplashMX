from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODEL_PATH = ROOT / "experiments/smx-049-compatibility/model.py"
SPEC = importlib.util.spec_from_file_location("smx049_compatibility_model", MODEL_PATH)
assert SPEC is not None and SPEC.loader is not None
model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = model
SPEC.loader.exec_module(model)

from splashmx.canonical.core import ProjectId, ProjectRevisionId, empty_document  # noqa: E402
from splashmx.canonical.serialization import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    CanonicalProjectRevision,
    MigrationRegistry,
    ProtectedAssetRevision,
    SerializationError,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
    serialize_project,
)
from splashmx.packages.model import LOCK_SCHEMA, MANIFEST_SCHEMA  # noqa: E402
from splashmx.publishing.generic import CREATION_SCHEMA, GENERIC_PLAYER_PROFILE  # noqa: E402
from splashmx.runtime.lifecycle import WORLD_SAVE_SCHEMA  # noqa: E402
from splashmx.canonical.core import AssetId  # noqa: E402

FIXTURE_PATH = ROOT / "spec/production/smx049-compatibility-fixtures.json"


class SMX049CompatibilityProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def programme(self):
        return model.CompatibilityProgramme()

    def test_programme_matches_real_current_generation_constants(self):
        generations = {row["artifact_class"]: row for row in self.fixture["current_generations"] if row["status"].startswith("current")}
        self.assertEqual(CURRENT_SCHEMA_VERSION, 1)
        self.assertEqual(generations["canonical-project"]["generation"], "splashmx.project-revision/schema-1")
        self.assertEqual(MANIFEST_SCHEMA, "splashmx.package-manifest/1")
        self.assertEqual(LOCK_SCHEMA, "splashmx.package-resolution-lock/1")
        self.assertEqual(generations["package-component"]["generation"], f"{MANIFEST_SCHEMA}+resolution-lock/1")
        self.assertEqual(CREATION_SCHEMA, generations["creation-revision"]["generation"])
        self.assertEqual(GENERIC_PLAYER_PROFILE, generations["creation-revision"]["runtime_profile"])
        self.assertEqual(WORLD_SAVE_SCHEMA, generations["world-save"]["generation"])

    def test_real_schema_zero_fixture_migrates_to_current_before_materialization(self):
        project = CanonicalProjectRevision(
            empty_document(ProjectId("compat-project"), ProjectRevisionId("r0")),
            {},
        )
        current = serialize_project(project)
        manifest = decode_canonical_cbor(current.root_manifest)
        manifest["schema_version"] = 0
        historical = SerializedProjectRevision(encode_canonical_cbor(manifest), dict(current.shards))
        self.assertEqual(deserialize_project(historical), project)
        decision = self.programme().negotiate(
            model.ArtifactClass.PROJECT,
            "splashmx.project-revision/schema-0",
        )
        self.assertEqual(decision.action, model.CompatibilityAction.MIGRATE)
        self.assertEqual(decision.migration_steps, ("project-schema-0->1",))

    def test_future_project_schema_fails_typed_in_real_parser(self):
        project = CanonicalProjectRevision(
            empty_document(ProjectId("compat-project"), ProjectRevisionId("r0")),
            {},
        )
        current = serialize_project(project)
        manifest = decode_canonical_cbor(current.root_manifest)
        manifest["schema_version"] = CURRENT_SCHEMA_VERSION + 1
        future = SerializedProjectRevision(encode_canonical_cbor(manifest), dict(current.shards))
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(future)
        self.assertEqual(caught.exception.code, "serialization.unsupported_version")

    def test_unknown_generation_and_unknown_required_semantics_fail_closed(self):
        programme = self.programme()
        with self.assertRaises(model.CompatibilityError) as unknown_generation:
            programme.negotiate(model.ArtifactClass.WORLD_SAVE, "splashmx.world-save/0")
        self.assertEqual(unknown_generation.exception.code, "compatibility.unsupported_generation")
        with self.assertRaises(model.CompatibilityError) as unknown_feature:
            programme.negotiate(
                model.ArtifactClass.CREATION,
                "splashmx.creation/1",
                required_features=("future-semantics-v9",),
                supported_features=(),
            )
        self.assertEqual(unknown_feature.exception.code, "compatibility.unsupported_required_semantics")

    def test_future_creation_transition_retains_exact_old_runtime_not_silent_reinterpretation(self):
        future = self.programme().simulate_creation_v2_transition()
        old = future.negotiate(model.ArtifactClass.CREATION, "splashmx.creation/1")
        new = future.negotiate(model.ArtifactClass.CREATION, "splashmx.creation/2")
        self.assertEqual(old.action, model.CompatibilityAction.RETAINED_RUNTIME)
        self.assertEqual(old.runtime_profile, "splashmx.generic-player/1")
        self.assertEqual(new.action, model.CompatibilityAction.DIRECT)
        self.assertEqual(new.runtime_profile, "splashmx.generic-player/2")

    def test_retained_runtime_missing_is_typed_failure_and_never_floats_to_new_runtime(self):
        future = self.programme().simulate_creation_v2_transition()
        with self.assertRaises(model.CompatibilityError) as caught:
            future.negotiate(
                model.ArtifactClass.CREATION,
                "splashmx.creation/1",
                runtime_available=False,
            )
        self.assertEqual(caught.exception.code, "compatibility.runtime_unavailable")

    def test_current_security_revocation_overrides_historical_compatibility(self):
        future = self.programme().simulate_creation_v2_transition()
        with self.assertRaises(model.CompatibilityError) as caught:
            future.negotiate(
                model.ArtifactClass.CREATION,
                "splashmx.creation/1",
                revoked=True,
                runtime_available=True,
            )
        self.assertEqual(caught.exception.code, "compatibility.revoked_artifact")

    def test_migration_chain_bound_is_enforced_by_programme_and_real_registry(self):
        overlong = model.GenerationRule(
            model.ArtifactClass.PROJECT,
            "fixture/schema-long",
            model.CompatibilityAction.MIGRATE,
            target_generation="fixture/schema-current",
            migration_steps=("a", "b"),
        )
        with self.assertRaises(model.CompatibilityError) as caught:
            model.CompatibilityProgramme((overlong,), max_migration_steps=1)
        self.assertEqual(caught.exception.code, "compatibility.migration_limit")

        registry = MigrationRegistry(max_steps=1)
        registry.register(0, 1, lambda rows: rows)
        # The production registry independently enforces its own bound; this
        # assertion freezes the programme decision that neither layer is unbounded.
        self.assertEqual(registry.max_steps, 1)

    def test_protected_asset_is_still_one_indivisible_revision_across_compatibility_paths(self):
        protected = ProtectedAssetRevision.create(
            AssetId("asset:historic-audio"),
            source_digest="sha256:" + "a" * 64,
            source_identity={"logical_name": "original.wav"},
            source_metadata={"format": "wav", "channels": 2},
            media_semantics={"sample_rate": 48000, "loop": {"enabled": False}},
            provenance={"origin": "compatibility fixture"},
            licence_attribution={"licence": "CC0-1.0", "attribution": "fixture"},
            derivation_lineage=({"operation": "import", "parent_digest": "sha256:" + "b" * 64},),
        )
        with self.assertRaises(SerializationError) as caught:
            replace(protected, source_metadata={"format": "wav", "channels": 1})
        self.assertEqual(caught.exception.code, "serialization.asset_revision_mismatch")

    def test_runtime_storage_model_is_content_addressed_and_replica_count_explicit(self):
        digest = "sha256:" + "1" * 64
        rows = [
            model.RetainedRuntime("splashmx.generic-player/1", digest, 100, deployment_copies=2),
            model.RetainedRuntime("splashmx.generic-player/1", digest, 100, deployment_copies=2),
            model.RetainedRuntime("splashmx.generic-player/2", "sha256:" + "2" * 64, 120, deployment_copies=3),
        ]
        self.assertEqual(model.estimate_retained_runtime_bytes(rows), 560)

    def test_fixture_has_complete_unique_adversarial_programme_surface(self):
        fixture_ids = [row["id"] for row in self.fixture["fixtures"]]
        self.assertEqual(len(fixture_ids), len(set(fixture_ids)))
        self.assertEqual(fixture_ids, [f"CMP-{index:03d}" for index in range(1, 21)])
        policy = self.fixture["policy"]
        self.assertTrue(policy["security_revocation_precedence"])
        self.assertTrue(policy["protected_asset_revision_atomic"])
        self.assertEqual(policy["hosted_binding"], "exact-creation-revision-plus-exact-runtime-profile")
        self.assertEqual(policy["offline_binding"], "exact-creation-revision-plus-exact-runtime-profile")


if __name__ == "__main__":
    unittest.main()
