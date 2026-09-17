"""Disposable SMX-005 canonical-document research model.

This code is deliberately non-production and non-normative.  It exists only to make the
semantic claims in docs/research/SMX-005-CANONICAL-DOCUMENT.md executable.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable


FORMAT_FAMILY = "SplashMX"
CURRENT_SCHEMA = 2
ALLOWED_RECORD_KINDS = {
    "thing",
    "definition",
    "definition_revision",
    "instance",
    "behavior",
    "behavior_revision",
    "attachment",
    "relation",
    "connection",
    "asset",
    "extension",
}
FORBIDDEN_AUTHORED_ATTACHMENT_FIELDS = {
    "private_state",
    "prng_state",
    "timers",
    "continuations",
    "pending_activations",
}


class DocumentError(Exception):
    """Base research-model failure."""


class ValidationError(DocumentError):
    pass


class UnsupportedFeature(DocumentError):
    pass


class TransactionConflict(DocumentError):
    pass


@dataclass(frozen=True)
class Limits:
    max_records: int = 10_000
    max_catalog_entries: int = 20_000
    max_asset_bytes: int = 64 * 1024 * 1024
    max_depth: int = 64
    max_string_bytes: int = 4 * 1024 * 1024


@dataclass(frozen=True)
class Resolution:
    state: str
    kind: str
    target_id: str
    document_id: str | None = None
    port_id: str | None = None


def sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON number is not permitted: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json_strict(text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("document root must be an object")
    return value


def _check_depth_and_strings(value: Any, limits: Limits, depth: int = 0) -> None:
    if depth > limits.max_depth:
        raise ValidationError("document exceeds configured nesting depth")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > limits.max_string_bytes:
            raise ValidationError("string exceeds configured byte limit")
    elif isinstance(value, dict):
        for key, child in value.items():
            _check_depth_and_strings(key, limits, depth + 1)
            _check_depth_and_strings(child, limits, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_depth_and_strings(child, limits, depth + 1)


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    kind = record.get("kind")
    record_id = record.get("id")
    if not isinstance(kind, str) or not isinstance(record_id, str):
        raise ValidationError("record must contain string kind and id")
    return kind, record_id


def _catalog_key(entry: dict[str, Any]) -> tuple[str, str]:
    kind = entry.get("kind")
    record_id = entry.get("id")
    if not isinstance(kind, str) or not isinstance(record_id, str):
        raise ValidationError("catalog entry must contain string kind and id")
    return kind, record_id


def _normalize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(data)
    value["records"] = sorted(value.get("records", []), key=_record_key)
    value["catalog"] = sorted(value.get("catalog", []), key=_catalog_key)
    value["required_features"] = sorted(set(value.get("required_features", [])))
    value["optional_features"] = sorted(set(value.get("optional_features", [])))
    return value


def _normalize_for_semantics(data: dict[str, Any]) -> dict[str, Any]:
    """Remove physical chunk location while retaining existence/tombstone semantics."""
    value = _normalize_for_storage(data)
    semantic_catalog = []
    for entry in value.get("catalog", []):
        semantic_catalog.append(
            {
                key: child
                for key, child in entry.items()
                if key not in {"chunk", "offset", "storage_uri"}
            }
        )
    value["catalog"] = semantic_catalog
    return value


def canonical_bytes(data: dict[str, Any]) -> bytes:
    """Deterministic research projection, not the selected production encoding."""
    try:
        return json.dumps(
            _normalize_for_storage(data),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"document is not canonically JSON-encodable: {exc}") from exc


def semantic_fingerprint(data: dict[str, Any]) -> str:
    try:
        payload = json.dumps(
            _normalize_for_semantics(data),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"document is not semantically encodable: {exc}") from exc
    return sha256_digest(payload)


def make_reference(
    kind: str,
    target_id: str,
    *,
    document_id: str | None = None,
    port_id: str | None = None,
) -> dict[str, str]:
    result = {"kind": kind, "id": target_id}
    if document_id is not None:
        result["document_id"] = document_id
    if port_id is not None:
        result["port_id"] = port_id
    return result


def new_document(
    *,
    document_id: str = "doc:test",
    revision_id: str = "docrev:1",
    schema_version: int = CURRENT_SCHEMA,
) -> dict[str, Any]:
    return {
        "format_family": FORMAT_FAMILY,
        "schema_version": schema_version,
        "document_id": document_id,
        "revision_id": revision_id,
        "required_features": [],
        "optional_features": [],
        "extensions": {},
        "records": [],
        "catalog": [],
    }


def add_record(
    data: dict[str, Any],
    record: dict[str, Any],
    *,
    chunk: str = "chunk:main",
    status: str = "present",
) -> None:
    record = deepcopy(record)
    kind, record_id = _record_key(record)
    data.setdefault("records", []).append(record)
    data.setdefault("catalog", []).append(
        {"kind": kind, "id": record_id, "chunk": chunk, "status": status}
    )


def _index_records(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in data.get("records", []):
        key = _record_key(record)
        if key in index:
            raise ValidationError(f"duplicate record identity: {key[0]} {key[1]}")
        index[key] = record
    return index


def _index_catalog(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in data.get("catalog", []):
        key = _catalog_key(entry)
        if key in index:
            raise ValidationError(f"duplicate catalog identity: {key[0]} {key[1]}")
        index[key] = entry
    return index


def validate_document(
    data: dict[str, Any],
    *,
    supported_features: Iterable[str] = (),
    limits: Limits = Limits(),
    blobs: dict[str, bytes] | None = None,
    allow_partial: bool = True,
) -> None:
    _check_depth_and_strings(data, limits)

    if data.get("format_family") != FORMAT_FAMILY:
        raise ValidationError("unexpected format family")
    if not isinstance(data.get("schema_version"), int):
        raise ValidationError("schema_version must be an integer")
    if not isinstance(data.get("document_id"), str) or not data["document_id"]:
        raise ValidationError("document_id must be non-empty string")
    if not isinstance(data.get("revision_id"), str) or not data["revision_id"]:
        raise ValidationError("revision_id must be non-empty string")

    required = data.get("required_features", [])
    optional = data.get("optional_features", [])
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise ValidationError("required_features must be a list of strings")
    if not isinstance(optional, list) or not all(isinstance(x, str) for x in optional):
        raise ValidationError("optional_features must be a list of strings")
    unsupported = sorted(set(required) - set(supported_features))
    if unsupported:
        raise UnsupportedFeature("unsupported required features: " + ", ".join(unsupported))

    records = data.get("records", [])
    catalog = data.get("catalog", [])
    if not isinstance(records, list) or len(records) > limits.max_records:
        raise ValidationError("invalid or oversized record list")
    if not isinstance(catalog, list) or len(catalog) > limits.max_catalog_entries:
        raise ValidationError("invalid or oversized catalog")

    record_index = _index_records(data)
    catalog_index = _index_catalog(data)

    for (kind, record_id), record in record_index.items():
        if kind not in ALLOWED_RECORD_KINDS:
            raise ValidationError(f"unknown record kind without extension envelope: {kind}")
        if record.get("id") != record_id:
            raise ValidationError("record identity mismatch")
        cat = catalog_index.get((kind, record_id))
        if cat is None:
            raise ValidationError(f"loaded record absent from catalog: {kind} {record_id}")
        if cat.get("status") == "tombstoned":
            raise ValidationError(f"tombstoned record may not be materialized: {kind} {record_id}")

        if kind == "attachment":
            forbidden = FORBIDDEN_AUTHORED_ATTACHMENT_FIELDS.intersection(record)
            if forbidden:
                raise ValidationError(
                    "live executor state cannot be embedded in authored attachment: "
                    + ", ".join(sorted(forbidden))
                )
        if kind == "asset":
            byte_length = record.get("byte_length")
            digest = record.get("blob_digest")
            if not isinstance(byte_length, int) or byte_length < 0:
                raise ValidationError(f"asset {record_id} has invalid byte_length")
            if byte_length > limits.max_asset_bytes:
                raise ValidationError(f"asset {record_id} exceeds configured byte limit")
            if not isinstance(digest, str) or not digest.startswith("sha256:"):
                raise ValidationError(f"asset {record_id} has invalid blob digest")
            if blobs is not None and digest in blobs:
                payload = blobs[digest]
                if len(payload) != byte_length:
                    raise ValidationError(f"asset {record_id} blob length mismatch")
                if sha256_digest(payload) != digest:
                    raise ValidationError(f"asset {record_id} blob digest mismatch")

    for (kind, record_id), entry in catalog_index.items():
        if kind not in ALLOWED_RECORD_KINDS:
            raise ValidationError(f"catalog contains invalid kind: {kind}")
        status = entry.get("status")
        if status not in {"present", "tombstoned"}:
            raise ValidationError(f"catalog entry has invalid status: {status}")
        if not allow_partial and status == "present" and (kind, record_id) not in record_index:
            raise ValidationError(f"full document missing catalog record: {kind} {record_id}")

    # Minimal referential sanity for tested record families.
    for record in records:
        if record["kind"] == "connection":
            for endpoint_name in ("source", "target"):
                endpoint = record.get(endpoint_name)
                if not isinstance(endpoint, dict):
                    raise ValidationError("connection endpoint must be object")
                if not isinstance(endpoint.get("thing_id"), str):
                    raise ValidationError("connection endpoint missing thing_id")
                if not isinstance(endpoint.get("port_id"), str):
                    raise ValidationError("connection endpoint missing port_id")
        elif record["kind"] == "instance":
            if not isinstance(record.get("root_thing_id"), str):
                raise ValidationError("instance missing root_thing_id")
            if not isinstance(record.get("definition_id"), str):
                raise ValidationError("instance missing definition_id")
            if not isinstance(record.get("base_revision_id"), str):
                raise ValidationError("instance missing base_revision_id")
            if not isinstance(record.get("provenance"), dict):
                raise ValidationError("instance provenance must be object")
            if not isinstance(record.get("overlay"), dict):
                raise ValidationError("instance overlay must be object")


def record_lookup(data: dict[str, Any], kind: str, record_id: str) -> dict[str, Any]:
    index = _index_records(data)
    try:
        return index[(kind, record_id)]
    except KeyError as exc:
        raise ValidationError(f"record not loaded: {kind} {record_id}") from exc


def resolve_reference(
    data: dict[str, Any],
    ref: dict[str, Any],
    *,
    available_documents: Iterable[str] = (),
    supported_features: Iterable[str] = (),
) -> Resolution:
    kind = ref.get("kind")
    target_id = ref.get("id")
    if not isinstance(kind, str) or not isinstance(target_id, str):
        raise ValidationError("reference requires string kind and id")
    document_id = ref.get("document_id")
    port_id = ref.get("port_id")
    if document_id is not None and not isinstance(document_id, str):
        raise ValidationError("reference document_id must be string")
    if port_id is not None and not isinstance(port_id, str):
        raise ValidationError("reference port_id must be string")

    if document_id is not None and document_id != data.get("document_id"):
        if document_id not in set(available_documents):
            return Resolution("dependency_unavailable", kind, target_id, document_id, port_id)
        # The external document is known available but is not materialized in this model.
        return Resolution("known_unloaded", kind, target_id, document_id, port_id)

    catalog = _index_catalog(data)
    entry = catalog.get((kind, target_id))
    if entry is None:
        return Resolution("unknown", kind, target_id, document_id, port_id)
    if entry.get("status") == "tombstoned":
        return Resolution("tombstoned", kind, target_id, document_id, port_id)
    required = set(entry.get("required_features", []))
    if required - set(supported_features):
        return Resolution("incompatible", kind, target_id, document_id, port_id)
    records = _index_records(data)
    if (kind, target_id) in records:
        return Resolution("loaded", kind, target_id, document_id, port_id)
    return Resolution("known_unloaded", kind, target_id, document_id, port_id)


def encode_document(data: dict[str, Any]) -> str:
    return canonical_bytes(data).decode("utf-8")


def decode_document(
    text: str,
    *,
    supported_features: Iterable[str] = (),
    limits: Limits = Limits(),
) -> dict[str, Any]:
    data = decode_json_strict(text)
    validate_document(data, supported_features=supported_features, limits=limits)
    return data


def apply_transaction(
    data: dict[str, Any],
    transaction: dict[str, Any],
    *,
    supported_features: Iterable[str] = (),
    limits: Limits = Limits(),
) -> dict[str, Any]:
    if transaction.get("base_revision_id") != data.get("revision_id"):
        raise TransactionConflict("base document revision precondition failed")
    new_revision_id = transaction.get("new_revision_id")
    if not isinstance(new_revision_id, str) or not new_revision_id:
        raise ValidationError("transaction requires new_revision_id")
    operations = transaction.get("operations")
    if not isinstance(operations, list):
        raise ValidationError("transaction operations must be list")

    candidate = deepcopy(data)
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValidationError("transaction operation must be object")
        op = operation.get("op")
        if op == "set_thing_label":
            thing = record_lookup(candidate, "thing", operation["thing_id"])
            expected = operation.get("expected_label", thing.get("label"))
            if thing.get("label") != expected:
                raise TransactionConflict("Thing label precondition failed")
            thing["label"] = operation["label"]
        elif op == "reparent_thing":
            thing = record_lookup(candidate, "thing", operation["thing_id"])
            expected = operation.get("expected_parent", thing.get("parent"))
            if thing.get("parent") != expected:
                raise TransactionConflict("Thing parent precondition failed")
            thing["parent"] = deepcopy(operation.get("parent"))
        elif op == "relocate_record":
            key = (operation["kind"], operation["id"])
            catalog = _index_catalog(candidate)
            if key not in catalog:
                raise TransactionConflict("record relocation target missing")
            catalog[key]["chunk"] = operation["chunk"]
        elif op == "set_instance_overlay":
            instance = record_lookup(candidate, "instance", operation["root_thing_id"])
            locus = operation["locus"]
            overlay = instance.setdefault("overlay", {})
            if "expected" in operation and overlay.get(locus) != operation["expected"]:
                raise TransactionConflict("instance overlay precondition failed")
            overlay[locus] = deepcopy(operation["value"])
        elif op == "update_asset_blob":
            asset = record_lookup(candidate, "asset", operation["asset_id"])
            if "expected_digest" in operation and asset.get("blob_digest") != operation["expected_digest"]:
                raise TransactionConflict("asset digest precondition failed")
            asset["blob_digest"] = operation["blob_digest"]
            asset["byte_length"] = operation["byte_length"]
        elif op == "tombstone_record":
            key = (operation["kind"], operation["id"])
            catalog = _index_catalog(candidate)
            entry = catalog.get(key)
            if entry is None:
                raise TransactionConflict("tombstone target missing")
            candidate["records"] = [
                record
                for record in candidate["records"]
                if _record_key(record) != key
            ]
            entry["status"] = "tombstoned"
        else:
            raise ValidationError(f"unknown semantic transaction operation: {op}")

    candidate["revision_id"] = new_revision_id
    validate_document(
        candidate,
        supported_features=supported_features,
        limits=limits,
    )
    return candidate


def migrate_v1_to_v2(
    source: dict[str, Any],
    *,
    supported_features: Iterable[str] = (),
    limits: Limits = Limits(),
) -> dict[str, Any]:
    if source.get("schema_version") != 1:
        raise ValidationError("v1->v2 migrator requires schema_version 1")
    candidate = deepcopy(source)

    for record in candidate.get("records", []):
        if record.get("kind") == "thing" and "name" in record:
            if "label" in record:
                raise ValidationError("v1 Thing contains both name and label")
            record["label"] = record.pop("name")

    candidate["schema_version"] = 2
    old_revision = candidate.get("revision_id")
    if not isinstance(old_revision, str):
        raise ValidationError("source revision_id missing")
    candidate["revision_id"] = old_revision + ":m2"

    validate_document(
        candidate,
        supported_features=supported_features,
        limits=limits,
    )
    return candidate


def migrate_to_current(
    source: dict[str, Any],
    *,
    supported_features: Iterable[str] = (),
    limits: Limits = Limits(),
) -> dict[str, Any]:
    candidate = deepcopy(source)
    while candidate.get("schema_version") != CURRENT_SCHEMA:
        version = candidate.get("schema_version")
        if version == 1:
            candidate = migrate_v1_to_v2(
                candidate,
                supported_features=supported_features,
                limits=limits,
            )
        else:
            raise UnsupportedFeature(f"no migration path from schema version {version}")
    return candidate
