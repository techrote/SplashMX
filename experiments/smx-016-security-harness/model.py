"""Disposable SMX-016 adversarial security harness.

This model is deliberately stricter than the earlier positive proof models. It
represents security boundaries and deterministic budgets, not production APIs,
cryptography, archive code, network transport, or a claim of OS/browser sandbox
escape resistance.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping


class SecurityError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class MalformedInput(SecurityError):
    pass


class CapabilityDenied(SecurityError):
    pass


class ResourceLimitExceeded(SecurityError):
    pass


class DependencyRejected(SecurityError):
    pass


@dataclass(frozen=True)
class Limits:
    # Package/container
    max_entries: int = 32
    max_compressed_bytes: int = 1_000_000
    max_expanded_bytes: int = 4_000_000
    max_single_entry_bytes: int = 2_000_000
    max_expansion_ratio: int = 16
    max_path_length: int = 180
    # Canonical structured input
    max_tree_depth: int = 12
    max_tree_nodes: int = 512
    max_string_bytes: int = 4096
    max_collection_items: int = 128
    max_records: int = 128
    # Dependency/migration
    max_dependency_depth: int = 6
    max_dependency_count: int = 24
    max_dependency_bytes: int = 16_000_000
    max_migration_steps: int = 12
    max_migration_cost: int = 2048
    max_migration_output_records: int = 256
    # Capability
    max_grants: int = 64
    max_delegation_depth: int = 4
    # Behaviour/runtime
    max_instructions: int = 64
    max_alloc_units: int = 256
    max_emits: int = 16
    max_timers: int = 16
    max_queue: int = 32
    max_service_requests: int = 8
    # Network
    max_network_bytes: int = 4096
    max_network_nodes: int = 128
    max_network_depth: int = 8
    max_network_messages_per_tick: int = 8
    max_network_queue: int = 16
    # Media pre-decode
    max_asset_compressed_bytes: int = 4_000_000
    max_asset_decoded_bytes: int = 32_000_000
    max_image_pixels: int = 8_388_608
    max_audio_frames: int = 48_000 * 60 * 10


DEFAULT_LIMITS = Limits()


# ------------------------------ package boundary -----------------------------

@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    compressed_bytes: int
    expanded_bytes: int
    kind: str = "file"
    nested_archive: bool = False


_WINDOWS_DEVICE = re.compile(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$")


def normalize_package_path(path: str, limits: Limits = DEFAULT_LIMITS) -> str:
    if not isinstance(path, str) or not path:
        raise MalformedInput("empty_package_path")
    normalized = unicodedata.normalize("NFC", path.replace("\\", "/"))
    if len(normalized.encode("utf-8")) > limits.max_path_length:
        raise ResourceLimitExceeded("package_path_too_long")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise MalformedInput("package_path_control_character")
    if normalized.startswith("/") or normalized.startswith("//"):
        raise MalformedInput("absolute_package_path")
    if re.match(r"^[A-Za-z]:", normalized):
        raise MalformedInput("drive_qualified_package_path")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise MalformedInput("ambiguous_or_traversing_package_path")
    if any(_WINDOWS_DEVICE.fullmatch(part.rstrip(" .")) for part in parts):
        raise MalformedInput("reserved_device_package_path")
    if any(part != part.rstrip(" .") for part in parts):
        raise MalformedInput("trailing_dot_or_space_package_path")
    return "/".join(parts)


def validate_archive(entries: Iterable[ArchiveEntry], limits: Limits = DEFAULT_LIMITS) -> tuple[str, ...]:
    items = list(entries)
    if len(items) > limits.max_entries:
        raise ResourceLimitExceeded("package_entry_count_exceeded")
    seen: set[str] = set()
    total_compressed = 0
    total_expanded = 0
    for entry in items:
        if entry.kind != "file":
            raise MalformedInput("special_archive_entry_forbidden", entry.kind)
        if entry.nested_archive:
            raise MalformedInput("nested_archive_forbidden")
        path = normalize_package_path(entry.path, limits)
        folded = path.casefold()
        # Canonical package namespace is NFC + case-insensitive for collision
        # rejection even though semantic IDs remain case-sensitive elsewhere.
        if folded in seen:
            raise MalformedInput("normalized_package_path_collision", path)
        seen.add(folded)
        if entry.compressed_bytes < 0 or entry.expanded_bytes < 0:
            raise MalformedInput("negative_archive_size")
        if entry.expanded_bytes > limits.max_single_entry_bytes:
            raise ResourceLimitExceeded("single_entry_size_exceeded")
        if entry.compressed_bytes == 0:
            if entry.expanded_bytes:
                raise ResourceLimitExceeded("undefined_expansion_ratio")
        elif entry.expanded_bytes > entry.compressed_bytes * limits.max_expansion_ratio:
            raise ResourceLimitExceeded("expansion_ratio_exceeded")
        total_compressed += entry.compressed_bytes
        total_expanded += entry.expanded_bytes
        if total_compressed > limits.max_compressed_bytes:
            raise ResourceLimitExceeded("package_compressed_bytes_exceeded")
        if total_expanded > limits.max_expanded_bytes:
            raise ResourceLimitExceeded("package_expanded_bytes_exceeded")
    return tuple(sorted(seen))


# ---------------------------- canonical boundary -----------------------------

FORBIDDEN_DURABLE_KEYS = {
    "capability_grant", "grant_id", "host_handle", "native_handle",
    "javascript_object", "godot_object", "rid", "node_path", "peer_id",
    "socket", "authority_token",
}


def validate_bounded_tree(
    value: Any,
    *,
    limits: Limits = DEFAULT_LIMITS,
    forbidden_keys: set[str] | frozenset[str] = frozenset(),
    max_depth: int | None = None,
    max_nodes: int | None = None,
) -> int:
    depth_limit = limits.max_tree_depth if max_depth is None else max_depth
    node_limit = limits.max_tree_nodes if max_nodes is None else max_nodes
    nodes = 0

    def walk(node: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > node_limit:
            raise ResourceLimitExceeded("structured_node_budget_exceeded")
        if depth > depth_limit:
            raise ResourceLimitExceeded("structured_depth_budget_exceeded")
        if isinstance(node, str):
            if len(node.encode("utf-8")) > limits.max_string_bytes:
                raise ResourceLimitExceeded("string_budget_exceeded")
        elif isinstance(node, Mapping):
            if len(node) > limits.max_collection_items:
                raise ResourceLimitExceeded("map_item_budget_exceeded")
            for key, child in node.items():
                if not isinstance(key, str):
                    raise MalformedInput("non_string_map_key")
                if key in forbidden_keys:
                    raise MalformedInput("forbidden_durable_authority_field", key)
                walk(key, depth + 1)
                walk(child, depth + 1)
        elif isinstance(node, (list, tuple)):
            if len(node) > limits.max_collection_items:
                raise ResourceLimitExceeded("list_item_budget_exceeded")
            for child in node:
                walk(child, depth + 1)
        elif node is None or isinstance(node, (bool, int, float)):
            return
        else:
            raise MalformedInput("unsupported_structured_value", type(node).__name__)

    walk(value, 0)
    return nodes


def validate_canonical_document(
    document: Mapping[str, Any],
    *,
    supported_required_features: Iterable[str] = (),
    limits: Limits = DEFAULT_LIMITS,
) -> None:
    validate_bounded_tree(document, limits=limits, forbidden_keys=FORBIDDEN_DURABLE_KEYS)
    records = document.get("records")
    if not isinstance(records, list):
        raise MalformedInput("records_must_be_list")
    if len(records) > limits.max_records:
        raise ResourceLimitExceeded("record_count_exceeded")
    ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise MalformedInput("record_must_be_object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise MalformedInput("record_id_required")
        if record_id in ids:
            raise MalformedInput("duplicate_record_id", record_id)
        ids.add(record_id)
    required = document.get("required_features", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise MalformedInput("invalid_required_features")
    missing = sorted(set(required) - set(supported_required_features))
    if missing:
        raise MalformedInput("unsupported_required_feature", ",".join(missing))


# --------------------------- dependency / exact lock -------------------------

@dataclass(frozen=True)
class LockEntry:
    package_id: str
    revision_id: str
    digest: str
    byte_size: int


@dataclass(frozen=True)
class Artifact:
    package_id: str
    revision_id: str
    digest: str
    byte_size: int


def validate_exact_artifact(lock: LockEntry, observed: Artifact) -> None:
    if observed.package_id != lock.package_id:
        raise DependencyRejected("package_identity_mismatch")
    if observed.revision_id != lock.revision_id:
        raise DependencyRejected("package_revision_substitution")
    if observed.digest != lock.digest:
        raise DependencyRejected("package_digest_substitution")
    if observed.byte_size != lock.byte_size:
        raise DependencyRejected("package_size_mismatch")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", observed.digest):
        raise MalformedInput("invalid_content_digest")


@dataclass(frozen=True)
class DependencyNode:
    package_id: str
    revision_id: str
    byte_size: int
    dependencies: tuple[str, ...] = ()


def validate_dependency_graph(
    root_id: str,
    graph: Mapping[str, DependencyNode],
    *,
    limits: Limits = DEFAULT_LIMITS,
) -> tuple[str, ...]:
    if root_id not in graph:
        raise DependencyRejected("missing_root_dependency")
    visited: set[str] = set()
    visiting: set[str] = set()
    total_bytes = 0

    def visit(package_id: str, depth: int) -> None:
        nonlocal total_bytes
        if depth > limits.max_dependency_depth:
            raise ResourceLimitExceeded("dependency_depth_exceeded")
        if package_id in visiting:
            raise DependencyRejected("dependency_cycle", package_id)
        if package_id in visited:
            return
        if package_id not in graph:
            raise DependencyRejected("missing_dependency", package_id)
        if len(visited) + len(visiting) + 1 > limits.max_dependency_count:
            raise ResourceLimitExceeded("dependency_count_exceeded")
        node = graph[package_id]
        if node.package_id != package_id or not node.revision_id or node.byte_size <= 0:
            raise MalformedInput("invalid_dependency_descriptor", package_id)
        visiting.add(package_id)
        total_bytes += node.byte_size
        if total_bytes > limits.max_dependency_bytes:
            raise ResourceLimitExceeded("dependency_bytes_exceeded")
        for child in node.dependencies:
            visit(child, depth + 1)
        visiting.remove(package_id)
        visited.add(package_id)

    visit(root_id, 1)
    return tuple(sorted(visited))


# ----------------------------- capability boundary ---------------------------

@dataclass(frozen=True)
class Grant:
    grant_id: str
    principal: str
    capability: str
    scope: frozenset[str]
    delegable: bool = False
    parent_grant_id: str | None = None
    expires_tick: int | None = None
    revoked: bool = False


class CapabilityBroker:
    def __init__(self, supported: Iterable[str], *, limits: Limits = DEFAULT_LIMITS) -> None:
        self.supported = set(supported)
        self.limits = limits
        self.grants: dict[str, Grant] = {}

    def issue(
        self, grant_id: str, principal: str, capability: str, scope: Iterable[str],
        *, delegable: bool = False, expires_tick: int | None = None
    ) -> Grant:
        if capability not in self.supported:
            raise CapabilityDenied("unsupported_capability", capability)
        if grant_id in self.grants:
            raise MalformedInput("duplicate_grant_id", grant_id)
        if len(self.grants) >= self.limits.max_grants:
            raise ResourceLimitExceeded("grant_count_exceeded")
        grant = Grant(grant_id, principal, capability, frozenset(scope), delegable, None, expires_tick)
        self.grants[grant_id] = grant
        return grant

    def _ancestry(self, grant_id: str) -> tuple[Grant, ...]:
        ancestry: list[Grant] = []
        seen: set[str] = set()
        current_id: str | None = grant_id
        while current_id is not None:
            if current_id in seen:
                raise MalformedInput("delegation_cycle", current_id)
            seen.add(current_id)
            grant = self.grants.get(current_id)
            if grant is None:
                raise CapabilityDenied("missing_parent_grant", current_id)
            ancestry.append(grant)
            if len(ancestry) > self.limits.max_delegation_depth + 1:
                raise ResourceLimitExceeded("delegation_depth_exceeded")
            current_id = grant.parent_grant_id
        return tuple(ancestry)

    def is_live(self, grant_id: str, *, tick: int) -> bool:
        try:
            ancestry = self._ancestry(grant_id)
        except SecurityError:
            return False
        return all(
            not grant.revoked and
            (grant.expires_tick is None or tick <= grant.expires_tick)
            for grant in ancestry
        )

    def authorize(self, principal: str, capability: str, scope: Iterable[str], *, tick: int) -> Grant:
        requested = frozenset(scope)
        for grant in self.grants.values():
            if grant.principal != principal or grant.capability != capability:
                continue
            if self.is_live(grant.grant_id, tick=tick) and requested.issubset(grant.scope):
                return grant
        raise CapabilityDenied("capability_denied", f"{principal}:{capability}")

    def delegate(
        self, source_grant_id: str, new_grant_id: str, child_principal: str,
        scope: Iterable[str], *, delegable: bool = False,
        expires_tick: int | None = None, tick: int = 0
    ) -> Grant:
        if new_grant_id in self.grants:
            raise MalformedInput("duplicate_grant_id", new_grant_id)
        if len(self.grants) >= self.limits.max_grants:
            raise ResourceLimitExceeded("grant_count_exceeded")
        source = self.grants.get(source_grant_id)
        if source is None or not self.is_live(source_grant_id, tick=tick):
            raise CapabilityDenied("source_grant_inactive")
        if not source.delegable:
            raise CapabilityDenied("source_grant_not_delegable")
        requested = frozenset(scope)
        if not requested.issubset(source.scope):
            raise CapabilityDenied("delegation_widens_scope")
        if source.expires_tick is not None and (
            expires_tick is None or expires_tick > source.expires_tick
        ):
            raise CapabilityDenied("delegation_widens_lifetime")
        source_depth = len(self._ancestry(source_grant_id)) - 1
        if source_depth + 1 > self.limits.max_delegation_depth:
            raise ResourceLimitExceeded("delegation_depth_exceeded")
        grant = Grant(
            new_grant_id, child_principal, source.capability, requested,
            delegable, source_grant_id, expires_tick
        )
        self.grants[new_grant_id] = grant
        return grant

    def revoke(self, grant_id: str) -> None:
        grant = self.grants.get(grant_id)
        if grant is not None:
            self.grants[grant_id] = replace(grant, revoked=True)


@dataclass
class HostRecorder:
    calls: list[tuple[str, str, tuple[str, ...]]] = field(default_factory=list)
    decoder_calls: int = 0

    def invoke(self, api: str, principal: str, scope: Iterable[str]) -> str:
        self.calls.append((api, principal, tuple(scope)))
        return f"ok:{api}"


FORBIDDEN_RAW_HOST_APIS = frozenset({
    "javascript.eval", "javascript.bridge", "godot.gdscript",
    "godot.resource_loader", "godot.pck.load", "native.gdextension",
    "native.process", "native.shell", "filesystem.raw", "network.raw_socket",
})


@dataclass(frozen=True)
class TargetProfile:
    name: str
    physically_exposed: frozenset[str]
    semantic_services: frozenset[str]
    hardened: bool


TARGETS = {
    "web_hardened": TargetProfile(
        "web_hardened", frozenset(), frozenset({"network.http", "storage.save"}), True
    ),
    # Deliberately models a weaker stock-template TCB surface. Semantic policy
    # must still deny raw JavaScriptBridge/eval to ordinary content.
    "web_official": TargetProfile(
        "web_official", frozenset({"javascript.bridge", "javascript.eval"}),
        frozenset({"network.http", "storage.save"}), False
    ),
    "native": TargetProfile(
        "native", frozenset({"native.gdextension", "native.process", "filesystem.raw"}),
        frozenset({"network.http", "storage.save"}), False
    ),
    "headless": TargetProfile(
        "headless", frozenset({"native.process", "filesystem.raw"}),
        frozenset({"network.http", "storage.save"}), False
    ),
}


@dataclass(frozen=True)
class PendingService:
    principal: str
    capability: str
    scope: frozenset[str]
    target_profile: str


class ServiceGateway:
    def __init__(self, broker: CapabilityBroker, host: HostRecorder, *, limits: Limits = DEFAULT_LIMITS):
        self.broker = broker
        self.host = host
        self.limits = limits
        self.request_counts: dict[tuple[int, str], int] = {}

    def raw_host_call(self, principal: str, api: str, *, target_profile: str) -> None:
        if api in FORBIDDEN_RAW_HOST_APIS:
            raise CapabilityDenied("raw_host_api_forbidden", api)
        raise CapabilityDenied("unknown_raw_host_api", api)

    def stage(self, principal: str, capability: str, scope: Iterable[str], *, target_profile: str, tick: int) -> PendingService:
        if target_profile not in TARGETS:
            raise MalformedInput("unknown_target_profile", target_profile)
        profile = TARGETS[target_profile]
        if capability not in profile.semantic_services:
            raise CapabilityDenied("service_unavailable_on_target", capability)
        # Admission check. A second live check occurs immediately before host call.
        self.broker.authorize(principal, capability, scope, tick=tick)
        key = (tick, principal)
        count = self.request_counts.get(key, 0) + 1
        if count > self.limits.max_service_requests:
            raise ResourceLimitExceeded("service_request_budget_exceeded")
        self.request_counts[key] = count
        return PendingService(principal, capability, frozenset(scope), target_profile)

    def flush(self, pending: PendingService, *, tick: int) -> str:
        profile = TARGETS[pending.target_profile]
        if pending.capability not in profile.semantic_services:
            raise CapabilityDenied("service_unavailable_on_target", pending.capability)
        # Critical use-time check: revocation/change between staging and execution
        # must fail before host API invocation.
        self.broker.authorize(pending.principal, pending.capability, pending.scope, tick=tick)
        return self.host.invoke(pending.capability, pending.principal, pending.scope)


def trusted_proxy_request(
    gateway: ServiceGateway,
    *,
    child_principal: str,
    proxy_principal: str,
    requested_origin: str,
    allowed_origin: str,
    target_profile: str,
    tick: int,
) -> PendingService:
    # Changing principal is a privileged application-level proxy operation, never
    # ambient containment. Validate child input before intentionally using proxy
    # authority.
    if requested_origin != allowed_origin:
        raise CapabilityDenied("trusted_proxy_input_rejected", child_principal)
    return gateway.stage(
        proxy_principal, "network.http", {allowed_origin},
        target_profile=target_profile, tick=tick
    )


# ----------------------------- behaviour budgets -----------------------------

@dataclass
class ExecutionResult:
    instructions: int = 0
    allocations: int = 0
    emits: int = 0
    timers: int = 0
    queued: int = 0
    service_requests: int = 0


class BudgetedExecutor:
    def __init__(self, limits: Limits = DEFAULT_LIMITS) -> None:
        self.limits = limits

    def execute(self, program: Iterable[Mapping[str, Any]]) -> ExecutionResult:
        result = ExecutionResult()

        def run(instructions: Iterable[Mapping[str, Any]], depth: int = 0) -> None:
            if depth > self.limits.max_tree_depth:
                raise ResourceLimitExceeded("ir_nesting_exceeded")
            for instr in instructions:
                result.instructions += 1
                if result.instructions > self.limits.max_instructions:
                    raise ResourceLimitExceeded("instruction_budget_exceeded")
                op = instr.get("op")
                if op == "alloc":
                    amount = int(instr.get("units", 0))
                    if amount < 0:
                        raise MalformedInput("negative_allocation")
                    result.allocations += amount
                    if result.allocations > self.limits.max_alloc_units:
                        raise ResourceLimitExceeded("allocation_budget_exceeded")
                elif op == "emit":
                    result.emits += 1
                    result.queued += 1
                    if result.emits > self.limits.max_emits:
                        raise ResourceLimitExceeded("emit_budget_exceeded")
                    if result.queued > self.limits.max_queue:
                        raise ResourceLimitExceeded("runtime_queue_budget_exceeded")
                elif op == "timer":
                    result.timers += 1
                    result.queued += 1
                    if result.timers > self.limits.max_timers:
                        raise ResourceLimitExceeded("timer_budget_exceeded")
                    if result.queued > self.limits.max_queue:
                        raise ResourceLimitExceeded("runtime_queue_budget_exceeded")
                elif op == "service":
                    result.service_requests += 1
                    if result.service_requests > self.limits.max_service_requests:
                        raise ResourceLimitExceeded("service_request_budget_exceeded")
                elif op == "repeat":
                    count = int(instr.get("count", 0))
                    if count < 0 or count > self.limits.max_instructions:
                        raise ResourceLimitExceeded("repeat_bound_exceeded")
                    body = instr.get("body", ())
                    if not isinstance(body, (list, tuple)):
                        raise MalformedInput("repeat_body_invalid")
                    for _ in range(count):
                        run(body, depth + 1)
                elif op in {"noop", "set", "if"}:
                    if op == "if":
                        branch = instr.get("then", ())
                        if not isinstance(branch, (list, tuple)):
                            raise MalformedInput("if_branch_invalid")
                        run(branch, depth + 1)
                else:
                    raise MalformedInput("unknown_ir_opcode", str(op))

        run(program)
        return result


# ------------------------------- migrations ---------------------------------

@dataclass
class MigrationProbe:
    calls: int = 0

    def run(self, steps: Iterable[Mapping[str, Any]], *, limits: Limits = DEFAULT_LIMITS) -> list[dict[str, Any]]:
        self.calls += 1
        cost = 0
        output: list[dict[str, Any]] = []
        step_list = list(steps)
        if len(step_list) > limits.max_migration_steps:
            raise ResourceLimitExceeded("migration_chain_exceeded")
        for step in step_list:
            op = step.get("op")
            if op in {"service", "host", "network", "filesystem"}:
                raise CapabilityDenied("migration_host_authority_forbidden", str(op))
            step_cost = int(step.get("cost", 1))
            if step_cost < 0:
                raise MalformedInput("negative_migration_cost")
            cost += step_cost
            if cost > limits.max_migration_cost:
                raise ResourceLimitExceeded("migration_cost_exceeded")
            emit = int(step.get("emit_records", 0))
            if emit < 0:
                raise MalformedInput("negative_migration_output")
            if len(output) + emit > limits.max_migration_output_records:
                raise ResourceLimitExceeded("migration_output_exceeded")
            output.extend({"migrated": True} for _ in range(emit))
        return output


def staged_load(
    *,
    lock: LockEntry,
    observed: Artifact,
    dependency_root: str,
    dependency_graph: Mapping[str, DependencyNode],
    canonical_document: Mapping[str, Any],
    migration: MigrationProbe,
    migration_steps: Iterable[Mapping[str, Any]],
    supported_required_features: Iterable[str] = (),
    limits: Limits = DEFAULT_LIMITS,
) -> list[dict[str, Any]]:
    # No migration/behaviour runs until exact artifact, dependency and canonical
    # validation all succeed.
    validate_exact_artifact(lock, observed)
    validate_dependency_graph(dependency_root, dependency_graph, limits=limits)
    validate_canonical_document(
        canonical_document,
        supported_required_features=supported_required_features,
        limits=limits,
    )
    return migration.run(migration_steps, limits=limits)


# ------------------------------- network ------------------------------------

NETWORK_FORBIDDEN_KEYS = FORBIDDEN_DURABLE_KEYS | {
    "capability_revoke", "raw_package_load", "script_definition", "ir_definition",
}


@dataclass
class NetworkGuard:
    limits: Limits = DEFAULT_LIMITS
    counts: dict[tuple[int, str], int] = field(default_factory=dict)
    queued: int = 0

    def validate(
        self,
        message: Mapping[str, Any],
        *,
        authenticated_principal: str,
        expected_world: str,
        expected_room: str,
        current_authority_epoch: int,
        tick: int,
    ) -> None:
        if not isinstance(message, Mapping):
            raise MalformedInput("network_message_must_be_object")
        encoded = json.dumps(
            message, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(encoded) > self.limits.max_network_bytes:
            raise ResourceLimitExceeded("network_message_bytes_exceeded")
        validate_bounded_tree(
            message,
            limits=self.limits,
            forbidden_keys=NETWORK_FORBIDDEN_KEYS,
            max_depth=self.limits.max_network_depth,
            max_nodes=self.limits.max_network_nodes,
        )
        if message.get("sender") != authenticated_principal:
            raise CapabilityDenied("network_sender_forgery")
        if message.get("world") != expected_world:
            raise CapabilityDenied("cross_world_message")
        if message.get("room") != expected_room:
            raise CapabilityDenied("cross_room_message")
        if message.get("authority_epoch") != current_authority_epoch:
            raise CapabilityDenied("stale_or_forged_authority_epoch")
        kind = message.get("kind")
        if kind not in {"state", "event", "input", "baseline", "application"}:
            raise MalformedInput("network_kind_forbidden", str(kind))
        key = (tick, authenticated_principal)
        count = self.counts.get(key, 0) + 1
        if count > self.limits.max_network_messages_per_tick:
            raise ResourceLimitExceeded("network_rate_budget_exceeded")
        self.counts[key] = count
        self.queued += 1
        if self.queued > self.limits.max_network_queue:
            raise ResourceLimitExceeded("network_queue_budget_exceeded")

    def consume(self, count: int = 1) -> None:
        self.queued = max(0, self.queued - count)


# --------------------------- protected media / decode ------------------------

@dataclass(frozen=True)
class AssetRevision:
    asset_id: str
    digest: str
    source_identity: str
    source_metadata: tuple[str, ...]
    media_semantics: tuple[str, ...]
    provenance: tuple[str, ...]
    license_expression: str
    derivation: tuple[str, ...]

    def validate(self) -> None:
        values = {
            "asset_id": self.asset_id,
            "digest": self.digest,
            "source_identity": self.source_identity,
            "source_metadata": self.source_metadata,
            "media_semantics": self.media_semantics,
            "provenance": self.provenance,
            "license_expression": self.license_expression,
            "derivation": self.derivation,
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise MalformedInput("incomplete_protected_asset_revision", ",".join(missing))
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest):
            raise MalformedInput("invalid_protected_asset_digest")


def atomic_replace_asset(current: AssetRevision, replacement: AssetRevision) -> AssetRevision:
    if replacement.asset_id != current.asset_id:
        raise MalformedInput("asset_identity_changed")
    replacement.validate()
    return replacement


@dataclass(frozen=True)
class MediaDescriptor:
    digest: str
    compressed_bytes: int
    decoded_bytes: int
    media_kind: str
    width: int = 0
    height: int = 0
    audio_frames: int = 0


def validate_before_decode(
    descriptor: MediaDescriptor, host: HostRecorder, *, limits: Limits = DEFAULT_LIMITS
) -> None:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", descriptor.digest):
        raise MalformedInput("invalid_media_digest")
    if descriptor.compressed_bytes < 0 or descriptor.decoded_bytes < 0:
        raise MalformedInput("negative_media_size")
    if descriptor.compressed_bytes > limits.max_asset_compressed_bytes:
        raise ResourceLimitExceeded("asset_compressed_bytes_exceeded")
    if descriptor.decoded_bytes > limits.max_asset_decoded_bytes:
        raise ResourceLimitExceeded("asset_decoded_bytes_exceeded")
    if descriptor.media_kind == "image":
        if descriptor.width <= 0 or descriptor.height <= 0:
            raise MalformedInput("invalid_image_dimensions")
        if descriptor.width * descriptor.height > limits.max_image_pixels:
            raise ResourceLimitExceeded("image_pixel_budget_exceeded")
    elif descriptor.media_kind == "audio":
        if descriptor.audio_frames < 0:
            raise MalformedInput("invalid_audio_frames")
        if descriptor.audio_frames > limits.max_audio_frames:
            raise ResourceLimitExceeded("audio_frame_budget_exceeded")
    else:
        raise MalformedInput("unsupported_media_kind", descriptor.media_kind)
    host.decoder_calls += 1


def sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
