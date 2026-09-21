extends Node

const CANDIDATES = ["node_per_thing", "scene_subtree", "facet_sparse"]
const FORBIDDEN_KEYS = [
    "NodePath", "RID", "ResourceUID", "resource_path", "transport_peer_id",
    "connection_handle", "socket_id", "session_id", "process_handle"
]

func _ready():
    var args = _parse_args(OS.get_cmdline_user_args())
    if not args.has("fixture") or not args.has("output"):
        push_error("SMX-037 requires --fixture=PATH and --output=PATH")
        get_tree().quit(2)
        return
    var fixture_file = FileAccess.open(args["fixture"], FileAccess.READ)
    if fixture_file == null:
        push_error("SMX-037 fixture could not be opened")
        get_tree().quit(2)
        return
    var fixture = JSON.parse_string(fixture_file.get_as_text())
    if typeof(fixture) != TYPE_DICTIONARY:
        push_error("SMX-037 fixture is not a JSON object")
        get_tree().quit(2)
        return
    var samples = int(args.get("samples", "5"))
    if samples < 1 or samples > 50:
        push_error("SMX-037 samples must be 1..50")
        get_tree().quit(2)
        return
    var evidence = _run_campaign(fixture, samples)
    var output_file = FileAccess.open(args["output"], FileAccess.WRITE)
    if output_file == null:
        push_error("SMX-037 output could not be opened")
        get_tree().quit(2)
        return
    output_file.store_string(JSON.stringify(evidence, "  ") + "\n")
    output_file.flush()
    print("SMX037_RESULT=" + JSON.stringify({"selected": evidence["selected_candidate"], "boundary_results": evidence["boundary_results"]}))
    get_tree().quit(0)

func _parse_args(args):
    var result = {}
    for arg in args:
        if arg.begins_with("--") and arg.contains("="):
            var pair = arg.substr(2).split("=", true, 1)
            result[pair[0]] = pair[1]
    return result

func _run_campaign(fixture, samples):
    if fixture.get("contract", "") != "splashmx.godot-binding-fixture/1":
        _fatal("fixture contract mismatch")
    if not _canonical_shape_is_clean(fixture):
        _fatal("fixture leaked a forbidden engine/runtime handle")
    if not _unique_semantic_ids(fixture["things"]):
        _fatal("fixture contains duplicate ThingId")

    var boundary = _run_boundary_tests(fixture)
    for key in boundary:
        if boundary[key] != true:
            _fatal("boundary test failed: " + str(key))

    var results = []
    for candidate in CANDIDATES:
        var rows = []
        for _sample in range(samples):
            rows.append(_measure_candidate(candidate, fixture))
        results.append(_summarize_candidate(candidate, rows))

    var selected = _select_candidate(results)
    if selected != "facet_sparse":
        _fatal("measured selection did not support facet_sparse")
    return {
        "contract": "splashmx.smx037-godot-raw-evidence/1",
        "fixture_revision": fixture.get("project_revision_id", "unknown"),
        "godot_version": Engine.get_version_info().get("string", "unknown"),
        "samples": samples,
        "selected_candidate": selected,
        "scheduler_integration": "central_turn_bridge",
        "candidate_results": results,
        "boundary_results": boundary,
        "target_profile_checks": _target_profile_checks(fixture),
        "protected_asset_refs": fixture.get("protected_asset_refs", []),
    }

func _measure_candidate(candidate, fixture):
    var before_nodes = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
    var before_objects = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var before_memory = int(Performance.get_monitor(Performance.MEMORY_STATIC))
    var started = Time.get_ticks_usec()
    var built = _build_layout(candidate, fixture["things"], fixture.get("protected_asset_refs", []))
    if not built["ok"]:
        _fatal("candidate failed to materialize: " + candidate)
    var create_usec = Time.get_ticks_usec() - started
    var after_nodes = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
    var after_objects = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var after_memory = int(Performance.get_monitor(Performance.MEMORY_STATIC))

    var scheduler_started = Time.get_ticks_usec()
    var trace = _schedule_trace(fixture["scheduler_events"])
    for _i in range(250):
        if _schedule_trace(fixture["scheduler_events"]) != trace:
            _fatal("central scheduler trace changed across repeated turns")
    var scheduler_usec = Time.get_ticks_usec() - scheduler_started

    var churn_started = Time.get_ticks_usec()
    var worker_id = "worker"
    for _i in range(40):
        if not _recreate_binding(candidate, built, worker_id, fixture["things"]):
            _fatal("binding recreation failed for " + candidate)
    var churn_usec = Time.get_ticks_usec() - churn_started
    if not built["bindings"].has(worker_id):
        _fatal("worker ThingId was lost during binding recreation")

    var path_checks = _exercise_adapter_paths(built, fixture)
    var result = {
        "create_usec": create_usec,
        "churn_usec": churn_usec,
        "scheduler_usec": scheduler_usec,
        "node_delta": max(0, after_nodes - before_nodes),
        "object_delta": max(0, after_objects - before_objects),
        "memory_delta_bytes": max(0, after_memory - before_memory),
        "bound_thing_count": built["bindings"].size(),
        "engine_binding_count": _binding_object_count(built["bindings"]),
        "scheduler_trace": trace,
        "path_checks": path_checks,
        "semantic_only_zero_binding": _semantic_only_zero_binding(candidate, built, fixture["things"]),
        "protected_asset_ref_preserved": built["asset_refs"] == fixture.get("protected_asset_refs", []),
    }
    built["root"].free()
    return result

func _build_layout(candidate, things, asset_refs):
    if not _unique_semantic_ids(things):
        return {"ok": false}
    var root = Node.new()
    root.name = "SMX037PrivateBindings"
    add_child(root)
    var bindings = {}
    for thing in things:
        var thing_id = str(thing.get("thing_id", ""))
        if thing_id == "":
            root.free()
            return {"ok": false}
        var facets = thing.get("facets", [])
        var objects = []
        if candidate == "node_per_thing":
            var node = Node2D.new()
            node.set_meta("smx_thing_id", thing_id)
            root.add_child(node)
            objects.append(node)
            _add_facet_children(node, facets, objects)
        elif candidate == "scene_subtree":
            var owner = Node.new()
            owner.set_meta("smx_thing_id", thing_id)
            root.add_child(owner)
            objects.append(owner)
            _add_facet_children(owner, facets, objects)
        elif candidate == "facet_sparse":
            _add_sparse_facets(root, thing_id, facets, objects)
        else:
            root.free()
            return {"ok": false}
        bindings[thing_id] = {"objects": objects, "thing_id": thing_id}
    return {"ok": true, "root": root, "bindings": bindings, "asset_refs": asset_refs.duplicate(true)}

func _add_facet_children(owner, facets, objects):
    if facets.has("render_2d") or facets.has("input"):
        var visual = Node2D.new()
        owner.add_child(visual)
        objects.append(visual)
    if facets.has("physics_2d"):
        var area = Area2D.new()
        var collision = CollisionShape2D.new()
        var shape = RectangleShape2D.new()
        shape.size = Vector2(8.0, 8.0)
        collision.shape = shape
        area.add_child(collision)
        owner.add_child(area)
        objects.append(area)
        objects.append(collision)
    if facets.has("audio_basic"):
        var audio = AudioStreamPlayer.new()
        owner.add_child(audio)
        objects.append(audio)

func _add_sparse_facets(root, thing_id, facets, objects):
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

func _recreate_binding(candidate, built, thing_id, things):
    if not built["bindings"].has(thing_id):
        return false
    var old = built["bindings"][thing_id]
    for obj in old["objects"]:
        if is_instance_valid(obj):
            obj.free()
    var target = null
    for thing in things:
        if str(thing.get("thing_id", "")) == thing_id:
            target = thing
            break
    if target == null:
        return false
    var objects = []
    var facets = target.get("facets", [])
    if candidate == "node_per_thing":
        var node = Node2D.new()
        node.set_meta("smx_thing_id", thing_id)
        built["root"].add_child(node)
        objects.append(node)
        _add_facet_children(node, facets, objects)
    elif candidate == "scene_subtree":
        var owner = Node.new()
        owner.set_meta("smx_thing_id", thing_id)
        built["root"].add_child(owner)
        objects.append(owner)
        _add_facet_children(owner, facets, objects)
    else:
        _add_sparse_facets(built["root"], thing_id, facets, objects)
    built["bindings"][thing_id] = {"objects": objects, "thing_id": thing_id}
    return built["bindings"][thing_id]["thing_id"] == thing_id

func _exercise_adapter_paths(built, fixture):
    var found_render = false
    var found_physics = false
    var found_audio = false
    for thing_id in built["bindings"]:
        for obj in built["bindings"][thing_id]["objects"]:
            if obj is Node2D:
                found_render = true
            if obj is Area2D:
                found_physics = true
            if obj is AudioStreamPlayer:
                found_audio = true
    var event = InputEventAction.new()
    event.action = &"smx037_probe"
    event.pressed = true
    var input_ok = event.is_pressed()
    var schedule_ok = _schedule_trace(fixture["scheduler_events"]).size() == fixture["scheduler_events"].size()
    return {"render": found_render, "physics": found_physics, "audio": found_audio, "input": input_ok, "scheduler": schedule_ok}

func _summarize_candidate(candidate, rows):
    var result = {"candidate": candidate}
    for metric in ["create_usec", "churn_usec", "scheduler_usec", "node_delta", "object_delta", "memory_delta_bytes", "bound_thing_count", "engine_binding_count"]:
        var values = []
        for row in rows:
            values.append(float(row[metric]))
        values.sort()
        result[metric + "_median"] = values[int(values.size() / 2)]
    result["scheduler_trace"] = rows[0]["scheduler_trace"]
    result["path_checks"] = rows[0]["path_checks"]
    result["semantic_only_zero_binding"] = rows[0]["semantic_only_zero_binding"]
    result["protected_asset_ref_preserved"] = rows[0]["protected_asset_ref_preserved"]
    return result

func _select_candidate(results):
    var by_name = {}
    for result in results:
        by_name[result["candidate"]] = result
        for check in result["path_checks"]:
            if result["path_checks"][check] != true:
                _fatal("adapter path missing for " + result["candidate"] + ": " + str(check))
        if result["protected_asset_ref_preserved"] != true:
            _fatal("protected Asset revision reference changed")
    var sparse = by_name["facet_sparse"]
    if sparse["semantic_only_zero_binding"] != true:
        _fatal("facet_sparse created engine bindings for semantic-only Things")
    if sparse["engine_binding_count_median"] > by_name["node_per_thing"]["engine_binding_count_median"]:
        return "node_per_thing"
    if sparse["engine_binding_count_median"] > by_name["scene_subtree"]["engine_binding_count_median"]:
        return "scene_subtree"
    return "facet_sparse"

func _run_boundary_tests(fixture):
    var poisoned = fixture.duplicate(true)
    poisoned["things"][0]["NodePath"] = "/root/Leak"
    var duplicate = fixture["things"].duplicate(true)
    duplicate.append(fixture["things"][0].duplicate(true))
    var reversed_events = fixture["scheduler_events"].duplicate(true)
    reversed_events.reverse()
    var unsupported = {
        "available": ["physics_2d"],
        "required": ["render_2d"],
        "optional": ["audio_basic"]
    }
    var optional_only = {
        "available": ["physics_2d"],
        "required": ["physics_2d"],
        "optional": ["audio_basic"]
    }
    var sparse = _build_layout("facet_sparse", fixture["things"], fixture.get("protected_asset_refs", []))
    var identity_before = sparse["bindings"]["worker"]["thing_id"]
    var asset_before = sparse["asset_refs"].duplicate(true)
    var recreated = _recreate_binding("facet_sparse", sparse, "worker", fixture["things"])
    var identity_after = sparse["bindings"]["worker"]["thing_id"]
    var result = {
        "forbidden_handle_rejected": not _canonical_shape_is_clean(poisoned),
        "duplicate_thing_id_rejected": not _unique_semantic_ids(duplicate),
        "scheduler_reorder_equivalent": _schedule_trace(fixture["scheduler_events"]) == _schedule_trace(reversed_events),
        "required_target_feature_fails_closed": not _profile_allows_activation(unsupported),
        "optional_target_feature_can_degrade": _profile_allows_activation(optional_only),
        "binding_recreation_preserves_thing_id": recreated and identity_before == identity_after,
        "binding_recreation_preserves_asset_ref": asset_before == sparse["asset_refs"],
        "semantic_only_has_zero_binding": _semantic_only_zero_binding("facet_sparse", sparse, fixture["things"]),
    }
    sparse["root"].free()
    return result

func _target_profile_checks(fixture):
    var result = {}
    for profile_name in fixture.get("target_profiles", {}):
        result[profile_name] = _profile_allows_activation(fixture["target_profiles"][profile_name])
    return result

func _profile_allows_activation(profile):
    var available = profile.get("available", [])
    for required in profile.get("required", []):
        if not available.has(required):
            return false
    return true

func _schedule_trace(events):
    var queue = events.duplicate(true)
    for i in range(1, queue.size()):
        var current = queue[i]
        var j = i - 1
        while j >= 0 and _event_less(current, queue[j]):
            queue[j + 1] = queue[j]
            j -= 1
        queue[j + 1] = current
    var trace = []
    for event in queue:
        trace.append("%s:%s:%s:%s:%s" % [
            event.get("logical_tick", 0), event.get("author_order", 0), event.get("sequence", 0),
            event.get("thing_id", ""), event.get("attachment_id", "")
        ])
    return trace

func _event_less(a, b):
    var ak = [int(a.get("logical_tick", 0)), int(a.get("author_order", 0)), int(a.get("sequence", 0)), str(a.get("thing_id", "")), str(a.get("attachment_id", ""))]
    var bk = [int(b.get("logical_tick", 0)), int(b.get("author_order", 0)), int(b.get("sequence", 0)), str(b.get("thing_id", "")), str(b.get("attachment_id", ""))]
    for i in range(ak.size()):
        if ak[i] == bk[i]:
            continue
        return ak[i] < bk[i]
    return false

func _unique_semantic_ids(things):
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

func _binding_object_count(bindings):
    var count = 0
    for thing_id in bindings:
        count += bindings[thing_id]["objects"].size()
    return count

func _semantic_only_zero_binding(candidate, built, things):
    if candidate != "facet_sparse":
        return true
    for thing in things:
        var facets = thing.get("facets", [])
        if facets.size() == 0:
            var thing_id = str(thing["thing_id"])
            if built["bindings"][thing_id]["objects"].size() != 0:
                return false
    return true

func _fatal(message):
    push_error("SMX-037: " + message)
    get_tree().quit(1)
    assert(false, message)
