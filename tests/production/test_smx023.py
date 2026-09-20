from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    AddBehaviourAttachment, AddConnection, AddDefinition, AddRelationship, AddThing,
    AssetId, BehaviourAttachmentId, BehaviourAttachmentRecord, ConnectionEndpoint,
    ConnectionId, ConnectionRecord, DefinitionElementRecord, DefinitionExposure,
    DefinitionId, DefinitionRecord, ElementId, InstantiateDefinition, PortDirection,
    PortId, PortKind, PortRecord, ProjectId, ProjectRevisionId, PromoteGroup,
    ReferenceState, RelationId, RelationshipKind, RelationshipRecord, RemovePort,
    RenameThing, ReplaceDefinition, SemanticError, SemanticTransaction,
    SetAuthoredState, SetContainment, SetInstanceStateOverride, ThingId, ThingRecord,
    TombstoneConnection, TombstoneThing, TransientContext, apply_transaction,
    definition_conflict_locus, empty_document, validate_document,
)


def pid(value: str) -> ProjectId: return ProjectId(value)
def rev(value: str) -> ProjectRevisionId: return ProjectRevisionId(value)
def tid(value: str) -> ThingId: return ThingId(value)
def port(value: str, kind: PortKind, direction: PortDirection) -> PortRecord:
    return PortRecord(PortId(value), value, kind, direction)
def tx(number: int, *ops) -> SemanticTransaction:
    return SemanticTransaction(rev(f"r{number}"), tuple(ops))


class SMX023CanonicalCoreTests(unittest.TestCase):
    def base_graph(self):
        doc = empty_document(pid("project-main"), rev("r0"))
        things = [
            ThingRecord(tid("parent-a"), "Parent A"), ThingRecord(tid("parent-b"), "Parent B"),
            ThingRecord(tid("child"), "Child", authored_state={"x": 1}),
            ThingRecord(tid("controller"), "Controller"), ThingRecord(tid("authority"), "Authority"),
            ThingRecord(tid("store"), "Store"), ThingRecord(tid("replica"), "Replica"),
        ]
        ops = [AddThing(item) for item in things] + [
            AddRelationship(RelationshipRecord(RelationId("rel-containment"), RelationshipKind.CONTAINS, tid("parent-a"), tid("child"))),
            AddRelationship(RelationshipRecord(RelationId("rel-control"), RelationshipKind.CONTROLLED_BY, tid("child"), tid("controller"))),
            AddRelationship(RelationshipRecord(RelationId("rel-authority"), RelationshipKind.AUTHORITY_AT, tid("child"), tid("authority"))),
            AddRelationship(RelationshipRecord(RelationId("rel-persistence"), RelationshipKind.PERSISTED_VIA, tid("child"), tid("store"))),
            AddRelationship(RelationshipRecord(RelationId("rel-replication"), RelationshipKind.REPLICATED_IN, tid("child"), tid("replica"))),
        ]
        return apply_transaction(doc, tx(1, *ops))

    def connection_graph(self):
        source_port = port("clicked", PortKind.EVENT, PortDirection.OUT)
        target_port = port("open", PortKind.COMMAND, PortDirection.IN)
        return apply_transaction(empty_document(pid("project-connect"), rev("r0")), tx(1,
            AddThing(ThingRecord(tid("button"), "Button", ports={source_port.port_id: source_port})),
            AddThing(ThingRecord(tid("door"), "Door", ports={target_port.port_id: target_port})),
            AddConnection(ConnectionRecord(ConnectionId("conn-open"), ConnectionEndpoint(tid("button"), PortId("clicked")), ConnectionEndpoint(tid("door"), PortId("open")))),
        ))

    def promoted_graph(self):
        public = port("signal", PortKind.EVENT, PortDirection.OUT)
        internal = port("internal-signal", PortKind.EVENT, PortDirection.OUT)
        sink = port("receive", PortKind.COMMAND, PortDirection.IN)
        doc = apply_transaction(empty_document(pid("project-def"), rev("r0")), tx(1,
            AddThing(ThingRecord(tid("group"), "Group", authored_state={"mode": "base"}, ports={public.port_id: public})),
            AddThing(ThingRecord(tid("child-a"), "Child A", authored_state={"gain": 1}, ports={internal.port_id: internal})),
            AddThing(ThingRecord(tid("child-b"), "Child B")),
            AddThing(ThingRecord(tid("sink"), "Sink", ports={sink.port_id: sink})),
            SetContainment(tid("child-a"), tid("group"), RelationId("rel-a")),
            SetContainment(tid("child-b"), tid("group"), RelationId("rel-b")),
            AddRelationship(RelationshipRecord(RelationId("rel-control"), RelationshipKind.CONTROLLED_BY, tid("child-a"), tid("sink"))),
            AddConnection(ConnectionRecord(ConnectionId("conn-public"), ConnectionEndpoint(tid("group"), PortId("signal")), ConnectionEndpoint(tid("sink"), PortId("receive")))),
        ))
        exposure = DefinitionExposure(PortId("signal"), ElementId("element-a"), PortId("internal-signal"))
        return apply_transaction(doc, tx(2, PromoteGroup(tid("group"), DefinitionId("def-group"), {
            tid("group"): ElementId("element-root"), tid("child-a"): ElementId("element-a"), tid("child-b"): ElementId("element-b")},
            {PortId("signal"): exposure})))

    def test_role_typed_identity_is_path_independent_and_non_interchangeable(self):
        self.assertNotEqual(tid("shared"), PortId("shared")); self.assertNotEqual(AssetId("shared"), tid("shared"))
        with self.assertRaises(SemanticError): ThingId("../node")
        with self.assertRaises(SemanticError): ProjectRevisionId("/engine/path")

    def test_rename_preserves_identity_and_unrelated_relationships(self):
        before = self.base_graph(); after = apply_transaction(before, tx(2, RenameThing(tid("child"), "Renamed")))
        self.assertEqual(after.things[tid("child")].thing_id, tid("child")); self.assertEqual(before.relationships, after.relationships)

    def test_reparent_changes_only_containment(self):
        before = self.base_graph(); unrelated = {k:v for k,v in before.relationships.items() if v.kind is not RelationshipKind.CONTAINS}
        after = apply_transaction(before, tx(2, SetContainment(tid("child"), tid("parent-b"), RelationId("unused"))))
        self.assertEqual(after.relationships[RelationId("rel-containment")].source, tid("parent-b"))
        self.assertEqual(unrelated, {k:v for k,v in after.relationships.items() if v.kind is not RelationshipKind.CONTAINS})

    def test_containment_cycle_fails_and_previous_revision_is_unchanged(self):
        before = self.base_graph(); snapshot = copy.deepcopy(before)
        with self.assertRaisesRegex(SemanticError, "cycle"):
            apply_transaction(before, tx(2, SetContainment(tid("parent-a"), tid("child"), RelationId("cycle"))))
        self.assertEqual(before, snapshot)

    def test_nested_transient_host_identity_is_rejected_before_commit(self):
        before = self.base_graph()
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(before, tx(2, SetAuthoredState(tid("child"), {"safe": {"nested": {"transport_peer_id": 41}}})))
        self.assertEqual(caught.exception.code, "canonical.forbidden_transient_identity"); self.assertEqual(before.things[tid("child")].authored_state, {"x": 1})

    def test_authored_url_value_is_data_not_implicitly_identity(self):
        after = apply_transaction(self.base_graph(), tx(2, SetAuthoredState(tid("child"), {"homepage": "https://example.invalid/a"})))
        self.assertIn("homepage", after.things[tid("child")].authored_state)

    def test_duplicate_identity_rolls_back_earlier_operations(self):
        before = self.base_graph(); snapshot = copy.deepcopy(before)
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(before, tx(2, RenameThing(tid("child"), "Would leak"), AddThing(ThingRecord(tid("child"), "Duplicate"))))
        self.assertEqual(caught.exception.code, "canonical.duplicate_identity"); self.assertEqual(before, snapshot)

    def test_invalid_connection_endpoint_rolls_back_whole_transaction(self):
        before = self.connection_graph(); snapshot = copy.deepcopy(before)
        bad = ConnectionRecord(ConnectionId("conn-bad"), ConnectionEndpoint(tid("button"), PortId("missing")), ConnectionEndpoint(tid("door"), PortId("open")))
        with self.assertRaises(SemanticError): apply_transaction(before, tx(2, RenameThing(tid("door"), "Changed"), AddConnection(bad)))
        self.assertEqual(before, snapshot)

    def test_final_document_validation_rejects_dangling_connection_and_rolls_back(self):
        before = self.connection_graph(); snapshot = copy.deepcopy(before)
        with self.assertRaises(SemanticError) as caught: apply_transaction(before, tx(2, RemovePort(tid("door"), PortId("open"))))
        self.assertEqual(caught.exception.code, "canonical.invalid_endpoint"); self.assertEqual(before, snapshot)

    def test_connection_can_be_tombstoned_then_port_removed_atomically(self):
        after = apply_transaction(self.connection_graph(), tx(2, TombstoneConnection(ConnectionId("conn-open")), RemovePort(tid("door"), PortId("open"))))
        self.assertTrue(after.connections[ConnectionId("conn-open")].tombstoned); self.assertNotIn(PortId("open"), after.things[tid("door")].ports)

    def test_connection_identity_cannot_be_reused_after_tombstone(self):
        removed = apply_transaction(self.connection_graph(), tx(2, TombstoneConnection(ConnectionId("conn-open"))))
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(removed, tx(3, AddConnection(ConnectionRecord(ConnectionId("conn-open"), ConnectionEndpoint(tid("button"), PortId("clicked")), ConnectionEndpoint(tid("door"), PortId("open"))))))
        self.assertEqual(caught.exception.code, "canonical.duplicate_identity")

    def test_r018_04_thing_tombstone_atomically_tombstones_incident_connections(self):
        after = apply_transaction(self.connection_graph(), tx(2, TombstoneThing(tid("door"))))
        self.assertTrue(after.things[tid("door")].tombstoned); self.assertTrue(after.connections[ConnectionId("conn-open")].tombstoned)
        self.assertEqual(after.reference_state(tid("door")), ReferenceState.TOMBSTONED)

    def test_r018_02_new_connection_to_tombstone_fails_without_resurrection(self):
        deleted = apply_transaction(self.connection_graph(), tx(2, TombstoneThing(tid("door")))); snapshot = copy.deepcopy(deleted)
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(deleted, tx(3, AddConnection(ConnectionRecord(ConnectionId("late"), ConnectionEndpoint(tid("button"), PortId("clicked")), ConnectionEndpoint(tid("door"), PortId("open"))))))
        self.assertEqual(caught.exception.code, "canonical.target_tombstoned"); self.assertEqual(deleted, snapshot)

    def test_known_unloaded_tombstone_and_unknown_are_distinct(self):
        doc = empty_document(pid("project-ref"), rev("r0")); doc.known_unloaded_things.add(tid("remote"))
        doc = apply_transaction(doc, tx(1, AddThing(ThingRecord(tid("local"), "Local")))); doc = apply_transaction(doc, tx(2, TombstoneThing(tid("local"))))
        self.assertEqual(doc.reference_state(tid("remote")), ReferenceState.KNOWN_UNLOADED); self.assertEqual(doc.reference_state(tid("local")), ReferenceState.TOMBSTONED); self.assertEqual(doc.reference_state(tid("never")), ReferenceState.UNKNOWN)

    def test_group_promotion_preserves_first_instance_thing_ids_and_relationships(self):
        before = self.promoted_graph(); instance = before.instances[tid("group")]
        self.assertEqual(instance.thing_by_element[ElementId("element-root")], tid("group")); self.assertEqual(instance.thing_by_element[ElementId("element-a")], tid("child-a"))
        self.assertEqual(before.relationships[RelationId("rel-control")].target, tid("sink")); self.assertEqual(before.connections[ConnectionId("conn-public")].source.thing_id, tid("group"))

    def test_definition_can_instantiate_with_explicit_independent_thing_ids(self):
        before = self.promoted_graph(); definition = before.definitions[DefinitionId("def-group")]
        mapping = {ElementId("element-root"): tid("copy-root"), ElementId("element-a"): tid("copy-a"), ElementId("element-b"): tid("copy-b")}
        after = apply_transaction(before, tx(3, InstantiateDefinition(definition.definition_id, mapping, {ElementId("element-a"): RelationId("copy-rel-a"), ElementId("element-b"): RelationId("copy-rel-b")})))
        self.assertEqual(after.instances[tid("copy-root")].thing_by_element, mapping); self.assertIn(PortId("signal"), after.things[tid("copy-root")].ports)

    def test_sparse_instance_override_keeps_definition_scoped_locus(self):
        before = self.promoted_graph(); after = apply_transaction(before, tx(3, SetInstanceStateOverride(tid("group"), DefinitionId("def-group"), ElementId("element-a"), "gain", 7)))
        self.assertEqual(after.instances[tid("group")].state_overrides[ElementId("element-a")]["gain"], 7)
        with self.assertRaises(SemanticError) as caught:
            apply_transaction(after, tx(4, SetInstanceStateOverride(tid("group"), DefinitionId("def-other"), ElementId("element-a"), "gain", 9)))
        self.assertEqual(caught.exception.code, "canonical.definition_scope_mismatch")

    def test_r018_01_definition_conflict_locus_includes_definition_identity(self):
        self.assertNotEqual(definition_conflict_locus(DefinitionId("def-one"), ElementId("shared-name"), "gain"), definition_conflict_locus(DefinitionId("def-two"), ElementId("shared-name"), "gain"))

    def test_compatible_definition_restructure_preserves_public_connection_and_control(self):
        before = self.promoted_graph(); old = before.definitions[DefinitionId("def-group")]; elements = dict(old.elements)
        elements[ElementId("element-b")] = replace(elements[ElementId("element-b")], parent_element_id=ElementId("element-a"))
        after = apply_transaction(before, tx(3, ReplaceDefinition(replace(old, revision=2, elements=elements))))
        self.assertEqual(after.relationships[RelationId("rel-b")].source, tid("child-a")); self.assertFalse(after.connections[ConnectionId("conn-public")].tombstoned)
        self.assertEqual(after.relationships[RelationId("rel-control")], before.relationships[RelationId("rel-control")])

    def test_definition_base_update_preserves_compatible_sparse_override(self):
        before = apply_transaction(self.promoted_graph(), tx(3, SetInstanceStateOverride(tid("group"), DefinitionId("def-group"), ElementId("element-a"), "gain", 9)))
        old = before.definitions[DefinitionId("def-group")]; elements = dict(old.elements); elements[ElementId("element-a")] = replace(elements[ElementId("element-a")], authored_state={"gain": 2})
        after = apply_transaction(before, tx(4, ReplaceDefinition(replace(old, revision=2, elements=elements))))
        self.assertEqual(after.instances[tid("group")].state_overrides[ElementId("element-a")]["gain"], 9)

    def test_definition_removal_of_override_target_conflicts_and_rolls_back(self):
        before = apply_transaction(self.promoted_graph(), tx(3, SetInstanceStateOverride(tid("group"), DefinitionId("def-group"), ElementId("element-a"), "gain", 9))); snapshot = copy.deepcopy(before)
        old = before.definitions[DefinitionId("def-group")]; elements = dict(old.elements); del elements[ElementId("element-a")]
        with self.assertRaises(SemanticError) as caught: apply_transaction(before, tx(4, ReplaceDefinition(replace(old, revision=2, elements=elements, exposures={}))))
        self.assertEqual(caught.exception.code, "canonical.definition_conflict"); self.assertEqual(before, snapshot)

    def test_definition_removal_with_durable_reference_conflicts(self):
        before = apply_transaction(self.promoted_graph(), tx(3, AddRelationship(RelationshipRecord(RelationId("ref-child-b"), RelationshipKind.REFERENCES, tid("sink"), tid("child-b")))))
        old = before.definitions[DefinitionId("def-group")]; elements = dict(old.elements); del elements[ElementId("element-b")]
        with self.assertRaises(SemanticError) as caught: apply_transaction(before, tx(4, ReplaceDefinition(replace(old, revision=2, elements=elements))))
        self.assertEqual(caught.exception.code, "canonical.definition_conflict")

    def test_removing_connected_public_exposure_conflicts(self):
        before = self.promoted_graph(); old = before.definitions[DefinitionId("def-group")]
        with self.assertRaises(SemanticError) as caught: apply_transaction(before, tx(3, ReplaceDefinition(replace(old, revision=2, exposures={}))))
        self.assertEqual(caught.exception.code, "canonical.definition_conflict")

    def test_behaviour_attachment_identity_is_separate_from_thing_identity(self):
        attachment = BehaviourAttachmentRecord(BehaviourAttachmentId("beh-main"), "behaviour-revision-1", {"speed": 2})
        after = apply_transaction(self.base_graph(), tx(2, AddBehaviourAttachment(tid("child"), attachment)))
        self.assertIn(attachment.attachment_id, after.things[tid("child")].behaviours); self.assertNotEqual(attachment.attachment_id, tid("beh-main"))

    def test_transient_context_is_not_part_of_canonical_document(self):
        doc = self.base_graph(); snapshot = copy.deepcopy(doc); context = TransientContext(runtime_handles={tid("child"): object()}, session_id="session-7", transport_peer_id="peer-9", editor_selection={tid("child")})
        context.session_id = "session-8"; self.assertEqual(doc, snapshot); self.assertFalse(hasattr(doc, "session_id")); self.assertFalse(hasattr(doc, "runtime_handles"))

    def test_protected_asset_identity_is_role_typed_without_field_level_media_mutation(self):
        asset_id = AssetId("asset-audio-1"); after = apply_transaction(self.base_graph(), tx(2, SetAuthoredState(tid("child"), {"sound_asset": asset_id})))
        self.assertEqual(after.things[tid("child")].authored_state["sound_asset"], asset_id); self.assertNotEqual(asset_id, tid("asset-audio-1")); self.assertFalse(hasattr(after, "asset_revision_fields"))

    def test_mismatched_identity_role_fails_document_validation(self):
        doc = empty_document(pid("project-bad"), rev("r0")); bad = ThingRecord(PortId("not-a-thing"), "Bad")  # type: ignore[arg-type]
        doc.things[PortId("not-a-thing")] = bad  # type: ignore[index]
        with self.assertRaises(SemanticError) as caught: validate_document(doc)
        self.assertEqual(caught.exception.code, "canonical.identity_role_mismatch")

    def test_invalid_definition_endpoint_fails_before_publication(self):
        doc = empty_document(pid("project-def-bad"), rev("r0")); definition = DefinitionRecord(DefinitionId("def-bad"), 1, ElementId("root"), {ElementId("root"): DefinitionElementRecord(ElementId("root"), "Root", ports={})}, {PortId("public"): DefinitionExposure(PortId("public"), ElementId("root"), PortId("missing"))})
        with self.assertRaises(SemanticError) as caught: apply_transaction(doc, tx(1, AddDefinition(definition)))
        self.assertEqual(caught.exception.code, "canonical.invalid_definition"); self.assertFalse(doc.definitions)


if __name__ == "__main__": unittest.main()
