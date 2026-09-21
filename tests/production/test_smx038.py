from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    AssetId,
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ProjectId,
    ProjectRevisionId,
    ThingId,
    ThingRecord,
)
from splashmx.execution.ir import (  # noqa: E402
    ExecutionRuntime,
    IRHandler,
    IRInstruction,
    IRProgram,
    ServiceRequest,
    payload,
)
from splashmx.runtime.godot import (  # noqa: E402
    BROWSER_PROFILE,
    CAP_AUDIO,
    CAP_INPUT,
    CAP_PHYSICS,
    CAP_RENDER,
    HEADLESS_PROFILE,
    NATIVE_PROFILE,
    BindingTable,
    EngineEvent,
    GodotRuntimeError,
    MediaDerivativeCache,
    ProtectedAssetRef,
    RuntimeProfileName,
    RuntimeProjection,
    SemanticTurnBridge,
    TargetProfile,
    ThingProjection,
    build_host_service_adapters,
    prepare_profile,
    validate_target_value,
)
from splashmx.security.capabilities import (  # noqa: E402
    CapabilityBroker,
    CapabilityError,
    CapabilityScope,
    PrincipalId,
    TrustedHostServiceBoundary,
)


FIXTURES = ROOT / "spec" / "production" / "smx038-godot-runtime-fixtures.json"


def projection(
    *,
    required=frozenset({"physics_2d"}),
    optional=frozenset({"render_2d", "input", "audio_basic"}),
) -> RuntimeProjection:
    return RuntimeProjection(
        things=(
            ThingProjection(
                ThingId("worker"),
                ("render_2d", "physics_2d", "audio_basic"),
                0,
            ),
            ThingProjection(ThingId("button"), ("render_2d", "input"), 1),
            ThingProjection(ThingId("inventory"), (), 2),
        ),
        protected_assets=(
            ProtectedAssetRef(AssetId("audio-main"), "digest-audio-v1"),
        ),
        required_features=required,
        optional_features=optional,
    )


def runtime_for_bridge() -> ExecutionRuntime:
    thing = ThingId("thing")
    attachment = BehaviourAttachmentId("slot")
    program = IRProgram(
        "bridge:1",
        (
            IRHandler(
                "engine-input",
                "engine_input",
                (
                    IRInstruction(
                        "set_public",
                        {"key": "last", "value": payload("value")},
                    ),
                ),
            ),
        ),
    )
    document = CanonicalDocument(ProjectId("project-godot"), ProjectRevisionId("r0"))
    document.things[thing] = ThingRecord(
        thing,
        "Thing",
        authored_state={"last": 0},
        behaviours={
            attachment: BehaviourAttachmentRecord(attachment, "bridge:1")
        },
    )
    return ExecutionRuntime.from_document(document, {"bridge:1": program})


class RecordingHost:
    def __init__(self, *, unsafe_result: bool = False):
        self.calls: list[tuple[str, object]] = []
        self.unsafe_result = unsafe_result

    def _record(self, family, payload):
        self.calls.append((family, payload))
        if self.unsafe_result:
            return object()
        return {"ok": True, "family": family}

    def render(self, payload):
        return self._record("render", payload)

    def audio(self, payload):
        return self._record("audio", payload)

    def input(self, payload):
        return self._record("input", payload)

    def physics(self, payload):
        return self._record("physics", payload)


def render_boundary(host: RecordingHost):
    broker = CapabilityBroker()
    principal = PrincipalId("behaviour:thing:slot")
    broker.issue_root_grant(
        grant_id="render-grant",
        principal_id=principal,
        capability_id=CAP_RENDER,
        scope=CapabilityScope(
            targets=frozenset({"thing:thing"}),
            operations=frozenset({"render:draw"}),
            max_bytes=1024,
        ),
        issuer_policy_id="test-policy",
        issued_at=0,
        expires_at=100,
    )
    boundary = TrustedHostServiceBoundary(broker, build_host_service_adapters(host))
    request = ServiceRequest(
        ThingId("thing"),
        BehaviourAttachmentId("slot"),
        "godot.render",
        {"thing_id": "thing", "operation": "draw", "byte_count": 8, "value": {"x": 1}},
        "req-1",
        7,
    )
    return broker, boundary, request


class SMX038GodotRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_data = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_fixture_family_is_complete_and_unique(self):
        cases = self.fixture_data["cases"]
        self.assertEqual(self.fixture_data["schema"], "splashmx.smx038-godot-runtime-fixtures/1")
        self.assertEqual(len(cases), 32)
        self.assertEqual(
            [row["id"] for row in cases],
            [f"GRT-{index:03d}" for index in range(1, 33)],
        )

    def test_same_projection_prepares_native_browser_and_headless_profiles(self):
        source = projection()
        native = prepare_profile(source, NATIVE_PROFILE)
        browser = prepare_profile(source, BROWSER_PROFILE)
        headless = prepare_profile(source, HEADLESS_PROFILE)
        self.assertEqual(native.protected_assets, source.protected_assets)
        self.assertEqual(browser.protected_assets, source.protected_assets)
        self.assertEqual(headless.protected_assets, source.protected_assets)
        self.assertEqual(headless.degraded_optional_features, ("audio_basic", "input", "render_2d"))
        worker = next(row for row in headless.things if row.thing_id == ThingId("worker"))
        inventory = next(row for row in headless.things if row.thing_id == ThingId("inventory"))
        self.assertEqual(worker.active_facets, ("physics_2d",))
        self.assertEqual(inventory.active_facets, ())

    def test_required_feature_unavailable_fails_before_materialization(self):
        source = projection(
            required=frozenset({"render_2d", "physics_2d"}),
            optional=frozenset({"audio_basic", "input"}),
        )
        with self.assertRaises(GodotRuntimeError) as caught:
            prepare_profile(source, HEADLESS_PROFILE)
        self.assertEqual(caught.exception.code, "godot.required_feature_unavailable")

    def test_unknown_target_feature_fails_closed(self):
        with self.assertRaises(GodotRuntimeError) as caught:
            TargetProfile(RuntimeProfileName.NATIVE, frozenset({"render_2d", "raw_gpu"}))
        self.assertEqual(caught.exception.code, "godot.unknown_feature")

    def test_projection_rejects_duplicate_thing_identity(self):
        row = ThingProjection(ThingId("same"), (), 0)
        with self.assertRaises(GodotRuntimeError) as caught:
            RuntimeProjection((row, row), (), frozenset(), frozenset())
        self.assertEqual(caught.exception.code, "godot.duplicate_thing")

    def test_projection_rejects_undeclared_facet(self):
        with self.assertRaises(GodotRuntimeError) as caught:
            RuntimeProjection(
                (ThingProjection(ThingId("thing"), ("render_2d",), 0),),
                (),
                frozenset({"physics_2d"}),
                frozenset(),
            )
        self.assertEqual(caught.exception.code, "godot.undeclared_feature")

    def test_projection_rejects_competing_protected_asset_revision(self):
        ref_a = ProtectedAssetRef(AssetId("asset"), "r1")
        ref_b = ProtectedAssetRef(AssetId("asset"), "r2")
        with self.assertRaises(GodotRuntimeError) as caught:
            RuntimeProjection((), (ref_a, ref_b), frozenset(), frozenset())
        self.assertEqual(caught.exception.code, "godot.protected_asset_conflict")

    def test_recursive_engine_handle_fields_are_rejected(self):
        for field in (
            "NodePath",
            "RID",
            "ResourceUID",
            "resource_path",
            "transport_peer_id",
            "process_handle",
            "instance_id",
        ):
            with self.subTest(field=field):
                with self.assertRaises(GodotRuntimeError) as caught:
                    validate_target_value({"nested": [{field: "poison"}]})
                self.assertEqual(caught.exception.code, "godot.forbidden_transient_identity")

    def test_non_finite_target_values_are_rejected(self):
        with self.assertRaises(GodotRuntimeError) as caught:
            validate_target_value({"value": float("nan")})
        self.assertEqual(caught.exception.code, "godot.invalid_value")

    def test_binding_materialization_is_sparse_and_semantic_view_has_no_handles(self):
        prepared = prepare_profile(projection(), NATIVE_PROFILE)
        created = []
        table = BindingTable(
            lambda thing_id, facets: [
                created.append((str(thing_id), facet)) or object()
                for facet in facets
            ],
            lambda _obj: None,
        )
        table.materialize(prepared)
        self.assertEqual(table.active_facets(ThingId("inventory")), ())
        self.assertEqual(table.private_objects(ThingId("inventory")), ())
        view = table.semantic_view()
        self.assertEqual(len(view), 3)
        self.assertFalse(any("object at" in repr(row) for row in view))
        self.assertEqual(table.object_count, 5)

    def test_binding_recreation_preserves_semantic_identity(self):
        prepared = prepare_profile(projection(), NATIVE_PROFILE)
        destroyed = []
        table = BindingTable(
            lambda _thing_id, facets: [object() for _ in facets],
            destroyed.append,
        )
        table.materialize(prepared)
        before = table.semantic_view()
        worker = next(row for row in prepared.things if row.thing_id == ThingId("worker"))
        old_objects = table.private_objects(ThingId("worker"))
        table.recreate(worker)
        self.assertEqual(table.semantic_view(), before)
        self.assertNotEqual(table.private_objects(ThingId("worker")), old_objects)
        self.assertEqual(len(destroyed), len(old_objects))

    def test_binding_prepare_failure_preserves_published_table(self):
        prepared = prepare_profile(projection(), NATIVE_PROFILE)
        failures = {"enabled": False}
        destroyed = []

        def factory(thing_id, facets):
            if failures["enabled"] and thing_id == ThingId("button"):
                raise RuntimeError("synthetic target failure")
            return [object() for _ in facets]

        table = BindingTable(factory, destroyed.append)
        table.materialize(prepared)
        before = table.semantic_view()
        before_handles = table.private_objects(ThingId("worker"))
        failures["enabled"] = True
        with self.assertRaises(GodotRuntimeError) as caught:
            table.materialize(prepared)
        self.assertEqual(caught.exception.code, "godot.binding_materialization_failed")
        self.assertEqual(table.semantic_view(), before)
        self.assertEqual(table.private_objects(ThingId("worker")), before_handles)

    def test_binding_object_budget_fails_closed(self):
        prepared = prepare_profile(projection(), NATIVE_PROFILE)
        table = BindingTable(
            lambda _thing_id, facets: [object() for _ in facets],
            lambda _obj: None,
            max_objects=2,
        )
        with self.assertRaises(GodotRuntimeError) as caught:
            table.materialize(prepared)
        self.assertEqual(caught.exception.code, "godot.object_limit")
        self.assertEqual(table.bound_thing_count, 0)

    def test_binding_count_budget_fails_closed(self):
        prepared = prepare_profile(projection(), NATIVE_PROFILE)
        table = BindingTable(
            lambda _thing_id, facets: [object() for _ in facets],
            lambda _obj: None,
            max_bindings=2,
        )
        with self.assertRaises(GodotRuntimeError) as caught:
            table.materialize(prepared)
        self.assertEqual(caught.exception.code, "godot.binding_limit")

    def test_engine_callback_capture_does_not_execute_behaviour_directly(self):
        runtime = runtime_for_bridge()
        bridge = SemanticTurnBridge(runtime)
        bridge.capture(EngineEvent(ThingId("thing"), "engine_input", {"value": 7}, 0, 0, 1))
        self.assertEqual(runtime.states[ThingId("thing")].public_state["last"], 0)
        self.assertEqual(runtime.queue_depth, 0)
        self.assertEqual(bridge.flush_to_scheduler(), 1)
        self.assertEqual(runtime.states[ThingId("thing")].public_state["last"], 0)
        runtime.run_current_tick()
        self.assertEqual(runtime.states[ThingId("thing")].public_state["last"], 7)

    def test_engine_arrival_order_cannot_redefine_semantic_order(self):
        events = (
            EngineEvent(ThingId("thing"), "engine_input", {"value": 11}, 0, 0, 10),
            EngineEvent(ThingId("thing"), "engine_input", {"value": 22}, 0, 1, 1),
        )

        def result(rows):
            runtime = runtime_for_bridge()
            bridge = SemanticTurnBridge(runtime)
            for row in rows:
                bridge.capture(row)
            bridge.flush_to_scheduler()
            runtime.run_current_tick()
            return runtime.states[ThingId("thing")].public_state["last"]

        self.assertEqual(result(events), 22)
        self.assertEqual(result(tuple(reversed(events))), 22)

    def test_engine_event_rejects_transient_identity_payload(self):
        with self.assertRaises(GodotRuntimeError) as caught:
            EngineEvent(
                ThingId("thing"),
                "engine_input",
                {"nested": {"RID": 123}},
                0,
                0,
                0,
            )
        self.assertEqual(caught.exception.code, "godot.forbidden_transient_identity")

    def test_engine_input_queue_has_independent_bound(self):
        runtime = runtime_for_bridge()
        bridge = SemanticTurnBridge(runtime, max_pending_inputs=1)
        event = EngineEvent(ThingId("thing"), "engine_input", {"value": 1}, 0, 0, 0)
        bridge.capture(event)
        with self.assertRaises(GodotRuntimeError) as caught:
            bridge.capture(event)
        self.assertEqual(caught.exception.code, "godot.input_queue_limit")

    def test_scheduler_budget_failure_is_not_bypassed_by_bridge(self):
        runtime = runtime_for_bridge()
        runtime.budgets = runtime.budgets.__class__(
            instruction_steps=20_000,
            recursion_depth=32,
            allocations=10_000,
            emitted_work=1_000,
            timers_per_activation=256,
            pending_timers=4_096,
            queue_entries=1,
            service_requests=256,
            pending_service_requests=4_096,
            outbox_entries=8_192,
            activations_per_run=20_000,
        )
        bridge = SemanticTurnBridge(runtime)
        bridge.capture(EngineEvent(ThingId("thing"), "engine_input", {"value": 1}, 0, 0, 0))
        bridge.capture(EngineEvent(ThingId("thing"), "engine_input", {"value": 2}, 0, 1, 1))
        with self.assertRaises(Exception) as caught:
            bridge.flush_to_scheduler()
        self.assertEqual(getattr(caught.exception, "code", None), "execution.queue_budget")
        self.assertEqual(bridge.pending_count, 1)

    def test_host_service_adapters_cover_four_capability_families(self):
        adapters = build_host_service_adapters(RecordingHost())
        self.assertEqual(
            {row.service_name: row.capability_id for row in adapters},
            {
                "godot.render": CAP_RENDER,
                "godot.audio": CAP_AUDIO,
                "godot.input": CAP_INPUT,
                "godot.physics": CAP_PHYSICS,
            },
        )

    def test_render_host_effect_crosses_only_after_capability_authorization(self):
        host = RecordingHost()
        _broker, boundary, request = render_boundary(host)
        call = boundary.admit(request, now=1)
        self.assertEqual(host.calls, [])
        result = boundary.execute(call, now=1)
        self.assertEqual(result, {"ok": True, "family": "render"})
        self.assertEqual(len(host.calls), 1)

    def test_capability_revocation_between_admission_and_host_use_wins_closed(self):
        host = RecordingHost()
        broker, boundary, request = render_boundary(host)
        call = boundary.admit(request, now=1)
        broker.revoke("render-grant")
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(call, now=2)
        self.assertEqual(caught.exception.code, "capability.revoked")
        self.assertEqual(host.calls, [])

    def test_missing_capability_denies_target_service_before_host_use(self):
        host = RecordingHost()
        boundary = TrustedHostServiceBoundary(
            CapabilityBroker(),
            build_host_service_adapters(host),
        )
        request = ServiceRequest(
            ThingId("thing"),
            BehaviourAttachmentId("slot"),
            "godot.audio",
            {"thing_id": "thing", "operation": "play"},
            "req-no-grant",
            1,
        )
        with self.assertRaises(CapabilityError) as caught:
            boundary.admit(request, now=1)
        self.assertEqual(caught.exception.code, "capability.denied")
        self.assertEqual(host.calls, [])

    def test_service_scope_cannot_be_confused_across_adapter_families(self):
        host = RecordingHost()
        _broker, boundary, request = render_boundary(host)
        audio_request = ServiceRequest(
            request.thing_id,
            request.attachment_id,
            "godot.audio",
            {"thing_id": "thing", "operation": "play"},
            "audio-1",
            8,
        )
        with self.assertRaises(CapabilityError) as caught:
            boundary.admit(audio_request, now=1)
        self.assertEqual(caught.exception.code, "capability.denied")
        self.assertEqual(host.calls, [])

    def test_service_payload_cannot_smuggle_godot_handle(self):
        adapter = next(
            row for row in build_host_service_adapters(RecordingHost())
            if row.service_name == "godot.render"
        )
        with self.assertRaises(GodotRuntimeError) as caught:
            adapter.target_resolver(
                {"thing_id": "thing", "operation": "draw", "NodePath": "/root/Leak"}
            )
        self.assertEqual(caught.exception.code, "godot.forbidden_transient_identity")

    def test_unsafe_host_result_is_rejected_by_existing_capability_boundary(self):
        host = RecordingHost(unsafe_result=True)
        _broker, boundary, request = render_boundary(host)
        call = boundary.admit(request, now=1)
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(call, now=1)
        self.assertEqual(caught.exception.code, "capability.invalid_value")

    def test_media_derivative_cache_is_bound_to_exact_protected_revision(self):
        ref = projection().protected_assets[0]
        cache = MediaDerivativeCache((ref,))
        handle = object()
        key = cache.put(
            ref,
            profile=RuntimeProfileName.NATIVE,
            derivative_kind="audio-decode",
            handle=handle,
        )
        self.assertIs(cache.get(key), handle)
        self.assertEqual(cache.protected_refs(), (ref,))

    def test_media_derivative_cannot_target_competing_asset_revision(self):
        ref = projection().protected_assets[0]
        cache = MediaDerivativeCache((ref,))
        with self.assertRaises(GodotRuntimeError) as caught:
            cache.put(
                ProtectedAssetRef(ref.asset_id, "digest-evil"),
                profile=RuntimeProfileName.NATIVE,
                derivative_kind="audio-decode",
                handle=object(),
            )
        self.assertEqual(caught.exception.code, "godot.protected_asset_conflict")

    def test_media_derivative_cannot_target_unknown_asset(self):
        ref = projection().protected_assets[0]
        cache = MediaDerivativeCache((ref,))
        with self.assertRaises(GodotRuntimeError) as caught:
            cache.put(
                ProtectedAssetRef(AssetId("other"), "digest-other"),
                profile=RuntimeProfileName.NATIVE,
                derivative_kind="audio-decode",
                handle=object(),
            )
        self.assertEqual(caught.exception.code, "godot.unknown_asset")

    def test_media_derivative_eviction_does_not_change_protected_asset_meaning(self):
        ref = projection().protected_assets[0]
        destroyed = []
        cache = MediaDerivativeCache((ref,), destructor=destroyed.append)
        handle = object()
        key = cache.put(
            ref,
            profile=RuntimeProfileName.BROWSER,
            derivative_kind="audio-decode",
            handle=handle,
        )
        before = cache.protected_refs()
        cache.evict(key)
        self.assertEqual(cache.protected_refs(), before)
        self.assertEqual(destroyed, [handle])

    def test_media_derivative_cache_has_independent_bound(self):
        ref = projection().protected_assets[0]
        cache = MediaDerivativeCache((ref,), max_entries=1)
        cache.put(
            ref,
            profile=RuntimeProfileName.NATIVE,
            derivative_kind="audio-decode",
            handle=object(),
        )
        with self.assertRaises(GodotRuntimeError) as caught:
            cache.put(
                ref,
                profile=RuntimeProfileName.NATIVE,
                derivative_kind="waveform",
                handle=object(),
            )
        self.assertEqual(caught.exception.code, "godot.derivative_cache_limit")

    def test_profile_preparation_preserves_asset_revision_reference_exactly(self):
        source = projection()
        for profile in (NATIVE_PROFILE, BROWSER_PROFILE, HEADLESS_PROFILE):
            with self.subTest(profile=profile.name):
                prepared = prepare_profile(source, profile)
                self.assertIs(prepared.protected_assets[0], source.protected_assets[0])
                self.assertEqual(
                    prepared.protected_assets[0].revision_digest,
                    "digest-audio-v1",
                )

    def test_runtime_projection_never_accepts_source_metadata_as_target_facets(self):
        with self.assertRaises(GodotRuntimeError) as caught:
            ThingProjection(
                ThingId("thing"),
                ("render_2d", "source_metadata"),
                0,
            )
        self.assertEqual(caught.exception.code, "godot.unknown_feature")


if __name__ == "__main__":
    unittest.main()
