"""SMX-040 production physical security boundary.

Cryptographic trust authenticates exact bytes, sandboxing contains hostile decoder
work, and neither creates SplashMX runtime capability. The module is deliberately
fail-closed: missing target isolation blocks public-untrusted use rather than
falling back to an in-process decoder.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import platform
import resource
import struct
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Protocol

from splashmx.canonical.core import AssetId
from splashmx.canonical.serialization import DecodeLimits, decode_canonical_cbor, encode_canonical_cbor
from splashmx.packages.bundle import BundleLimits, ParsedBundle, SPB1_MAGIC, parse_spb1
from splashmx.packages.model import PackageError, PackageRevisionId
from splashmx.security.capabilities import CapabilityId, HostServiceAdapter, ServiceTarget

CAP_MEDIA_DECODE = CapabilityId("media.decode")

FORBIDDEN_BUNDLE_KINDS = frozenset({
    "path", "symlink", "hardlink", "device", "native-extension", "gdextension",
    "pck", "gdscript", "javascript", "install-script", "executable",
})
FORBIDDEN_AUTHORITY_FIELDS = frozenset({
    "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
    "databaserowid", "cachekey", "transportpeerid", "connectionhandle",
    "socketid", "sessionid", "processhandle", "hosthandle", "hostobject",
    "capabilitytoken", "capabilitygrant", "grantid", "delegationgrant",
    "javascriptbridge", "gdextension", "nativehandle", "peerid", "socket",
    "process", "loaderauthority",
})
PROTECTED_ASSET_FIELDS = frozenset({
    "asset_id", "revision_digest", "source_digest", "source_identity",
    "source_metadata", "media_semantics", "provenance", "licence_attribution",
    "derivation_lineage",
})


class SecurityStage(str, Enum):
    CONTAINER = "container"
    TRUST = "trust"
    SEMANTIC = "semantic"
    CAPABILITY = "capability"
    DECODER_PREFLIGHT = "decoder_preflight"
    ISOLATION = "isolation"
    DECODER_RESULT = "decoder_result"
    CACHE = "cache"


class PhysicalSecurityError(ValueError):
    """Stable typed failure; privileged host exception text is never public."""

    def __init__(self, code: str, stage: SecurityStage, message: str, *, public_details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.public_details = dict(public_details or {})


def _fail(code: str, stage: SecurityStage, message: str, **details: Any) -> None:
    raise PhysicalSecurityError(code, stage, message, public_details=details)


@dataclass(frozen=True)
class SecurityEvent:
    code: str
    stage: SecurityStage
    outcome: str
    correlation_id: str | None = None


class SecurityTelemetry:
    """Bounded safe telemetry containing stable codes, never raw host details."""

    def __init__(self, max_events: int = 4096) -> None:
        if not isinstance(max_events, int) or isinstance(max_events, bool) or max_events <= 0:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self._events: list[SecurityEvent] = []

    def record(self, code: str, stage: SecurityStage, outcome: str, correlation_id: str | None = None) -> None:
        if len(self._events) >= self.max_events:
            self._events.pop(0)
        self._events.append(SecurityEvent(code, stage, outcome, correlation_id))

    @property
    def events(self) -> tuple[SecurityEvent, ...]:
        return tuple(self._events)


@dataclass(frozen=True)
class PhysicalLimits:
    max_bundle_bytes: int = 512 * 1024 * 1024
    max_index_bytes: int = 8 * 1024 * 1024
    max_entries: int = 4096
    max_entry_bytes: int = 256 * 1024 * 1024
    max_source_bytes: int = 64 * 1024 * 1024
    max_decoded_bytes: int = 256 * 1024 * 1024
    max_image_pixels: int = 8192 * 8192
    max_audio_frames: int = 57_600_000
    max_ipc_message_bytes: int = 16 * 1024 * 1024
    max_metadata_depth: int = 32
    max_metadata_nodes: int = 4096
    max_metadata_string_bytes: int = 256 * 1024
    max_derivative_cache_entries: int = 4096
    max_derivative_cache_bytes: int = 512 * 1024 * 1024
    native_address_space_bytes: int = 768 * 1024 * 1024
    native_cpu_seconds: int = 5
    native_open_files: int = 16
    native_output_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


def preflight_spb1(data: bytes, limits: PhysicalLimits | None = None) -> ParsedBundle:
    """R-016-01: ordinary packages are pathless SPB1; no host extraction occurs."""
    limits = limits or PhysicalLimits()
    raw = bytes(data)
    if len(raw) > limits.max_bundle_bytes:
        _fail("security.container_budget", SecurityStage.CONTAINER, "package exceeds ingress byte limit")
    if not raw.startswith(SPB1_MAGIC):
        _fail("security.container_format", SecurityStage.CONTAINER, "ordinary packages must use pathless SPB1")
    try:
        parsed = parse_spb1(raw, limits=BundleLimits(
            max_bundle_bytes=limits.max_bundle_bytes,
            max_index_bytes=limits.max_index_bytes,
            max_entries=limits.max_entries,
            max_entry_bytes=limits.max_entry_bytes,
        ))
    except PackageError as exc:
        raise PhysicalSecurityError("security.container_invalid", SecurityStage.CONTAINER, "package container failed bounded validation") from exc
    for entry in parsed.entries:
        if entry.kind.casefold() in FORBIDDEN_BUNDLE_KINDS:
            _fail("security.container_executable_kind", SecurityStage.CONTAINER, "ordinary package contains executable/extraction semantics")
    return parsed


def _normalise_field(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def reject_transient_authority(
    value: Any, *, limits: PhysicalLimits | None = None,
    where: str = "security message", stage: SecurityStage = SecurityStage.DECODER_PREFLIGHT,
) -> None:
    """Independent recursive R-016-02 enforcement at the physical boundary."""
    limits = limits or PhysicalLimits()
    counter = [0]

    def walk(item: Any, depth: int) -> None:
        counter[0] += 1
        if counter[0] > limits.max_metadata_nodes or depth > limits.max_metadata_depth:
            _fail("security.message_budget", stage, f"{where} exceeds structural bounds")
        if item is None or isinstance(item, (bool, int)):
            return
        if isinstance(item, float):
            if item != item or item in (float("inf"), float("-inf")):
                _fail("security.message_type", stage, f"{where} contains non-finite number")
            return
        if isinstance(item, (bytes, bytearray)):
            if len(item) > limits.max_ipc_message_bytes:
                _fail("security.message_budget", stage, f"{where} byte value exceeds IPC limit")
            return
        if isinstance(item, str):
            if len(item.encode("utf-8")) > limits.max_metadata_string_bytes:
                _fail("security.message_budget", stage, f"{where} string exceeds limit")
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child, depth + 1)
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    _fail("security.message_type", stage, f"{where} keys must be strings")
                if _normalise_field(key) in FORBIDDEN_AUTHORITY_FIELDS:
                    _fail("security.serialized_authority", stage, "transient host/capability authority cannot cross physical boundary")
                walk(child, depth + 1)
            return
        _fail("security.message_type", stage, f"{where} contains unsupported value type")

    walk(value, 0)


@dataclass(frozen=True)
class MediaDescriptor:
    asset_id: AssetId
    revision_digest: str
    source_digest: str
    source_bytes: int
    predicted_decoded_bytes: int
    image_pixels: int = 0
    audio_frames: int = 0
    derivative_kind: str = "decoded"
    derivative_version: str = "1"
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, AssetId):
            raise TypeError("asset_id must be AssetId")
        for name in ("revision_digest", "source_digest", "derivative_kind", "derivative_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 256:
                raise ValueError(f"{name} must be a bounded non-empty string")


@dataclass(frozen=True)
class DecoderResult:
    bytes: bytes
    decoded_bytes: int
    image_pixels: int = 0
    audio_frames: int = 0
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class DerivativeCacheKey:
    asset_id: AssetId
    revision_digest: str
    target_profile: str
    derivative_kind: str
    derivative_version: str


def derivative_cache_key(descriptor: MediaDescriptor, target_profile: str) -> DerivativeCacheKey:
    if not isinstance(target_profile, str) or not target_profile:
        raise ValueError("target_profile must be non-empty")
    return DerivativeCacheKey(
        descriptor.asset_id, descriptor.revision_digest, target_profile,
        descriptor.derivative_kind, descriptor.derivative_version,
    )


def _cache_key_id(key: DerivativeCacheKey) -> str:
    return hashlib.sha256(encode_canonical_cbor({
        "asset_id": str(key.asset_id), "revision_digest": key.revision_digest,
        "target_profile": key.target_profile, "derivative_kind": key.derivative_kind,
        "derivative_version": key.derivative_version,
    })).hexdigest()


class DerivativeCache:
    """Target-private immutable derivative cache; eviction/publication is non-semantic."""
    def __init__(self, limits: PhysicalLimits | None = None) -> None:
        self.limits = limits or PhysicalLimits()
        self._items: dict[str, bytes] = {}
        self._bytes = 0

    @property
    def entry_count(self) -> int:
        return len(self._items)

    @property
    def total_bytes(self) -> int:
        return self._bytes

    def publish(self, key: DerivativeCacheKey, data: bytes) -> str:
        item = bytes(data)
        key_id = _cache_key_id(key)
        old = self._items.get(key_id)
        new_total = self._bytes - (len(old) if old is not None else 0) + len(item)
        new_entries = len(self._items) + (0 if old is not None else 1)
        if new_entries > self.limits.max_derivative_cache_entries or new_total > self.limits.max_derivative_cache_bytes:
            _fail("security.derivative_cache_budget", SecurityStage.CACHE, "derivative cache publication exceeds finite bound")
        self._items[key_id] = item
        self._bytes = new_total
        return key_id

    def get(self, key_id: str) -> bytes:
        return bytes(self._items[key_id])



def preflight_media(descriptor: MediaDescriptor, limits: PhysicalLimits | None = None) -> None:
    limits = limits or PhysicalLimits()
    dims = (
        ("source_bytes", descriptor.source_bytes, limits.max_source_bytes),
        ("predicted_decoded_bytes", descriptor.predicted_decoded_bytes, limits.max_decoded_bytes),
        ("image_pixels", descriptor.image_pixels, limits.max_image_pixels),
        ("audio_frames", descriptor.audio_frames, limits.max_audio_frames),
    )
    for name, value, maximum in dims:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > maximum:
            _fail("security.decoder_budget", SecurityStage.DECODER_PREFLIGHT, f"{name} exceeds decoder admission bound", dimension=name)
    reject_transient_authority(descriptor.metadata or {}, limits=limits)


def validate_decoder_result(descriptor: MediaDescriptor, result: DecoderResult, limits: PhysicalLimits | None = None) -> None:
    limits = limits or PhysicalLimits()
    if not isinstance(result, DecoderResult):
        _fail("security.decoder_result_type", SecurityStage.DECODER_RESULT, "decoder returned invalid result type")
    if not isinstance(result.bytes, (bytes, bytearray)) or result.decoded_bytes != len(result.bytes):
        _fail("security.decoder_result_length", SecurityStage.DECODER_RESULT, "decoder result length does not match declaration")
    dims = (
        ("decoded_bytes", result.decoded_bytes, limits.max_decoded_bytes, descriptor.predicted_decoded_bytes),
        ("image_pixels", result.image_pixels, limits.max_image_pixels, descriptor.image_pixels or limits.max_image_pixels),
        ("audio_frames", result.audio_frames, limits.max_audio_frames, descriptor.audio_frames or limits.max_audio_frames),
    )
    for name, value, hard_max, declared_max in dims:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > hard_max or value > declared_max:
            _fail("security.decoder_result_budget", SecurityStage.DECODER_RESULT, f"{name} exceeds admitted/result bound", dimension=name)
    reject_transient_authority(result.metadata or {}, limits=limits, where="decoder result", stage=SecurityStage.DECODER_RESULT)


class DecoderBackend(Protocol):
    profile_name: str
    public_untrusted_ready: bool
    def decode(self, source: bytes, descriptor: MediaDescriptor) -> DecoderResult: ...


class DecoderBroker:
    """Preflight -> exact source -> isolated decode -> revalidate -> cache publish."""
    _COMMON = {
        "profile", "asset_id", "revision_digest", "source_digest",
        "predicted_decoded_bytes", "image_pixels", "audio_frames",
        "derivative_kind", "derivative_version", "metadata",
    }

    def __init__(
        self, backends: Mapping[str, DecoderBackend], *, limits: PhysicalLimits | None = None,
        telemetry: SecurityTelemetry | None = None, cache: DerivativeCache | None = None,
        source_provider: Callable[[AssetId, str, str], bytes] | None = None,
    ) -> None:
        self.backends = dict(backends)
        self.limits = limits or PhysicalLimits()
        self.telemetry = telemetry or SecurityTelemetry()
        self.cache = cache or DerivativeCache(self.limits)
        self.source_provider = source_provider
        self.worker_invocations = 0

    def _descriptor(self, payload: Mapping[str, Any], source_bytes: int) -> tuple[DecoderBackend, MediaDescriptor]:
        try:
            descriptor = MediaDescriptor(
                AssetId(payload["asset_id"]), payload["revision_digest"], payload["source_digest"],
                source_bytes, payload["predicted_decoded_bytes"], payload["image_pixels"], payload["audio_frames"],
                payload["derivative_kind"], payload["derivative_version"], payload["metadata"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PhysicalSecurityError("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "decode descriptor is invalid") from exc
        preflight_media(descriptor, self.limits)
        profile = payload.get("profile")
        backend = self.backends.get(profile)
        if backend is None or not backend.public_untrusted_ready:
            _fail("security.isolation_unavailable", SecurityStage.ISOLATION, "target profile cannot isolate public untrusted decode", profile=str(profile))
        return backend, descriptor

    def _run(self, backend: DecoderBackend, descriptor: MediaDescriptor, source: bytes, *, expose_cache_key: bool) -> Mapping[str, Any]:
        if len(source) != descriptor.source_bytes or hashlib.sha256(source).hexdigest() != descriptor.source_digest:
            _fail("security.source_digest", SecurityStage.DECODER_PREFLIGHT, "source bytes do not match protected source identity")
        self.worker_invocations += 1
        try:
            result = backend.decode(bytes(source), descriptor)
        except PhysicalSecurityError as exc:
            self.telemetry.record(exc.code, exc.stage, "deny")
            raise
        except Exception as exc:
            self.telemetry.record("security.decoder_failed", SecurityStage.ISOLATION, "deny")
            raise PhysicalSecurityError("security.decoder_failed", SecurityStage.ISOLATION, "isolated decoder failed without exposing privileged host detail") from exc
        validate_decoder_result(descriptor, result, self.limits)
        key = derivative_cache_key(descriptor, backend.profile_name)
        key_id = self.cache.publish(key, result.bytes)
        response: dict[str, Any] = {
            "asset_id": str(key.asset_id), "revision_digest": key.revision_digest,
            "target_profile": key.target_profile, "derivative_kind": key.derivative_kind,
            "derivative_version": key.derivative_version, "decoded_bytes": result.decoded_bytes,
            "derivative_digest": hashlib.sha256(result.bytes).hexdigest(),
        }
        if expose_cache_key:
            response["cache_key"] = key_id
        self.telemetry.record("security.decoder_allowed", SecurityStage.DECODER_RESULT, "allow")
        return response

    def decode_bytes(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "decode payload must be a mapping")
        reject_transient_authority(payload, limits=self.limits, where="decode payload")
        if set(payload) != self._COMMON | {"source"}:
            _fail("security.decoder_request_schema", SecurityStage.DECODER_PREFLIGHT, "decode payload has unknown or missing fields")
        source = payload["source"]
        if not isinstance(source, (bytes, bytearray)):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "source must be bytes")
        backend, descriptor = self._descriptor(payload, len(source))
        return self._run(backend, descriptor, bytes(source), expose_cache_key=True)

    def preflight_reference(self, payload: Mapping[str, Any]) -> tuple[DecoderBackend, MediaDescriptor]:
        if not isinstance(payload, Mapping):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "decode reference must be a mapping")
        reject_transient_authority(payload, limits=self.limits, where="decode reference")
        if set(payload) != self._COMMON | {"source_bytes"}:
            _fail("security.decoder_request_schema", SecurityStage.DECODER_PREFLIGHT, "decode reference has unknown or missing fields")
        source_bytes = payload["source_bytes"]
        if not isinstance(source_bytes, int) or isinstance(source_bytes, bool):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "source_bytes must be integer")
        return self._descriptor(payload, source_bytes)

    def target_for_reference(self, payload: Mapping[str, Any]) -> ServiceTarget:
        _backend, descriptor = self.preflight_reference(payload)
        return ServiceTarget(str(descriptor.asset_id), "decode", descriptor.source_bytes)

    def decode_reference(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        backend, descriptor = self.preflight_reference(payload)
        if self.source_provider is None:
            _fail("security.source_provider_missing", SecurityStage.ISOLATION, "trusted exact source provider is unavailable")
        try:
            source = self.source_provider(descriptor.asset_id, descriptor.revision_digest, descriptor.source_digest)
        except PhysicalSecurityError:
            raise
        except Exception as exc:
            raise PhysicalSecurityError("security.source_provider_failed", SecurityStage.ISOLATION, "trusted source provider failed without exposing host detail") from exc
        if not isinstance(source, (bytes, bytearray)):
            _fail("security.source_provider_type", SecurityStage.ISOLATION, "trusted source provider returned invalid type")
        return self._run(backend, descriptor, bytes(source), expose_cache_key=False)

    def host_adapter(self, capability_id: CapabilityId = CAP_MEDIA_DECODE) -> HostServiceAdapter:
        if self.source_provider is None:
            _fail("security.source_provider_missing", SecurityStage.ISOLATION, "host adapter requires exact trusted source provider")
        # TrustedHostServiceBoundary.execute rechecks the exact grant immediately
        # before decode_reference, so provider/worker access occurs only after R-016-04.
        return HostServiceAdapter("security.media_decode", capability_id, self.target_for_reference, self.decode_reference)


@dataclass(frozen=True)
class BrowserIsolationProfile:
    module_worker: bool = True
    fixed_maximum_wasm_memory: bool = True
    no_wasm_imports_except_memory: bool = True
    worker_connect_src_none: bool = True
    worker_src_self: bool = True
    javascript_bridge_disabled: bool = True
    decoder_module_pinned: bool = False

    @property
    def public_untrusted_ready(self) -> bool:
        return all(self.__dict__.values())


class BrowserWasmDecoder:
    """Trusted browser-worker transport. Real worker contract lives under security/web."""
    profile_name = "web-hardened"

    def __init__(self, transport: Callable[[bytes, MediaDescriptor], DecoderResult], profile: BrowserIsolationProfile) -> None:
        if not callable(transport) or not isinstance(profile, BrowserIsolationProfile):
            raise TypeError("browser decoder needs trusted transport and explicit profile")
        self._transport = transport
        self.profile = profile

    @property
    def public_untrusted_ready(self) -> bool:
        return self.profile.public_untrusted_ready

    def decode(self, source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
        if not self.public_untrusted_ready:
            _fail("security.web_profile_incomplete", SecurityStage.ISOLATION, "hardened web decoder profile is incomplete")
        return self._transport(bytes(source), descriptor)


@dataclass(frozen=True)
class LinuxSandboxStatus:
    os_linux: bool
    fork: bool
    no_new_privs: bool
    seccomp: bool
    landlock: bool
    rlimits: bool

    @property
    def ready(self) -> bool:
        return all(self.__dict__.values())


_PR_SET_NO_NEW_PRIVS = 38
_LANDLOCK_CREATE_RULESET_VERSION = 1
_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_RESTRICT_SELF = 446


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def _set_no_new_privs() -> None:
    if _libc().prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")


def _landlock_abi() -> int:
    if platform.system() != "Linux":
        return 0
    result = _libc().syscall(_SYS_LANDLOCK_CREATE_RULESET, 0, 0, _LANDLOCK_CREATE_RULESET_VERSION)
    return int(result) if result >= 1 else 0


def _apply_landlock_deny_all() -> None:
    abi = _landlock_abi()
    if abi < 1:
        raise OSError(errno.ENOSYS, "Landlock unavailable")
    rights = (1 << 13) - 1
    if abi >= 2:
        rights |= 1 << 13
    if abi >= 3:
        rights |= 1 << 14
    if abi >= 5:
        rights |= 1 << 15

    class RulesetAttr(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    attr = RulesetAttr(rights)
    libc = _libc()
    fd = libc.syscall(_SYS_LANDLOCK_CREATE_RULESET, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "Landlock ruleset creation failed")
    try:
        if libc.syscall(_SYS_LANDLOCK_RESTRICT_SELF, fd, 0) != 0:
            raise OSError(ctypes.get_errno(), "Landlock restrict_self failed")
    finally:
        os.close(fd)


def _seccomp_library() -> ctypes.CDLL | None:
    for name in ("libseccomp.so.2", "libseccomp.so"):
        try:
            return ctypes.CDLL(name, use_errno=True)
        except OSError:
            pass
    return None


def _apply_seccomp_allowlist() -> None:
    lib = _seccomp_library()
    if lib is None:
        raise OSError(errno.ENOSYS, "libseccomp unavailable")
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.restype = None
    ctx = lib.seccomp_init(ctypes.c_uint32(0x00050000 | errno.EPERM))
    if not ctx:
        raise OSError("seccomp_init failed")
    allowed = (
        b"read", b"write", b"close", b"fstat", b"newfstatat", b"lseek",
        b"mmap", b"mprotect", b"munmap", b"mremap", b"brk", b"madvise",
        b"rt_sigaction", b"rt_sigprocmask", b"rt_sigreturn", b"sigaltstack",
        b"futex", b"clock_gettime", b"gettimeofday", b"nanosleep",
        b"getpid", b"gettid", b"getrandom", b"uname", b"prlimit64",
        b"sched_yield", b"landlock_create_ruleset", b"landlock_restrict_self",
        b"exit", b"exit_group",
    )
    try:
        for name in allowed:
            number = lib.seccomp_syscall_resolve_name(name)
            if number >= 0 and lib.seccomp_rule_add(ctx, ctypes.c_uint32(0x7FFF0000), number, 0) != 0:
                raise OSError(ctypes.get_errno(), f"seccomp rule failed for {name!r}")
        if lib.seccomp_load(ctx) != 0:
            raise OSError(ctypes.get_errno(), "seccomp_load failed")
    finally:
        lib.seccomp_release(ctx)


def probe_linux_sandbox() -> LinuxSandboxStatus:
    linux = platform.system() == "Linux"
    return LinuxSandboxStatus(
        linux,
        hasattr(os, "fork"),
        linux and hasattr(_libc(), "prctl"),
        linux and _seccomp_library() is not None,
        linux and _landlock_abi() >= 1,
        all(hasattr(resource, name) for name in ("RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_NOFILE", "RLIMIT_FSIZE", "RLIMIT_NPROC")),
    )


class LinuxProcessDecoder:
    """Forked Linux decoder boundary; absent primitives make the profile unusable."""
    def __init__(self, decoder: Callable[[bytes, MediaDescriptor], DecoderResult], *, profile_name: str = "linux-native", limits: PhysicalLimits | None = None) -> None:
        if profile_name not in {"linux-native", "linux-headless"} or not callable(decoder):
            raise ValueError("Linux decoder needs native/headless profile and callable")
        self._decoder = decoder
        self.profile_name = profile_name
        self.limits = limits or PhysicalLimits()
        self.status = probe_linux_sandbox()

    @property
    def public_untrusted_ready(self) -> bool:
        return self.status.ready

    def _apply_limits(self) -> None:
        resource.setrlimit(resource.RLIMIT_AS, (self.limits.native_address_space_bytes,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (self.limits.native_cpu_seconds,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.limits.native_open_files,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.limits.native_output_bytes,) * 2)
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))

    def decode(self, source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
        if not self.public_untrusted_ready:
            _fail("security.linux_sandbox_unavailable", SecurityStage.ISOLATION, "Linux sandbox primitive missing")
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_fd)
                self._apply_limits()
                _set_no_new_privs()
                _apply_seccomp_allowlist()
                _apply_landlock_deny_all()
                result = self._decoder(bytes(source), descriptor)
                validate_decoder_result(descriptor, result, self.limits)
                body = encode_canonical_cbor({
                    "ok": True, "bytes": bytes(result.bytes), "decoded_bytes": result.decoded_bytes,
                    "image_pixels": result.image_pixels, "audio_frames": result.audio_frames,
                    "metadata": dict(result.metadata or {}),
                })
                if len(body) > self.limits.max_ipc_message_bytes:
                    os._exit(73)
                os.write(write_fd, struct.pack(">I", len(body)) + body)
                os._exit(0)
            except BaseException:
                try:
                    os.write(write_fd, struct.pack(">I", 0))
                except BaseException:
                    pass
                os._exit(72)
        os.close(write_fd)
        status = 0
        try:
            header = b""
            while len(header) < 4:
                chunk = os.read(read_fd, 4 - len(header))
                if not chunk:
                    break
                header += chunk
            body = b""
            if len(header) == 4:
                length = struct.unpack(">I", header)[0]
                if length > self.limits.max_ipc_message_bytes:
                    os.kill(pid, 9)
                    _fail("security.ipc_budget", SecurityStage.ISOLATION, "decoder worker response exceeds IPC limit")
                while len(body) < length:
                    chunk = os.read(read_fd, min(65536, length - len(body)))
                    if not chunk:
                        break
                    body += chunk
            _pid, status = os.waitpid(pid, 0)
        finally:
            os.close(read_fd)
        if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0 or not body:
            _fail("security.decoder_worker_failed", SecurityStage.ISOLATION, "sandboxed decoder worker failed")
        try:
            obj = decode_canonical_cbor(body, limits=DecodeLimits(max_bytes=self.limits.max_ipc_message_bytes, max_items=self.limits.max_metadata_nodes * 4))
        except Exception as exc:
            raise PhysicalSecurityError("security.decoder_worker_protocol", SecurityStage.ISOLATION, "sandboxed decoder returned invalid framed response") from exc
        if not isinstance(obj, dict) or set(obj) != {"ok", "bytes", "decoded_bytes", "image_pixels", "audio_frames", "metadata"} or obj["ok"] is not True:
            _fail("security.decoder_worker_protocol", SecurityStage.ISOLATION, "sandboxed decoder response schema invalid")
        return DecoderResult(bytes(obj["bytes"]), obj["decoded_bytes"], obj["image_pixels"], obj["audio_frames"], obj["metadata"])


@dataclass(frozen=True)
class Signature:
    key_id: str
    signature: bytes


@dataclass(frozen=True)
class RolePolicy:
    key_ids: frozenset[str]
    threshold: int
    def __post_init__(self) -> None:
        if not self.key_ids or not isinstance(self.threshold, int) or isinstance(self.threshold, bool) or self.threshold < 1 or self.threshold > len(self.key_ids):
            raise ValueError("invalid trust role policy")


@dataclass(frozen=True)
class RootMetadata:
    version: int
    expires_at: int
    keys: Mapping[str, bytes]
    roles: Mapping[str, RolePolicy]
    def __post_init__(self) -> None:
        if set(self.roles) != {"root", "targets", "snapshot", "timestamp"} or self.version < 1 or self.expires_at < 1:
            raise ValueError("invalid root metadata")
        for role in self.roles.values():
            if not role.key_ids <= set(self.keys):
                raise ValueError("role refers to unknown key")


@dataclass(frozen=True)
class TargetRecord:
    package_revision_id: PackageRevisionId
    length: int
    sha256: str


@dataclass(frozen=True)
class RoleEnvelope:
    role: str
    version: int
    expires_at: int
    body: Mapping[str, Any]
    signatures: tuple[Signature, ...]
    def signing_bytes(self) -> bytes:
        return encode_canonical_cbor({"role": self.role, "version": self.version, "expires_at": self.expires_at, "body": dict(self.body)})


def root_metadata_body(root: RootMetadata) -> Mapping[str, Any]:
    return {
        "keys": {key_id: bytes(value) for key_id, value in sorted(root.keys.items())},
        "roles": {role: {"key_ids": sorted(policy.key_ids), "threshold": policy.threshold} for role, policy in sorted(root.roles.items())},
    }


def root_metadata_from_body(version: int, expires_at: int, body: Mapping[str, Any]) -> RootMetadata:
    if not isinstance(body, Mapping) or set(body) != {"keys", "roles"}:
        _fail("security.root_schema", SecurityStage.TRUST, "root metadata body schema invalid")
    keys, roles = body["keys"], body["roles"]
    if not isinstance(keys, Mapping) or not isinstance(roles, Mapping) or len(keys) > 64:
        _fail("security.root_schema", SecurityStage.TRUST, "root keys/roles invalid")
    parsed_keys: dict[str, bytes] = {}
    for key_id, public_key in keys.items():
        if not isinstance(key_id, str) or not key_id or len(key_id.encode()) > 128 or not isinstance(public_key, bytes) or len(public_key) > 8192:
            _fail("security.root_schema", SecurityStage.TRUST, "root key entry invalid")
        parsed_keys[key_id] = bytes(public_key)
    parsed_roles: dict[str, RolePolicy] = {}
    for role, raw in roles.items():
        if role not in {"root", "targets", "snapshot", "timestamp"} or not isinstance(raw, Mapping) or set(raw) != {"key_ids", "threshold"}:
            _fail("security.root_schema", SecurityStage.TRUST, "root role policy invalid")
        ids = raw["key_ids"]
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            _fail("security.root_schema", SecurityStage.TRUST, "root role key ids invalid")
        try:
            parsed_roles[role] = RolePolicy(frozenset(ids), raw["threshold"])
        except (TypeError, ValueError) as exc:
            raise PhysicalSecurityError("security.root_schema", SecurityStage.TRUST, "root role policy invalid") from exc
    try:
        return RootMetadata(version, expires_at, parsed_keys, parsed_roles)
    except (TypeError, ValueError) as exc:
        raise PhysicalSecurityError("security.root_schema", SecurityStage.TRUST, "root metadata invalid") from exc


def parse_role_envelope(data: bytes, *, limits: PhysicalLimits | None = None) -> RoleEnvelope:
    limits = limits or PhysicalLimits()
    raw = bytes(data)
    if len(raw) > limits.max_ipc_message_bytes:
        _fail("security.trust_budget", SecurityStage.TRUST, "repository metadata exceeds byte bound")
    try:
        obj = decode_canonical_cbor(raw, limits=DecodeLimits(
            max_bytes=limits.max_ipc_message_bytes, max_depth=limits.max_metadata_depth,
            max_items=limits.max_metadata_nodes * 8, max_string_bytes=limits.max_metadata_string_bytes,
        ))
    except Exception as exc:
        raise PhysicalSecurityError("security.trust_parse", SecurityStage.TRUST, "repository metadata is not bounded canonical CBOR") from exc
    if not isinstance(obj, dict) or set(obj) != {"role", "version", "expires_at", "body", "signatures"}:
        _fail("security.trust_schema", SecurityStage.TRUST, "repository metadata envelope schema invalid")
    if obj["role"] not in {"root", "targets", "snapshot", "timestamp"}:
        _fail("security.trust_role", SecurityStage.TRUST, "unknown repository metadata role")
    if not isinstance(obj["version"], int) or isinstance(obj["version"], bool) or obj["version"] < 1:
        _fail("security.trust_schema", SecurityStage.TRUST, "metadata version invalid")
    if not isinstance(obj["expires_at"], int) or isinstance(obj["expires_at"], bool) or obj["expires_at"] < 1 or not isinstance(obj["body"], dict):
        _fail("security.trust_schema", SecurityStage.TRUST, "metadata expiry/body invalid")
    rows = obj["signatures"]
    if not isinstance(rows, list) or len(rows) > 64:
        _fail("security.trust_budget", SecurityStage.TRUST, "metadata signatures exceed bound")
    signatures: list[Signature] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"key_id", "signature"}:
            _fail("security.trust_schema", SecurityStage.TRUST, "signature record schema invalid")
        key_id, signature = row["key_id"], row["signature"]
        if not isinstance(key_id, str) or not key_id or len(key_id.encode()) > 128 or not isinstance(signature, bytes) or len(signature) > 256 or key_id in seen:
            _fail("security.trust_schema", SecurityStage.TRUST, "signature record invalid or duplicate")
        seen.add(key_id); signatures.append(Signature(key_id, bytes(signature)))
    reject_transient_authority(obj["body"], limits=limits, where="repository metadata", stage=SecurityStage.TRUST)
    return RoleEnvelope(obj["role"], obj["version"], obj["expires_at"], obj["body"], tuple(signatures))


def encode_role_envelope(envelope: RoleEnvelope) -> bytes:
    return encode_canonical_cbor({
        "role": envelope.role, "version": envelope.version, "expires_at": envelope.expires_at,
        "body": dict(envelope.body),
        "signatures": [{"key_id": sig.key_id, "signature": bytes(sig.signature)} for sig in envelope.signatures],
    })


class SignatureVerifier(Protocol):
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class OpenSslEd25519Verifier:
    """Verification-only Ed25519 adapter; runtime contains no private-key operation."""
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        with tempfile.TemporaryDirectory(prefix="splashmx-ed25519-") as tmp:
            root = Path(tmp); key = root / "public.pem"; msg = root / "message.bin"; sig = root / "signature.bin"
            key.write_bytes(bytes(public_key)); msg.write_bytes(bytes(message)); sig.write_bytes(bytes(signature))
            try:
                result = subprocess.run(
                    ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(key), "-in", str(msg), "-sigfile", str(sig)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False
            return result.returncode == 0


@dataclass(frozen=True)
class RepositoryTrustState:
    root: RootMetadata
    root_version: int
    targets_version: int = 0
    snapshot_version: int = 0
    timestamp_version: int = 0
    targets_metadata_digest: str | None = None


class RepositoryTrust:
    """Bounded TUF-compatible root/targets/snapshot/timestamp trust state."""
    def __init__(self, state: RepositoryTrustState, verifier: SignatureVerifier | None = None) -> None:
        if state.root_version != state.root.version:
            raise ValueError("root state version mismatch")
        self.state = state
        self.verifier = verifier or OpenSslEd25519Verifier()

    def _verify_threshold(self, envelope: RoleEnvelope, root: RootMetadata, role: str) -> None:
        policy = root.roles[role]
        good: set[str] = set()
        for sig in envelope.signatures:
            if sig.key_id in good or sig.key_id not in policy.key_ids:
                continue
            key = root.keys.get(sig.key_id)
            if key is not None and self.verifier.verify(key, envelope.signing_bytes(), sig.signature):
                good.add(sig.key_id)
        if len(good) < policy.threshold:
            _fail("security.trust_threshold", SecurityStage.TRUST, f"{role} signature threshold not met")

    @staticmethod
    def _fresh(envelope: RoleEnvelope, now: int) -> None:
        if not isinstance(now, int) or isinstance(now, bool) or now < 0:
            _fail("security.trust_time", SecurityStage.TRUST, "trust time invalid")
        if envelope.expires_at <= now:
            _fail("security.trust_expired", SecurityStage.TRUST, f"{envelope.role} metadata expired/frozen")

    def rotate_root(self, candidate: RootMetadata, envelope: RoleEnvelope, *, now: int) -> None:
        current = self.state.root
        if candidate.version != current.version + 1 or envelope.role != "root" or envelope.version != candidate.version or envelope.expires_at != candidate.expires_at:
            _fail("security.root_version", SecurityStage.TRUST, "root rotation must be sequential and exactly bound")
        self._fresh(envelope, now)
        self._verify_threshold(envelope, current, "root")
        self._verify_threshold(envelope, candidate, "root")
        if candidate.expires_at <= now or envelope.body != root_metadata_body(candidate):
            _fail("security.root_binding", SecurityStage.TRUST, "signed root envelope does not bind live candidate root")
        self.state = RepositoryTrustState(
            candidate, candidate.version, self.state.targets_version, self.state.snapshot_version,
            self.state.timestamp_version, self.state.targets_metadata_digest,
        )

    def refresh(self, targets: RoleEnvelope, snapshot: RoleEnvelope, timestamp: RoleEnvelope, *, now: int) -> None:
        root = self.state.root
        if root.expires_at <= now:
            _fail("security.trust_expired", SecurityStage.TRUST, "trusted root expired")
        for envelope, role in ((targets, "targets"), (snapshot, "snapshot"), (timestamp, "timestamp")):
            if envelope.role != role:
                _fail("security.trust_role", SecurityStage.TRUST, "repository metadata role mismatch")
            self._fresh(envelope, now); self._verify_threshold(envelope, root, role)
        if targets.version < self.state.targets_version or snapshot.version < self.state.snapshot_version or timestamp.version < self.state.timestamp_version:
            _fail("security.trust_rollback", SecurityStage.TRUST, "repository metadata version rolled back")
        if set(snapshot.body) != {"targets_version", "targets_sha256"} or set(timestamp.body) != {"snapshot_version", "snapshot_sha256"}:
            _fail("security.trust_mix_match", SecurityStage.TRUST, "snapshot/timestamp metadata schema is not exact")
        targets_digest = hashlib.sha256(encode_role_envelope(targets)).hexdigest()
        snapshot_digest = hashlib.sha256(encode_role_envelope(snapshot)).hexdigest()
        if snapshot.body["targets_version"] != targets.version or snapshot.body["targets_sha256"] != targets_digest:
            _fail("security.trust_mix_match", SecurityStage.TRUST, "snapshot does not bind exact targets metadata")
        if timestamp.body["snapshot_version"] != snapshot.version or timestamp.body["snapshot_sha256"] != snapshot_digest:
            _fail("security.trust_mix_match", SecurityStage.TRUST, "timestamp does not bind exact snapshot metadata")
        self.state = RepositoryTrustState(root, root.version, targets.version, snapshot.version, timestamp.version, targets_digest)

    def verify_target(self, targets: RoleEnvelope, revision_id: PackageRevisionId, package_bytes: bytes) -> None:
        digest = hashlib.sha256(encode_role_envelope(targets)).hexdigest()
        if targets.version != self.state.targets_version or self.state.targets_metadata_digest is None or digest != self.state.targets_metadata_digest:
            _fail("security.trust_uncommitted_targets", SecurityStage.TRUST, "target lookup must use exact refreshed targets metadata")
        records = targets.body.get("targets")
        if set(targets.body) != {"targets"} or not isinstance(records, list) or len(records) > 100_000:
            _fail("security.trust_targets", SecurityStage.TRUST, "targets metadata exact record set invalid")
        expected_digest = hashlib.sha256(package_bytes).hexdigest()
        for raw in records:
            if not isinstance(raw, Mapping) or set(raw) != {"package_revision_id", "length", "sha256"}:
                _fail("security.trust_targets", SecurityStage.TRUST, "target record schema invalid")
            if raw["package_revision_id"] == str(revision_id):
                if raw["length"] != len(package_bytes) or raw["sha256"] != expected_digest:
                    _fail("security.trust_target_mismatch", SecurityStage.TRUST, "trusted target does not bind exact package bytes")
                return
        _fail("security.trust_target_missing", SecurityStage.TRUST, "requested exact package revision is not trusted")


def trust_signature_grants_capability(*_: Any, **__: Any) -> bool:
    return False


def validate_protected_asset_candidate(candidate: Mapping[str, Any]) -> None:
    if set(candidate) != PROTECTED_ASSET_FIELDS:
        _fail("security.protected_asset_partial", SecurityStage.SEMANTIC, "protected Asset replacement must carry complete canonical revision")


class SecurityBoundary:
    """Trust exact target bytes before bounded SPB1 parsing/semantic activation."""
    def __init__(self, *, limits: PhysicalLimits | None = None, telemetry: SecurityTelemetry | None = None) -> None:
        self.limits = limits or PhysicalLimits()
        self.telemetry = telemetry or SecurityTelemetry()

    def trusted_package(self, trust: RepositoryTrust, targets: RoleEnvelope, revision_id: PackageRevisionId, package_bytes: bytes) -> ParsedBundle:
        try:
            trust.verify_target(targets, revision_id, package_bytes)
            parsed = preflight_spb1(package_bytes, self.limits)
        except PhysicalSecurityError as exc:
            self.telemetry.record(exc.code, exc.stage, "deny")
            raise
        self.telemetry.record("security.package_verified", SecurityStage.CONTAINER, "allow")
        return parsed


__all__ = [
    "BrowserIsolationProfile", "BrowserWasmDecoder", "CAP_MEDIA_DECODE", "DecoderBroker",
    "DecoderResult", "DerivativeCache", "DerivativeCacheKey", "LinuxProcessDecoder",
    "LinuxSandboxStatus", "MediaDescriptor", "OpenSslEd25519Verifier", "PhysicalLimits",
    "PhysicalSecurityError", "RepositoryTrust", "RepositoryTrustState", "RoleEnvelope",
    "RolePolicy", "RootMetadata", "SecurityBoundary", "SecurityEvent", "SecurityStage",
    "SecurityTelemetry", "Signature", "TargetRecord", "derivative_cache_key",
    "encode_role_envelope", "parse_role_envelope", "preflight_media", "preflight_spb1",
    "probe_linux_sandbox", "reject_transient_authority", "root_metadata_body",
    "root_metadata_from_body", "trust_signature_grants_capability", "validate_decoder_result",
    "validate_protected_asset_candidate",
]
