from __future__ import annotations

import copy
import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    AddConnection,
    AddThing,
    AssetId,
    ConnectionEndpoint,
    ConnectionId,
    ConnectionRecord,
    DefinitionExposure,
    DefinitionId,
    ElementId,
    PortDirection,
    PortId,
    PortKind,
    PortRecord,
    ProjectId,
    ProjectRevisionId,
    PromoteGroup,
    RelationId,
    SemanticTransaction,
    SetContainment,
    ThingId,
    ThingRecord,
    apply_transaction,
    empty_document,
)
from splashmx.canonical.serialization import (  # noqa: E402
    CANONICAL_PROFILE,
    CURRENT_SCHEMA_VERSION,
    CanonicalProjectRevision,
    DecodeLimits,
    MigrationRegistry,
    ProtectedAssetRevision,
    SerializationError,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
    prepare_migration,
    serialize_project,
)


def pid(value: str) -> ProjectId:
    return ProjectId(value)


def rev(value: str) -> ProjectRevisionId:
    return ProjectRevisionId(value)


def tid(value: str) -> ThingId:
    return ThingId(value)


def tx(number: int, *ops) -> SemanticTransaction:
    return SemanticTransaction(rev(f"r{number}"), tuple(ops))


def asset(asset_id: str, marker: str) -> ProtectedAssetRevision:
    return ProtectedAssetRevision.create(
        AssetId(asset_id),
        source_digest="sha256:" + marker * 64,
        source_identity={"kind": "author-import", "logical_name": f"{asset_id}.wav"},
        source_metadata={"bytes": 4096, "original_extension": "wav"},
        media_semantics={
            "kind": "audio",
            "channels": 2,
            "sample_rate": 48000,
            "loop": {"enabled": True, "start_frame": 64, "end_frame": 2048},
        },
        provenance={"creator": "fixture-author", "source": "original recording"},
        licence_attribution={"licence": "CC0-1.0", "attribution": ""},
        derivation_lineage=({"operation": "trim", "tool": "fixture", "parent_digest": "sha256:" + "f" * 64},),
    )


class SMX024CanonicalSerializationTests(unittest.TestCase):
    def complex_project(self) -> CanonicalProjectRevision:
        public = PortRecord(PortId("signal"), "signal", PortKind.EVENT, PortDirection.OUT)
        internal = PortRecord(PortId("internal-signal"), "internal-signal", PortKind.EVENT, PortDirection.OUT)
        receive = PortRecord(PortId("receive"), "receive", PortKind.COMMAND, PortDirection.IN)
        doc = apply_transaction(
            empty_document(pid("project-serialization"), rev("r0")),
            tx(
                1,
                AddThing(ThingRecord(tid("group"), "Group", authored_state={"gain": 1, "minus_zero": -0.0}, ports={public.port_id: public})),
                AddThing(ThingRecord(tid("child"), "Child", authored_state={"labels": ["a", "b"]}, ports={internal.port_id: internal})),
                AddThing(ThingRecord(tid("sink"), "Sink", ports={receive.port_id: receive})),
                SetContainment(tid("child"), tid("group"), RelationId("rel-child")),
                AddConnection(
                    ConnectionRecord(
                        ConnectionId("conn-public"),
                        ConnectionEndpoint(tid("group"), PortId("signal")),
                        ConnectionEndpoint(tid("sink"), PortId("receive")),
                    )
                ),
            ),
        )
        exposure = DefinitionExposure(PortId("signal"), ElementId("element-child"), PortId("internal-signal"))
        doc = apply_transaction(
            doc,
            tx(
                2,
                PromoteGroup(
                    tid("group"),
                    DefinitionId("def-group"),
                    {tid("group"): ElementId("element-root"), tid("child"): ElementId("element-child")},
                    {PortId("signal"): exposure},
                ),
            ),
        )
        doc.known_unloaded_things.add(tid("remote-known"))
        return CanonicalProjectRevision(doc, {AssetId("music"): asset("music", "a")})

    @staticmethod
    def with_manifest(serialized: SerializedProjectRevision, **changes) -> SerializedProjectRevision:
        manifest = decode_canonical_cbor(serialized.root_manifest)
        manifest.update(changes)
        return SerializedProjectRevision(encode_canonical_cbor(manifest), dict(serialized.shards))

    def test_round_trip_preserves_semantic_equality_stable_ids_and_protected_media(self):
        before = self.complex_project()
        encoded = serialize_project(before, target_shard_bytes=1024)
        after = deserialize_project(encoded)
        self.assertEqual(after, before)
        self.assertEqual(after.document.project_id, pid("project-serialization"))
        self.assertEqual(after.document.project_revision_id, rev("r2"))
        self.assertEqual(after.document.instances[tid("group")].definition_id, DefinitionId("def-group"))
        protected = after.assets[AssetId("music")]
        self.assertEqual(protected.source_digest, "sha256:" + "a" * 64)
        self.assertEqual(protected.media_semantics["sample_rate"], 48000)
        self.assertEqual(protected.provenance["creator"], "fixture-author")
        self.assertEqual(protected.licence_attribution["licence"], "CC0-1.0")
        self.assertEqual(protected.derivation_lineage[0]["operation"], "trim")

    def test_logically_equal_mapping_insertion_orders_produce_identical_bytes(self):
        first = self.complex_project()
        second = copy.deepcopy(first)
        second.document.things = dict(reversed(list(second.document.things.items())))
        second.document.connections = dict(reversed(list(second.document.connections.items())))
        second.document.definitions = dict(reversed(list(second.document.definitions.items())))
        second = CanonicalProjectRevision(second.document, dict(reversed(list(second.assets.items()))))
        a = serialize_project(first, target_shard_bytes=1024)
        b = serialize_project(second, target_shard_bytes=1024)
        self.assertEqual(a.root_manifest, b.root_manifest)
        self.assertEqual(a.shards, b.shards)

    def test_protected_asset_partial_field_mix_rejected_by_revision_digest(self):
        original = asset("music", "a")
        competing = asset("music", "b")
        with self.assertRaises(SerializationError) as caught:
            replace(original, source_digest=competing.source_digest)
        self.assertEqual(caught.exception.code, "serialization.asset_revision_mismatch")

    def test_whole_asset_replacement_is_a_complete_distinct_revision(self):
        original = asset("music", "a")
        competing = asset("music", "b")
        self.assertNotEqual(original.revision_digest, competing.revision_digest)
        project = self.complex_project()
        replaced = CanonicalProjectRevision(project.document, {AssetId("music"): competing})
        round_tripped = deserialize_project(serialize_project(replaced, target_shard_bytes=1024))
        self.assertEqual(round_tripped.assets[AssetId("music")], competing)
        self.assertNotEqual(round_tripped.assets[AssetId("music")], original)

    def test_derivative_digest_cannot_silently_replace_canonical_source_revision(self):
        original = asset("music", "a")
        derivative_digest = "sha256:" + "d" * 64
        with self.assertRaises(SerializationError) as caught:
            replace(original, source_digest=derivative_digest)
        self.assertEqual(caught.exception.code, "serialization.asset_revision_mismatch")

    def test_corrupt_shard_fails_before_materialization(self):
        project = self.complex_project()
        encoded = serialize_project(project, target_shard_bytes=1024)
        shards = dict(encoded.shards)
        key = next(iter(shards))
        raw = bytearray(shards[key])
        raw[-1] ^= 1
        corrupted = SerializedProjectRevision(encoded.root_manifest, {**shards, key: bytes(raw)})
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(corrupted)
        self.assertEqual(caught.exception.code, "serialization.integrity_failure")

    def test_missing_or_extra_shard_fails_closed(self):
        encoded = serialize_project(self.complex_project(), target_shard_bytes=1024)
        shards = dict(encoded.shards)
        shards.pop(next(iter(shards)))
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(SerializedProjectRevision(encoded.root_manifest, shards))
        self.assertEqual(caught.exception.code, "serialization.integrity_failure")

    def test_newer_schema_version_is_typed_failure_not_silent_reinterpretation(self):
        encoded = serialize_project(self.complex_project(), target_shard_bytes=1024)
        newer = self.with_manifest(encoded, schema_version=CURRENT_SCHEMA_VERSION + 1)
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(newer)
        self.assertEqual(caught.exception.code, "serialization.unsupported_version")

    def test_unknown_required_feature_is_typed_failure(self):
        encoded = serialize_project(self.complex_project(), target_shard_bytes=1024)
        incompatible = self.with_manifest(encoded, required_features=["protected-assets-v1", "future-required-semantics"])
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(incompatible)
        self.assertEqual(caught.exception.code, "serialization.unsupported_feature")

    def test_wrong_canonical_profile_is_typed_failure(self):
        encoded = serialize_project(self.complex_project(), target_shard_bytes=1024)
        incompatible = self.with_manifest(encoded, canonical_profile=CANONICAL_PROFILE + "-other")
        with self.assertRaises(SerializationError) as caught:
            deserialize_project(incompatible)
        self.assertEqual(caught.exception.code, "serialization.incompatible_profile")

    def test_v0_envelope_migrates_to_current_without_rewriting_semantics(self):
        project = self.complex_project()
        encoded = serialize_project(project, target_shard_bytes=1024)
        legacy = self.with_manifest(encoded, schema_version=0)
        migrated = prepare_migration(legacy)
        self.assertEqual(migrated, project)

    def test_failed_migration_does_not_publish_or_mutate_prior_revision(self):
        project = self.complex_project()
        snapshot = copy.deepcopy(project)
        encoded = self.with_manifest(serialize_project(project, target_shard_bytes=1024), schema_version=0)
        registry = MigrationRegistry()

        def fail(_records):
            raise RuntimeError("injected migration failure")

        registry.register(0, 1, fail)
        active = project
        with self.assertRaises(SerializationError) as caught:
            candidate = prepare_migration(encoded, migrations=registry)
            active = candidate
        self.assertEqual(caught.exception.code, "serialization.migration_failed")
        self.assertEqual(active, snapshot)

    def test_missing_migration_path_fails_typed_and_non_destructively(self):
        project = self.complex_project()
        encoded = self.with_manifest(serialize_project(project, target_shard_bytes=1024), schema_version=0)
        with self.assertRaises(SerializationError) as caught:
            prepare_migration(encoded, migrations=MigrationRegistry())
        self.assertEqual(caught.exception.code, "serialization.unsupported_version")
        self.assertEqual(project, self.complex_project())

    def test_migration_injecting_transient_identity_is_rejected_before_publish(self):
        encoded = self.with_manifest(serialize_project(self.complex_project(), target_shard_bytes=1024), schema_version=0)
        registry = MigrationRegistry()

        def inject(records):
            records[0]["value"]["authored_state"] = {"nested": {"transport_peer_id": 7}}
            return records

        registry.register(0, 1, inject)
        with self.assertRaises(SerializationError) as caught:
            prepare_migration(encoded, migrations=registry)
        self.assertEqual(caught.exception.code, "serialization.forbidden_transient_identity")

    def test_cbor_map_insertion_order_is_canonical(self):
        self.assertEqual(
            encode_canonical_cbor({"longer": 1, "a": 2, "b": [3]}),
            encode_canonical_cbor({"b": [3], "a": 2, "longer": 1}),
        )

    def test_noncanonical_integer_encoding_is_rejected(self):
        with self.assertRaises(SerializationError) as caught:
            decode_canonical_cbor(b"\x18\x00")
        self.assertEqual(caught.exception.code, "serialization.noncanonical_cbor")

    def test_duplicate_cbor_map_key_is_rejected_before_overwrite(self):
        with self.assertRaises(SerializationError) as caught:
            decode_canonical_cbor(b"\xa2\x61a\x01\x61a\x02")
        self.assertEqual(caught.exception.code, "serialization.duplicate_map_key")

    def test_indefinite_length_cbor_is_outside_profile(self):
        with self.assertRaises(SerializationError) as caught:
            decode_canonical_cbor(b"\x9f\x01\xff")
        self.assertEqual(caught.exception.code, "serialization.indefinite_cbor")

    def test_unregistered_cbor_tag_is_rejected(self):
        with self.assertRaises(SerializationError) as caught:
            decode_canonical_cbor(b"\xc0\x61a")
        self.assertEqual(caught.exception.code, "serialization.unregistered_tag")

    def test_non_finite_floats_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(SerializationError) as caught:
                    encode_canonical_cbor({"value": value})
                self.assertEqual(caught.exception.code, "serialization.non_finite_float")

    def test_negative_zero_remains_distinguishable(self):
        positive = encode_canonical_cbor({"value": 0.0})
        negative = encode_canonical_cbor({"value": -0.0})
        self.assertNotEqual(positive, negative)
        decoded = decode_canonical_cbor(negative)["value"]
        self.assertEqual(math.copysign(1.0, decoded), -1.0)

    def test_parser_byte_limit_is_enforced_before_decode(self):
        payload = encode_canonical_cbor({"payload": "x" * 128})
        with self.assertRaises(SerializationError) as caught:
            decode_canonical_cbor(payload, limits=DecodeLimits(max_bytes=8))
        self.assertEqual(caught.exception.code, "serialization.limit_exceeded")

    def test_forbidden_transient_durable_field_is_rejected_by_encoder(self):
        with self.assertRaises(SerializationError) as caught:
            encode_canonical_cbor({"safe": {"session_id": "transient"}})
        self.assertEqual(caught.exception.code, "serialization.forbidden_transient_identity")


if __name__ == "__main__":
    unittest.main()
