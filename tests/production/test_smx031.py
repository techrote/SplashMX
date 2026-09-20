from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PRODUCTION = ROOT / "tests" / "production"
for path in (SRC, PRODUCTION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from smx031_harness import (  # noqa: E402
    AUDIO,
    BOMB,
    BOMB_SLOT,
    BUTTON,
    CONNECTION,
    GROUP,
    INVENTORY,
    PROJECT,
    WORKER,
    WORKER_SLOT,
    CoreFixture,
    build_project,
    complete_vertical_flow,
    protected_asset,
    worker_program_v2,
)
from splashmx.canonical.core import (  # noqa: E402
    AddThing,
    ProjectRevisionId,
    ReferenceState,
    SemanticError,
    SemanticTransaction,
    ThingRecord,
    apply_transaction,
)
from splashmx.canonical.serialization import CanonicalProjectRevision  # noqa: E402
from splashmx.execution.hotswap import (  # noqa: E402
    PrivateStateMigration,
    ReplacementContract,
    ReplacementError,
    replace_behaviour,
)
from splashmx.runtime.lifecycle import (  # noqa: E402
    deserialize_world_save,
    serialize_world_save,
)
from splashmx.runtime.streaming import (  # noqa: E402
    ArtifactKind,
    StreamingError,
    descriptor_for,
    encode_project_artifact,
)
from splashmx.security.capabilities import CapabilityError  # noqa: E402
from splashmx.storage.local import SQLiteProjectStore, StorageError  # noqa: E402


class SMX031ProductionCoreGateTests(unittest.TestCase):
    def test_complete_create_reuse_behave_connect_play_stop_save_reload_vertical(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = complete_vertical_flow(tmp)
            fixture = result["fixture"]
            self.assertEqual(result["before_stop"], {"clicks": 1, "score": 1, "count": 1})
            self.assertEqual(result["reloaded"], fixture.project)
            self.assertEqual(result["stopped"].runtime.states[BUTTON].public_state["clicks"], 0)
            self.assertEqual(result["stopped"].runtime.states[WORKER].public_state["score"], 0)
            self.assertIn(CONNECTION, result["reloaded"].document.connections)
            self.assertIn(GROUP, result["reloaded"].document.instances)

    def test_group_reuse_identity_survives_physical_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CoreFixture.create()
            loaded = fixture.save_project(Path(tmp) / "project.sqlite3")
            self.assertEqual(loaded.document.definitions, fixture.project.document.definitions)
            self.assertEqual(loaded.document.instances, fixture.project.document.instances)
            self.assertEqual(loaded.document.relationships, fixture.project.document.relationships)

    def test_rule_and_advanced_behaviour_share_real_execution_runtime(self):
        fixture = CoreFixture.create()
        fixture.play()
        self.assertEqual(fixture.world.runtime.states[BUTTON].public_state["clicks"], 1)
        self.assertEqual(fixture.world.runtime.states[WORKER].public_state["score"], 1)
        self.assertEqual(
            fixture.world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"], 1
        )
        self.assertEqual(fixture.project.document.things[BUTTON].authored_state["clicks"], 0)
        self.assertEqual(fixture.project.document.things[WORKER].authored_state["score"], 0)

    def test_stable_port_connection_survives_play_and_stop(self):
        fixture = CoreFixture.create()
        original = copy.deepcopy(fixture.project.document.connections[CONNECTION])
        fixture.play()
        stopped = fixture.stop_to_authored()
        self.assertEqual(fixture.project.document.connections[CONNECTION], original)
        self.assertEqual(stopped.document.connections[CONNECTION], original)

    def test_fresh_process_restore_uses_only_persisted_semantic_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = complete_vertical_flow(tmp)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC)
            process = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION / "smx031_harness.py"),
                    "restore-probe",
                    str(result["project_db"]),
                    str(result["world_save"]),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            evidence = json.loads(process.stdout)
            self.assertEqual(evidence["project_revision_id"], "p3")
            self.assertEqual(evidence["worker_score"], 1)
            self.assertEqual(evidence["worker_private_count"], 1)
            self.assertEqual(evidence["inventory_target"], str(WORKER))
            self.assertEqual(evidence["connection_id"], str(CONNECTION))
            self.assertEqual(
                evidence["asset_revision_digest"], result["fixture"].project.assets[AUDIO].revision_digest
            )

    def test_worldsave_bytes_do_not_capture_host_or_capability_handles(self):
        fixture = CoreFixture.create()
        fixture.play()
        raw = serialize_world_save(fixture.world.snapshot("clean-save"))
        for forbidden in (
            b"nodepath", b"resourceuid", b"transport_peer_id", b"session_id",
            b"process_handle", b"capability_token", b"capability_grant",
        ):
            self.assertNotIn(forbidden, raw.lower())

    def test_durable_reference_to_unloaded_thing_survives_stream_out_and_in(self):
        fixture = CoreFixture.create()
        fixture.play()
        streaming = fixture.stream_worker()
        streaming.stream_out((WORKER,))
        self.assertEqual(streaming.reference_state(WORKER), ReferenceState.KNOWN_UNLOADED)
        self.assertEqual(
            streaming.world.document.things[INVENTORY].authored_state["durable_target"], str(WORKER)
        )
        outcome = streaming.stream_in((WORKER,))
        self.assertEqual(outcome.acquired_artifact_ids, ("worker-ir", "worker-basis"))
        self.assertEqual(streaming.reference_state(WORKER), ReferenceState.LOADED)
        self.assertEqual(streaming.world.runtime.states[WORKER].public_state["score"], 1)
        self.assertEqual(
            streaming.world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"], 1
        )

    def test_missing_exact_stream_dependency_is_typed_and_atomic(self):
        fixture = CoreFixture.create()
        fixture.play()
        streaming = fixture.stream_worker()
        streaming.stream_out((WORKER,))
        before = serialize_world_save(streaming.world.snapshot("before-missing"))
        streaming.acquirer.fetcher.payloads.pop("worker-ir")
        with self.assertRaises(StreamingError) as caught:
            streaming.stream_in((WORKER,))
        self.assertEqual(caught.exception.code, "streaming.dependency_unavailable")
        self.assertEqual(serialize_world_save(streaming.world.snapshot("before-missing")), before)
        self.assertEqual(streaming.reference_state(WORKER), ReferenceState.KNOWN_UNLOADED)

    def test_protected_asset_competing_complete_revision_cannot_field_mix_on_stream_in(self):
        fixture = CoreFixture.create()
        fixture.play()
        streaming = fixture.stream_worker()
        streaming.stream_out((WORKER,))
        before = serialize_world_save(streaming.world.snapshot("before-asset-conflict"))
        competitor = CanonicalProjectRevision(
            fixture.project.document,
            {AUDIO: protected_asset("competitor")},
        )
        payload = encode_project_artifact(competitor)
        streaming.acquirer.descriptors["worker-basis"] = descriptor_for(
            "worker-basis",
            ArtifactKind.CANONICAL_SUBGRAPH,
            payload,
            dependencies=("worker-ir",),
        )
        streaming.acquirer.fetcher.payloads["worker-basis"] = payload
        with self.assertRaises(StreamingError) as caught:
            streaming.stream_in((WORKER,))
        self.assertEqual(caught.exception.code, "streaming.protected_asset_conflict")
        self.assertEqual(
            serialize_world_save(streaming.world.snapshot("before-asset-conflict")), before
        )
        self.assertEqual(streaming.protected_assets[AUDIO], fixture.project.assets[AUDIO])

    def test_hot_replacement_keeps_thing_attachment_and_state_then_runs_new_revision(self):
        fixture = CoreFixture.create()
        fixture.play()
        fixture.hot_replace_worker()
        self.assertEqual(
            fixture.world.runtime.programs[(WORKER, WORKER_SLOT)].behaviour_revision,
            "worker:2",
        )
        fixture.world.dispatch(WORKER, "step")
        fixture.world.runtime.run_current_tick()
        self.assertEqual(fixture.world.runtime.states[WORKER].public_state["score"], 3)
        self.assertEqual(
            fixture.world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"], 3
        )
        self.assertEqual(
            fixture.project.document.things[WORKER].behaviours[WORKER_SLOT].behaviour_revision,
            "worker:1",
        )

    def test_failed_hot_replacement_does_not_partially_mutate_live_runtime(self):
        fixture = CoreFixture.create()
        fixture.play()
        before_program = fixture.world.runtime.programs[(WORKER, WORKER_SLOT)]
        before_state = copy.deepcopy(fixture.world.runtime.states[WORKER])
        contract = ReplacementContract(
            "wrong-source",
            "worker:0",
            "worker:2",
            private_state=PrivateStateMigration("preserve"),
        )
        with self.assertRaises(ReplacementError) as caught:
            replace_behaviour(
                fixture.world.runtime, WORKER, WORKER_SLOT, worker_program_v2(), contract
            )
        self.assertEqual(caught.exception.code, "replacement.source_revision_mismatch")
        self.assertEqual(fixture.world.runtime.programs[(WORKER, WORKER_SLOT)], before_program)
        self.assertEqual(fixture.world.runtime.states[WORKER], before_state)

    def test_instruction_budget_fault_rolls_back_integrated_runtime_mutation(self):
        fixture = CoreFixture.create()
        fixture.world.dispatch(BOMB, "explode")
        fixture.world.runtime.run_current_tick()
        self.assertFalse(fixture.world.runtime.states[BOMB].public_state["committed"])
        self.assertEqual(fixture.world.runtime.faults[-1].code, "execution.instruction_budget")
        self.assertIn(BOMB_SLOT, fixture.world.runtime.states[BOMB].private_by_attachment)

    def test_required_capability_denial_remains_fail_closed_without_ambient_authority(self):
        fixture = CoreFixture.create()
        with self.assertRaises(CapabilityError) as caught:
            fixture.deny_required_capability()
        self.assertEqual(caught.exception.code, "capability.required_denied")
        self.assertEqual(fixture.world.runtime.service_requests, [])

    def test_failed_canonical_transaction_keeps_previous_integrated_project_revision(self):
        fixture = CoreFixture.create()
        before = copy.deepcopy(fixture.project.document)
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(
                fixture.project.document,
                SemanticTransaction(
                    ProjectRevisionId("p4"),
                    (AddThing(ThingRecord(WORKER, "duplicate")),),
                ),
            )
        self.assertEqual(caught.exception.code, "canonical.duplicate_identity")
        self.assertEqual(fixture.project.document, before)

    def test_same_project_revision_cannot_be_rebound_to_different_protected_asset_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.sqlite3"
            original = build_project()
            competing = CanonicalProjectRevision(
                original.document,
                {AUDIO: protected_asset("competitor")},
            )
            with SQLiteProjectStore(path) as store:
                store.save(original)
                with self.assertRaises(StorageError) as caught:
                    store.save(competing)
                self.assertEqual(caught.exception.code, "storage.revision_conflict")
                self.assertEqual(store.load(PROJECT), original)

    def test_corrupt_worldsave_fails_before_fresh_runtime_publication(self):
        fixture = CoreFixture.create()
        fixture.play()
        raw = bytearray(serialize_world_save(fixture.world.snapshot("corrupt-me")))
        raw[-2] ^= 1
        with self.assertRaises(Exception) as caught:
            deserialize_world_save(bytes(raw))
        self.assertTrue(hasattr(caught.exception, "code"))

    def test_cache_eviction_after_exact_reload_is_non_semantic(self):
        fixture = CoreFixture.create()
        fixture.play()
        streaming = fixture.stream_worker()
        streaming.stream_out((WORKER,))
        streaming.stream_in((WORKER,))
        before = serialize_world_save(streaming.world.snapshot("cache-stable"))
        self.assertTrue(streaming.evict_artifact("worker-basis"))
        self.assertEqual(serialize_world_save(streaming.world.snapshot("cache-stable")), before)
        self.assertEqual(streaming.protected_assets[AUDIO], fixture.project.assets[AUDIO])

    def test_tombstoned_thing_cannot_be_resurrected_by_streaming_catalog(self):
        fixture = CoreFixture.create()
        streaming = fixture.stream_worker()
        streaming.world.tombstone(WORKER, reason="destroyed")
        with self.assertRaises(StreamingError) as caught:
            streaming.stream_in((WORKER,))
        self.assertEqual(caught.exception.code, "streaming.tombstoned")
        self.assertEqual(streaming.reference_state(WORKER), ReferenceState.TOMBSTONED)

    def test_protected_asset_roundtrip_preserves_every_indivisible_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project()
            with SQLiteProjectStore(Path(tmp) / "project.sqlite3") as store:
                store.save(project)
                restored = store.load(PROJECT).assets[AUDIO]
            original = project.assets[AUDIO]
            self.assertEqual(restored, original)
            self.assertEqual(restored.source_digest, original.source_digest)
            self.assertEqual(restored.source_identity, original.source_identity)
            self.assertEqual(restored.source_metadata, original.source_metadata)
            self.assertEqual(restored.media_semantics, original.media_semantics)
            self.assertEqual(restored.provenance, original.provenance)
            self.assertEqual(restored.licence_attribution, original.licence_attribution)
            self.assertEqual(restored.derivation_lineage, original.derivation_lineage)


if __name__ == "__main__":
    unittest.main()
