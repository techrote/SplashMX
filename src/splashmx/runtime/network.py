"""Production runtime networking semantics and adapter boundary for SMX-046.

Authenticated principals, runtime sessions, transient transports and durable Thing
identity remain role-distinct. Physical WebRTC/WSS adapters terminate below this
module; hostile ingress is admitted only after semantic boundary validation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

MAX_TICKET_BYTES = 4096
MAX_SIGNAL_BYTES = 65536
MAX_MESSAGE_BYTES = 65536
MAX_MESSAGES_PER_TICK = 64
MAX_PENDING_EVENTS_PER_THING = 128
MAX_DEDUP_IDS_PER_SENDER = 512
MAX_SESSIONS = 4096
MAX_THINGS = 100000
MAX_SEQUENCE_GAP = 4096
MAX_TICKET_TTL_SECONDS = 300

PROTECTED_ASSET_FIELDS = (
    "revision_digest", "source_digest", "source_identity", "source_metadata",
    "media_semantics", "provenance", "licence_attribution", "derivation_lineage",
)

FORBIDDEN_REMOTE_AUTHORITY_KEYS = frozenset({
    "capability", "capability_grant", "capability_id", "host_handle", "node_path",
    "rid", "resource_uid", "resource_path", "socket_id", "connection_handle",
    "process_handle", "godot_peer_id", "peer_id", "javascript_handle",
    "filesystem_handle", "raw_network_handle", "transport_id", "session_id",
})
FORBIDDEN_SIGNAL_KEYS = (FORBIDDEN_REMOTE_AUTHORITY_KEYS - {"session_id", "transport_id"}) | frozenset({"principal_id", "thing_id", "authority_epoch"})


class RuntimeOutcome(str, Enum):
    AUTH_REQUIRED = "network.auth_required"
    AUTH_EXPIRED = "network.auth_expired"
    AUTH_REJECTED = "network.auth_rejected"
    TLS_FAILED = "network.tls_failed"
    SIGNAL_UNAVAILABLE = "network.signalling_unavailable"
    SIGNAL_OVERSIZE = "network.signalling_oversize"
    ICE_NO_CANDIDATE = "network.ice_no_candidate"
    TURN_UNAVAILABLE = "network.turn_unavailable"
    TRANSPORT_UNAVAILABLE = "network.transport_unavailable"
    TRANSPORT_FALLBACK = "network.transport_fallback"
    SUSPENDED = "network.suspended"
    RECONNECT_REQUIRED = "network.reconnect_required"
    RECONNECT_FAILED = "network.reconnect_failed"
    SERVER_UNAVAILABLE = "network.server_unavailable"
    AUTHORITY_LOST = "network.authority_lost"
    MESSAGE_OVERSIZE = "network.message_oversize"
    SENDER_REJECTED = "network.sender_rejected"
    STALE_EPOCH = "network.stale_epoch"
    REPLAY = "network.replay"
    REORDERED = "network.reordered"
    RATE_LIMITED = "network.rate_limited"
    QUEUE_FULL = "network.queue_full"
    TARGET_UNKNOWN = "network.target_unknown"
    TARGET_TOMBSTONED = "network.target_tombstoned"
    AUTHORITY_REJECTED = "network.authority_rejected"
    CONTROLLER_REJECTED = "network.controller_rejected"
    LOCUS_REJECTED = "network.locus_rejected"
    CHECKPOINT_UNCONFIRMED = "network.checkpoint_unconfirmed"
    MIGRATION_UNSUPPORTED = "network.migration_unsupported"
    DEPENDENCY_UNAVAILABLE = "network.dependency_unavailable"


class Topology(str, Enum):
    OFFLINE = "offline"
    PEER_HOSTED = "peer_hosted"
    DEDICATED_AUTHORITATIVE = "dedicated_authoritative"


class TransportPath(str, Enum):
    LOCAL = "local"
    WEBRTC_DIRECT = "webrtc_datachannel_direct"
    WEBRTC_TURN = "webrtc_datachannel_turn"
    WSS_PEER_RELAY = "wss_peer_relay"
    WSS_DEDICATED = "wss_dedicated_authority"


class MessageClass(str, Enum):
    INPUT = "input"
    STATE = "state"
    EVENT = "event"
    BASELINE = "baseline"


class Residency(str, Enum):
    RESIDENT = "resident"
    KNOWN_UNLOADED = "known_unloaded"
    TOMBSTONED = "tombstoned"


class NetworkError(ValueError):
    def __init__(self, outcome: RuntimeOutcome, message: str):
        super().__init__(message)
        self.outcome = outcome


@dataclass(frozen=True)
class SessionIdentity:
    principal_id: str
    session_id: str
    room_id: str
    expires_at: int


@dataclass(frozen=True)
class TransportBinding:
    session: SessionIdentity
    transport_id: str
    path: TransportPath
    generation: int = 1


@dataclass(frozen=True)
class TransportDecision:
    path: TransportPath | None
    outcome: RuntimeOutcome | None
    diagnostics: tuple[RuntimeOutcome, ...] = ()


@dataclass(frozen=True)
class NetworkDeclaration:
    input_kinds: frozenset[str] = frozenset()
    state_loci: frozenset[str] = frozenset()
    event_kinds: frozenset[str] = frozenset()
    input_numeric_bounds: Mapping[str, Mapping[str, tuple[float, float]]] = field(default_factory=dict)


@dataclass(frozen=True)
class NetworkEnvelope:
    message_id: str
    message_class: MessageClass
    sender_session_id: str
    authority_epoch: int
    sequence: int
    target_thing_id: str
    locus: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    outcome: RuntimeOutcome | None = None
    target_thing_id: str | None = None
    message_id: str | None = None


@dataclass
class ThingNetworkState:
    thing_id: str
    declaration: NetworkDeclaration
    authority_session_id: str
    authority_epoch: int
    controller_principal_id: str | None
    residency: Residency = Residency.RESIDENT
    replicated_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorityCheckpoint:
    """Portable semantic checkpoint containing no transport/session handle."""
    scope: tuple[str, ...]
    source_epoch: int
    confirmed: bool
    replicated_state: Mapping[str, Mapping[str, Any]]
    state_watermarks: Mapping[str, Mapping[str, int]]
    protected_assets: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_serializable(self) -> dict[str, Any]:
        return {
            "scope": list(self.scope), "source_epoch": self.source_epoch, "confirmed": self.confirmed,
            "replicated_state": deepcopy(dict(self.replicated_state)),
            "state_watermarks": deepcopy(dict(self.state_watermarks)),
            "protected_assets": deepcopy(dict(self.protected_assets)),
        }


@dataclass(frozen=True)
class _TicketRecord:
    session: SessionIdentity
    audience: str
    expires_at: int


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def verify_pkce_s256(code_verifier: str, expected_challenge: str) -> bool:
    if not 43 <= len(code_verifier) <= 128:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    if any(ch not in allowed for ch in code_verifier):
        return False
    actual = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    return secrets.compare_digest(actual, expected_challenge)


class OpaqueJoinTicketAuthority:
    """Single-use room/audience-scoped post-login runtime admission."""
    def __init__(self, *, max_outstanding: int = MAX_SESSIONS):
        if max_outstanding < 1:
            raise ValueError("max_outstanding must be positive")
        self._max_outstanding = max_outstanding
        self._tickets: dict[str, _TicketRecord] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def issue(self, session: SessionIdentity, *, audience: str, now: int, ttl_seconds: int = 60) -> str:
        if not 1 <= ttl_seconds <= MAX_TICKET_TTL_SECONDS:
            raise ValueError("runtime join ticket ttl outside bounded policy")
        if session.expires_at <= now:
            raise NetworkError(RuntimeOutcome.AUTH_EXPIRED, "runtime session expired")
        self.purge(now=now)
        if len(self._tickets) >= self._max_outstanding:
            raise NetworkError(RuntimeOutcome.RATE_LIMITED, "runtime join ticket capacity exhausted")
        token = secrets.token_urlsafe(32)
        if len(token.encode("ascii")) > MAX_TICKET_BYTES:
            raise AssertionError("generated ticket exceeded configured bound")
        self._tickets[self._digest(token)] = _TicketRecord(session, audience, min(now + ttl_seconds, session.expires_at))
        return token

    def redeem(self, token: str, *, audience: str, room_id: str, now: int) -> SessionIdentity:
        try:
            encoded = token.encode("ascii")
        except UnicodeEncodeError as exc:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "runtime join ticket malformed") from exc
        if not encoded or len(encoded) > MAX_TICKET_BYTES:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "runtime join ticket malformed")
        record = self._tickets.pop(self._digest(token), None)
        if record is None:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "runtime join ticket invalid or replayed")
        if now >= record.expires_at or now >= record.session.expires_at:
            raise NetworkError(RuntimeOutcome.AUTH_EXPIRED, "runtime join ticket expired")
        if record.audience != audience or record.session.room_id != room_id:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "runtime join ticket scope mismatch")
        return record.session

    def purge(self, *, now: int) -> int:
        stale = [digest for digest, rec in self._tickets.items() if now >= rec.expires_at]
        for digest in stale:
            del self._tickets[digest]
        return len(stale)


def _walk_forbidden(value: Any, forbidden: frozenset[str], *, depth: int = 0) -> None:
    if depth > 32:
        raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "serialized authority nesting exceeds bound")
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in forbidden:
                raise NetworkError(RuntimeOutcome.AUTH_REJECTED, f"forbidden remote authority field: {key_text}")
            _walk_forbidden(child, forbidden, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _walk_forbidden(child, forbidden, depth=depth + 1)


def validate_signalling_envelope(message: Mapping[str, Any]) -> dict[str, Any]:
    blob = canonical_json(message)
    if len(blob) > MAX_SIGNAL_BYTES:
        raise NetworkError(RuntimeOutcome.SIGNAL_OVERSIZE, "signalling envelope exceeds byte bound")
    allowed = {"kind", "session_id", "transport_id", "offer", "answer", "candidate", "ice_restart"}
    unknown = set(message) - allowed
    if unknown:
        raise NetworkError(RuntimeOutcome.AUTH_REJECTED, f"unknown signalling fields: {sorted(unknown)}")
    _walk_forbidden(message, FORBIDDEN_SIGNAL_KEYS)
    if message.get("kind") not in {"offer", "answer", "ice_candidate", "ice_restart"}:
        raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "unsupported signalling kind")
    if not isinstance(message.get("session_id"), str) or not isinstance(message.get("transport_id"), str):
        raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "signalling identity fields malformed")
    return deepcopy(dict(message))


def select_peer_path(*, tls_ok: bool, signalling_ok: bool, webrtc_available: bool, ice_direct_ok: bool, turn_ok: bool, wss_relay_ok: bool) -> TransportDecision:
    if not tls_ok:
        return TransportDecision(None, RuntimeOutcome.TLS_FAILED)
    if not signalling_ok:
        return TransportDecision(None, RuntimeOutcome.SIGNAL_UNAVAILABLE)
    if webrtc_available and ice_direct_ok:
        return TransportDecision(TransportPath.WEBRTC_DIRECT, None)
    if webrtc_available and turn_ok:
        return TransportDecision(TransportPath.WEBRTC_TURN, None)
    if wss_relay_ok:
        diagnostics = (RuntimeOutcome.TURN_UNAVAILABLE, RuntimeOutcome.TRANSPORT_FALLBACK) if webrtc_available else (RuntimeOutcome.TRANSPORT_FALLBACK,)
        return TransportDecision(TransportPath.WSS_PEER_RELAY, None, diagnostics)
    return TransportDecision(None, RuntimeOutcome.ICE_NO_CANDIDATE if webrtc_available else RuntimeOutcome.TRANSPORT_UNAVAILABLE)


def select_dedicated_path(*, tls_ok: bool, server_ok: bool, wss_ok: bool) -> TransportDecision:
    if not tls_ok:
        return TransportDecision(None, RuntimeOutcome.TLS_FAILED)
    if not server_ok:
        return TransportDecision(None, RuntimeOutcome.SERVER_UNAVAILABLE)
    if not wss_ok:
        return TransportDecision(None, RuntimeOutcome.TRANSPORT_UNAVAILABLE)
    return TransportDecision(TransportPath.WSS_DEDICATED, None)


def validate_protected_asset_revision(revision: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in PROTECTED_ASSET_FIELDS if field not in revision]
    if missing:
        raise NetworkError(RuntimeOutcome.AUTH_REJECTED, f"incomplete protected asset revision: {missing}")
    return deepcopy(dict(revision))


class ProductionTransportService:
    """Authenticated transient transport/session binding below network semantics."""
    def __init__(self, topology: Topology):
        self.topology = topology
        self._sessions: dict[str, SessionIdentity] = {}
        self._bindings: dict[str, TransportBinding] = {}
        self._suspended: set[str] = set()
        self._generations: dict[str, int] = {}
        self._last_transport_ids: dict[str, str] = {}

    def admit(self, session: SessionIdentity, *, transport_id: str, path: TransportPath, now: int) -> TransportBinding:
        if session.expires_at <= now:
            raise NetworkError(RuntimeOutcome.AUTH_EXPIRED, "session expired before transport admission")
        if len(self._sessions) >= MAX_SESSIONS and session.session_id not in self._sessions:
            raise NetworkError(RuntimeOutcome.RATE_LIMITED, "session capacity exhausted")
        if not transport_id or transport_id in {session.principal_id, session.session_id, session.room_id}:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "transport identity must be role-distinct")
        if self.topology == Topology.PEER_HOSTED and path not in {TransportPath.WEBRTC_DIRECT, TransportPath.WEBRTC_TURN, TransportPath.WSS_PEER_RELAY}:
            raise NetworkError(RuntimeOutcome.TRANSPORT_UNAVAILABLE, "transport incompatible with peer-hosted topology")
        if self.topology == Topology.DEDICATED_AUTHORITATIVE and path != TransportPath.WSS_DEDICATED:
            raise NetworkError(RuntimeOutcome.TRANSPORT_UNAVAILABLE, "dedicated topology requires selected WSS baseline")
        if self.topology == Topology.OFFLINE and path != TransportPath.LOCAL:
            raise NetworkError(RuntimeOutcome.TRANSPORT_UNAVAILABLE, "offline topology accepts only local adapter")
        generation = self._generations.get(session.session_id, 0) + 1
        binding = TransportBinding(session, transport_id, path, generation)
        self._sessions[session.session_id] = session
        self._bindings[session.session_id] = binding
        self._generations[session.session_id] = generation
        self._last_transport_ids[session.session_id] = transport_id
        self._suspended.discard(session.session_id)
        return binding

    def reconnect(self, session_id: str, *, transport_id: str, path: TransportPath, now: int) -> TransportBinding:
        session = self._sessions.get(session_id)
        if session is None:
            raise NetworkError(RuntimeOutcome.AUTH_REQUIRED, "runtime session is not admitted")
        if now >= session.expires_at:
            raise NetworkError(RuntimeOutcome.AUTH_EXPIRED, "runtime session expired")
        if self._last_transport_ids.get(session_id) == transport_id:
            raise NetworkError(RuntimeOutcome.RECONNECT_FAILED, "reconnect must bind a new transient transport identity")
        return self.admit(session, transport_id=transport_id, path=path, now=now)

    def suspend(self, session_id: str) -> RuntimeOutcome:
        if session_id not in self._sessions:
            raise NetworkError(RuntimeOutcome.AUTH_REQUIRED, "runtime session is not admitted")
        self._suspended.add(session_id)
        return RuntimeOutcome.SUSPENDED

    def disconnect(self, session_id: str) -> None:
        self._bindings.pop(session_id, None)
        self._suspended.discard(session_id)

    def close_session(self, session_id: str) -> None:
        self.disconnect(session_id)
        self._sessions.pop(session_id, None)
        self._generations.pop(session_id, None)
        self._last_transport_ids.pop(session_id, None)

    def session(self, session_id: str, *, now: int) -> SessionIdentity:
        session = self._sessions.get(session_id)
        if session is None:
            raise NetworkError(RuntimeOutcome.AUTH_REQUIRED, "unknown runtime session")
        if now >= session.expires_at:
            raise NetworkError(RuntimeOutcome.AUTH_EXPIRED, "runtime session expired")
        return session

    def binding(self, session_id: str) -> TransportBinding:
        binding = self._bindings.get(session_id)
        if binding is None:
            raise NetworkError(RuntimeOutcome.RECONNECT_REQUIRED, "session has no live transport")
        return binding


class RuntimeNetworkingService:
    """Topology-independent authority, ingress, relevance and reconnect semantics."""
    def __init__(self, *, topology: Topology, room_id: str):
        self.topology, self.room_id = topology, room_id
        self.transport = ProductionTransportService(topology)
        self._things: dict[str, ThingNetworkState] = {}
        self._relevance: dict[str, set[str]] = defaultdict(set)
        self._pending_state: dict[str, dict[str, NetworkEnvelope]] = defaultdict(dict)
        self._pending_events: dict[str, deque[NetworkEnvelope]] = defaultdict(deque)
        self._last_sequence: dict[tuple[str, MessageClass], int] = {}
        self._state_watermarks: dict[tuple[str, str], int] = {}
        self._dedup_seen: dict[str, set[str]] = defaultdict(set)
        self._dedup_order: dict[str, deque[str]] = defaultdict(deque)
        self._rate_bucket: dict[tuple[str, int], int] = defaultdict(int)
        self._counters: dict[str, int] = defaultdict(int)
        self._protected_assets: dict[str, dict[str, Any]] = {}

    def admit_session(self, session: SessionIdentity, *, transport_id: str, path: TransportPath, now: int) -> TransportBinding:
        if session.room_id != self.room_id:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "runtime session room mismatch")
        return self.transport.admit(session, transport_id=transport_id, path=path, now=now)

    def reconnect_session(self, session_id: str, *, transport_id: str, path: TransportPath, now: int) -> TransportBinding:
        return self.transport.reconnect(session_id, transport_id=transport_id, path=path, now=now)

    def leave_session(self, session_id: str) -> None:
        self.transport.close_session(session_id)
        self._relevance.pop(session_id, None)
        self._counters["session_leaves"] += 1

    def reconnect_baseline(self, session_id: str, *, now: int) -> dict[str, Any]:
        self.transport.session(session_id, now=now); self.transport.binding(session_id)
        relevant = self._relevance.get(session_id)
        thing_ids = sorted(relevant) if relevant else sorted(self._things)
        things: dict[str, Any] = {}
        for thing_id in thing_ids:
            thing = self._thing(thing_id)
            if thing.residency == Residency.TOMBSTONED:
                continue
            things[thing_id] = {
                "thing_id": thing_id, "authority_epoch": thing.authority_epoch,
                "residency": thing.residency.value, "replicated_state": deepcopy(thing.replicated_state),
                "state_watermarks": {locus: sequence for (tid, locus), sequence in self._state_watermarks.items() if tid == thing_id},
            }
        return {"room_id": self.room_id, "things": things}

    def register_thing(self, *, thing_id: str, declaration: NetworkDeclaration, authority_session_id: str, authority_epoch: int = 1, controller_principal_id: str | None = None) -> None:
        if thing_id in self._things:
            raise ValueError(f"Thing already registered: {thing_id}")
        if len(self._things) >= MAX_THINGS:
            raise NetworkError(RuntimeOutcome.RATE_LIMITED, "network Thing capacity exhausted")
        if authority_epoch < 1:
            raise ValueError("authority epoch must be positive")
        self._things[thing_id] = ThingNetworkState(thing_id, declaration, authority_session_id, authority_epoch, controller_principal_id)

    def add_protected_asset(self, asset_id: str, revision: Mapping[str, Any]) -> None:
        self._protected_assets[asset_id] = validate_protected_asset_revision(revision)

    def protected_asset(self, asset_id: str) -> dict[str, Any]:
        return deepcopy(self._protected_assets[asset_id])

    def set_controller(self, thing_id: str, principal_id: str | None) -> None:
        self._thing(thing_id).controller_principal_id = principal_id
        self._counters["controller_changes"] += 1

    def set_relevant(self, session_id: str, thing_id: str, relevant: bool) -> None:
        if thing_id not in self._things:
            raise NetworkError(RuntimeOutcome.TARGET_UNKNOWN, "cannot set relevance for unknown Thing")
        (self._relevance[session_id].add if relevant else self._relevance[session_id].discard)(thing_id)

    def is_relevant(self, session_id: str, thing_id: str) -> bool:
        return thing_id in self._relevance.get(session_id, set())

    def set_residency(self, thing_id: str, residency: Residency) -> tuple[NetworkEnvelope, ...]:
        thing = self._thing(thing_id)
        if thing.residency == Residency.TOMBSTONED and residency != Residency.TOMBSTONED:
            raise NetworkError(RuntimeOutcome.TARGET_TOMBSTONED, "tombstoned Thing cannot resurrect")
        thing.residency = residency
        if residency == Residency.TOMBSTONED:
            self._pending_state.pop(thing_id, None); self._pending_events.pop(thing_id, None); return ()
        if residency == Residency.RESIDENT:
            queued = list(self._pending_state.pop(thing_id, {}).values()) + list(self._pending_events.pop(thing_id, ()))
            queued.sort(key=lambda env: (env.sequence, env.message_id))
            return tuple(queued)
        return ()

    def ingress(self, envelope: NetworkEnvelope, *, now: int, tick: int) -> DeliveryResult:
        try:
            return self._ingress_impl(envelope, now=now, tick=tick)
        except NetworkError as exc:
            self._counters[f"rejected.{exc.outcome.value}"] += 1
            raise

    def _ingress_impl(self, envelope: NetworkEnvelope, *, now: int, tick: int) -> DeliveryResult:
        self._validate_envelope_size_and_authority(envelope)
        session = self.transport.session(envelope.sender_session_id, now=now)
        self.transport.binding(envelope.sender_session_id)
        self._rate_limit(envelope.sender_session_id, tick)
        thing = self._thing(envelope.target_thing_id)
        if thing.residency == Residency.TOMBSTONED:
            raise NetworkError(RuntimeOutcome.TARGET_TOMBSTONED, "message targets tombstoned Thing")
        if envelope.authority_epoch != thing.authority_epoch:
            raise NetworkError(RuntimeOutcome.STALE_EPOCH, "message authority epoch is stale or premature")
        self._check_sequence(envelope); self._check_dedup(envelope)
        if envelope.message_class == MessageClass.INPUT:
            result = self._ingest_input(thing, session, envelope)
        elif envelope.message_class == MessageClass.STATE:
            result = self._ingest_state(thing, envelope)
        elif envelope.message_class == MessageClass.EVENT:
            result = self._ingest_event(thing, envelope)
        elif envelope.message_class == MessageClass.BASELINE:
            result = self._ingest_baseline(thing, envelope)
        else:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "unknown message class")
        self._remember_sequence(envelope); self._remember_dedup(envelope)
        self._counters[f"accepted.{envelope.message_class.value}"] += 1
        return result

    def capture_checkpoint(self, *, thing_ids: Iterable[str], confirmed: bool) -> AuthorityCheckpoint:
        scope = tuple(sorted(set(thing_ids)))
        if not scope:
            raise ValueError("checkpoint scope must not be empty")
        things = [self._thing(tid) for tid in scope]
        epochs = {thing.authority_epoch for thing in things}
        if len(epochs) != 1:
            raise NetworkError(RuntimeOutcome.CHECKPOINT_UNCONFIRMED, "checkpoint scope spans authority epochs")
        state = {thing.thing_id: deepcopy(thing.replicated_state) for thing in things}
        watermarks = {thing.thing_id: {locus: seq for (tid, locus), seq in self._state_watermarks.items() if tid == thing.thing_id} for thing in things}
        return AuthorityCheckpoint(scope, next(iter(epochs)), confirmed, state, watermarks, deepcopy(self._protected_assets))

    def migrate_peer_host(self, *, new_authority_session_id: str, checkpoint: AuthorityCheckpoint, now: int) -> int:
        if self.topology != Topology.PEER_HOSTED:
            raise NetworkError(RuntimeOutcome.MIGRATION_UNSUPPORTED, "client authority migration is not valid in this topology")
        if not checkpoint.confirmed:
            raise NetworkError(RuntimeOutcome.CHECKPOINT_UNCONFIRMED, "peer host migration requires confirmed checkpoint")
        self.transport.session(new_authority_session_id, now=now); self.transport.binding(new_authority_session_id)
        if set(checkpoint.replicated_state) != set(checkpoint.scope):
            raise NetworkError(RuntimeOutcome.CHECKPOINT_UNCONFIRMED, "checkpoint state scope is incomplete or inconsistent")
        staged_things: list[ThingNetworkState] = []
        staged_assets: dict[str, dict[str, Any]] = {}
        for thing_id in checkpoint.scope:
            thing = self._thing(thing_id)
            if thing.authority_epoch != checkpoint.source_epoch:
                raise NetworkError(RuntimeOutcome.STALE_EPOCH, "checkpoint no longer matches current authority epoch")
            staged_things.append(thing)
        for asset_id, revision in checkpoint.protected_assets.items():
            staged_assets[asset_id] = validate_protected_asset_revision(revision)
        new_epoch = checkpoint.source_epoch + 1
        for thing in staged_things:
            thing.replicated_state = deepcopy(dict(checkpoint.replicated_state[thing.thing_id]))
            thing.authority_session_id = new_authority_session_id
            thing.authority_epoch = new_epoch
            for locus, sequence in checkpoint.state_watermarks.get(thing.thing_id, {}).items():
                self._state_watermarks[(thing.thing_id, locus)] = int(sequence)
        self._protected_assets.update(staged_assets)
        self._counters["authority_migrations"] += 1
        return new_epoch

    def authority_lost(self, *, thing_id: str) -> RuntimeOutcome:
        self._thing(thing_id); self._counters["authority_lost"] += 1
        return RuntimeOutcome.AUTHORITY_LOST

    def semantic_snapshot(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id, "topology": self.topology.value,
            "things": {tid: {"thing_id": tid, "authority_epoch": thing.authority_epoch, "residency": thing.residency.value, "replicated_state": deepcopy(thing.replicated_state)} for tid, thing in sorted(self._things.items())},
            "protected_assets": deepcopy(self._protected_assets),
        }

    def counters(self) -> dict[str, int]:
        return dict(self._counters)

    def pending_count(self, thing_id: str) -> int:
        return len(self._pending_state.get(thing_id, {})) + len(self._pending_events.get(thing_id, ()))

    def _thing(self, thing_id: str) -> ThingNetworkState:
        thing = self._things.get(thing_id)
        if thing is None:
            raise NetworkError(RuntimeOutcome.TARGET_UNKNOWN, "message targets unknown Thing")
        return thing

    def _validate_envelope_size_and_authority(self, envelope: NetworkEnvelope) -> None:
        primitive = {"message_id": envelope.message_id, "message_class": envelope.message_class.value, "sender_session_id": envelope.sender_session_id, "authority_epoch": envelope.authority_epoch, "sequence": envelope.sequence, "target_thing_id": envelope.target_thing_id, "locus": envelope.locus, "payload": envelope.payload}
        try:
            blob = canonical_json(primitive)
        except (TypeError, ValueError) as exc:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "network payload is not canonical-JSON representable") from exc
        if len(blob) > MAX_MESSAGE_BYTES:
            raise NetworkError(RuntimeOutcome.MESSAGE_OVERSIZE, "network message exceeds byte bound")
        if not envelope.message_id or len(envelope.message_id) > 128:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "message identity malformed")
        if envelope.sequence < 0 or envelope.authority_epoch < 1:
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "negative sequence or invalid authority epoch")
        _walk_forbidden(envelope.payload, FORBIDDEN_REMOTE_AUTHORITY_KEYS)

    def _rate_limit(self, session_id: str, tick: int) -> None:
        key = (session_id, tick); self._rate_bucket[key] += 1
        if self._rate_bucket[key] > MAX_MESSAGES_PER_TICK:
            self._counters[RuntimeOutcome.RATE_LIMITED.value] += 1
            raise NetworkError(RuntimeOutcome.RATE_LIMITED, "per-session ingress rate exceeded")
        if len(self._rate_bucket) > MAX_SESSIONS * 4:
            oldest_tick = min(bucket_tick for _, bucket_tick in self._rate_bucket)
            for stale in [key for key in self._rate_bucket if key[1] == oldest_tick]:
                del self._rate_bucket[stale]

    def _check_sequence(self, envelope: NetworkEnvelope) -> None:
        previous = self._last_sequence.get((envelope.sender_session_id, envelope.message_class))
        if previous is None:
            return
        if envelope.sequence <= previous or envelope.sequence - previous > MAX_SEQUENCE_GAP:
            raise NetworkError(RuntimeOutcome.REORDERED, "network sequence violates monotonic/gap policy")

    def _remember_sequence(self, envelope: NetworkEnvelope) -> None:
        self._last_sequence[(envelope.sender_session_id, envelope.message_class)] = envelope.sequence

    def _check_dedup(self, envelope: NetworkEnvelope) -> None:
        if envelope.message_id in self._dedup_seen[envelope.sender_session_id]:
            raise NetworkError(RuntimeOutcome.REPLAY, "network message replayed")

    def _remember_dedup(self, envelope: NetworkEnvelope) -> None:
        sender = envelope.sender_session_id
        seen, order = self._dedup_seen[sender], self._dedup_order[sender]
        seen.add(envelope.message_id); order.append(envelope.message_id)
        while len(order) > MAX_DEDUP_IDS_PER_SENDER:
            seen.discard(order.popleft())

    def _ingest_input(self, thing: ThingNetworkState, session: SessionIdentity, env: NetworkEnvelope) -> DeliveryResult:
        if env.locus not in thing.declaration.input_kinds:
            raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, "undeclared input kind")
        if thing.controller_principal_id is not None and session.principal_id != thing.controller_principal_id:
            raise NetworkError(RuntimeOutcome.CONTROLLER_REJECTED, "principal does not control target Thing")
        bounds = thing.declaration.input_numeric_bounds.get(env.locus)
        if bounds is not None:
            if set(env.payload) != set(bounds):
                raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, "input payload does not match declared fields")
            for field_name, (minimum, maximum) in bounds.items():
                value = env.payload[field_name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
                    raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, f"input field outside declared bound: {field_name}")
        return DeliveryResult("intent_accepted", target_thing_id=thing.thing_id, message_id=env.message_id)

    def _require_authority(self, thing: ThingNetworkState, env: NetworkEnvelope) -> None:
        if env.sender_session_id != thing.authority_session_id:
            raise NetworkError(RuntimeOutcome.AUTHORITY_REJECTED, "sender is not current simulation authority")

    def _ingest_state(self, thing: ThingNetworkState, env: NetworkEnvelope) -> DeliveryResult:
        self._require_authority(thing, env)
        if env.locus not in thing.declaration.state_loci:
            raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, "undeclared replicated state locus")
        key = (thing.thing_id, env.locus); previous = self._state_watermarks.get(key)
        if previous is not None and env.sequence <= previous:
            raise NetworkError(RuntimeOutcome.REORDERED, "state sequence cannot roll back locus")
        self._state_watermarks[key] = env.sequence
        thing.replicated_state[env.locus] = deepcopy(dict(env.payload))
        if thing.residency == Residency.KNOWN_UNLOADED:
            self._pending_state[thing.thing_id][env.locus] = env
            return DeliveryResult("coalesced_known_unloaded", target_thing_id=thing.thing_id, message_id=env.message_id)
        return DeliveryResult("state_applied", target_thing_id=thing.thing_id, message_id=env.message_id)

    def _ingest_event(self, thing: ThingNetworkState, env: NetworkEnvelope) -> DeliveryResult:
        self._require_authority(thing, env)
        if env.locus not in thing.declaration.event_kinds:
            raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, "undeclared event kind")
        if thing.residency == Residency.KNOWN_UNLOADED:
            queue = self._pending_events[thing.thing_id]
            if len(queue) >= MAX_PENDING_EVENTS_PER_THING:
                raise NetworkError(RuntimeOutcome.QUEUE_FULL, "reliable unloaded-event queue exhausted")
            queue.append(env)
            return DeliveryResult("queued_known_unloaded", target_thing_id=thing.thing_id, message_id=env.message_id)
        return DeliveryResult("event_delivered", target_thing_id=thing.thing_id, message_id=env.message_id)

    def _ingest_baseline(self, thing: ThingNetworkState, env: NetworkEnvelope) -> DeliveryResult:
        self._require_authority(thing, env)
        if env.locus != "baseline":
            raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, "baseline envelope uses invalid locus")
        state = env.payload.get("state")
        if not isinstance(state, Mapping):
            raise NetworkError(RuntimeOutcome.AUTH_REJECTED, "baseline state malformed")
        undeclared = set(state) - set(thing.declaration.state_loci)
        if undeclared:
            raise NetworkError(RuntimeOutcome.LOCUS_REJECTED, f"baseline contains undeclared state loci: {sorted(undeclared)}")
        thing.replicated_state = deepcopy(dict(state))
        return DeliveryResult("baseline_applied", target_thing_id=thing.thing_id, message_id=env.message_id)
