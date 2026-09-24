from __future__ import annotations

from copy import deepcopy
import unittest

from splashmx.canonical.core import (
    AssetId,
    ConnectionId,
    DefinitionId,
    PortId,
    RelationshipKind,
    ThingId,
)
from splashmx.canonical.serialization import ProtectedAssetRevision, SerializationError
from splashmx.editor.authoring import (
    AuthoringError,
    AuthoringSession,
    assert_author_surface_vocabulary,
)
from splashmx.execution.ir import IR_VERSION


class AuthoringSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = AuthoringSession.blank("smx032-tests")

    def test_blank_stage_creation_publishes_through_canonical_revision(self) -> None:
        before = self.session.document.project_revision_id
        thing = self.session.create_thing(label="Button", thing_id="button", authored_state={"x": 12})
        self.assertEqual(thing, ThingId("button"))
        self.assertNotEqual(self.session.document.project_revision_id, before)
        self.assertEqual(self.session.document.things[thing].authored_state["x"], 12)

    def test_visual_projection_is_canonical_and_updates_without_losing_other_state(self) -> None:
        thing = self.session.create_thing(
            label="Box",
            thing_id="box",
            authored_state={
                "custom": {"kept": True},
                "visual": {"x": 10, "y": 20, "width": 120, "height": 80, "rotation": 0, "shape": "rectangle", "fill": "#ABCDEF"},
            },
        )
        visual = self.session.document.things[thing].authored_state["visual"]
        self.assertEqual(visual["fill"], "#abcdef")
        before = self.session.document.project_revision_id
        updated = self.session.update_visual_state(thing, visual={"x": 55, "rotation": 15})
        self.assertNotEqual(self.session.document.project_revision_id, before)
        self.assertEqual(updated["x"], 55)
        self.assertEqual(updated["y"], 20)
        self.assertEqual(updated["width"], 120)
        self.assertEqual(updated["rotation"], 15)
        self.assertEqual(self.session.document.things[thing].authored_state["custom"], {"kept": True})

    def test_visual_projection_rejects_invalid_values_without_mutation(self) -> None:
        thing = self.session.create_thing(
            label="Box",
            thing_id="box",
            authored_state={"visual": {"shape": "ellipse", "fill": "#123456"}},
        )
        before_revision = self.session.document.project_revision_id
        before_state = deepcopy(self.session.document.things[thing].authored_state)
        with self.assertRaises(AuthoringError):
            self.session.update_visual_state(thing, visual={"width": 0})
        self.assertEqual(self.session.document.project_revision_id, before_revision)
        self.assertEqual(self.session.document.things[thing].authored_state, before_state)

    def test_selection_is_transient_and_does_not_advance_project_revision(self) -> None:
        thing = self.session.create_thing(label="Button", thing_id="button")
        revision = self.session.document.project_revision_id
        self.session.select([thing])
        self.session.set_inspect_open(True)
        self.assertEqual(self.session.document.project_revision_id, revision)
        snapshot = self.session.snapshot()
        self.assertEqual(snapshot["editor"]["selection"], ["button"])
        self.assertTrue(snapshot["editor"]["inspect_open"])
        self.assertNotIn("selection", snapshot["canonical"])
        self.assertNotIn("inspect_open", snapshot["canonical"])

    def test_grouping_changes_containment_only_and_preserves_member_ids(self) -> None:
        first = self.session.create_thing(label="First", thing_id="first")
        second = self.session.create_thing(label="Second", thing_id="second")
        group = self.session.group_things([first, second], label="Pair", group_id="pair")
        self.assertEqual(set(self.session.document.things), {first, second, group})
        active = [
            row for row in self.session.document.relationships.values()
            if not row.tombstoned and row.kind is RelationshipKind.CONTAINS
        ]
        self.assertEqual({row.target for row in active}, {first, second})
        self.assertEqual({row.source for row in active}, {group})

    def test_group_failure_is_atomic(self) -> None:
        first = self.session.create_thing(label="First", thing_id="first")
        revision = self.session.document.project_revision_id
        before = deepcopy(self.session.document)
        with self.assertRaises(AuthoringError):
            self.session.group_things([first, ThingId("missing")], group_id="bad-group")
        self.assertEqual(self.session.document.project_revision_id, revision)
        self.assertEqual(self.session.document, before)
        self.assertNotIn(ThingId("bad-group"), self.session.document.things)

    def test_make_reusable_preserves_first_instance_concrete_identities(self) -> None:
        first = self.session.create_thing(label="First", thing_id="first")
        second = self.session.create_thing(label="Second", thing_id="second")
        group = self.session.group_things([first, second], group_id="pair")
        before = set(self.session.document.things)
        definition = self.session.make_reusable(group, definition_id="pair-definition")
        self.assertEqual(definition, DefinitionId("pair-definition"))
        self.assertEqual(set(self.session.document.things), before)
        instance = self.session.document.instances[group]
        self.assertEqual(set(instance.thing_by_element.values()), before)

    def test_reusable_instantiation_allocates_independent_concrete_ids(self) -> None:
        child = self.session.create_thing(label="Child", thing_id="child")
        group = self.session.group_things([child], group_id="group")
        definition = self.session.make_reusable(group, definition_id="widget")
        first_ids = set(self.session.document.instances[group].thing_by_element.values())
        copy_root = self.session.instantiate_reusable(definition)
        second_ids = set(self.session.document.instances[copy_root].thing_by_element.values())
        self.assertTrue(first_ids.isdisjoint(second_ids))

    def test_rule_and_behaviour_share_versioned_constrained_ir(self) -> None:
        rule_thing = self.session.create_thing(label="Rule thing", thing_id="rule-thing")
        behaviour_thing = self.session.create_thing(label="Behaviour thing", thing_id="behaviour-thing")
        rule_slot = self.session.attach_rule(
            rule_thing,
            attachment_id="rule-slot",
            actions=[{"action": "set_public", "key": "on", "value": True}],
        )
        behaviour_slot = self.session.attach_behaviour(
            behaviour_thing,
            attachment_id="behaviour-slot",
            actions=[{"action": "set_public", "key": "on", "value": True}],
        )
        rule_revision = self.session.document.things[rule_thing].behaviours[rule_slot].behaviour_revision
        behaviour_revision = self.session.document.things[behaviour_thing].behaviours[behaviour_slot].behaviour_revision
        self.assertEqual(self.session.programs[rule_revision].ir_version, IR_VERSION)
        self.assertEqual(self.session.programs[behaviour_revision].ir_version, IR_VERSION)
        self.assertEqual(
            self.session.programs[rule_revision].handlers[0].instructions,
            self.session.programs[behaviour_revision].handlers[0].instructions,
        )

    def test_invalid_behaviour_is_rejected_before_attachment_publication(self) -> None:
        thing = self.session.create_thing(label="Button", thing_id="button")
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.attach_rule(
                thing,
                attachment_id="unsafe",
                actions=[{"action": "host_call", "key": "x", "value": 1}],
            )
        self.assertEqual(self.session.document.project_revision_id, revision)
        self.assertNotIn("unsafe", {str(key) for key in self.session.document.things[thing].behaviours})

    def test_connection_uses_stable_thing_and_port_ids(self) -> None:
        source = self.session.create_thing(label="Button", thing_id="button")
        target = self.session.create_thing(label="Lamp", thing_id="lamp")
        self.session.add_port(source, port_id="clicked", name="Clicked", kind="event", direction="out")
        self.session.add_port(target, port_id="toggle", name="Toggle", kind="command", direction="in")
        connection = self.session.connect(
            source_thing_id=source,
            source_port_id="clicked",
            target_thing_id=target,
            target_port_id="toggle",
            connection_id="button-lamp",
        )
        row = self.session.document.connections[connection]
        self.assertEqual(row.connection_id, ConnectionId("button-lamp"))
        self.assertEqual(row.source.thing_id, source)
        self.assertEqual(row.source.port_id, PortId("clicked"))
        self.assertEqual(row.target.thing_id, target)
        self.assertEqual(row.target.port_id, PortId("toggle"))

    def test_hierarchy_path_cannot_be_smuggled_in_as_port_identity(self) -> None:
        thing = self.session.create_thing(label="Button", thing_id="button")
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.add_port(thing, port_id="Stage/Button", name="Bad", kind="event", direction="out")
        self.assertEqual(self.session.document.project_revision_id, revision)

    def test_invalid_connection_rolls_back_without_partial_record(self) -> None:
        source = self.session.create_thing(label="Button", thing_id="button")
        target = self.session.create_thing(label="Lamp", thing_id="lamp")
        self.session.add_port(source, port_id="clicked", name="Clicked", kind="event", direction="out")
        before = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.connect(
                source_thing_id=source,
                source_port_id="clicked",
                target_thing_id=target,
                target_port_id="missing",
                connection_id="broken",
            )
        self.assertEqual(self.session.document.project_revision_id, before)
        self.assertNotIn(ConnectionId("broken"), self.session.document.connections)

    def test_visual_timeline_targets_existing_visual_projection_without_mutating_base(self) -> None:
        thing = self.session.create_thing(
            label="Sprite",
            thing_id="visual-sprite",
            authored_state={"visual": {"x": 25, "y": 30, "width": 120, "height": 80, "rotation": 0, "shape": "rectangle", "fill": "#123456"}},
        )
        base_visual = deepcopy(self.session.document.things[thing].authored_state["visual"])
        track = self.session.add_timeline_track(
            thing,
            property_name="visual.x",
            keyframes=[{"tick": 0, "value": 25}, {"tick": 60, "value": 225}],
            track_id="visual-move-x",
        )
        self.assertEqual(track, "visual-move-x")
        authored = self.session.document.things[thing].authored_state
        self.assertEqual(authored["visual"], base_visual)
        self.assertEqual(authored["timeline_tracks"][0]["property"], "visual.x")
        self.assertEqual(authored["timeline_tracks"][0]["keyframes"][-1], {"tick": 60, "value": 225})

    def test_timeline_is_optional_and_targets_stable_thing_identity(self) -> None:
        thing = self.session.create_thing(label="Sprite", thing_id="sprite", authored_state={"x": 0})
        self.assertNotIn("timeline_tracks", self.session.document.things[thing].authored_state)
        track = self.session.add_timeline_track(
            thing,
            property_name="x",
            keyframes=[{"tick": 0, "value": 0}, {"tick": 60, "value": 100}],
            track_id="move-x",
        )
        self.assertEqual(track, "move-x")
        row = self.session.document.things[thing].authored_state["timeline_tracks"][0]
        self.assertEqual(row["target_thing_id"], "sprite")
        self.assertEqual(row["property"], "x")

    def test_timeline_rejects_substrate_locator_target_without_mutation(self) -> None:
        thing = self.session.create_thing(label="Sprite", thing_id="sprite")
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.add_timeline_track(thing, property_name="NodePath.position", keyframes=[])
        self.assertEqual(self.session.document.project_revision_id, revision)

    def test_complete_media_import_creates_indivisible_protected_revision(self) -> None:
        thing, asset_id = self.session.import_asset_thing(
            content=b"RIFF-smx032-audio",
            source_name="tone.wav",
            media_type="audio/wav",
            media_semantics={"kind": "audio", "loop": False, "gain_db": 0},
            provenance={"origin": "recorded", "creator": "fixture"},
            licence_attribution={"licence": "CC0", "attribution": "fixture"},
            derivation_lineage=({"operation": "source", "parent": None},),
            asset_id="tone",
            thing_id="tone-thing",
        )
        asset = self.session.project.assets[asset_id]
        self.assertEqual(asset.asset_id, AssetId("tone"))
        self.assertTrue(asset.source_digest.startswith("sha256:"))
        self.assertEqual(self.session.document.things[thing].authored_state["asset_id"], "tone")
        self.assertEqual(
            self.session.document.things[thing].authored_state["asset_revision_digest"],
            asset.revision_digest,
        )

    def test_incomplete_protected_media_import_fails_without_partial_thing_or_asset(self) -> None:
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.import_asset_thing(
                content=b"source",
                source_name="tone.wav",
                media_type="audio/wav",
                media_semantics={"kind": "audio"},
                provenance={},
                licence_attribution={"licence": "CC0"},
                derivation_lineage=({"operation": "source", "parent": None},),
                asset_id="tone",
                thing_id="tone-thing",
            )
        self.assertEqual(self.session.document.project_revision_id, revision)
        self.assertFalse(self.session.project.assets)
        self.assertNotIn(ThingId("tone-thing"), self.session.document.things)

    def test_existing_asset_id_cannot_be_rebound_to_competing_revision(self) -> None:
        _, asset_id = self.session.import_asset_thing(
            content=b"original",
            source_name="tone.wav",
            media_type="audio/wav",
            media_semantics={"kind": "audio"},
            provenance={"origin": "first"},
            licence_attribution={"licence": "CC0"},
            derivation_lineage=({"operation": "source", "parent": None},),
            asset_id="tone",
            thing_id="first",
        )
        old = self.session.project.assets[asset_id]
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.import_asset_thing(
                content=b"replacement",
                source_name="tone-2.wav",
                media_type="audio/wav",
                media_semantics={"kind": "audio"},
                provenance={"origin": "second"},
                licence_attribution={"licence": "CC-BY", "attribution": "second"},
                derivation_lineage=({"operation": "source", "parent": None},),
                asset_id="tone",
                thing_id="second",
            )
        self.assertEqual(self.session.document.project_revision_id, revision)
        self.assertEqual(self.session.project.assets[asset_id], old)
        self.assertNotIn(ThingId("second"), self.session.document.things)

    def test_old_asset_digest_cannot_validate_field_mixed_revision(self) -> None:
        _, asset_id = self.session.import_asset_thing(
            content=b"original",
            source_name="tone.wav",
            media_type="audio/wav",
            media_semantics={"kind": "audio"},
            provenance={"origin": "first"},
            licence_attribution={"licence": "CC0"},
            derivation_lineage=({"operation": "source", "parent": None},),
            asset_id="tone",
            thing_id="first",
        )
        old = self.session.project.assets[asset_id]
        with self.assertRaises(SerializationError):
            ProtectedAssetRevision(
                old.asset_id,
                old.revision_digest,
                old.source_digest,
                old.source_identity,
                old.source_metadata,
                old.media_semantics,
                {"origin": "mixed"},
                old.licence_attribution,
                old.derivation_lineage,
            )

    def test_transient_authority_field_is_rejected_without_publication(self) -> None:
        revision = self.session.document.project_revision_id
        with self.assertRaises(AuthoringError):
            self.session.create_thing(
                label="Bad",
                thing_id="bad",
                authored_state={"transport_peer_id": "peer-9"},
            )
        self.assertEqual(self.session.document.project_revision_id, revision)
        self.assertNotIn(ThingId("bad"), self.session.document.things)

    def test_ordinary_surface_vocabulary_guard(self) -> None:
        assert_author_surface_vocabulary("Stage Thing Behaviour Rule Connection Timeline Inspect")
        for forbidden in ("NodePath", "SceneTree", "ResourceUID", "package manager", "export preset"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(AuthoringError):
                    assert_author_surface_vocabulary(f"Please configure {forbidden}.")

    def test_snapshot_preserves_connection_id_as_canonical_not_transport_identity(self) -> None:
        source = self.session.create_thing(label="Button", thing_id="button")
        target = self.session.create_thing(label="Lamp", thing_id="lamp")
        self.session.add_port(source, port_id="clicked", name="Clicked", kind="event", direction="out")
        self.session.add_port(target, port_id="toggle", name="Toggle", kind="command", direction="in")
        self.session.connect(
            source_thing_id=source,
            source_port_id="clicked",
            target_thing_id=target,
            target_port_id="toggle",
            connection_id="semantic-connection",
        )
        snapshot = self.session.snapshot()
        self.assertEqual(snapshot["canonical"]["connections"][0]["connection_id"], "semantic-connection")
        self.assertNotIn("transport_peer_id", repr(snapshot["canonical"]))


if __name__ == "__main__":
    unittest.main()
