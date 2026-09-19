from __future__ import annotations

import itertools
import unittest

from model import (
    CausalCycle,
    Operation,
    Relay,
    Replica,
    Transaction,
    TransactionCollision,
    ValidationError,
    equivalent,
    materialize,
    synchronize,
    validate_document,
)


def asset_bundle(tag: str) -> dict:
    return {
        "digest": f"sha256:{tag}",
        "source": {
            "logical_source": f"source:{tag}",
            "master_digest": f"sha256:master-{tag}",
            "media_type": "audio/flac",
        },
        "audio": {
            "channels": 2,
            "sample_rate": 48000,
            "semantic_role": "music",
        },
        "provenance": {
            "author": f"author-{tag}",
            "origin": f"capture:{tag}",
        },
        "licence": "CC-BY-4.0",
        "derivation": {
            "derived_from": f"master:{tag}",
            "recipe": "identity",
        },
    }


def base_state() -> dict:
    return {
        "document_id": "doc:smx018",
        "revision_id": "rev:base",
        "schema_version": 1,
        "things": {
            "world": {
                "parent": None,
                "props": {"name": "World"},
                "ports": [],
                "existence": "present",
            },
            "x": {
                "parent": "world",
                "props": {"title": "base", "left": 0, "right": 0},
                "ports": ["out", "alt"],
                "existence": "present",
            },
            "y": {
                "parent": "world",
                "props": {"value": 0},
                "ports": ["in"],
                "existence": "present",
            },
            "a": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
            "b": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
            "c": {"parent": "world", "props": {}, "ports": [], "existence": "present"},
        },
        "catalog_status": {
            "world": "loaded",
            "x": "loaded",
            "y": "loaded",
            "a": "loaded",
            "b": "loaded",
            "c": "loaded",
        },
        "definitions": {
            "def:widget": {
                "revision_id": "defrev:widget:1",
                "elements": {
                    "body": {"color": "white"},
                    "label": {"text": "hello"},
                },
            },
            "def:other": {
                "revision_id": "defrev:other:1",
                "elements": {"body": {"color": "black"}},
            },
        },
        "instances": {
            "inst:widget": {
                "definition_id": "def:widget",
                "base_revision_id": "defrev:widget:1",
                "component_version": "1.0.0",
                "overlays": {},
            },
            "inst:other": {
                "definition_id": "def:other",
                "base_revision_id": "defrev:other:1",
                "component_version": "1.0.0",
                "overlays": {},
            },
        },
        "connections": {
            "conn:base": {
                "source_thing": "x",
                "source_port": "out",
                "target_thing": "y",
                "target_port": "in",
                "tombstoned": False,
            }
        },
        "keyframes": {},
        "groups": {},
        "assets": {
            "asset:music": {
                "asset_id": "asset:music",
                "label": "Theme",
                "revision_bundle": asset_bundle("base"),
            }
        },
    }


def op(kind: str, target: str, **data) -> Operation:
    return Operation(kind, target, data)


def tx(
    tx_id: str,
    actor: str,
    *operations: Operation,
    deps=(),
    permission_epoch: int = 1,
    schema_version: int = 1,
    inverse_of: str | None = None,
    resolves=(),
) -> Transaction:
    return Transaction(
        tx_id,
        actor,
        tuple(operations),
        frozenset(deps),
        permission_epoch,
        schema_version,
        inverse_of,
        frozenset(resolves),
    )


def conflict_kinds(result) -> list[str]:
    return [item.kind for item in result.conflicts]


def two_replicas():
    return Replica("left", base_state()), Replica("right", base_state()), Relay()


class CollaborationHarnessTests(unittest.TestCase):
    def test_cr001_offline_independent_edits_reconnect_and_converge(self):
        left, right, relay = two_replicas()
        left.disconnect(); right.disconnect()
        left.author(tx("tx:left", "alice", op("set_property", "x", key="left", value=9)))
        right.author(tx("tx:right", "bob", op("set_property", "x", key="right", value=8)))
        left.reconnect(); right.reconnect()
        synchronize(
            relay,
            [left, right],
            delivery_orders={
                "left": ["tx:right", "tx:left"],
                "right": ["tx:left", "tx:right"],
            },
        )
        self.assertTrue(equivalent([left, right]))
        state = left.materialize().state
        self.assertEqual(state["things"]["x"]["props"]["left"], 9)
        self.assertEqual(state["things"]["x"]["props"]["right"], 8)

    def test_cr002_same_property_conflict_survives_reordered_reconnect(self):
        left, right, relay = two_replicas()
        left.author(tx("tx:a", "alice", op("set_property", "x", key="title", value="A")))
        right.author(tx("tx:b", "bob", op("set_property", "x", key="title", value="B")))
        synchronize(
            relay,
            [left, right],
            delivery_orders={"left": ["tx:b", "tx:a"], "right": ["tx:a", "tx:b"]},
            duplicate_each=True,
        )
        self.assertTrue(equivalent([left, right]))
        result = left.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertEqual(conflict_kinds(result), ["same_property"])

    def test_cr003_delete_edit_is_remove_wins_and_never_resurrects(self):
        result = materialize(
            base_state(),
            [
                tx("tx:delete", "alice", op("delete_thing", "x")),
                tx("tx:edit", "bob", op("set_property", "x", key="title", value="late")),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["existence"], "tombstoned")
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertIn("delete_edit", conflict_kinds(result))

    def test_cr004_reparent_reparent_holds_prior_legal_parent(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("reparent", "x", parent="a")),
                tx("tx:b", "bob", op("reparent", "x", parent="b")),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["parent"], "world")
        self.assertEqual(conflict_kinds(result), ["reparent"])

    def test_cr005_compatible_definition_edit_and_instance_overlay_merge(self):
        result = materialize(
            base_state(),
            [
                tx("tx:def", "alice", op("definition_set", "def:widget", element="body", key="color", value="blue")),
                tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")),
            ],
        )
        self.assertEqual(result.conflicts, ())
        self.assertEqual(result.state["definitions"]["def:widget"]["elements"]["body"]["color"], "blue")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")

    def test_cr006_definition_removal_and_same_definition_overlay_conflict(self):
        result = materialize(
            base_state(),
            [
                tx("tx:remove", "alice", op("definition_remove_element", "def:widget", element="body")),
                tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["definition_instance"])
        self.assertIn("body", result.state["definitions"]["def:widget"]["elements"])

    def test_cr007_definition_conflict_is_scoped_by_definition_identity(self):
        result = materialize(
            base_state(),
            [
                tx("tx:remove", "alice", op("definition_remove_element", "def:widget", element="body")),
                tx("tx:overlay", "bob", op("instance_overlay", "inst:other", element="body", key="color", value="red")),
            ],
        )
        self.assertEqual(result.conflicts, ())
        self.assertNotIn("body", result.state["definitions"]["def:widget"]["elements"])
        self.assertEqual(result.state["instances"]["inst:other"]["overlays"]["body:color"], "red")

    def test_cr008_structural_move_and_stable_port_connection_merge(self):
        result = materialize(
            base_state(),
            [
                tx("tx:move", "alice", op("reparent", "x", parent="a")),
                tx("tx:connect", "bob", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")),
            ],
        )
        self.assertEqual(result.conflicts, ())
        self.assertEqual(result.state["things"]["x"]["parent"], "a")
        self.assertIn("conn:new", result.state["connections"])

    def test_cr009_port_removal_and_connection_are_atomic_conflict(self):
        result = materialize(
            base_state(),
            [
                tx("tx:port", "alice", op("delete_port", "x", port="out")),
                tx("tx:connect", "bob", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["structure_connection"])
        self.assertIn("out", result.state["things"]["x"]["ports"])
        self.assertNotIn("conn:new", result.state["connections"])

    def test_cr010_thing_delete_remove_wins_over_new_connection_endpoint(self):
        result = materialize(
            base_state(),
            [
                tx("tx:delete", "alice", op("delete_thing", "x")),
                tx("tx:connect", "bob", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")),
            ],
        )
        self.assertIn("delete_connection_endpoint", conflict_kinds(result))
        self.assertEqual(result.state["things"]["x"]["existence"], "tombstoned")
        self.assertNotIn("conn:new", result.state["connections"])
        validate_document(result.state)

    def test_cr011_invalid_connection_endpoint_or_port_cannot_materialize(self):
        result = materialize(
            base_state(),
            [
                tx("tx:bad", "alice", op("create_connection", "conn:bad", source_thing="x", source_port="missing", target_thing="y", target_port="in")),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["precondition_failed"])
        self.assertNotIn("conn:bad", result.state["connections"])

    def test_cr012_independent_timeline_keys_merge(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("set_keyframe", "kf:a", track="t", time=1, value=10)),
                tx("tx:b", "bob", op("set_keyframe", "kf:b", track="t", time=2, value=20)),
            ],
        )
        self.assertEqual(result.conflicts, ())
        self.assertEqual(set(result.state["keyframes"]), {"kf:a", "kf:b"})

    def test_cr013_overlapping_timeline_locus_is_explicit_conflict(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("set_keyframe", "kf:a", track="t", time=1, value=10)),
                tx("tx:b", "bob", op("set_keyframe", "kf:b", track="t", time=1, value=20)),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["timeline_overlap"])
        self.assertEqual(result.state["keyframes"], {})

    def test_cr014_overlapping_group_commands_never_partially_apply(self):
        result = materialize(
            base_state(),
            [
                tx("tx:ab", "alice", op("group", "group:ab", members=["a", "b"])),
                tx("tx:bc", "bob", op("group", "group:bc", members=["b", "c"])),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["group_overlap"])
        self.assertEqual(result.state["groups"], {})
        self.assertEqual(result.state["things"]["b"]["parent"], "world")

    def test_cr015_compatible_component_update_and_local_overlay_survive(self):
        result = materialize(
            base_state(),
            [
                tx("tx:update", "alice", op("component_update", "inst:widget", from_version="1.0.0", to_version="1.1.0", migration_ok=True)),
                tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")),
            ],
        )
        self.assertEqual(result.conflicts, ())
        self.assertEqual(result.state["instances"]["inst:widget"]["component_version"], "1.1.0")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")

    def test_cr016_incompatible_component_update_is_held_and_local_edit_survives(self):
        result = materialize(
            base_state(),
            [
                tx("tx:update", "alice", op("component_update", "inst:widget", from_version="1.0.0", to_version="2.0.0", migration_ok=False)),
                tx("tx:overlay", "bob", op("instance_overlay", "inst:widget", element="body", key="color", value="red")),
            ],
        )
        self.assertIn("component_update_local_edit", conflict_kinds(result))
        self.assertEqual(result.state["instances"]["inst:widget"]["component_version"], "1.0.0")
        self.assertEqual(result.state["instances"]["inst:widget"]["overlays"]["body:color"], "red")

    def test_cr017_connection_remove_wins_same_id_recreate(self):
        result = materialize(
            base_state(),
            [
                tx("tx:delete", "alice", op("delete_connection", "conn:base")),
                tx("tx:create", "bob", op("create_connection", "conn:base", source_thing="x", source_port="out", target_thing="y", target_port="in")),
            ],
        )
        self.assertIn("connection_remove_recreate", conflict_kinds(result))
        self.assertTrue(result.state["connections"]["conn:base"]["tombstoned"])

    def test_cr018_same_connection_id_different_endpoints_is_explicit_conflict(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("create_connection", "conn:new", source_thing="x", source_port="out", target_thing="y", target_port="in")),
                tx("tx:b", "bob", op("create_connection", "conn:new", source_thing="x", source_port="alt", target_thing="y", target_port="in")),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["connection_identity_collision"])
        self.assertNotIn("conn:new", result.state["connections"])

    def test_cr019_duplicate_delivery_is_idempotent(self):
        left, right, relay = two_replicas()
        left.author(tx("tx:a", "alice", op("set_property", "x", key="left", value=1)))
        synchronize(relay, [left, right], duplicate_each=True)
        self.assertTrue(equivalent([left, right]))
        self.assertEqual(right.materialize().state["things"]["x"]["props"]["left"], 1)

    def test_cr020_transaction_id_collision_is_corruption_not_a_second_edit(self):
        relay = Relay()
        relay.ingest(tx("tx:a", "alice", op("set_property", "x", key="left", value=1)))
        with self.assertRaises(TransactionCollision):
            relay.ingest(tx("tx:a", "alice", op("set_property", "x", key="left", value=2)))

    def test_cr021_missing_causal_ancestor_pends_then_applies_after_reunion(self):
        left, right, relay = two_replicas()
        ancestor = tx("tx:a", "alice", op("set_property", "x", key="left", value=1))
        child = tx("tx:b", "bob", op("set_property", "x", key="right", value=2), deps=("tx:a",))
        right.author(child)
        right.push(relay)
        left.pull(relay)
        result = left.materialize()
        self.assertEqual(result.pending[0].reason, "missing_causal_dependency")
        left.author(ancestor); left.push(relay); right.pull(relay); left.pull(relay)
        self.assertTrue(equivalent([left, right]))
        self.assertEqual(left.materialize().state["things"]["x"]["props"]["right"], 2)

    def test_cr022_selective_undo_preserves_unrelated_remote_work(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("set_property", "x", key="left", value=1)),
                tx("tx:b", "bob", op("set_property", "x", key="right", value=2)),
                tx("tx:undo", "alice", op("set_property", "x", key="left", value=0, expected=1), deps=("tx:a", "tx:b"), inverse_of="tx:a"),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertEqual(result.state["things"]["x"]["props"]["right"], 2)

    def test_cr023_undo_precondition_failure_does_not_clobber_later_work(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("set_property", "x", key="left", value=1)),
                tx("tx:b", "bob", op("set_property", "x", key="left", value=2), deps=("tx:a",)),
                tx("tx:undo", "alice", op("set_property", "x", key="left", value=0, expected=1), deps=("tx:b",), inverse_of="tx:a"),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 2)
        self.assertIn("precondition_failed", conflict_kinds(result))

    def test_cr024_permission_change_while_offline_rejects_stale_edit_but_retains_history(self):
        replica = Replica("offline", base_state(), permission_epochs={"alice": 2})
        replica.disconnect()
        replica.author(tx("tx:offline", "alice", op("set_property", "x", key="title", value="offline"), permission_epoch=1))
        result = replica.materialize()
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "base")
        self.assertEqual(result.rejections[0].reason, "permission_epoch_changed")
        self.assertIn("tx:offline", result.history)

    def test_cr025_presence_is_ephemeral_and_never_relayed_or_persisted(self):
        left, right, relay = two_replicas()
        before = left.persisted_snapshot()
        left.set_presence(cursor=[4, 8], selection=["x"])
        synchronize(relay, [left, right])
        self.assertEqual(left.persisted_snapshot(), before)
        self.assertEqual(right.presence, {})
        self.assertEqual(relay.ids(), ())

    def test_cr026_known_unloaded_target_pends_and_applies_when_loaded(self):
        state = base_state()
        state["catalog_status"]["x"] = "known_unloaded"
        transaction = tx("tx:a", "alice", op("set_property", "x", key="left", value=4))
        result = materialize(state, [transaction])
        self.assertEqual(result.pending[0].reason, "known_unloaded_target")
        state2 = base_state()
        result2 = materialize(state2, [transaction])
        self.assertEqual(result2.state["things"]["x"]["props"]["left"], 4)

    def test_cr027_schema_mismatch_is_quarantined(self):
        result = materialize(
            base_state(),
            [tx("tx:future", "alice", op("set_property", "x", key="left", value=4), schema_version=2)],
        )
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertEqual(result.rejections[0].reason, "schema_migration_required")

    def test_cr028_resolution_is_new_causal_transaction_and_history_is_retained(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("set_property", "x", key="title", value="A")),
                tx("tx:b", "bob", op("set_property", "x", key="title", value="B")),
                tx("tx:resolve", "alice", op("set_property", "x", key="title", value="B", expected="base"), deps=("tx:a", "tx:b"), resolves=("tx:a", "tx:b")),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["props"]["title"], "B")
        self.assertEqual(result.conflicts, ())
        self.assertEqual(len(result.resolved_conflicts), 1)
        self.assertEqual(set(result.history), {"tx:a", "tx:b", "tx:resolve"})

    def test_boundary_tombstoned_target_rejects_late_edit(self):
        state = base_state()
        state["things"]["x"]["existence"] = "tombstoned"
        state["catalog_status"]["x"] = "tombstoned"
        state["connections"]["conn:base"]["tombstoned"] = True
        result = materialize(
            state,
            [tx("tx:late", "alice", op("set_property", "x", key="left", value=4))],
        )
        self.assertIn("target_tombstoned", conflict_kinds(result))
        self.assertEqual(result.state["things"]["x"]["existence"], "tombstoned")

    def test_boundary_concurrent_asset_replacements_never_field_mix(self):
        result = materialize(
            base_state(),
            [
                tx("tx:a", "alice", op("asset_replace", "asset:music", bundle=asset_bundle("A"))),
                tx("tx:b", "bob", op("asset_replace", "asset:music", bundle=asset_bundle("B"))),
            ],
        )
        self.assertEqual(conflict_kinds(result), ["asset_replacement"])
        self.assertEqual(result.state["assets"]["asset:music"]["revision_bundle"], asset_bundle("base"))

    def test_boundary_asset_rename_and_complete_replacement_merge_with_stable_asset_id(self):
        result = materialize(
            base_state(),
            [
                tx("tx:rename", "alice", op("asset_rename", "asset:music", label="New Theme", expected_label="Theme")),
                tx("tx:replace", "bob", op("asset_replace", "asset:music", bundle=asset_bundle("next"), expected_digest="sha256:base")),
            ],
        )
        asset = result.state["assets"]["asset:music"]
        self.assertEqual(asset["asset_id"], "asset:music")
        self.assertEqual(asset["label"], "New Theme")
        self.assertEqual(asset["revision_bundle"], asset_bundle("next"))

    def test_boundary_partial_protected_asset_revision_is_rejected_before_history_admission(self):
        broken = asset_bundle("broken")
        broken.pop("licence")
        replica = Replica("left", base_state())
        with self.assertRaises(ValidationError):
            replica.author(tx("tx:bad", "alice", op("asset_replace", "asset:music", bundle=broken)))

    def test_boundary_runtime_multiplayer_fields_are_rejected_recursively(self):
        replica = Replica("left", base_state())
        with self.assertRaises(ValidationError):
            replica.author(
                tx(
                    "tx:bad",
                    "alice",
                    op("set_property", "x", key="left", value={"nested": {"peer_id": 7}}),
                )
            )

    def test_boundary_multi_operation_transaction_is_atomic_on_document_invalidity(self):
        result = materialize(
            base_state(),
            [
                tx(
                    "tx:atomic",
                    "alice",
                    op("set_property", "x", key="left", value=99),
                    op("delete_port", "x", port="out"),
                )
            ],
        )
        # Existing conn:base still uses x.out, so the whole transaction is held.
        self.assertIn("precondition_failed", conflict_kinds(result))
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 0)
        self.assertIn("out", result.state["things"]["x"]["ports"])

    def test_boundary_redo_is_new_edit_not_global_time_rewind(self):
        result = materialize(
            base_state(),
            [
                tx("tx:set", "alice", op("set_property", "x", key="left", value=1)),
                tx("tx:remote", "bob", op("set_property", "x", key="right", value=7)),
                tx("tx:undo", "alice", op("set_property", "x", key="left", value=0, expected=1), deps=("tx:set", "tx:remote"), inverse_of="tx:set"),
                tx("tx:redo", "alice", op("set_property", "x", key="left", value=1, expected=0), deps=("tx:undo",)),
            ],
        )
        self.assertEqual(result.state["things"]["x"]["props"]["left"], 1)
        self.assertEqual(result.state["things"]["x"]["props"]["right"], 7)

    def test_boundary_every_arrival_permutation_converges_to_same_semantic_snapshot(self):
        items = [
            tx("tx:a", "alice", op("set_property", "x", key="title", value="A")),
            tx("tx:b", "bob", op("set_property", "x", key="title", value="B")),
            tx("tx:c", "carol", op("set_property", "x", key="right", value=3)),
        ]
        snapshots = []
        for order in itertools.permutations(items):
            replica = Replica("r", base_state())
            for item in order:
                replica.author(item)
            snapshots.append(replica.persisted_snapshot())
        self.assertTrue(all(item == snapshots[0] for item in snapshots[1:]))

    def test_boundary_causal_cycle_is_rejected(self):
        with self.assertRaises(CausalCycle):
            materialize(
                base_state(),
                [
                    tx("tx:a", "alice", op("set_property", "x", key="left", value=1), deps=("tx:b",)),
                    tx("tx:b", "bob", op("set_property", "x", key="right", value=2), deps=("tx:a",)),
                ],
            )

    def test_boundary_scale_256_offline_edits_has_deterministic_linear_wire_footprint(self):
        left, right, relay = two_replicas()
        left.disconnect()
        for index in range(256):
            left.author(
                tx(
                    f"tx:{index:03d}",
                    "alice",
                    op("set_property", "x", key=f"offline_{index:03d}", value=index),
                )
            )
        left.reconnect()
        synchronize(relay, [left, right])
        self.assertTrue(equivalent([left, right]))
        self.assertEqual(len(relay.ids()), 256)
        self.assertEqual(relay.encoded_bytes, left.history_bytes)
        self.assertGreater(relay.encoded_bytes, 0)
        self.assertLess(relay.encoded_bytes, 256 * 1024)

    def test_boundary_materialized_documents_validate_after_each_required_conflict_family(self):
        scenarios = [
            [tx("a", "alice", op("set_property", "x", key="left", value=1))],
            [tx("a", "alice", op("delete_thing", "x")), tx("b", "bob", op("set_property", "x", key="title", value="b"))],
            [tx("a", "alice", op("group", "g1", members=["a", "b"])), tx("b", "bob", op("group", "g2", members=["b", "c"]))],
            [tx("a", "alice", op("asset_replace", "asset:music", bundle=asset_bundle("A"))), tx("b", "bob", op("asset_replace", "asset:music", bundle=asset_bundle("B")))],
        ]
        for transactions in scenarios:
            result = materialize(base_state(), transactions)
            validate_document(result.state)


if __name__ == "__main__":
    unittest.main()
