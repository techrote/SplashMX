from __future__ import annotations

from dataclasses import dataclass, field
import json
import posixpath
from typing import Any, Iterable


class SecurityError(Exception):
    pass


class CapabilityDenied(SecurityError):
    pass


class DelegationDenied(SecurityError):
    pass


class ResourceLimitExceeded(SecurityError):
    pass


class MalformedInput(SecurityError):
    pass


@dataclass(frozen=True)
class CapabilityRequirement:
    name: str
    scope: dict[str, Any] = field(default_factory=dict)
    required: bool = True


@dataclass
class CapabilityGrant:
    grant_id: str
    principal_id: str
    name: str
    scope: dict[str, Any]
    delegable: bool = False
    parent_grant_id: str | None = None
    expires_tick: int | None = None
    revoked: bool = False


def _as_set(value: Any) -> set[Any]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set, frozenset)):
        return set(value)
    return {value}


def scope_contains(parent: dict[str, Any], requested: dict[str, Any]) -> bool:
    """Return True when requested authority is no wider than parent authority.

    This is a research-only typed subset relation. Collection fields narrow by
    set inclusion; max_* integer fields narrow by <=; scalar fields must match.
    """
    for key, req_value in requested.items():
        if key not in parent:
            return False
        parent_value = parent[key]
        if key.startswith("max_") and isinstance(req_value, int) and isinstance(parent_value, int):
            if req_value > parent_value:
                return False
        elif isinstance(parent_value, (list, tuple, set, frozenset)):
            if not _as_set(req_value).issubset(_as_set(parent_value)):
                return False
        else:
            if req_value != parent_value:
                return False
    return True


class CapabilityBroker:
    def __init__(self, *, supported_capabilities: Iterable[str], per_tick_service_limit: int = 4):
        self.supported_capabilities = set(supported_capabilities)
        self.per_tick_service_limit = per_tick_service_limit
        self.grants: dict[str, CapabilityGrant] = {}
        self._service_counts: dict[tuple[int, str], int] = {}

    def issue_grant(
        self,
        *,
        grant_id: str,
        principal_id: str,
        name: str,
        scope: dict[str, Any] | None = None,
        delegable: bool = False,
        expires_tick: int | None = None,
    ) -> CapabilityGrant:
        if name not in self.supported_capabilities:
            raise CapabilityDenied(f"unsupported capability: {name}")
        if grant_id in self.grants:
            raise SecurityError(f"duplicate grant id: {grant_id}")
        grant = CapabilityGrant(
            grant_id=grant_id,
            principal_id=principal_id,
            name=name,
            scope=dict(scope or {}),
            delegable=delegable,
            expires_tick=expires_tick,
        )
        self.grants[grant_id] = grant
        return grant

    def _is_live(self, grant: CapabilityGrant, *, tick: int) -> bool:
        if grant.revoked:
            return False
        if grant.expires_tick is not None and tick > grant.expires_tick:
            return False
        if grant.parent_grant_id is not None:
            parent = self.grants.get(grant.parent_grant_id)
            return parent is not None and self._is_live(parent, tick=tick)
        return True

    def matching_grant(
        self,
        *,
        principal_id: str,
        name: str,
        requested_scope: dict[str, Any] | None = None,
        tick: int = 0,
    ) -> CapabilityGrant | None:
        requested_scope = dict(requested_scope or {})
        for grant in self.grants.values():
            if grant.principal_id != principal_id or grant.name != name:
                continue
            if not self._is_live(grant, tick=tick):
                continue
            if scope_contains(grant.scope, requested_scope):
                return grant
        return None

    def authorize(
        self,
        *,
        principal_id: str,
        name: str,
        requested_scope: dict[str, Any] | None = None,
        tick: int = 0,
    ) -> CapabilityGrant:
        if name not in self.supported_capabilities:
            raise CapabilityDenied(f"unsupported capability: {name}")
        grant = self.matching_grant(
            principal_id=principal_id,
            name=name,
            requested_scope=requested_scope,
            tick=tick,
        )
        if grant is None:
            raise CapabilityDenied(f"{principal_id} lacks {name} for requested scope")
        return grant

    def delegate(
        self,
        *,
        source_grant_id: str,
        new_grant_id: str,
        child_principal_id: str,
        scope: dict[str, Any],
        delegable: bool = False,
        expires_tick: int | None = None,
        tick: int = 0,
    ) -> CapabilityGrant:
        source = self.grants.get(source_grant_id)
        if source is None or not self._is_live(source, tick=tick):
            raise DelegationDenied("source grant is absent or inactive")
        if not source.delegable:
            raise DelegationDenied("source grant is not delegable")
        if not scope_contains(source.scope, scope):
            raise DelegationDenied("delegated scope would widen authority")
        if source.expires_tick is not None:
            if expires_tick is None or expires_tick > source.expires_tick:
                raise DelegationDenied("delegated lifetime would exceed source")
        if new_grant_id in self.grants:
            raise DelegationDenied("duplicate delegated grant id")
        grant = CapabilityGrant(
            grant_id=new_grant_id,
            principal_id=child_principal_id,
            name=source.name,
            scope=dict(scope),
            delegable=delegable,
            parent_grant_id=source.grant_id,
            expires_tick=expires_tick,
        )
        self.grants[new_grant_id] = grant
        return grant

    def revoke(self, grant_id: str) -> None:
        grant = self.grants.get(grant_id)
        if grant is None:
            return
        grant.revoked = True

    def evaluate_requirements(
        self,
        *,
        principal_id: str,
        requirements: Iterable[CapabilityRequirement],
        tick: int = 0,
    ) -> tuple[list[str], list[str]]:
        missing_required: list[str] = []
        missing_optional: list[str] = []
        for req in requirements:
            found = self.matching_grant(
                principal_id=principal_id,
                name=req.name,
                requested_scope=req.scope,
                tick=tick,
            )
            if found is None:
                (missing_required if req.required else missing_optional).append(req.name)
        return missing_required, missing_optional

    def request_service(
        self,
        *,
        principal_id: str,
        capability_name: str,
        requested_scope: dict[str, Any],
        tick: int,
    ) -> str:
        self.authorize(
            principal_id=principal_id,
            name=capability_name,
            requested_scope=requested_scope,
            tick=tick,
        )
        key = (tick, principal_id)
        count = self._service_counts.get(key, 0) + 1
        if count > self.per_tick_service_limit:
            raise ResourceLimitExceeded("per-principal service request quota exceeded")
        self._service_counts[key] = count
        return f"service-ok:{capability_name}"


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    compressed_bytes: int
    expanded_bytes: int


@dataclass(frozen=True)
class PackageLimits:
    max_entries: int = 64
    max_compressed_bytes: int = 2_000_000
    max_expanded_bytes: int = 8_000_000
    max_single_entry_bytes: int = 4_000_000
    max_expansion_ratio: int = 20
    max_path_length: int = 240
    max_dependency_depth: int = 8
    max_migration_steps: int = 16
    max_migration_cost: int = 10_000
    max_migration_output_records: int = 20_000


def normalize_package_path(path: str, *, max_path_length: int) -> str:
    if not isinstance(path, str) or not path:
        raise MalformedInput("empty package path")
    if len(path) > max_path_length:
        raise ResourceLimitExceeded("path too long")
    if "\x00" in path:
        raise MalformedInput("NUL in package path")
    path = path.replace("\\", "/")
    if path.startswith("/"):
        raise MalformedInput("absolute path")
    if len(path) >= 2 and path[1] == ":":
        raise MalformedInput("drive-qualified path")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise MalformedInput("ambiguous or traversing path segment")
    normalized = posixpath.normpath(path)
    if normalized.startswith("../") or normalized == "..":
        raise MalformedInput("path traversal")
    return normalized


def validate_package(entries: Iterable[ArchiveEntry], limits: PackageLimits = PackageLimits()) -> list[str]:
    entries = list(entries)
    if len(entries) > limits.max_entries:
        raise ResourceLimitExceeded("too many package entries")

    total_compressed = 0
    total_expanded = 0
    normalized_paths: set[str] = set()

    for entry in entries:
        path = normalize_package_path(entry.path, max_path_length=limits.max_path_length)
        if path in normalized_paths:
            raise MalformedInput("duplicate normalized package path")
        normalized_paths.add(path)

        if entry.compressed_bytes < 0 or entry.expanded_bytes < 0:
            raise MalformedInput("negative size")
        if entry.expanded_bytes > limits.max_single_entry_bytes:
            raise ResourceLimitExceeded("single entry too large")
        if entry.compressed_bytes == 0:
            if entry.expanded_bytes > 0:
                raise ResourceLimitExceeded("infinite/undefined expansion ratio")
        elif entry.expanded_bytes > entry.compressed_bytes * limits.max_expansion_ratio:
            raise ResourceLimitExceeded("expansion ratio exceeded")

        total_compressed += entry.compressed_bytes
        total_expanded += entry.expanded_bytes

    if total_compressed > limits.max_compressed_bytes:
        raise ResourceLimitExceeded("compressed package too large")
    if total_expanded > limits.max_expanded_bytes:
        raise ResourceLimitExceeded("expanded package too large")

    return sorted(normalized_paths)


def validate_dependency_and_migration_budget(
    *,
    dependency_depth: int,
    migration_steps: int,
    migration_cost: int,
    migration_output_records: int,
    limits: PackageLimits = PackageLimits(),
) -> None:
    if dependency_depth > limits.max_dependency_depth:
        raise ResourceLimitExceeded("dependency depth exceeded")
    if migration_steps > limits.max_migration_steps:
        raise ResourceLimitExceeded("migration chain exceeded")
    if migration_cost > limits.max_migration_cost:
        raise ResourceLimitExceeded("migration cost exceeded")
    if migration_output_records > limits.max_migration_output_records:
        raise ResourceLimitExceeded("migration output record limit exceeded")


@dataclass(frozen=True)
class PackageMetadata:
    package_id: str
    signed_by: str | None = None


def effective_capabilities_for_package(metadata: PackageMetadata, broker: CapabilityBroker, principal_id: str) -> set[str]:
    # Authenticity/provenance never changes authority.
    return {
        grant.name
        for grant in broker.grants.values()
        if grant.principal_id == principal_id and broker._is_live(grant, tick=0)
    }


RESERVED_NETWORK_FIELDS = {"capability_grant", "grant_id", "host_handle", "native_handle"}
ALLOWED_NETWORK_KINDS = {"application", "state", "event", "command"}


def validate_network_message(
    message: dict[str, Any],
    *,
    max_bytes: int = 4096,
    allowed_kinds: set[str] | None = None,
) -> None:
    allowed_kinds = allowed_kinds or ALLOWED_NETWORK_KINDS
    if not isinstance(message, dict):
        raise MalformedInput("network message must be object")
    kind = message.get("kind")
    if kind not in allowed_kinds:
        raise MalformedInput("unknown or forbidden network message kind")
    if RESERVED_NETWORK_FIELDS.intersection(message):
        raise MalformedInput("network message attempts host-authority injection")
    encoded = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ResourceLimitExceeded("network message too large")


def validate_required_security_features(required: Iterable[str], supported: Iterable[str]) -> None:
    supported_set = set(supported)
    missing = sorted(set(required) - supported_set)
    if missing:
        raise MalformedInput("unsupported required security feature(s): " + ", ".join(missing))
