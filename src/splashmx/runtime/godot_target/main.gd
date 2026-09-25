extends Node

const FORBIDDEN_KEYS = [
    "NodePath", "RID", "ResourceUID", "resource_path", "DOM_node_identity",
    "database_row_id", "cache_key", "url", "transport_peer_id",
    "connection_handle", "socket_id", "session_id", "process_handle",
    "instance_id", "godot_object_id"
]
const MAX_BINDINGS = 100000
const MAX_OBJECTS = 500000
const MAX_DERIVATIVES = 4096
const FRAME_SAMPLES = 30

var _args = {}
var _fixture = {}
var _profile = "native"
var _available = []
var _active_features = []
var _degraded_optional = []
var _binding_root = null
var _bindings = {}
var _asset_revisions = {}
var _derivatives = {}
var _evidence = {}
var _frame_usec = []
var _frames_left = FRAME_SAMPLES
var _output_path = ""
var _startup_usec = 0

# SMX-051C editor-live state. This is a second physical input mode for the same
# generic Godot target, not a second canonical model.
var _editor_live = false
var _live_request = null
var _live_root = null
var _live_bindings = {}
var _live_ready = false
var _live_ticks_per_second = 60.0
var _live_max_tick = 0.0
var _live_elapsed_tick = 0.0
var _live_mid_emitted = false
var _live_end_emitted = false
var _live_project_revision_id = ""
var _live_event_pending = false


func _ready():
    if _editor_live_requested():
        _editor_live = true
        _ready_editor_live()
        return
    var startup_started = Time.get_ticks_usec()
    _args = _parse_args(OS.get_cmdline_user_args())
    _profile = str(_args.get("profile", "browser" if OS.has_feature("web") else "native"))
    _output_path = str(_args.get("output", ""))
    if not ["native", "browser", "headless"].has(_profile):
        _fatal("unknown runtime profile " + _profile)
        return
    _fixture = _load_fixture()
    if _fixture.is_empty():
        return
    if str(_fixture.get("contract", "")) != "splashmx.godot-runtime-fixture/1":
        _fatal("fixture contract mismatch")
        return
    if not _canonical_shape_is_clean(_fixture):
        _fatal("fixture leaked engine/runtime identity")
        return
    if not _unique_thing_ids(_fixture.get("things", [])):
        _fatal("duplicate or missing ThingId")
        return
    if not _prepare_profile():
        return
    if not _load_asset_refs():
        return

    var materialize_started = Time.get_ticks_usec()
    if not _materialize_all():
        return
    var materialize_usec = Time.get_ticks_usec() - materialize_started

    var adapter_started = Time.get_ticks_usec()
    var adapter_results = _exercise_adapters()
    var adapter_usec = Time.get_ticks_usec() - adapter_started
    for key in adapter_results:
        if adapter_results[key] != true:
            _fatal("adapter path failed: " + str(key))
            return

    var scheduler_started = Time.get_ticks_usec()
    var scheduler_trace = _schedule_trace(_fixture.get("scheduler_events", []))
    var reversed_events = _fixture.get("scheduler_events", []).duplicate(true)
    reversed_events.reverse()
    var scheduler_reordered = scheduler_trace == _schedule_trace(reversed_events)
    var scheduler_usec = Time.get_ticks_usec() - scheduler_started
    if not scheduler_reordered:
        _fatal("semantic scheduler trace depends on callback arrival order")
        return

    var churn_started = Time.get_ticks_usec()
    var churn_target = str(_fixture.get("churn_thing_id", "worker"))
    var before_churn = _semantic_binding_view()
    var old_save_fingerprint = str(_fixture.get("worldsave_fingerprint", ""))
    for _i in range(40):
        if not _recreate_binding(churn_target):
            _fatal("binding recreation failed")
            return
    var after_churn = _semantic_binding_view()
    var churn_usec = Time.get_ticks_usec() - churn_started

    var derivative_started = Time.get_ticks_usec()
    var derivative_results = _exercise_derivative_cache()
    var derivative_usec = Time.get_ticks_usec() - derivative_started
    for key in derivative_results:
        if derivative_results[key] != true:
            _fatal("media derivative boundary failed: " + str(key))
            return

    var boundary = _run_boundary_tests(
        scheduler_reordered,
        before_churn == after_churn,
        old_save_fingerprint == str(_fixture.get("worldsave_fingerprint", ""))
    )
    for key in boundary:
        if boundary[key] != true:
            _fatal("boundary test failed: " + str(key))
            return

    _startup_usec = Time.get_ticks_usec() - startup_started
    _evidence = {
        "contract": "splashmx.smx038-godot-profile-evidence/1",
        "profile": _profile,
        "godot_version": Engine.get_version_info().get("string", "unknown"),
        "os": OS.get_name(),
        "architecture": Engine.get_architecture_name(),
        "headless_process": DisplayServer.get_name() == "headless",
        "project_revision_id": _fixture.get("project_revision_id", ""),
        "worldsave_fingerprint": _fixture.get("worldsave_fingerprint", ""),
        "protected_asset_refs": _fixture.get("protected_asset_refs", []).duplicate(true),
        "available_features": _available.duplicate(),
        "active_features": _active_features.duplicate(),
        "degraded_optional_features": _degraded_optional.duplicate(),
        "semantic_binding_view": _semantic_binding_view(),
        "private_engine_binding_count": _private_object_count(),
        "materialize_usec": materialize_usec,
        "binding_churn_40x_usec": churn_usec,
        "scheduler_250x_usec": scheduler_usec,
        "adapter_probe_usec": adapter_usec,
        "derivative_probe_usec": derivative_usec,
        "scheduler_trace": scheduler_trace,
        "adapter_results": adapter_results,
        "derivative_results": derivative_results,
        "boundary_results": boundary,
        "startup_to_ready_usec": _startup_usec,
        "node_count": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
        "object_count": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
        "memory_static_bytes": int(Performance.get_monitor(Performance.MEMORY_STATIC)),
        "frame_measurement_class": "engine-loop evidence on named CI/browser environment; not universal renderer/audio SLO"
    }
    set_process(true)


func _process(delta):
    if _editor_live:
        _process_editor_live(delta)
        return
    if _frames_left <= 0:
        return
    _frame_usec.append(float(delta) * 1000000.0)
    _frames_left -= 1
    if _frames_left == 0:
        _frame_usec.sort()
        _evidence["frame_samples"] = _frame_usec.size()
        _evidence["frame_delta_usec_median"] = _frame_usec[int(_frame_usec.size() / 2)]
        _evidence["frame_delta_usec_max"] = _frame_usec[_frame_usec.size() - 1]
        _evidence["memory_static_bytes_after_frames"] = int(
            Performance.get_monitor(Performance.MEMORY_STATIC)
        )
        _finish()


func _editor_live_requested():
    if not OS.has_feature("web"):
        return false
    var search = str(JavaScriptBridge.eval("window.location.search", true))
    return search.contains("editor_live=1")


func _ready_editor_live():
    _live_request = HTTPRequest.new()
    add_child(_live_request)
    _live_request.request_completed.connect(_on_editor_live_projection)
    var origin = str(JavaScriptBridge.eval("window.location.origin", true))
    if origin == "":
        _fatal("editor-live browser origin is unavailable")
        return
    var error = _live_request.request(origin + "/api/godot-play-projection")
    if error != OK:
        _fatal("editor-live projection request could not start")


func _on_editor_live_projection(_result, response_code, _headers, body):
    if int(response_code) != 200:
        _fatal("editor-live projection request failed with status " + str(response_code))
        return
    var envelope = JSON.parse_string(body.get_string_from_utf8())
    if typeof(envelope) != TYPE_DICTIONARY or envelope.get("ok", false) != true:
        _fatal("editor-live projection response is invalid")
        return
    var projection = envelope.get("projection", {})
    if typeof(projection) != TYPE_DICTIONARY:
        _fatal("editor-live projection is not an object")
        return
    if str(projection.get("contract", "")) != "splashmx.editor-godot-play/1":
        _fatal("editor-live projection contract mismatch")
        return
    if not _canonical_shape_is_clean(projection):
        _fatal("editor-live projection leaked engine/runtime identity")
        return
    var required_features = projection.get("required_features", [])
    if typeof(required_features) != TYPE_ARRAY or not required_features.has("render_2d"):
        _fatal("editor-live projection requires an invalid target feature set")
        return

    _live_project_revision_id = str(projection.get("project_revision_id", ""))
    _live_ticks_per_second = float(projection.get("ticks_per_second", 60))
    if _live_project_revision_id == "" or _live_ticks_per_second <= 0.0:
        _fatal("editor-live projection metadata is invalid")
        return

    _live_root = Node2D.new()
    _live_root.name = "SplashMXEditorPlay"
    add_child(_live_root)
    _live_bindings.clear()
    _live_max_tick = 0.0
    _live_event_pending = false

    var things = projection.get("things", [])
    if typeof(things) != TYPE_ARRAY or things.size() > MAX_BINDINGS:
        _fatal("editor-live Thing collection is invalid or too large")
        return
    var z_order = 0
    for thing in things:
        if typeof(thing) != TYPE_DICTIONARY:
            _fatal("editor-live Thing is invalid")
            return
        var thing_id = str(thing.get("thing_id", ""))
        var visual = thing.get("visual", {})
        var tracks = thing.get("timeline_tracks", [])
        var interactive_events = thing.get("interactive_events", [])
        if thing_id == "" or _live_bindings.has(thing_id):
            _fatal("editor-live Thing identity is empty or duplicated")
            return
        if (
            typeof(visual) != TYPE_DICTIONARY
            or typeof(tracks) != TYPE_ARRAY
            or typeof(interactive_events) != TYPE_ARRAY
        ):
            _fatal("editor-live visual/Timeline/interaction projection is invalid")
            return
        for event_name in interactive_events:
            if str(event_name) != "pointer_click":
                _fatal("editor-live interaction event is unsupported")
                return
        if not interactive_events.is_empty() and not required_features.has("input"):
            _fatal("editor-live interaction projection did not declare input")
            return
        var node = Node2D.new()
        node.set_meta("smx_thing_id", thing_id)
        node.z_index = z_order
        z_order += 1
        var polygon = Polygon2D.new()
        node.add_child(polygon)
        var area = Area2D.new()
        area.input_pickable = interactive_events.has("pointer_click")
        var collision = CollisionPolygon2D.new()
        area.add_child(collision)
        node.add_child(area)
        if interactive_events.has("pointer_click"):
            area.input_event.connect(_on_editor_live_input.bind(thing_id))
        _live_root.add_child(node)
        var binding = {
            "thing_id": thing_id,
            "node": node,
            "polygon": polygon,
            "area": area,
            "collision": collision,
            "interactive_events": interactive_events.duplicate(),
            "base_visual": visual.duplicate(true),
            "timeline_tracks": tracks.duplicate(true),
            "sample_visual": visual.duplicate(true),
        }
        _live_bindings[thing_id] = binding
        for track in tracks:
            for keyframe in track.get("keyframes", []):
                _live_max_tick = max(_live_max_tick, float(keyframe.get("tick", 0)))

    _apply_editor_live_tick(0.0)

    # One transparent viewport-sized Control owns browser pointer capture for the
    # editor-live target. It performs target-private hit testing over the exact
    # materialized visuals, then forwards only semantic pointer_click events.
    var input_surface = Control.new()
    input_surface.name = "SplashMXEditorInputSurface"
    input_surface.position = Vector2.ZERO
    input_surface.size = get_viewport().get_visible_rect().size
    input_surface.mouse_filter = Control.MOUSE_FILTER_STOP
    input_surface.focus_mode = Control.FOCUS_NONE
    input_surface.z_index = 4096
    input_surface.gui_input.connect(_on_editor_live_surface_input)
    _live_root.add_child(input_surface)

    # Ready is an externally observed contract: enable input before announcing it.
    _live_ready = true
    set_process(true)
    _emit_editor_live_ready()
    _emit_editor_live_sample(0.0)


func _shape_polygon(shape, width, height):
    var points = PackedVector2Array()
    var half_w = width / 2.0
    var half_h = height / 2.0
    if str(shape) == "ellipse":
        for index in range(32):
            var angle = TAU * float(index) / 32.0
            points.append(Vector2(cos(angle) * half_w, sin(angle) * half_h))
        return points
    points.append(Vector2(-half_w, -half_h))
    points.append(Vector2(half_w, -half_h))
    points.append(Vector2(half_w, half_h))
    points.append(Vector2(-half_w, half_h))
    return points


func _timeline_value(track, tick):
    var keyframes = track.get("keyframes", [])
    if keyframes.is_empty():
        return null
    if tick <= float(keyframes[0].get("tick", 0)):
        return float(keyframes[0].get("value", 0))
    if tick >= float(keyframes[keyframes.size() - 1].get("tick", 0)):
        return float(keyframes[keyframes.size() - 1].get("value", 0))
    for index in range(1, keyframes.size()):
        var right = keyframes[index]
        var left = keyframes[index - 1]
        var right_tick = float(right.get("tick", 0))
        var left_tick = float(left.get("tick", 0))
        if tick <= right_tick:
            if is_equal_approx(right_tick, left_tick):
                return float(right.get("value", 0))
            var ratio = (tick - left_tick) / (right_tick - left_tick)
            return lerp(float(left.get("value", 0)), float(right.get("value", 0)), ratio)
    return float(keyframes[keyframes.size() - 1].get("value", 0))


func _apply_binding_visual(binding, visual):
    var width = max(12.0, float(visual.get("width", 12)))
    var height = max(12.0, float(visual.get("height", 12)))
    var x = float(visual.get("x", 0))
    var y = float(visual.get("y", 0))
    var node = binding["node"]
    var polygon = binding["polygon"]
    node.position = Vector2(x + width / 2.0, y + height / 2.0)
    node.rotation_degrees = float(visual.get("rotation", 0))
    var points = _shape_polygon(visual.get("shape", "rectangle"), width, height)
    polygon.polygon = points
    binding["collision"].polygon = points
    polygon.color = Color.from_string(str(visual.get("fill", "#5b7cfa")), Color.WHITE)
    binding["sample_visual"] = visual.duplicate(true)


func _apply_editor_live_tick(tick):
    for thing_id in _live_bindings:
        var binding = _live_bindings[thing_id]
        var visual = binding["base_visual"].duplicate(true)
        for track in binding["timeline_tracks"]:
            var property = str(track.get("property", ""))
            if not property.begins_with("visual."):
                continue
            var key = property.substr("visual.".length())
            if not visual.has(key):
                continue
            var value = _timeline_value(track, tick)
            if value != null:
                visual[key] = value
        _apply_binding_visual(binding, visual)


func _on_editor_live_surface_input(event):
    if not _live_ready or _live_event_pending:
        return
    var point = Vector2.ZERO
    if event is InputEventMouseButton:
        if not event.pressed or event.button_index != MOUSE_BUTTON_LEFT:
            return
        point = event.position
    elif event is InputEventScreenTouch:
        if not event.pressed:
            return
        point = event.position
    else:
        return

    var hit_thing_id = ""
    var hit_z = -2147483648
    for thing_id in _live_bindings:
        var binding = _live_bindings[thing_id]
        if not binding["interactive_events"].has("pointer_click"):
            continue
        var node = binding["node"]
        var visual = binding["sample_visual"]
        var width = max(12.0, float(visual.get("width", 12)))
        var height = max(12.0, float(visual.get("height", 12)))
        # gui_input positions are in viewport space. Include the viewport's
        # canvas transform when mapping them into the authored Thing's local
        # coordinate space; Node2D.to_local() alone only accounts for the
        # CanvasItem transform and mis-picks scaled browser canvases.
        var local_point = node.get_global_transform_with_canvas().affine_inverse() * point
        var half_w = width / 2.0
        var half_h = height / 2.0
        var inside = false
        if str(visual.get("shape", "rectangle")) == "ellipse":
            var nx = local_point.x / half_w
            var ny = local_point.y / half_h
            inside = nx * nx + ny * ny <= 1.0
        else:
            inside = abs(local_point.x) <= half_w and abs(local_point.y) <= half_h
        if inside and int(node.z_index) >= hit_z:
            hit_z = int(node.z_index)
            hit_thing_id = str(thing_id)

    print("SMX_EDITOR_POINTER=" + JSON.stringify({
        "path": "surface",
        "x": point.x,
        "y": point.y,
        "hit_thing_id": hit_thing_id,
    }))
    if hit_thing_id != "":
        _dispatch_editor_live_event(hit_thing_id, "pointer_click", {"pointer": "primary"})
        get_viewport().set_input_as_handled()


func _on_editor_live_input(_viewport, event, _shape_idx, thing_id):
    if not _live_ready:
        return
    var primary_pointer = false
    if event is InputEventMouseButton:
        primary_pointer = event.pressed and event.button_index == MOUSE_BUTTON_LEFT
    elif event is InputEventScreenTouch:
        primary_pointer = event.pressed
    if not primary_pointer:
        return
    print("SMX_EDITOR_POINTER=" + JSON.stringify({
        "path": "area",
        "thing_id": str(thing_id),
    }))
    _dispatch_editor_live_event(str(thing_id), "pointer_click", {"pointer": "primary"})


func _dispatch_editor_live_event(thing_id, trigger, payload):
    if _live_event_pending:
        return
    _live_event_pending = true
    var request = HTTPRequest.new()
    add_child(request)
    request.request_completed.connect(
        _on_editor_live_event_completed.bind(request, str(thing_id), str(trigger))
    )
    var origin = str(JavaScriptBridge.eval("window.location.origin", true))
    if origin == "":
        _live_event_pending = false
        request.queue_free()
        _fatal("editor-live browser origin is unavailable for interaction")
        return
    var headers = PackedStringArray(["Content-Type: application/json"])
    var body = JSON.stringify({
        "thing_id": str(thing_id),
        "trigger": str(trigger),
        "payload": payload,
    })
    var error = request.request(
        origin + "/api/godot-runtime-event",
        headers,
        HTTPClient.METHOD_POST,
        body
    )
    if error != OK:
        _live_event_pending = false
        request.queue_free()
        _fatal("editor-live interaction request could not start")


func _on_editor_live_event_completed(
    _result, response_code, _headers, body, request, thing_id, trigger
):
    _live_event_pending = false
    request.queue_free()
    if int(response_code) != 200:
        _fatal("editor-live interaction request failed with status " + str(response_code))
        return
    var envelope = JSON.parse_string(body.get_string_from_utf8())
    if typeof(envelope) != TYPE_DICTIONARY or envelope.get("ok", false) != true:
        _fatal("editor-live interaction response is invalid")
        return
    var updates = envelope.get("updates", [])
    if typeof(updates) != TYPE_ARRAY or updates.is_empty():
        var legacy_update = envelope.get("update", {})
        updates = [legacy_update]
    for update in updates:
        if (
            typeof(update) != TYPE_DICTIONARY
            or str(update.get("contract", "")) != "splashmx.editor-godot-runtime-update/1"
            or str(update.get("project_revision_id", "")) != _live_project_revision_id
        ):
            _fatal("editor-live interaction update identity is invalid")
            return
        if not _canonical_shape_is_clean(update):
            _fatal("editor-live interaction update leaked engine/runtime identity")
            return
        var update_thing_id = str(update.get("thing_id", ""))
        if not _live_bindings.has(update_thing_id):
            _fatal("editor-live interaction target is no longer materialized")
            return
        var visual = update.get("visual", {})
        if typeof(visual) != TYPE_DICTIONARY:
            _fatal("editor-live interaction visual is invalid")
            return
        var binding = _live_bindings[update_thing_id]
        binding["base_visual"] = visual.duplicate(true)
        _apply_editor_live_tick(_live_elapsed_tick)
        print("SMX051D_INTERACTION=" + JSON.stringify({
            "contract": "splashmx.editor-godot-interaction/1",
            "project_revision_id": _live_project_revision_id,
            "source_thing_id": str(thing_id),
            "thing_id": update_thing_id,
            "trigger": str(trigger),
            "visual": binding["sample_visual"].duplicate(true),
        }))


func _semantic_live_sample(tick):
    var ids = _live_bindings.keys()
    ids.sort()
    var things = []
    for thing_id in ids:
        var visual = _live_bindings[thing_id]["sample_visual"]
        things.append({
            "thing_id": thing_id,
            "x": float(visual.get("x", 0)),
            "y": float(visual.get("y", 0)),
            "width": float(visual.get("width", 0)),
            "height": float(visual.get("height", 0)),
            "rotation": float(visual.get("rotation", 0)),
        })
    return {
        "contract": "splashmx.editor-godot-play-sample/1",
        "project_revision_id": _live_project_revision_id,
        "tick": tick,
        "things": things,
    }


func _emit_editor_live_ready():
    var ids = _live_bindings.keys()
    ids.sort()
    var interactive_ids = []
    for thing_id in ids:
        if _live_bindings[thing_id]["interactive_events"].has("pointer_click"):
            interactive_ids.append(thing_id)
    print("SMX051C_PLAY_READY=" + JSON.stringify({
        "contract": "splashmx.editor-godot-play-ready/1",
        "project_revision_id": _live_project_revision_id,
        "thing_ids": ids,
        "interactive_thing_ids": interactive_ids,
        "max_tick": _live_max_tick,
    }))


func _emit_editor_live_sample(tick):
    print("SMX051C_SAMPLE=" + JSON.stringify(_semantic_live_sample(tick)))


func _process_editor_live(delta):
    if not _live_ready or _live_end_emitted or _live_max_tick <= 0.0:
        return
    var prior = _live_elapsed_tick
    _live_elapsed_tick = min(_live_max_tick, _live_elapsed_tick + float(delta) * _live_ticks_per_second)
    var midpoint = _live_max_tick / 2.0
    if not _live_mid_emitted and prior < midpoint and _live_elapsed_tick >= midpoint:
        _apply_editor_live_tick(midpoint)
        _emit_editor_live_sample(midpoint)
        _live_mid_emitted = true
    _apply_editor_live_tick(_live_elapsed_tick)
    if _live_elapsed_tick >= _live_max_tick:
        _apply_editor_live_tick(_live_max_tick)
        _emit_editor_live_sample(_live_max_tick)
        _live_end_emitted = true


func _parse_args(args):
    var result = {}
    for arg in args:
        if arg.begins_with("--") and arg.contains("="):
            var pair = arg.substr(2).split("=", true, 1)
            result[pair[0]] = pair[1]
    return result


func _load_fixture():
    var path = str(_args.get("fixture", "res://runtime_fixture.json"))
    var handle = FileAccess.open(path, FileAccess.READ)
    if handle == null:
        _fatal("runtime fixture could not be opened: " + path)
        return {}
    var parsed = JSON.parse_string(handle.get_as_text())
    if typeof(parsed) != TYPE_DICTIONARY:
        _fatal("runtime fixture is not a JSON object")
        return {}
    return parsed


func _prepare_profile():
    var profiles = _fixture.get("profiles", {})
    if not profiles.has(_profile):
        _fatal("fixture lacks selected profile")
        return false
    var row = profiles[_profile]
    _available = row.get("available", []).duplicate()
    var required = _fixture.get("required_features", [])
    var optional = _fixture.get("optional_features", [])
    for feature in required:
        if not _available.has(feature):
            _fatal("required target feature unavailable: " + str(feature))
            return false
    _active_features = required.duplicate()
    _degraded_optional = []
    for feature in optional:
        if _available.has(feature):
            if not _active_features.has(feature):
                _active_features.append(feature)
        else:
            _degraded_optional.append(feature)
    _active_features.sort()
    _degraded_optional.sort()
    return true


func _load_asset_refs():
    _asset_revisions.clear()
    for ref in _fixture.get("protected_asset_refs", []):
        var asset_id = str(ref.get("asset_id", ""))
        var digest = str(ref.get("revision_digest", ""))
        if asset_id == "" or digest == "":
            _fatal("protected Asset reference is incomplete")
            return false
        if _asset_revisions.has(asset_id) and str(_asset_revisions[asset_id]) != digest:
            _fatal("competing protected Asset revisions")
            return false
        if _asset_revisions.has(asset_id):
            _fatal("duplicate protected Asset reference")
            return false
        _asset_revisions[asset_id] = digest
    return true


func _materialize_all():
    var things = _fixture.get("things", [])
    if things.size() > MAX_BINDINGS:
        _fatal("binding count limit exceeded")
        return false
    var candidate_root = Node.new()
    candidate_root.name = "SplashMXPrivateBindings"
    add_child(candidate_root)
    var candidate = {}
    var object_count = 0
    for thing in things:
        var thing_id = str(thing.get("thing_id", ""))
        var facets = _active_facets(thing.get("facets", []))
        var objects = _create_private_objects(candidate_root, thing_id, facets)
        object_count += objects.size()
        if object_count > MAX_OBJECTS:
            candidate_root.free()
            _fatal("private object count limit exceeded")
            return false
        candidate[thing_id] = {
            "thing_id": thing_id,
            "facets": facets,
            "objects": objects,
            "generation": 1
        }
    var old_root = _binding_root
    _binding_root = candidate_root
    _bindings = candidate
    if old_root != null and is_instance_valid(old_root):
        old_root.free()
    return true


func _active_facets(requested):
    var result = []
    for feature in requested:
        if _active_features.has(feature):
            result.append(feature)
    return result


func _create_private_objects(root, thing_id, facets):
    var objects = []
    if facets.has("render_2d") or facets.has("input"):
        var visual = Node2D.new()
        visual.set_meta("smx_thing_id", thing_id)
        root.add_child(visual)
        objects.append(visual)
    if facets.has("physics_2d"):
        var area = Area2D.new()
        area.set_meta("smx_thing_id", thing_id)
        var collision = CollisionShape2D.new()
        var shape = RectangleShape2D.new()
        shape.size = Vector2(8.0, 8.0)
        collision.shape = shape
        area.add_child(collision)
        root.add_child(area)
        objects.append(area)
        objects.append(collision)
    if facets.has("audio_basic"):
        var audio = AudioStreamPlayer.new()
        audio.set_meta("smx_thing_id", thing_id)
        root.add_child(audio)
        objects.append(audio)
    return objects


func _recreate_binding(thing_id):
    if not _bindings.has(thing_id):
        return false
    var source = null
    for thing in _fixture.get("things", []):
        if str(thing.get("thing_id", "")) == thing_id:
            source = thing
            break
    if source == null:
        return false
    var old = _bindings[thing_id]
    var facets = _active_facets(source.get("facets", []))
    var objects = _create_private_objects(_binding_root, thing_id, facets)
    var candidate_count = _private_object_count() - old["objects"].size() + objects.size()
    if candidate_count > MAX_OBJECTS:
        for obj in objects:
            if is_instance_valid(obj):
                obj.free()
        return false
    var generation = int(old.get("generation", 1)) + 1
    _bindings[thing_id] = {
        "thing_id": thing_id,
        "facets": facets,
        "objects": objects,
        "generation": generation
    }
    for obj in old["objects"]:
        if is_instance_valid(obj):
            obj.free()
    return str(_bindings[thing_id]["thing_id"]) == thing_id


func _exercise_adapters():
    var result = {
        "render": not _active_features.has("render_2d"),
        "physics": not _active_features.has("physics_2d"),
        "audio": not _active_features.has("audio_basic"),
        "input": not _active_features.has("input")
    }
    for thing_id in _bindings:
        for obj in _bindings[thing_id]["objects"]:
            if obj is Node2D and _active_features.has("render_2d"):
                obj.position = Vector2(2.0, 3.0)
                result["render"] = obj.position == Vector2(2.0, 3.0)
            if obj is Area2D and _active_features.has("physics_2d"):
                obj.monitoring = true
                result["physics"] = obj.monitoring
            if obj is AudioStreamPlayer and _active_features.has("audio_basic"):
                obj.volume_db = -3.0
                result["audio"] = is_equal_approx(obj.volume_db, -3.0)
    if _active_features.has("input"):
        var event = InputEventAction.new()
        event.action = &"smx038_probe"
        event.pressed = true
        var normalized = {
            "thing_id": str(_fixture.get("input_thing_id", "button")),
            "trigger": "engine_input",
            "pressed": event.is_pressed()
        }
        result["input"] = normalized["pressed"] == true and not normalized.has("NodePath")
    return result


func _exercise_derivative_cache():
    var refs = _fixture.get("protected_asset_refs", [])
    if refs.is_empty():
        return {
            "exact_revision_key": false,
            "competing_revision_rejected": false,
            "eviction_semantic_noop": false
        }
    var ref = refs[0]
    var before = _asset_revisions.duplicate(true)
    var stream = AudioStreamWAV.new()
    var stored = _cache_derivative(ref, "audio_decode", stream)
    var conflicting = ref.duplicate(true)
    conflicting["revision_digest"] = str(ref.get("revision_digest", "")) + "-other"
    var conflict_rejected = not _cache_derivative(conflicting, "audio_decode", AudioStreamWAV.new())
    var key = _derivative_key(ref, "audio_decode")
    _derivatives.erase(key)
    return {
        "exact_revision_key": stored and key.contains(str(ref.get("asset_id", ""))) and key.contains(str(ref.get("revision_digest", ""))),
        "competing_revision_rejected": conflict_rejected,
        "eviction_semantic_noop": before == _asset_revisions
    }


func _cache_derivative(ref, kind, resource):
    var asset_id = str(ref.get("asset_id", ""))
    var digest = str(ref.get("revision_digest", ""))
    if not _asset_revisions.has(asset_id):
        return false
    if str(_asset_revisions[asset_id]) != digest:
        return false
    var key = _derivative_key(ref, kind)
    if not _derivatives.has(key) and _derivatives.size() >= MAX_DERIVATIVES:
        return false
    _derivatives[key] = resource
    return true


func _derivative_key(ref, kind):
    return "%s|%s|%s|%s" % [
        str(ref.get("asset_id", "")),
        str(ref.get("revision_digest", "")),
        _profile,
        kind
    ]


func _run_boundary_tests(scheduler_reordered, identity_preserved, worldsave_preserved):
    var poisoned = _fixture.duplicate(true)
    poisoned["things"][0]["NodePath"] = "/root/Leak"
    var duplicates = _fixture.get("things", []).duplicate(true)
    duplicates.append(_fixture.get("things", [])[0].duplicate(true))
    var required_missing = not _profile_contract_allows([], ["physics_2d"])
    var semantic_only_zero = true
    for thing in _fixture.get("things", []):
        if thing.get("facets", []).is_empty():
            var thing_id = str(thing.get("thing_id", ""))
            if not _bindings.has(thing_id) or _bindings[thing_id]["objects"].size() != 0:
                semantic_only_zero = false
    return {
        "forbidden_handle_rejected": not _canonical_shape_is_clean(poisoned),
        "duplicate_thing_rejected": not _unique_thing_ids(duplicates),
        "required_feature_fails_closed": required_missing,
        "scheduler_reorder_equivalent": scheduler_reordered,
        "binding_recreation_preserves_semantic_identity": identity_preserved,
        "binding_recreation_preserves_worldsave_fingerprint": worldsave_preserved,
        "semantic_only_zero_binding": semantic_only_zero
    }


func _profile_contract_allows(available, required):
    for feature in required:
        if not available.has(feature):
            return false
    return true


func _schedule_trace(events):
    var queue = events.duplicate(true)
    queue.sort_custom(_event_less)
    var trace = []
    for event in queue:
        trace.append("%s:%s:%s:%s:%s" % [
            event.get("logical_tick", 0),
            event.get("author_order", 0),
            event.get("sequence", 0),
            event.get("thing_id", ""),
            event.get("attachment_id", "")
        ])
    for _i in range(250):
        var probe = events.duplicate(true)
        probe.sort_custom(_event_less)
        if probe.size() != queue.size():
            _fatal("scheduler probe size drift")
            break
    return trace


func _event_less(a, b):
    var ak = [
        int(a.get("logical_tick", 0)),
        int(a.get("author_order", 0)),
        int(a.get("sequence", 0)),
        str(a.get("thing_id", "")),
        str(a.get("attachment_id", ""))
    ]
    var bk = [
        int(b.get("logical_tick", 0)),
        int(b.get("author_order", 0)),
        int(b.get("sequence", 0)),
        str(b.get("thing_id", "")),
        str(b.get("attachment_id", ""))
    ]
    for i in range(ak.size()):
        if ak[i] == bk[i]:
            continue
        return ak[i] < bk[i]
    return false


func _semantic_binding_view():
    var ids = _bindings.keys()
    ids.sort()
    var result = []
    for thing_id in ids:
        result.append({
            "thing_id": thing_id,
            "facets": _bindings[thing_id]["facets"].duplicate()
        })
    return result


func _private_object_count():
    var count = 0
    for thing_id in _bindings:
        count += _bindings[thing_id]["objects"].size()
    return count


func _unique_thing_ids(things):
    var seen = {}
    for thing in things:
        var thing_id = str(thing.get("thing_id", ""))
        if thing_id == "" or seen.has(thing_id):
            return false
        seen[thing_id] = true
    return true


func _canonical_shape_is_clean(value):
    if typeof(value) == TYPE_DICTIONARY:
        for key in value:
            if FORBIDDEN_KEYS.has(str(key)):
                return false
            if not _canonical_shape_is_clean(value[key]):
                return false
    elif typeof(value) == TYPE_ARRAY:
        for item in value:
            if not _canonical_shape_is_clean(item):
                return false
    return true


func _finish():
    var text = JSON.stringify(_evidence)
    print("SMX038_RESULT=" + text)
    if _output_path != "":
        var output = FileAccess.open(_output_path, FileAccess.WRITE)
        if output == null:
            _fatal("output path could not be opened")
            return
        output.store_string(JSON.stringify(_evidence, "  ") + "\n")
        output.flush()
    get_tree().quit(0)


func _fatal(message):
    push_error("SMX-038: " + message)
    print("SMX038_ERROR=" + message)
    get_tree().quit(1)
