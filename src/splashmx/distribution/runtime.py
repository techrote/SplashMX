"""SMX-050 production distribution, runtime-retention and recovery boundary.

Distribution owns placement and availability only. Canonical project, package,
CreationRevision, WorldSave and protected Asset meaning remain owned by their
existing production modules. Friendly aliases, CDN keys, runtime artifact
digests, installer state and service health are explicitly non-canonical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any, Callable, Iterable, Mapping

from splashmx.canonical.serialization import (
    DecodeLimits,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
)
from splashmx.publishing.generic import (
    CreationRevisionId,
    GenericPlayer,
    HostedReleaseId,
    PreparedCreation,
    PublishedCreation,
    decode_creation_manifest,
)
from splashmx.runtime.lifecycle import (
    WorldSaveSnapshot,
    deserialize_world_save,
    serialize_world_save,
)

DISTRIBUTION_ARCHIVE_SCHEMA = "splashmx.recovery-archive/1"
RUNTIME_ARTIFACT_SCHEMA = "splashmx.runtime-artifact/1"
NATIVE_PACKAGE_SCHEMA = "splashmx.native-package/1"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_OBJECTS = 32768
MAX_RUNTIME_BYTES = 256 * 1024 * 1024
ARCHIVE_CHUNK_BYTES = 4 * 1024 * 1024
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_NATIVE_TARGETS = frozenset({"native", "headless"})


class DistributionError(ValueError):
    """Stable typed distribution/recovery failure."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _fail(code: str, message: str) -> None:
    raise DistributionError(code, message)


def _token(value: str, role: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        _fail("distribution.invalid_identity", f"{role} must be a bounded token")
    return value


def _digest(payload: bytes) -> str:
    return "sha256:" + sha256(bytes(payload)).hexdigest()


def _chunks(payload: bytes) -> list[bytes]:
    data = bytes(payload)
    return [data[index:index + ARCHIVE_CHUNK_BYTES] for index in range(0, len(data), ARCHIVE_CHUNK_BYTES)] or [b""]


def _unchunks(value: Any, where: str) -> bytes:
    if not isinstance(value, list) or not value:
        _fail("distribution.invalid_archive", f"{where} chunks must be a non-empty array")
    if len(value) > (MAX_ARCHIVE_BYTES // ARCHIVE_CHUNK_BYTES) + 1:
        _fail("distribution.resource_limit", f"{where} has too many chunks")
    parts: list[bytes] = []
    for part in value:
        if not isinstance(part, bytes) or len(part) > ARCHIVE_CHUNK_BYTES:
            _fail("distribution.invalid_archive", f"{where} contains an invalid chunk")
        parts.append(part)
    data = b"".join(parts)
    if len(data) > MAX_ARCHIVE_BYTES:
        _fail("distribution.resource_limit", f"{where} exceeds archive byte limit")
    return data


@dataclass(frozen=True)
class RuntimeArtifact:
    profile: str
    target: str
    payload: bytes
    attestation: Mapping[str, Any] = field(default_factory=dict)
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        _token(self.profile, "runtime profile")
        _token(self.target, "runtime target")
        if not isinstance(self.payload, (bytes, bytearray)):
            _fail("distribution.invalid_runtime", "runtime payload must be bytes")
        payload = bytes(self.payload)
        if len(payload) > MAX_RUNTIME_BYTES:
            _fail("distribution.resource_limit", "runtime payload exceeds byte limit")
        if not isinstance(self.attestation, Mapping):
            _fail("distribution.invalid_runtime", "runtime attestation must be a mapping")
        attestation = dict(self.attestation)
        encode_canonical_cbor(attestation)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "attestation", attestation)
        object.__setattr__(self, "digest", _digest(payload))


class RuntimeStore:
    """Content-addressed retained runtimes with explicit eligibility/revocation."""

    def __init__(self) -> None:
        self._artifacts: dict[str, RuntimeArtifact] = {}
        self._qualified: dict[str, set[str]] = {}
        self._revoked: set[str] = set()

    def qualify(self, artifact: RuntimeArtifact) -> str:
        prior = self._artifacts.get(artifact.digest)
        if prior is not None and prior != artifact:
            _fail("distribution.digest_collision", "runtime digest cannot bind different metadata/bytes")
        self._artifacts[artifact.digest] = artifact
        self._qualified.setdefault(artifact.profile, set()).add(artifact.digest)
        return artifact.digest

    def revoke(self, digest: str) -> None:
        if digest not in self._artifacts:
            _fail("distribution.runtime_unavailable", "cannot revoke unknown runtime artifact")
        self._revoked.add(digest)

    def get(self, profile: str, digest: str) -> RuntimeArtifact:
        _token(profile, "runtime profile")
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            _fail("distribution.invalid_digest", "runtime digest must be sha256")
        artifact = self._artifacts.get(digest)
        if artifact is None or digest not in self._qualified.get(profile, set()):
            _fail("distribution.runtime_unavailable", "exact retained runtime is unavailable")
        if digest in self._revoked:
            _fail("distribution.runtime_revoked", "exact retained runtime is revoked")
        if artifact.profile != profile:
            _fail("distribution.runtime_profile_mismatch", "runtime artifact profile differs from binding")
        return artifact

    def is_revoked(self, digest: str) -> bool:
        return digest in self._revoked

    def retained_bytes(self, *, copies: Mapping[str, int] | None = None) -> int:
        copies = {} if copies is None else dict(copies)
        total = 0
        for digest, artifact in self._artifacts.items():
            count = copies.get(digest, 1)
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                _fail("distribution.invalid_replica_count", "runtime copy count must be positive")
            total += len(artifact.payload) * count
        return total


@dataclass(frozen=True)
class ReleaseBinding:
    release_id: HostedReleaseId
    creation_revision_id: CreationRevisionId
    runtime_profile: str
    runtime_digest: str


@dataclass(frozen=True)
class ServiceEvent:
    service: str
    available: bool
    reason: str


class ServiceHealth:
    """Operational state only; never serialized into project/creation/WorldSave."""

    def __init__(self, services: Iterable[str] = ("hosting", "collaboration", "networking")):
        self._available = {_token(name, "service"): True for name in services}
        self._events: list[ServiceEvent] = []

    def set(self, service: str, *, available: bool, reason: str = "") -> None:
        service = _token(service, "service")
        if service not in self._available:
            _fail("distribution.unknown_service", f"unknown service {service}")
        if not isinstance(available, bool):
            _fail("distribution.invalid_service_state", "service availability must be boolean")
        self._available[service] = available
        self._events.append(ServiceEvent(service, available, str(reason)[:1024]))

    def require(self, service: str) -> None:
        if not self._available.get(service, False):
            _fail("distribution.service_unavailable", f"{service} service is unavailable")

    @property
    def events(self) -> tuple[ServiceEvent, ...]:
        return tuple(self._events)


class ContentAddressedCache:
    """CDN/cache placement keyed by immutable byte digest, never by semantic identity."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, payload: bytes) -> str:
        data = bytes(payload)
        digest = _digest(data)
        prior = self._objects.get(digest)
        if prior is not None and prior != data:
            _fail("distribution.digest_collision", "cache digest cannot be rebound")
        self._objects[digest] = data
        return digest

    def get(self, digest: str) -> bytes:
        value = self._objects.get(digest)
        if value is None:
            _fail("distribution.cache_miss", "immutable cache object is unavailable")
        if _digest(value) != digest:
            _fail("distribution.cache_integrity", "immutable cache object failed digest validation")
        return value

    def evict(self, digest: str) -> None:
        self._objects.pop(digest, None)


class HostedDistribution:
    """Immutable hosted releases bound to exact CreationRevision + runtime bytes."""

    def __init__(self, runtimes: RuntimeStore, *, services: ServiceHealth | None = None):
        self.runtimes = runtimes
        self.services = services or ServiceHealth()
        self._bindings: dict[HostedReleaseId, ReleaseBinding] = {}
        self._creations: dict[CreationRevisionId, PublishedCreation] = {}
        self._aliases: dict[str, HostedReleaseId] = {}

    def publish(
        self,
        release_id: HostedReleaseId,
        published: PublishedCreation,
        *,
        runtime_profile: str,
        runtime_digest: str,
    ) -> ReleaseBinding:
        if not isinstance(release_id, HostedReleaseId):
            _fail("distribution.invalid_release", "release_id must be HostedReleaseId")
        runtime = self.runtimes.get(runtime_profile, runtime_digest)
        manifest = decode_creation_manifest(published.manifest_bytes)
        GenericPlayer().prepare(published)
        revision = manifest.creation_revision_id
        prior_creation = self._creations.get(revision)
        if prior_creation is not None and (
            prior_creation.manifest_bytes != published.manifest_bytes
            or dict(prior_creation.blobs) != dict(published.blobs)
        ):
            _fail("distribution.immutable_rebind", "CreationRevisionId cannot be rebound")
        binding = ReleaseBinding(release_id, revision, runtime.profile, runtime.digest)
        prior = self._bindings.get(release_id)
        if prior is not None and prior != binding:
            _fail("distribution.immutable_release", "HostedReleaseId cannot retarget creation/runtime")
        self._creations[revision] = published
        self._bindings[release_id] = binding
        return binding

    def retarget_alias(self, alias: str, release_id: HostedReleaseId) -> None:
        alias = _token(alias, "friendly alias")
        if release_id not in self._bindings:
            _fail("distribution.unknown_release", "alias target must be an existing release")
        self._aliases[alias] = release_id

    def resolve(self, locator: HostedReleaseId | str) -> ReleaseBinding:
        self.services.require("hosting")
        release_id = locator
        if isinstance(locator, str) and not isinstance(locator, HostedReleaseId):
            release_id = self._aliases.get(locator)
            if release_id is None:
                _fail("distribution.unknown_alias", "unknown friendly alias")
        if not isinstance(release_id, HostedReleaseId):
            _fail("distribution.invalid_locator", "hosted locator must be release ID or alias")
        binding = self._bindings.get(release_id)
        if binding is None:
            _fail("distribution.unknown_release", "unknown immutable hosted release")
        self.runtimes.get(binding.runtime_profile, binding.runtime_digest)
        return binding

    def fetch(self, locator: HostedReleaseId | str) -> tuple[ReleaseBinding, PublishedCreation, RuntimeArtifact]:
        binding = self.resolve(locator)
        return (
            binding,
            self._creations[binding.creation_revision_id],
            self.runtimes.get(binding.runtime_profile, binding.runtime_digest),
        )


@dataclass(frozen=True)
class OfflineInstall:
    creation_revision_id: CreationRevisionId
    published: PublishedCreation
    runtime_profile: str
    runtime_digest: str
    runtime_target: str
    runtime_payload: bytes

    def __post_init__(self) -> None:
        manifest = decode_creation_manifest(self.published.manifest_bytes)
        if manifest.creation_revision_id != self.creation_revision_id:
            _fail("distribution.install_identity_mismatch", "offline install CreationRevisionId differs from payload")
        if _digest(self.runtime_payload) != self.runtime_digest:
            _fail("distribution.runtime_integrity", "offline runtime digest mismatch")
        _token(self.runtime_profile, "runtime profile")
        _token(self.runtime_target, "runtime target")


class OfflineDistributionLibrary:
    """Network-independent exact creation+runtime installations."""

    def __init__(self) -> None:
        self._installs: dict[CreationRevisionId, OfflineInstall] = {}
        self._revoked_runtime_digests: set[str] = set()

    def revoke_runtime(self, digest: str) -> None:
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            _fail("distribution.invalid_digest", "runtime digest must be sha256")
        self._revoked_runtime_digests.add(digest)

    def install(
        self,
        published: PublishedCreation,
        runtime: RuntimeArtifact,
        *,
        verifier: GenericPlayer | None = None,
    ) -> CreationRevisionId:
        prepared = (verifier or GenericPlayer()).prepare(published)
        revision = prepared.manifest.creation_revision_id
        install = OfflineInstall(
            revision,
            published,
            runtime.profile,
            runtime.digest,
            runtime.target,
            runtime.payload,
        )
        prior = self._installs.get(revision)
        if prior is not None and prior != install:
            _fail("distribution.immutable_rebind", "offline CreationRevision cannot be rebound")
        self._installs[revision] = install
        return revision

    def get(self, revision: CreationRevisionId) -> OfflineInstall:
        value = self._installs.get(revision)
        if value is None:
            _fail("distribution.offline_unavailable", "exact creation/runtime install is unavailable")
        return value

    def launch(
        self,
        revision: CreationRevisionId,
        activator: Callable[[PreparedCreation], Any],
        *,
        supported_features: Iterable[str] = (),
    ) -> Any:
        install = self.get(revision)
        if _digest(install.runtime_payload) != install.runtime_digest:
            _fail("distribution.runtime_integrity", "installed runtime bytes changed")
        if install.runtime_digest in self._revoked_runtime_digests:
            _fail("distribution.runtime_revoked", "installed runtime is revoked by local policy")
        player = GenericPlayer(supported_features=supported_features)
        return player.activate(player.prepare(install.published), activator)


@dataclass(frozen=True)
class ProtectedAssetDisclosure:
    asset_id: str
    revision_digest: str
    source_digest: str
    source_identity: Mapping[str, Any]
    source_metadata: Mapping[str, Any]
    media_semantics: Mapping[str, Any]
    provenance: Mapping[str, Any]
    licence_attribution: Mapping[str, Any]
    derivation_lineage: tuple[Mapping[str, Any], ...]


def protected_asset_disclosures(published: PublishedCreation) -> tuple[ProtectedAssetDisclosure, ...]:
    prepared = GenericPlayer().prepare(published)
    rows = []
    for asset_id, asset in sorted(prepared.protected_assets.items(), key=lambda row: str(row[0])):
        rows.append(
            ProtectedAssetDisclosure(
                str(asset_id),
                asset.revision_digest,
                asset.source_digest,
                dict(asset.source_identity),
                dict(asset.source_metadata),
                dict(asset.media_semantics),
                dict(asset.provenance),
                dict(asset.licence_attribution),
                tuple(dict(value) for value in asset.derivation_lineage),
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class RecoveryBundle:
    project: SerializedProjectRevision | None
    installs: tuple[OfflineInstall, ...]
    world_saves: tuple[WorldSaveSnapshot, ...]


def _install_object(install: OfflineInstall) -> dict[str, Any]:
    return {
        "creation_revision_id": str(install.creation_revision_id),
        "creation_manifest_chunks": _chunks(install.published.manifest_bytes),
        "creation_blobs": [
            {"digest": digest, "payload_chunks": _chunks(payload)}
            for digest, payload in sorted(install.published.blobs.items())
        ],
        "runtime_profile": install.runtime_profile,
        "runtime_digest": install.runtime_digest,
        "runtime_target": install.runtime_target,
        "runtime_payload_chunks": _chunks(install.runtime_payload),
    }


def export_recovery_archive(
    *,
    project: SerializedProjectRevision | None = None,
    installs: Iterable[OfflineInstall] = (),
    world_saves: Iterable[WorldSaveSnapshot] = (),
) -> bytes:
    project_object = None
    if project is not None:
        deserialize_project(project)
        project_object = {
            "root_manifest_chunks": _chunks(project.root_manifest),
            "shards": [
                {"key": key, "payload_chunks": _chunks(value)}
                for key, value in sorted(project.shards.items())
            ],
        }

    install_rows = tuple(installs)
    world_rows = tuple(world_saves)
    if len(install_rows) + len(world_rows) > MAX_ARCHIVE_OBJECTS:
        _fail("distribution.resource_limit", "recovery archive exceeds object limit")
    for install in install_rows:
        GenericPlayer().prepare(install.published)
        if _digest(install.runtime_payload) != install.runtime_digest:
            _fail("distribution.runtime_integrity", "cannot export corrupt runtime")
    encoded_worlds = [_chunks(serialize_world_save(row)) for row in world_rows]

    archive = encode_canonical_cbor(
        {
            "schema": DISTRIBUTION_ARCHIVE_SCHEMA,
            "project": project_object,
            "installs": [_install_object(row) for row in install_rows],
            "world_saves": encoded_worlds,
        }
    )
    if len(archive) > MAX_ARCHIVE_BYTES:
        _fail("distribution.resource_limit", "recovery archive exceeds byte limit")
    return archive


def _exact(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _fail("distribution.invalid_archive", f"{where} fields are invalid")
    return value


def import_recovery_archive(raw: bytes) -> RecoveryBundle:
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_ARCHIVE_BYTES:
        _fail("distribution.resource_limit", "recovery archive is invalid or too large")
    try:
        root = decode_canonical_cbor(
            bytes(raw),
            limits=DecodeLimits(
                max_bytes=MAX_ARCHIVE_BYTES,
                max_depth=64,
                max_items=MAX_ARCHIVE_OBJECTS * 32,
                max_string_bytes=MAX_ARCHIVE_BYTES,
            ),
        )
    except DistributionError:
        raise
    except Exception as exc:
        raise DistributionError("distribution.invalid_archive", "recovery archive is not canonical CBOR", cause=exc) from exc
    root = _exact(root, {"schema", "project", "installs", "world_saves"}, "recovery archive")
    if root["schema"] != DISTRIBUTION_ARCHIVE_SCHEMA:
        _fail("distribution.unsupported_archive", "unsupported recovery archive schema")
    if not isinstance(root["installs"], list) or not isinstance(root["world_saves"], list):
        _fail("distribution.invalid_archive", "archive collections must be arrays")
    if len(root["installs"]) + len(root["world_saves"]) > MAX_ARCHIVE_OBJECTS:
        _fail("distribution.resource_limit", "recovery archive exceeds object limit")

    project = None
    if root["project"] is not None:
        row = _exact(root["project"], {"root_manifest_chunks", "shards"}, "project")
        if not isinstance(row["shards"], list):
            _fail("distribution.invalid_archive", "project archive fields are invalid")
        shards: dict[str, bytes] = {}
        for item in row["shards"]:
            item = _exact(item, {"key", "payload_chunks"}, "project shard")
            if not isinstance(item["key"], str):
                _fail("distribution.invalid_archive", "project shard is invalid")
            if item["key"] in shards:
                _fail("distribution.invalid_archive", "duplicate project shard key")
            shards[item["key"]] = _unchunks(item["payload_chunks"], "project shard")
        project = SerializedProjectRevision(_unchunks(row["root_manifest_chunks"], "project manifest"), shards)
        deserialize_project(project)

    installs: list[OfflineInstall] = []
    seen_revisions: set[CreationRevisionId] = set()
    for item in root["installs"]:
        item = _exact(
            item,
            {
                "creation_revision_id", "creation_manifest_chunks", "creation_blobs",
                "runtime_profile", "runtime_digest", "runtime_target", "runtime_payload_chunks",
            },
            "offline install",
        )
        if not isinstance(item["creation_blobs"], list):
            _fail("distribution.invalid_archive", "offline install creation fields are invalid")
        blobs: dict[str, bytes] = {}
        for blob in item["creation_blobs"]:
            blob = _exact(blob, {"digest", "payload_chunks"}, "creation blob")
            if not isinstance(blob["digest"], str):
                _fail("distribution.invalid_archive", "creation blob is invalid")
            payload = _unchunks(blob["payload_chunks"], "creation blob")
            if _DIGEST.fullmatch(blob["digest"]) is None or _digest(payload) != blob["digest"]:
                _fail("distribution.creation_integrity", "creation blob digest mismatch")
            if blob["digest"] in blobs:
                _fail("distribution.invalid_archive", "duplicate creation blob digest")
            blobs[blob["digest"]] = payload
        published = PublishedCreation(_unchunks(item["creation_manifest_chunks"], "creation manifest"), blobs)
        prepared = GenericPlayer().prepare(published)
        revision = CreationRevisionId(item["creation_revision_id"])
        if prepared.manifest.creation_revision_id != revision:
            _fail("distribution.install_identity_mismatch", "archive creation revision differs from payload")
        install = OfflineInstall(
            revision,
            published,
            item["runtime_profile"],
            item["runtime_digest"],
            item["runtime_target"],
            _unchunks(item["runtime_payload_chunks"], "runtime payload"),
        )
        if revision in seen_revisions:
            _fail("distribution.invalid_archive", "duplicate installed CreationRevisionId")
        seen_revisions.add(revision)
        installs.append(install)

    worlds: list[WorldSaveSnapshot] = []
    world_ids: set[tuple[str, str]] = set()
    for payload_chunks in root["world_saves"]:
        snapshot = deserialize_world_save(_unchunks(payload_chunks, "WorldSave"))
        key = (str(snapshot.world_save_id), str(snapshot.world_revision_id))
        if key in world_ids:
            _fail("distribution.invalid_archive", "duplicate WorldSave revision")
        world_ids.add(key)
        worlds.append(snapshot)

    return RecoveryBundle(project, tuple(installs), tuple(worlds))


@dataclass(frozen=True)
class NativePackage:
    target: str
    creation_revision_id: CreationRevisionId
    runtime_profile: str
    runtime_digest: str
    payload: bytes


def build_native_package(install: OfflineInstall, *, target: str) -> NativePackage:
    """Build exact portable native payload; OS installer choice remains evidence-gated."""
    target = _token(target, "native target")
    if target not in _NATIVE_TARGETS:
        _fail("distribution.native_target_unsupported", "target lacks qualified native runtime evidence")
    if install.runtime_target != target:
        _fail("distribution.native_target_mismatch", "installed runtime target differs from native package")
    archive = export_recovery_archive(installs=(install,))
    payload = encode_canonical_cbor(
        {
            "schema": NATIVE_PACKAGE_SCHEMA,
            "target": target,
            "creation_revision_id": str(install.creation_revision_id),
            "runtime_profile": install.runtime_profile,
            "runtime_digest": install.runtime_digest,
            "recovery_archive_chunks": _chunks(archive),
        }
    )
    return NativePackage(target, install.creation_revision_id, install.runtime_profile, install.runtime_digest, payload)


def verify_native_package(package: NativePackage) -> OfflineInstall:
    if not isinstance(package.payload, (bytes, bytearray)):
        _fail("distribution.invalid_native_package", "native package payload must be bytes")
    try:
        root = decode_canonical_cbor(bytes(package.payload))
    except Exception as exc:
        raise DistributionError("distribution.invalid_native_package", "native package is malformed", cause=exc) from exc
    root = _exact(
        root,
        {
            "schema", "target", "creation_revision_id", "runtime_profile",
            "runtime_digest", "recovery_archive_chunks",
        },
        "native package",
    )
    if root["schema"] != NATIVE_PACKAGE_SCHEMA:
        _fail("distribution.invalid_native_package", "unsupported native package schema")
    bundle = import_recovery_archive(_unchunks(root["recovery_archive_chunks"], "native recovery archive"))
    if len(bundle.installs) != 1:
        _fail("distribution.invalid_native_package", "native package must contain exactly one install")
    install = bundle.installs[0]
    if (
        root["target"] != package.target
        or root["creation_revision_id"] != str(package.creation_revision_id)
        or root["runtime_profile"] != package.runtime_profile
        or root["runtime_digest"] != package.runtime_digest
        or install.creation_revision_id != package.creation_revision_id
        or install.runtime_target != package.target
        or install.runtime_profile != package.runtime_profile
        or install.runtime_digest != package.runtime_digest
    ):
        _fail("distribution.invalid_native_package", "native package metadata differs from exact payload")
    return install


__all__ = [
    "DISTRIBUTION_ARCHIVE_SCHEMA",
    "ContentAddressedCache",
    "DistributionError",
    "HostedDistribution",
    "NativePackage",
    "OfflineDistributionLibrary",
    "OfflineInstall",
    "ProtectedAssetDisclosure",
    "RecoveryBundle",
    "ReleaseBinding",
    "RuntimeArtifact",
    "RuntimeStore",
    "ServiceEvent",
    "ServiceHealth",
    "build_native_package",
    "export_recovery_archive",
    "import_recovery_archive",
    "protected_asset_disclosures",
    "verify_native_package",
]
