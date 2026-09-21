"""SMX-040 production physical security boundary.

This module turns the SMX-039 mechanism selection into executable production
boundaries. It deliberately keeps semantic authority in the existing
capability/package/runtime layers: cryptographic trust authenticates bytes,
sandboxing contains hostile decoders, and neither creates a capability.
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
from typing import Any, Callable, Mapping, Protocol, Sequence

from splashmx.canonical.core import AssetId
from splashmx.canonical.serialization import DecodeLimits, decode_canonical_cbor, encode_canonical_cbor
from splashmx.packages.bundle import BundleLimits, SPB1_MAGIC, ParsedBundle, parse_spb1
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
    """Stable typed failure. Raw host/crypto/decoder exceptions remain internal."""

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
    """Bounded safe telemetry: stable codes only, never raw privileged exception text."""

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
    native_address_space_bytes: int = 768 * 1024 * 1024
    native_cpu_seconds: int = 5
    native_open_files: int = 16
    native_output_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

def preflight_spb1(data: bytes, limits: PhysicalLimits | None = None) -> ParsedBundle:
    """R-016-01 production package boundary: pathless SPB1 only, no extraction."""

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

def reject_transient_authority(value: Any, *, limits: PhysicalLimits | None = None, where: str = "security message") -> None:
    """Independent recursive R-016-02 enforcement for physical-boundary messages."""

    limits = limits or PhysicalLimits()
    counter = [0]

    def walk(item: Any, depth: int) -> None:
        counter[0] += 1
        if counter[0] > limits.max_metadata_nodes or depth > limits.max_metadata_depth:
            _fail("security.message_budget", SecurityStage.DECODER_PREFLIGHT, f"{where} exceeds structural bounds")
        if item is None or isinstance(item, (bool, int)):
            return
        if isinstance(item, float):
            if item != item or item in (float("inf"), float("-inf")):
                _fail("security.message_type", SecurityStage.DECODER_PREFLIGHT, f"{where} contains non-finite number")
            return
        if isinstance(item, (bytes, bytearray)):
            if len(item) > limits.max_ipc_message_bytes:
                _fail("security.message_budget", SecurityStage.DECODER_PREFLIGHT, f"{where} byte value exceeds IPC limit")
            return
        if isinstance(item, str):
            if len(item.encode("utf-8")) > limits.max_metadata_string_bytes:
                _fail("security.message_budget", SecurityStage.DECODER_PREFLIGHT, f"{where} string exceeds limit")
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child, depth + 1)
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    _fail("security.message_type", SecurityStage.DECODER_PREFLIGHT, f"{where} keys must be strings")
                if _normalise_field(key) in FORBIDDEN_AUTHORITY_FIELDS:
                    _fail("security.serialized_authority", SecurityStage.DECODER_PREFLIGHT, "transient host/capability authority cannot cross physical boundary")
                walk(child, depth + 1)
            return
        _fail("security.message_type", SecurityStage.DECODER_PREFLIGHT, f"{where} contains unsupported value type")

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
    if result.decoded_bytes != len(result.bytes):
        _fail("security.decoder_result_length", SecurityStage.DECODER_RESULT, "decoder result length does not match declaration")
    dims = (
        ("decoded_bytes", result.decoded_bytes, limits.max_decoded_bytes, descriptor.predicted_decoded_bytes),
        ("image_pixels", result.image_pixels, limits.max_image_pixels, descriptor.image_pixels or limits.max_image_pixels),
        ("audio_frames", result.audio_frames, limits.max_audio_frames, descriptor.audio_frames or limits.max_audio_frames),
    )
    for name, value, hard_max, declared_max in dims:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > hard_max or value > declared_max:
            _fail("security.decoder_result_budget", SecurityStage.DECODER_RESULT, f"{name} exceeds admitted/result bound", dimension=name)
    reject_transient_authority(result.metadata or {}, limits=limits, where="decoder result")

class DecoderBackend(Protocol):
    profile_name: str
    public_untrusted_ready: bool

    def decode(self, source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
        ...

class DecoderBroker:
    """Preflight -> isolated decode -> result validation. No cache publish on failure."""

    def __init__(self, backends: Mapping[str, DecoderBackend], *, limits: PhysicalLimits | None = None, telemetry: SecurityTelemetry | None = None) -> None:
        self.backends = dict(backends)
        self.limits = limits or PhysicalLimits()
        self.telemetry = telemetry or SecurityTelemetry()
        self.worker_invocations = 0

    def preflight(self, payload: Mapping[str, Any]) -> tuple[DecoderBackend, MediaDescriptor, bytes]:
        if not isinstance(payload, Mapping):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "decode payload must be a mapping")
        reject_transient_authority(payload, limits=self.limits, where="decode payload")
        allowed = {
            "profile", "asset_id", "revision_digest", "source_digest", "source",
            "predicted_decoded_bytes", "image_pixels", "audio_frames",
            "derivative_kind", "derivative_version", "metadata",
        }
        if set(payload) != allowed:
            _fail("security.decoder_request_schema", SecurityStage.DECODER_PREFLIGHT, "decode payload has unknown or missing fields")
        source = payload["source"]
        if not isinstance(source, (bytes, bytearray)):
            _fail("security.decoder_request_type", SecurityStage.DECODER_PREFLIGHT, "source must be immutable bytes")
        source = bytes(source)
        descriptor = MediaDescriptor(
            AssetId(payload["asset_id"]),
            payload["revision_digest"],
            payload["source_digest"],
            len(source),
            payload["predicted_decoded_bytes"],
            payload["image_pixels"],
            payload["audio_frames"],
            payload["derivative_kind"],
            payload["derivative_version"],
            payload["metadata"],
        )
        if hashlib.sha256(source).hexdigest() != descriptor.source_digest:
            _fail("security.source_digest", SecurityStage.DECODER_PREFLIGHT, "source bytes do not match protected source digest")
        preflight_media(descriptor, self.limits)
        profile = payload["profile"]
        backend = self.backends.get(profile)
        if backend is None or not backend.public_untrusted_ready:
            _fail("security.isolation_unavailable", SecurityStage.ISOLATION, "target profile cannot isolate public untrusted decode", profile=str(profile))
        return backend, descriptor, source

    def target_for_payload(self, payload: Mapping[str, Any]) -> ServiceTarget:
        _backend, descriptor, _source = self.preflight(payload)
        return ServiceTarget(str(descriptor.asset_id), "decode", descriptor.source_bytes)

    def decode_payload(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        backend, descriptor, source = self.preflight(payload)
        self.worker_invocations += 1
        try:
            result = backend.decode(source, descriptor)
        except PhysicalSecurityError:
            raise
        except Exception as exc:
            raise PhysicalSecurityError(
                "security.decoder_failed", SecurityStage.ISOLATION,
                "isolated decoder failed without exposing privileged host detail",
            ) from exc
        validate_decoder_result(descriptor, result, self.limits)
        key = derivative_cache_key(descriptor, backend.profile_name)
        return {
            "asset_id": str(key.asset_id),
            "revision_digest": key.revision_digest,
            "target_profile": key.target_profile,
            "derivative_kind": key.derivative_kind,
            "derivative_version": key.derivative_version,
            "decoded_bytes": result.decoded_bytes,
            "bytes": bytes(result.bytes),
        }

    def host_adapter(self, capability_id: CapabilityId = CAP_MEDIA_DECODE) -> HostServiceAdapter:
        # TrustedHostServiceBoundary performs the final R-016-04 authorization
        # immediately before invoke(), so a revoke/expiry after admission wins.
        return HostServiceAdapter(
            "security.media_decode",
            capability_id,
            self.target_for_payload,
            self.decode_payload,
        )

@dataclass(frozen=True)
class BrowserIsolationProfile:
    module_worker: bool = True
    fixed_maximum_wasm_memory: bool = True
    no_wasm_imports: bool = True
    worker_connect_src_none: bool = True
    worker_src_self: bool = True
    javascript_bridge_disabled: bool = True

    @property
    def public_untrusted_ready(self) -> bool:
        return all(self.__dict__.values())

class BrowserWasmDecoder:
    """Trusted bridge for the hardened module Worker/WASM implementation.

    Actual browser execution lives in ``security/web/decoder_worker.mjs``. Python
    tests use an injected transport so host authorization/order stays executable
    without pretending a Python callback is a browser sandbox.
    """

    profile_name = "web-hardened"

    def __init__(self, transport: Callable[[bytes, MediaDescriptor], DecoderResult], profile: BrowserIsolationProfile) -> None:
        if not isinstance(profile, BrowserIsolationProfile):
            raise TypeError("public web decoder requires an explicit hardened isolation profile")
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

# Linux constants used only after an explicit Linux target check.
_PR_SET_NO_NEW_PRIVS = 38
_LANDLOCK_CREATE_RULESET_VERSION = 1
_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_RESTRICT_SELF = 446

def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)

def _set_no_new_privs() -> None:
    libc = _libc()
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")

def _landlock_abi() -> int:
    if platform.system() != "Linux":
        return 0
    libc = _libc()
    result = libc.syscall(_SYS_LANDLOCK_CREATE_RULESET, 0, 0, _LANDLOCK_CREATE_RULESET_VERSION)
    return int(result) if result >= 1 else 0

def _apply_landlock_deny_all() -> None:
    abi = _landlock_abi()
    if abi < 1:
        raise OSError(errno.ENOSYS, "Landlock unavailable")
    rights = (1 << 13) - 1
    if abi >= 2:
        rights |= 1 << 13  # REFER
    if abi >= 3:
        rights |= 1 << 14  # TRUNCATE
    if abi >= 5:
        rights |= 1 << 15  # IOCTL_DEV
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
            continue
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
    ctx = lib.seccomp_init(ctypes.c_uint32(0x00050000 | errno.EPERM))  # SCMP_ACT_ERRNO(EPERM)
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
    has_fork = hasattr(os, "fork")
    nnp = linux and hasattr(_libc(), "prctl")
    seccomp = linux and _seccomp_library() is not None
    landlock = linux and _landlock_abi() >= 1
    rlimits = all(hasattr(resource, name) for name in ("RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_NOFILE", "RLIMIT_FSIZE", "RLIMIT_NPROC"))
    return LinuxSandboxStatus(linux, has_fork, nnp, seccomp, landlock, rlimits)

class LinuxProcessDecoder:
    """Actual forked Linux decoder boundary with fail-closed primitive probing.

    The decoder callable executes only after no_new_privs, deny-all Landlock,
    rlimits and a seccomp allowlist are installed. Missing primitives make
    ``public_untrusted_ready`` false; there is no in-process fallback.
    """

    def __init__(self, decoder: Callable[[bytes, MediaDescriptor], DecoderResult], *, profile_name: str = "linux-native", limits: PhysicalLimits | None = None) -> None:
        if profile_name not in {"linux-native", "linux-headless"}:
            raise ValueError("Linux decoder profile must be native or headless")
        self._decoder = decoder
        self.profile_name = profile_name
        self.limits = limits or PhysicalLimits()
        self.status = probe_linux_sandbox()

    @property
    def public_untrusted_ready(self) -> bool:
        return self.status.ready

    def _apply_limits(self) -> None:
        resource.setrlimit(resource.RLIMIT_AS, (self.limits.native_address_space_bytes, self.limits.native_address_space_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (self.limits.native_cpu_seconds, self.limits.native_cpu_seconds))
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.limits.native_open_files, self.limits.native_open_files))
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.limits.native_output_bytes, self.limits.native_output_bytes))
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
                    "ok": True,
                    "bytes": bytes(result.bytes),
                    "decoded_bytes": result.decoded_bytes,
                    "image_pixels": result.image_pixels,
                    "audio_frames": result.audio_frames,
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
        if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0 or len(body) == 0:
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
        if set(self.roles) != {"root", "targets", "snapshot", "timestamp"}:
            raise ValueError("root metadata must define all four TUF-compatible roles")
        if self.version < 1 or self.expires_at < 1:
            raise ValueError("root version/expiry invalid")
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
        "roles": {
            role: {"key_ids": sorted(policy.key_ids), "threshold": policy.threshold}
            for role, policy in sorted(root.roles.items())
        },
    }

def root_metadata_from_body(version: int, expires_at: int, body: Mapping[str, Any]) -> RootMetadata:
    if not isinstance(body, Mapping) or set(body) != {"keys", "roles"}:
        _fail("security.root_schema", SecurityStage.TRUST, "root metadata body schema invalid")
    keys = body["keys"]
    roles = body["roles"]
    if not isinstance(keys, Mapping) or not isinstance(roles, Mapping):
        _fail("security.root_schema", SecurityStage.TRUST, "root keys/roles must be mappings")
    if len(keys) > 64:
        _fail("security.trust_budget", SecurityStage.TRUST, "root key count exceeds bound")
    parsed_keys: dict[str, bytes] = {}
    for key_id, public_key in keys.items():
        if not isinstance(key_id, str) or not key_id or len(key_id.encode("utf-8")) > 128 or not isinstance(public_key, bytes) or len(public_key) > 8192:
            _fail("security.root_schema", SecurityStage.TRUST, "root key entry invalid")
        parsed_keys[key_id] = bytes(public_key)
    parsed_roles: dict[str, RolePolicy] = {}
    for role, raw in roles.items():
        if role not in {"root", "targets", "snapshot", "timestamp"} or not isinstance(raw, Mapping) or set(raw) != {"key_ids", "threshold"}:
            _fail("security.root_schema", SecurityStage.TRUST, "root role policy invalid")
        ids = raw["key_ids"]
        threshold = raw["threshold"]
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            _fail("security.root_schema", SecurityStage.TRUST, "root role key ids invalid")
        parsed_roles[role] = RolePolicy(frozenset(ids), threshold)
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
        obj = decode_canonical_cbor(
            raw,
            limits=DecodeLimits(
                max_bytes=limits.max_ipc_message_bytes,
                max_depth=limits.max_metadata_depth,
                max_items=limits.max_metadata_nodes * 8,
                max_string_bytes=limits.max_metadata_string_bytes,
            ),
        )
    except Exception as exc:
        raise PhysicalSecurityError("security.trust_parse", SecurityStage.TRUST, "repository metadata is not bounded canonical CBOR") from exc
    if not isinstance(obj, dict) or set(obj) != {"role", "version", "expires_at", "body", "signatures"}:
        _fail("security.trust_schema", SecurityStage.TRUST, "repository metadata envelope schema invalid")
    role, version, expires_at = obj["role"], obj["version"], obj["expires_at"]
    if role not in {"root", "targets", "snapshot", "timestamp"}:
        _fail("security.trust_role", SecurityStage.TRUST, "unknown repository metadata role")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        _fail("security.trust_schema", SecurityStage.TRUST, "metadata version invalid")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool) or expires_at < 1:
        _fail("security.trust_schema", SecurityStage.TRUST, "metadata expiry invalid")
    if not isinstance(obj["body"], dict):
        _fail("security.trust_schema", SecurityStage.TRUST, "metadata body must be a mapping")
    signatures = obj["signatures"]
    if not isinstance(signatures, list) or len(signatures) > 64:
        _fail("security.trust_budget", SecurityStage.TRUST, "metadata signatures exceed bound")
    parsed: list[Signature] = []
    seen: set[str] = set()
    for row in signatures:
        if not isinstance(row, dict) or set(row) != {"key_id", "signature"}:
            _fail("security.trust_schema", SecurityStage.TRUST, "signature record schema invalid")
        key_id, signature = row["key_id"], row["signature"]
        if not isinstance(key_id, str) or not key_id or len(key_id.encode("utf-8")) > 128 or not isinstance(signature, bytes) or len(signature) > 256:
            _fail("security.trust_schema", SecurityStage.TRUST, "signature record invalid")
        if key_id in seen:
            _fail("security.trust_schema", SecurityStage.TRUST, "duplicate signature key id")
        seen.add(key_id)
        parsed.append(Signature(key_id, bytes(signature)))
    reject_transient_authority(obj["body"], limits=limits, where="repository metadata")
    return RoleEnvelope(role, version, expires_at, obj["body"], tuple(parsed))

def encode_role_envelope(envelope: RoleEnvelope) -> bytes:
    return encode_canonical_cbor({
        "role": envelope.role,
        "version": envelope.version,
        "expires_at": envelope.expires_at,
        "body": dict(envelope.body),
        "signatures": [
            {"key_id": sig.key_id, "signature": bytes(sig.signature)}
            for sig in envelope.signatures
        ],
    })

class SignatureVerifier(Protocol):
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        ...

class OpenSslEd25519Verifier:
    """Concrete verification-only Ed25519 adapter; no private-key operation exists."""

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        with tempfile.TemporaryDirectory(prefix="splashmx-ed25519-") as tmp:
            root = Path(tmp)
            key_path = root / "public.pem"
            msg_path = root / "message.bin"
            sig_path = root / "signature.bin"
            key_path.write_bytes(bytes(public_key))
            msg_path.write_bytes(bytes(message))
            sig_path.write_bytes(bytes(signature))
            proc = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(key_path), "-in", str(msg_path), "-sigfile", str(sig_path)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=5,
            )
            return proc.returncode == 0

@dataclass(frozen=True)
class RepositoryTrustState:
    root: RootMetadata
    root_version: int
    targets_version: int = 0
    snapshot_version: int = 0
    timestamp_version: int = 0
    targets_metadata_digest: str | None = None

class RepositoryTrust:
    """Small TUF-compatible four-role state machine for exact package targets."""

    def __init__(self, state: RepositoryTrustState, verifier: SignatureVerifier | None = None) -> None:
        self.state = state
        self.verifier = verifier or OpenSslEd25519Verifier()

    def _verify_threshold(self, envelope: RoleEnvelope, root: RootMetadata, role: str) -> None:
        policy = root.roles[role]
        payload = envelope.signing_bytes()
        good: set[str] = set()
        for sig in envelope.signatures:
            if sig.key_id in good or sig.key_id not in policy.key_ids:
                continue
            key = root.keys.get(sig.key_id)
            if key is not None and self.verifier.verify(key, payload, sig.signature):
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
        if candidate.version != current.version + 1 or envelope.role != "root" or envelope.version != candidate.version:
            _fail("security.root_version", SecurityStage.TRUST, "root rotation must be sequential and self-consistent")
        self._fresh(envelope, now)
        self._verify_threshold(envelope, current, "root")
        self._verify_threshold(envelope, candidate, "root")
        if candidate.expires_at <= now:
            _fail("security.trust_expired", SecurityStage.TRUST, "candidate root expired")
        if envelope.body != root_metadata_body(candidate):
            _fail("security.root_binding", SecurityStage.TRUST, "signed root envelope does not bind candidate root")
        self.state = RepositoryTrustState(
            candidate, candidate.version, self.state.targets_version,
            self.state.snapshot_version, self.state.timestamp_version,
            self.state.targets_metadata_digest,
        )

    def refresh(self, targets: RoleEnvelope, snapshot: RoleEnvelope, timestamp: RoleEnvelope, *, now: int) -> None:
        root = self.state.root
        if root.expires_at <= now:
            _fail("security.trust_expired", SecurityStage.TRUST, "trusted root expired")
        envelopes = ((targets, "targets"), (snapshot, "snapshot"), (timestamp, "timestamp"))
        for envelope, role in envelopes:
            if envelope.role != role:
                _fail("security.trust_role", SecurityStage.TRUST, "repository metadata role mismatch")
            self._fresh(envelope, now)
            self._verify_threshold(envelope, root, role)
        if targets.version < self.state.targets_version or snapshot.version < self.state.snapshot_version or timestamp.version < self.state.timestamp_version:
            _fail("security.trust_rollback", SecurityStage.TRUST, "repository metadata version rolled back")
        if snapshot.body.get("targets_version") != targets.version or timestamp.body.get("snapshot_version") != snapshot.version:
            _fail("security.trust_mix_match", SecurityStage.TRUST, "repository metadata set is incoherent")
        self.state = RepositoryTrustState(
            root, root.version, targets.version, snapshot.version, timestamp.version,
            hashlib.sha256(targets.signing_bytes()).hexdigest(),
        )

    def verify_target(self, targets: RoleEnvelope, revision_id: PackageRevisionId, package_bytes: bytes) -> None:
        if (
            targets.version != self.state.targets_version
            or self.state.targets_metadata_digest is None
            or hashlib.sha256(targets.signing_bytes()).hexdigest() != self.state.targets_metadata_digest
        ):
            _fail("security.trust_uncommitted_targets", SecurityStage.TRUST, "target lookup must use the exact refreshed targets metadata")
        records = targets.body.get("targets")
        if not isinstance(records, list):
            _fail("security.trust_targets", SecurityStage.TRUST, "targets metadata missing exact records")
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
        _fail("security.protected_asset_partial", SecurityStage.SEMANTIC, "protected Asset replacement must carry the complete canonical revision")

class SecurityBoundary:
    """Production orchestrator for trust -> container -> decoder seams."""

    def __init__(self, *, limits: PhysicalLimits | None = None, telemetry: SecurityTelemetry | None = None) -> None:
        self.limits = limits or PhysicalLimits()
        self.telemetry = telemetry or SecurityTelemetry()

    def trusted_package(self, trust: RepositoryTrust, targets: RoleEnvelope, revision_id: PackageRevisionId, package_bytes: bytes) -> ParsedBundle:
        trust.verify_target(targets, revision_id, package_bytes)
        parsed = preflight_spb1(package_bytes, self.limits)
        self.telemetry.record("security.package_verified", SecurityStage.CONTAINER, "allow")
        return parsed

__all__ = [
    "BrowserIsolationProfile", "BrowserWasmDecoder", "CAP_MEDIA_DECODE",
    "DecoderBroker", "DecoderResult", "DerivativeCacheKey", "LinuxProcessDecoder",
    "LinuxSandboxStatus", "MediaDescriptor", "OpenSslEd25519Verifier",
    "PhysicalLimits", "PhysicalSecurityError", "RepositoryTrust",
    "RepositoryTrustState", "RoleEnvelope", "RolePolicy", "RootMetadata",
    "SecurityBoundary", "SecurityEvent", "SecurityStage", "SecurityTelemetry",
    "Signature", "TargetRecord", "derivative_cache_key", "preflight_media",
    "preflight_spb1", "probe_linux_sandbox", "reject_transient_authority",
    "encode_role_envelope", "parse_role_envelope", "root_metadata_body",
    "root_metadata_from_body", "trust_signature_grants_capability", "validate_decoder_result",
    "validate_protected_asset_candidate",
]
