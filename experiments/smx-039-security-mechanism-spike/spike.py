"""SMX-039 physical-boundary mechanism-selection spike.

This is falsification/selection evidence, not a production sandbox implementation.
It deliberately reuses the production SPB1 parser and models the enforcement seams
that SMX-040 must implement around real decoder workers and repository trust.
"""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from splashmx.packages.bundle import BundleLimits, SPB1_MAGIC, parse_spb1
from splashmx.packages.model import PackageError


class SelectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParserLimits:
    """Current production SPB1 hard ceilings; SMX-040 may only tighten/calibrate."""

    max_bundle_bytes: int = 512 * 1024 * 1024
    max_index_bytes: int = 8 * 1024 * 1024
    max_entries: int = 4096
    max_entry_bytes: int = 256 * 1024 * 1024


@dataclass(frozen=True)
class MediaLimits:
    """Candidate decoder-ingress ceilings for the spike, not universal product SLOs."""

    max_compressed_bytes: int = 64 * 1024 * 1024
    max_decoded_bytes: int = 256 * 1024 * 1024
    max_image_pixels: int = 8192 * 8192
    max_audio_frames: int = 57_600_000
    max_ipc_message_bytes: int = 16 * 1024 * 1024


@dataclass(frozen=True)
class MediaDescriptor:
    compressed_bytes: int
    decoded_bytes: int
    image_pixels: int = 0
    audio_frames: int = 0
    metadata: Mapping[str, Any] | None = None


FORBIDDEN_BUNDLE_KINDS = frozenset(
    {
        "path",
        "symlink",
        "hardlink",
        "device",
        "native-extension",
        "gdextension",
        "pck",
        "gdscript",
        "javascript",
        "install-script",
        "executable",
    }
)

FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "capability_grant",
        "capability_token",
        "delegation_root",
        "host_handle",
        "native_handle",
        "javascript_object",
        "nodepath",
        "rid",
        "resource_uid",
        "peer_id",
        "socket",
        "process_handle",
        "session_handle",
    }
)

PROTECTED_ASSET_FIELDS = frozenset(
    {
        "asset_id",
        "revision_digest",
        "source_digest",
        "source_identity",
        "source_metadata",
        "media_semantics",
        "provenance",
        "licence_attribution",
        "derivation_lineage",
    }
)


def preflight_spb1(data: bytes, limits: ParserLimits | None = None):
    """Parse the selected pathless container through the real production parser."""

    policy = limits or ParserLimits()
    payload = bytes(data)
    if len(payload) > policy.max_bundle_bytes:
        raise SelectionError("security.container_budget", "bundle exceeds physical ingress bound")
    if not payload.startswith(SPB1_MAGIC):
        raise SelectionError("security.container_format", "ordinary packages must use pathless SPB1")
    try:
        parsed = parse_spb1(
            payload,
            limits=BundleLimits(
                max_bundle_bytes=policy.max_bundle_bytes,
                max_index_bytes=policy.max_index_bytes,
                max_entries=policy.max_entries,
                max_entry_bytes=policy.max_entry_bytes,
            ),
        )
    except PackageError as exc:
        raise SelectionError("security.container_invalid", str(exc)) from exc
    for entry in parsed.entries:
        if entry.kind.casefold() in FORBIDDEN_BUNDLE_KINDS:
            raise SelectionError(
                "security.container_executable_kind",
                f"ordinary package entry kind {entry.kind!r} crosses the non-executable boundary",
            )
    return parsed


def _reject_transient_authority(value: Any, *, max_depth: int = 32, max_nodes: int = 4096) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes or depth > max_depth:
            raise SelectionError("security.decoder_metadata_budget", "decoder metadata exceeds structural bound")
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise SelectionError("security.decoder_metadata_type", "decoder metadata keys must be strings")
                if key.casefold() in FORBIDDEN_AUTHORITY_KEYS:
                    raise SelectionError("security.serialized_authority", f"forbidden transient authority field: {key}")
                visit(child, depth + 1)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child, depth + 1)
        elif item is None or isinstance(item, (str, int, float, bool, bytes)):
            return
        else:
            raise SelectionError("security.decoder_metadata_type", "unsupported decoder metadata value")

    visit(value, 0)


def preflight_media(descriptor: MediaDescriptor, limits: MediaLimits | None = None) -> None:
    policy = limits or MediaLimits()
    dimensions = (
        (descriptor.compressed_bytes, policy.max_compressed_bytes, "compressed_bytes"),
        (descriptor.decoded_bytes, policy.max_decoded_bytes, "decoded_bytes"),
        (descriptor.image_pixels, policy.max_image_pixels, "image_pixels"),
        (descriptor.audio_frames, policy.max_audio_frames, "audio_frames"),
    )
    for value, maximum, name in dimensions:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
            raise SelectionError("security.decoder_budget", f"{name} exceeds physical decoder-ingress bound")
    _reject_transient_authority(descriptor.metadata or {})


class DecoderBroker:
    """Probe proving preflight ordering: denial must occur before decoder invocation."""

    def __init__(self, limits: MediaLimits | None = None) -> None:
        self.limits = limits or MediaLimits()
        self.calls = 0

    def invoke(self, descriptor: MediaDescriptor, decoder: Callable[[MediaDescriptor], Any]) -> Any:
        preflight_media(descriptor, self.limits)
        self.calls += 1
        return decoder(descriptor)


@dataclass(frozen=True)
class IsolationProfile:
    target: str
    dedicated_worker: bool
    memory_safe_decoder: bool
    fixed_linear_memory: bool
    csp_worker_src_self: bool = False
    javascript_bridge_disabled: bool = False
    process_boundary: bool = False
    no_new_privs: bool = False
    seccomp_allowlist: bool = False
    landlock_deny_by_default: bool = False
    rlimits: bool = False


def browser_profile(*, decoder_backend: str = "wasm-memory-safe") -> IsolationProfile:
    return IsolationProfile(
        target="web",
        dedicated_worker=True,
        memory_safe_decoder=decoder_backend == "wasm-memory-safe",
        fixed_linear_memory=decoder_backend == "wasm-memory-safe",
        csp_worker_src_self=True,
        javascript_bridge_disabled=True,
    )


def linux_profile(target: str = "native", *, omit: str | None = None) -> IsolationProfile:
    if target not in {"native", "headless"}:
        raise ValueError("linux profile target must be native or headless")
    values = {
        "process_boundary": True,
        "no_new_privs": True,
        "seccomp_allowlist": True,
        "landlock_deny_by_default": True,
        "rlimits": True,
    }
    if omit in values:
        values[omit] = False
    return IsolationProfile(
        target=target,
        dedicated_worker=True,
        memory_safe_decoder=False,
        fixed_linear_memory=False,
        **values,
    )


def public_untrusted_release_ready(profile: IsolationProfile) -> bool:
    """Deliberately conservative release gate for untrusted public content."""

    if profile.target == "web":
        # A Worker is not claimed to be an OS-process security boundary. Public
        # content is permitted only with a trusted, memory-safe fixed-memory WASM
        # decoder and a hardened player build that omits JavaScriptBridge.
        return all(
            (
                profile.dedicated_worker,
                profile.memory_safe_decoder,
                profile.fixed_linear_memory,
                profile.csp_worker_src_self,
                profile.javascript_bridge_disabled,
            )
        )
    if profile.target in {"native", "headless"}:
        return all(
            (
                profile.dedicated_worker,
                profile.process_boundary,
                profile.no_new_privs,
                profile.seccomp_allowlist,
                profile.landlock_deny_by_default,
                profile.rlimits,
            )
        )
    return False


@dataclass(frozen=True)
class RolePolicy:
    key_ids: frozenset[str]
    threshold: int

    def __post_init__(self) -> None:
        if self.threshold < 1 or self.threshold > len(self.key_ids):
            raise SelectionError("security.trust_policy", "invalid signature threshold")


@dataclass(frozen=True)
class RootMetadata:
    version: int
    expires_at: int
    root: RolePolicy
    targets: RolePolicy
    revoked_key_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TargetMetadata:
    version: int
    expires_at: int
    package_revision_id: str
    length: int
    sha256: str


@dataclass(frozen=True)
class TrustState:
    root_version: int
    targets_version: int
    now: int


def _threshold_ok(policy: RolePolicy, signatures: Sequence[str], revoked: frozenset[str]) -> bool:
    valid = set(signatures) & set(policy.key_ids)
    valid.difference_update(revoked)
    return len(valid) >= policy.threshold


def rotate_root(
    current: RootMetadata,
    candidate: RootMetadata,
    *,
    old_role_signatures: Sequence[str],
    new_role_signatures: Sequence[str],
    now: int,
) -> RootMetadata:
    """Model TUF-style sequential root rotation: old and new thresholds must sign."""

    if candidate.version != current.version + 1:
        raise SelectionError("security.root_version", "root rotation must be sequential")
    if current.expires_at <= now or candidate.expires_at <= now:
        raise SelectionError("security.trust_expired", "root metadata expired")
    if not _threshold_ok(current.root, old_role_signatures, current.revoked_key_ids):
        raise SelectionError("security.root_old_threshold", "old root threshold not met")
    if not _threshold_ok(candidate.root, new_role_signatures, candidate.revoked_key_ids):
        raise SelectionError("security.root_new_threshold", "new root threshold not met")
    return candidate


def verify_target_metadata(
    root: RootMetadata,
    state: TrustState,
    metadata: TargetMetadata,
    *,
    signatures: Sequence[str],
    expected_revision_id: str,
    expected_length: int,
    expected_sha256: str,
) -> TrustState:
    if root.version < state.root_version or metadata.version < state.targets_version:
        raise SelectionError("security.trust_rollback", "trusted metadata version rolled back")
    if root.expires_at <= state.now or metadata.expires_at <= state.now:
        raise SelectionError("security.trust_expired", "trusted metadata expired/frozen")
    if not _threshold_ok(root.targets, signatures, root.revoked_key_ids):
        raise SelectionError("security.trust_threshold", "targets signature threshold not met")
    if (
        metadata.package_revision_id != expected_revision_id
        or metadata.length != expected_length
        or metadata.sha256 != expected_sha256
    ):
        raise SelectionError("security.trust_target_mismatch", "signed target does not bind exact requested revision")
    return TrustState(root.version, metadata.version, state.now)


def signature_trust_grants_capability(*_: Any, **__: Any) -> bool:
    """D-122/R-016-10: authenticity/provenance never mint runtime capability."""

    return False


def verify_ed25519_with_openssl(message: bytes, tamper: bool = False) -> bool:
    """Exercise the selected primitive through the CI host OpenSSL implementation."""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        private = root / "private.pem"
        public = root / "public.pem"
        payload = root / "payload.bin"
        signature = root / "signature.bin"
        payload.write_bytes(message)
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(private), "-in", str(payload), "-out", str(signature)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if tamper:
            payload.write_bytes(message + b"!")
        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(public), "-in", str(payload), "-sigfile", str(signature)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0


def validate_protected_asset_candidate(candidate: Mapping[str, Any]) -> None:
    if set(candidate) != PROTECTED_ASSET_FIELDS:
        raise SelectionError(
            "security.protected_asset_partial",
            "protected Asset replacement must carry the complete indivisible canonical revision",
        )


def selected_mechanisms() -> dict[str, Any]:
    return {
        "container": "SPB1 pathless bounded deterministic-CBOR index + raw immutable blobs",
        "decoder": "preflighted broker; memory-safe fixed-memory WASM Worker on web; sandboxed worker process on Linux native/headless",
        "trust": "TUF-style versioned threshold metadata with Ed25519 target/root signatures and exact digest+length binding",
        "linux_sandbox": ["process", "no_new_privs", "seccomp allowlist", "Landlock deny-by-default", "rlimits"],
        "browser_hardening": ["dedicated module Worker", "fixed WASM memory", "worker CSP", "JavaScriptBridge disabled"],
        "release_rule": "untrusted public content is blocked on targets that cannot provide the selected decoder isolation profile",
        "authority_rule": "signature/provenance/trust never creates a SplashMX capability grant",
    }


__all__ = [
    "DecoderBroker",
    "IsolationProfile",
    "MediaDescriptor",
    "MediaLimits",
    "ParserLimits",
    "RolePolicy",
    "RootMetadata",
    "SelectionError",
    "TargetMetadata",
    "TrustState",
    "browser_profile",
    "linux_profile",
    "preflight_media",
    "preflight_spb1",
    "public_untrusted_release_ready",
    "rotate_root",
    "selected_mechanisms",
    "signature_trust_grants_capability",
    "validate_protected_asset_candidate",
    "verify_ed25519_with_openssl",
    "verify_target_metadata",
]
