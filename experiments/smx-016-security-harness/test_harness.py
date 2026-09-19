from __future__ import annotations

import unittest

from model import (
    ArchiveEntry, Artifact, AssetRevision, BudgetedExecutor, CapabilityBroker,
    CapabilityDenied, DependencyNode, DependencyRejected, Grant, HostRecorder,
    Limits, LockEntry, MalformedInput, MediaDescriptor, MigrationProbe,
    NetworkGuard, ResourceLimitExceeded, ServiceGateway, TARGETS,
    atomic_replace_asset, normalize_package_path, staged_load,
    trusted_proxy_request, validate_archive, validate_before_decode,
    validate_canonical_document, validate_dependency_graph,
    validate_exact_artifact,
)


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
SecurityErrorTuple = (DependencyRejected, MalformedInput)


def canonical_doc(**extra):
    base = {
        "schema": 1,
        "required_features": [],
        "records": [{"id": "thing:root", "kind": "thing", "state": {}}],
    }
    base.update(extra)
    return base


def dependency_graph():
    return {
        "root": DependencyNode("root", "r1", 100, ("dep",)),
        "dep": DependencyNode("dep", "d1", 100, ()),
    }


def replace_asset(asset: AssetRevision, **changes) -> AssetRevision:
    values = asset.__dict__.copy()
    values.update(changes)
    return AssetRevision(**values)


class PackageBoundaryTests(unittest.TestCase):
    def test_unicode_normalization_collision_rejected(self):
        with self.assertRaisesRegex(MalformedInput, "normalized_package_path_collision"):
            validate_archive([
                ArchiveEntry("assets/caf\u00e9.png", 10, 10),
                ArchiveEntry("assets/cafe\u0301.png", 10, 10),
            ])

    def test_case_collision_rejected(self):
        with self.assertRaisesRegex(MalformedInput, "normalized_package_path_collision"):
            validate_archive([
                ArchiveEntry("Assets/A.png", 10, 10),
                ArchiveEntry("assets/a.png", 10, 10),
            ])

    def test_traversal_backslash_and_absolute_paths_rejected(self):
        for path in ("../secret", r"a\..\secret", "/etc/passwd", r"C:\Windows\x"):
            with self.subTest(path=path), self.assertRaises(MalformedInput):
                normalize_package_path(path)

    def test_reserved_device_and_trailing_dot_rejected(self):
        for path in ("NUL", "aux.txt", "safe/name. ", "dir/COM1.log"):
            with self.subTest(path=path), self.assertRaises(MalformedInput):
                normalize_package_path(path)

    def test_symlink_special_and_nested_archive_rejected(self):
        with self.assertRaisesRegex(MalformedInput, "special_archive_entry_forbidden"):
            validate_archive([ArchiveEntry("x", 1, 1, kind="symlink")])
        with self.assertRaisesRegex(MalformedInput, "nested_archive_forbidden"):
            validate_archive([ArchiveEntry("x.zip", 1, 1, nested_archive=True)])

    def test_decompression_and_entry_budgets_fail_before_expansion(self):
        with self.assertRaisesRegex(ResourceLimitExceeded, "expansion_ratio_exceeded"):
            validate_archive([ArchiveEntry("bomb.bin", 1, 17)])
        with self.assertRaisesRegex(ResourceLimitExceeded, "undefined_expansion_ratio"):
            validate_archive([ArchiveEntry("bomb.bin", 0, 1)])
        tiny = Limits(max_entries=1)
        with self.assertRaisesRegex(ResourceLimitExceeded, "package_entry_count_exceeded"):
            validate_archive([ArchiveEntry("a", 1, 1), ArchiveEntry("b", 1, 1)], tiny)


class CanonicalBoundaryTests(unittest.TestCase):
    def test_duplicate_record_id_rejected(self):
        doc = canonical_doc(records=[{"id": "x"}, {"id": "x"}])
        with self.assertRaisesRegex(MalformedInput, "duplicate_record_id"):
            validate_canonical_document(doc)

    def test_nested_capability_or_host_handle_rejected_recursively(self):
        for key in ("capability_grant", "host_handle", "rid", "peer_id"):
            doc = canonical_doc(records=[{"id": "x", "state": {"nested": {key: "forged"}}}])
            with self.subTest(key=key), self.assertRaisesRegex(
                MalformedInput, "forbidden_durable_authority_field"
            ):
                validate_canonical_document(doc)

    def test_unknown_required_feature_fails_closed(self):
        with self.assertRaisesRegex(MalformedInput, "unsupported_required_feature"):
            validate_canonical_document(
                canonical_doc(required_features=["future:raw-host"]),
                supported_required_features={"known:safe"},
            )

    def test_depth_node_string_and_record_limits(self):
        limits = Limits(max_tree_depth=3, max_tree_nodes=20, max_string_bytes=8, max_records=1)
        with self.assertRaisesRegex(ResourceLimitExceeded, "structured_depth_budget_exceeded"):
            validate_canonical_document(
                {"records": [{"id": "x", "a": {"b": {"c": {"d": 1}}}}]}, limits=limits
            )
        with self.assertRaisesRegex(ResourceLimitExceeded, "string_budget_exceeded"):
            validate_canonical_document({"records": [{"id": "123456789"}]}, limits=limits)
        with self.assertRaisesRegex(ResourceLimitExceeded, "record_count_exceeded"):
            validate_canonical_document(
                {"records": [{"id": "a"}, {"id": "b"}]}, limits=limits
            )


class DependencyTests(unittest.TestCase):
    def test_exact_lock_rejects_revision_digest_and_size_substitution(self):
        lock = LockEntry("pkg", "r1", DIGEST_A, 10)
        for observed in (
            Artifact("pkg", "r2", DIGEST_A, 10),
            Artifact("pkg", "r1", DIGEST_B, 10),
            Artifact("pkg", "r1", DIGEST_A, 11),
            Artifact("evil", "r1", DIGEST_A, 10),
        ):
            with self.subTest(observed=observed), self.assertRaises(SecurityErrorTuple):
                validate_exact_artifact(lock, observed)

    def test_dependency_cycle_rejected(self):
        graph = {
            "a": DependencyNode("a", "1", 1, ("b",)),
            "b": DependencyNode("b", "1", 1, ("a",)),
        }
        with self.assertRaisesRegex(DependencyRejected, "dependency_cycle"):
            validate_dependency_graph("a", graph)

    def test_dependency_depth_count_and_bytes_are_bounded(self):
        chain = {
            str(i): DependencyNode(str(i), "1", 1, (str(i + 1),) if i < 5 else ())
            for i in range(6)
        }
        with self.assertRaisesRegex(ResourceLimitExceeded, "dependency_depth_exceeded"):
            validate_dependency_graph("0", chain, limits=Limits(max_dependency_depth=3))
        with self.assertRaisesRegex(ResourceLimitExceeded, "dependency_count_exceeded"):
            validate_dependency_graph("0", chain, limits=Limits(max_dependency_count=3))
        with self.assertRaisesRegex(ResourceLimitExceeded, "dependency_bytes_exceeded"):
            validate_dependency_graph("0", chain, limits=Limits(max_dependency_bytes=3))


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.broker = CapabilityBroker({"network.http", "storage.save"})
        self.host = HostRecorder()
        self.gateway = ServiceGateway(self.broker, self.host)

    def test_forbidden_raw_host_apis_never_reach_host_on_any_target(self):
        for target in TARGETS:
            for api in (
                "javascript.eval", "javascript.bridge", "godot.gdscript",
                "godot.pck.load", "native.gdextension", "native.process",
                "filesystem.raw", "network.raw_socket",
            ):
                with self.subTest(target=target, api=api), self.assertRaisesRegex(
                    CapabilityDenied, "raw_host_api_forbidden"
                ):
                    self.gateway.raw_host_call("attacker", api, target_profile=target)
        self.assertEqual(self.host.calls, [])

    def test_unsigned_or_signed_content_has_no_ambient_capability(self):
        # Provenance/signature is deliberately absent from the broker API.
        with self.assertRaisesRegex(CapabilityDenied, "capability_denied"):
            self.gateway.stage(
                "signed:publisher", "network.http", {"https://api.example"},
                target_profile="native", tick=0
            )
        self.assertEqual(self.host.calls, [])

    def test_parent_grant_is_not_inherited_by_child(self):
        self.broker.issue("g", "parent", "network.http", {"https://api.example"}, delegable=True)
        with self.assertRaisesRegex(CapabilityDenied, "capability_denied"):
            self.gateway.stage(
                "child", "network.http", {"https://api.example"},
                target_profile="web_hardened", tick=0
            )

    def test_delegation_cannot_widen_scope_or_lifetime(self):
        self.broker.issue(
            "g", "parent", "network.http", {"a", "b"}, delegable=True, expires_tick=10
        )
        with self.assertRaisesRegex(CapabilityDenied, "delegation_widens_scope"):
            self.broker.delegate("g", "x", "child", {"a", "c"}, expires_tick=9)
        with self.assertRaisesRegex(CapabilityDenied, "delegation_widens_lifetime"):
            self.broker.delegate("g", "y", "child", {"a"}, expires_tick=11)

    def test_delegation_depth_is_bounded_before_new_grant(self):
        limits = Limits(max_delegation_depth=2, max_grants=10)
        broker = CapabilityBroker({"network.http"}, limits=limits)
        broker.issue("g0", "p0", "network.http", {"a"}, delegable=True)
        broker.delegate("g0", "g1", "p1", {"a"}, delegable=True)
        broker.delegate("g1", "g2", "p2", {"a"}, delegable=True)
        before = set(broker.grants)
        with self.assertRaisesRegex(ResourceLimitExceeded, "delegation_depth_exceeded"):
            broker.delegate("g2", "g3", "p3", {"a"}, delegable=True)
        self.assertEqual(set(broker.grants), before)

    def test_forged_delegation_cycle_is_non_live_and_cannot_authorize(self):
        broker = CapabilityBroker({"network.http"})
        broker.grants["a"] = Grant("a", "p", "network.http", frozenset({"x"}), True, "b")
        broker.grants["b"] = Grant("b", "p", "network.http", frozenset({"x"}), True, "a")
        self.assertFalse(broker.is_live("a", tick=0))
        with self.assertRaisesRegex(CapabilityDenied, "capability_denied"):
            broker.authorize("p", "network.http", {"x"}, tick=0)

    def test_revocation_between_stage_and_flush_fails_before_host(self):
        self.broker.issue("g", "p", "network.http", {"https://api.example"})
        pending = self.gateway.stage(
            "p", "network.http", {"https://api.example"}, target_profile="web_official", tick=0
        )
        self.broker.revoke("g")
        with self.assertRaisesRegex(CapabilityDenied, "capability_denied"):
            self.gateway.flush(pending, tick=0)
        self.assertEqual(self.host.calls, [])

    def test_service_request_flood_is_bounded(self):
        limits = Limits(max_service_requests=2)
        broker = CapabilityBroker({"network.http"}, limits=limits)
        broker.issue("g", "p", "network.http", {"a"})
        gateway = ServiceGateway(broker, HostRecorder(), limits=limits)
        gateway.stage("p", "network.http", {"a"}, target_profile="native", tick=1)
        gateway.stage("p", "network.http", {"a"}, target_profile="native", tick=1)
        with self.assertRaisesRegex(ResourceLimitExceeded, "service_request_budget_exceeded"):
            gateway.stage("p", "network.http", {"a"}, target_profile="native", tick=1)

    def test_explicit_trusted_proxy_validates_child_input(self):
        self.broker.issue("proxy", "parent", "network.http", {"https://fixed"}, delegable=False)
        with self.assertRaisesRegex(CapabilityDenied, "trusted_proxy_input_rejected"):
            trusted_proxy_request(
                self.gateway, child_principal="child", proxy_principal="parent",
                requested_origin="https://evil", allowed_origin="https://fixed",
                target_profile="native", tick=0,
            )
        self.assertEqual(self.host.calls, [])
        pending = trusted_proxy_request(
            self.gateway, child_principal="child", proxy_principal="parent",
            requested_origin="https://fixed", allowed_origin="https://fixed",
            target_profile="native", tick=0,
        )
        self.gateway.flush(pending, tick=0)
        self.assertEqual(self.host.calls[-1][1], "parent")


class ExecutorTests(unittest.TestCase):
    def test_instruction_budget_contains_recursive_repeat(self):
        executor = BudgetedExecutor(Limits(max_instructions=8))
        with self.assertRaisesRegex(ResourceLimitExceeded, "instruction_budget_exceeded"):
            executor.execute([{"op": "repeat", "count": 8, "body": [{"op": "noop"}]}])

    def test_allocation_amplification_is_bounded(self):
        executor = BudgetedExecutor(Limits(max_alloc_units=10))
        with self.assertRaisesRegex(ResourceLimitExceeded, "allocation_budget_exceeded"):
            executor.execute([{"op": "alloc", "units": 11}])

    def test_event_storm_is_bounded(self):
        executor = BudgetedExecutor(Limits(max_emits=3, max_queue=10))
        with self.assertRaisesRegex(ResourceLimitExceeded, "emit_budget_exceeded"):
            executor.execute([{"op": "emit"}] * 4)

    def test_timer_and_queue_storm_is_bounded(self):
        executor = BudgetedExecutor(Limits(max_timers=3, max_queue=3))
        with self.assertRaisesRegex(ResourceLimitExceeded, "timer_budget_exceeded"):
            executor.execute([{"op": "timer"}] * 4)

    def test_unknown_ir_opcode_fails_closed(self):
        with self.assertRaisesRegex(MalformedInput, "unknown_ir_opcode"):
            BudgetedExecutor().execute([{"op": "host_call", "api": "javascript.eval"}])


class MigrationOrderingTests(unittest.TestCase):
    def test_bad_exact_lock_rejects_before_migration(self):
        probe = MigrationProbe()
        with self.assertRaisesRegex(DependencyRejected, "package_digest_substitution"):
            staged_load(
                lock=LockEntry("root", "r1", DIGEST_A, 100),
                observed=Artifact("root", "r1", DIGEST_B, 100),
                dependency_root="root", dependency_graph=dependency_graph(),
                canonical_document=canonical_doc(), migration=probe,
                migration_steps=[{"op": "copy"}],
            )
        self.assertEqual(probe.calls, 0)

    def test_bad_dependency_rejects_before_migration(self):
        probe = MigrationProbe()
        graph = {"root": DependencyNode("root", "r1", 100, ("missing",))}
        with self.assertRaisesRegex(DependencyRejected, "missing_dependency"):
            staged_load(
                lock=LockEntry("root", "r1", DIGEST_A, 100),
                observed=Artifact("root", "r1", DIGEST_A, 100),
                dependency_root="root", dependency_graph=graph,
                canonical_document=canonical_doc(), migration=probe,
                migration_steps=[{"op": "copy"}],
            )
        self.assertEqual(probe.calls, 0)

    def test_migration_cannot_invoke_host_authority(self):
        probe = MigrationProbe()
        with self.assertRaisesRegex(CapabilityDenied, "migration_host_authority_forbidden"):
            staged_load(
                lock=LockEntry("root", "r1", DIGEST_A, 100),
                observed=Artifact("root", "r1", DIGEST_A, 100),
                dependency_root="root", dependency_graph=dependency_graph(),
                canonical_document=canonical_doc(), migration=probe,
                migration_steps=[{"op": "service", "cost": 1}],
            )

    def test_migration_cost_and_output_are_bounded(self):
        probe = MigrationProbe()
        with self.assertRaisesRegex(ResourceLimitExceeded, "migration_cost_exceeded"):
            probe.run([{"op": "copy", "cost": 3}], limits=Limits(max_migration_cost=2))
        with self.assertRaisesRegex(ResourceLimitExceeded, "migration_output_exceeded"):
            probe.run(
                [{"op": "copy", "emit_records": 3}],
                limits=Limits(max_migration_output_records=2)
            )


class NetworkTests(unittest.TestCase):
    def good_message(self):
        return {
            "kind": "event", "sender": "alice", "world": "w", "room": "r",
            "authority_epoch": 3, "payload": {"value": 1},
        }

    def test_nested_remote_capability_injection_rejected(self):
        guard = NetworkGuard()
        msg = self.good_message()
        msg["payload"] = {"nested": {"capability_grant": {"name": "filesystem.raw"}}}
        with self.assertRaisesRegex(MalformedInput, "forbidden_durable_authority_field"):
            guard.validate(
                msg, authenticated_principal="alice", expected_world="w",
                expected_room="r", current_authority_epoch=3, tick=0,
            )

    def test_sender_cross_world_room_and_stale_epoch_rejected(self):
        mutations = [
            ("sender", "mallory", "network_sender_forgery"),
            ("world", "other", "cross_world_message"),
            ("room", "other", "cross_room_message"),
            ("authority_epoch", 2, "stale_or_forged_authority_epoch"),
        ]
        for field, value, error in mutations:
            guard = NetworkGuard()
            msg = self.good_message()
            msg[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(CapabilityDenied, error):
                guard.validate(
                    msg, authenticated_principal="alice", expected_world="w",
                    expected_room="r", current_authority_epoch=3, tick=0,
                )

    def test_network_rate_and_queue_budgets(self):
        limits = Limits(max_network_messages_per_tick=2, max_network_queue=10)
        guard = NetworkGuard(limits)
        for _ in range(2):
            guard.validate(
                self.good_message(), authenticated_principal="alice", expected_world="w",
                expected_room="r", current_authority_epoch=3, tick=0,
            )
        with self.assertRaisesRegex(ResourceLimitExceeded, "network_rate_budget_exceeded"):
            guard.validate(
                self.good_message(), authenticated_principal="alice", expected_world="w",
                expected_room="r", current_authority_epoch=3, tick=0,
            )
        limits2 = Limits(max_network_messages_per_tick=10, max_network_queue=1)
        guard2 = NetworkGuard(limits2)
        guard2.validate(
            self.good_message(), authenticated_principal="alice", expected_world="w",
            expected_room="r", current_authority_epoch=3, tick=0,
        )
        with self.assertRaisesRegex(ResourceLimitExceeded, "network_queue_budget_exceeded"):
            guard2.validate(
                self.good_message(), authenticated_principal="alice", expected_world="w",
                expected_room="r", current_authority_epoch=3, tick=0,
            )


class TargetBoundaryTests(unittest.TestCase):
    def test_target_differences_are_explicit_but_do_not_change_semantic_authority(self):
        self.assertTrue(TARGETS["web_hardened"].hardened)
        self.assertNotIn("javascript.bridge", TARGETS["web_hardened"].physically_exposed)
        self.assertIn("javascript.bridge", TARGETS["web_official"].physically_exposed)
        self.assertIn("native.gdextension", TARGETS["native"].physically_exposed)
        self.assertNotIn("media.camera", TARGETS["headless"].semantic_services)

    def test_raw_api_denial_is_target_independent_even_when_tcb_exposes_api(self):
        broker = CapabilityBroker({"network.http"})
        host = HostRecorder()
        gateway = ServiceGateway(broker, host)
        for target, api in (
            ("web_official", "javascript.bridge"),
            ("native", "native.gdextension"),
            ("headless", "native.process"),
        ):
            with self.subTest(target=target), self.assertRaises(CapabilityDenied):
                gateway.raw_host_call("p", api, target_profile=target)
        self.assertEqual(host.calls, [])


class ProtectedMediaTests(unittest.TestCase):
    def valid_asset(self):
        return AssetRevision(
            "asset:voice", DIGEST_A, "source:master",
            ("container:wav",), ("audio:pcm:48k:stereo",),
            ("author:alice",), "CC-BY-4.0", ("original",),
        )

    def test_partial_protected_media_replacement_fails_without_mutating_old_revision(self):
        current = self.valid_asset()
        broken = replace_asset(current, provenance=())
        with self.assertRaisesRegex(MalformedInput, "incomplete_protected_asset_revision"):
            atomic_replace_asset(current, broken)
        self.assertEqual(current.provenance, ("author:alice",))
        self.assertEqual(current.media_semantics, ("audio:pcm:48k:stereo",))

    def test_decoder_limits_fail_before_host_decoder(self):
        host = HostRecorder()
        too_big = MediaDescriptor(DIGEST_A, 100, 100, "image", width=10000, height=10000)
        with self.assertRaisesRegex(ResourceLimitExceeded, "image_pixel_budget_exceeded"):
            validate_before_decode(too_big, host)
        self.assertEqual(host.decoder_calls, 0)
        ok = MediaDescriptor(DIGEST_A, 100, 1000, "image", width=10, height=10)
        validate_before_decode(ok, host)
        self.assertEqual(host.decoder_calls, 1)


if __name__ == "__main__":
    unittest.main()
