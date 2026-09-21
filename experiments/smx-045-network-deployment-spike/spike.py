#!/usr/bin/env python3
"""SMX-045 bounded network deployment/auth/signalling mechanism spike."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

MAX_TICKET_BYTES = 4096
MAX_SIGNAL_BYTES = 65536
TICKET_VERSION = 1
PROTECTED_ASSET_FIELDS = (
    "revision_digest",
    "source_digest",
    "source_identity",
    "source_metadata",
    "media_semantics",
    "provenance",
    "licence_attribution",
    "derivation_lineage",
)


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


class TransportPath(str, Enum):
    WEBRTC_DIRECT = "webrtc_datachannel_direct"
    WEBRTC_TURN = "webrtc_datachannel_turn"
    WSS_PEER_RELAY = "wss_peer_relay"
    WSS_DEDICATED = "wss_dedicated_authority"


@dataclass(frozen=True)
class SessionIdentity:
    principal_id: str
    session_id: str
    room_id: str


@dataclass(frozen=True)
class TransportBinding:
    session: SessionIdentity
    transport_id: str
    path: TransportPath


@dataclass(frozen=True)
class TransportDecision:
    path: TransportPath | None
    outcome: RuntimeOutcome | None
    diagnostics: tuple[RuntimeOutcome, ...] = ()


class TicketError(ValueError):
    def __init__(self, outcome: RuntimeOutcome, message: str):
        super().__init__(message)
        self.outcome = outcome


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class JoinTicketAuthority:
    """Disposable spike for post-login, audience-bound runtime join tickets.

    The user-facing login protocol is deliberately outside this class. Production
    uses a standards-based authorization-code + PKCE control plane, then exchanges
    that authenticated result for a short-lived runtime join ticket. The ticket
    never grants a SplashMX capability and is never a canonical identity.
    """

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("ticket signing secret must be at least 32 bytes")
        self._secret = secret
        self._redeemed: set[str] = set()

    def issue(
        self,
        session: SessionIdentity,
        *,
        audience: str,
        now: int,
        ttl_seconds: int = 60,
        nonce: str | None = None,
    ) -> str:
        if not (1 <= ttl_seconds <= 300):
            raise ValueError("runtime join ticket ttl outside bounded policy")
        payload = {
            "v": TICKET_VERSION,
            "principal_id": session.principal_id,
            "session_id": session.session_id,
            "room_id": session.room_id,
            "aud": audience,
            "iat": now,
            "exp": now + ttl_seconds,
            "nonce": nonce or secrets.token_hex(12),
        }
        body = _b64url(canonical_json(payload))
        sig = _b64url(hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest())
        token = f"{body}.{sig}"
        if len(token.encode("ascii")) > MAX_TICKET_BYTES:
            raise ValueError("runtime join ticket exceeds byte bound")
        return token

    def redeem(
        self,
        token: str,
        *,
        audience: str,
        room_id: str,
        now: int,
    ) -> SessionIdentity:
        if len(token.encode("utf-8")) > MAX_TICKET_BYTES:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, "ticket exceeds byte bound")
        try:
            body, sig = token.split(".", 1)
            expected = hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest()
            supplied = _b64url_decode(sig)
            if not hmac.compare_digest(expected, supplied):
                raise TicketError(RuntimeOutcome.AUTH_REJECTED, "ticket signature invalid")
            payload = json.loads(_b64url_decode(body))
        except TicketError:
            raise
        except Exception as exc:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, "malformed ticket") from exc

        if payload.get("v") != TICKET_VERSION:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, "ticket version unsupported")
        if payload.get("aud") != audience or payload.get("room_id") != room_id:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, "ticket scope mismatch")
        if not isinstance(payload.get("exp"), int) or now > payload["exp"]:
            raise TicketError(RuntimeOutcome.AUTH_EXPIRED, "ticket expired")
        nonce = payload.get("nonce")
        if not isinstance(nonce, str) or nonce in self._redeemed:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, "ticket replayed")
        self._redeemed.add(nonce)
        return SessionIdentity(
            principal_id=str(payload["principal_id"]),
            session_id=str(payload["session_id"]),
            room_id=str(payload["room_id"]),
        )


def select_peer_path(
    *,
    tls_ok: bool,
    signalling_ok: bool,
    webrtc_available: bool,
    ice_direct_ok: bool,
    turn_ok: bool,
    wss_relay_ok: bool,
) -> TransportDecision:
    """Select a transport below topology-independent network semantics."""
    if not tls_ok:
        return TransportDecision(None, RuntimeOutcome.TLS_FAILED)
    if not signalling_ok:
        return TransportDecision(None, RuntimeOutcome.SIGNAL_UNAVAILABLE)
    if webrtc_available and ice_direct_ok:
        return TransportDecision(TransportPath.WEBRTC_DIRECT, None)
    if webrtc_available and turn_ok:
        return TransportDecision(TransportPath.WEBRTC_TURN, None)
    if wss_relay_ok:
        diagnostics = [RuntimeOutcome.TRANSPORT_FALLBACK]
        if webrtc_available:
            diagnostics.insert(0, RuntimeOutcome.TURN_UNAVAILABLE)
        return TransportDecision(TransportPath.WSS_PEER_RELAY, None, tuple(diagnostics))
    if webrtc_available:
        return TransportDecision(None, RuntimeOutcome.ICE_NO_CANDIDATE)
    return TransportDecision(None, RuntimeOutcome.TRANSPORT_UNAVAILABLE)


def select_dedicated_path(*, tls_ok: bool, server_ok: bool, wss_ok: bool) -> TransportDecision:
    if not tls_ok:
        return TransportDecision(None, RuntimeOutcome.TLS_FAILED)
    if not server_ok:
        return TransportDecision(None, RuntimeOutcome.SERVER_UNAVAILABLE)
    if not wss_ok:
        return TransportDecision(None, RuntimeOutcome.TRANSPORT_UNAVAILABLE)
    return TransportDecision(TransportPath.WSS_DEDICATED, None)


def validate_signal(message: dict[str, Any]) -> dict[str, Any]:
    """Bound signalling before any transport adapter consumes it."""
    blob = canonical_json(message)
    if len(blob) > MAX_SIGNAL_BYTES:
        raise TicketError(RuntimeOutcome.SIGNAL_OVERSIZE, "signalling envelope exceeds byte bound")
    allowed = {"kind", "session_id", "transport_id", "offer", "answer", "candidate"}
    unknown = set(message) - allowed
    if unknown:
        raise TicketError(RuntimeOutcome.AUTH_REJECTED, f"forbidden signalling fields: {sorted(unknown)}")
    for forbidden in ("principal_id", "thing_id", "capability", "host_handle", "peer_id"):
        if forbidden in message:
            raise TicketError(RuntimeOutcome.AUTH_REJECTED, f"forbidden authority/identity field: {forbidden}")
    return dict(message)


def bind_transport(
    session: SessionIdentity,
    *,
    path: TransportPath,
    transport_id: str,
) -> TransportBinding:
    if not transport_id or transport_id in {session.principal_id, session.session_id, session.room_id}:
        raise ValueError("transport identity must be non-empty and role-distinct")
    return TransportBinding(session=session, transport_id=transport_id, path=path)


def reconnect(
    previous: TransportBinding,
    *,
    new_transport_id: str,
    session_still_valid: bool,
) -> tuple[TransportBinding | None, RuntimeOutcome | None]:
    if not session_still_valid:
        return None, RuntimeOutcome.AUTH_EXPIRED
    if new_transport_id == previous.transport_id:
        return None, RuntimeOutcome.RECONNECT_FAILED
    return bind_transport(previous.session, path=previous.path, transport_id=new_transport_id), None


def dedicated_authority_failure() -> RuntimeOutcome:
    """A client never self-promotes when dedicated authority disappears."""
    return RuntimeOutcome.AUTHORITY_LOST


def validate_protected_asset_revision(revision: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in PROTECTED_ASSET_FIELDS if field not in revision]
    if missing:
        raise ValueError(f"incomplete protected asset revision: {missing}")
    return json.loads(json.dumps(revision))


def candidate_matrix() -> list[dict[str, Any]]:
    return [
        {
            "candidate": "WebRTC DataChannel",
            "web": "built-in",
            "native": "requires pinned webrtc-native GDExtension",
            "peer_hosted": "selected primary",
            "dedicated": "not v1 baseline",
            "reason": "ICE/STUN/TURN support and data-channel delivery without exposing transport identity",
        },
        {
            "candidate": "WebSocket/WSS",
            "web": "built-in client",
            "native": "built-in client/server",
            "peer_hosted": "selected relay fallback",
            "dedicated": "selected baseline",
            "reason": "single HTTPS/WSS control-plane deployment and broad Godot web/native compatibility",
        },
        {
            "candidate": "ENet/UDP",
            "web": "unavailable",
            "native": "built-in",
            "peer_hosted": "rejected baseline",
            "dedicated": "deferred optional adapter",
            "reason": "cannot satisfy browser target directly",
        },
        {
            "candidate": "WebTransport/custom QUIC",
            "web": "browser API support varies",
            "native": "no selected Godot 4.7 built-in path",
            "peer_hosted": "deferred",
            "dedicated": "deferred",
            "reason": "would add a new target-specific stack without current acceptance need",
        },
    ]


def trust_profiles() -> dict[str, dict[str, str]]:
    return {
        "peer_hosted": {
            "identity_authority": "trusted session/signalling service",
            "simulation_authority": "designated participant host; not trusted for fairness",
            "transport_relay": "routing only; never semantic authority",
        },
        "dedicated_authoritative": {
            "identity_authority": "trusted session service",
            "simulation_authority": "operated dedicated service",
            "transport_relay": "not simulation authority",
        },
    }


def measure(iterations: int = 1000) -> dict[str, Any]:
    secret = b"s" * 32
    authority = JoinTicketAuthority(secret)
    session = SessionIdentity("principal:alice", "session:measure", "room:measure")
    ticket_sizes = []
    start = time.perf_counter_ns()
    for i in range(iterations):
        token = authority.issue(session, audience="signal", now=1_700_000_000, nonce=f"{i:024x}")
        ticket_sizes.append(len(token))
        authority.redeem(token, audience="signal", room_id="room:measure", now=1_700_000_001)
    elapsed_ns = time.perf_counter_ns() - start

    signal = {
        "kind": "ice_candidate",
        "session_id": session.session_id,
        "transport_id": "transport:1",
        "candidate": "candidate:0 1 UDP 2122252543 192.0.2.1 54321 typ host",
    }
    signal_bytes = len(canonical_json(signal))
    return {
        "schema": "splashmx.smx045-network-measurement/1",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "iterations": iterations,
        "metrics": {
            "join_ticket_issue_and_redeem_mean_us": round(elapsed_ns / iterations / 1000.0, 3),
            "join_ticket_max_bytes": max(ticket_sizes),
            "sample_signal_envelope_bytes": signal_bytes,
        },
        "note": "CI-local mechanism evidence only; not a product latency or throughput SLO.",
    }


def main() -> int:
    result = {
        "selection": {
            "peer_primary": TransportPath.WEBRTC_DIRECT.value,
            "peer_nat_relay": TransportPath.WEBRTC_TURN.value,
            "peer_fallback": TransportPath.WSS_PEER_RELAY.value,
            "dedicated": TransportPath.WSS_DEDICATED.value,
            "signalling": "authenticated WSS control plane",
            "nat": "ICE with STUN and short-lived TURN credentials; TURN/TLS fallback where required",
            "authentication": "authorization-code + PKCE control plane; short-lived audience/room-bound runtime join ticket",
        },
        "candidates": candidate_matrix(),
        "trust": trust_profiles(),
        "measurement": measure(),
    }
    out = Path(os.environ.get("SMX045_EVIDENCE_PATH", "artifacts/smx045-network-evidence.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
