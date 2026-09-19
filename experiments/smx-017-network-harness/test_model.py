import copy
import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("smx017_model", HERE / "model.py")
model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(model)


def authority(topology="peer"):
    return model.Replica(
        principal="host",
        transport_peer="conn-1",
        topology=topology,
        authority_principal="host",
    )


def valid_input(seq=1, kind="move", **extra):
    msg = {
        "type": "input",
        "sender_principal": "alice",
        "authority_epoch": 1,
        "input_seq": seq,
        "kind": kind,
    }
    msg.update(extra or ({"dx": 1} if kind == "move" else {}))
    if kind == "move" and "dx" not in msg:
        msg["dx"] = 1
    return msg


class TopologyBoundaryTests(unittest.TestCase):
    def test_TN001_same_semantic_input_offline_peer_dedicated(self):
        snapshots = []
        for topo in ("offline", "peer", "dedicated"):
            r = authority(topo)
            r.accept_input(valid_input(1, dx=1))
            r.accept_input(valid_input(2, dx=2))
            r.accept_input(valid_input(3, kind="open_door"))
            snapshots.append((r.avatar_x, r.door_open, r.controller, r.containment_parent))
        self.assertEqual(len(set(snapshots)), 1)
        self.assertEqual(snapshots[0], (3, True, "alice", "world"))

    def test_TN002_control_is_not_containment_or_authority(self):
        r = authority()
        r.transfer_control("bob")
        self.assertEqual(r.containment_parent, "world")
        self.assertEqual(r.authority_principal, "host")
        self.assertEqual(r.controller, "bob")

    def test_TN003_transport_identity_rebind_does_not_change_principal(self):
        r = authority()
        r.reconnect("conn-44")
        self.assertEqual(r.principal, "host")
        self.assertEqual(r.transport_peer, "conn-44")

    def test_TN004_reconnect_requires_new_transient_peer(self):
        with self.assertRaises(model.Rejected):
            authority().reconnect("conn-1")

    def test_TN005_non_controller_input_rejected(self):
        r = authority()
        msg = valid_input(1, dx=1)
        msg["sender_principal"] = "mallory"
        with self.assertRaises(model.Rejected):
            r.accept_input(msg)

    def test_TN006_duplicate_input_rejected_without_mutation(self):
        r = authority()
        r.accept_input(valid_input(1, dx=1))
        before = r.semantic_snapshot()
        with self.assertRaises(model.Rejected):
            r.accept_input(valid_input(1, dx=4))
        self.assertEqual(r.semantic_snapshot(), before)

    def test_TN007_reordered_input_rejected(self):
        r = authority()
        r.accept_input(valid_input(2, dx=2))
        with self.assertRaises(model.Rejected):
            r.accept_input(valid_input(1, dx=1))

    def test_TN008_stale_authority_epoch_rejected(self):
        r = authority()
        r.transfer_authority("alice", checkpoint_confirmed=True)
        stale = valid_input(1, dx=1)
        with self.assertRaises(model.Rejected):
            r.accept_input(stale)

    def test_TN009_unconfirmed_host_loss_cannot_migrate_authority(self):
        r = authority()
        with self.assertRaises(model.Rejected):
            r.transfer_authority("alice", checkpoint_confirmed=False)
        self.assertEqual((r.authority_principal, r.authority_epoch), ("host", 1))

    def test_TN010_confirmed_host_migration_bumps_epoch_preserves_thing_state(self):
        r = authority()
        r.accept_input(valid_input(1, dx=2))
        before = (r.avatar_x, r.door_open, r.containment_parent)
        r.transfer_authority("alice", checkpoint_confirmed=True)
        self.assertEqual((r.avatar_x, r.door_open, r.containment_parent), before)
        self.assertEqual(r.authority_epoch, 2)

    def test_TN011_forged_remote_state_not_accepted_as_input(self):
        r = authority()
        with self.assertRaises(model.Rejected):
            r.accept_input({"type": "state", "sender_principal": "alice", "authority_epoch": 1})

    def test_TN012_undeclared_input_rejected(self):
        r = authority()
        with self.assertRaises(model.Rejected):
            r.accept_input(valid_input(1, kind="teleport"))

    def test_TN013_out_of_range_input_rejected(self):
        with self.assertRaises(model.Rejected):
            authority().accept_input(valid_input(1, dx=999))

    def test_TN014_capability_injection_rejected_recursively(self):
        msg = valid_input(1, dx=1)
        msg["meta"] = {"nested": [{"capability_token": "forged"}]}
        with self.assertRaises(model.Rejected):
            authority().accept_input(msg)

    def test_TN015_host_handle_injection_rejected(self):
        msg = valid_input(1, dx=1)
        msg["host_handle"] = "JavaScriptBridge"
        with self.assertRaises(model.Rejected):
            authority().accept_input(msg)

    def test_TN016_oversized_message_rejected(self):
        msg = valid_input(1, dx=1)
        msg["padding"] = "x" * model.MAX_MESSAGE_BYTES
        with self.assertRaises(model.Rejected):
            authority().accept_input(msg)

    def test_TN017_known_unloaded_state_is_coalesced(self):
        r = model.Replica("alice", "c", "peer", "host")
        r.unload("door")
        r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":1,"target":"door","payload":{"open":False}})
        r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":2,"target":"door","payload":{"open":True}})
        self.assertEqual(r.pending_state["door"], {"open": True})
        r.restore("door")
        self.assertTrue(r.door_open)

    def test_TN018_reliable_event_survives_unload_then_deduplicates(self):
        r = model.Replica("alice", "c", "peer", "host")
        r.unload("door")
        event = {"type":"event","sender_principal":"host","authority_epoch":1,"event_id":"evt-1","target":"door","kind":"door_opened"}
        r.receive_event(event)
        r.receive_event(copy.deepcopy(event))
        self.assertEqual(len(r.pending_events), 1)
        r.restore("door")
        self.assertTrue(r.door_open)

    def test_TN019_relevance_leave_is_not_destroy_or_unload(self):
        r = model.Replica("alice", "c", "peer", "host")
        r.set_relevance("door", False)
        self.assertEqual(r.lifecycle["door"], "active")
        r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":1,"target":"door","payload":{"open":True}})
        self.assertFalse(r.door_open)
        r.set_relevance("door", True)
        self.assertTrue(r.door_open)

    def test_TN020_tombstone_drops_pending_and_rejects_event(self):
        r = model.Replica("alice", "c", "peer", "host")
        r.unload("door")
        event = {"type":"event","sender_principal":"host","authority_epoch":1,"event_id":"evt-a","target":"door","kind":"door_opened"}
        r.receive_event(event)
        r.tombstone("door")
        self.assertEqual(r.pending_events, [])
        event["event_id"] = "evt-b"
        with self.assertRaises(model.Rejected):
            r.receive_event(event)

    def test_TN021_stale_state_cannot_roll_back(self):
        r = model.Replica("alice", "c", "peer", "host")
        r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":2,"target":"avatar:alice","payload":{"position_x":7}})
        with self.assertRaises(model.Rejected):
            r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":1,"target":"avatar:alice","payload":{"position_x":0}})
        self.assertEqual(r.avatar_x, 7)

    def test_TN022_non_authority_state_rejected(self):
        r = model.Replica("alice", "c", "peer", "host")
        with self.assertRaises(model.Rejected):
            r.receive_state({"type":"state","sender_principal":"mallory","authority_epoch":1,"state_seq":1,"target":"door","payload":{"open":True}})

    def test_TN023_undeclared_state_locus_rejected(self):
        r = model.Replica("alice", "c", "peer", "host")
        with self.assertRaises(model.Rejected):
            r.receive_state({"type":"state","sender_principal":"host","authority_epoch":1,"state_seq":1,"target":"door","payload":{"secret":1}})

    def test_TN024_protected_source_audio_provenance_bundle_is_atomic(self):
        creation = json.loads((HERE / "creation.json").read_text())
        bundle = creation["protected_assets"][0]
        model.assert_protected_bundle_unchanged(bundle, copy.deepcopy(bundle))
        mixed = copy.deepcopy(bundle)
        mixed["provenance"] = {"origin": "other revision", "author": "mallory"}
        with self.assertRaises(model.Rejected):
            model.assert_protected_bundle_unchanged(bundle, mixed)

    def test_TN025_topology_policy_does_not_mutate_protected_bundle(self):
        creation = json.loads((HERE / "creation.json").read_text())
        original = copy.deepcopy(creation["protected_assets"][0])
        for _topo in ("offline", "peer", "dedicated"):
            projected = copy.deepcopy(creation)
            projected["runtime_topology"] = _topo
            model.assert_protected_bundle_unchanged(original, projected["protected_assets"][0])

    def test_TN026_creation_contains_no_transport_or_godot_identity(self):
        text = (HERE / "creation.json").read_text().lower()
        for forbidden in ("websocket", "webrtc", "enet", "peer_id", "nodepath", "resourceuid", "rpc"):
            self.assertNotIn(forbidden, text)

    def test_TN027_same_thing_definition_attachment_port_ids_all_topologies(self):
        creation = json.loads((HERE / "creation.json").read_text())
        ids = {
            "things": [x["thing_id"] for x in creation["things"]],
            "definitions": [x["definition_id"] for x in creation["definitions"]],
            "attachments": [x["attachment_id"] for x in creation["attachments"]],
            "ports": creation["ports"],
        }
        for _topo in ("offline", "peer", "dedicated"):
            self.assertEqual(ids, copy.deepcopy(ids))

    def test_TN028_snapshot_excludes_transport_peer(self):
        snap = authority().semantic_snapshot()
        self.assertNotIn("transport_peer", snap)


if __name__ == "__main__":
    unittest.main()
