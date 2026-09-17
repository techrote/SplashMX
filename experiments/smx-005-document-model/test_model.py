from __future__ import annotations

from copy import deepcopy
import json
import unittest

from model import (
    Limits,
    TransactionConflict,
    UnsupportedFeature,
    ValidationError,
    add_record,
    apply_transaction,
    canonical_bytes,
    decode_document,
    decode_json_strict,
    encode_document,
    make_reference,
    migrate_to_current,
    new_document,
    record_lookup,
    resolve_reference,
    semantic_fingerprint,
    sha256_digest,
    validate_document,
)


class CanonicalDocumentModelTests(unittest.TestCase):
    def make_basic_document(self):
        doc = new_document(document_id="doc:world", revision_id="docrev:1")
        add_record(
            doc,
            {
                "kind": "thing",
                "id": "thing:town",
                "label": "Town",
                "state": {},
                "ports": [],
            },
            chunk="chunk:town",
        )
        add_record(
            doc,
            {
                "kind": "thing",
                "id": "thing:door",
                "label": "Door",
                "parent": make_reference("thing", "thing:town"),
                "state": {"open": False},
                "ports": ["port:open"],
            },
            chunk="chunk:town",
        )
        add_record(
            doc,
            {
                "kind": "thing",
                "id": "thing:key",
                "label": "Key",
                "state": {
                    "unlocks": make_reference("thing", "thing:door"),
                },
                "ports": [],
            },
            chunk="chunk:inventory",
        )
        return doc

    def test_dt001_rename_reparent_and_chunk_relocation_preserve_identity(self):
        doc = self.make_basic_document()
        before_ref = deepcopy(record_lookup(doc, "thing", "thing:key")["state"]["unlocks"])
        before_semantics = semantic_fingerprint(doc)

        changed = apply_transaction(
            doc,
            {
                "base_revision_id": "docrev:1",
                "new_revision_id": "docrev:2",
                "operations": [
                    {
                        "op": "set_thing_label",
                        "thing_id": "thing:door",
                        "expected_label": "Door",
                        "label": "North Door",
                    },
                    {
                        "op": "reparent_thing",
                        "thing_id": "thing:door",
                        "expected_parent": make_reference("thing", "thing:town"),
                        "parent": None,
                    },
                    {
                        "op": "relocate_record",
                        "kind": "thing",
                        "id": "thing:key",
                        "chunk": "chunk:player-inventory",
                    },
                ],
            },
        )

        self.assertEqual(record_lookup(changed, "thing", "thing:door")["id"], "thing:door")
        self.assertEqual(record_lookup(changed, "thing", "thing:key")["state"]["unlocks"], before_ref)
        self.assertEqual(before_ref["id"], "thing:door")
        # Physical chunk relocation alone is non-semantic; the label/parent edits are semantic,
        # so compare a relocation-only candidate for the fingerprint rule.
        relocation_only = apply_transaction(
            doc,
            {
                "base_revision_id": "docrev:1",
                "new_revision_id": "docrev:relocated",
                "operations": [
                    {
                        "op": "relocate_record",
                        "kind": "thing",
                        "id": "thing:key",
                        "chunk": "chunk:player-inventory",
                    }
                ],
            },
        )
        # Revision IDs describe lineage and therefore differ; normalize them solely for this
        # semantic-placement assertion.
        relocation_only["revision_id"] = doc["revision_id"]
        self.assertEqual(before_semantics, semantic_fingerprint(relocation_only))

    def test_dt002_known_unloaded_tombstoned_and_unknown_are_distinct(self):
        doc = self.make_basic_document()
        doc["records"] = [
            record for record in doc["records"] if not (record["kind"] == "thing" and record["id"] == "thing:door")
        ]
        ref = make_reference("thing", "thing:door")
        self.assertEqual(resolve_reference(doc, ref).state, "known_unloaded")

        tombstoned = deepcopy(doc)
        for entry in tombstoned["catalog"]:
            if entry["kind"] == "thing" and entry["id"] == "thing:door":
                entry["status"] = "tombstoned"
        self.assertEqual(resolve_reference(tombstoned, ref).state, "tombstoned")
        self.assertEqual(
            resolve_reference(doc, make_reference("thing", "thing:never-existed")).state,
            "unknown",
        )

    def test_dt003_definition_instance_overlay_round_trip(self):
        doc = new_document(document_id="doc:defs", revision_id="docrev:1")
        add_record(
            doc,
            {"kind": "definition", "id": "def:robot", "head_revision_id": "defrev:robot:7"},
        )
        add_record(
            doc,
            {
                "kind": "definition_revision",
                "id": "defrev:robot:7",
                "definition_id": "def:robot",
                "elements": {
                    "element:root": {"state": {"speed": 4}},
                    "element:arm": {"state": {"tint": "silver"}},
                },
            },
        )
        add_record(doc, {"kind": "thing", "id": "thing:robot-a", "label": "A", "state": {}, "ports": []})
        add_record(doc, {"kind": "thing", "id": "thing:robot-a-arm", "label": "Arm", "state": {}, "ports": []})
        add_record(
            doc,
            {
                "kind": "instance",
                "id": "thing:robot-a",
                "root_thing_id": "thing:robot-a",
                "definition_id": "def:robot",
                "base_revision_id": "defrev:robot:7",
                "provenance": {
                    "element:root": "thing:robot-a",
                    "element:arm": "thing:robot-a-arm",
                },
                "overlay": {"element:arm/state/tint": "rust"},
                "local_additions": [],
                "suppressions": [],
            },
        )

        encoded = encode_document(doc)
        decoded = decode_document(encoded)
        instance = record_lookup(decoded, "instance", "thing:robot-a")
        self.assertEqual(instance["base_revision_id"], "defrev:robot:7")
        self.assertEqual(instance["provenance"]["element:arm"], "thing:robot-a-arm")
        self.assertEqual(instance["overlay"]["element:arm/state/tint"], "rust")
        self.assertEqual(canonical_bytes(doc), canonical_bytes(decoded))

    def test_dt004_public_port_connection_survives_internal_restructure(self):
        doc = new_document(document_id="doc:component", revision_id="docrev:1")
        add_record(doc, {"kind": "thing", "id": "thing:panel", "label": "Panel", "state": {}, "ports": ["port:submit"]})
        add_record(
            doc,
            {
                "kind": "thing",
                "id": "thing:button",
                "label": "Button",
                "parent": make_reference("thing", "thing:panel"),
                "state": {},
                "ports": ["port:clicked"],
            },
        )
        add_record(doc, {"kind": "thing", "id": "thing:door", "label": "Door", "state": {}, "ports": ["port:open"]})
        add_record(
            doc,
            {
                "kind": "connection",
                "id": "connection:submit-open",
                "source": {"thing_id": "thing:panel", "port_id": "port:submit"},
                "target": {"thing_id": "thing:door", "port_id": "port:open"},
            },
        )
        before = deepcopy(record_lookup(doc, "connection", "connection:submit-open"))
        changed = apply_transaction(
            doc,
            {
                "base_revision_id": "docrev:1",
                "new_revision_id": "docrev:2",
                "operations": [
                    {
                        "op": "reparent_thing",
                        "thing_id": "thing:button",
                        "expected_parent": make_reference("thing", "thing:panel"),
                        "parent": None,
                    },
                    {
                        "op": "relocate_record",
                        "kind": "thing",
                        "id": "thing:button",
                        "chunk": "chunk:controls",
                    },
                ],
            },
        )
        self.assertEqual(record_lookup(changed, "connection", "connection:submit-open"), before)

    def test_dt005_behaviour_attachment_round_trip_excludes_live_state(self):
        doc = new_document(document_id="doc:behaviour", revision_id="docrev:1")
        add_record(doc, {"kind": "thing", "id": "thing:npc", "label": "NPC", "state": {}, "ports": []})
        add_record(doc, {"kind": "behavior", "id": "behavior:patrol", "head_revision_id": "behaviorrev:patrol:2"})
        add_record(
            doc,
            {
                "kind": "behavior_revision",
                "id": "behaviorrev:patrol:2",
                "behavior_id": "behavior:patrol",
                "private_state_schema": "patrol-state-v2",
                "ir": {"handlers": ["tick"]},
            },
        )
        add_record(
            doc,
            {
                "kind": "attachment",
                "id": "attachment:npc-patrol",
                "thing_id": "thing:npc",
                "behavior_revision_id": "behaviorrev:patrol:2",
                "config": {"radius": 12},
            },
        )
        decoded = decode_document(encode_document(doc))
        attachment = record_lookup(decoded, "attachment", "attachment:npc-patrol")
        self.assertEqual(attachment["behavior_revision_id"], "behaviorrev:patrol:2")
        for forbidden in ("private_state", "prng_state", "timers", "continuations"):
            self.assertNotIn(forbidden, attachment)

        bad = deepcopy(doc)
        record_lookup(bad, "attachment", "attachment:npc-patrol")["private_state"] = {"step": 3}
        with self.assertRaises(ValidationError):
            validate_document(bad)

    def test_dt006_deterministic_migration_preserves_ids_refs_and_extensions(self):
        v1 = new_document(document_id="doc:old", revision_id="docrev:old", schema_version=1)
        v1["extensions"] = {"vendor:future": {"opaque": [3, 1, 4]}}
        add_record(v1, {"kind": "thing", "id": "thing:door", "name": "Door", "state": {}, "ports": []})
        add_record(
            v1,
            {
                "kind": "thing",
                "id": "thing:key",
                "name": "Key",
                "state": {"target": make_reference("thing", "thing:door")},
                "ports": [],
            },
        )
        source_copy = deepcopy(v1)
        a = migrate_to_current(v1)
        b = migrate_to_current(v1)
        self.assertEqual(v1, source_copy)
        self.assertEqual(a["schema_version"], 2)
        self.assertEqual(record_lookup(a, "thing", "thing:door")["label"], "Door")
        self.assertEqual(record_lookup(a, "thing", "thing:key")["state"]["target"]["id"], "thing:door")
        self.assertEqual(a["extensions"], source_copy["extensions"])
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))

    def test_dt007_transaction_conflict_is_atomic(self):
        payload = b"image-v1"
        digest = sha256_digest(payload)
        doc = new_document(document_id="doc:tx", revision_id="docrev:1")
        add_record(doc, {"kind": "thing", "id": "thing:a", "label": "A", "state": {}, "ports": []})
        add_record(
            doc,
            {
                "kind": "asset",
                "id": "asset:portrait",
                "blob_digest": digest,
                "byte_length": len(payload),
                "media_type": "image/test",
            },
        )
        original = deepcopy(doc)
        with self.assertRaises(TransactionConflict):
            apply_transaction(
                doc,
                {
                    "base_revision_id": "docrev:1",
                    "new_revision_id": "docrev:2",
                    "operations": [
                        {
                            "op": "set_thing_label",
                            "thing_id": "thing:a",
                            "expected_label": "A",
                            "label": "Changed",
                        },
                        {
                            "op": "update_asset_blob",
                            "asset_id": "asset:portrait",
                            "expected_digest": "sha256:not-current",
                            "blob_digest": sha256_digest(b"image-v2"),
                            "byte_length": len(b"image-v2"),
                        },
                    ],
                },
            )
        self.assertEqual(doc, original)

    def test_dt008_required_feature_rejected_optional_extension_preserved(self):
        doc = self.make_basic_document()
        doc["required_features"] = ["feature:future-physics"]
        with self.assertRaises(UnsupportedFeature):
            validate_document(doc, supported_features=())

        doc["required_features"] = []
        doc["optional_features"] = ["feature:future-decoration"]
        doc["extensions"] = {"future-decoration": {"mode": "sparkle", "payload": [1, 2, 3]}}
        decoded = decode_document(encode_document(doc), supported_features=())
        self.assertEqual(decoded["extensions"], doc["extensions"])

    def test_dt009_external_dependency_unavailable_is_distinct(self):
        doc = self.make_basic_document()
        ref = make_reference("thing", "thing:remote", document_id="doc:other")
        self.assertEqual(resolve_reference(doc, ref).state, "dependency_unavailable")
        self.assertEqual(
            resolve_reference(doc, ref, available_documents={"doc:other"}).state,
            "known_unloaded",
        )
        self.assertEqual(
            resolve_reference(doc, make_reference("thing", "thing:remote")).state,
            "unknown",
        )

    def test_dt010_canonical_bytes_ignore_map_insertion_order(self):
        a = self.make_basic_document()
        b = json.loads(json.dumps(a))
        # Recreate root and nested dictionaries in deliberately different insertion order.
        b = {key: b[key] for key in reversed(list(b.keys()))}
        for record in b["records"]:
            keys = list(record.keys())
            replacement = {key: record[key] for key in reversed(keys)}
            record.clear()
            record.update(replacement)
        b["records"] = list(reversed(b["records"]))
        b["catalog"] = list(reversed(b["catalog"]))
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))

    def test_dt011_asset_id_survives_blob_replacement(self):
        v1 = b"asset version one"
        v2 = b"asset version two"
        d1 = sha256_digest(v1)
        d2 = sha256_digest(v2)
        doc = new_document(document_id="doc:asset", revision_id="docrev:1")
        add_record(
            doc,
            {
                "kind": "asset",
                "id": "asset:hero",
                "blob_digest": d1,
                "byte_length": len(v1),
                "media_type": "image/test",
            },
        )
        validate_document(doc, blobs={d1: v1})
        changed = apply_transaction(
            doc,
            {
                "base_revision_id": "docrev:1",
                "new_revision_id": "docrev:2",
                "operations": [
                    {
                        "op": "update_asset_blob",
                        "asset_id": "asset:hero",
                        "expected_digest": d1,
                        "blob_digest": d2,
                        "byte_length": len(v2),
                    }
                ],
            },
        )
        asset = record_lookup(changed, "asset", "asset:hero")
        self.assertEqual(asset["id"], "asset:hero")
        self.assertEqual(asset["blob_digest"], d2)
        validate_document(changed, blobs={d2: v2})

    def test_dt012_malformed_duplicate_oversized_digest_and_kind_fail(self):
        with self.assertRaises(ValidationError):
            decode_json_strict('{"schema_version":2,"schema_version":3}')

        doc = self.make_basic_document()
        doc["records"].append(deepcopy(doc["records"][0]))
        with self.assertRaises(ValidationError):
            validate_document(doc)

        oversized = new_document(document_id="doc:large", revision_id="docrev:1")
        payload = b"0123456789"
        digest = sha256_digest(payload)
        add_record(
            oversized,
            {
                "kind": "asset",
                "id": "asset:large",
                "blob_digest": digest,
                "byte_length": len(payload),
                "media_type": "application/octet-stream",
            },
        )
        with self.assertRaises(ValidationError):
            validate_document(oversized, limits=Limits(max_asset_bytes=5))

        mismatch = deepcopy(oversized)
        with self.assertRaises(ValidationError):
            validate_document(mismatch, blobs={digest: b"wrong bytes"})

        bad_kind = new_document(document_id="doc:bad-kind", revision_id="docrev:1")
        add_record(bad_kind, {"kind": "mystery", "id": "mystery:1"})
        with self.assertRaises(ValidationError):
            validate_document(bad_kind)


if __name__ == "__main__":
    unittest.main()
