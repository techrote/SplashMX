from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


class CollaborationHarnessError(ValueError):
    """Base error for the disposable SMX-018 collaboration harness."""


class ValidationError(CollaborationHarnessError):
    pass


class TransactionCollision(CollaborationHarnessError):
    pass


class CausalCycle(CollaborationHarnessError):
    pass


FORBIDDEN_RUNTIME_KEYS = frozenset({
    "peer_id", "connection_id", "authority_epoch", "rpc", "rpc_id",
    "transport", "websocket", "webrtc", "enet", "session_token",
    "capability_grant", "host_handle", "multiplayer_authority", "socket",
})

ALLOWED_KINDS = frozenset({
    "set_property", "delete_thing", "reparent", "definition_set",
    "definition_remove_element", "instance_overlay", "create_connection",
    "delete_connection", "delete_port", "set_keyframe", "group",
    "component_update", "asset_rename", "asset_replace",
})

ASSET_BUNDLE_KEYS = frozenset({
    "digest", "source", "audio", "provenance", "licence", "derivation"
})


@dataclass(frozen=True)
class Operation:
    kind: str
    target: str
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Transaction:
    tx_id: str
    actor: str
    operations: tuple[Operation, ...]
    deps: frozenset[str] = frozenset()
    permission_epoch: int = 1
    schema_version: int = 1
    inverse_of: str | None = None
    resolves: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Conflict:
    conflict_id: str
    kind: str
    tx_ids: tuple[str, ...]
    loci: tuple[str, ...]
    policy: str


@dataclass(frozen=True)
class Rejection:
    tx_id: str
    reason: str


@dataclass(frozen=True)
class Pending:
    tx_id: str
    reason: str


@dataclass
class Materialization:
    state: dict[str, Any]
    conflicts: tuple[Conflict, ...]
    rejections: tuple[Rejection, ...]
    pending: tuple[Pending, ...]
    applied: tuple[str, ...]
    resolved_conflicts: tuple[str, ...]
    history: tuple[str, ...]

    def canonical_snapshot(self) -> dict[str, Any]:
        return json.loads(canonical_json(self.state))

    def collaboration_snapshot(self) -> dict[str, Any]:
        return {
            "canonical": self.canonical_snapshot(),
            "conflicts": [
                {
                    "id": c.conflict_id,
                    "kind": c.kind,
                    "tx_ids": list(c.tx_ids),
                    "loci": list(c.loci),
                    "policy": c.policy,
                }
                for c in self.conflicts
            ],
            "rejections": [r.__dict__ for r in self.rejections],
            "pending": [p.__dict__ for p in self.pending],
            "applied": list(self.applied),
            "resolved_conflicts": list(self.resolved_conflicts),
            "history": list(self.history),
        }

    @property
    def digest(self) -> str:
        return sha256(canonical_json(self.collaboration_snapshot()).encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_RUNTIME_KEYS:
                raise ValidationError(
                    f"runtime multiplayer key {key!r} is not collaboration data at {path}"
                )
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def validate_asset_bundle(bundle: Any) -> None:
    if not isinstance(bundle, Mapping) or set(bundle) != ASSET_BUNDLE_KEYS:
        raise ValidationError(
            "asset_replace requires one complete digest/source/audio/provenance/"
            "licence/derivation bundle"
        )
    if not isinstance(bundle["digest"], str) or not bundle["digest"]:
        raise ValidationError("asset digest must be non-empty")
    for key in ("source", "audio", "provenance", "derivation"):
        if not isinstance(bundle[key], Mapping):
            raise ValidationError(f"asset replacement {key} must be an object")
    if not isinstance(bundle["licence"], str) or not bundle["licence"]:
        raise ValidationError("asset replacement licence must be non-empty")


def validate_transaction(tx: Transaction) -> None:
    if not tx.tx_id or not tx.actor or not tx.operations:
        raise ValidationError("transaction id, actor and operations are required")
    if tx.tx_id in tx.deps:
        raise ValidationError("transaction cannot depend on itself")
    if tx.permission_epoch < 0 or tx.schema_version < 1:
        raise ValidationError("invalid permission/schema epoch")
    for operation in tx.operations:
        if operation.kind not in ALLOWED_KINDS:
            raise ValidationError(f"unknown collaboration operation: {operation.kind}")
        if not operation.target:
            raise ValidationError("operation target is required")
        _walk_forbidden(operation.data)
        if operation.kind == "asset_replace":
            validate_asset_bundle(operation.data.get("bundle"))


def encode_transaction(tx: Transaction) -> str:
    validate_transaction(tx)
    payload = {
        "tx_id": tx.tx_id,
        "actor": tx.actor,
        "operations": [
            {"kind": op.kind, "target": op.target, "data": dict(op.data)}
            for op in tx.operations
        ],
        "deps": sorted(tx.deps),
        "permission_epoch": tx.permission_epoch,
        "schema_version": tx.schema_version,
        "inverse_of": tx.inverse_of,
        "resolves": sorted(tx.resolves),
    }
    return canonical_json(payload)


def decode_transaction(payload: str) -> Transaction:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValidationError("invalid transaction JSON") from exc
    if not isinstance(value, Mapping):
        raise ValidationError("transaction envelope must be an object")
    operations = value.get("operations")
    if not isinstance(operations, list):
        raise ValidationError("transaction operations must be an array")
    tx = Transaction(
        tx_id=str(value.get("tx_id", "")),
        actor=str(value.get("actor", "")),
        operations=tuple(
            Operation(str(item.get("kind", "")), str(item.get("target", "")), item.get("data", {}))
            for item in operations
            if isinstance(item, Mapping)
        ),
        deps=frozenset(map(str, value.get("deps", []))),
        permission_epoch=int(value.get("permission_epoch", 1)),
        schema_version=int(value.get("schema_version", 1)),
        inverse_of=(None if value.get("inverse_of") is None else str(value["inverse_of"])),
        resolves=frozenset(map(str, value.get("resolves", []))),
    )
    validate_transaction(tx)
    return tx


def _thing(state: Mapping[str, Any], thing_id: str) -> Mapping[str, Any]:
    try:
        return state["things"][thing_id]
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"unknown Thing {thing_id}") from exc


def _instance_definition(base_state: Mapping[str, Any], instance_id: str) -> str | None:
    try:
        return str(base_state["instances"][instance_id]["definition_id"])
    except (KeyError, TypeError):
        return None


def _connection_uses_thing(operation: Operation, thing_id: str) -> bool:
    if operation.kind != "create_connection":
        return False
    data = operation.data
    return (
        str(data.get("source_thing")) == thing_id
        or str(data.get("target_thing")) == thing_id
    )


def _connection_uses_port(operation: Operation, thing_id: str, port_id: str) -> bool:
    if operation.kind != "create_connection":
        return False
    data = operation.data
    return (
        (str(data.get("source_thing")), str(data.get("source_port"))) == (thing_id, port_id)
        or (str(data.get("target_thing")), str(data.get("target_port"))) == (thing_id, port_id)
    )


def op_locus(operation: Operation, base_state: Mapping[str, Any] | None = None) -> str:
    data = operation.data
    if operation.kind == "set_property":
        return f"thing:{operation.target}.property:{data.get('key')}"
    if operation.kind == "delete_thing":
        return f"thing:{operation.target}.existence"
    if operation.kind == "reparent":
        return f"thing:{operation.target}.parent"
    if operation.kind == "definition_set":
        return (
            f"definition:{operation.target}.element:{data.get('element')}"
            f".field:{data.get('key')}"
        )
    if operation.kind == "definition_remove_element":
        return f"definition:{operation.target}.element:{data.get('element')}"
    if operation.kind == "instance_overlay":
        definition = (
            _instance_definition(base_state, operation.target) if base_state is not None else "?"
        )
        return (
            f"instance:{operation.target}.definition:{definition}.element:{data.get('element')}"
            f".field:{data.get('key')}"
        )
    if operation.kind in {"create_connection", "delete_connection"}:
        return f"connection:{operation.target}"
    if operation.kind == "delete_port":
        return f"thing:{operation.target}.port:{data.get('port')}"
    if operation.kind == "set_keyframe":
        return (
            f"timeline:{data.get('track')}.key:{operation.target}.time:{data.get('time')}"
        )
    if operation.kind == "group":
        return f"group:{operation.target}"
    if operation.kind == "component_update":
        return f"instance:{operation.target}.component-version"
    if operation.kind == "asset_rename":
        return f"asset:{operation.target}.label"
    if operation.kind == "asset_replace":
        return f"asset:{operation.target}.revision-bundle"
    return f"{operation.kind}:{operation.target}"


def _same_locus_conflict(left: Operation, right: Operation) -> tuple[str, str] | None:
    ld, rd = left.data, right.data
    if left.kind == right.kind == "set_property" and left.target == right.target:
        if ld.get("key") == rd.get("key") and ld.get("value") != rd.get("value"):
            return ("same_property", "hold_both")
    if left.kind == right.kind == "definition_set" and left.target == right.target:
        if (
            ld.get("element") == rd.get("element")
            and ld.get("key") == rd.get("key")
            and ld.get("value") != rd.get("value")
        ):
            return ("definition_same_locus", "hold_both")
    if left.kind == right.kind == "instance_overlay" and left.target == right.target:
        if (
            ld.get("element") == rd.get("element")
            and ld.get("key") == rd.get("key")
            and ld.get("value") != rd.get("value")
        ):
            return ("instance_overlay_same_locus", "hold_both")
    if left.kind == right.kind == "asset_rename" and left.target == right.target:
        if ld.get("label") != rd.get("label"):
            return ("asset_label", "hold_both")
    if left.kind == right.kind == "component_update" and left.target == right.target:
        if ld.get("to_version") != rd.get("to_version"):
            return ("component_update", "hold_both")
    return None


def operation_conflict(
    left: Operation, right: Operation, base_state: Mapping[str, Any]
) -> tuple[str, str] | None:
    direct = _same_locus_conflict(left, right)
    if direct is not None:
        return direct

    ld, rd = left.data, right.data

    if left.target == right.target:
        if left.kind == "delete_thing" and right.kind != "delete_thing":
            return ("delete_edit", "left_remove_wins")
        if right.kind == "delete_thing" and left.kind != "delete_thing":
            return ("delete_edit", "right_remove_wins")

    if left.kind == "delete_thing" and _connection_uses_thing(right, left.target):
        return ("delete_connection_endpoint", "left_remove_wins")
    if right.kind == "delete_thing" and _connection_uses_thing(left, right.target):
        return ("delete_connection_endpoint", "right_remove_wins")

    if left.kind == right.kind == "reparent" and left.target == right.target:
        if ld.get("parent") != rd.get("parent"):
            return ("reparent", "hold_both")

    if left.kind == "definition_remove_element" and right.kind == "instance_overlay":
        if (
            _instance_definition(base_state, right.target) == left.target
            and ld.get("element") == rd.get("element")
        ):
            return ("definition_instance", "hold_both")
    if right.kind == "definition_remove_element" and left.kind == "instance_overlay":
        if (
            _instance_definition(base_state, left.target) == right.target
            and rd.get("element") == ld.get("element")
        ):
            return ("definition_instance", "hold_both")

    if left.kind == "delete_port" and _connection_uses_port(
        right, left.target, str(ld.get("port"))
    ):
        return ("structure_connection", "hold_both")
    if right.kind == "delete_port" and _connection_uses_port(
        left, right.target, str(rd.get("port"))
    ):
        return ("structure_connection", "hold_both")

    if left.kind == right.kind == "set_keyframe" and ld.get("track") == rd.get("track"):
        if left.target == right.target or ld.get("time") == rd.get("time"):
            if ld.get("value") != rd.get("value"):
                return ("timeline_overlap", "hold_both")

    if left.kind == right.kind == "group":
        left_members = set(map(str, ld.get("members", [])))
        right_members = set(map(str, rd.get("members", [])))
        if left_members & right_members and (
            left.target != right.target or left_members != right_members
        ):
            return ("group_overlap", "hold_both")

    if left.kind == "component_update" and right.kind == "instance_overlay":
        if left.target == right.target and not ld.get("migration_ok", True):
            return ("component_update_local_edit", "hold_left")
    if right.kind == "component_update" and left.kind == "instance_overlay":
        if left.target == right.target and not rd.get("migration_ok", True):
            return ("component_update_local_edit", "hold_right")

    if left.kind == "delete_connection" and right.kind == "create_connection":
        if left.target == right.target:
            return ("connection_remove_recreate", "left_remove_wins")
    if right.kind == "delete_connection" and left.kind == "create_connection":
        if left.target == right.target:
            return ("connection_remove_recreate", "right_remove_wins")

    if left.kind == right.kind == "create_connection" and left.target == right.target:
        if canonical_json(ld) != canonical_json(rd):
            return ("connection_identity_collision", "hold_both")

    if left.kind == right.kind == "asset_replace" and left.target == right.target:
        if canonical_json(ld.get("bundle")) != canonical_json(rd.get("bundle")):
            return ("asset_replacement", "hold_both")

    return None


def _topological_order(transactions: Mapping[str, Transaction]) -> list[str]:
    remaining = set(transactions)
    result: list[str] = []
    while remaining:
        ready = sorted(
            tx_id
            for tx_id in remaining
            if not (transactions[tx_id].deps & remaining)
        )
        if not ready:
            raise CausalCycle("transaction dependency cycle")
        result.extend(ready)
        remaining.difference_update(ready)
    return result


def _ancestors(transactions: Mapping[str, Transaction]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for tx_id in _topological_order(transactions):
        ancestors: set[str] = set()
        for dep in transactions[tx_id].deps:
            if dep in transactions:
                ancestors.add(dep)
                ancestors.update(result[dep])
        result[tx_id] = ancestors
    return result


def transaction_availability(state: Mapping[str, Any], tx: Transaction) -> str:
    statuses = state.get("catalog_status", {})
    seen: list[str] = []
    for operation in tx.operations:
        if operation.kind in {"set_property", "delete_thing", "reparent", "delete_port"}:
            seen.append(str(statuses.get(operation.target, "unknown")))
        elif operation.kind == "create_connection":
            seen.append(str(statuses.get(str(operation.data.get("source_thing")), "unknown")))
            seen.append(str(statuses.get(str(operation.data.get("target_thing")), "unknown")))
    if "tombstoned" in seen:
        return "tombstoned"
    if "unknown" in seen:
        return "unknown"
    if "known_unloaded" in seen:
        return "known_unloaded"
    return "loaded"


def _apply(state: dict[str, Any], operation: Operation) -> None:
    data = operation.data
    if operation.kind == "set_property":
        thing = _thing(state, operation.target)
        if thing.get("existence", "present") != "present":
            raise ValidationError("tombstoned Thing")
        props = thing.setdefault("props", {})
        key = str(data["key"])
        if "expected" in data and props.get(key) != data.get("expected"):
            raise ValidationError("property precondition")
        props[key] = deepcopy(data.get("value"))
        return

    if operation.kind == "delete_thing":
        thing = _thing(state, operation.target)
        thing["existence"] = "tombstoned"
        state.setdefault("catalog_status", {})[operation.target] = "tombstoned"
        # Referential-integrity consequence of a durable Thing tombstone: live
        # connections incident on the destroyed identity become tombstoned in the
        # same atomic semantic transaction. They are history, not dangling active
        # edges and cannot later resurrect the deleted Thing.
        for connection in state.get("connections", {}).values():
            if connection.get("tombstoned"):
                continue
            if (
                str(connection.get("source_thing")) == operation.target
                or str(connection.get("target_thing")) == operation.target
            ):
                connection["tombstoned"] = True
        return

    if operation.kind == "reparent":
        thing = _thing(state, operation.target)
        if thing.get("existence", "present") != "present":
            raise ValidationError("tombstoned Thing")
        if "expected_parent" in data and thing.get("parent") != data.get("expected_parent"):
            raise ValidationError("parent precondition")
        parent = data.get("parent")
        if parent is not None and parent not in state.get("things", {}) and parent not in state.get("groups", {}):
            raise ValidationError("unknown parent")
        thing["parent"] = parent
        return

    if operation.kind == "definition_set":
        try:
            element = state["definitions"][operation.target]["elements"][str(data["element"])]
        except KeyError as exc:
            raise ValidationError("definition element missing") from exc
        element[str(data["key"])] = deepcopy(data.get("value"))
        return

    if operation.kind == "definition_remove_element":
        try:
            del state["definitions"][operation.target]["elements"][str(data["element"])]
        except KeyError as exc:
            raise ValidationError("definition element missing") from exc
        return

    if operation.kind == "instance_overlay":
        try:
            instance = state["instances"][operation.target]
            definition = state["definitions"][instance["definition_id"]]
            element = str(data["element"])
            if element not in definition["elements"]:
                raise KeyError(element)
        except KeyError as exc:
            raise ValidationError("instance overlay target missing") from exc
        locus = f"{data['element']}:{data['key']}"
        instance.setdefault("overlays", {})[locus] = deepcopy(data.get("value"))
        return

    if operation.kind == "create_connection":
        source_id = str(data["source_thing"])
        target_id = str(data["target_thing"])
        source = _thing(state, source_id)
        target = _thing(state, target_id)
        if source.get("existence", "present") != "present" or target.get("existence", "present") != "present":
            raise ValidationError("connection endpoint tombstoned")
        if str(data["source_port"]) not in source.get("ports", []):
            raise ValidationError("source port missing")
        if str(data["target_port"]) not in target.get("ports", []):
            raise ValidationError("target port missing")
        old = state.setdefault("connections", {}).get(operation.target)
        candidate = {
            "source_thing": source_id,
            "source_port": str(data["source_port"]),
            "target_thing": target_id,
            "target_port": str(data["target_port"]),
            "tombstoned": False,
        }
        if old is not None:
            if old.get("tombstoned"):
                raise ValidationError("connection identity cannot be resurrected")
            if old != candidate:
                raise ValidationError("connection identity already exists")
        state["connections"][operation.target] = candidate
        return

    if operation.kind == "delete_connection":
        connection = state.setdefault("connections", {}).setdefault(operation.target, {})
        connection["tombstoned"] = True
        return

    if operation.kind == "delete_port":
        thing = _thing(state, operation.target)
        port = str(data["port"])
        if port not in thing.get("ports", []):
            return
        thing["ports"] = [item for item in thing["ports"] if item != port]
        return

    if operation.kind == "set_keyframe":
        state.setdefault("keyframes", {})[operation.target] = {
            "track": str(data["track"]),
            "time": data["time"],
            "value": deepcopy(data.get("value")),
        }
        return

    if operation.kind == "group":
        members = list(map(str, data.get("members", [])))
        if not members or len(members) != len(set(members)):
            raise ValidationError("group members must be non-empty and unique")
        for member in members:
            thing = _thing(state, member)
            if thing.get("existence", "present") != "present":
                raise ValidationError("cannot group tombstoned Thing")
        state.setdefault("groups", {})[operation.target] = {"members": members}
        for member in members:
            state["things"][member]["parent"] = operation.target
        return

    if operation.kind == "component_update":
        try:
            instance = state["instances"][operation.target]
        except KeyError as exc:
            raise ValidationError("component instance missing") from exc
        if instance.get("component_version") != data.get("from_version"):
            raise ValidationError("component version precondition")
        if not data.get("migration_ok", True):
            raise ValidationError("component migration failed")
        instance["component_version"] = str(data["to_version"])
        return

    if operation.kind == "asset_rename":
        try:
            asset = state["assets"][operation.target]
        except KeyError as exc:
            raise ValidationError("asset missing") from exc
        if "expected_label" in data and asset.get("label") != data.get("expected_label"):
            raise ValidationError("asset label precondition")
        asset["label"] = str(data["label"])
        return

    if operation.kind == "asset_replace":
        try:
            asset = state["assets"][operation.target]
        except KeyError as exc:
            raise ValidationError("asset missing") from exc
        validate_asset_bundle(data["bundle"])
        if (
            "expected_digest" in data
            and asset.get("revision_bundle", {}).get("digest") != data.get("expected_digest")
        ):
            raise ValidationError("asset digest precondition")
        asset["revision_bundle"] = deepcopy(dict(data["bundle"]))
        return

    raise ValidationError(f"unsupported operation {operation.kind}")


def validate_document(state: Mapping[str, Any]) -> None:
    _walk_forbidden(state)
    things = state.get("things", {})
    groups = state.get("groups", {})

    for thing_id, thing in things.items():
        parent = thing.get("parent")
        if parent is not None and parent not in things and parent not in groups:
            raise ValidationError(f"Thing {thing_id} has unknown parent {parent}")

    for group_id, group in groups.items():
        members = list(map(str, group.get("members", [])))
        if not members or len(members) != len(set(members)):
            raise ValidationError(f"group {group_id} has invalid membership")
        for member in members:
            if member not in things or things[member].get("existence", "present") != "present":
                raise ValidationError(f"group {group_id} contains unavailable Thing {member}")

    for connection_id, connection in state.get("connections", {}).items():
        if connection.get("tombstoned"):
            continue
        source_id = str(connection.get("source_thing"))
        target_id = str(connection.get("target_thing"))
        source = _thing(state, source_id)
        target = _thing(state, target_id)
        if source.get("existence", "present") != "present" or target.get("existence", "present") != "present":
            raise ValidationError(f"connection {connection_id} targets tombstoned Thing")
        if str(connection.get("source_port")) not in source.get("ports", []):
            raise ValidationError(f"connection {connection_id} has missing source port")
        if str(connection.get("target_port")) not in target.get("ports", []):
            raise ValidationError(f"connection {connection_id} has missing target port")

    for instance_id, instance in state.get("instances", {}).items():
        definition_id = str(instance.get("definition_id"))
        if definition_id not in state.get("definitions", {}):
            raise ValidationError(f"instance {instance_id} has missing definition")
        elements = state["definitions"][definition_id].get("elements", {})
        for locus in instance.get("overlays", {}):
            element = str(locus).split(":", 1)[0]
            if element not in elements:
                raise ValidationError(
                    f"instance {instance_id} overlay targets missing element {element}"
                )

    for asset_id, asset in state.get("assets", {}).items():
        if str(asset.get("asset_id")) != str(asset_id):
            raise ValidationError(f"asset identity mismatch for {asset_id}")
        validate_asset_bundle(asset.get("revision_bundle"))

    statuses = state.get("catalog_status", {})
    for thing_id, thing in things.items():
        if thing.get("existence", "present") == "tombstoned":
            if statuses.get(thing_id) != "tombstoned":
                raise ValidationError(f"tombstoned Thing {thing_id} has inconsistent catalog status")


def materialize(
    base_state: Mapping[str, Any],
    transactions: Iterable[Transaction],
    *,
    permission_epochs: Mapping[str, int] | None = None,
) -> Materialization:
    state = deepcopy(dict(base_state))
    validate_document(state)
    permission_epochs = dict(permission_epochs or {})
    txs: dict[str, Transaction] = {}

    for tx in transactions:
        validate_transaction(tx)
        old = txs.get(tx.tx_id)
        if old is not None and old != tx:
            raise TransactionCollision(f"transaction id collision for {tx.tx_id}")
        txs[tx.tx_id] = tx

    order = _topological_order(txs)
    ancestry = _ancestors(txs)
    schema_version = int(state.get("schema_version", 1))

    invalid: set[str] = set()
    rejections: list[Rejection] = []
    for tx in txs.values():
        current_permission = permission_epochs.get(tx.actor, tx.permission_epoch)
        if tx.permission_epoch != current_permission:
            invalid.add(tx.tx_id)
            rejections.append(Rejection(tx.tx_id, "permission_epoch_changed"))
        elif tx.schema_version != schema_version:
            invalid.add(tx.tx_id)
            rejections.append(Rejection(tx.tx_id, "schema_migration_required"))

    missing = {
        tx_id
        for tx_id, tx in txs.items()
        if set(tx.deps) - set(txs)
    }

    conflicts: dict[str, Conflict] = {}
    held: set[str] = set()
    ids = sorted(txs)
    for index, left_id in enumerate(ids):
        if left_id in invalid:
            continue
        for right_id in ids[index + 1 :]:
            if right_id in invalid:
                continue
            if left_id in ancestry[right_id] or right_id in ancestry[left_id]:
                continue
            left = txs[left_id]
            right = txs[right_id]
            for left_op in left.operations:
                for right_op in right.operations:
                    found = operation_conflict(left_op, right_op, base_state)
                    if found is None:
                        continue
                    kind, policy = found
                    pair = tuple(sorted((left_id, right_id)))
                    conflict_id = f"conflict:{kind}:{pair[0]}:{pair[1]}"
                    loci = tuple(
                        sorted(
                            {
                                op_locus(left_op, base_state),
                                op_locus(right_op, base_state),
                            }
                        )
                    )
                    conflicts[conflict_id] = Conflict(
                        conflict_id, kind, pair, loci, policy
                    )
                    if policy == "hold_both":
                        held.update(pair)
                    elif policy == "left_remove_wins":
                        held.add(right_id)
                    elif policy == "right_remove_wins":
                        held.add(left_id)
                    elif policy == "hold_left":
                        held.add(left_id)
                    elif policy == "hold_right":
                        held.add(right_id)

    resolved: set[str] = set()
    for tx in txs.values():
        for conflict_id, conflict in conflicts.items():
            if (
                tx.resolves
                and set(conflict.tx_ids).issubset(tx.resolves)
                and set(conflict.tx_ids).issubset(tx.deps)
            ):
                resolved.add(conflict_id)

    unresolved = {
        conflict_id: conflict
        for conflict_id, conflict in conflicts.items()
        if conflict_id not in resolved
    }

    pending: list[Pending] = []
    applied: list[str] = []
    applied_set: set[str] = set()

    for tx_id in order:
        tx = txs[tx_id]
        if tx_id in invalid:
            continue
        if tx_id in missing:
            pending.append(Pending(tx_id, "missing_causal_dependency"))
            continue
        if tx_id in held:
            continue

        unavailable = set(tx.deps) - applied_set
        unavailable -= unavailable & set(tx.resolves)
        if unavailable:
            pending.append(Pending(tx_id, "blocked_by_unapplied_dependency"))
            continue

        availability = transaction_availability(state, tx)
        if availability == "known_unloaded":
            pending.append(Pending(tx_id, "known_unloaded_target"))
            continue
        if availability in {"tombstoned", "unknown"}:
            conflict_id = f"conflict:target_{availability}:{tx_id}"
            unresolved[conflict_id] = Conflict(
                conflict_id,
                f"target_{availability}",
                (tx_id,),
                tuple(sorted(op_locus(op, base_state) for op in tx.operations)),
                "hold_transaction",
            )
            continue

        candidate = deepcopy(state)
        try:
            for operation in tx.operations:
                _apply(candidate, operation)
            validate_document(candidate)
        except (KeyError, ValidationError):
            conflict_id = f"conflict:precondition:{tx_id}"
            unresolved[conflict_id] = Conflict(
                conflict_id,
                "precondition_failed",
                (tx_id,),
                tuple(sorted(op_locus(op, base_state) for op in tx.operations)),
                "hold_transaction",
            )
            continue

        state = candidate
        applied.append(tx_id)
        applied_set.add(tx_id)

    validate_document(state)
    return Materialization(
        state=state,
        conflicts=tuple(unresolved[key] for key in sorted(unresolved)),
        rejections=tuple(sorted(rejections, key=lambda item: item.tx_id)),
        pending=tuple(sorted(pending, key=lambda item: (item.tx_id, item.reason))),
        applied=tuple(applied),
        resolved_conflicts=tuple(sorted(resolved)),
        history=tuple(sorted(txs)),
    )


class Relay:
    """Deterministic content-checked causal transaction relay.

    This is deliberately not a production sync server or CRDT. It exercises the
    accepted semantic transaction layer across serialization, offline batching,
    duplicate delivery and adversarial reorder.
    """

    def __init__(self) -> None:
        self._payloads: dict[str, str] = {}

    def ingest(self, tx: Transaction) -> None:
        payload = encode_transaction(tx)
        old = self._payloads.get(tx.tx_id)
        if old is not None and old != payload:
            raise TransactionCollision(f"relay transaction id collision for {tx.tx_id}")
        self._payloads[tx.tx_id] = payload

    def ingest_payload(self, payload: str) -> None:
        self.ingest(decode_transaction(payload))

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._payloads))

    def payload(self, tx_id: str) -> str:
        return self._payloads[tx_id]

    @property
    def encoded_bytes(self) -> int:
        return sum(len(payload.encode("utf-8")) for payload in self._payloads.values())


class Replica:
    def __init__(
        self,
        replica_id: str,
        base_state: Mapping[str, Any],
        *,
        permission_epochs: Mapping[str, int] | None = None,
    ) -> None:
        self.replica_id = replica_id
        self.base_state = deepcopy(dict(base_state))
        validate_document(self.base_state)
        self.permission_epochs = dict(permission_epochs or {})
        self.transactions: dict[str, Transaction] = {}
        self.presence: dict[str, Any] = {}
        self.online = True

    def author(self, tx: Transaction) -> None:
        validate_transaction(tx)
        old = self.transactions.get(tx.tx_id)
        if old is not None and old != tx:
            raise TransactionCollision(f"replica transaction id collision for {tx.tx_id}")
        self.transactions[tx.tx_id] = tx

    def set_presence(self, **state: Any) -> None:
        self.presence = deepcopy(state)

    def clear_presence(self) -> None:
        self.presence.clear()

    def disconnect(self) -> None:
        self.online = False

    def reconnect(self) -> None:
        self.online = True

    def set_permission_epoch(self, actor: str, epoch: int) -> None:
        self.permission_epochs[actor] = epoch

    def push(self, relay: Relay) -> None:
        if not self.online:
            return
        for tx_id in sorted(self.transactions):
            relay.ingest(self.transactions[tx_id])

    def pull(
        self,
        relay: Relay,
        *,
        order: Sequence[str] | None = None,
        duplicate_each: bool = False,
    ) -> None:
        if not self.online:
            return
        ids = list(order if order is not None else relay.ids())
        if set(ids) - set(relay.ids()):
            raise ValidationError("pull order references unknown relay transaction")
        for tx_id in ids:
            tx = decode_transaction(relay.payload(tx_id))
            self.author(tx)
            if duplicate_each:
                self.author(decode_transaction(relay.payload(tx_id)))

    def materialize(self) -> Materialization:
        return materialize(
            self.base_state,
            self.transactions.values(),
            permission_epochs=self.permission_epochs,
        )

    def persisted_snapshot(self) -> dict[str, Any]:
        # Presence is deliberately absent.
        return self.materialize().collaboration_snapshot()

    @property
    def history_bytes(self) -> int:
        return sum(
            len(encode_transaction(tx).encode("utf-8"))
            for tx in self.transactions.values()
        )


def synchronize(
    relay: Relay,
    replicas: Sequence[Replica],
    *,
    delivery_orders: Mapping[str, Sequence[str]] | None = None,
    duplicate_each: bool = False,
) -> None:
    for replica in replicas:
        replica.push(relay)
    for replica in replicas:
        order = None
        if delivery_orders is not None:
            order = delivery_orders.get(replica.replica_id)
        replica.pull(relay, order=order, duplicate_each=duplicate_each)


def equivalent(replicas: Sequence[Replica]) -> bool:
    if not replicas:
        return True
    expected = replicas[0].persisted_snapshot()
    return all(replica.persisted_snapshot() == expected for replica in replicas[1:])
