from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Any, Iterable, Mapping


class CollaborationError(ValueError):
    pass


class CollaborationValidationError(CollaborationError):
    pass


class DuplicateTransactionError(CollaborationError):
    pass


class SemanticPreconditionError(CollaborationError):
    pass


ALLOWED_KINDS = frozenset({
    "set_property", "delete_thing", "reparent", "definition_set",
    "definition_remove_element", "instance_overlay", "create_connection",
    "delete_connection", "delete_port", "set_keyframe", "group",
    "component_update", "asset_rename", "asset_replace",
})
FORBIDDEN_RUNTIME_KEYS = frozenset({
    "peer_id", "connection_id", "authority_epoch", "rpc", "rpc_id",
    "transport", "websocket", "webrtc", "enet", "session_token",
    "capability_grant", "host_handle", "multiplayer_authority",
})
ASSET_BUNDLE_KEYS = frozenset({"digest", "source", "audio", "provenance"})


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

    def canonical_snapshot(self) -> dict[str, Any]:
        return json.loads(_canonical_json(self.state))

    def collaboration_snapshot(self) -> dict[str, Any]:
        return {
            "canonical": self.canonical_snapshot(),
            "conflicts": [
                {"id": c.conflict_id, "kind": c.kind, "tx_ids": list(c.tx_ids),
                 "loci": list(c.loci), "policy": c.policy}
                for c in self.conflicts
            ],
            "rejections": [r.__dict__ for r in self.rejections],
            "pending": [p.__dict__ for p in self.pending],
            "applied": list(self.applied),
            "resolved_conflicts": list(self.resolved_conflicts),
        }


class CollaborationWorkspace:
    """Disposable local-first semantic transaction model, not production code."""

    def __init__(self, base_state: Mapping[str, Any], *, permission_epochs: Mapping[str, int] | None = None):
        self.base_state = deepcopy(dict(base_state))
        self.permission_epochs = dict(permission_epochs or {})
        self.transactions: dict[str, Transaction] = {}
        self.presence: dict[str, dict[str, Any]] = {}

    def fork(self) -> "CollaborationWorkspace":
        result = CollaborationWorkspace(self.base_state, permission_epochs=self.permission_epochs)
        result.transactions = dict(self.transactions)
        return result

    def set_presence(self, actor: str, state: Mapping[str, Any] | None) -> None:
        if state is None:
            self.presence.pop(actor, None)
        else:
            self.presence[actor] = deepcopy(dict(state))

    def ephemeral_presence(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.presence)

    def add(self, tx: Transaction) -> None:
        validate_transaction(tx)
        old = self.transactions.get(tx.tx_id)
        if old is not None and old != tx:
            raise DuplicateTransactionError(f"transaction id collision for {tx.tx_id}")
        self.transactions[tx.tx_id] = tx

    def sync_from(self, other: "CollaborationWorkspace") -> None:
        if _canonical_json(self.base_state) != _canonical_json(other.base_state):
            raise CollaborationValidationError("cannot sync workspaces with different bases")
        for tx in other.transactions.values():
            self.add(tx)

    def materialize(self) -> Materialization:
        return materialize(self.base_state, self.transactions.values(), permission_epochs=self.permission_epochs)

    def canonical_snapshot(self) -> dict[str, Any]:
        return self.materialize().canonical_snapshot()

    def persisted_collaboration_snapshot(self) -> dict[str, Any]:
        result = self.materialize().collaboration_snapshot()
        result["history"] = sorted(self.transactions)
        return result


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_RUNTIME_KEYS:
                raise CollaborationValidationError(f"runtime multiplayer key {key!r} is not collaboration data at {path}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for i, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{i}]")


def validate_transaction(tx: Transaction) -> None:
    if not tx.tx_id or not tx.actor or not tx.operations:
        raise CollaborationValidationError("transaction id, actor and operations are required")
    if tx.tx_id in tx.deps:
        raise CollaborationValidationError("transaction cannot depend on itself")
    if tx.permission_epoch < 0 or tx.schema_version < 1:
        raise CollaborationValidationError("invalid permission/schema epoch")
    for op in tx.operations:
        if op.kind not in ALLOWED_KINDS:
            raise CollaborationValidationError(f"unknown collaboration operation: {op.kind}")
        if not op.target:
            raise CollaborationValidationError("operation target is required")
        _walk_forbidden(op.data)
        if op.kind == "asset_replace":
            bundle = op.data.get("bundle")
            if not isinstance(bundle, Mapping) or set(bundle) != ASSET_BUNDLE_KEYS:
                raise CollaborationValidationError("asset_replace requires one complete digest/source/audio/provenance bundle")
            for key in ("source", "audio", "provenance"):
                if not isinstance(bundle.get(key), Mapping):
                    raise CollaborationValidationError(f"asset replacement {key} must be an object")


def _op_locus(op: Operation) -> str:
    d = op.data
    if op.kind == "set_property": return f"thing:{op.target}.property:{d.get('key')}"
    if op.kind == "reparent": return f"thing:{op.target}.parent"
    if op.kind == "delete_thing": return f"thing:{op.target}.existence"
    if op.kind == "definition_set": return f"definition:{op.target}.element:{d.get('element')}.field:{d.get('key')}"
    if op.kind == "definition_remove_element": return f"definition:{op.target}.element:{d.get('element')}"
    if op.kind == "instance_overlay": return f"instance:{op.target}.element:{d.get('element')}.field:{d.get('key')}"
    if op.kind in {"create_connection", "delete_connection"}: return f"connection:{op.target}"
    if op.kind == "delete_port": return f"thing:{op.target}.port:{d.get('port')}"
    if op.kind == "set_keyframe": return f"timeline:{d.get('track')}.key:{op.target}.time:{d.get('time')}"
    if op.kind == "group": return f"group:{op.target}"
    if op.kind == "component_update": return f"instance:{op.target}.component-version"
    if op.kind == "asset_rename": return f"asset:{op.target}.label"
    if op.kind == "asset_replace": return f"asset:{op.target}.revision-bundle"
    return f"{op.kind}:{op.target}"


def _connection_uses_port(op: Operation, thing_id: str, port_id: str) -> bool:
    if op.kind != "create_connection": return False
    d = op.data
    return ((d.get("source_thing"), d.get("source_port")) == (thing_id, port_id)
            or (d.get("target_thing"), d.get("target_port")) == (thing_id, port_id))


def _op_conflict(left: Operation, right: Operation) -> tuple[str, str] | None:
    ld, rd = left.data, right.data
    if left.kind == right.kind == "set_property" and left.target == right.target and ld.get("key") == rd.get("key"):
        if ld.get("value") != rd.get("value"): return ("same_property", "hold_both")
    if left.target == right.target:
        if left.kind == "delete_thing" and right.kind != "delete_thing": return ("delete_edit", "left_remove_wins")
        if right.kind == "delete_thing" and left.kind != "delete_thing": return ("delete_edit", "right_remove_wins")
    if left.kind == right.kind == "reparent" and left.target == right.target and ld.get("parent") != rd.get("parent"):
        return ("reparent", "hold_both")
    if left.kind == "definition_remove_element" and right.kind == "instance_overlay" and ld.get("element") == rd.get("element"):
        return ("definition_instance", "hold_both")
    if right.kind == "definition_remove_element" and left.kind == "instance_overlay" and rd.get("element") == ld.get("element"):
        return ("definition_instance", "hold_both")
    if left.kind == "delete_port" and _connection_uses_port(right, left.target, str(ld.get("port"))):
        return ("structure_connection", "hold_both")
    if right.kind == "delete_port" and _connection_uses_port(left, right.target, str(rd.get("port"))):
        return ("structure_connection", "hold_both")
    if left.kind == right.kind == "set_keyframe" and ld.get("track") == rd.get("track"):
        if left.target == right.target or ld.get("time") == rd.get("time"):
            if ld.get("value") != rd.get("value"): return ("timeline_overlap", "hold_both")
    if left.kind == right.kind == "group":
        if set(map(str, ld.get("members", []))) & set(map(str, rd.get("members", []))) and left.target != right.target:
            return ("group_overlap", "hold_both")
    if left.kind == "component_update" and right.kind == "instance_overlay" and left.target == right.target and not ld.get("migration_ok", True):
        return ("component_update_local_edit", "hold_left")
    if right.kind == "component_update" and left.kind == "instance_overlay" and left.target == right.target and not rd.get("migration_ok", True):
        return ("component_update_local_edit", "hold_right")
    if left.kind == "delete_connection" and right.kind == "create_connection" and left.target == right.target:
        return ("connection_remove_recreate", "left_remove_wins")
    if right.kind == "delete_connection" and left.kind == "create_connection" and left.target == right.target:
        return ("connection_remove_recreate", "right_remove_wins")
    if left.kind == right.kind == "asset_replace" and left.target == right.target and _canonical_json(ld.get("bundle")) != _canonical_json(rd.get("bundle")):
        return ("asset_replacement", "hold_both")
    return None


def _topological_order(txs: Mapping[str, Transaction]) -> list[str]:
    remaining = set(txs)
    result: list[str] = []
    while remaining:
        ready = sorted(i for i in remaining if not (txs[i].deps & remaining))
        if not ready:
            raise CollaborationValidationError("transaction dependency cycle")
        result.extend(ready)
        remaining.difference_update(ready)
    return result


def _ancestors(txs: Mapping[str, Transaction]) -> dict[str, set[str]]:
    order = _topological_order(txs)
    out: dict[str, set[str]] = {}
    for tx_id in order:
        acc: set[str] = set()
        for dep in txs[tx_id].deps:
            if dep in txs:
                acc.add(dep); acc.update(out[dep])
        out[tx_id] = acc
    return out


def _availability(state: Mapping[str, Any], tx: Transaction) -> str:
    statuses = state.get("catalog_status", {})
    seen: list[str] = []
    for op in tx.operations:
        if op.kind in {"set_property", "delete_thing", "reparent", "delete_port"}:
            seen.append(str(statuses.get(op.target, "unknown")))
    if "tombstoned" in seen: return "tombstoned"
    if "unknown" in seen: return "unknown"
    if "known_unloaded" in seen: return "known_unloaded"
    return "loaded"


def _thing(state: dict[str, Any], thing_id: str) -> dict[str, Any]:
    if thing_id not in state.get("things", {}):
        raise SemanticPreconditionError(f"unknown Thing {thing_id}")
    return state["things"][thing_id]


def _apply(state: dict[str, Any], op: Operation) -> None:
    d = op.data
    if op.kind == "set_property":
        thing = _thing(state, op.target)
        if thing.get("existence", "present") != "present": raise SemanticPreconditionError("tombstoned Thing")
        props = thing.setdefault("props", {}); key = str(d["key"])
        if "expected" in d and props.get(key) != d.get("expected"): raise SemanticPreconditionError("property precondition")
        props[key] = deepcopy(d.get("value")); return
    if op.kind == "delete_thing":
        thing = _thing(state, op.target); thing["existence"] = "tombstoned"; state.setdefault("catalog_status", {})[op.target] = "tombstoned"; return
    if op.kind == "reparent":
        thing = _thing(state, op.target)
        if "expected_parent" in d and thing.get("parent") != d.get("expected_parent"): raise SemanticPreconditionError("parent precondition")
        thing["parent"] = d.get("parent"); return
    if op.kind == "definition_set":
        element = state["definitions"][op.target]["elements"][str(d["element"])]
        element[str(d["key"])] = deepcopy(d.get("value")); return
    if op.kind == "definition_remove_element":
        del state["definitions"][op.target]["elements"][str(d["element"])]; return
    if op.kind == "instance_overlay":
        instance = state["instances"][op.target]; locus = f"{d['element']}:{d['key']}"
        instance.setdefault("overlays", {})[locus] = deepcopy(d.get("value")); return
    if op.kind == "create_connection":
        state.setdefault("connections", {})[op.target] = {
            "source_thing": str(d["source_thing"]), "source_port": str(d["source_port"]),
            "target_thing": str(d["target_thing"]), "target_port": str(d["target_port"]), "tombstoned": False,
        }; return
    if op.kind == "delete_connection":
        state.setdefault("connections", {}).setdefault(op.target, {})["tombstoned"] = True; return
    if op.kind == "delete_port":
        thing = _thing(state, op.target); port = str(d["port"])
        if port not in thing.get("ports", []): raise SemanticPreconditionError("port missing")
        thing["ports"] = [p for p in thing["ports"] if p != port]; return
    if op.kind == "set_keyframe":
        state.setdefault("keyframes", {})[op.target] = {"track": str(d["track"]), "time": d["time"], "value": deepcopy(d.get("value"))}; return
    if op.kind == "group":
        members = list(map(str, d.get("members", []))); state.setdefault("groups", {})[op.target] = {"members": members}
        for member in members: _thing(state, member)["parent"] = op.target
        return
    if op.kind == "component_update":
        inst = state["instances"][op.target]
        if inst.get("component_version") != d.get("from_version"): raise SemanticPreconditionError("component version precondition")
        if not d.get("migration_ok", True): raise SemanticPreconditionError("component migration failed")
        inst["component_version"] = str(d["to_version"]); return
    if op.kind == "asset_rename":
        asset = state["assets"][op.target]
        if "expected_label" in d and asset.get("label") != d.get("expected_label"): raise SemanticPreconditionError("asset label precondition")
        asset["label"] = str(d["label"]); return
    if op.kind == "asset_replace":
        asset = state["assets"][op.target]
        if "expected_digest" in d and asset.get("revision_bundle", {}).get("digest") != d.get("expected_digest"): raise SemanticPreconditionError("asset digest precondition")
        asset["revision_bundle"] = deepcopy(dict(d["bundle"])); return
    raise SemanticPreconditionError(f"unsupported operation {op.kind}")


def materialize(base_state: Mapping[str, Any], transactions: Iterable[Transaction], *, permission_epochs: Mapping[str, int] | None = None) -> Materialization:
    state = deepcopy(dict(base_state)); permission_epochs = dict(permission_epochs or {})
    txs: dict[str, Transaction] = {}
    for tx in transactions:
        validate_transaction(tx)
        if tx.tx_id in txs and txs[tx.tx_id] != tx: raise DuplicateTransactionError(f"transaction id collision for {tx.tx_id}")
        txs[tx.tx_id] = tx
    order = _topological_order(txs); ancestry = _ancestors(txs)
    schema = int(state.get("schema_version", 1)); invalid: set[str] = set(); rejections: list[Rejection] = []
    for tx in txs.values():
        if tx.permission_epoch != permission_epochs.get(tx.actor, tx.permission_epoch):
            invalid.add(tx.tx_id); rejections.append(Rejection(tx.tx_id, "permission_epoch_changed"))
        elif tx.schema_version != schema:
            invalid.add(tx.tx_id); rejections.append(Rejection(tx.tx_id, "schema_migration_required"))
    missing = {i for i, tx in txs.items() if set(tx.deps) - set(txs)}

    conflicts: dict[str, Conflict] = {}; held: set[str] = set()
    ids = sorted(txs)
    for n, left_id in enumerate(ids):
        if left_id in invalid: continue
        for right_id in ids[n + 1:]:
            if right_id in invalid: continue
            if left_id in ancestry[right_id] or right_id in ancestry[left_id]: continue
            left, right = txs[left_id], txs[right_id]
            for lop in left.operations:
                for rop in right.operations:
                    found = _op_conflict(lop, rop)
                    if not found: continue
                    kind, policy = found; pair = tuple(sorted((left_id, right_id))); cid = f"conflict:{kind}:{pair[0]}:{pair[1]}"
                    loci = tuple(sorted({_op_locus(lop), _op_locus(rop)})); conflicts[cid] = Conflict(cid, kind, pair, loci, policy)
                    if policy == "hold_both": held.update(pair)
                    elif policy == "left_remove_wins": held.add(right_id)
                    elif policy == "right_remove_wins": held.add(left_id)
                    elif policy == "hold_left": held.add(left_id)
                    elif policy == "hold_right": held.add(right_id)

    resolved: set[str] = set()
    for tx in txs.values():
        for cid, conflict in conflicts.items():
            if tx.resolves and set(conflict.tx_ids).issubset(tx.resolves) and set(conflict.tx_ids).issubset(tx.deps): resolved.add(cid)
    unresolved = {cid: c for cid, c in conflicts.items() if cid not in resolved}

    pending: list[Pending] = []; applied: list[str] = []; applied_set: set[str] = set()
    for tx_id in order:
        tx = txs[tx_id]
        if tx_id in invalid: continue
        if tx_id in missing: pending.append(Pending(tx_id, "missing_causal_dependency")); continue
        # Transaction atomicity dominates a pairwise remove-wins preference: a tx
        # held by any other conflict never partially materializes.
        if tx_id in held: continue
        unavailable = set(tx.deps) - applied_set
        unavailable -= unavailable & set(tx.resolves)
        if unavailable: pending.append(Pending(tx_id, "blocked_by_unapplied_dependency")); continue
        availability = _availability(state, tx)
        if availability == "known_unloaded": pending.append(Pending(tx_id, "known_unloaded_target")); continue
        if availability in {"tombstoned", "unknown"}:
            cid = f"conflict:target_{availability}:{tx_id}"; unresolved[cid] = Conflict(cid, f"target_{availability}", (tx_id,), tuple(sorted(_op_locus(o) for o in tx.operations)), "hold_transaction"); continue
        candidate = deepcopy(state)
        try:
            for op in tx.operations: _apply(candidate, op)
        except (KeyError, SemanticPreconditionError):
            cid = f"conflict:precondition:{tx_id}"; unresolved[cid] = Conflict(cid, "precondition_failed", (tx_id,), tuple(sorted(_op_locus(o) for o in tx.operations)), "hold_transaction"); continue
        state = candidate; applied.append(tx_id); applied_set.add(tx_id)

    return Materialization(
        state=state,
        conflicts=tuple(unresolved[k] for k in sorted(unresolved)),
        rejections=tuple(sorted(rejections, key=lambda r: r.tx_id)),
        pending=tuple(sorted(pending, key=lambda p: (p.tx_id, p.reason))),
        applied=tuple(applied),
        resolved_conflicts=tuple(sorted(resolved)),
    )
