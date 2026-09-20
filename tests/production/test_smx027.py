from __future__ import annotations

import unittest

from splashmx.canonical.core import BehaviourAttachmentId, ThingId
from splashmx.execution.ir import ServiceRequest
from splashmx.security.capabilities import (
    AdmittedServiceCall,
    CapabilityBroker,
    CapabilityError,
    CapabilityGrant,
    CapabilityId,
    CapabilityRequirement,
    CapabilityScope,
    HostServiceAdapter,
    PrincipalId,
    ServiceLimits,
    ServiceTarget,
    TrustedHostServiceBoundary,
    principal_for_service_request,
    validate_untrusted_service_value,
)


def req(*, thing: str = "thing-a", attachment: str = "beh-a", service: str = "network.http", payload=None, request_id: str = "r1", seq: int = 7):
    return ServiceRequest(
        ThingId(thing), BehaviourAttachmentId(attachment), service,
        {} if payload is None else payload, request_id, seq,
    )


def http_scope(*targets: str, operations=("GET",), max_bytes: int | None = 1024) -> CapabilityScope:
    return CapabilityScope(frozenset(targets), frozenset(operations), max_bytes)


def http_target(payload) -> ServiceTarget:
    return ServiceTarget(payload["origin"], payload.get("method", "GET"), payload.get("max_response_bytes", 0))


class CapabilityBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cap = CapabilityId("network.http")
        self.parent = PrincipalId("behaviour:parent:root")
        self.child = PrincipalId("behaviour:thing-a:beh-a")
        self.scope = http_scope("https://api.example.com", operations=("GET", "POST"), max_bytes=4096)

    def test_no_ambient_authority_and_signing_provenance_never_create_grant(self):
        broker = CapabilityBroker()
        target = ServiceTarget("https://api.example.com", "GET", 32)
        with self.assertRaisesRegex(CapabilityError, "no matching capability grant") as caught:
            broker.find_authorized_grant(
                principal_id=self.child, capability_id=self.cap, target=target, now=10
            )
        self.assertEqual(caught.exception.code, "capability.denied")
        validate_untrusted_service_value({"signed_by": "publisher", "provenance": "authentic", "licence": "EUPL"})
        with self.assertRaises(CapabilityError):
            broker.find_authorized_grant(
                principal_id=self.child, capability_id=self.cap, target=target, now=10
            )

    def test_parent_or_containment_grant_does_not_authorize_child_principal(self):
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="g-parent", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1,
        )
        with self.assertRaises(CapabilityError) as caught:
            broker.find_authorized_grant(
                principal_id=self.child, capability_id=self.cap,
                target=ServiceTarget("https://api.example.com", "GET", 32), now=2,
            )
        self.assertEqual(caught.exception.code, "capability.denied")

    def test_scope_target_operation_and_byte_ceiling_are_all_enforced(self):
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="g", principal_id=self.child, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1,
        )
        broker.find_authorized_grant(
            principal_id=self.child, capability_id=self.cap,
            target=ServiceTarget("https://api.example.com", "POST", 4096), now=2,
        )
        for denied in (
            ServiceTarget("https://evil.example", "GET", 1),
            ServiceTarget("https://api.example.com", "DELETE", 1),
            ServiceTarget("https://api.example.com", "GET", 4097),
        ):
            with self.assertRaises(CapabilityError) as caught:
                broker.find_authorized_grant(
                    principal_id=self.child, capability_id=self.cap, target=denied, now=2
                )
            self.assertEqual(caught.exception.code, "capability.scope_denied")

    def test_delegation_is_monotonic_and_lifetime_cannot_widen(self):
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="root", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1, expires_at=100,
            delegable=True,
        )
        child_scope = http_scope("https://api.example.com", operations=("GET",), max_bytes=512)
        delegated = broker.delegate(
            parent_grant_id="root", grant_id="child", principal_id=self.child,
            scope=child_scope, issued_at=2, expires_at=80, delegable=False,
        )
        self.assertEqual(delegated.capability_id, self.cap)
        self.assertEqual(delegated.parent_grant_id, "root")
        with self.assertRaises(CapabilityError) as wide_scope:
            broker.delegate(
                parent_grant_id="root", grant_id="wide", principal_id=self.child,
                scope=http_scope("https://evil.example"), issued_at=2, expires_at=80,
            )
        self.assertEqual(wide_scope.exception.code, "capability.scope_escalation")
        with self.assertRaises(CapabilityError) as wide_lifetime:
            broker.delegate(
                parent_grant_id="root", grant_id="late", principal_id=self.child,
                scope=child_scope, issued_at=2, expires_at=101,
            )
        self.assertEqual(wide_lifetime.exception.code, "capability.lifetime_escalation")
        with self.assertRaises(CapabilityError) as no_further:
            broker.delegate(
                parent_grant_id="child", grant_id="grandchild",
                principal_id=PrincipalId("behaviour:grand:child"), scope=child_scope,
                issued_at=3, expires_at=70,
            )
        self.assertEqual(no_further.exception.code, "capability.not_delegable")

    def test_delegation_depth_and_count_fail_before_new_grant_is_allocated(self):
        narrow = http_scope("https://api.example.com", operations=("GET",), max_bytes=128)
        broker = CapabilityBroker(max_delegation_depth=1, max_descendants_per_root=8)
        broker.issue_root_grant(
            grant_id="root", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1, delegable=True,
        )
        broker.delegate(
            parent_grant_id="root", grant_id="child", principal_id=self.child,
            scope=narrow, issued_at=2, delegable=True,
        )
        with self.assertRaises(CapabilityError) as depth:
            broker.delegate(
                parent_grant_id="child", grant_id="too-deep",
                principal_id=PrincipalId("behaviour:deep:x"), scope=narrow, issued_at=3,
            )
        self.assertEqual(depth.exception.code, "capability.delegation_depth")
        with self.assertRaises(CapabilityError) as absent:
            broker.grant("too-deep")
        self.assertEqual(absent.exception.code, "capability.unknown_grant")

        counted = CapabilityBroker(max_delegation_depth=4, max_descendants_per_root=1)
        counted.issue_root_grant(
            grant_id="root", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1, delegable=True,
        )
        counted.delegate(
            parent_grant_id="root", grant_id="one", principal_id=self.child,
            scope=narrow, issued_at=2,
        )
        with self.assertRaises(CapabilityError) as count:
            counted.delegate(
                parent_grant_id="root", grant_id="two",
                principal_id=PrincipalId("behaviour:thing-b:beh-b"), scope=narrow, issued_at=2,
            )
        self.assertEqual(count.exception.code, "capability.delegation_count")
        with self.assertRaises(CapabilityError):
            counted.grant("two")

    def test_trusted_snapshot_rejects_missing_and_cyclic_ancestry_boundedly(self):
        rootish = CapabilityGrant(
            "a", self.child, self.cap, self.scope, "policy", 1,
            parent_grant_id="missing",
        )
        with self.assertRaises(CapabilityError) as missing:
            CapabilityBroker.from_trusted_grants([rootish])
        self.assertEqual(missing.exception.code, "capability.missing_ancestry")

        a = CapabilityGrant(
            "a", self.child, self.cap, self.scope, "policy", 1,
            delegable=True, parent_grant_id="b",
        )
        b = CapabilityGrant(
            "b", self.child, self.cap, self.scope, "policy", 1,
            delegable=True, parent_grant_id="a",
        )
        with self.assertRaises(CapabilityError) as cycle:
            CapabilityBroker.from_trusted_grants([a, b])
        self.assertEqual(cycle.exception.code, "capability.cyclic_ancestry")

    def test_revocation_and_expiry_of_ancestor_invalidate_delegated_lease(self):
        narrow = http_scope("https://api.example.com", operations=("GET",), max_bytes=128)
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="root", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1,
            expires_at=50, delegable=True,
        )
        broker.delegate(
            parent_grant_id="root", grant_id="child", principal_id=self.child,
            scope=narrow, issued_at=2, expires_at=40,
        )
        target = ServiceTarget("https://api.example.com", "GET", 32)
        broker.authorize_grant("child", principal_id=self.child, capability_id=self.cap, target=target, now=3)
        broker.revoke("root")
        with self.assertRaises(CapabilityError) as revoked:
            broker.authorize_grant("child", principal_id=self.child, capability_id=self.cap, target=target, now=4)
        self.assertEqual(revoked.exception.code, "capability.revoked")

        expiring = CapabilityBroker()
        expiring.issue_root_grant(
            grant_id="root", principal_id=self.parent, capability_id=self.cap,
            scope=self.scope, issuer_policy_id="policy", issued_at=1,
            expires_at=5, delegable=True,
        )
        expiring.delegate(
            parent_grant_id="root", grant_id="child", principal_id=self.child,
            scope=narrow, issued_at=2, expires_at=5,
        )
        with self.assertRaises(CapabilityError) as expired:
            expiring.authorize_grant("child", principal_id=self.child, capability_id=self.cap, target=target, now=5)
        self.assertEqual(expired.exception.code, "capability.expired")

    def test_required_denial_fails_and_optional_denial_selects_explicit_reduced_mode(self):
        broker = CapabilityBroker()
        camera = CapabilityRequirement(
            CapabilityId("media.camera"),
            CapabilityScope(frozenset({"user"}), frozenset({"capture"}), None),
            required=False,
            reduced_mode="avatar-only",
        )
        plan = broker.resolve_requirements(self.child, [camera], now=1)
        self.assertEqual(tuple(map(str, plan.optional_denied)), ("media.camera",))
        self.assertEqual(plan.reduced_modes, ("avatar-only",))
        required = CapabilityRequirement(self.cap, self.scope, required=True)
        with self.assertRaises(CapabilityError) as caught:
            broker.resolve_requirements(self.child, [required], now=1)
        self.assertEqual(caught.exception.code, "capability.required_denied")


class HostBoundaryTests(unittest.TestCase):
    def make_boundary(self, *, calls=None, limits=None, expiry=None):
        calls = [] if calls is None else calls
        broker = CapabilityBroker()
        request = req(payload={"origin": "https://api.example.com", "method": "GET", "max_response_bytes": 64})
        principal = principal_for_service_request(request)
        broker.issue_root_grant(
            grant_id="http-grant", principal_id=principal, capability_id=CapabilityId("network.http"),
            scope=http_scope("https://api.example.com", max_bytes=128),
            issuer_policy_id="host-policy", issued_at=1, expires_at=expiry,
        )
        adapter = HostServiceAdapter(
            "network.http", CapabilityId("network.http"), http_target,
            lambda payload: calls.append(dict(payload)) or {"status": 200, "body": "ok"},
        )
        return request, broker, TrustedHostServiceBoundary(broker, [adapter], limits=limits), calls

    def test_service_request_principal_is_exact_thing_attachment_origin(self):
        request = req()
        self.assertEqual(
            principal_for_service_request(request),
            PrincipalId("behaviour:thing-a:beh-a"),
        )
        other = req(attachment="beh-b")
        self.assertNotEqual(principal_for_service_request(request), principal_for_service_request(other))

    def test_parent_grant_cannot_be_used_as_confused_deputy_for_child_request(self):
        request = req(payload={"origin": "https://api.example.com", "method": "GET"})
        broker = CapabilityBroker()
        broker.issue_root_grant(
            grant_id="parent", principal_id=PrincipalId("behaviour:parent:root"),
            capability_id=CapabilityId("network.http"), scope=http_scope("https://api.example.com"),
            issuer_policy_id="host", issued_at=1,
        )
        boundary = TrustedHostServiceBoundary(
            broker,
            [HostServiceAdapter("network.http", CapabilityId("network.http"), http_target, lambda _: "bad")],
        )
        with self.assertRaises(CapabilityError) as caught:
            boundary.admit(request, now=2)
        self.assertEqual(caught.exception.code, "capability.denied")

    def test_admission_never_invokes_host_and_execute_crosses_only_after_authorization(self):
        request, broker, boundary, calls = self.make_boundary()
        admitted = boundary.admit(request, now=2)
        self.assertIsInstance(admitted, AdmittedServiceCall)
        self.assertEqual(calls, [])
        result = boundary.execute(admitted, now=3)
        self.assertEqual(calls, [request.payload])
        self.assertEqual(result, {"status": 200, "body": "ok"})
        with self.assertRaises(CapabilityError) as replay:
            boundary.execute(admitted, now=3)
        self.assertEqual(replay.exception.code, "capability.stale_call")

    def test_revocation_between_admission_and_host_crossing_fails_closed(self):
        request, broker, boundary, calls = self.make_boundary()
        admitted = boundary.admit(request, now=2)
        broker.revoke("http-grant")
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(admitted, now=3)
        self.assertEqual(caught.exception.code, "capability.revoked")
        self.assertEqual(calls, [])
        with self.assertRaises(CapabilityError):
            boundary.execute(admitted, now=3)

    def test_expiry_between_admission_and_host_crossing_fails_closed(self):
        request, broker, boundary, calls = self.make_boundary(expiry=5)
        admitted = boundary.admit(request, now=4)
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(admitted, now=5)
        self.assertEqual(caught.exception.code, "capability.expired")
        self.assertEqual(calls, [])

    def test_recursive_serialized_authority_is_rejected_again_at_service_boundary(self):
        request, broker, boundary, calls = self.make_boundary()
        hostile = req(payload={
            "origin": "https://api.example.com",
            "nested": [{"Capability-Grant": {"grant_id": "http-grant"}}],
        })
        with self.assertRaises(CapabilityError) as caught:
            boundary.admit(hostile, now=2)
        self.assertEqual(caught.exception.code, "capability.serialized_authority")
        self.assertEqual(calls, [])

    def test_copying_grant_id_in_payload_cannot_launder_authority(self):
        request, broker, boundary, calls = self.make_boundary()
        attacker = req(attachment="no-grant", payload={
            "origin": "https://api.example.com", "grant_id": "http-grant"
        })
        with self.assertRaises(CapabilityError) as caught:
            boundary.admit(attacker, now=2)
        self.assertEqual(caught.exception.code, "capability.serialized_authority")
        self.assertEqual(calls, [])

    def test_service_request_quota_is_principal_scoped_and_checked_before_admission(self):
        limits = ServiceLimits(max_pending_per_principal=1, max_admissions_per_window=2)
        request, broker, boundary, calls = self.make_boundary(limits=limits)
        first = boundary.admit(request, now=2)
        second_request = req(request_id="r2", seq=8, payload=request.payload)
        with self.assertRaises(CapabilityError) as pending:
            boundary.admit(second_request, now=2)
        self.assertEqual(pending.exception.code, "capability.pending_service_quota")
        boundary.cancel(first)
        second = boundary.admit(second_request, now=2)
        boundary.cancel(second)
        third_request = req(request_id="r3", seq=9, payload=request.payload)
        with self.assertRaises(CapabilityError) as rate:
            boundary.admit(third_request, now=2)
        self.assertEqual(rate.exception.code, "capability.service_rate_quota")
        boundary.reset_quota_window()
        third = boundary.admit(third_request, now=2)
        boundary.cancel(third)

    def test_unknown_service_and_scope_violation_fail_before_host_use(self):
        request, broker, boundary, calls = self.make_boundary()
        unknown = req(service="filesystem.raw", payload={"origin": "https://api.example.com"})
        with self.assertRaises(CapabilityError) as missing:
            boundary.admit(unknown, now=2)
        self.assertEqual(missing.exception.code, "capability.unknown_service")
        outside = req(payload={"origin": "https://evil.example", "method": "GET", "max_response_bytes": 1})
        with self.assertRaises(CapabilityError) as scope:
            boundary.admit(outside, now=2)
        self.assertEqual(scope.exception.code, "capability.scope_denied")
        self.assertEqual(calls, [])

    def test_raw_host_object_result_is_not_returned_to_content(self):
        class HostObject:
            pass

        request = req(payload={"origin": "https://api.example.com", "method": "GET"})
        broker = CapabilityBroker()
        principal = principal_for_service_request(request)
        broker.issue_root_grant(
            grant_id="g", principal_id=principal, capability_id=CapabilityId("network.http"),
            scope=http_scope("https://api.example.com"), issuer_policy_id="host", issued_at=1,
        )
        boundary = TrustedHostServiceBoundary(
            broker,
            [HostServiceAdapter("network.http", CapabilityId("network.http"), http_target, lambda _: HostObject())],
        )
        admitted = boundary.admit(request, now=2)
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(admitted, now=2)
        self.assertEqual(caught.exception.code, "capability.invalid_value")

    def test_raw_host_exception_is_wrapped_in_typed_failure(self):
        request = req(payload={"origin": "https://api.example.com", "method": "GET"})
        broker = CapabilityBroker()
        principal = principal_for_service_request(request)
        broker.issue_root_grant(
            grant_id="g", principal_id=principal, capability_id=CapabilityId("network.http"),
            scope=http_scope("https://api.example.com"), issuer_policy_id="host", issued_at=1,
        )
        def boom(_):
            raise RuntimeError("secret host detail")
        boundary = TrustedHostServiceBoundary(
            broker,
            [HostServiceAdapter("network.http", CapabilityId("network.http"), http_target, boom)],
        )
        admitted = boundary.admit(request, now=2)
        with self.assertRaises(CapabilityError) as caught:
            boundary.execute(admitted, now=2)
        self.assertEqual(caught.exception.code, "capability.host_service_failed")
        self.assertNotIn("secret host detail", str(caught.exception))

    def test_untrusted_payload_cannot_smuggle_raw_engine_browser_or_session_handles(self):
        for key in ("NodePath", "JavaScriptBridge", "process_handle", "session-id", "native_handle"):
            with self.subTest(key=key):
                with self.assertRaises(CapabilityError) as caught:
                    validate_untrusted_service_value({"safe": [{key: "x"}]})
                self.assertEqual(caught.exception.code, "capability.serialized_authority")


if __name__ == "__main__":
    unittest.main()
