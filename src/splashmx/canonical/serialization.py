"""SMX-024 production canonical serialization and protected-asset envelope.

Architecture v1 semantics remain authoritative. This module owns only the selected
SMX-022 physical boundary: deterministic CBOR records, stable-ID hash shards,
protected Asset revisions, and a bounded prepare-before-publish migration envelope.
Storage transaction ownership is deliberately left to SMX-025.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import math
import re
import struct
from typing import Any, Callable, Mapping, Sequence

from .core import (
    AssetId,
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ConnectionEndpoint,
    ConnectionId,
    ConnectionRecord,
    DefinitionElementRecord,
    DefinitionExposure,
    DefinitionId,
    DefinitionRecord,
    ElementId,
    InstanceRecord,
    PortDirection,
    PortId,
    PortKind,
    PortRecord,
    ProjectId,
    ProjectRevisionId,
    RelationId,
    RelationshipKind,
    RelationshipRecord,
    ThingId,
    ThingRecord,
    validate_document,
)

CANONICAL_PROFILE = "splashmx.deterministic-cbor/1"
SHARD_PROFILE = "splashmx.stable-id-shard/1"
SHARD_POLICY = "sha256-prefix/1"
CURRENT_SCHEMA_VERSION = 1
DEFAULT_TARGET_SHARD_BYTES = 32 * 1024
KNOWN_REQUIRED_FEATURES = frozenset({"protected-assets-v1", "stable-id-shards-v1"})

_FORBIDDEN_DURABLE_FIELD_NAMES = {
    "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
    "databaserowid", "cachekey", "transportpeerid", "connectionhandle",
    "socketid", "sessionid", "processhandle", "capabilitytoken", "capabilitygrant",
}
_DIGEST_RE = re.compile(r"^[a-z0-9._-]+:[A-Za-z0-9_-]{16,}$")


class SerializationError(ValueError):
    """Typed canonical-serialization failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DecodeLimits:
    max_bytes: int = 64 * 1024 * 1024
    max_depth: int = 64
    max_items: int = 200_000
    max_string_bytes: int = 8 * 1024 * 1024


DEFAULT_LIMITS = DecodeLimits()


def _normalise_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _raise(code: str, message: str) -> None:
    raise SerializationError(code, message)


def _ensure_plain(value: Any, where: str = "value", depth: int = 0) -> Any:
    if depth > DEFAULT_LIMITS.max_depth:
        _raise("serialization.limit_exceeded", f"{where} exceeds maximum nesting depth")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value < -(1 << 63) or value > (1 << 64) - 1:
            _raise("serialization.integer_out_of_range", f"{where} integer is outside the v1 CBOR range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _raise("serialization.non_finite_float", f"{where} contains NaN or infinity")
        return value
    if isinstance(value, bytes):
        if len(value) > DEFAULT_LIMITS.max_string_bytes:
            _raise("serialization.limit_exceeded", f"{where} byte string exceeds limit")
        return value
    if isinstance(value, list):
        return [_ensure_plain(item, f"{where}[{index}]", depth + 1) for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _raise("serialization.invalid_map_key", f"{where} map keys must be strings")
            normalised = _normalise_field_name(key)
            if normalised in _FORBIDDEN_DURABLE_FIELD_NAMES:
                _raise("serialization.forbidden_transient_identity", f"{where} contains forbidden durable field {key!r}")
            if key in result:
                _raise("serialization.duplicate_map_key", f"{where} duplicates key {key!r}")
            result[key] = _ensure_plain(item, f"{where}.{key}", depth + 1)
        return result
    _raise("serialization.unsupported_value", f"{where} uses unsupported durable value type {type(value).__name__}")


def _head(major: int, argument: int) -> bytes:
    if argument < 0:
        _raise("serialization.cbor_internal", "negative CBOR argument")
    prefix = major << 5
    if argument < 24:
        return bytes((prefix | argument,))
    if argument <= 0xFF:
        return bytes((prefix | 24, argument))
    if argument <= 0xFFFF:
        return bytes((prefix | 25,)) + struct.pack(">H", argument)
    if argument <= 0xFFFFFFFF:
        return bytes((prefix | 26,)) + struct.pack(">I", argument)
    if argument <= 0xFFFFFFFFFFFFFFFF:
        return bytes((prefix | 27,)) + struct.pack(">Q", argument)
    _raise("serialization.integer_out_of_range", "CBOR argument exceeds uint64")


def _float_same(left: float, right: float) -> bool:
    if left != right:
        return False
    if left == 0.0:
        return math.copysign(1.0, left) == math.copysign(1.0, right)
    return True


def encode_canonical_cbor(value: Any) -> bytes:
    """Encode the SplashMX v1 deterministic-CBOR subset."""
    value = _ensure_plain(value)

    def enc(item: Any) -> bytes:
        if item is None:
            return b"\xf6"
        if item is False:
            return b"\xf4"
        if item is True:
            return b"\xf5"
        if isinstance(item, int):
            return _head(0, item) if item >= 0 else _head(1, -1 - item)
        if isinstance(item, bytes):
            return _head(2, len(item)) + item
        if isinstance(item, str):
            data = item.encode("utf-8", errors="strict")
            return _head(3, len(data)) + data
        if isinstance(item, float):
            for marker, fmt in ((b"\xf9", ">e"), (b"\xfa", ">f")):
                try:
                    packed = struct.pack(fmt, item)
                    decoded = struct.unpack(fmt, packed)[0]
                except (OverflowError, struct.error):
                    continue
                if _float_same(decoded, item):
                    return marker + packed
            return b"\xfb" + struct.pack(">d", item)
        if isinstance(item, list):
            return _head(4, len(item)) + b"".join(enc(child) for child in item)
        if isinstance(item, dict):
            encoded_items = []
            for key, child in item.items():
                key_bytes = enc(key)
                encoded_items.append((len(key_bytes), key_bytes, enc(child)))
            encoded_items.sort(key=lambda row: (row[0], row[1]))
            return _head(5, len(encoded_items)) + b"".join(key + child for _, key, child in encoded_items)
        _raise("serialization.cbor_internal", f"unexpected CBOR value {type(item).__name__}")

    return enc(value)


class _CborReader:
    def __init__(self, data: bytes, limits: DecodeLimits):
        if not isinstance(data, (bytes, bytearray)):
            _raise("serialization.invalid_cbor", "canonical CBOR input must be bytes")
        if len(data) > limits.max_bytes:
            _raise("serialization.limit_exceeded", "CBOR input exceeds maximum byte length")
        self.data = bytes(data)
        self.pos = 0
        self.limits = limits
        self.items = 0

    def _take(self, count: int) -> bytes:
        end = self.pos + count
        if end > len(self.data):
            _raise("serialization.truncated_cbor", "truncated CBOR input")
        result = self.data[self.pos:end]
        self.pos = end
        return result

    def _argument(self, additional: int) -> int:
        if additional < 24:
            return additional
        if additional == 24:
            return self._take(1)[0]
        if additional == 25:
            return struct.unpack(">H", self._take(2))[0]
        if additional == 26:
            return struct.unpack(">I", self._take(4))[0]
        if additional == 27:
            return struct.unpack(">Q", self._take(8))[0]
        if additional == 31:
            _raise("serialization.indefinite_cbor", "indefinite-length CBOR is not in the v1 profile")
        _raise("serialization.invalid_cbor", f"unsupported CBOR additional info {additional}")

    def read(self, depth: int = 0) -> Any:
        if depth > self.limits.max_depth:
            _raise("serialization.limit_exceeded", "CBOR nesting depth exceeds limit")
        self.items += 1
        if self.items > self.limits.max_items:
            _raise("serialization.limit_exceeded", "CBOR item count exceeds limit")
        initial = self._take(1)[0]
        major, additional = initial >> 5, initial & 31
        if major in (0, 1):
            argument = self._argument(additional)
            return argument if major == 0 else -1 - argument
        if major in (2, 3):
            length = self._argument(additional)
            if length > self.limits.max_string_bytes:
                _raise("serialization.limit_exceeded", "CBOR string exceeds configured limit")
            payload = self._take(length)
            if major == 2:
                return payload
            try:
                return payload.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SerializationError("serialization.invalid_utf8", "CBOR text is not strict UTF-8") from exc
        if major == 4:
            length = self._argument(additional)
            if length > self.limits.max_items:
                _raise("serialization.limit_exceeded", "CBOR array exceeds item limit")
            return [self.read(depth + 1) for _ in range(length)]
        if major == 5:
            length = self._argument(additional)
            if length > self.limits.max_items:
                _raise("serialization.limit_exceeded", "CBOR map exceeds item limit")
            result: dict[str, Any] = {}
            for _ in range(length):
                key = self.read(depth + 1)
                if not isinstance(key, str):
                    _raise("serialization.invalid_map_key", "v1 canonical CBOR map keys must be strings")
                if key in result:
                    _raise("serialization.duplicate_map_key", f"duplicate CBOR map key {key!r}")
                result[key] = self.read(depth + 1)
            return result
        if major == 6:
            _raise("serialization.unregistered_tag", "CBOR tags are not registered in profile v1")
        if major == 7:
            if additional == 20:
                return False
            if additional == 21:
                return True
            if additional == 22:
                return None
            if additional == 25:
                value = struct.unpack(">e", self._take(2))[0]
            elif additional == 26:
                value = struct.unpack(">f", self._take(4))[0]
            elif additional == 27:
                value = struct.unpack(">d", self._take(8))[0]
            else:
                _raise("serialization.invalid_cbor", f"unsupported simple/float value {additional}")
            if not math.isfinite(value):
                _raise("serialization.non_finite_float", "NaN and infinities are forbidden")
            return value
        _raise("serialization.invalid_cbor", f"unsupported CBOR major type {major}")


def decode_canonical_cbor(data: bytes, *, limits: DecodeLimits = DEFAULT_LIMITS) -> Any:
    """Decode and require byte-for-byte canonical v1 representation."""
    reader = _CborReader(data, limits)
    result = reader.read()
    if reader.pos != len(reader.data):
        _raise("serialization.trailing_cbor", "canonical CBOR has trailing bytes")
    if encode_canonical_cbor(result) != bytes(data):
        _raise("serialization.noncanonical_cbor", "CBOR bytes are valid but not canonical for profile v1")
    return result


@dataclass(frozen=True)
class ProtectedAssetRevision:
    """One indivisible protected Asset revision selected by a stable AssetId."""

    asset_id: AssetId
    revision_digest: str
    source_digest: str
    source_identity: Mapping[str, Any]
    source_metadata: Mapping[str, Any]
    media_semantics: Mapping[str, Any]
    provenance: Mapping[str, Any]
    licence_attribution: Mapping[str, Any]
    derivation_lineage: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_asset_revision(self)

    @classmethod
    def create(
        cls,
        asset_id: AssetId,
        *,
        source_digest: str,
        source_identity: Mapping[str, Any],
        source_metadata: Mapping[str, Any],
        media_semantics: Mapping[str, Any],
        provenance: Mapping[str, Any],
        licence_attribution: Mapping[str, Any],
        derivation_lineage: Sequence[Mapping[str, Any]] = (),
    ) -> "ProtectedAssetRevision":
        payload = _asset_payload(
            asset_id, source_digest, source_identity, source_metadata, media_semantics,
            provenance, licence_attribution, derivation_lineage,
        )
        revision_digest = "sha256:" + sha256(encode_canonical_cbor(payload)).hexdigest()
        return cls(
            asset_id, revision_digest, source_digest, dict(source_identity),
            dict(source_metadata), dict(media_semantics), dict(provenance),
            dict(licence_attribution), tuple(dict(row) for row in derivation_lineage),
        )


@dataclass(frozen=True)
class CanonicalProjectRevision:
    document: CanonicalDocument
    assets: Mapping[AssetId, ProtectedAssetRevision] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_project_revision(self)


@dataclass(frozen=True)
class SerializedProjectRevision:
    root_manifest: bytes
    shards: Mapping[str, bytes]


MigrationFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


class MigrationRegistry:
    """Bounded, capability-free physical-schema migration registry."""

    def __init__(self, max_steps: int = 8):
        self.max_steps = max_steps
        self._steps: dict[int, tuple[int, MigrationFn]] = {}

    def register(self, source_version: int, target_version: int, fn: MigrationFn) -> None:
        if source_version < 0 or target_version <= source_version:
            _raise("serialization.invalid_migration", "migration versions must advance")
        if source_version in self._steps:
            _raise("serialization.invalid_migration", f"duplicate migration source {source_version}")
        self._steps[source_version] = (target_version, fn)

    def migrate(self, version: int, records: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
        current = version
        candidate = [_clone_plain(row) for row in records]
        steps = 0
        while current < CURRENT_SCHEMA_VERSION:
            if steps >= self.max_steps:
                _raise("serialization.migration_limit", "migration path exceeds configured step bound")
            step = self._steps.get(current)
            if step is None:
                _raise("serialization.unsupported_version", f"no migration from schema version {current}")
            target, fn = step
            before = [_clone_plain(row) for row in candidate]
            try:
                candidate = fn(before)
            except SerializationError:
                raise
            except Exception as exc:
                raise SerializationError("serialization.migration_failed", f"migration {current}->{target} failed") from exc
            if not isinstance(candidate, list):
                _raise("serialization.migration_failed", "migration must return a record list")
            candidate = [_ensure_record_plain(row) for row in candidate]
            current = target
            steps += 1
        if current != CURRENT_SCHEMA_VERSION:
            _raise("serialization.unsupported_version", f"migration ended at unsupported version {current}")
        return current, candidate


def _v0_to_v1(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # v0 is the accepted old-version fixture profile: semantic records are unchanged;
    # only the physical envelope version advances. This demonstrates bounded migration
    # without inventing a semantic rewrite.
    return [_clone_plain(row) for row in records]


DEFAULT_MIGRATIONS = MigrationRegistry()
DEFAULT_MIGRATIONS.register(0, 1, _v0_to_v1)


def _clone_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_plain(item) for item in value]
    if isinstance(value, bytes):
        return bytes(value)
    return value


def _ensure_record_plain(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        _raise("serialization.invalid_record", "migration produced a non-map record")
    return _ensure_plain(record, "migrated record")


def _expect_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise("serialization.invalid_record", f"{where} must be a map")
    actual = set(value)
    if actual != keys:
        _raise("serialization.invalid_record", f"{where} keys differ: expected {sorted(keys)}, got {sorted(actual)}")
    return value


def _asset_payload(
    asset_id: AssetId,
    source_digest: str,
    source_identity: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
    media_semantics: Mapping[str, Any],
    provenance: Mapping[str, Any],
    licence_attribution: Mapping[str, Any],
    derivation_lineage: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(asset_id, AssetId):
        _raise("serialization.invalid_asset", "protected asset identity must be AssetId")
    if not isinstance(source_digest, str) or _DIGEST_RE.fullmatch(source_digest) is None:
        _raise("serialization.invalid_asset", "source digest must be an algorithm-prefixed immutable digest")
    return {
        "asset_id": str(asset_id),
        "source_digest": source_digest,
        "source_identity": _ensure_plain(dict(source_identity), "asset.source_identity"),
        "source_metadata": _ensure_plain(dict(source_metadata), "asset.source_metadata"),
        "media_semantics": _ensure_plain(dict(media_semantics), "asset.media_semantics"),
        "provenance": _ensure_plain(dict(provenance), "asset.provenance"),
        "licence_attribution": _ensure_plain(dict(licence_attribution), "asset.licence_attribution"),
        "derivation_lineage": [_ensure_plain(dict(row), "asset.derivation_lineage") for row in derivation_lineage],
    }


def _validate_asset_revision(asset: ProtectedAssetRevision) -> None:
    payload = _asset_payload(
        asset.asset_id, asset.source_digest, asset.source_identity, asset.source_metadata,
        asset.media_semantics, asset.provenance, asset.licence_attribution, asset.derivation_lineage,
    )
    expected = "sha256:" + sha256(encode_canonical_cbor(payload)).hexdigest()
    if asset.revision_digest != expected:
        _raise(
            "serialization.asset_revision_mismatch",
            "protected Asset fields do not match the indivisible revision digest",
        )


def validate_project_revision(project: CanonicalProjectRevision) -> None:
    validate_document(project.document)
    seen: set[AssetId] = set()
    for asset_id, asset in project.assets.items():
        if not isinstance(asset_id, AssetId) or asset_id != asset.asset_id:
            _raise("serialization.asset_identity_mismatch", "Asset map key does not match protected AssetId")
        if asset_id in seen:
            _raise("serialization.duplicate_asset", f"duplicate AssetId {asset_id}")
        seen.add(asset_id)
        _validate_asset_revision(asset)


def _port_to_obj(record: PortRecord) -> dict[str, Any]:
    return {"id": str(record.port_id), "name": record.name, "kind": record.kind.value, "direction": record.direction.value}


def _port_from_obj(value: Any) -> PortRecord:
    row = _expect_keys(value, {"id", "name", "kind", "direction"}, "PortRecord")
    return PortRecord(PortId(row["id"]), row["name"], PortKind(row["kind"]), PortDirection(row["direction"]))


def _behaviour_to_obj(record: BehaviourAttachmentRecord) -> dict[str, Any]:
    return {
        "id": str(record.attachment_id),
        "behaviour_revision": record.behaviour_revision,
        "authored_config": _ensure_plain(dict(record.authored_config), "behaviour.authored_config"),
    }


def _behaviour_from_obj(value: Any) -> BehaviourAttachmentRecord:
    row = _expect_keys(value, {"id", "behaviour_revision", "authored_config"}, "BehaviourAttachmentRecord")
    return BehaviourAttachmentRecord(
        BehaviourAttachmentId(row["id"]), row["behaviour_revision"],
        _ensure_plain(row["authored_config"], "behaviour.authored_config"),
    )


def _thing_to_obj(record: ThingRecord) -> dict[str, Any]:
    return {
        "thing_id": str(record.thing_id),
        "label": record.label,
        "authored_state": _ensure_plain(dict(record.authored_state), "thing.authored_state"),
        "ports": [_port_to_obj(record.ports[key]) for key in sorted(record.ports, key=str)],
        "behaviours": [_behaviour_to_obj(record.behaviours[key]) for key in sorted(record.behaviours, key=str)],
        "tombstoned": record.tombstoned,
    }


def _thing_from_obj(value: Any) -> ThingRecord:
    row = _expect_keys(value, {"thing_id", "label", "authored_state", "ports", "behaviours", "tombstoned"}, "ThingRecord")
    ports = [_port_from_obj(item) for item in row["ports"]]
    behaviours = [_behaviour_from_obj(item) for item in row["behaviours"]]
    return ThingRecord(
        ThingId(row["thing_id"]), row["label"], _ensure_plain(row["authored_state"], "thing.authored_state"),
        _unique_map(ports, lambda item: item.port_id, "PortId"),
        _unique_map(behaviours, lambda item: item.attachment_id, "BehaviourAttachmentId"),
        bool(row["tombstoned"]),
    )


def _relationship_to_obj(record: RelationshipRecord) -> dict[str, Any]:
    return {
        "relation_id": str(record.relation_id), "kind": record.kind.value,
        "source": str(record.source), "target": str(record.target), "tombstoned": record.tombstoned,
    }


def _relationship_from_obj(value: Any) -> RelationshipRecord:
    row = _expect_keys(value, {"relation_id", "kind", "source", "target", "tombstoned"}, "RelationshipRecord")
    return RelationshipRecord(
        RelationId(row["relation_id"]), RelationshipKind(row["kind"]),
        ThingId(row["source"]), ThingId(row["target"]), bool(row["tombstoned"]),
    )


def _endpoint_to_obj(value: ConnectionEndpoint) -> dict[str, Any]:
    return {"thing_id": str(value.thing_id), "port_id": str(value.port_id)}


def _endpoint_from_obj(value: Any) -> ConnectionEndpoint:
    row = _expect_keys(value, {"thing_id", "port_id"}, "ConnectionEndpoint")
    return ConnectionEndpoint(ThingId(row["thing_id"]), PortId(row["port_id"]))


def _connection_to_obj(record: ConnectionRecord) -> dict[str, Any]:
    return {
        "connection_id": str(record.connection_id), "source": _endpoint_to_obj(record.source),
        "target": _endpoint_to_obj(record.target), "tombstoned": record.tombstoned,
    }


def _connection_from_obj(value: Any) -> ConnectionRecord:
    row = _expect_keys(value, {"connection_id", "source", "target", "tombstoned"}, "ConnectionRecord")
    return ConnectionRecord(
        ConnectionId(row["connection_id"]), _endpoint_from_obj(row["source"]),
        _endpoint_from_obj(row["target"]), bool(row["tombstoned"]),
    )


def _element_to_obj(record: DefinitionElementRecord) -> dict[str, Any]:
    return {
        "element_id": str(record.element_id), "label": record.label,
        "authored_state": _ensure_plain(dict(record.authored_state), "definition.authored_state"),
        "ports": [_port_to_obj(record.ports[key]) for key in sorted(record.ports, key=str)],
        "parent_element_id": None if record.parent_element_id is None else str(record.parent_element_id),
    }


def _element_from_obj(value: Any) -> DefinitionElementRecord:
    row = _expect_keys(value, {"element_id", "label", "authored_state", "ports", "parent_element_id"}, "DefinitionElementRecord")
    ports = [_port_from_obj(item) for item in row["ports"]]
    return DefinitionElementRecord(
        ElementId(row["element_id"]), row["label"], _ensure_plain(row["authored_state"], "definition.authored_state"),
        _unique_map(ports, lambda item: item.port_id, "definition PortId"),
        None if row["parent_element_id"] is None else ElementId(row["parent_element_id"]),
    )


def _exposure_to_obj(record: DefinitionExposure) -> dict[str, Any]:
    return {
        "public_port_id": str(record.public_port_id),
        "element_id": str(record.element_id),
        "element_port_id": str(record.element_port_id),
    }


def _exposure_from_obj(value: Any) -> DefinitionExposure:
    row = _expect_keys(value, {"public_port_id", "element_id", "element_port_id"}, "DefinitionExposure")
    return DefinitionExposure(PortId(row["public_port_id"]), ElementId(row["element_id"]), PortId(row["element_port_id"]))


def _definition_to_obj(record: DefinitionRecord) -> dict[str, Any]:
    return {
        "definition_id": str(record.definition_id), "revision": record.revision,
        "root_element_id": str(record.root_element_id),
        "elements": [_element_to_obj(record.elements[key]) for key in sorted(record.elements, key=str)],
        "exposures": [_exposure_to_obj(record.exposures[key]) for key in sorted(record.exposures, key=str)],
    }


def _definition_from_obj(value: Any) -> DefinitionRecord:
    row = _expect_keys(value, {"definition_id", "revision", "root_element_id", "elements", "exposures"}, "DefinitionRecord")
    elements = [_element_from_obj(item) for item in row["elements"]]
    exposures = [_exposure_from_obj(item) for item in row["exposures"]]
    return DefinitionRecord(
        DefinitionId(row["definition_id"]), int(row["revision"]), ElementId(row["root_element_id"]),
        _unique_map(elements, lambda item: item.element_id, "ElementId"),
        _unique_map(exposures, lambda item: item.public_port_id, "public PortId"),
    )


def _instance_to_obj(record: InstanceRecord) -> dict[str, Any]:
    return {
        "root_thing_id": str(record.root_thing_id), "definition_id": str(record.definition_id),
        "base_revision": record.base_revision,
        "thing_by_element": [
            {"element_id": str(key), "thing_id": str(record.thing_by_element[key])}
            for key in sorted(record.thing_by_element, key=str)
        ],
        "state_overrides": [
            {"element_id": str(key), "values": _ensure_plain(dict(record.state_overrides[key]), "instance.state_overrides")}
            for key in sorted(record.state_overrides, key=str)
        ],
        "parent_overrides": [
            {"element_id": str(key), "parent_element_id": None if record.parent_overrides[key] is None else str(record.parent_overrides[key])}
            for key in sorted(record.parent_overrides, key=str)
        ],
        "local_thing_ids": [str(key) for key in sorted(record.local_thing_ids, key=str)],
    }


def _instance_from_obj(value: Any) -> InstanceRecord:
    row = _expect_keys(
        value,
        {"root_thing_id", "definition_id", "base_revision", "thing_by_element", "state_overrides", "parent_overrides", "local_thing_ids"},
        "InstanceRecord",
    )
    mapping: dict[ElementId, ThingId] = {}
    for item in row["thing_by_element"]:
        pair = _expect_keys(item, {"element_id", "thing_id"}, "instance element mapping")
        element = ElementId(pair["element_id"])
        if element in mapping:
            _raise("serialization.duplicate_identity", f"duplicate instance ElementId {element}")
        mapping[element] = ThingId(pair["thing_id"])
    state_overrides: dict[ElementId, Mapping[str, Any]] = {}
    for item in row["state_overrides"]:
        pair = _expect_keys(item, {"element_id", "values"}, "instance state override")
        element = ElementId(pair["element_id"])
        if element in state_overrides:
            _raise("serialization.duplicate_identity", f"duplicate override ElementId {element}")
        state_overrides[element] = _ensure_plain(pair["values"], "instance.state_overrides")
    parent_overrides: dict[ElementId, ElementId | None] = {}
    for item in row["parent_overrides"]:
        pair = _expect_keys(item, {"element_id", "parent_element_id"}, "instance parent override")
        element = ElementId(pair["element_id"])
        if element in parent_overrides:
            _raise("serialization.duplicate_identity", f"duplicate parent override ElementId {element}")
        parent_overrides[element] = None if pair["parent_element_id"] is None else ElementId(pair["parent_element_id"])
    local = frozenset(ThingId(item) for item in row["local_thing_ids"])
    if len(local) != len(row["local_thing_ids"]):
        _raise("serialization.duplicate_identity", "duplicate local ThingId")
    return InstanceRecord(
        ThingId(row["root_thing_id"]), DefinitionId(row["definition_id"]), int(row["base_revision"]),
        mapping, state_overrides, parent_overrides, local,
    )


def _asset_to_obj(record: ProtectedAssetRevision) -> dict[str, Any]:
    payload = _asset_payload(
        record.asset_id, record.source_digest, record.source_identity, record.source_metadata,
        record.media_semantics, record.provenance, record.licence_attribution, record.derivation_lineage,
    )
    payload["revision_digest"] = record.revision_digest
    return payload


def _asset_from_obj(value: Any) -> ProtectedAssetRevision:
    keys = {
        "asset_id", "revision_digest", "source_digest", "source_identity", "source_metadata",
        "media_semantics", "provenance", "licence_attribution", "derivation_lineage",
    }
    row = _expect_keys(value, keys, "ProtectedAssetRevision")
    return ProtectedAssetRevision(
        AssetId(row["asset_id"]), row["revision_digest"], row["source_digest"],
        _ensure_plain(row["source_identity"], "asset.source_identity"),
        _ensure_plain(row["source_metadata"], "asset.source_metadata"),
        _ensure_plain(row["media_semantics"], "asset.media_semantics"),
        _ensure_plain(row["provenance"], "asset.provenance"),
        _ensure_plain(row["licence_attribution"], "asset.licence_attribution"),
        tuple(_ensure_plain(item, "asset.derivation_lineage") for item in row["derivation_lineage"]),
    )


def _unique_map(items: Sequence[Any], key_fn: Callable[[Any], Any], label: str) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for item in items:
        key = key_fn(item)
        if key in result:
            _raise("serialization.duplicate_identity", f"duplicate {label}: {key}")
        result[key] = item
    return result


def _record(semantic_key: str, record_type: str, value: dict[str, Any]) -> tuple[str, bytes]:
    row = {"semantic_key": semantic_key, "record_type": record_type, "value": value}
    return semantic_key, encode_canonical_cbor(row)


def _project_records(project: CanonicalProjectRevision) -> list[tuple[str, bytes]]:
    validate_project_revision(project)
    document = project.document
    records: list[tuple[str, bytes]] = []
    for key in sorted(document.things, key=str):
        records.append(_record(f"thing:{key}", "thing", _thing_to_obj(document.things[key])))
    for key in sorted(document.relationships, key=str):
        records.append(_record(f"relationship:{key}", "relationship", _relationship_to_obj(document.relationships[key])))
    for key in sorted(document.connections, key=str):
        records.append(_record(f"connection:{key}", "connection", _connection_to_obj(document.connections[key])))
    for key in sorted(document.definitions, key=str):
        records.append(_record(f"definition:{key}", "definition", _definition_to_obj(document.definitions[key])))
    for key in sorted(document.instances, key=str):
        records.append(_record(f"instance:{key}", "instance", _instance_to_obj(document.instances[key])))
    for key in sorted(document.known_unloaded_things, key=str):
        records.append(_record(f"known-unloaded:{key}", "known-unloaded", {"thing_id": str(key)}))
    for key in sorted(project.assets, key=str):
        records.append(_record(f"asset:{key}", "asset", _asset_to_obj(project.assets[key])))
    return records


def _hash_prefix(semantic_key: str, bits: int) -> int:
    if bits == 0:
        return 0
    value = int.from_bytes(sha256(semantic_key.encode("utf-8")).digest(), "big")
    return value >> (256 - bits)


def _partition_records(
    records: list[tuple[str, bytes]], target: int, bits: int = 0, prefix: int = 0,
) -> list[tuple[int, int, list[tuple[str, bytes]]]]:
    total = sum(len(payload) for _, payload in records)
    if not records:
        return []
    if total <= target or len(records) == 1:
        return [(bits, prefix, records)]
    if bits >= 32:
        _raise("serialization.shard_limit", "stable-ID shard split exceeded 32 prefix bits")
    left: list[tuple[str, bytes]] = []
    right: list[tuple[str, bytes]] = []
    next_bits = bits + 1
    for row in records:
        candidate = _hash_prefix(row[0], next_bits)
        (left if candidate == prefix * 2 else right).append(row)
    output: list[tuple[int, int, list[tuple[str, bytes]]]] = []
    if left:
        output.extend(_partition_records(left, target, next_bits, prefix * 2))
    if right:
        output.extend(_partition_records(right, target, next_bits, prefix * 2 + 1))
    return output


def _build_shard(bits: int, prefix: int, records: list[tuple[str, bytes]]) -> bytes:
    payload = bytearray()
    index: list[dict[str, Any]] = []
    for semantic_key, encoded in sorted(records, key=lambda row: row[0]):
        offset = len(payload)
        payload.extend(encoded)
        index.append({
            "semantic_key": semantic_key,
            "offset": offset,
            "length": len(encoded),
            "digest": "sha256:" + sha256(encoded).hexdigest(),
        })
    return encode_canonical_cbor({
        "profile": SHARD_PROFILE,
        "prefix_bits": bits,
        "prefix": prefix,
        "index": index,
        "payload": bytes(payload),
    })


def serialize_project(
    project: CanonicalProjectRevision,
    *,
    target_shard_bytes: int = DEFAULT_TARGET_SHARD_BYTES,
) -> SerializedProjectRevision:
    if target_shard_bytes < 1024 or target_shard_bytes > 1024 * 1024:
        _raise("serialization.invalid_shard_target", "target shard bytes must be within 1 KiB..1 MiB")
    records = _project_records(project)
    shards: dict[str, bytes] = {}
    descriptors: list[dict[str, Any]] = []
    for bits, prefix, rows in _partition_records(records, target_shard_bytes):
        key = f"{bits}:{prefix:x}"
        shard = _build_shard(bits, prefix, rows)
        shards[key] = shard
        descriptors.append({
            "key": key, "prefix_bits": bits, "prefix": prefix,
            "length": len(shard), "digest": "sha256:" + sha256(shard).hexdigest(),
        })
    descriptors.sort(key=lambda row: (row["prefix_bits"], row["prefix"]))
    root = encode_canonical_cbor({
        "format": "splashmx.project-revision",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "project_id": str(project.document.project_id),
        "project_revision_id": str(project.document.project_revision_id),
        "shard_policy": SHARD_POLICY,
        "required_features": sorted(KNOWN_REQUIRED_FEATURES),
        "shards": descriptors,
    })
    return SerializedProjectRevision(root, dict(shards))


def _load_shard(descriptor: dict[str, Any], encoded: bytes) -> list[dict[str, Any]]:
    expected = {"key", "prefix_bits", "prefix", "length", "digest"}
    _expect_keys(descriptor, expected, "shard descriptor")
    if descriptor["length"] != len(encoded):
        _raise("serialization.integrity_failure", f"shard {descriptor['key']} length mismatch")
    digest = "sha256:" + sha256(encoded).hexdigest()
    if descriptor["digest"] != digest:
        _raise("serialization.integrity_failure", f"shard {descriptor['key']} digest mismatch")
    shard = decode_canonical_cbor(encoded)
    row = _expect_keys(shard, {"profile", "prefix_bits", "prefix", "index", "payload"}, "shard")
    if row["profile"] != SHARD_PROFILE:
        _raise("serialization.incompatible_profile", "unsupported shard profile")
    if row["prefix_bits"] != descriptor["prefix_bits"] or row["prefix"] != descriptor["prefix"]:
        _raise("serialization.integrity_failure", "shard prefix disagrees with root manifest")
    if not isinstance(row["payload"], bytes) or not isinstance(row["index"], list):
        _raise("serialization.invalid_shard", "shard payload/index types are invalid")
    payload = row["payload"]
    records: list[dict[str, Any]] = []
    last_key: str | None = None
    expected_offset = 0
    for entry in row["index"]:
        item = _expect_keys(entry, {"semantic_key", "offset", "length", "digest"}, "shard index entry")
        semantic_key = item["semantic_key"]
        if not isinstance(semantic_key, str):
            _raise("serialization.invalid_shard", "semantic key must be text")
        if last_key is not None and semantic_key <= last_key:
            _raise("serialization.noncanonical_shard", "shard index is not strict semantic-key order")
        if item["offset"] != expected_offset or not isinstance(item["length"], int) or item["length"] < 1:
            _raise("serialization.invalid_shard", "shard byte ranges are non-contiguous or invalid")
        end = expected_offset + item["length"]
        if end > len(payload):
            _raise("serialization.invalid_shard", "shard index points beyond payload")
        record_bytes = payload[expected_offset:end]
        if item["digest"] != "sha256:" + sha256(record_bytes).hexdigest():
            _raise("serialization.integrity_failure", f"record {semantic_key} digest mismatch")
        record = decode_canonical_cbor(record_bytes)
        envelope = _expect_keys(record, {"semantic_key", "record_type", "value"}, "semantic record")
        if envelope["semantic_key"] != semantic_key:
            _raise("serialization.identity_mismatch", "shard index semantic key disagrees with record")
        if _hash_prefix(semantic_key, int(row["prefix_bits"])) != int(row["prefix"]):
            _raise("serialization.invalid_shard", "record is placed in the wrong stable-ID shard")
        records.append(envelope)
        last_key = semantic_key
        expected_offset = end
    if expected_offset != len(payload):
        _raise("serialization.invalid_shard", "shard payload contains unindexed bytes")
    return records


def _materialize(
    project_id: str, project_revision_id: str, records: list[dict[str, Any]],
) -> CanonicalProjectRevision:
    document = CanonicalDocument(ProjectId(project_id), ProjectRevisionId(project_revision_id))
    assets: dict[AssetId, ProtectedAssetRevision] = {}
    seen_keys: set[str] = set()
    for envelope in records:
        envelope = _expect_keys(envelope, {"semantic_key", "record_type", "value"}, "semantic record")
        semantic_key = envelope["semantic_key"]
        if not isinstance(semantic_key, str) or semantic_key in seen_keys:
            _raise("serialization.duplicate_identity", f"duplicate or invalid semantic record key {semantic_key!r}")
        seen_keys.add(semantic_key)
        record_type, value = envelope["record_type"], envelope["value"]
        if record_type == "thing":
            obj = _thing_from_obj(value)
            expected = f"thing:{obj.thing_id}"
            _insert_unique(document.things, obj.thing_id, obj, "ThingId")
        elif record_type == "relationship":
            obj = _relationship_from_obj(value)
            expected = f"relationship:{obj.relation_id}"
            _insert_unique(document.relationships, obj.relation_id, obj, "RelationId")
        elif record_type == "connection":
            obj = _connection_from_obj(value)
            expected = f"connection:{obj.connection_id}"
            _insert_unique(document.connections, obj.connection_id, obj, "ConnectionId")
        elif record_type == "definition":
            obj = _definition_from_obj(value)
            expected = f"definition:{obj.definition_id}"
            _insert_unique(document.definitions, obj.definition_id, obj, "DefinitionId")
        elif record_type == "instance":
            obj = _instance_from_obj(value)
            expected = f"instance:{obj.root_thing_id}"
            _insert_unique(document.instances, obj.root_thing_id, obj, "instance root")
        elif record_type == "known-unloaded":
            row = _expect_keys(value, {"thing_id"}, "known-unloaded record")
            obj = ThingId(row["thing_id"])
            expected = f"known-unloaded:{obj}"
            if obj in document.known_unloaded_things:
                _raise("serialization.duplicate_identity", f"duplicate known-unloaded ThingId {obj}")
            document.known_unloaded_things.add(obj)
        elif record_type == "asset":
            obj = _asset_from_obj(value)
            expected = f"asset:{obj.asset_id}"
            _insert_unique(assets, obj.asset_id, obj, "AssetId")
        else:
            _raise("serialization.unsupported_record", f"unsupported semantic record type {record_type!r}")
        if semantic_key != expected:
            _raise("serialization.identity_mismatch", f"semantic key {semantic_key!r} does not match record identity {expected!r}")
    return CanonicalProjectRevision(document, assets)


def _insert_unique(target: dict[Any, Any], key: Any, value: Any, label: str) -> None:
    if key in target:
        _raise("serialization.duplicate_identity", f"duplicate {label}: {key}")
    target[key] = value


def deserialize_project(
    serialized: SerializedProjectRevision,
    *,
    migrations: MigrationRegistry = DEFAULT_MIGRATIONS,
) -> CanonicalProjectRevision:
    manifest = decode_canonical_cbor(serialized.root_manifest)
    manifest = _expect_keys(
        manifest,
        {
            "format", "schema_version", "canonical_profile", "project_id", "project_revision_id",
            "shard_policy", "required_features", "shards",
        },
        "root manifest",
    )
    if manifest["format"] != "splashmx.project-revision":
        _raise("serialization.incompatible_profile", "not a SplashMX project-revision manifest")
    if manifest["canonical_profile"] != CANONICAL_PROFILE or manifest["shard_policy"] != SHARD_POLICY:
        _raise("serialization.incompatible_profile", "canonical or shard profile is unsupported")
    version = manifest["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        _raise("serialization.invalid_version", "schema_version must be a non-negative integer")
    if version > CURRENT_SCHEMA_VERSION:
        _raise("serialization.unsupported_version", f"schema version {version} is newer than supported {CURRENT_SCHEMA_VERSION}")
    required = manifest["required_features"]
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        _raise("serialization.invalid_feature_set", "required_features must be a string list")
    unknown = set(required) - KNOWN_REQUIRED_FEATURES
    if unknown:
        _raise("serialization.unsupported_feature", f"unsupported required features: {sorted(unknown)}")
    descriptors = manifest["shards"]
    if not isinstance(descriptors, list):
        _raise("serialization.invalid_manifest", "shards must be a list")
    descriptor_keys = [row.get("key") if isinstance(row, dict) else None for row in descriptors]
    if len(descriptor_keys) != len(set(descriptor_keys)):
        _raise("serialization.duplicate_identity", "duplicate shard descriptor key")
    expected_keys = set(descriptor_keys)
    actual_keys = set(serialized.shards)
    if expected_keys != actual_keys:
        _raise("serialization.integrity_failure", "root manifest shard set does not match provided shards")
    descriptor_order = [(row.get("prefix_bits"), row.get("prefix")) for row in descriptors if isinstance(row, dict)]
    try:
        canonical_order = sorted(descriptor_order)
    except TypeError as exc:
        raise SerializationError("serialization.invalid_manifest", "shard descriptor prefix types are invalid") from exc
    if descriptor_order != canonical_order:
        _raise("serialization.noncanonical_manifest", "shard descriptors are not in canonical prefix order")
    records: list[dict[str, Any]] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            _raise("serialization.invalid_manifest", "shard descriptor must be a map")
        records.extend(_load_shard(descriptor, serialized.shards[descriptor["key"]]))
    if version < CURRENT_SCHEMA_VERSION:
        version, records = migrations.migrate(version, records)
    if version != CURRENT_SCHEMA_VERSION:
        _raise("serialization.unsupported_version", f"schema version {version} is not supported")
    records = [_ensure_record_plain(row) for row in records]
    project = _materialize(manifest["project_id"], manifest["project_revision_id"], records)
    validate_project_revision(project)
    return project


def prepare_migration(
    serialized: SerializedProjectRevision,
    *,
    migrations: MigrationRegistry = DEFAULT_MIGRATIONS,
) -> CanonicalProjectRevision:
    """Prepare and validate a migrated candidate without publishing mutable state."""
    return deserialize_project(serialized, migrations=migrations)
