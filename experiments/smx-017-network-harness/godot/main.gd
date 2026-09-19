extends Node

# Trusted SMX-017 integration harness.  This script is substrate/test code, not
# SplashMX user IR and not a public wire protocol.
const EXPECTED_CREATION_SHA256 := "dd5e7bb8b33ab447b4234fb8036453b248c5721e22b9f0e1c19cc57438e71580"
const MAX_PACKET_BYTES := 8192
const FORBIDDEN_KEYS := [
	"capability_grant", "capability_token", "host_handle", "godot_node",
	"node_path", "resource_uid", "socket"
]

var cfg := {
	"topology": "offline",
	"role": "client",
	"principal": "alice",
	"room": "smx017",
	"ws_url": "ws://127.0.0.1:8877",
	"no_checkpoint": "0",
	"no_reconnect": "0"
}
var creation: Dictionary = {}
var creation_sha256 := ""
var socket := WebSocketPeer.new()
var socket_started := false
var socket_open := false
var registered := false
var transport_peer_id := "local"
var previous_transport_peer_id := ""
var reconnect_count := 0
var reconnect_after_ms := 0
var authority_principal := "local"
var authority_epoch := 1
var is_authority := false
var controller := "alice"
var containment_parent := "world"
var avatar_x := 0
var door_open := false
var state_seq := 0
var last_remote_state_seq := 0
var input_watermark := 0
var seen_events := {}
var lifecycle := {"avatar:alice": "active", "door": "active"}
var relevance := {"avatar:alice": true, "door": true}
var pending_state := {}
var pending_events: Array = []
var scenario_start_ms := 0
var scenario_flags := {}
var last_heartbeat_ms := 0
var last_checkpoint_ms := 0
var last_snapshot_ms := 0
var control_transfer_done := false


func _ready() -> void:
	_parse_config()
	if not _load_creation():
		get_tree().quit(2)
		return
	_emit("boot", {
		"topology": cfg.topology,
		"role": cfg.role,
		"principal": cfg.principal,
		"creation_revision_id": creation.get("creation_revision_id", ""),
		"creation_sha256": creation_sha256,
		"thing_ids": _ids("things", "thing_id"),
		"definition_ids": _ids("definitions", "definition_id"),
		"attachment_ids": _ids("attachments", "attachment_id"),
		"ports": creation.get("ports", []),
		"protected_assets": creation.get("protected_assets", [])
	})
	if cfg.topology == "offline":
		authority_principal = "local"
		is_authority = true
		_run_offline_scenario()
		return
	_start_socket()


func _process(_delta: float) -> void:
	if cfg.topology == "offline":
		return
	var now := Time.get_ticks_msec()
	if socket_started:
		socket.poll()
		var ready := socket.get_ready_state()
		if ready == WebSocketPeer.STATE_OPEN:
			if not socket_open:
				socket_open = true
				_emit("socket_open", {"reconnect_count": reconnect_count})
			while socket.get_available_packet_count() > 0:
				var packet := socket.get_packet()
				if packet.size() > MAX_PACKET_BYTES:
					_emit("reject", {"reason": "oversized_ingress", "bytes": packet.size()})
					continue
				_handle_wire_text(packet.get_string_from_utf8())
		elif ready == WebSocketPeer.STATE_CLOSED:
			if socket_open or registered:
				_emit("socket_closed", {
					"code": socket.get_close_code(),
					"reason": socket.get_close_reason(),
					"transport_peer_id": transport_peer_id
				})
				socket_open = false
				registered = false
				socket_started = false
				if cfg.no_reconnect != "1":
					reconnect_after_ms = now + 250
	if not socket_started and reconnect_after_ms > 0 and now >= reconnect_after_ms:
		reconnect_count += 1
		reconnect_after_ms = 0
		_start_socket()
	if socket_open and now - last_heartbeat_ms >= 200:
		last_heartbeat_ms = now
		_send_raw({"type": "heartbeat", "client_ticks_ms": now})
	if registered and not is_authority and scenario_start_ms > 0:
		_drive_client_scenario(now - scenario_start_ms)
	if registered and is_authority and cfg.no_checkpoint != "1":
		if now - last_checkpoint_ms >= 1000:
			_send_checkpoint()
	if now - last_snapshot_ms >= 1000:
		last_snapshot_ms = now
		_emit_snapshot("periodic")


func _parse_config() -> void:
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--smx-"):
			continue
		var bits := arg.trim_prefix("--smx-").split("=", true, 1)
		if bits.size() == 2 and cfg.has(bits[0]):
			cfg[bits[0]] = bits[1]
	if OS.has_feature("web"):
		# Trusted harness instrumentation only.  User content never receives
		# JavaScriptBridge or host authority through this route.
		var raw_query = JavaScriptBridge.eval("window.location.search", true)
		if typeof(raw_query) == TYPE_STRING:
			var query := String(raw_query).trim_prefix("?")
			for item in query.split("&"):
				var pair := item.split("=", true, 1)
				if pair.size() != 2:
					continue
				var key := pair[0].trim_prefix("smx_")
				if cfg.has(key):
					cfg[key] = pair[1].uri_decode()


func _load_creation() -> bool:
	var bytes := FileAccess.get_file_as_bytes("res://creation.json")
	if bytes.is_empty():
		_emit("fatal", {"reason": "creation_missing"})
		return false
	var hash := HashingContext.new()
	if hash.start(HashingContext.HASH_SHA256) != OK:
		_emit("fatal", {"reason": "hash_start_failed"})
		return false
	if hash.update(bytes) != OK:
		_emit("fatal", {"reason": "hash_update_failed"})
		return false
	creation_sha256 = hash.finish().hex_encode()
	if creation_sha256 != EXPECTED_CREATION_SHA256:
		_emit("fatal", {"reason": "creation_digest_mismatch", "actual": creation_sha256})
		return false
	var parsed = JSON.parse_string(bytes.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		_emit("fatal", {"reason": "creation_parse_failed"})
		return false
	creation = parsed
	if creation.get("creation_revision_id", "") != "smx017-topology-equivalence-v1":
		_emit("fatal", {"reason": "creation_revision_mismatch"})
		return false
	return true


func _start_socket() -> void:
	socket = WebSocketPeer.new()
	socket.inbound_buffer_size = 32768
	socket.outbound_buffer_size = 32768
	var url := "%s/?room=%s&role=%s&principal=%s&topology=%s" % [
		cfg.ws_url, cfg.room, cfg.role, cfg.principal, cfg.topology
	]
	var err := socket.connect_to_url(url)
	if err != OK:
		_emit("socket_connect_error", {"error": err, "url": url})
		reconnect_after_ms = Time.get_ticks_msec() + 500
		return
	socket_started = true


func _handle_wire_text(text: String) -> void:
	var message = JSON.parse_string(text)
	if typeof(message) != TYPE_DICTIONARY:
		_emit("reject", {"reason": "malformed_json"})
		return
	if _contains_forbidden(message):
		_emit("reject", {"reason": "forbidden_host_authority_key"})
		return
	var kind := String(message.get("type", ""))
	if kind == "welcome":
		previous_transport_peer_id = transport_peer_id
		transport_peer_id = String(message.get("conn_id", ""))
		authority_principal = String(message.get("authority_principal", ""))
		authority_epoch = int(message.get("authority_epoch", 1))
		is_authority = authority_principal == String(cfg.principal)
		registered = true
		if reconnect_count > 0:
			_emit("reconnected", {
				"previous_transport_peer_id": previous_transport_peer_id,
				"transport_peer_id": transport_peer_id,
				"principal": cfg.principal,
				"authority_epoch": authority_epoch
			})
		else:
			_emit("welcome", {
				"transport_peer_id": transport_peer_id,
				"principal": cfg.principal,
				"authority_principal": authority_principal,
				"authority_epoch": authority_epoch
			})
		if is_authority:
			if cfg.no_checkpoint != "1":
				_send_checkpoint()
		else:
			scenario_start_ms = Time.get_ticks_msec()
		return
	if kind == "authority_granted":
		var new_epoch := int(message.get("authority_epoch", 0))
		if new_epoch <= authority_epoch:
			_emit("reject", {"reason": "non_monotonic_authority_grant", "epoch": new_epoch})
			return
		authority_epoch = new_epoch
		authority_principal = String(cfg.principal)
		is_authority = true
		var checkpoint = message.get("checkpoint", {})
		if typeof(checkpoint) == TYPE_DICTIONARY and not checkpoint.is_empty():
			_apply_checkpoint(checkpoint)
		_emit("authority_granted", {
			"principal": cfg.principal,
			"authority_epoch": authority_epoch,
			"checkpoint_confirmed": not checkpoint.is_empty()
		})
		_send_checkpoint()
		return
	if kind == "authority_unavailable":
		is_authority = false
		_emit("authority_unavailable", {
			"reason": message.get("reason", "unknown"),
			"authority_epoch": authority_epoch,
			"topology": cfg.topology
		})
		return
	if kind == "message":
		var payload = message.get("payload", {})
		if typeof(payload) != TYPE_DICTIONARY:
			_emit("reject", {"reason": "payload_not_dictionary"})
			return
		_handle_payload(
			payload,
			String(message.get("sender_principal", "")),
			String(message.get("sender_conn_id", "")),
			String(message.get("sender_role", ""))
		)
		return
	_emit("reject", {"reason": "unknown_relay_message", "type": kind})


func _handle_payload(payload: Dictionary, sender_principal: String, sender_conn_id: String, sender_role: String) -> void:
	if _contains_forbidden(payload):
		_emit("reject", {"reason": "forbidden_host_authority_key", "sender": sender_principal})
		return
	var kind := String(payload.get("type", ""))
	if kind == "input":
		if not is_authority:
			_emit("reject", {"reason": "input_received_by_non_authority"})
			return
		_handle_input(payload, sender_principal, sender_conn_id)
		return
	if kind == "state":
		if is_authority:
			_emit("reject", {"reason": "remote_state_assertion", "sender": sender_principal})
			return
		_handle_state(payload, sender_principal)
		return
	if kind == "event":
		if is_authority:
			_emit("reject", {"reason": "remote_event_assertion", "sender": sender_principal})
			return
		_handle_event(payload, sender_principal)
		return
	if kind == "checkpoint":
		if sender_principal != authority_principal or int(payload.get("authority_epoch", -1)) != authority_epoch:
			_emit("reject", {"reason": "checkpoint_not_from_current_authority", "sender": sender_principal})
			return
		_apply_checkpoint(payload)
		_emit("checkpoint_applied", {"state_seq": state_seq, "authority_epoch": authority_epoch})
		return
	if kind == "baseline_request":
		if is_authority and sender_role == "relay":
			_send_checkpoint()
		return
	_emit("reject", {"reason": "undeclared_payload_type", "type": kind})


func _handle_input(payload: Dictionary, sender_principal: String, sender_conn_id: String) -> void:
	if sender_principal != controller:
		_emit("reject", {"reason": "non_controller_input", "sender": sender_principal})
		return
	if int(payload.get("authority_epoch", -1)) != authority_epoch:
		_emit("reject", {"reason": "stale_authority_epoch", "sender": sender_principal})
		return
	var kind := String(payload.get("kind", ""))
	if kind != "move" and kind != "open_door":
		_emit("reject", {"reason": "undeclared_input", "kind": kind})
		return
	var seq := int(payload.get("input_seq", -1))
	if seq <= input_watermark:
		_emit("reject", {"reason": "duplicate_or_reordered_input", "input_seq": seq})
		return
	if kind == "move":
		var dx := int(payload.get("dx", 0))
		if abs(dx) > 4:
			_emit("reject", {"reason": "input_out_of_bounds", "dx": dx})
			return
		input_watermark = seq
		avatar_x += dx
		state_seq += 1
		_send_payload({
			"type": "state", "target": "avatar:alice", "state_seq": state_seq,
			"authority_epoch": authority_epoch, "payload": {"position_x": avatar_x},
			"authority_principal": cfg.principal
		})
	else:
		input_watermark = seq
		door_open = true
		state_seq += 1
		_send_payload({
			"type": "state", "target": "door", "state_seq": state_seq,
			"authority_epoch": authority_epoch, "payload": {"open": true},
			"authority_principal": cfg.principal
		})
		_send_payload({
			"type": "event", "target": "door", "kind": "door_opened",
			"event_id": "door-open:%d:%d" % [authority_epoch, seq],
			"authority_epoch": authority_epoch,
			"authority_principal": cfg.principal
		})
	_emit("input_accepted", {
		"kind": kind, "input_seq": seq, "sender_principal": sender_principal,
		"sender_conn_id": sender_conn_id, "state_seq": state_seq
	})
	if seq >= 4 and not control_transfer_done:
		control_transfer_done = true
		var before_authority := authority_principal
		var before_parent := containment_parent
		controller = "bob"
		_emit("control_transfer", {
			"controller": controller, "authority_principal": authority_principal,
			"containment_parent": containment_parent,
			"authority_unchanged": before_authority == authority_principal,
			"containment_unchanged": before_parent == containment_parent
		})
		controller = "alice"
		_emit("control_transfer", {
			"controller": controller, "authority_principal": authority_principal,
			"containment_parent": containment_parent,
			"authority_unchanged": before_authority == authority_principal,
			"containment_unchanged": before_parent == containment_parent
		})
	if cfg.no_checkpoint != "1" and seq >= 3:
		_send_checkpoint()
	_emit_snapshot("after_input")


func _handle_state(payload: Dictionary, sender_principal: String) -> void:
	if sender_principal != authority_principal:
		_emit("reject", {"reason": "state_not_from_authority", "sender": sender_principal})
		return
	if int(payload.get("authority_epoch", -1)) != authority_epoch:
		_emit("reject", {"reason": "stale_authority_state", "sender": sender_principal})
		return
	var seq := int(payload.get("state_seq", -1))
	if seq <= last_remote_state_seq:
		_emit("reject", {"reason": "stale_state_seq", "state_seq": seq, "watermark": last_remote_state_seq})
		return
	last_remote_state_seq = seq
	var target := String(payload.get("target", ""))
	var state_payload = payload.get("payload", {})
	if target != "avatar:alice" and target != "door":
		_emit("reject", {"reason": "undeclared_state_target", "target": target})
		return
	if typeof(state_payload) != TYPE_DICTIONARY:
		_emit("reject", {"reason": "state_payload_not_dictionary"})
		return
	if lifecycle.get(target, "unknown") == "known_unloaded" or not relevance.get(target, false):
		pending_state[target] = state_payload.duplicate(true)
		_emit("state_coalesced", {"target": target, "state_seq": seq})
		return
	if not _apply_state(target, state_payload):
		return
	_emit("state_applied", {"target": target, "state_seq": seq})


func _handle_event(payload: Dictionary, sender_principal: String) -> void:
	if sender_principal != authority_principal or int(payload.get("authority_epoch", -1)) != authority_epoch:
		_emit("reject", {"reason": "event_not_from_authority", "sender": sender_principal})
		return
	var event_id := String(payload.get("event_id", ""))
	if event_id == "":
		_emit("reject", {"reason": "event_missing_id"})
		return
	if seen_events.has(event_id):
		_emit("event_deduplicated", {"event_id": event_id})
		return
	seen_events[event_id] = true
	var target := String(payload.get("target", ""))
	if target != "door" or String(payload.get("kind", "")) != "door_opened":
		_emit("reject", {"reason": "undeclared_event"})
		return
	if lifecycle.door == "known_unloaded" or not relevance.door:
		pending_events.append(payload.duplicate(true))
		_emit("event_queued", {"event_id": event_id, "target": target})
		return
	door_open = true
	_emit("event_applied", {"event_id": event_id, "target": target})


func _drive_client_scenario(elapsed_ms: int) -> void:
	if elapsed_ms >= 300 and not scenario_flags.has("move1"):
		scenario_flags.move1 = true
		_send_input(1, "move", {"dx": 1})
	if elapsed_ms >= 430 and not scenario_flags.has("duplicate"):
		scenario_flags.duplicate = true
		_send_input(1, "move", {"dx": 4})
	if elapsed_ms >= 550 and not scenario_flags.has("move2"):
		scenario_flags.move2 = true
		_send_input(2, "move", {"dx": 2})
	if elapsed_ms >= 680 and not scenario_flags.has("unload"):
		scenario_flags.unload = true
		lifecycle.door = "known_unloaded"
		_emit("lifecycle", {"thing_id": "door", "state": "known_unloaded"})
		_send_input(3, "open_door", {})
	if elapsed_ms >= 820 and not scenario_flags.has("undeclared"):
		scenario_flags.undeclared = true
		_send_input(5, "teleport", {"dx": 1})
	if elapsed_ms >= 940 and not scenario_flags.has("forbidden"):
		scenario_flags.forbidden = true
		_send_payload({
			"type": "input", "authority_epoch": authority_epoch, "input_seq": 5,
			"kind": "move", "dx": 1,
			"meta": {"nested": [{"capability_token": "forged"}]}
		})
	if elapsed_ms >= 1060 and not scenario_flags.has("forged_state"):
		scenario_flags.forged_state = true
		_send_payload({
			"type": "state", "target": "avatar:alice", "state_seq": 999,
			"authority_epoch": authority_epoch, "payload": {"position_x": 999}
		})
	if elapsed_ms >= 1180 and not scenario_flags.has("oversized"):
		scenario_flags.oversized = true
		_send_payload({
			"type": "input", "authority_epoch": authority_epoch, "input_seq": 5,
			"kind": "move", "dx": 1, "padding": "x".repeat(MAX_PACKET_BYTES + 512)
		})
	if elapsed_ms >= 1320 and not scenario_flags.has("irrelevant"):
		scenario_flags.irrelevant = true
		relevance["avatar:alice"] = false
		_emit("relevance", {"thing_id": "avatar:alice", "relevant": false, "lifecycle": lifecycle["avatar:alice"]})
		_send_input(4, "move", {"dx": 1})
	if elapsed_ms >= 1600 and not scenario_flags.has("restore"):
		scenario_flags.restore = true
		lifecycle.door = "active"
		_flush_pending("door")
		_emit("lifecycle", {"thing_id": "door", "state": "active", "door_open": door_open})
	if elapsed_ms >= 1750 and not scenario_flags.has("relevant"):
		scenario_flags.relevant = true
		relevance["avatar:alice"] = true
		_flush_pending("avatar:alice")
		_emit("relevance", {"thing_id": "avatar:alice", "relevant": true, "lifecycle": lifecycle["avatar:alice"], "avatar_x": avatar_x})
	if elapsed_ms >= 2000 and not scenario_flags.has("complete"):
		scenario_flags.complete = true
		_emit_snapshot("client_scenario_complete")


func _run_offline_scenario() -> void:
	var accepted := [
		{"seq": 1, "kind": "move", "dx": 1},
		{"seq": 2, "kind": "move", "dx": 2},
		{"seq": 3, "kind": "open_door"},
		{"seq": 4, "kind": "move", "dx": 1}
	]
	for item in accepted:
		if item.kind == "move":
			avatar_x += int(item.dx)
		else:
			door_open = true
		input_watermark = int(item.seq)
		state_seq += 1
	var before_authority := authority_principal
	var before_parent := containment_parent
	controller = "bob"
	_emit("control_transfer", {
		"controller": controller, "authority_principal": authority_principal,
		"containment_parent": containment_parent,
		"authority_unchanged": before_authority == authority_principal,
		"containment_unchanged": before_parent == containment_parent
	})
	controller = "alice"
	_emit_snapshot("offline_complete")
	call_deferred("_quit_offline")


func _quit_offline() -> void:
	get_tree().quit(0)


func _send_input(seq: int, kind: String, extra: Dictionary) -> void:
	var payload := {
		"type": "input", "authority_epoch": authority_epoch,
		"input_seq": seq, "kind": kind
	}
	for key in extra:
		payload[key] = extra[key]
	if kind == "move":
		var predicted := avatar_x + int(payload.get("dx", 0))
		_emit("prediction", {"input_seq": seq, "predicted_avatar_x": predicted, "authoritative_avatar_x": avatar_x})
	_send_payload(payload)


func _send_checkpoint() -> void:
	if not is_authority or not socket_open:
		return
	last_checkpoint_ms = Time.get_ticks_msec()
	_send_payload({
		"type": "checkpoint",
		"authority_epoch": authority_epoch,
		"state_seq": state_seq,
		"input_watermark": input_watermark,
		"avatar_x": avatar_x,
		"door_open": door_open,
		"controller": controller,
		"containment_parent": containment_parent,
		"lifecycle": lifecycle.duplicate(true)
	})
	_emit("checkpoint_sent", {"state_seq": state_seq, "authority_epoch": authority_epoch})


func _apply_checkpoint(checkpoint: Dictionary) -> void:
	avatar_x = int(checkpoint.get("avatar_x", avatar_x))
	door_open = bool(checkpoint.get("door_open", door_open))
	state_seq = maxi(state_seq, int(checkpoint.get("state_seq", state_seq)))
	last_remote_state_seq = maxi(last_remote_state_seq, state_seq)
	input_watermark = maxi(input_watermark, int(checkpoint.get("input_watermark", input_watermark)))
	controller = String(checkpoint.get("controller", controller))
	containment_parent = String(checkpoint.get("containment_parent", containment_parent))


func _apply_state(target: String, payload: Dictionary) -> bool:
	if target == "avatar:alice":
		if payload.size() != 1 or not payload.has("position_x"):
			_emit("reject", {"reason": "undeclared_state_locus", "target": target})
			return false
		avatar_x = int(payload.position_x)
		return true
	if target == "door":
		if payload.size() != 1 or not payload.has("open"):
			_emit("reject", {"reason": "undeclared_state_locus", "target": target})
			return false
		door_open = bool(payload.open)
		return true
	return false


func _flush_pending(target: String) -> void:
	if pending_state.has(target):
		_apply_state(target, pending_state[target])
		pending_state.erase(target)
	var keep: Array = []
	for event in pending_events:
		if String(event.get("target", "")) == target:
			if target == "door" and String(event.get("kind", "")) == "door_opened":
				door_open = true
				emit_signal_if_possible(event)
		else:
			keep.append(event)
	pending_events = keep


func emit_signal_if_possible(event: Dictionary) -> void:
	_emit("event_flushed", {"event_id": event.get("event_id", ""), "target": event.get("target", "")})


func _send_payload(payload: Dictionary) -> void:
	_send_raw({"type": "payload", "payload": payload})


func _send_raw(message: Dictionary) -> void:
	if not socket_open:
		_emit("send_skipped", {"reason": "socket_not_open", "type": message.get("type", "")})
		return
	var text := JSON.stringify(message)
	var err := socket.send_text(text)
	if err != OK:
		_emit("send_error", {"error": err, "type": message.get("type", "")})


func _contains_forbidden(value) -> bool:
	if typeof(value) == TYPE_DICTIONARY:
		for key in value:
			if String(key) in FORBIDDEN_KEYS:
				return true
			if _contains_forbidden(value[key]):
				return true
	elif typeof(value) == TYPE_ARRAY:
		for item in value:
			if _contains_forbidden(item):
				return true
	return false


func _emit_snapshot(reason: String) -> void:
	_emit("snapshot", {
		"reason": reason,
		"topology": cfg.topology,
		"principal": cfg.principal,
		"transport_peer_id": transport_peer_id,
		"authority_principal": authority_principal,
		"authority_epoch": authority_epoch,
		"controller": controller,
		"containment_parent": containment_parent,
		"avatar_x": avatar_x,
		"door_open": door_open,
		"state_seq": state_seq,
		"input_watermark": input_watermark,
		"lifecycle": lifecycle.duplicate(true),
		"relevance": relevance.duplicate(true),
		"creation_revision_id": creation.get("creation_revision_id", ""),
		"creation_sha256": creation_sha256,
		"protected_assets": creation.get("protected_assets", [])
	})


func _emit(event: String, fields: Dictionary) -> void:
	var record := fields.duplicate(true)
	record["event"] = event
	record["ticks_ms"] = Time.get_ticks_msec()
	record["wall_ms"] = int(Time.get_unix_time_from_system() * 1000.0)
	print("SMX017 " + JSON.stringify(record))


func _ids(array_name: String, id_key: String) -> Array:
	var result: Array = []
	for item in creation.get(array_name, []):
		if typeof(item) == TYPE_DICTIONARY:
			result.append(item.get(id_key, ""))
	return result
