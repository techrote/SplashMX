from __future__ import annotations

import unittest

from splashmx.canonical.core import (
    AssetId,
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ReferenceState,
    RelationId,
    RelationshipKind,
    RelationshipRecord,
    ThingId,
    ThingRecord,
)
from splashmx.canonical.serialization import CanonicalProjectRevision, ProtectedAssetRevision
from splashmx.execution.ir import IRHandler, IRInstruction, IRProgram, literal
from splashmx.runtime.lifecycle import WorldRuntime, serialize_world_save
from splashmx.runtime.streaming import (
    AcquisitionLimits,
    ArtifactKind,
    ExactAcquirer,
    ImmutableArtifactCache,
    MappingArtifactSource,
    StreamingError,
    StreamingRuntime,
    ThingStreamSpec,
    decode_ir_artifact,
    descriptor_for,
    encode_ir_artifact,
    encode_project_artifact,
)

SWORD = ThingId("sword")
REGION = ThingId("town")
INVENTORY = ThingId("inventory")
SLOT = BehaviourAttachmentId("logic")


def program(revision: str = "sword-behaviour:1") -> IRProgram:
    return IRProgram(
        revision,
        (
            IRHandler(
                "step",
                "step",
                (IRInstruction("add_private", {"key": "count", "value": literal(1)}),),
            ),
            IRHandler(
                "later",
                "later",
                (IRInstruction("add_private", {"key": "count", "value": literal(10)}),),
            ),
            IRHandler(
                "start",
                "start",
                (
                    IRInstruction(
                        "schedule",
                        {
                            "timer_id": "pending",
                            "delay": 5,
                            "handler": "later",
                            "payload": literal({"from": "timer"}),
                        },
                    ),
                ),
            ),
        ),
        private_defaults={"count": 1},
    )


def asset(label: str = "original") -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId("audio"),
        source_digest="sha256:" + ("1" if label == "original" else "2") * 64,
        source_identity={"name": f"{label}.wav"},
        source_metadata={"channels": 2, "sample_rate": 48000},
        media_semantics={"kind": "audio", "loop": False},
        provenance={"origin": label},
        licence_attribution={"licence": "CC0"},
        derivation_lineage=({"operation": "source"},),
    )


def document(*, revision: str = "p1", sword_label: str = "Sword") -> CanonicalDocument:
    doc = CanonicalDocument(ProjectId("project"), ProjectRevisionId(revision))
    doc.things[REGION] = ThingRecord(REGION, "Town")
    doc.things[INVENTORY] = ThingRecord(
        INVENTORY, "Inventory", authored_state={"durable_target": str(SWORD)}
    )
    doc.things[SWORD] = ThingRecord(
        SWORD,
        sword_label,
        authored_state={"damage": 7},
        behaviours={SLOT: BehaviourAttachmentRecord(SLOT, "sword-behaviour:1")},
    )
    relation = RelationshipRecord(
        RelationId("town-contains-sword"),
        RelationshipKind.CONTAINS,
        REGION,
        SWORD,
    )
    doc.relationships[relation.relation_id] = relation
    return doc


def make_bundle(
    *,
    project_document: CanonicalDocument | None = None,
    ir_program: IRProgram | None = None,
    project_asset: ProtectedAssetRevision | None = None,
    protected_asset: ProtectedAssetRevision | None = None,
    source_override: dict[str, bytes] | None = None,
    required_features: tuple[str, ...] = (),
    cache: ImmutableArtifactCache | None = None,
    limits: AcquisitionLimits | None = None,
):
    doc = project_document or document()
    p = ir_program or program()
    basis_project = CanonicalProjectRevision(
        doc,
        {} if project_asset is None else {project_asset.asset_id: project_asset},
    )
    basis = encode_project_artifact(basis_project)
    ir = encode_ir_artifact(p)
    descriptors = {
        "ir": descriptor_for("ir", ArtifactKind.BEHAVIOUR_IR, ir),
        "basis": descriptor_for(
            "basis",
            ArtifactKind.CANONICAL_SUBGRAPH,
            basis,
            dependencies=("ir",),
            required_features=required_features,
        ),
    }
    payloads = {"basis": basis, "ir": ir}
    if source_override is not None:
        payloads = source_override
    source = MappingArtifactSource(payloads)
    world = WorldRuntime.create(doc, {"sword-behaviour:1": program()})
    runtime = StreamingRuntime(
        world,
        protected_assets=(
            {} if protected_asset is None else {protected_asset.asset_id: protected_asset}
        ),
        catalog={SWORD: ThingStreamSpec(SWORD, ("basis",))},
        descriptors=descriptors,
        fetcher=source,
        cache=cache,
        limits=limits,
    )
    return runtime, source, descriptors, payloads


def saved_bytes(runtime: StreamingRuntime) -> bytes:
    return serialize_world_save(runtime.world.snapshot("probe"))


class SMX030StreamingTests(unittest.TestCase):
    def test_inventory_reference_survives_selective_unload_reload_without_containment_load(self):
        runtime, _, _, _ = make_bundle()
        runtime.world.dispatch(SWORD, "step")
        runtime.world.runtime.run_current_tick()
        self.assertEqual(runtime.world.runtime.states[SWORD].private_by_attachment[SLOT]["count"], 2)
        runtime.stream_out((SWORD,))
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)
        self.assertEqual(runtime.reference_state(REGION), ReferenceState.LOADED)
        self.assertEqual(runtime.reference_state(INVENTORY), ReferenceState.LOADED)
        self.assertEqual(runtime.world.document.things[INVENTORY].authored_state["durable_target"], str(SWORD))
        runtime.stream_in((SWORD,))
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.LOADED)
        self.assertEqual(runtime.world.runtime.states[SWORD].private_by_attachment[SLOT]["count"], 2)

    def test_stream_in_acquires_dependency_before_basis_in_deterministic_order(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        outcome = runtime.stream_in((SWORD,))
        self.assertEqual(outcome.acquired_artifact_ids, ("ir", "basis"))

    def test_missing_exact_dependency_fails_without_partial_activation(self):
        runtime, source, descriptors, _ = make_bundle()
        runtime.stream_out((SWORD,))
        source.payloads.pop("ir")
        before = saved_bytes(runtime)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.dependency_unavailable")
        self.assertEqual(saved_bytes(runtime), before)
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)
        self.assertFalse(runtime.cache.contains(descriptors["basis"]))

    def test_corrupt_exact_dependency_fails_digest_before_decode(self):
        runtime, source, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        source.payloads["ir"] += b"x"
        before = saved_bytes(runtime)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.integrity_failure")
        self.assertEqual(saved_bytes(runtime), before)

    def test_wrong_exact_project_revision_is_incompatible_and_atomic(self):
        wrong = document(revision="p2")
        runtime, source, descriptors, _ = make_bundle()
        runtime.stream_out((SWORD,))
        basis = encode_project_artifact(CanonicalProjectRevision(wrong, {}))
        descriptors["basis"] = descriptor_for("basis", ArtifactKind.CANONICAL_SUBGRAPH, basis, dependencies=("ir",))
        runtime.acquirer.descriptors["basis"] = descriptors["basis"]
        source.payloads["basis"] = basis
        before = saved_bytes(runtime)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.incompatible_dependency")
        self.assertEqual(saved_bytes(runtime), before)

    def test_same_revision_but_different_thing_basis_is_rejected(self):
        mismatched = document(sword_label="Counterfeit Sword")
        runtime, source, descriptors, _ = make_bundle()
        runtime.stream_out((SWORD,))
        basis = encode_project_artifact(CanonicalProjectRevision(mismatched, {}))
        descriptors["basis"] = descriptor_for("basis", ArtifactKind.CANONICAL_SUBGRAPH, basis, dependencies=("ir",))
        runtime.acquirer.descriptors["basis"] = descriptors["basis"]
        source.payloads["basis"] = basis
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.incompatible_dependency")
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)

    def test_wrong_behaviour_revision_cannot_satisfy_exact_attachment(self):
        runtime, source, descriptors, _ = make_bundle()
        runtime.stream_out((SWORD,))
        ir = encode_ir_artifact(program("sword-behaviour:2"))
        descriptors["ir"] = descriptor_for("ir", ArtifactKind.BEHAVIOUR_IR, ir)
        runtime.acquirer.descriptors["ir"] = descriptors["ir"]
        source.payloads["ir"] = ir
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.exact_behaviour_missing")
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)

    def test_ir_roundtrip_preserves_exact_validated_program(self):
        p = program()
        self.assertEqual(decode_ir_artifact(encode_ir_artifact(p)), p)

    def test_unsupported_required_feature_fails_before_fetch(self):
        runtime, _, _, _ = make_bundle(required_features=("future-stream-mode",))
        runtime.stream_out((SWORD,))
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.incompatible_dependency")

    def test_descriptor_missing_from_graph_is_typed(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        del runtime.acquirer.descriptors["ir"]
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.descriptor_missing")

    def test_dependency_depth_is_bounded(self):
        payload = b"x"
        descriptors = {
            "a": descriptor_for("a", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("b",)),
            "b": descriptor_for("b", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("c",)),
            "c": descriptor_for("c", ArtifactKind.OPAQUE_EXACT, payload),
        }
        acquirer = ExactAcquirer(
            descriptors,
            MappingArtifactSource({"a": payload, "b": payload, "c": payload}),
            ImmutableArtifactCache(),
            limits=AcquisitionLimits(max_descriptors=10, max_depth=1, max_total_bytes=100, max_artifact_bytes=10),
        )
        with self.assertRaises(StreamingError) as caught:
            acquirer.acquire(("a",))
        self.assertEqual(caught.exception.code, "streaming.dependency_depth_limit")

    def test_dependency_count_is_bounded(self):
        payload = b"x"
        descriptors = {
            "a": descriptor_for("a", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("b", "c")),
            "b": descriptor_for("b", ArtifactKind.OPAQUE_EXACT, payload),
            "c": descriptor_for("c", ArtifactKind.OPAQUE_EXACT, payload),
        }
        acquirer = ExactAcquirer(
            descriptors,
            MappingArtifactSource({key: payload for key in descriptors}),
            ImmutableArtifactCache(),
            limits=AcquisitionLimits(max_descriptors=2, max_depth=4, max_total_bytes=100, max_artifact_bytes=10),
        )
        with self.assertRaises(StreamingError) as caught:
            acquirer.acquire(("a",))
        self.assertEqual(caught.exception.code, "streaming.dependency_count_limit")

    def test_total_declared_bytes_are_bounded_before_fetch(self):
        payload = b"12345"
        descriptors = {
            "a": descriptor_for("a", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("b",)),
            "b": descriptor_for("b", ArtifactKind.OPAQUE_EXACT, payload),
        }
        acquirer = ExactAcquirer(
            descriptors,
            MappingArtifactSource({"a": payload, "b": payload}),
            ImmutableArtifactCache(),
            limits=AcquisitionLimits(max_descriptors=5, max_depth=5, max_total_bytes=9, max_artifact_bytes=10),
        )
        with self.assertRaises(StreamingError) as caught:
            acquirer.acquire(("a",))
        self.assertEqual(caught.exception.code, "streaming.total_size_limit")

    def test_exact_declarative_dependency_cycle_is_bounded_and_allowed(self):
        payload = b"x"
        descriptors = {
            "a": descriptor_for("a", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("b",)),
            "b": descriptor_for("b", ArtifactKind.OPAQUE_EXACT, payload, dependencies=("a",)),
        }
        result = ExactAcquirer(
            descriptors,
            MappingArtifactSource({"a": payload, "b": payload}),
            ImmutableArtifactCache(),
        ).acquire(("a",))
        self.assertEqual(set(result.ordered_artifact_ids), {"a", "b"})

    def test_cache_hit_can_complete_when_source_goes_offline(self):
        runtime, source, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        first = runtime.stream_in((SWORD,))
        self.assertEqual(first.cache_hits, ())
        runtime.stream_out((SWORD,))
        source.payloads.clear()
        second = runtime.stream_in((SWORD,))
        self.assertEqual(set(second.cache_hits), {"basis", "ir"})
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.LOADED)

    def test_cache_eviction_does_not_change_worldsave_or_reference_meaning(self):
        runtime, _, descriptors, _ = make_bundle()
        runtime.stream_out((SWORD,))
        runtime.stream_in((SWORD,))
        runtime.stream_out((SWORD,))
        before = saved_bytes(runtime)
        self.assertTrue(runtime.evict_artifact("basis"))
        self.assertTrue(runtime.evict_artifact("ir"))
        self.assertEqual(saved_bytes(runtime), before)
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)
        self.assertFalse(runtime.cache.contains(descriptors["basis"]))

    def test_evicted_cache_refetches_same_exact_bytes(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        runtime.stream_in((SWORD,))
        runtime.stream_out((SWORD,))
        runtime.evict_artifact("basis")
        runtime.evict_artifact("ir")
        outcome = runtime.stream_in((SWORD,))
        self.assertEqual(outcome.cache_hits, ())
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.LOADED)

    def test_full_cache_is_advisory_and_does_not_change_semantics(self):
        tiny = ImmutableArtifactCache(max_entries=1, max_bytes=1)
        runtime, _, _, _ = make_bundle(cache=tiny)
        runtime.stream_out((SWORD,))
        runtime.stream_in((SWORD,))
        self.assertEqual(tiny.entry_count, 0)
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.LOADED)

    def test_cancelled_acquisition_does_not_publish(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        before = saved_bytes(runtime)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,), cancel_check=lambda: True)
        self.assertEqual(caught.exception.code, "streaming.cancelled")
        self.assertEqual(saved_bytes(runtime), before)

    def test_cancel_after_fetch_still_does_not_publish(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        before = saved_bytes(runtime)
        calls = {"n": 0}
        def cancel():
            calls["n"] += 1
            return calls["n"] >= 4
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,), cancel_check=cancel)
        self.assertEqual(caught.exception.code, "streaming.cancelled")
        self.assertEqual(saved_bytes(runtime), before)

    def test_tombstoned_thing_cannot_be_resurrected_by_acquisition(self):
        runtime, _, _, _ = make_bundle()
        runtime.world.tombstone(SWORD, reason="destroyed")
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.tombstoned")
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.TOMBSTONED)

    def test_tombstone_discards_retained_pending_work_before_any_later_acquisition(self):
        runtime, _, _, _ = make_bundle()
        runtime.world.dispatch(SWORD, "start")
        runtime.world.runtime.run_current_tick()
        runtime.stream_out((SWORD,))
        self.assertEqual(len(runtime.world._retained[SWORD].timers), 1)
        runtime.world.tombstone(SWORD, reason="destroyed")
        snap = runtime.world.snapshot("after-destroy")
        row = next(row for row in snap.things if row.thing_id == SWORD)
        self.assertEqual(row.timers, ())
        self.assertEqual(row.queued_work, ())
        with self.assertRaises(StreamingError):
            runtime.stream_in((SWORD,))

    def test_unknown_thing_is_not_conflated_with_known_unloaded(self):
        runtime, _, _, _ = make_bundle()
        runtime.stream_out((SWORD,))
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)
        self.assertEqual(runtime.reference_state(ThingId("missing")), ReferenceState.UNKNOWN)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((ThingId("missing"),))
        self.assertEqual(caught.exception.code, "streaming.unknown_thing")

    def test_stream_out_requires_exact_reload_catalog(self):
        runtime, _, _, _ = make_bundle()
        runtime.catalog.clear()
        before = saved_bytes(runtime)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_out((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.catalog_missing")
        self.assertEqual(saved_bytes(runtime), before)

    def test_loaded_stream_in_is_noop_and_does_not_fetch(self):
        runtime, source, _, _ = make_bundle()
        source.payloads.clear()
        outcome = runtime.stream_in((SWORD,))
        self.assertEqual(outcome.thing_ids, ())
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.LOADED)

    def test_protected_asset_competing_complete_revision_is_not_field_mixed(self):
        original = asset("original")
        competing = asset("competing")
        runtime, _, _, _ = make_bundle(project_asset=competing, protected_asset=original)
        runtime.stream_out((SWORD,))
        before = dict(runtime.protected_assets)
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.protected_asset_conflict")
        self.assertEqual(runtime.protected_assets, before)
        self.assertEqual(runtime.protected_assets[AssetId("audio")], original)

    def test_complete_protected_asset_revision_can_be_acquired_atomically(self):
        original = asset("original")
        runtime, _, _, _ = make_bundle(project_asset=original)
        runtime.stream_out((SWORD,))
        runtime.stream_in((SWORD,))
        self.assertEqual(runtime.protected_assets[AssetId("audio")], original)

    def test_opaque_dependency_is_integrity_checked_but_never_executed(self):
        runtime, source, descriptors, payloads = make_bundle()
        opaque = b"trusted-bytes-not-code"
        descriptors["opaque"] = descriptor_for("opaque", ArtifactKind.OPAQUE_EXACT, opaque)
        descriptors["basis"] = descriptor_for(
            "basis", ArtifactKind.CANONICAL_SUBGRAPH, payloads["basis"], dependencies=("ir", "opaque")
        )
        runtime.acquirer.descriptors = descriptors
        source.payloads["opaque"] = opaque
        runtime.stream_out((SWORD,))
        outcome = runtime.stream_in((SWORD,))
        self.assertIn("opaque", outcome.acquired_artifact_ids)

    def test_corrupt_opaque_dependency_blocks_activation(self):
        runtime, source, descriptors, payloads = make_bundle()
        opaque = b"expected"
        descriptors["opaque"] = descriptor_for("opaque", ArtifactKind.OPAQUE_EXACT, opaque)
        descriptors["basis"] = descriptor_for(
            "basis", ArtifactKind.CANONICAL_SUBGRAPH, payloads["basis"], dependencies=("ir", "opaque")
        )
        runtime.acquirer.descriptors = descriptors
        source.payloads["opaque"] = b"tampered"
        runtime.stream_out((SWORD,))
        with self.assertRaises(StreamingError) as caught:
            runtime.stream_in((SWORD,))
        self.assertEqual(caught.exception.code, "streaming.integrity_failure")
        self.assertEqual(runtime.reference_state(SWORD), ReferenceState.KNOWN_UNLOADED)


if __name__ == "__main__":
    unittest.main()
