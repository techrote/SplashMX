#!/usr/bin/env python3
"""Dependency-free validation helpers for SplashMX Phase-0 production contracts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    pass


SUPPORTED_SCHEMA_KEYS = {
    "$schema", "$id", "title", "description",
    "type", "const", "enum", "pattern", "minLength", "minimum", "maximum",
    "required", "properties", "additionalProperties", "items", "minItems",
}

FORBIDDEN_CANONICAL_IDENTITY_CLASSES = (
    "NodePath", "RID", "ResourceUID", "resource_path", "DOM_node_identity",
    "database_row_id", "cache_key", "url", "transport_peer_id",
    "connection_handle", "socket_id", "session_id", "process_handle",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ContractError(f"unsupported schema type: {expected}")


def assert_supported_schema(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ContractError(f"{path}: schema must be an object")
    unknown = sorted(set(schema) - SUPPORTED_SCHEMA_KEYS)
    if unknown:
        raise ContractError(f"{path}: unsupported schema keywords: {unknown}")
    properties = schema.get("properties", {})
    if properties:
        if not isinstance(properties, dict):
            raise ContractError(f"{path}.properties must be an object")
        for name, child in properties.items():
            assert_supported_schema(child, f"{path}.properties.{name}")
    if "items" in schema:
        assert_supported_schema(schema["items"], f"{path}.items")


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "const" in schema and instance != schema["const"]:
        raise ContractError(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise ContractError(f"{path}: value {instance!r} is outside enum")

    expected_type = schema.get("type")
    if expected_type is not None and not _is_type(instance, expected_type):
        raise ContractError(
            f"{path}: expected {expected_type}, got {type(instance).__name__}"
        )

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise ContractError(f"{path}: missing required keys {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                raise ContractError(f"{path}: unexpected keys {extra}")
        for key, child_schema in properties.items():
            if key in instance:
                validate(instance[key], child_schema, f"{path}.{key}")

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            raise ContractError(f"{path}: requires at least {min_items} items")
        child_schema = schema.get("items")
        if child_schema is not None:
            for index, value in enumerate(instance):
                validate(value, child_schema, f"{path}[{index}]")

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            raise ContractError(f"{path}: requires length >= {min_length}")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, instance) is None:
            raise ContractError(
                f"{path}: {instance!r} does not match {pattern!r}"
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and instance < minimum:
            raise ContractError(f"{path}: {instance} < minimum {minimum}")
        if maximum is not None and instance > maximum:
            raise ContractError(f"{path}: {instance} > maximum {maximum}")


def _normalise_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def validate_module_identity_policy(manifest: dict[str, Any]) -> None:
    declared_forbidden = manifest.get("forbidden_canonical_identity_classes")
    if declared_forbidden != list(FORBIDDEN_CANONICAL_IDENTITY_CLASSES):
        raise ContractError("module manifest forbidden identity class list changed")

    forbidden = {
        _normalise_identity(value)
        for value in FORBIDDEN_CANONICAL_IDENTITY_CLASSES
    }
    for module in manifest.get("modules", []):
        if module.get("forbidden_identity_classes") != list(
            FORBIDDEN_CANONICAL_IDENTITY_CLASSES
        ):
            raise ContractError(
                f"{module.get('module_id')}: forbidden identity classes are incomplete"
            )
        for identity in module.get("canonical_identity_inputs", []):
            if _normalise_identity(identity) in forbidden:
                raise ContractError(
                    f"{module.get('module_id')}: "
                    f"forbidden canonical identity input {identity!r}"
                )
