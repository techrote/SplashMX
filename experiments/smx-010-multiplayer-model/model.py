from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


class NetworkSemanticError(ValueError):
    """Base error for rejected network-semantic operations."""


class CanonicalNetworkLeak(NetworkSemanticError):
    pass


class AuthorityViolation(NetworkSemanticError):
    pass


class ReplayRejected(NetworkSemanticError):
    pass


class CapabilityDenied(NetworkSemanticError):
    pass


class QueueBudgetExceeded(NetworkSemanticError):
    pass


class ReferenceUnavailable(NetworkSemanticError):
    pass


FORBIDDEN_CANONICAL_NETWORK_KEYS = frozenset(
    {
        "peer_id",
        "connection_id",
        "socket",
        "rpc",
        "rpc_id",
        "node_path",
        "multiplayer_authority",
        "websocket",
        "webrtc",
        "enet",
        "udp",
        "host_handle",
        "session_token",
        "capability_grant",
    }
)


@dataclass(frozen=True)
class ReplicationField:
    name: str
    lane: str = "state"
    delivery: str = "latest"
    visibility: str = "relevant"


@dataclass(frozen=True)
class NetworkDeclaration:
    replicated_fields: tuple[ReplicationField, ...] = ()
    accepts_inputs: tuple[str, ...] = ()
    emits_events: tuple[str, ...] = ()
    authority_mode: str = "runtime_policy"
    relevance_mode: str = "runtime_policy"

    def as_dict(self) -> dict[str, Any]:
        return {
            "replicated_fields": [
                {
                    "name": item.name,
                    "lane": item.lane,
                    "delivery": item.delivery,
                    "visibility": item.visibility,
                }
                for item in self.replicated_fields
            ],
            "accepts_inputs": list(self.accepts_inputs),
            "emits_events": list(self.emits_events),
            "authority_mode": self.authority_mode,
            "relevance_mode": self.relevance_mode,
        }


@dataclass(frozen=True)
class ThingRecord:
    thing_id: str
    parent_id: str | None
    initial_state: Mapping[str, Any]
    network: NetworkDeclaration = NetworkDeclaration()


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    digest: str
    source: Mapping[str, Any]
    provenance: Mapping[str, Any]
    audio: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalCreation:
    revision_id: str
    things: tuple[ThingRecord, ...]
    assets: tuple[AssetRecord, ...] = ()

    def projection(self) -> dict[str, Any]:
        result = {
            "revision_id": self.revision_id,
            "things": [
                {
                    "thing_id": item.thing_id,
                    "parent_id": item.parent_id,
                    "initial_state": dict(item.initial_state),
                    "network": item.network.as_dict(),
                }
                for item in self.things
            ],
            "assets": [
                {
                    "asset_id": item.asset_id,
                    "digest": item.digest,
                    "source": dict(item.source),
                    "provenance": dict(item.provenance),
                    "audio": dict(item.audio),
                }
                for item in self.assets
            ],
        }
        reject_transport_leaks(result)
        return result

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.projection(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return sha256(payload).hexdigest()


@dataclass(frozen=True)
class TopologyPolicy:
    name: str
    authority_default: str
    transport: str | None
    trusted_server: bool
    host_migration: bool

    @staticmethod
    def offline() -> "TopologyPolicy":
        return TopologyPolicy("offline", "local", None, True, False)

    @staticmethod
    def peer_hosted(transport: str = "webrtc") -> "TopologyPolicy":
        return TopologyPolicy("peer_hosted", "host", transport, False, True)

    @staticmethod
    def authoritative(transport: str = "websocket") -> "TopologyPolicy":
        return TopologyPolicy("authoritative", "server", transport, True, False)


@dataclass
class RuntimeThing:
    thing_id: str
    parent_id: str | None
    state: dict[str, Any]
    network: NetworkDeclaration
    existence: str = "present"
    residency: str = "resident"
    controller_principal: str | None = None
    authority_principal: str = "local"
    authority_epoch: int = 1


@dataclass(frozen=True)
class InputMessage:
    thing_id: str
    input_name: str
    value: Any
    sender_principal: str
    sequence: int
    authority_epoch: int


@dataclass(frozen=True)
class StateUpdate:
    thing_id: str
    field: str
    value: Any
    authority_principal: str
    authority_epoch: int
    sequence: int


@dataclass(frozen=True)
class EventMessage:
    thing_id: str
    event_name: str
    payload: Any
    event_id: str
    authority_principal: str
    authority_epoch: int


@dataclass
class PeerContext:
    principal_id: str
    peer_id: int | str
    relevant_things: set[str] = field(default_factory=set)


class RuntimeSession:
    """Disposable topology-independent semantic model.

    Transport, peer IDs and capability handles are runtime context only.
    """

    def __init__(
        self,
        creation: CanonicalCreation,
        policy: TopologyPolicy,
        *,
        multiplayer_capability: bool = True,
        max_pending_per_thing: int = 8,
    ):
        self.creation = creation
        self.canonical_digest = creation.digest
        self.policy = policy
        self.max_pending_per_thing = max_pending_per_thing
        if policy.name != "offline" and not multiplayer_capability:
            raise CapabilityDenied("multiplayer.session capability is required")
        self.things = {
            record.thing_id: RuntimeThing(
                record.thing_id,
                record.parent_id,
                dict(record.initial_state),
                record.network,
                authority_principal=policy.authority_default,
            )
            for record in creation.things
        }
        self.peers: dict[str, PeerContext] = {}
        self.last_input_sequence: dict[tuple[str, str], int] = {}
        self.last_state_sequence: dict[tuple[str, str], int] = {}
        self.seen_event_ids: set[str] = set()
        self.delivered_events: list[str] = []
        self.pending_for_unloaded: dict[str, list[StateUpdate | EventMessage]] = {}

    def attach_peer(self, principal_id: str, peer_id: int | str) -> None:
        self.peers[principal_id] = PeerContext(principal_id, peer_id)

    def detach_peer(self, principal_id: str) -> None:
        self.peers.pop(principal_id, None)

    def reattach_peer(self, principal_id: str, new_peer_id: int | str) -> None:
        """Reconnect rebinds transport identity without changing user/Thing semantics."""
        old_relevance = set(
            self.peers.get(principal_id, PeerContext(principal_id, -1)).relevant_things
        )
        self.peers[principal_id] = PeerContext(principal_id, new_peer_id, old_relevance)

    def set_relevance(self, principal_id: str, thing_ids: set[str]) -> None:
        peer = self.peers[principal_id]
        unknown = thing_ids - self.things.keys()
        if unknown:
            raise ReferenceUnavailable(f"unknown relevance target(s): {sorted(unknown)}")
        peer.relevant_things = set(thing_ids)

    def set_controller(self, thing_id: str, principal_id: str | None) -> None:
        self.things[thing_id].controller_principal = principal_id

    def transfer_authority(self, thing_id: str, new_authority: str) -> int:
        thing = self.things[thing_id]
        thing.authority_principal = new_authority
        thing.authority_epoch += 1
        self._purge_stale_pending(thing_id, thing.authority_epoch)
        return thing.authority_epoch

    def reparent(self, thing_id: str, new_parent: str | None) -> None:
        """Containment mutation changes containment only."""
        self.things[thing_id].parent_id = new_parent

    def unload(self, thing_id: str) -> None:
        thing = self.things[thing_id]
        if thing.existence != "present":
            raise ReferenceUnavailable("cannot unload a tombstoned Thing")
        thing.residency = "known_unloaded"

    def restore(self, thing_id: str) -> None:
        thing = self.things[thing_id]
        if thing.existence != "present":
            raise ReferenceUnavailable("cannot restore a tombstoned Thing")
        thing.residency = "resident"
        pending = self.pending_for_unloaded.pop(thing_id, [])
        for message in pending:
            if isinstance(message, StateUpdate):
                key = (message.thing_id, message.field)
                self.last_state_sequence[key] = message.sequence
                thing.state[message.field] = message.value
            else:
                self.delivered_events.append(message.event_id)

    def tombstone(self, thing_id: str) -> None:
        thing = self.things[thing_id]
        thing.existence = "tombstoned"
        thing.residency = "unavailable"
        self.pending_for_unloaded.pop(thing_id, None)

    def receive_input(self, message: InputMessage) -> None:
        thing = self._present(message.thing_id)
        if message.input_name not in thing.network.accepts_inputs:
            raise AuthorityViolation("input not declared by Thing")
        if message.authority_epoch != thing.authority_epoch:
            raise ReplayRejected("stale authority epoch")
        if thing.controller_principal != message.sender_principal:
            raise AuthorityViolation("sender does not control Thing")
        key = (message.sender_principal, message.thing_id)
        if message.sequence <= self.last_input_sequence.get(key, -1):
            raise ReplayRejected("duplicate or stale input sequence")
        self.last_input_sequence[key] = message.sequence

    def authoritative_state_update(
        self,
        thing_id: str,
        field: str,
        value: Any,
        *,
        sender_principal: str,
        sequence: int,
    ) -> StateUpdate:
        thing = self._present(thing_id)
        if sender_principal != thing.authority_principal:
            raise AuthorityViolation("only current simulation authority may author state")
        update = StateUpdate(
            thing_id,
            field,
            value,
            sender_principal,
            thing.authority_epoch,
            sequence,
        )
        self.receive_state(update)
        return update

    def receive_state(self, update: StateUpdate) -> None:
        thing = self._present(update.thing_id)
        if update.authority_epoch != thing.authority_epoch:
            raise ReplayRejected("stale authority epoch")
        if update.authority_principal != thing.authority_principal:
            raise AuthorityViolation("state update is not from current authority")
        declared = {
            field.name: field
            for field in thing.network.replicated_fields
            if field.lane == "state"
        }
        if update.field not in declared:
            raise AuthorityViolation("field is not declared for state replication")
        key = (update.thing_id, update.field)
        if update.sequence <= self.last_state_sequence.get(key, -1):
            raise ReplayRejected("duplicate or stale state sequence")
        if thing.residency != "resident":
            self._queue_unloaded(update.thing_id, update)
            self.last_state_sequence[key] = update.sequence
            return
        self.last_state_sequence[key] = update.sequence
        thing.state[update.field] = update.value

    def receive_event(self, event: EventMessage) -> bool:
        thing = self._present(event.thing_id)
        if event.authority_epoch != thing.authority_epoch:
            raise ReplayRejected("stale authority epoch")
        if event.authority_principal != thing.authority_principal:
            raise AuthorityViolation("event is not from current authority")
        if event.event_name not in thing.network.emits_events:
            raise AuthorityViolation("event is not declared")
        if event.event_id in self.seen_event_ids:
            return False
        if thing.residency != "resident":
            self._queue_unloaded(event.thing_id, event)
            self.seen_event_ids.add(event.event_id)
            return True
        self.seen_event_ids.add(event.event_id)
        self.delivered_events.append(event.event_id)
        return True

    def migrate_peer_host(self, old_host: str, new_host: str) -> None:
        if self.policy.name != "peer_hosted" or not self.policy.host_migration:
            raise AuthorityViolation("host migration is not enabled for this topology")
        for thing in self.things.values():
            if thing.authority_principal == old_host:
                thing.authority_principal = new_host
                thing.authority_epoch += 1
                self._purge_stale_pending(thing.thing_id, thing.authority_epoch)

    def semantic_snapshot(self) -> dict[str, Any]:
        return {
            "revision_id": self.creation.revision_id,
            "canonical_digest": self.canonical_digest,
            "things": {
                thing_id: {
                    "state": dict(thing.state),
                    "parent_id": thing.parent_id,
                    "existence": thing.existence,
                    "residency": thing.residency,
                }
                for thing_id, thing in sorted(self.things.items())
            },
        }

    def _queue_unloaded(self, thing_id: str, message: StateUpdate | EventMessage) -> None:
        queue = self.pending_for_unloaded.setdefault(thing_id, [])
        if isinstance(message, StateUpdate):
            # Latest-state semantics supersede the prior queued value before capacity is
            # evaluated, so a one-slot budget can still accept arbitrarily newer samples
            # of the same state locus without becoming an accidental denial of service.
            queue[:] = [
                item
                for item in queue
                if not (
                    isinstance(item, StateUpdate)
                    and item.field == message.field
                    and item.authority_epoch == message.authority_epoch
                )
            ]
        if len(queue) >= self.max_pending_per_thing:
            raise QueueBudgetExceeded("pending network delivery budget exceeded")
        queue.append(message)

    def _purge_stale_pending(self, thing_id: str, authority_epoch: int) -> None:
        queue = self.pending_for_unloaded.get(thing_id)
        if queue is None:
            return
        queue[:] = [item for item in queue if item.authority_epoch == authority_epoch]
        if not queue:
            self.pending_for_unloaded.pop(thing_id, None)

    def _present(self, thing_id: str) -> RuntimeThing:
        try:
            thing = self.things[thing_id]
        except KeyError as exc:
            raise ReferenceUnavailable("unknown Thing") from exc
        if thing.existence != "present":
            raise ReferenceUnavailable("Thing is tombstoned")
        return thing


def reject_transport_leaks(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_CANONICAL_NETWORK_KEYS:
                raise CanonicalNetworkLeak(
                    f"transport/runtime network key {key!r} leaked into canonical data at {path}"
                )
            reject_transport_leaks(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            reject_transport_leaks(child, path=f"{path}[{index}]")
