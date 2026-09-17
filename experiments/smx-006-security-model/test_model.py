from __future__ import annotations

import unittest

from model import (
    ArchiveEntry,
    CapabilityBroker,
    CapabilityDenied,
    CapabilityRequirement,
    DelegationDenied,
    MalformedInput,
    PackageLimits,
    PackageMetadata,
    ResourceLimitExceeded,
    effective_capabilities_for_package,
    validate_dependency_and_migration_budget,
    validate_network_message,
    validate_package,
    validate_required_security_features,
)


HTTP_SCOPE = {
    "origins": ["https://api.example.com"],
    "methods": ["GET"],
    "path_prefixes": ["/public/"],
    "max_response_bytes": 1024,
}


class SecurityModelTests(unittest.TestCase):
    def broker(self, *, per_tick_service_limit: int = 4) -> CapabilityBroker:
        return CapabilityBroker(
            supported_capabilities={
                "network.http",
                "clipboard.write",
                "media.camera",
                "storage.save",
            },
            per_tick_service_limit=per_tick_service_limit,
        )

    def test_st001_no_ambient_authority_from_parent(self) -> None:
        broker = self.broker()
        broker.issue_grant(
            grant_id="g-parent",
            principal_id="component:parent",
            name="network.http",
            scope=HTTP_SCOPE,
            delegable=True,
        )
        with self.assertRaises(CapabilityDenied):
            broker.request_service(
                principal_id="component:child",
                capability_name="network.http",
                requested_scope={
                    "origins": ["https://api.example.com"],
                    "methods": ["GET"],
                    "path_prefixes": ["/public/"],
                    "max_response_bytes": 512,
                },
                tick=1,
            )

    def test_st002_http_scope_is_enforced(self) -> None:
        broker = self.broker()
        broker.issue_grant(
            grant_id="g-http",
            principal_id="component:weather",
            name="network.http",
            scope=HTTP_SCOPE,
        )
        self.assertEqual(
            broker.request_service(
                principal_id="component:weather",
                capability_name="network.http",
                requested_scope={
                    "origins": ["https://api.example.com"],
                    "methods": ["GET"],
                    "path_prefixes": ["/public/"],
                    "max_response_bytes": 512,
                },
                tick=1,
            ),
            "service-ok:network.http",
        )
        for bad_scope in (
            {**HTTP_SCOPE, "origins": ["https://evil.example"]},
            {**HTTP_SCOPE, "methods": ["POST"]},
            {**HTTP_SCOPE, "path_prefixes": ["/private/"]},
            {**HTTP_SCOPE, "max_response_bytes": 2048},
        ):
            with self.assertRaises(CapabilityDenied):
                broker.authorize(
                    principal_id="component:weather",
                    name="network.http",
                    requested_scope=bad_scope,
                    tick=1,
                )

    def test_st003_nested_component_requires_explicit_delegation(self) -> None:
        broker = self.broker()
        broker.issue_grant(
            grant_id="g-parent",
            principal_id="component:parent",
            name="network.http",
            scope=HTTP_SCOPE,
            delegable=True,
        )
        with self.assertRaises(CapabilityDenied):
            broker.authorize(
                principal_id="component:child",
                name="network.http",
                requested_scope=HTTP_SCOPE,
            )
        broker.delegate(
            source_grant_id="g-parent",
            new_grant_id="g-child",
            child_principal_id="component:child",
            scope={
                "origins": ["https://api.example.com"],
                "methods": ["GET"],
                "path_prefixes": ["/public/"],
                "max_response_bytes": 256,
            },
        )
        self.assertIsNotNone(
            broker.authorize(
                principal_id="component:child",
                name="network.http",
                requested_scope={
                    "origins": ["https://api.example.com"],
                    "methods": ["GET"],
                    "path_prefixes": ["/public/"],
                    "max_response_bytes": 128,
                },
            )
        )

    def test_st004_delegation_cannot_widen_or_use_nondelegable_grant(self) -> None:
        broker = self.broker()
        broker.issue_grant(
            grant_id="g-nondelegable",
            principal_id="component:a",
            name="network.http",
            scope=HTTP_SCOPE,
            delegable=False,
        )
        with self.assertRaises(DelegationDenied):
            broker.delegate(
                source_grant_id="g-nondelegable",
                new_grant_id="g-child-a",
                child_principal_id="component:b",
                scope=HTTP_SCOPE,
            )

        broker.issue_grant(
            grant_id="g-delegable",
            principal_id="component:a",
            name="network.http",
            scope=HTTP_SCOPE,
            delegable=True,
            expires_tick=10,
        )
        with self.assertRaises(DelegationDenied):
            broker.delegate(
                source_grant_id="g-delegable",
                new_grant_id="g-child-b",
                child_principal_id="component:b",
                scope={**HTTP_SCOPE, "methods": ["GET", "POST"]},
                expires_tick=9,
            )
        with self.assertRaises(DelegationDenied):
            broker.delegate(
                source_grant_id="g-delegable",
                new_grant_id="g-child-c",
                child_principal_id="component:b",
                scope=HTTP_SCOPE,
                expires_tick=11,
            )

    def test_st005_revocation_invalidates_descendants(self) -> None:
        broker = self.broker()
        broker.issue_grant(
            grant_id="g-root",
            principal_id="component:root",
            name="network.http",
            scope=HTTP_SCOPE,
            delegable=True,
        )
        broker.delegate(
            source_grant_id="g-root",
            new_grant_id="g-child",
            child_principal_id="component:child",
            scope=HTTP_SCOPE,
            delegable=True,
        )
        broker.delegate(
            source_grant_id="g-child",
            new_grant_id="g-grandchild",
            child_principal_id="component:grandchild",
            scope=HTTP_SCOPE,
        )
        self.assertIsNotNone(
            broker.authorize(
                principal_id="component:grandchild",
                name="network.http",
                requested_scope=HTTP_SCOPE,
            )
        )
        broker.revoke("g-root")
        with self.assertRaises(CapabilityDenied):
            broker.authorize(
                principal_id="component:grandchild",
                name="network.http",
                requested_scope=HTTP_SCOPE,
            )

    def test_st006_required_and_optional_capabilities_differ(self) -> None:
        broker = self.broker()
        missing_required, missing_optional = broker.evaluate_requirements(
            principal_id="component:camera-widget",
            requirements=[
                CapabilityRequirement("media.camera", {"facing": "user"}, required=True),
                CapabilityRequirement("clipboard.write", {"mime_types": ["text/plain"]}, required=False),
            ],
        )
        self.assertEqual(missing_required, ["media.camera"])
        self.assertEqual(missing_optional, ["clipboard.write"])

        broker.issue_grant(
            grant_id="g-camera",
            principal_id="component:camera-widget",
            name="media.camera",
            scope={"facing": "user"},
        )
        missing_required, missing_optional = broker.evaluate_requirements(
            principal_id="component:camera-widget",
            requirements=[
                CapabilityRequirement("media.camera", {"facing": "user"}, required=True),
                CapabilityRequirement("clipboard.write", {"mime_types": ["text/plain"]}, required=False),
            ],
        )
        self.assertEqual(missing_required, [])
        self.assertEqual(missing_optional, ["clipboard.write"])

    def test_st007_package_parser_blocks_traversal_duplicates_and_bombs(self) -> None:
        limits = PackageLimits()
        good = [
            ArchiveEntry("manifest.json", 100, 200),
            ArchiveEntry("assets/image.bin", 1000, 1500),
        ]
        self.assertEqual(validate_package(good, limits), ["assets/image.bin", "manifest.json"])

        for bad in (
            [ArchiveEntry("../escape", 10, 10)],
            [ArchiveEntry("/absolute", 10, 10)],
            [ArchiveEntry("C:/device", 10, 10)],
            [ArchiveEntry("a//b", 10, 10)],
            [ArchiveEntry("same", 10, 10), ArchiveEntry("same", 10, 10)],
        ):
            with self.assertRaises(MalformedInput):
                validate_package(bad, limits)

        with self.assertRaises(ResourceLimitExceeded):
            validate_package([ArchiveEntry("bomb.bin", 1, 1000)], limits)

    def test_st008_dependency_and_migration_amplification_is_bounded(self) -> None:
        validate_dependency_and_migration_budget(
            dependency_depth=2,
            migration_steps=3,
            migration_cost=100,
            migration_output_records=100,
        )
        for kwargs in (
            dict(dependency_depth=99, migration_steps=1, migration_cost=1, migration_output_records=1),
            dict(dependency_depth=1, migration_steps=99, migration_cost=1, migration_output_records=1),
            dict(dependency_depth=1, migration_steps=1, migration_cost=99_999, migration_output_records=1),
            dict(dependency_depth=1, migration_steps=1, migration_cost=1, migration_output_records=99_999),
        ):
            with self.assertRaises(ResourceLimitExceeded):
                validate_dependency_and_migration_budget(**kwargs)

    def test_st009_signature_does_not_grant_capability(self) -> None:
        broker = self.broker()
        unsigned = PackageMetadata("pkg:a", None)
        signed = PackageMetadata("pkg:b", "publisher:key")
        self.assertEqual(effective_capabilities_for_package(unsigned, broker, "pkg:a"), set())
        self.assertEqual(effective_capabilities_for_package(signed, broker, "pkg:b"), set())

        broker.issue_grant(
            grant_id="g-save",
            principal_id="pkg:b",
            name="storage.save",
            scope={"namespace": "current_creation", "max_bytes": 1024},
        )
        self.assertEqual(effective_capabilities_for_package(signed, broker, "pkg:b"), {"storage.save"})

    def test_st010_network_cannot_inject_host_authority(self) -> None:
        validate_network_message({"kind": "application", "payload": {"x": 1}})
        with self.assertRaises(MalformedInput):
            validate_network_message({"kind": "capability_grant", "payload": {}})
        with self.assertRaises(MalformedInput):
            validate_network_message({"kind": "application", "grant_id": "g-root", "payload": {}})
        with self.assertRaises(ResourceLimitExceeded):
            validate_network_message({"kind": "application", "payload": "x" * 5000}, max_bytes=256)

    def test_st011_service_request_quota_is_per_principal(self) -> None:
        broker = self.broker(per_tick_service_limit=2)
        broker.issue_grant(
            grant_id="g-http",
            principal_id="component:client",
            name="network.http",
            scope=HTTP_SCOPE,
        )
        for _ in range(2):
            broker.request_service(
                principal_id="component:client",
                capability_name="network.http",
                requested_scope=HTTP_SCOPE,
                tick=5,
            )
        with self.assertRaises(ResourceLimitExceeded):
            broker.request_service(
                principal_id="component:client",
                capability_name="network.http",
                requested_scope=HTTP_SCOPE,
                tick=5,
            )
        # New tick gets a fresh bounded window.
        broker.request_service(
            principal_id="component:client",
            capability_name="network.http",
            requested_scope=HTTP_SCOPE,
            tick=6,
        )

    def test_st012_unknown_required_security_feature_fails_closed(self) -> None:
        validate_required_security_features(
            ["capabilities.v1", "bounded-parser.v1"],
            ["capabilities.v1", "bounded-parser.v1"],
        )
        with self.assertRaises(MalformedInput):
            validate_required_security_features(
                ["capabilities.v1", "native-host-escape.v99"],
                ["capabilities.v1", "bounded-parser.v1"],
            )


if __name__ == "__main__":
    unittest.main()
