"""Production capability broker and trusted host-service boundary for SplashMX.

SMX-027 turns the mediated ``ServiceRequest`` values emitted by ``execution.ir``
into deny-by-default, principal-attributed host-service calls. Ordinary content
never receives a host object or a grant handle; only trusted runtime policy may
issue root grants, register adapters, delegate authority or revoke it.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

from splashmx.canonical.core import BehaviourAttachmentId, SemanticId, ThingId
from splashmx.execution.ir import ServiceRequest


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_FORBIDDEN_UNTRUSTED_FIELDS = {
    "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
    "databaserowid", "cachekey", "transportpeerid", "connectionhandle",
    "socketid", "sessionid", "processhandle", "hosthandle", "hostobject",
    "capabilitytoken", "capabilitygrant", "grantid", "delegationgrant",
    "javascriptbridge", "gdextension", "nativehandle",
}
MAX_SERVICE_VALUE_DEPTH = 32
MAX_SERVICE_VALUE_NODES = 20_000
MAX_SERVICE_STRING_BYTES = 2 * 1024 * 1024


class CapabilityError(ValueError):
    """Typed capability/service failure suitable for the production envelope."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise CapabilityError(code, message)


def _normalise_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _validate_name(value: str, role: str) -> None:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        _fail("capability.invalid_identity", f"{role} must be a bounded semantic token")


class PrincipalId(SemanticId):
    role = "PrincipalId"


class CapabilityId(SemanticId):
    role = "CapabilityId"


@dataclass(frozen=True)
class CapabilityScope:
    """Small typed scope algebra for first production host-service adapters.

    ``targets`` and ``operations`` are explicit allow sets; ``*`` means all values
    in that one dimension. ``max_bytes`` is an optional upper bound. Future
    capability families may add versioned scope types, but delegation must retain
    the same monotonic-narrowing property.
    """

    targets: frozenset[str]
    operations: frozenset[str]
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.targets or not self.operations:
            _fail("capability.invalid_scope", "scope targets and operations must be non-empty")
        for label, values in (("target", self.targets), ("operation", self.operations)):
            for value in values:
                if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 2048:
                    _fail("capability.invalid_scope", f"scope {label} values must be bounded strings")
        if self.max_bytes is not None and (
            not isinstance(self.max_bytes, int) or isinstance(self.max_bytes, bool) or self.max_bytes < 0
        ):
            _fail("capability.invalid_scope", "scope max_bytes must be a non-negative integer")

    @staticmethod
    def _set_narrows(child: frozenset[str], parent: frozenset[str]) -> bool:
        return "*" in parent or ("*" not in child and child <= parent)

    def is_narrower_than(self, parent: "CapabilityScope") -> bool:
        if not self._set_narrows(self.targets, parent.targets):
            return False
        if not self._set_narrows(self.operations, parent.operations):
            return False
        if parent.max_bytes is not None and (self.max_bytes is None or self.max_bytes > parent.max_bytes):
            return False
        return True

    def permits(self, target: "ServiceTarget") -> bool:
        if "*" not in self.targets and target.target not in self.targets:
            return False
        if "*" not in self.operations and target.operation not in self.operations:
            return False
        if self.max_bytes is not None and target.byte_count > self.max_bytes:
            return False
        return True


@dataclass(frozen=True)
class ServiceTarget:
    target: str
    operation: str
    byte_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target or len(self.target.encode("utf-8")) > 2048:
            _fail("capability.invalid_service_target", "service target must be a bounded non-empty string")
        if not isinstance(self.operation, str) or not self.operation or len(self.operation.encode("utf-8")) > 256:
            _fail("capability.invalid_service_target", "service operation must be a bounded non-empty string")
        if not isinstance(self.byte_count, int) or isinstance(self.byte_count, bool) or self.byte_count < 0:
            _fail("capability.invalid_service_target", "service byte_count must be a non-negative integer")


@dataclass(frozen=True)
class CapabilityGrant:
    grant_id: str
    principal_id: PrincipalId
    capability_id: CapabilityId
    scope: CapabilityScope
    issuer_policy_id: str
    issued_at: int
    expires_at: int | None = None
    delegable: bool = False
    parent_grant_id: str | None = None
    revoked: bool = False

    def __post_init__(self) -> None:
        _validate_name(self.grant_id, "grant_id")
        _validate_name(self.issuer_policy_id, "issuer_policy_id")
        if not isinstance(self.principal_id, PrincipalId):
            _fail("capability.invalid_grant", "grant principal_id must be PrincipalId")
        if not isinstance(self.capability_id, CapabilityId):
            _fail("capability.invalid_grant", "grant capability_id must be CapabilityId")
        if not isinstance(self.scope, CapabilityScope):
            _fail("capability.invalid_grant", "grant scope must be CapabilityScope")
        if not isinstance(self.issued_at, int) or isinstance(self.issued_at, bool) or self.issued_at < 0:
            _fail("capability.invalid_grant", "issued_at must be a non-negative policy timestamp")
        if self.expires_at is not None and (
            not isinstance(self.expires_at, int) or isinstance(self.expires_at, bool)
            or self.expires_at <= self.issued_at
        ):
            _fail("capability.invalid_grant", "expires_at must be greater than issued_at")
        if self.parent_grant_id is not None:
            _validate_name(self.parent_grant_id, "parent_grant_id")


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: CapabilityId
    scope: CapabilityScope
    required: bool = True
    reduced_mode: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId) or not isinstance(self.scope, CapabilityScope):
            _fail("capability.invalid_requirement", "requirements need typed capability and scope")
        if not self.required and self.reduced_mode is not None and (
            not isinstance(self.reduced_mode, str) or not self.reduced_mode
        ):
            _fail("capability.invalid_requirement", "reduced_mode must be a non-empty string when present")


@dataclass(frozen=True)
class CapabilityPlan:
    granted: tuple[CapabilityId, ...]
    optional_denied: tuple[CapabilityId, ...]
    reduced_modes: tuple[str, ...]


class CapabilityBroker:
    """Trusted in-memory grant authority with bounded, narrowing delegation."""

    def __init__(self, *, max_grants: int = 4096, max_delegation_depth: int = 8, max_descendants_per_root: int = 256):
        for name, value in {
            "max_grants": max_grants,
            "max_delegation_depth": max_delegation_depth,
            "max_descendants_per_root": max_descendants_per_root,
        }.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                _fail("capability.invalid_limit", f"{name} must be a positive integer")
        self.max_grants = max_grants
        self.max_delegation_depth = max_delegation_depth
        self.max_descendants_per_root = max_descendants_per_root
        self._grants: dict[str, CapabilityGrant] = {}

    @classmethod
    def from_trusted_grants(
        cls,
        grants: Sequence[CapabilityGrant],
        *,
        max_grants: int = 4096,
        max_delegation_depth: int = 8,
        max_descendants_per_root: int = 256,
    ) -> "CapabilityBroker":
        """Load trusted runtime-policy state only after bounded whole-set validation."""
        broker = cls(
            max_grants=max_grants,
            max_delegation_depth=max_delegation_depth,
            max_descendants_per_root=max_descendants_per_root,
        )
        if len(grants) > broker.max_grants:
            _fail("capability.grant_limit", "trusted grant snapshot exceeds grant limit")
        for grant in grants:
            if not isinstance(grant, CapabilityGrant):
                _fail("capability.invalid_grant", "trusted snapshot contains non-grant value")
            if grant.grant_id in broker._grants:
                _fail("capability.duplicate_grant", f"duplicate grant_id {grant.grant_id!r}")
            broker._grants[grant.grant_id] = grant
        broker._validate_graph()
        return broker

    def _check_now(self, now: int) -> None:
        if not isinstance(now, int) or isinstance(now, bool) or now < 0:
            _fail("capability.invalid_time", "policy time must be a non-negative integer")

    def _ancestry(self, grant_id: str) -> list[CapabilityGrant]:
        chain: list[CapabilityGrant] = []
        seen: set[str] = set()
        current_id: str | None = grant_id
        while current_id is not None:
            if current_id in seen:
                _fail("capability.cyclic_ancestry", "delegation ancestry contains a cycle")
            if len(chain) > self.max_delegation_depth:
                _fail("capability.delegation_depth", "delegation ancestry exceeds depth limit")
            seen.add(current_id)
            grant = self._grants.get(current_id)
            if grant is None:
                _fail("capability.missing_ancestry", f"delegation ancestor {current_id!r} is missing")
            chain.append(grant)
            current_id = grant.parent_grant_id
        if len(chain) - 1 > self.max_delegation_depth:
            _fail("capability.delegation_depth", "delegation ancestry exceeds depth limit")
        return chain

    def _validate_graph(self) -> None:
        for grant in sorted(self._grants.values(), key=lambda row: row.grant_id):
            chain = self._ancestry(grant.grant_id)
            for child, parent in zip(chain, chain[1:]):
                if child.capability_id != parent.capability_id:
                    _fail("capability.invalid_ancestry", "delegated capability differs from parent")
                if not parent.delegable:
                    _fail("capability.invalid_ancestry", "delegation descends from non-delegable grant")
                if not child.scope.is_narrower_than(parent.scope):
                    _fail("capability.scope_escalation", "delegated scope widens parent authority")
                if child.issued_at < parent.issued_at:
                    _fail("capability.invalid_ancestry", "delegated grant predates its parent")
                if parent.expires_at is not None and (
                    child.expires_at is None or child.expires_at > parent.expires_at
                ):
                    _fail("capability.lifetime_escalation", "delegated lifetime exceeds parent")
        root_counts: dict[str, int] = {}
        for grant in sorted(self._grants.values(), key=lambda row: row.grant_id):
            chain = self._ancestry(grant.grant_id)
            if len(chain) > 1:
                root = chain[-1].grant_id
                root_counts[root] = root_counts.get(root, 0) + 1
                if root_counts[root] > self.max_descendants_per_root:
                    _fail("capability.delegation_count", "delegation descendant count exceeds limit")

    def issue_root_grant(
        self, *, grant_id: str, principal_id: PrincipalId, capability_id: CapabilityId,
        scope: CapabilityScope, issuer_policy_id: str, issued_at: int,
        expires_at: int | None = None, delegable: bool = False,
    ) -> CapabilityGrant:
        if len(self._grants) >= self.max_grants:
            _fail("capability.grant_limit", "grant table is full")
        if grant_id in self._grants:
            _fail("capability.duplicate_grant", f"grant_id {grant_id!r} already exists")
        grant = CapabilityGrant(
            grant_id, principal_id, capability_id, scope, issuer_policy_id,
            issued_at, expires_at, delegable, None, False,
        )
        self._grants[grant_id] = grant
        return grant

    def _live_chain(self, grant_id: str, *, now: int) -> list[CapabilityGrant]:
        self._check_now(now)
        chain = self._ancestry(grant_id)
        for grant in chain:
            if grant.revoked:
                _fail("capability.revoked", f"grant {grant.grant_id!r} or an ancestor is revoked")
            if grant.expires_at is not None and now >= grant.expires_at:
                _fail("capability.expired", f"grant {grant.grant_id!r} or an ancestor is expired")
        return chain

    def delegate(
        self, *, parent_grant_id: str, grant_id: str, principal_id: PrincipalId,
        scope: CapabilityScope, issued_at: int, expires_at: int | None = None,
        delegable: bool = False,
    ) -> CapabilityGrant:
        self._check_now(issued_at)
        if len(self._grants) >= self.max_grants:
            _fail("capability.grant_limit", "grant table is full")
        if grant_id in self._grants:
            _fail("capability.duplicate_grant", f"grant_id {grant_id!r} already exists")
        chain = self._live_chain(parent_grant_id, now=issued_at)
        parent = chain[0]
        if not parent.delegable:
            _fail("capability.not_delegable", "source grant is not delegable")
        if len(chain) > self.max_delegation_depth:
            _fail("capability.delegation_depth", "delegation would exceed depth limit")
        if not scope.is_narrower_than(parent.scope):
            _fail("capability.scope_escalation", "delegated scope must narrow source scope")
        if parent.expires_at is not None and (expires_at is None or expires_at > parent.expires_at):
            _fail("capability.lifetime_escalation", "delegated lifetime cannot exceed source lifetime")
        if expires_at is not None and expires_at <= issued_at:
            _fail("capability.invalid_grant", "delegated expiry must be after issued_at")
        root_id = chain[-1].grant_id
        descendants = 0
        for existing in sorted(self._grants.values(), key=lambda row: row.grant_id):
            existing_chain = self._ancestry(existing.grant_id)
            if len(existing_chain) > 1 and existing_chain[-1].grant_id == root_id:
                descendants += 1
                if descendants >= self.max_descendants_per_root:
                    _fail("capability.delegation_count", "delegation descendant count would exceed limit")
        grant = CapabilityGrant(
            grant_id, principal_id, parent.capability_id, scope,
            parent.issuer_policy_id, issued_at, expires_at, delegable,
            parent_grant_id, False,
        )
        self._grants[grant_id] = grant
        return grant

    def revoke(self, grant_id: str) -> None:
        grant = self._grants.get(grant_id)
        if grant is None:
            _fail("capability.unknown_grant", f"unknown grant {grant_id!r}")
        self._grants[grant_id] = replace(grant, revoked=True)

    def grant(self, grant_id: str) -> CapabilityGrant:
        grant = self._grants.get(grant_id)
        if grant is None:
            _fail("capability.unknown_grant", f"unknown grant {grant_id!r}")
        return grant

    def authorize_grant(
        self, grant_id: str, *, principal_id: PrincipalId, capability_id: CapabilityId,
        target: ServiceTarget, now: int,
    ) -> CapabilityGrant:
        chain = self._live_chain(grant_id, now=now)
        grant = chain[0]
        if grant.principal_id != principal_id:
            _fail("capability.wrong_principal", "grant belongs to a different principal")
        if grant.capability_id != capability_id:
            _fail("capability.wrong_capability", "grant does not authorize requested capability")
        if not grant.scope.permits(target):
            _fail("capability.scope_denied", "requested service target is outside grant scope")
        return grant

    def find_authorized_grant(
        self, *, principal_id: PrincipalId, capability_id: CapabilityId,
        target: ServiceTarget, now: int,
    ) -> CapabilityGrant:
        self._check_now(now)
        saw_candidate = False
        last_error: CapabilityError | None = None
        for grant in sorted(self._grants.values(), key=lambda row: row.grant_id):
            if grant.principal_id != principal_id or grant.capability_id != capability_id:
                continue
            saw_candidate = True
            try:
                return self.authorize_grant(
                    grant.grant_id, principal_id=principal_id,
                    capability_id=capability_id, target=target, now=now,
                )
            except CapabilityError as exc:
                last_error = exc
        if saw_candidate and last_error is not None:
            raise last_error
        _fail("capability.denied", "principal has no matching capability grant")

    def resolve_requirements(
        self, principal_id: PrincipalId, requirements: Sequence[CapabilityRequirement], *, now: int,
    ) -> CapabilityPlan:
        granted: list[CapabilityId] = []
        optional_denied: list[CapabilityId] = []
        reduced: list[str] = []
        for requirement in requirements:
            authorized = False
            last_error: CapabilityError | None = None
            for grant in sorted(self._grants.values(), key=lambda row: row.grant_id):
                if grant.principal_id != principal_id or grant.capability_id != requirement.capability_id:
                    continue
                if not requirement.scope.is_narrower_than(grant.scope):
                    continue
                try:
                    self._live_chain(grant.grant_id, now=now)
                    authorized = True
                    break
                except CapabilityError as exc:
                    last_error = exc
            if authorized:
                granted.append(requirement.capability_id)
                continue
            if requirement.required:
                detail = f": {last_error}" if last_error is not None else ""
                _fail(
                    "capability.required_denied",
                    f"required capability {requirement.capability_id} denied{detail}",
                )
            optional_denied.append(requirement.capability_id)
            if requirement.reduced_mode is not None:
                reduced.append(requirement.reduced_mode)
        return CapabilityPlan(tuple(granted), tuple(optional_denied), tuple(reduced))


def principal_for_service_request(request: ServiceRequest) -> PrincipalId:
    if not isinstance(request, ServiceRequest):
        _fail("capability.invalid_request", "host boundary accepts only execution ServiceRequest values")
    return PrincipalId(f"behaviour:{request.thing_id}:{request.attachment_id}")


def validate_untrusted_service_value(
    value: Any, *, where: str = "service value", depth: int = 0,
    counter: list[int] | None = None,
) -> None:
    """Independent recursive R-016-02 enforcement at the host-service boundary."""
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_SERVICE_VALUE_NODES:
        _fail("capability.value_limit", f"{where} exceeds node limit")
    if depth > MAX_SERVICE_VALUE_DEPTH:
        _fail("capability.value_limit", f"{where} exceeds depth limit")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            _fail("capability.invalid_value", f"{where} contains non-finite number")
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_SERVICE_STRING_BYTES:
            _fail("capability.value_limit", f"{where} string exceeds byte limit")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_untrusted_service_value(
                child, where=f"{where}[{index}]", depth=depth + 1, counter=counter
            )
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("capability.invalid_value", f"{where} map keys must be strings")
            if _normalise_field_name(key) in _FORBIDDEN_UNTRUSTED_FIELDS:
                _fail(
                    "capability.serialized_authority",
                    f"{where} contains forbidden authority/host field {key!r}",
                )
            validate_untrusted_service_value(
                child, where=f"{where}.{key}", depth=depth + 1, counter=counter
            )
        return
    _fail("capability.invalid_value", f"{where} contains unsupported host object type {type(value).__name__}")


@dataclass(frozen=True)
class HostServiceAdapter:
    service_name: str
    capability_id: CapabilityId
    target_resolver: Callable[[Any], ServiceTarget]
    invoke: Callable[[Any], Any]

    def __post_init__(self) -> None:
        _validate_name(self.service_name, "service_name")
        if not isinstance(self.capability_id, CapabilityId):
            _fail("capability.invalid_adapter", "adapter capability_id must be CapabilityId")
        if not callable(self.target_resolver) or not callable(self.invoke):
            _fail("capability.invalid_adapter", "adapter resolver and invoke must be trusted callables")


@dataclass(frozen=True)
class ServiceLimits:
    max_pending_per_principal: int = 64
    max_admissions_per_window: int = 1024

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                _fail("capability.invalid_limit", f"{name} must be a positive integer")


@dataclass(frozen=True)
class AdmittedServiceCall:
    call_id: str
    principal_id: PrincipalId
    grant_id: str
    service_name: str
    target: ServiceTarget
    payload: Any
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId
    request_id: str
    source_activation_sequence: int


class TrustedHostServiceBoundary:
    """Admission + final-use recheck around trusted host adapters.

    Admission deliberately does *not* invoke the host. ``execute`` revalidates the
    exact originating principal/grant/scope immediately before crossing the trusted
    adapter, so revocation or expiry after admission wins closed (R-016-04).
    """

    def __init__(
        self, broker: CapabilityBroker, adapters: Iterable[HostServiceAdapter],
        *, limits: ServiceLimits | None = None,
    ) -> None:
        self.broker = broker
        self.limits = limits or ServiceLimits()
        self._adapters: dict[str, HostServiceAdapter] = {}
        for adapter in adapters:
            if adapter.service_name in self._adapters:
                _fail("capability.duplicate_service", f"duplicate service {adapter.service_name!r}")
            self._adapters[adapter.service_name] = adapter
        self._pending: dict[str, AdmittedServiceCall] = {}
        self._pending_by_principal: dict[PrincipalId, int] = {}
        self._admissions_by_principal: dict[PrincipalId, int] = {}

    def reset_quota_window(self) -> None:
        """Trusted host policy starts a new accounting window; pending calls remain."""
        self._admissions_by_principal.clear()

    def _resolve_target(self, adapter: HostServiceAdapter, payload: Any) -> ServiceTarget:
        try:
            target = adapter.target_resolver(deepcopy(payload))
        except CapabilityError:
            raise
        except Exception as exc:
            raise CapabilityError(
                "capability.invalid_service_request", f"service target resolution failed: {exc}"
            ) from exc
        if not isinstance(target, ServiceTarget):
            _fail("capability.invalid_service_request", "trusted adapter resolver returned invalid target")
        return target

    def admit(self, request: ServiceRequest, *, now: int) -> AdmittedServiceCall:
        principal_id = principal_for_service_request(request)
        validate_untrusted_service_value(request.payload, where="service request payload")
        adapter = self._adapters.get(request.service)
        if adapter is None:
            _fail("capability.unknown_service", f"unknown trusted service {request.service!r}")
        target = self._resolve_target(adapter, request.payload)
        grant = self.broker.find_authorized_grant(
            principal_id=principal_id,
            capability_id=adapter.capability_id,
            target=target,
            now=now,
        )
        pending = self._pending_by_principal.get(principal_id, 0)
        admissions = self._admissions_by_principal.get(principal_id, 0)
        if pending >= self.limits.max_pending_per_principal:
            _fail("capability.pending_service_quota", "principal pending-service quota exceeded")
        if admissions >= self.limits.max_admissions_per_window:
            _fail("capability.service_rate_quota", "principal service-admission quota exceeded")
        call_id = f"{principal_id}:{request.request_id}:{request.source_activation_sequence}"
        if call_id in self._pending:
            _fail("capability.duplicate_call", "service correlation identity is already pending")
        call = AdmittedServiceCall(
            call_id=call_id,
            principal_id=principal_id,
            grant_id=grant.grant_id,
            service_name=request.service,
            target=target,
            payload=deepcopy(request.payload),
            thing_id=request.thing_id,
            attachment_id=request.attachment_id,
            request_id=request.request_id,
            source_activation_sequence=request.source_activation_sequence,
        )
        self._pending[call_id] = call
        self._pending_by_principal[principal_id] = pending + 1
        self._admissions_by_principal[principal_id] = admissions + 1
        return call

    def _drop_pending(self, call: AdmittedServiceCall) -> None:
        self._pending.pop(call.call_id, None)
        count = self._pending_by_principal.get(call.principal_id, 0)
        if count <= 1:
            self._pending_by_principal.pop(call.principal_id, None)
        else:
            self._pending_by_principal[call.principal_id] = count - 1

    def cancel(self, call: AdmittedServiceCall) -> None:
        current = self._pending.get(call.call_id)
        if current != call:
            _fail("capability.stale_call", "service call is not pending")
        self._drop_pending(call)

    def execute(self, call: AdmittedServiceCall, *, now: int) -> Any:
        current = self._pending.get(call.call_id)
        if current != call:
            _fail("capability.stale_call", "service call is not pending or was already consumed")
        adapter = self._adapters.get(call.service_name)
        if adapter is None:
            self._drop_pending(call)
            _fail("capability.unknown_service", "trusted service disappeared before execution")
        try:
            # R-016-04: this is deliberately the final operation before host crossing.
            self.broker.authorize_grant(
                call.grant_id,
                principal_id=call.principal_id,
                capability_id=adapter.capability_id,
                target=call.target,
                now=now,
            )
        except CapabilityError:
            self._drop_pending(call)
            raise
        self._drop_pending(call)
        try:
            result = adapter.invoke(deepcopy(call.payload))
        except CapabilityError:
            raise
        except Exception as exc:
            raise CapabilityError(
                "capability.host_service_failed",
                "trusted host service failed without exposing a raw host exception",
            ) from exc
        validate_untrusted_service_value(result, where="service result")
        return deepcopy(result)
