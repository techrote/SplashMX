"""Deterministic semantic oracle for the SMX-017 real topology harness.

This is deliberately not a transport simulator.  It encodes the accepted SMX-010
semantic rules so the real Godot/browser observations can be checked against a
small, deterministic oracle without making WebSocket/Godot details canonical.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


MAX_MESSAGE_BYTES = 8192
FORBIDDEN_WIRE_KEYS = {
    "capability_grant",
    "capability_token",
    "host_handle",
    "godot_node",
    "node_path",
    "resource_uid",
    "socket",
}


class Rejected(ValueError):
    pass


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(k in FORBIDDEN_WIRE_KEYS or _contains_forbidden(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(v) for v in value)
    return False


@dataclass
class Replica:
    principal: str
    transport_peer: str
    topology: str
    authority_principal: str
    authority_epoch: int = 1
    controller: str = "alice"
    containment_parent: str = "world"
    avatar_x: int = 0
    door_open: bool = False
    state_watermark: int = 0
    input_watermarks: dict[str, int] = field(default_factory=dict)
    seen_events: set[str] = field(default_factory=set)
    relevance: dict[str, bool] = field(default_factory=lambda: {"avatar:alice": True, "door": True})
    lifecycle: dict[str, str] = field(default_factory=lambda: {"avatar:alice": "active", "door": "active"})
    pending_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_events: list[dict[str, Any]] = field(default_factory=list)

    def reconnect(self, new_transport_peer: str) -> None:
        if new_transport_peer == self.transport_peer:
            raise Rejected("reconnect must bind a new transient transport peer")
        self.transport_peer = new_transport_peer

    def accept_input(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self._validate_envelope(envelope)
        if envelope.get("type") != "input":
            raise Rejected("authority accepts declared input intent, not remote state assertion")
        if envelope.get("sender_principal") != self.controller:
            raise Rejected("sender is not controller")
        if envelope.get("authority_epoch") != self.authority_epoch:
            raise Rejected("stale or future authority epoch")
        kind = envelope.get("kind")
        if kind not in {"move", "open_door"}:
            raise Rejected("undeclared input kind")
        seq = envelope.get("input_seq")
        if not isinstance(seq, int) or seq <= self.input_watermarks.get(self.controller, 0):
            raise Rejected("duplicate/reordered input")
        self.input_watermarks[self.controller] = seq
        if kind == "move":
            dx = envelope.get("dx")
            if not isinstance(dx, int) or abs(dx) > 4:
                raise Rejected("movement outside declared input bound")
            self.avatar_x += dx
        else:
            self.door_open = True
        self.state_watermark += 1
        return self.snapshot_message()

    def receive_state(self, envelope: dict[str, Any]) -> None:
        self._validate_envelope(envelope)
        if envelope.get("type") != "state":
            raise Rejected("not a state message")
        if envelope.get("sender_principal") != self.authority_principal:
            raise Rejected("state sender is not authority")
        if envelope.get("authority_epoch") != self.authority_epoch:
            raise Rejected("stale or future authority epoch")
        seq = envelope.get("state_seq")
        if not isinstance(seq, int) or seq <= self.state_watermark:
            raise Rejected("stale state")
        target = envelope.get("target")
        if target not in self.relevance:
            raise Rejected("unknown target")
        payload = deepcopy(envelope.get("payload", {}))
        self.state_watermark = seq
        if not self.relevance[target] or self.lifecycle[target] == "known_unloaded":
            self.pending_state[target] = payload
            return
        self._apply_state(target, payload)

    def receive_event(self, envelope: dict[str, Any]) -> None:
        self._validate_envelope(envelope)
        if envelope.get("type") != "event":
            raise Rejected("not an event")
        if envelope.get("sender_principal") != self.authority_principal:
            raise Rejected("event sender is not authority")
        if envelope.get("authority_epoch") != self.authority_epoch:
            raise Rejected("stale event epoch")
        event_id = envelope.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise Rejected("event id required")
        if event_id in self.seen_events:
            return
        self.seen_events.add(event_id)
        target = envelope.get("target")
        if target not in self.lifecycle:
            raise Rejected("unknown target")
        if self.lifecycle[target] == "tombstoned":
            raise Rejected("event targets tombstone")
        if self.lifecycle[target] == "known_unloaded" or not self.relevance[target]:
            self.pending_events.append(deepcopy(envelope))
            return
        self._apply_event(envelope)

    def set_relevance(self, thing_id: str, relevant: bool) -> None:
        if thing_id not in self.relevance:
            raise Rejected("unknown target")
        self.relevance[thing_id] = relevant
        if relevant and self.lifecycle[thing_id] == "active":
            self._flush(thing_id)

    def unload(self, thing_id: str) -> None:
        if self.lifecycle.get(thing_id) != "active":
            raise Rejected("only active Thing can unload")
        self.lifecycle[thing_id] = "known_unloaded"

    def restore(self, thing_id: str) -> None:
        if self.lifecycle.get(thing_id) != "known_unloaded":
            raise Rejected("restore requires known_unloaded")
        self.lifecycle[thing_id] = "active"
        if self.relevance[thing_id]:
            self._flush(thing_id)

    def tombstone(self, thing_id: str) -> None:
        if thing_id not in self.lifecycle:
            raise Rejected("unknown target")
        self.lifecycle[thing_id] = "tombstoned"
        self.pending_state.pop(thing_id, None)
        self.pending_events = [e for e in self.pending_events if e.get("target") != thing_id]

    def transfer_control(self, principal: str) -> None:
        self.controller = principal

    def transfer_authority(self, principal: str, *, checkpoint_confirmed: bool) -> None:
        if not checkpoint_confirmed:
            raise Rejected("authority transfer requires confirmed checkpoint")
        if principal == self.authority_principal:
            raise Rejected("authority transfer requires a new authority")
        self.authority_principal = principal
        self.authority_epoch += 1

    def snapshot_message(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "authority_epoch": self.authority_epoch,
            "state_seq": self.state_watermark,
            "avatar_x": self.avatar_x,
            "door_open": self.door_open,
            "controller": self.controller,
            "containment_parent": self.containment_parent,
        }

    def semantic_snapshot(self) -> dict[str, Any]:
        return {
            "avatar_x": self.avatar_x,
            "door_open": self.door_open,
            "controller": self.controller,
            "containment_parent": self.containment_parent,
            "authority_epoch": self.authority_epoch,
            "lifecycle": deepcopy(self.lifecycle),
        }

    def _validate_envelope(self, envelope: dict[str, Any]) -> None:
        if _contains_forbidden(envelope):
            raise Rejected("wire message attempts host/capability authority injection")
        encoded = repr(envelope).encode("utf-8")
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise Rejected("message exceeds semantic ingress budget")

    def _apply_state(self, target: str, payload: dict[str, Any]) -> None:
        if target == "avatar:alice" and set(payload) == {"position_x"}:
            self.avatar_x = int(payload["position_x"])
        elif target == "door" and set(payload) == {"open"}:
            self.door_open = bool(payload["open"])
        else:
            raise Rejected("undeclared state locus")

    def _apply_event(self, envelope: dict[str, Any]) -> None:
        if envelope.get("target") != "door" or envelope.get("kind") != "door_opened":
            raise Rejected("undeclared event")
        self.door_open = True

    def _flush(self, thing_id: str) -> None:
        if thing_id in self.pending_state:
            payload = self.pending_state.pop(thing_id)
            self._apply_state(thing_id, payload)
        keep: list[dict[str, Any]] = []
        for event in self.pending_events:
            if event.get("target") == thing_id:
                self._apply_event(event)
            else:
                keep.append(event)
        self.pending_events = keep


def assert_protected_bundle_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Protected asset revisions are alternatives, never field-merge inputs."""
    keys = {
        "asset_id",
        "digest",
        "source_identity",
        "source_metadata",
        "audio_media_semantics",
        "provenance",
        "licence",
        "derivation",
    }
    if set(before) != keys or set(after) != keys or before != after:
        raise Rejected("protected source/audio/provenance revision changed or was field-mixed")
