"""Production Godot target boundary for SplashMX.

SMX-038 implements the first production realization selected by SMX-037:
stable semantic Thing identities index sparse, target-private Godot bindings,
while one centralized bridge feeds normalized engine input into the existing
SMX-026 scheduler.  Godot handles and media derivatives remain transient and
never become canonical or WorldSave identity.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from splashmx.canonical.core import AssetId, ThingId
from splashmx.execution.ir import ExecutionRuntime
from splashmx.security.capabilities import (
    CapabilityId,
    HostServiceAdapter,
    ServiceTarget,
)


_ALLOWED_FEATURES = frozenset({"render_2d", "input", "physics_2d", "audio_basic"})
_FORBIDDEN_TARGET_FIELDS = frozenset({
    "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
    "databaserowid", "cachekey", "url", "transportpeerid", "connectionhandle",
    "socketid", "sessionid", "processhandle", "hosthandle", "hostobject",
    "instanceid", "godotobjectid", "capabilitytoken", "capabilitygrant",
})
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
MAX_TARGET_VALUE_DEPTH = 32
MAX_TARGET_VALUE_NODES = 20_000
MAX_TARGET_STRING_BYTES = 2 * 1024 * 1024

CAP_RENDER = CapabilityId("godot.render")
CAP_AUDIO = CapabilityId("godot.audio")
CAP_INPUT = CapabilityId("godot.input")
CAP_PHYSICS = CapabilityId("godot.physics")


class GodotRuntimeError(ValueError):
    """Typed target/runtime failure suitable for the production failure envelope."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise GodotRuntimeError(code, message)


def _normalise_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _validate_token(value: str, role: str) -> None:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        _fail("godot.invalid_identity", f"{role} must be a bounded semantic token")


def validate_target_value(
    value: Any,
    *,
    where: str = "target value",
    depth: int = 0,
    counter: list[int] | None = None,
) -> None:
    """Reject serialized engine/transport/process authority at the adapter boundary."""

    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_TARGET_VALUE_NODES:
        _fail("godot.value_limit", f"{where} exceeds node limit")
    if depth > MAX_TARGET_VALUE_DEPTH:
        _fail("godot.value_limit", f"{where} exceeds depth limit")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            _fail("godot.invalid_value", f"{where} contains non-finite number")
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_TARGET_STRING_BYTES:
            _fail("godot.value_limit", f"{where} string exceeds byte limit")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_target_value(
                child, where=f"{where}[{index}]", depth=depth + 1, counter=counter
            )
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("godot.invalid_value", f"{where} map keys must be strings")
            if _normalise_field_name(key) in _FORBIDDEN_TARGET_FIELDS:
                _fail(
                    "godot.forbidden_transient_identity",
                    f"{where} contains forbidden engine/runtime field {key!r}",
                )
            validate_target_value(
                child, where=f"{where}.{key}", depth=depth + 1, counter=counter
            )
        return
    _fail(
        "godot.invalid_value",
        f"{where} contains unsupported target value type {type(value).__name__}",
    )


class RuntimeProfileName(str, Enum):
    NATIVE = "native"
    BROWSER = "browser"
    HEADLESS = "headless"


@dataclass(frozen=True)
class TargetProfile:
    name: RuntimeProfileName
    available_features: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.name, RuntimeProfileName):
            _fail("godot.invalid_profile", "profile name must be RuntimeProfileName")
        unknown = set(self.available_features) - _ALLOWED_FEATURES
        if unknown:
            _fail(
                "godot.unknown_feature",
                f"profile contains unsupported target features: {sorted(unknown)}",
            )


NATIVE_PROFILE = TargetProfile(RuntimeProfileName.NATIVE, _ALLOWED_FEATURES)
BROWSER_PROFILE = TargetProfile(RuntimeProfileName.BROWSER, _ALLOWED_FEATURES)
HEADLESS_PROFILE = TargetProfile(
    RuntimeProfileName.HEADLESS, frozenset({"physics_2d"})
)


@dataclass(frozen=True, order=True)
class ProtectedAssetRef:
    """Exact reference to one indivisible canonical protected Asset revision."""

    asset_id: AssetId
    revision_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, AssetId):
            _fail("godot.invalid_asset_ref", "asset_id must be AssetId")
        if (
            not isinstance(self.revision_digest, str)
            or not self.revision_digest
            or len(self.revision_digest.encode("utf-8")) > 256
        ):
            _fail(
                "godot.invalid_asset_ref",
                "protected Asset revision digest must be a bounded non-empty string",
            )


@dataclass(frozen=True)
class ThingProjection:
    thing_id: ThingId
    facets: tuple[str, ...]
    author_order: int

    def __post_init__(self) -> None:
        if not isinstance(self.thing_id, ThingId):
            _fail("godot.invalid_projection", "thing_id must be ThingId")
        if (
            not isinstance(self.author_order, int)
            or isinstance(self.author_order, bool)
            or self.author_order < 0
        ):
            _fail("godot.invalid_projection", "author_order must be a non-negative integer")
        if len(self.facets) != len(set(self.facets)):
            _fail("godot.invalid_projection", "Thing target facets must be unique")
        unknown = set(self.facets) - _ALLOWED_FEATURES
        if unknown:
            _fail(
                "godot.unknown_feature",
                f"Thing {self.thing_id} requests unsupported facets: {sorted(unknown)}",
            )


@dataclass(frozen=True)
class RuntimeProjection:
    """Target projection only; it never owns canonical source/media/provenance fields."""

    things: tuple[ThingProjection, ...]
    protected_assets: tuple[ProtectedAssetRef, ...]
    required_features: frozenset[str]
    optional_features: frozenset[str]

    def __post_init__(self) -> None:
        if self.required_features & self.optional_features:
            _fail(
                "godot.invalid_projection",
                "features cannot be both required and optional",
            )
        declared = self.required_features | self.optional_features
        unknown = declared - _ALLOWED_FEATURES
        if unknown:
            _fail(
                "godot.unknown_feature",
                f"projection declares unsupported features: {sorted(unknown)}",
            )
        thing_ids = [row.thing_id for row in self.things]
        if len(thing_ids) != len(set(thing_ids)):
            _fail("godot.duplicate_thing", "target projection contains duplicate ThingId")
        orders = [row.author_order for row in self.things]
        if len(orders) != len(set(orders)):
            _fail(
                "godot.duplicate_author_order",
                "target projection author_order values must be unique",
            )
        for row in self.things:
            undeclared = set(row.facets) - declared
            if undeclared:
                _fail(
                    "godot.undeclared_feature",
                    f"Thing {row.thing_id} requests undeclared target facets: {sorted(undeclared)}",
                )
        seen_assets: dict[AssetId, str] = {}
        for ref in self.protected_assets:
            if not isinstance(ref, ProtectedAssetRef):
                _fail(
                    "godot.invalid_asset_ref",
                    "protected_assets must contain ProtectedAssetRef values",
                )
            existing = seen_assets.get(ref.asset_id)
            if existing is not None and existing != ref.revision_digest:
                _fail(
                    "godot.protected_asset_conflict",
                    f"AssetId {ref.asset_id} is bound to competing protected revisions",
                )
            if existing is not None:
                _fail(
                    "godot.duplicate_asset_ref",
                    f"AssetId {ref.asset_id} appears more than once in target projection",
                )
            seen_assets[ref.asset_id] = ref.revision_digest


@dataclass(frozen=True)
class PreparedThing:
    thing_id: ThingId
    active_facets: tuple[str, ...]
    author_order: int


@dataclass(frozen=True)
class PreparedProjection:
    profile: RuntimeProfileName
    things: tuple[PreparedThing, ...]
    protected_assets: tuple[ProtectedAssetRef, ...]
    degraded_optional_features: tuple[str, ...]


def prepare_profile(
    projection: RuntimeProjection,
    profile: TargetProfile,
) -> PreparedProjection:
    """Prepare a target profile before any host object is materialized."""

    if not isinstance(projection, RuntimeProjection) or not isinstance(profile, TargetProfile):
        _fail("godot.invalid_projection", "prepare_profile needs typed projection/profile")
    missing_required = projection.required_features - profile.available_features
    if missing_required:
        _fail(
            "godot.required_feature_unavailable",
            f"{profile.name.value} lacks required features: {sorted(missing_required)}",
        )
    active = projection.required_features | (
        projection.optional_features & profile.available_features
    )
    degraded = tuple(sorted(projection.optional_features - profile.available_features))
    prepared = tuple(
        PreparedThing(
            thing_id=row.thing_id,
            active_facets=tuple(facet for facet in row.facets if facet in active),
            author_order=row.author_order,
        )
        for row in sorted(projection.things, key=lambda item: item.author_order)
    )
    return PreparedProjection(
        profile=profile.name,
        things=prepared,
        protected_assets=projection.protected_assets,
        degraded_optional_features=degraded,
    )


@dataclass
class PrivateBinding:
    """Transient target binding. ``objects`` must never be serialized."""

    thing_id: ThingId
    active_facets: tuple[str, ...]
    generation: int
    objects: tuple[Any, ...]


@dataclass
class _BindingCandidate:
    profile: RuntimeProfileName
    bindings: dict[ThingId, PrivateBinding]


class BindingTable:
    """Sparse prepare-before-publish target-private binding table."""

    def __init__(
        self,
        object_factory: Callable[[ThingId, tuple[str, ...]], Sequence[Any]],
        object_destructor: Callable[[Any], None],
        *,
        max_bindings: int = 100_000,
        max_objects: int = 500_000,
    ) -> None:
        if not callable(object_factory) or not callable(object_destructor):
            _fail("godot.invalid_adapter", "binding factory/destructor must be trusted callables")
        for name, value in (("max_bindings", max_bindings), ("max_objects", max_objects)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                _fail("godot.invalid_limit", f"{name} must be a positive integer")
        self._factory = object_factory
        self._destructor = object_destructor
        self.max_bindings = max_bindings
        self.max_objects = max_objects
        self._bindings: dict[ThingId, PrivateBinding] = {}
        self._generation: dict[ThingId, int] = {}
        self.profile: RuntimeProfileName | None = None

    @property
    def object_count(self) -> int:
        return sum(len(binding.objects) for binding in self._bindings.values())

    @property
    def bound_thing_count(self) -> int:
        return len(self._bindings)

    def _destroy_objects(self, objects: Sequence[Any]) -> None:
        for obj in objects:
            try:
                self._destructor(obj)
            except Exception as exc:
                raise GodotRuntimeError(
                    "godot.binding_cleanup_failed",
                    "trusted target binding cleanup failed",
                ) from exc

    def _create_binding(self, row: PreparedThing) -> PrivateBinding:
        try:
            objects = tuple(self._factory(row.thing_id, row.active_facets))
        except GodotRuntimeError:
            raise
        except Exception as exc:
            raise GodotRuntimeError(
                "godot.binding_materialization_failed",
                f"trusted target binding materialization failed for {row.thing_id}",
            ) from exc
        generation = self._generation.get(row.thing_id, 0) + 1
        return PrivateBinding(row.thing_id, row.active_facets, generation, objects)

    def prepare(self, projection: PreparedProjection) -> _BindingCandidate:
        if len(projection.things) > self.max_bindings:
            _fail("godot.binding_limit", "target projection exceeds binding limit")
        candidate: dict[ThingId, PrivateBinding] = {}
        created_objects: list[Any] = []
        object_count = 0
        try:
            for row in projection.things:
                binding = self._create_binding(row)
                object_count += len(binding.objects)
                if object_count > self.max_objects:
                    _fail("godot.object_limit", "target projection exceeds private object limit")
                candidate[row.thing_id] = binding
                created_objects.extend(binding.objects)
        except Exception:
            for obj in reversed(created_objects):
                try:
                    self._destructor(obj)
                except Exception:
                    pass
            raise
        return _BindingCandidate(projection.profile, candidate)

    def publish(self, candidate: _BindingCandidate) -> None:
        if not isinstance(candidate, _BindingCandidate):
            _fail("godot.invalid_binding_candidate", "publish requires prepared binding candidate")
        old = self._bindings
        self._bindings = candidate.bindings
        self.profile = candidate.profile
        for thing_id, binding in self._bindings.items():
            self._generation[thing_id] = binding.generation
        # Old bindings are private implementation state. Candidate publication is
        # complete before cleanup so cleanup order cannot redefine semantic identity.
        for binding in old.values():
            self._destroy_objects(binding.objects)

    def materialize(self, projection: PreparedProjection) -> None:
        self.publish(self.prepare(projection))

    def destroy(self, thing_id: ThingId) -> None:
        binding = self._bindings.pop(thing_id, None)
        if binding is not None:
            self._destroy_objects(binding.objects)

    def recreate(self, row: PreparedThing) -> None:
        old = self._bindings.get(row.thing_id)
        candidate = self._create_binding(row)
        if self.object_count - (len(old.objects) if old else 0) + len(candidate.objects) > self.max_objects:
            self._destroy_objects(candidate.objects)
            _fail("godot.object_limit", "binding replacement would exceed private object limit")
        self._bindings[row.thing_id] = candidate
        self._generation[row.thing_id] = candidate.generation
        if old is not None:
            self._destroy_objects(old.objects)

    def active_facets(self, thing_id: ThingId) -> tuple[str, ...]:
        binding = self._bindings.get(thing_id)
        if binding is None:
            _fail("godot.unknown_binding", f"Thing {thing_id} has no current target binding")
        return binding.active_facets

    def private_objects(self, thing_id: ThingId) -> tuple[Any, ...]:
        """Trusted target code only; returned objects are never canonical identity."""

        binding = self._bindings.get(thing_id)
        if binding is None:
            _fail("godot.unknown_binding", f"Thing {thing_id} has no current target binding")
        return binding.objects

    def semantic_view(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Safe diagnostic view: stable IDs/facets only, never engine handles."""

        return tuple(
            (str(binding.thing_id), binding.active_facets)
            for binding in sorted(self._bindings.values(), key=lambda row: str(row.thing_id))
        )

    def clear(self) -> None:
        old = self._bindings
        self._bindings = {}
        self.profile = None
        for binding in old.values():
            self._destroy_objects(binding.objects)


@dataclass(frozen=True)
class EngineEvent:
    """Normalized engine input captured without executing semantic Behaviour code."""

    thing_id: ThingId
    trigger: str
    payload: Any
    logical_tick: int
    author_order: int
    source_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.thing_id, ThingId):
            _fail("godot.invalid_event", "engine event thing_id must be ThingId")
        if not isinstance(self.trigger, str) or not self.trigger:
            _fail("godot.invalid_event", "engine event trigger must be non-empty")
        for name, value in (
            ("logical_tick", self.logical_tick),
            ("author_order", self.author_order),
            ("source_sequence", self.source_sequence),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                _fail("godot.invalid_event", f"{name} must be a non-negative integer")
        validate_target_value(self.payload, where="normalized engine event payload")


class SemanticTurnBridge:
    """Central bridge from engine callbacks into the SMX-026 scheduler."""

    def __init__(
        self,
        runtime: ExecutionRuntime,
        *,
        max_pending_inputs: int = 4096,
    ) -> None:
        if not isinstance(runtime, ExecutionRuntime):
            _fail("godot.invalid_scheduler", "bridge requires production ExecutionRuntime")
        if (
            not isinstance(max_pending_inputs, int)
            or isinstance(max_pending_inputs, bool)
            or max_pending_inputs <= 0
        ):
            _fail("godot.invalid_limit", "max_pending_inputs must be a positive integer")
        self.runtime = runtime
        self.max_pending_inputs = max_pending_inputs
        self._pending: list[EngineEvent] = []

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def capture(self, event: EngineEvent) -> None:
        if not isinstance(event, EngineEvent):
            _fail("godot.invalid_event", "bridge accepts only EngineEvent values")
        if len(self._pending) >= self.max_pending_inputs:
            _fail("godot.input_queue_limit", "normalized engine-input queue is full")
        self._pending.append(
            EngineEvent(
                event.thing_id,
                event.trigger,
                deepcopy(event.payload),
                event.logical_tick,
                event.author_order,
                event.source_sequence,
            )
        )

    @staticmethod
    def _key(event: EngineEvent) -> tuple[int, int, int, str, str]:
        return (
            event.logical_tick,
            event.author_order,
            event.source_sequence,
            str(event.thing_id),
            event.trigger,
        )

    def flush_to_scheduler(self) -> int:
        ordered = sorted(self._pending, key=self._key)
        self._pending = []
        dispatched = 0
        for index, event in enumerate(ordered):
            try:
                dispatched += self.runtime.dispatch(
                    event.thing_id,
                    event.trigger,
                    deepcopy(event.payload),
                    due_tick=event.logical_tick,
                )
            except Exception:
                # Preserve not-yet-forwarded normalized inputs. Prefix events are
                # already explicit scheduler work and are not replayed.
                self._pending = ordered[index:] + self._pending
                raise
        return dispatched


class GodotHost(Protocol):
    """Trusted physical host implementation; never exposed to user content."""

    def render(self, payload: Mapping[str, Any]) -> Any: ...
    def audio(self, payload: Mapping[str, Any]) -> Any: ...
    def input(self, payload: Mapping[str, Any]) -> Any: ...
    def physics(self, payload: Mapping[str, Any]) -> Any: ...


def _service_target(payload: Any, *, family: str) -> ServiceTarget:
    validate_target_value(payload, where=f"{family} service payload")
    if not isinstance(payload, Mapping):
        _fail("godot.invalid_service_request", "Godot service payload must be a mapping")
    allowed = {"thing_id", "operation", "byte_count", "asset_id", "revision_digest", "value"}
    extra = set(payload) - allowed
    if extra:
        _fail(
            "godot.invalid_service_request",
            f"Godot service payload contains unknown fields: {sorted(extra)}",
        )
    thing_id = payload.get("thing_id")
    operation = payload.get("operation")
    if not isinstance(thing_id, str):
        _fail("godot.invalid_service_request", "Godot service requires string thing_id")
    _validate_token(thing_id, "ThingId")
    if not isinstance(operation, str) or not operation:
        _fail("godot.invalid_service_request", "Godot service requires operation")
    byte_count = payload.get("byte_count", 0)
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        _fail("godot.invalid_service_request", "byte_count must be a non-negative integer")
    if ("asset_id" in payload) != ("revision_digest" in payload):
        _fail(
            "godot.invalid_service_request",
            "asset_id and revision_digest must be supplied together",
        )
    if "asset_id" in payload:
        _validate_token(payload["asset_id"], "AssetId")
        digest = payload["revision_digest"]
        if not isinstance(digest, str) or not digest or len(digest.encode("utf-8")) > 256:
            _fail("godot.invalid_service_request", "revision_digest must be bounded")
    return ServiceTarget(
        target=f"thing:{thing_id}",
        operation=f"{family}:{operation}",
        byte_count=byte_count,
    )


def build_host_service_adapters(host: GodotHost) -> tuple[HostServiceAdapter, ...]:
    """Bind physical Godot effects behind the SMX-027 final-use authorization seam."""

    methods = (
        ("godot.render", CAP_RENDER, "render", host.render),
        ("godot.audio", CAP_AUDIO, "audio", host.audio),
        ("godot.input", CAP_INPUT, "input", host.input),
        ("godot.physics", CAP_PHYSICS, "physics", host.physics),
    )
    adapters: list[HostServiceAdapter] = []
    for service_name, capability_id, family, invoke in methods:
        if not callable(invoke):
            _fail("godot.invalid_adapter", f"trusted host lacks callable {family} adapter")
        adapters.append(
            HostServiceAdapter(
                service_name=service_name,
                capability_id=capability_id,
                target_resolver=lambda payload, family=family: _service_target(
                    payload, family=family
                ),
                invoke=lambda payload, invoke=invoke: invoke(deepcopy(payload)),
            )
        )
    return tuple(adapters)


@dataclass(frozen=True)
class MediaDerivativeKey:
    asset_id: AssetId
    revision_digest: str
    profile: RuntimeProfileName
    derivative_kind: str

    def __post_init__(self) -> None:
        ProtectedAssetRef(self.asset_id, self.revision_digest)
        if not isinstance(self.profile, RuntimeProfileName):
            _fail("godot.invalid_derivative", "derivative profile must be RuntimeProfileName")
        _validate_token(self.derivative_kind, "derivative_kind")


@dataclass
class _DerivativeRecord:
    key: MediaDerivativeKey
    handle: Any


class MediaDerivativeCache:
    """Target-private media cache bound to exact canonical protected revisions."""

    def __init__(
        self,
        protected_assets: Sequence[ProtectedAssetRef],
        *,
        max_entries: int = 4096,
        destructor: Callable[[Any], None] | None = None,
    ) -> None:
        if not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries <= 0:
            _fail("godot.invalid_limit", "max_entries must be a positive integer")
        self.max_entries = max_entries
        self._destructor = destructor or (lambda _value: None)
        if not callable(self._destructor):
            _fail("godot.invalid_adapter", "media derivative destructor must be callable")
        self._revisions: dict[AssetId, str] = {}
        for ref in protected_assets:
            if not isinstance(ref, ProtectedAssetRef):
                _fail("godot.invalid_asset_ref", "cache needs exact ProtectedAssetRef values")
            existing = self._revisions.get(ref.asset_id)
            if existing is not None and existing != ref.revision_digest:
                _fail(
                    "godot.protected_asset_conflict",
                    f"AssetId {ref.asset_id} has competing canonical revisions",
                )
            if existing is not None:
                _fail("godot.duplicate_asset_ref", f"duplicate AssetId {ref.asset_id}")
            self._revisions[ref.asset_id] = ref.revision_digest
        self._entries: dict[MediaDerivativeKey, _DerivativeRecord] = {}

    def _require_exact_ref(self, ref: ProtectedAssetRef) -> None:
        expected = self._revisions.get(ref.asset_id)
        if expected is None:
            _fail("godot.unknown_asset", f"AssetId {ref.asset_id} is not in active projection")
        if expected != ref.revision_digest:
            _fail(
                "godot.protected_asset_conflict",
                f"AssetId {ref.asset_id} derivative requested for competing revision",
            )

    def put(
        self,
        ref: ProtectedAssetRef,
        *,
        profile: RuntimeProfileName,
        derivative_kind: str,
        handle: Any,
    ) -> MediaDerivativeKey:
        self._require_exact_ref(ref)
        key = MediaDerivativeKey(ref.asset_id, ref.revision_digest, profile, derivative_kind)
        if key not in self._entries and len(self._entries) >= self.max_entries:
            _fail("godot.derivative_cache_limit", "media derivative cache is full")
        old = self._entries.get(key)
        self._entries[key] = _DerivativeRecord(key, handle)
        if old is not None and old.handle is not handle:
            self._destructor(old.handle)
        return key

    def get(self, key: MediaDerivativeKey) -> Any | None:
        record = self._entries.get(key)
        return None if record is None else record.handle

    def evict(self, key: MediaDerivativeKey) -> None:
        record = self._entries.pop(key, None)
        if record is not None:
            self._destructor(record.handle)

    def protected_refs(self) -> tuple[ProtectedAssetRef, ...]:
        return tuple(
            ProtectedAssetRef(asset_id, digest)
            for asset_id, digest in sorted(
                self._revisions.items(), key=lambda row: str(row[0])
            )
        )

    def clear(self) -> None:
        records = list(self._entries.values())
        self._entries.clear()
        for record in records:
            self._destructor(record.handle)
