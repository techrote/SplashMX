"""SMX-030 logical streaming, exact acquisition and immutable cache.

This module deliberately keeps three concerns separate:

* semantic identity/reference state is owned by the canonical document and WorldRuntime;
* logical residency is an explicit lifecycle decision for selected Things/subgraphs;
* physical dependency bytes live behind exact immutable descriptors and an evictable cache.

Cache location, fetch location and containment hierarchy are therefore never durable
identity. Acquisition is prepare-before-publish: every exact dependency is fetched,
digest/size checked, decoded/migrated and reconciled before any Thing is rehydrated.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re
from typing import Any, Callable, Mapping, Sequence

from splashmx.canonical.core import (
    AssetId,
    BehaviourAttachmentId,
    ReferenceState,
    ThingId,
)
from splashmx.canonical.serialization import (
    CanonicalProjectRevision,
    ProtectedAssetRevision,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
    serialize_project,
)
from splashmx.execution.ir import IRHandler, IRInstruction, IRProgram, validate_program
from splashmx.runtime.lifecycle import LifecycleError, WorldRuntime
from splashmx.security.capabilities import CapabilityBroker, CapabilityRequirement

STREAM_PROJECT_FORMAT = "splashmx.stream-project-artifact/1"
STREAM_IR_FORMAT = "splashmx.stream-behaviour-ir/1"
MAX_ARTIFACT_ID_BYTES = 512
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class StreamingError(ValueError):
    """Stable typed streaming/acquisition failure."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _fail(code: str, message: str) -> None:
    raise StreamingError(code, message)


class ArtifactKind(str, Enum):
    CANONICAL_SUBGRAPH = "canonical-subgraph"
    BEHAVIOUR_IR = "behaviour-ir"
    OPAQUE_EXACT = "opaque-exact"


@dataclass(frozen=True)
class ExactArtifactDescriptor:
    """One exact immutable physical dependency.

    ``artifact_id`` is only a manifest-local semantic label. The immutable physical
    identity is the digest+length pair; URLs, paths and cache keys are not represented.
    """

    artifact_id: str
    kind: ArtifactKind
    digest: str
    size_bytes: int
    dependencies: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.artifact_id, str)
            or not self.artifact_id
            or len(self.artifact_id.encode("utf-8")) > MAX_ARTIFACT_ID_BYTES
        ):
            _fail("streaming.invalid_descriptor", "artifact_id must be bounded non-empty text")
        if not isinstance(self.kind, ArtifactKind):
            _fail("streaming.invalid_descriptor", "artifact kind must be ArtifactKind")
        if not isinstance(self.digest, str) or _DIGEST_RE.fullmatch(self.digest) is None:
            _fail("streaming.invalid_descriptor", "artifact digest must be sha256:<64 lowercase hex>")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            _fail("streaming.invalid_descriptor", "artifact size must be a non-negative integer")
        if len(set(self.dependencies)) != len(self.dependencies):
            _fail("streaming.invalid_descriptor", "dependency list contains duplicates")
        for value in self.dependencies:
            if not isinstance(value, str) or not value:
                _fail("streaming.invalid_descriptor", "dependency IDs must be non-empty text")
        if len(set(self.required_features)) != len(self.required_features):
            _fail("streaming.invalid_descriptor", "required feature list contains duplicates")
        for value in self.required_features:
            if not isinstance(value, str) or not value:
                _fail("streaming.invalid_descriptor", "required features must be non-empty text")
        if not isinstance(self.media_type, str) or not self.media_type:
            _fail("streaming.invalid_descriptor", "media_type must be non-empty text")


@dataclass(frozen=True)
class AcquisitionLimits:
    max_descriptors: int = 512
    max_depth: int = 64
    max_total_bytes: int = 128 * 1024 * 1024
    max_artifact_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                _fail("streaming.invalid_limits", f"{name} must be a positive integer")


@dataclass(frozen=True)
class ThingStreamSpec:
    thing_id: ThingId
    root_artifact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.thing_id, ThingId):
            _fail("streaming.invalid_catalog", "ThingStreamSpec requires ThingId")
        if not self.root_artifact_ids or len(set(self.root_artifact_ids)) != len(self.root_artifact_ids):
            _fail("streaming.invalid_catalog", "stream roots must be non-empty and unique")
        if any(not isinstance(value, str) or not value for value in self.root_artifact_ids):
            _fail("streaming.invalid_catalog", "stream root IDs must be non-empty text")


@dataclass(frozen=True)
class AcquisitionResult:
    payloads: Mapping[str, bytes]
    ordered_artifact_ids: tuple[str, ...]
    cache_hits: tuple[str, ...]


@dataclass(frozen=True)
class StreamOutcome:
    thing_ids: tuple[ThingId, ...]
    acquired_artifact_ids: tuple[str, ...]
    cache_hits: tuple[str, ...]


def exact_digest(payload: bytes) -> str:
    if not isinstance(payload, (bytes, bytearray)):
        _fail("streaming.invalid_payload", "artifact payload must be bytes")
    return "sha256:" + sha256(bytes(payload)).hexdigest()


class ImmutableArtifactCache:
    """Evictable verified bytes keyed only by immutable digest.

    Cache membership is explicitly non-semantic. Capacity pressure never rewrites a
    descriptor or canonical record, and eviction cannot alter WorldSave state.
    """

    def __init__(self, *, max_entries: int = 1024, max_bytes: int = 256 * 1024 * 1024):
        if max_entries <= 0 or max_bytes <= 0:
            _fail("streaming.invalid_cache_limit", "cache limits must be positive")
        self.max_entries = int(max_entries)
        self.max_bytes = int(max_bytes)
        self._payloads: dict[str, bytes] = {}
        self._bytes = 0

    @property
    def entry_count(self) -> int:
        return len(self._payloads)

    @property
    def byte_count(self) -> int:
        return self._bytes

    def contains(self, descriptor: ExactArtifactDescriptor) -> bool:
        return descriptor.digest in self._payloads

    def get(self, descriptor: ExactArtifactDescriptor) -> bytes | None:
        payload = self._payloads.get(descriptor.digest)
        if payload is None:
            return None
        _verify_payload(descriptor, payload)
        return bytes(payload)

    def put(self, descriptor: ExactArtifactDescriptor, payload: bytes) -> bool:
        data = bytes(payload)
        _verify_payload(descriptor, data)
        prior = self._payloads.get(descriptor.digest)
        if prior is not None:
            if prior != data:
                _fail("streaming.cache_integrity_failure", "immutable digest is bound to different bytes")
            return True
        if len(self._payloads) + 1 > self.max_entries or self._bytes + len(data) > self.max_bytes:
            return False
        self._payloads[descriptor.digest] = data
        self._bytes += len(data)
        return True

    def evict(self, descriptor: ExactArtifactDescriptor) -> bool:
        payload = self._payloads.pop(descriptor.digest, None)
        if payload is None:
            return False
        self._bytes -= len(payload)
        return True

    def evict_digest(self, digest: str) -> bool:
        payload = self._payloads.pop(digest, None)
        if payload is None:
            return False
        self._bytes -= len(payload)
        return True

    def clear(self) -> None:
        self._payloads.clear()
        self._bytes = 0


ArtifactFetcher = Callable[[ExactArtifactDescriptor], bytes | None]
CancelCheck = Callable[[], bool]


class MappingArtifactSource:
    """Deterministic test/local source keyed by manifest-local artifact ID."""

    def __init__(self, payloads: Mapping[str, bytes]):
        self.payloads = {key: bytes(value) for key, value in payloads.items()}

    def __call__(self, descriptor: ExactArtifactDescriptor) -> bytes | None:
        payload = self.payloads.get(descriptor.artifact_id)
        return None if payload is None else bytes(payload)


def _verify_payload(descriptor: ExactArtifactDescriptor, payload: bytes) -> None:
    if len(payload) != descriptor.size_bytes:
        _fail(
            "streaming.integrity_failure",
            f"artifact {descriptor.artifact_id!r} length does not match exact descriptor",
        )
    if exact_digest(payload) != descriptor.digest:
        _fail(
            "streaming.integrity_failure",
            f"artifact {descriptor.artifact_id!r} digest does not match exact descriptor",
        )


class ExactAcquirer:
    """Resolve and fetch a bounded exact dependency closure."""

    def __init__(
        self,
        descriptors: Mapping[str, ExactArtifactDescriptor],
        fetcher: ArtifactFetcher,
        cache: ImmutableArtifactCache,
        *,
        limits: AcquisitionLimits | None = None,
        supported_features: Sequence[str] = (),
    ):
        self.descriptors = dict(descriptors)
        self.fetcher = fetcher
        self.cache = cache
        self.limits = limits or AcquisitionLimits()
        self.supported_features = frozenset(supported_features)
        for key, descriptor in self.descriptors.items():
            if key != descriptor.artifact_id:
                _fail("streaming.invalid_descriptor", "descriptor map key does not match artifact_id")

    def _closure(self, roots: Sequence[str]) -> tuple[str, ...]:
        if not roots:
            _fail("streaming.invalid_request", "at least one exact dependency root is required")
        seen: set[str] = set()
        ordered: list[str] = []

        def visit(artifact_id: str, depth: int, ancestry: frozenset[str]) -> None:
            if depth > self.limits.max_depth:
                _fail("streaming.dependency_depth_limit", "exact dependency graph exceeds depth bound")
            descriptor = self.descriptors.get(artifact_id)
            if descriptor is None:
                _fail("streaming.descriptor_missing", f"no exact descriptor for {artifact_id!r}")
            unknown = set(descriptor.required_features) - self.supported_features
            if unknown:
                _fail(
                    "streaming.incompatible_dependency",
                    f"artifact {artifact_id!r} requires unsupported features {sorted(unknown)}",
                )
            if artifact_id in ancestry:
                return
            if artifact_id in seen:
                return
            if len(seen) + 1 > self.limits.max_descriptors:
                _fail("streaming.dependency_count_limit", "exact dependency closure exceeds descriptor bound")
            seen.add(artifact_id)
            next_ancestry = ancestry | {artifact_id}
            for dependency in descriptor.dependencies:
                visit(dependency, depth + 1, next_ancestry)
            ordered.append(artifact_id)

        for root in roots:
            visit(root, 0, frozenset())

        total = 0
        for artifact_id in seen:
            size = self.descriptors[artifact_id].size_bytes
            if size > self.limits.max_artifact_bytes:
                _fail(
                    "streaming.artifact_size_limit",
                    f"artifact {artifact_id!r} exceeds per-artifact byte bound",
                )
            total += size
            if total > self.limits.max_total_bytes:
                _fail("streaming.total_size_limit", "exact dependency closure exceeds total byte bound")
        return tuple(ordered)

    def acquire(self, roots: Sequence[str], *, cancel_check: CancelCheck | None = None) -> AcquisitionResult:
        ordered = self._closure(tuple(roots))
        payloads: dict[str, bytes] = {}
        cache_hits: list[str] = []
        for artifact_id in ordered:
            if cancel_check is not None and cancel_check():
                _fail("streaming.cancelled", "exact acquisition was cancelled before publication")
            descriptor = self.descriptors[artifact_id]
            payload = self.cache.get(descriptor)
            if payload is not None:
                cache_hits.append(artifact_id)
            else:
                try:
                    fetched = self.fetcher(descriptor)
                except StreamingError:
                    raise
                except Exception as exc:
                    raise StreamingError(
                        "streaming.source_failure",
                        f"artifact source failed for {artifact_id!r}",
                        cause=exc,
                    ) from exc
                if fetched is None:
                    _fail("streaming.dependency_unavailable", f"exact artifact {artifact_id!r} is unavailable")
                payload = bytes(fetched)
                _verify_payload(descriptor, payload)
                self.cache.put(descriptor, payload)
            payloads[artifact_id] = bytes(payload)
        if cancel_check is not None and cancel_check():
            _fail("streaming.cancelled", "exact acquisition was cancelled before publication")
        return AcquisitionResult(payloads, ordered, tuple(cache_hits))


def descriptor_for(
    artifact_id: str,
    kind: ArtifactKind,
    payload: bytes,
    *,
    dependencies: Sequence[str] = (),
    required_features: Sequence[str] = (),
    media_type: str = "application/octet-stream",
) -> ExactArtifactDescriptor:
    data = bytes(payload)
    return ExactArtifactDescriptor(
        artifact_id,
        kind,
        exact_digest(data),
        len(data),
        tuple(dependencies),
        tuple(required_features),
        media_type,
    )


def encode_project_artifact(project: CanonicalProjectRevision) -> bytes:
    serialized = serialize_project(project)
    return encode_canonical_cbor(
        {
            "format": STREAM_PROJECT_FORMAT,
            "root_manifest": serialized.root_manifest,
            "shards": [
                {"key": key, "payload": serialized.shards[key]}
                for key in sorted(serialized.shards)
            ],
        }
    )


def decode_project_artifact(payload: bytes) -> CanonicalProjectRevision:
    try:
        value = decode_canonical_cbor(payload)
    except Exception as exc:
        code = getattr(exc, "code", "invalid_canonical_artifact")
        raise StreamingError(
            "streaming.incompatible_dependency",
            f"canonical subgraph artifact failed bounded decoding ({code})",
            cause=exc,
        ) from exc
    if not isinstance(value, dict) or set(value) != {"format", "root_manifest", "shards"}:
        _fail("streaming.incompatible_dependency", "canonical subgraph envelope is malformed")
    if value["format"] != STREAM_PROJECT_FORMAT or not isinstance(value["root_manifest"], bytes):
        _fail("streaming.incompatible_dependency", "canonical subgraph profile is unsupported")
    if not isinstance(value["shards"], list):
        _fail("streaming.incompatible_dependency", "canonical subgraph shards must be a list")
    shards: dict[str, bytes] = {}
    for row in value["shards"]:
        if not isinstance(row, dict) or set(row) != {"key", "payload"}:
            _fail("streaming.incompatible_dependency", "canonical subgraph shard entry is malformed")
        if not isinstance(row["key"], str) or not isinstance(row["payload"], bytes):
            _fail("streaming.incompatible_dependency", "canonical subgraph shard types are invalid")
        if row["key"] in shards:
            _fail("streaming.incompatible_dependency", "canonical subgraph duplicates a shard key")
        shards[row["key"]] = row["payload"]
    try:
        return deserialize_project(SerializedProjectRevision(value["root_manifest"], shards))
    except Exception as exc:
        code = getattr(exc, "code", "invalid_canonical_artifact")
        raise StreamingError(
            "streaming.incompatible_dependency",
            f"canonical subgraph validation/migration failed ({code})",
            cause=exc,
        ) from exc


def _ir_value_to_obj(value: Any) -> Any:
    if isinstance(value, IRInstruction):
        return {"$instruction": _instruction_to_obj(value)}
    if isinstance(value, tuple):
        return {"$tuple": [_ir_value_to_obj(child) for child in value]}
    if isinstance(value, list):
        return [_ir_value_to_obj(child) for child in value]
    if isinstance(value, Mapping):
        return {str(key): _ir_value_to_obj(child) for key, child in value.items()}
    return value


def _ir_value_from_obj(value: Any) -> Any:
    if isinstance(value, list):
        return [_ir_value_from_obj(child) for child in value]
    if isinstance(value, dict):
        if set(value) == {"$instruction"}:
            return _instruction_from_obj(value["$instruction"])
        if set(value) == {"$tuple"}:
            children = value["$tuple"]
            if not isinstance(children, list):
                _fail("streaming.incompatible_dependency", "IR tuple marker requires a list")
            return tuple(_ir_value_from_obj(child) for child in children)
        return {key: _ir_value_from_obj(child) for key, child in value.items()}
    return value


def _instruction_to_obj(instruction: IRInstruction) -> dict[str, Any]:
    return {"op": instruction.op, "args": _ir_value_to_obj(dict(instruction.args))}


def _instruction_from_obj(value: Any) -> IRInstruction:
    if not isinstance(value, dict) or set(value) != {"op", "args"}:
        _fail("streaming.incompatible_dependency", "IR instruction envelope is malformed")
    if not isinstance(value["op"], str) or not isinstance(value["args"], dict):
        _fail("streaming.incompatible_dependency", "IR instruction types are invalid")
    return IRInstruction(value["op"], _ir_value_from_obj(value["args"]))


def encode_ir_artifact(program: IRProgram) -> bytes:
    validate_program(program)
    return encode_canonical_cbor(
        {
            "format": STREAM_IR_FORMAT,
            "ir_version": program.ir_version,
            "behaviour_revision": program.behaviour_revision,
            "source_kind": program.source_kind,
            "private_defaults": _ir_value_to_obj(dict(program.private_defaults)),
            "handlers": [
                {
                    "handler_id": handler.handler_id,
                    "trigger": handler.trigger,
                    "instructions": [_instruction_to_obj(row) for row in handler.instructions],
                }
                for handler in program.handlers
            ],
            "procedures": [
                {
                    "name": name,
                    "instructions": [_instruction_to_obj(row) for row in program.procedures[name]],
                }
                for name in sorted(program.procedures)
            ],
        }
    )


def decode_ir_artifact(payload: bytes) -> IRProgram:
    try:
        value = decode_canonical_cbor(payload)
    except Exception as exc:
        code = getattr(exc, "code", "invalid_ir_artifact")
        raise StreamingError(
            "streaming.incompatible_dependency",
            f"Behaviour artifact failed bounded decoding ({code})",
            cause=exc,
        ) from exc
    expected = {
        "format", "ir_version", "behaviour_revision", "source_kind",
        "private_defaults", "handlers", "procedures",
    }
    if not isinstance(value, dict) or set(value) != expected:
        _fail("streaming.incompatible_dependency", "Behaviour artifact envelope is malformed")
    if value["format"] != STREAM_IR_FORMAT:
        _fail("streaming.incompatible_dependency", "Behaviour artifact profile is unsupported")
    if not isinstance(value["handlers"], list) or not isinstance(value["procedures"], list):
        _fail("streaming.incompatible_dependency", "Behaviour handler/procedure tables must be lists")
    handlers: list[IRHandler] = []
    for row in value["handlers"]:
        if not isinstance(row, dict) or set(row) != {"handler_id", "trigger", "instructions"}:
            _fail("streaming.incompatible_dependency", "Behaviour handler envelope is malformed")
        if not isinstance(row["instructions"], list):
            _fail("streaming.incompatible_dependency", "Behaviour handler instructions must be a list")
        handlers.append(
            IRHandler(
                row["handler_id"], row["trigger"],
                tuple(_instruction_from_obj(item) for item in row["instructions"]),
            )
        )
    procedures: dict[str, tuple[IRInstruction, ...]] = {}
    for row in value["procedures"]:
        if not isinstance(row, dict) or set(row) != {"name", "instructions"}:
            _fail("streaming.incompatible_dependency", "Behaviour procedure envelope is malformed")
        name = row["name"]
        if not isinstance(name, str) or not name or name in procedures or not isinstance(row["instructions"], list):
            _fail("streaming.incompatible_dependency", "Behaviour procedure identity/table is invalid")
        procedures[name] = tuple(_instruction_from_obj(item) for item in row["instructions"])
    try:
        program = IRProgram(
            value["behaviour_revision"], tuple(handlers), procedures,
            _ir_value_from_obj(value["private_defaults"]), value["ir_version"], value["source_kind"],
        )
        validate_program(program)
    except Exception as exc:
        code = getattr(exc, "code", "invalid_ir")
        raise StreamingError(
            "streaming.incompatible_dependency",
            f"Behaviour artifact validation/migration failed ({code})",
            cause=exc,
        ) from exc
    return program


class StreamingRuntime:
    """Transactional logical-residency coordinator over a WorldRuntime."""

    def __init__(
        self,
        world: WorldRuntime,
        *,
        protected_assets: Mapping[AssetId, ProtectedAssetRevision] | None = None,
        catalog: Mapping[ThingId, ThingStreamSpec],
        descriptors: Mapping[str, ExactArtifactDescriptor],
        fetcher: ArtifactFetcher,
        cache: ImmutableArtifactCache | None = None,
        limits: AcquisitionLimits | None = None,
        supported_features: Sequence[str] = (),
    ):
        if not isinstance(world, WorldRuntime):
            _fail("streaming.invalid_runtime", "StreamingRuntime requires WorldRuntime")
        self.world = world
        self.protected_assets = dict(protected_assets or {})
        self.catalog = dict(catalog)
        for thing_id, spec in self.catalog.items():
            if thing_id != spec.thing_id:
                _fail("streaming.invalid_catalog", "catalog key does not match ThingStreamSpec ThingId")
        self.cache = cache or ImmutableArtifactCache()
        self.acquirer = ExactAcquirer(
            descriptors, fetcher, self.cache, limits=limits, supported_features=supported_features
        )

    def reference_state(self, thing_id: ThingId) -> ReferenceState:
        return self.world.reference_state(thing_id)

    def stream_out(self, thing_ids: Sequence[ThingId]) -> StreamOutcome:
        requested = _unique_things(thing_ids)
        staged = deepcopy(self.world)
        changed: list[ThingId] = []
        for thing_id in requested:
            state = staged.reference_state(thing_id)
            if state is ReferenceState.UNKNOWN:
                _fail("streaming.unknown_thing", f"cannot unload unknown Thing {thing_id}")
            if state is ReferenceState.TOMBSTONED:
                _fail("streaming.tombstoned", f"cannot unload tombstoned Thing {thing_id}")
            if state is ReferenceState.KNOWN_UNLOADED:
                continue
            if thing_id not in self.catalog:
                _fail("streaming.catalog_missing", f"cannot unload {thing_id} without an exact reload catalog")
            try:
                staged.unload(thing_id)
            except LifecycleError as exc:
                raise StreamingError("streaming.unload_failed", str(exc), cause=exc) from exc
            changed.append(thing_id)
        self._publish_world(staged)
        return StreamOutcome(tuple(changed), (), ())

    def stream_in(
        self,
        thing_ids: Sequence[ThingId],
        *,
        capability_broker: CapabilityBroker | None = None,
        capability_requirements: Mapping[
            tuple[ThingId, BehaviourAttachmentId], Sequence[CapabilityRequirement]
        ] | None = None,
        policy_time: int = 0,
        cancel_check: CancelCheck | None = None,
    ) -> StreamOutcome:
        requested = _unique_things(thing_ids)
        targets: list[ThingId] = []
        roots: list[str] = []
        for thing_id in requested:
            state = self.world.reference_state(thing_id)
            if state is ReferenceState.UNKNOWN:
                _fail("streaming.unknown_thing", f"cannot acquire unknown Thing {thing_id}")
            if state is ReferenceState.TOMBSTONED:
                _fail("streaming.tombstoned", f"tombstoned Thing {thing_id} cannot be resurrected")
            if state is ReferenceState.LOADED:
                continue
            spec = self.catalog.get(thing_id)
            if spec is None:
                _fail("streaming.catalog_missing", f"no exact stream catalog entry for {thing_id}")
            targets.append(thing_id)
            roots.extend(spec.root_artifact_ids)
        if not targets:
            return StreamOutcome((), (), ())

        acquisition = self.acquirer.acquire(tuple(dict.fromkeys(roots)), cancel_check=cancel_check)
        staged_registry = dict(self.world.program_registry)
        staged_assets = deepcopy(self.protected_assets)
        decoded_projects: dict[str, CanonicalProjectRevision] = {}
        acquired_program_revisions: set[str] = set()

        for artifact_id in acquisition.ordered_artifact_ids:
            descriptor = self.acquirer.descriptors[artifact_id]
            payload = acquisition.payloads[artifact_id]
            if descriptor.kind is ArtifactKind.CANONICAL_SUBGRAPH:
                project = decode_project_artifact(payload)
                self._validate_project_artifact(project, staged_assets)
                decoded_projects[artifact_id] = project
                for asset_id, asset in project.assets.items():
                    staged_assets.setdefault(asset_id, deepcopy(asset))
            elif descriptor.kind is ArtifactKind.BEHAVIOUR_IR:
                program = decode_ir_artifact(payload)
                acquired_program_revisions.add(program.behaviour_revision)
                prior = staged_registry.get(program.behaviour_revision)
                if prior is not None and prior != program:
                    _fail(
                        "streaming.incompatible_dependency",
                        f"Behaviour revision {program.behaviour_revision!r} conflicts with resident exact artifact",
                    )
                staged_registry[program.behaviour_revision] = program
            elif descriptor.kind is ArtifactKind.OPAQUE_EXACT:
                pass
            else:
                _fail("streaming.incompatible_dependency", f"unsupported artifact kind {descriptor.kind!r}")

        for thing_id in targets:
            spec = self.catalog[thing_id]
            closure = set(self.acquirer._closure(spec.root_artifact_ids))
            basis_candidates = [
                project for artifact_id, project in decoded_projects.items() if artifact_id in closure
            ]
            self._validate_thing_basis(thing_id, basis_candidates)
            authored = self.world.document.things.get(thing_id)
            if authored is None or authored.tombstoned:
                _fail("streaming.semantic_basis_unavailable", f"Thing {thing_id} has no live authored semantic basis")
            for attachment in authored.behaviours.values():
                if attachment.behaviour_revision not in acquired_program_revisions:
                    _fail(
                        "streaming.exact_behaviour_missing",
                        f"catalog closure for {thing_id} did not acquire exact Behaviour "
                        f"{attachment.behaviour_revision!r}",
                    )

        staged = deepcopy(self.world)
        staged.program_registry = staged_registry
        try:
            for thing_id in targets:
                staged.rehydrate(
                    thing_id,
                    capability_broker=capability_broker,
                    capability_requirements=capability_requirements,
                    policy_time=policy_time,
                )
        except LifecycleError as exc:
            raise StreamingError(
                "streaming.activation_failed", f"staged rehydration failed ({exc.code})", cause=exc
            ) from exc

        if cancel_check is not None and cancel_check():
            _fail("streaming.cancelled", "stream-in was cancelled before publication")

        self._publish_world(staged)
        self.protected_assets = staged_assets
        return StreamOutcome(tuple(targets), acquisition.ordered_artifact_ids, acquisition.cache_hits)

    def evict_artifact(self, artifact_id: str) -> bool:
        descriptor = self.acquirer.descriptors.get(artifact_id)
        if descriptor is None:
            _fail("streaming.descriptor_missing", f"no exact descriptor for {artifact_id!r}")
        return self.cache.evict(descriptor)

    def _validate_project_artifact(
        self,
        project: CanonicalProjectRevision,
        staged_assets: Mapping[AssetId, ProtectedAssetRevision],
    ) -> None:
        if project.document.project_id != self.world.document.project_id:
            _fail("streaming.incompatible_dependency", "canonical artifact belongs to another ProjectId")
        if project.document.project_revision_id != self.world.document.project_revision_id:
            _fail(
                "streaming.incompatible_dependency",
                "canonical artifact belongs to another exact ProjectRevisionId",
            )
        for definition_id, definition in project.document.definitions.items():
            current = self.world.document.definitions.get(definition_id)
            if current is not None and current != definition:
                _fail(
                    "streaming.incompatible_dependency",
                    f"Definition {definition_id} differs from exact authored basis",
                )
        for asset_id, asset in project.assets.items():
            current = staged_assets.get(asset_id)
            if current is not None and current != asset:
                _fail(
                    "streaming.protected_asset_conflict",
                    f"protected AssetId {asset_id} names a different complete revision",
                )

    def _validate_thing_basis(
        self, thing_id: ThingId, candidates: Sequence[CanonicalProjectRevision]
    ) -> None:
        authored = self.world.document.things.get(thing_id)
        if authored is None:
            _fail("streaming.semantic_basis_unavailable", f"no authored Thing record for {thing_id}")
        matches = [
            candidate.document.things[thing_id]
            for candidate in candidates
            if thing_id in candidate.document.things
        ]
        if not matches:
            _fail(
                "streaming.exact_basis_missing",
                f"catalog closure for {thing_id} contains no exact canonical Thing basis",
            )
        if any(record != authored for record in matches):
            _fail(
                "streaming.incompatible_dependency",
                f"canonical Thing basis for {thing_id} differs from authored semantics",
            )

    def _publish_world(self, staged: WorldRuntime) -> None:
        self.world.runtime = staged.runtime
        self.world.program_registry = staged.program_registry
        self.world.lifecycle = staged.lifecycle
        self.world._retained = staged._retained
        self.world.deferred_external_waits = staged.deferred_external_waits


def _unique_things(values: Sequence[ThingId]) -> tuple[ThingId, ...]:
    if not values:
        _fail("streaming.invalid_request", "at least one ThingId is required")
    seen: set[ThingId] = set()
    result: list[ThingId] = []
    for value in values:
        if not isinstance(value, ThingId):
            _fail("streaming.invalid_request", "logical streaming accepts only ThingId values")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
