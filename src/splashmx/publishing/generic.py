"""SMX-036 immutable publication and generic-player boundary.

The module deliberately owns publication semantics only.  A published creation is
immutable SplashMX data plus an exact package lock, consumed by a separately built
generic player.  Hosted aliases, offline placement, WorldSave identity and
target-private derivatives never become canonical creation identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any, Callable, Iterable, Mapping

from splashmx.canonical.core import AssetId, ProjectId, ProjectRevisionId, SemanticId
from splashmx.canonical.serialization import (
    CanonicalProjectRevision,
    DecodeLimits,
    ProtectedAssetRevision,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
    serialize_project,
)
from splashmx.packages.bundle import decode_lock, encode_lock
from splashmx.packages.model import (
    PackageId,
    PackageRevisionId,
    ResolutionLock,
    digest,
)
from splashmx.packages.system import (
    MappingPackageSource,
    PackageRuntimeState,
    PackageSystem,
    ValidatedPackage,
    validate_lock_dependencies,
    validate_locked_bundle,
)
from splashmx.runtime.lifecycle import WorldSaveId, WorldSaveSnapshot
from splashmx.runtime.streaming import ImmutableArtifactCache
from splashmx.security.capabilities import CapabilityBroker

CREATION_SCHEMA = "splashmx.creation/1"
CREATION_ENVELOPE_SCHEMA = "splashmx.creation-envelope/1"
GENERIC_PLAYER_PROFILE = "splashmx.generic-player/1"
MAX_CREATION_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_CREATION_BLOBS = 16384
_ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~:/-]{0,255}")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


class PublicationError(ValueError):
    """Stable typed publication/player failure."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _fail(code: str, message: str) -> None:
    raise PublicationError(code, message)


class CreationId(SemanticId):
    role = "CreationId"


class CreationRevisionId(SemanticId):
    role = "CreationRevisionId"


class HostedReleaseId(SemanticId):
    role = "HostedReleaseId"


@dataclass(frozen=True)
class BlobRef:
    digest: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.digest, str) or _DIGEST_RE.fullmatch(self.digest) is None:
            _fail("publication.invalid_digest", "blob digest must be sha256:<64 lowercase hex>")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            _fail("publication.invalid_size", "blob size must be a non-negative integer")

    def object(self) -> dict[str, Any]:
        return {"digest": self.digest, "size_bytes": self.size_bytes}


@dataclass(frozen=True)
class NamedBlobRef:
    key: str
    blob: BlobRef

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key or len(self.key.encode("utf-8")) > 1024:
            _fail("publication.invalid_blob_key", "blob key must be a bounded non-empty string")

    def object(self) -> dict[str, Any]:
        return {"key": self.key, **self.blob.object()}


@dataclass(frozen=True)
class PackageBlobRef:
    package_id: PackageId
    package_revision_id: PackageRevisionId
    blob: BlobRef

    def object(self) -> dict[str, Any]:
        return {
            "package_id": str(self.package_id),
            "package_revision_id": str(self.package_revision_id),
            **self.blob.object(),
        }


@dataclass(frozen=True)
class CreationManifest:
    creation_id: CreationId
    creation_revision_id: CreationRevisionId
    project_id: ProjectId
    project_revision_id: ProjectRevisionId
    project_manifest: BlobRef
    project_shards: tuple[NamedBlobRef, ...]
    resolution_lock: BlobRef
    package_bundles: tuple[PackageBlobRef, ...]
    required_features: tuple[str, ...] = ()
    player_profile: str = GENERIC_PLAYER_PROFILE

    def __post_init__(self) -> None:
        if self.player_profile != GENERIC_PLAYER_PROFILE:
            _fail("publication.unsupported_player_profile", "unsupported generic-player profile")
        if len(self.project_shards) + len(self.package_bundles) + 2 > MAX_CREATION_BLOBS:
            _fail("publication.resource_limit", "creation closure exceeds blob-count limit")
        if len({row.key for row in self.project_shards}) != len(self.project_shards):
            _fail("publication.invalid_manifest", "duplicate project shard key")
        if len({row.package_id for row in self.package_bundles}) != len(self.package_bundles):
            _fail("publication.invalid_manifest", "duplicate PackageId in creation closure")
        if len({row.package_revision_id for row in self.package_bundles}) != len(self.package_bundles):
            _fail("publication.invalid_manifest", "duplicate PackageRevisionId in creation closure")
        if len(set(self.required_features)) != len(self.required_features):
            _fail("publication.invalid_manifest", "duplicate required feature")
        for feature in self.required_features:
            if not isinstance(feature, str) or not feature or len(feature) > 128:
                _fail("publication.invalid_manifest", "required features must be bounded strings")


@dataclass(frozen=True)
class PublishedCreation:
    manifest_bytes: bytes
    blobs: Mapping[str, bytes]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_bytes, (bytes, bytearray)):
            _fail("publication.invalid_manifest", "creation manifest must be bytes")
        if len(self.manifest_bytes) > MAX_CREATION_MANIFEST_BYTES:
            _fail("publication.resource_limit", "creation manifest exceeds byte limit")
        if len(self.blobs) > MAX_CREATION_BLOBS:
            _fail("publication.resource_limit", "creation closure exceeds blob-count limit")
        copied: dict[str, bytes] = {}
        for key, value in self.blobs.items():
            if not isinstance(key, str) or _DIGEST_RE.fullmatch(key) is None:
                _fail("publication.invalid_digest", "creation blob map must be keyed by sha256 digest")
            if not isinstance(value, (bytes, bytearray)):
                _fail("publication.invalid_blob", "creation blobs must be byte strings")
            copied[key] = bytes(value)
        object.__setattr__(self, "manifest_bytes", bytes(self.manifest_bytes))
        object.__setattr__(self, "blobs", copied)


@dataclass(frozen=True)
class PreparedCreation:
    manifest: CreationManifest
    project: CanonicalProjectRevision
    lock: ResolutionLock
    package_state: PackageRuntimeState
    packages: Mapping[PackageId, ValidatedPackage]
    protected_assets: Mapping[AssetId, ProtectedAssetRevision]


@dataclass(frozen=True)
class WorldSaveBasis:
    """Explicit basis relation; the identities remain role-distinct."""

    world_save_id: WorldSaveId
    creation_revision_id: CreationRevisionId
    project_id: ProjectId
    project_revision_id: ProjectRevisionId


@dataclass(frozen=True)
class TargetMediaDerivative:
    """Target-private cache material, never canonical Asset meaning."""

    asset_id: AssetId
    canonical_asset_revision_digest: str
    target_profile: str
    payload_digest: str
    payload_size: int


def _blob(payload: bytes) -> BlobRef:
    data = bytes(payload)
    return BlobRef(digest(data), len(data))


def _manifest_payload(
    *,
    creation_id: CreationId,
    project_id: ProjectId,
    project_revision_id: ProjectRevisionId,
    project_manifest: BlobRef,
    project_shards: tuple[NamedBlobRef, ...],
    resolution_lock: BlobRef,
    package_bundles: tuple[PackageBlobRef, ...],
    required_features: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema": CREATION_SCHEMA,
        "creation_id": str(creation_id),
        "project_id": str(project_id),
        "project_revision_id": str(project_revision_id),
        "project_manifest": project_manifest.object(),
        "project_shards": [row.object() for row in project_shards],
        "resolution_lock": resolution_lock.object(),
        "package_bundles": [row.object() for row in package_bundles],
        "required_features": list(required_features),
        "player_profile": GENERIC_PLAYER_PROFILE,
    }


def _revision_id(payload: Mapping[str, Any]) -> CreationRevisionId:
    return CreationRevisionId("sha256:" + sha256(encode_canonical_cbor(dict(payload))).hexdigest())


def encode_creation_manifest(manifest: CreationManifest) -> bytes:
    payload = _manifest_payload(
        creation_id=manifest.creation_id,
        project_id=manifest.project_id,
        project_revision_id=manifest.project_revision_id,
        project_manifest=manifest.project_manifest,
        project_shards=manifest.project_shards,
        resolution_lock=manifest.resolution_lock,
        package_bundles=manifest.package_bundles,
        required_features=manifest.required_features,
    )
    expected = _revision_id(payload)
    if expected != manifest.creation_revision_id:
        _fail("publication.revision_mismatch", "CreationRevisionId does not match immutable creation payload")
    return encode_canonical_cbor(
        {
            "schema": CREATION_ENVELOPE_SCHEMA,
            "creation_revision_id": str(manifest.creation_revision_id),
            "payload": payload,
        }
    )


def _exact(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _fail("publication.invalid_manifest", f"{where} must contain exactly {sorted(keys)}")
    return value


def _decode_blob_ref(value: Any, where: str) -> BlobRef:
    value = _exact(value, {"digest", "size_bytes"}, where)
    return BlobRef(value["digest"], value["size_bytes"])


def decode_creation_manifest(raw: bytes) -> CreationManifest:
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_CREATION_MANIFEST_BYTES:
        _fail("publication.resource_limit", "creation manifest is invalid or exceeds byte limit")
    try:
        envelope = decode_canonical_cbor(
            bytes(raw),
            limits=DecodeLimits(
                max_bytes=MAX_CREATION_MANIFEST_BYTES,
                max_depth=64,
                max_items=MAX_CREATION_BLOBS * 16,
                max_string_bytes=MAX_CREATION_MANIFEST_BYTES,
            ),
        )
    except PublicationError:
        raise
    except Exception as exc:
        raise PublicationError("publication.invalid_manifest", "creation manifest is not canonical bounded CBOR", cause=exc) from exc
    envelope = _exact(envelope, {"schema", "creation_revision_id", "payload"}, "creation envelope")
    if envelope["schema"] != CREATION_ENVELOPE_SCHEMA:
        _fail("publication.unsupported_schema", "unsupported creation-envelope schema")
    payload = _exact(
        envelope["payload"],
        {
            "schema", "creation_id", "project_id", "project_revision_id",
            "project_manifest", "project_shards", "resolution_lock", "package_bundles",
            "required_features", "player_profile",
        },
        "creation payload",
    )
    if payload["schema"] != CREATION_SCHEMA:
        _fail("publication.unsupported_schema", "unsupported creation schema")
    if not isinstance(payload["project_shards"], list) or not isinstance(payload["package_bundles"], list):
        _fail("publication.invalid_manifest", "creation shard/package descriptors must be arrays")
    if len(payload["project_shards"]) + len(payload["package_bundles"]) + 2 > MAX_CREATION_BLOBS:
        _fail("publication.resource_limit", "creation closure exceeds blob-count limit")
    shards: list[NamedBlobRef] = []
    for value in payload["project_shards"]:
        value = _exact(value, {"key", "digest", "size_bytes"}, "project shard")
        shards.append(NamedBlobRef(value["key"], BlobRef(value["digest"], value["size_bytes"])))
    packages: list[PackageBlobRef] = []
    for value in payload["package_bundles"]:
        value = _exact(value, {"package_id", "package_revision_id", "digest", "size_bytes"}, "package bundle")
        packages.append(
            PackageBlobRef(
                PackageId(value["package_id"]),
                PackageRevisionId(value["package_revision_id"]),
                BlobRef(value["digest"], value["size_bytes"]),
            )
        )
    if not isinstance(payload["required_features"], list):
        _fail("publication.invalid_manifest", "required_features must be an array")
    manifest = CreationManifest(
        CreationId(payload["creation_id"]),
        CreationRevisionId(envelope["creation_revision_id"]),
        ProjectId(payload["project_id"]),
        ProjectRevisionId(payload["project_revision_id"]),
        _decode_blob_ref(payload["project_manifest"], "project manifest"),
        tuple(shards),
        _decode_blob_ref(payload["resolution_lock"], "resolution lock"),
        tuple(packages),
        tuple(payload["required_features"]),
        payload["player_profile"],
    )
    if manifest.creation_revision_id != _revision_id(payload):
        _fail("publication.revision_mismatch", "CreationRevisionId does not match immutable creation payload")
    return manifest


def _add_blob(blobs: dict[str, bytes], payload: bytes) -> BlobRef:
    data = bytes(payload)
    ref = _blob(data)
    prior = blobs.get(ref.digest)
    if prior is not None and prior != data:
        _fail("publication.digest_collision", "same digest was rebound to different bytes")
    blobs[ref.digest] = data
    return ref


def _collect_assets(
    project: CanonicalProjectRevision,
    packages: Iterable[ValidatedPackage],
) -> dict[AssetId, ProtectedAssetRevision]:
    assets = dict(project.assets)
    for package in packages:
        for asset in package.manifest.protected_assets:
            prior = assets.get(asset.asset_id)
            if prior is not None and prior.revision_digest != asset.revision_digest:
                _fail(
                    "publication.protected_asset_conflict",
                    f"AssetId {asset.asset_id} resolves to competing immutable revisions",
                )
            assets[asset.asset_id] = asset
    return assets


def publish_creation(
    creation_id: CreationId,
    project: CanonicalProjectRevision,
    lock: ResolutionLock,
    package_bundles: Mapping[PackageRevisionId | str, bytes],
    *,
    required_features: Iterable[str] = (),
) -> PublishedCreation:
    """Freeze one coherent authored project and exact package closure.

    No engine export/build callback exists in this operation.  Every package named
    by the lock, including lazy packages, must be present and fully verified so an
    offline install is the same immutable closure as a hosted release.
    """
    if not isinstance(creation_id, CreationId):
        _fail("publication.invalid_identity", "publish requires CreationId")
    if not isinstance(project, CanonicalProjectRevision) or not isinstance(lock, ResolutionLock):
        _fail("publication.invalid_input", "publish requires a canonical project and ResolutionLock")

    by_revision = {str(key): bytes(value) for key, value in package_bundles.items()}
    expected_revisions = {str(row.package_revision_id) for row in lock.packages.values()}
    if set(by_revision) != expected_revisions:
        _fail("publication.incomplete_closure", "package bytes must exactly cover every locked package revision")

    validated: list[ValidatedPackage] = []
    for package_id, locked in sorted(lock.packages.items(), key=lambda row: str(row[0])):
        payload = by_revision[str(locked.package_revision_id)]
        if len(payload) != locked.bundle_size or digest(payload) != locked.bundle_digest:
            _fail("publication.dependency_integrity", f"locked package {package_id} bytes do not match exact digest/size")
        try:
            package = validate_locked_bundle(locked, payload)
            validate_lock_dependencies(lock, package)
        except Exception as exc:
            code = getattr(exc, "code", "publication.invalid_dependency")
            raise PublicationError("publication.invalid_dependency", f"locked package validation failed: {code}", cause=exc) from exc
        validated.append(package)

    _collect_assets(project, validated)
    serialized = serialize_project(project)
    lock_bytes = encode_lock(lock)

    blobs: dict[str, bytes] = {}
    project_manifest = _add_blob(blobs, serialized.root_manifest)
    project_shards = tuple(
        NamedBlobRef(key, _add_blob(blobs, payload))
        for key, payload in sorted(serialized.shards.items())
    )
    lock_ref = _add_blob(blobs, lock_bytes)
    package_refs: list[PackageBlobRef] = []
    for package_id, locked in sorted(lock.packages.items(), key=lambda row: str(row[0])):
        ref = _add_blob(blobs, by_revision[str(locked.package_revision_id)])
        package_refs.append(PackageBlobRef(package_id, locked.package_revision_id, ref))

    features = tuple(sorted(set(required_features)))
    payload = _manifest_payload(
        creation_id=creation_id,
        project_id=project.document.project_id,
        project_revision_id=project.document.project_revision_id,
        project_manifest=project_manifest,
        project_shards=project_shards,
        resolution_lock=lock_ref,
        package_bundles=tuple(package_refs),
        required_features=features,
    )
    revision = _revision_id(payload)
    manifest = CreationManifest(
        creation_id,
        revision,
        project.document.project_id,
        project.document.project_revision_id,
        project_manifest,
        project_shards,
        lock_ref,
        tuple(package_refs),
        features,
    )
    return PublishedCreation(encode_creation_manifest(manifest), blobs)


def _all_refs(manifest: CreationManifest) -> tuple[BlobRef, ...]:
    return (
        manifest.project_manifest,
        *(row.blob for row in manifest.project_shards),
        manifest.resolution_lock,
        *(row.blob for row in manifest.package_bundles),
    )


def _verified_blob(published: PublishedCreation, ref: BlobRef) -> bytes:
    payload = published.blobs.get(ref.digest)
    if payload is None:
        _fail("publication.missing_blob", f"creation closure is missing {ref.digest}")
    if len(payload) != ref.size_bytes or digest(payload) != ref.digest:
        _fail("publication.integrity_failure", f"creation blob {ref.digest} failed exact digest/size validation")
    return bytes(payload)


class GenericPlayer:
    """Prepare-before-activate generic player seam.

    Parsing, exact closure verification, canonical compatibility, package
    validation and current capability policy all complete before `activator` is
    invoked.  The separately built renderer/engine binding is intentionally a
    later adapter.
    """

    def __init__(
        self,
        *,
        supported_features: Iterable[str] = (),
        capability_broker: CapabilityBroker | None = None,
        policy_time: int = 0,
    ):
        self.supported_features = frozenset(supported_features)
        self.capability_broker = capability_broker
        self.policy_time = policy_time
        self.active: PreparedCreation | None = None

    def prepare(self, published: PublishedCreation) -> PreparedCreation:
        manifest = decode_creation_manifest(published.manifest_bytes)
        unsupported = set(manifest.required_features) - self.supported_features
        if unsupported:
            _fail("publication.unsupported_feature", f"creation requires unsupported features {sorted(unsupported)}")

        refs = _all_refs(manifest)
        referenced = {ref.digest for ref in refs}
        if set(published.blobs) != referenced:
            _fail("publication.unexpected_blob", "creation blob map must equal the exact declared closure")
        for ref in refs:
            _verified_blob(published, ref)

        serialized = SerializedProjectRevision(
            _verified_blob(published, manifest.project_manifest),
            {row.key: _verified_blob(published, row.blob) for row in manifest.project_shards},
        )
        try:
            project = deserialize_project(serialized)
        except Exception as exc:
            raise PublicationError("publication.invalid_project", "canonical project failed before activation", cause=exc) from exc
        if (
            project.document.project_id != manifest.project_id
            or project.document.project_revision_id != manifest.project_revision_id
        ):
            _fail("publication.project_identity_mismatch", "creation manifest and canonical project identities differ")

        try:
            lock = decode_lock(_verified_blob(published, manifest.resolution_lock))
        except Exception as exc:
            raise PublicationError("publication.invalid_lock", "exact resolution lock failed before activation", cause=exc) from exc

        descriptor_by_package = {row.package_id: row for row in manifest.package_bundles}
        if set(descriptor_by_package) != set(lock.packages):
            _fail("publication.incomplete_closure", "creation package descriptors differ from exact lock")
        package_payloads: dict[str, bytes] = {}
        validated: dict[PackageId, ValidatedPackage] = {}
        for package_id, locked in sorted(lock.packages.items(), key=lambda row: str(row[0])):
            descriptor = descriptor_by_package[package_id]
            if (
                descriptor.package_revision_id != locked.package_revision_id
                or descriptor.blob.digest != locked.bundle_digest
                or descriptor.blob.size_bytes != locked.bundle_size
            ):
                _fail("publication.floating_dependency", f"creation descriptor for {package_id} differs from exact lock")
            payload = _verified_blob(published, descriptor.blob)
            try:
                package = validate_locked_bundle(
                    locked, payload, supported_features=self.supported_features
                )
                validate_lock_dependencies(lock, package)
            except Exception as exc:
                raise PublicationError("publication.invalid_dependency", f"package {package_id} failed before activation", cause=exc) from exc
            validated[package_id] = package
            package_payloads[str(locked.package_revision_id)] = payload

        assets = _collect_assets(project, validated.values())

        package_system = PackageSystem(
            source=MappingPackageSource(package_payloads),
            cache=ImmutableArtifactCache(),
            capability_broker=self.capability_broker,
            supported_features=self.supported_features,
        )
        try:
            package_state = package_system.apply_lock(lock, policy_time=self.policy_time)
        except Exception as exc:
            raise PublicationError("publication.capability_or_package_policy", "package policy failed before activation", cause=exc) from exc

        return PreparedCreation(
            manifest,
            project,
            lock,
            package_state,
            dict(validated),
            assets,
        )

    def activate(
        self,
        prepared: PreparedCreation,
        activator: Callable[[PreparedCreation], Any],
    ) -> Any:
        if not isinstance(prepared, PreparedCreation):
            _fail("publication.invalid_prepared", "activate requires PreparedCreation")
        if not callable(activator):
            _fail("publication.invalid_activator", "activator must be callable")
        result = activator(prepared)
        self.active = prepared
        return result

    def load_hosted(
        self,
        store: "HostedReleaseStore",
        locator: CreationRevisionId | HostedReleaseId | str,
        activator: Callable[[PreparedCreation], Any],
    ) -> Any:
        revision = store.resolve(locator)
        return self.activate(self.prepare(store.get(revision)), activator)

    def load_offline(
        self,
        library: "OfflineLibrary",
        revision: CreationRevisionId,
        activator: Callable[[PreparedCreation], Any],
    ) -> Any:
        return self.activate(self.prepare(library.get(revision)), activator)


class HostedReleaseStore:
    """Immutable release/revision store plus deliberately mutable friendly aliases."""

    def __init__(self):
        self._creations: dict[CreationRevisionId, PublishedCreation] = {}
        self._releases: dict[HostedReleaseId, CreationRevisionId] = {}
        self._aliases: dict[str, HostedReleaseId] = {}

    def publish_release(
        self,
        release_id: HostedReleaseId,
        published: PublishedCreation,
    ) -> CreationRevisionId:
        manifest = decode_creation_manifest(published.manifest_bytes)
        prior_creation = self._creations.get(manifest.creation_revision_id)
        if prior_creation is not None and (
            prior_creation.manifest_bytes != published.manifest_bytes
            or dict(prior_creation.blobs) != dict(published.blobs)
        ):
            _fail("publication.immutable_rebind", "CreationRevisionId cannot be rebound to different bytes")
        prior_release = self._releases.get(release_id)
        if prior_release is not None and prior_release != manifest.creation_revision_id:
            _fail("publication.immutable_release", "HostedReleaseId cannot retarget")
        self._creations[manifest.creation_revision_id] = published
        self._releases[release_id] = manifest.creation_revision_id
        return manifest.creation_revision_id

    def retarget_alias(self, alias: str, release_id: HostedReleaseId) -> None:
        if not isinstance(alias, str) or _ALIAS_RE.fullmatch(alias) is None:
            _fail("publication.invalid_alias", "friendly alias is invalid or unbounded")
        if release_id not in self._releases:
            _fail("publication.unknown_release", "friendly alias must point to an existing immutable release")
        self._aliases[alias] = release_id

    def resolve(self, locator: CreationRevisionId | HostedReleaseId | str) -> CreationRevisionId:
        if isinstance(locator, CreationRevisionId):
            if locator not in self._creations:
                _fail("publication.unknown_revision", "unknown immutable creation revision")
            return locator
        if isinstance(locator, HostedReleaseId):
            revision = self._releases.get(locator)
            if revision is None:
                _fail("publication.unknown_release", "unknown immutable hosted release")
            return revision
        if isinstance(locator, str):
            release = self._aliases.get(locator)
            if release is None:
                _fail("publication.unknown_alias", "unknown friendly alias")
            return self._releases[release]
        _fail("publication.invalid_locator", "hosted locator has unsupported identity role")

    def get(self, revision: CreationRevisionId) -> PublishedCreation:
        value = self._creations.get(revision)
        if value is None:
            _fail("publication.unknown_revision", "unknown immutable creation revision")
        return value


class OfflineLibrary:
    """Exact verified offline placements keyed only by CreationRevisionId."""

    def __init__(self, verifier: GenericPlayer):
        self.verifier = verifier
        self._installed: dict[CreationRevisionId, PublishedCreation] = {}

    def install(self, published: PublishedCreation) -> CreationRevisionId:
        prepared = self.verifier.prepare(published)
        revision = prepared.manifest.creation_revision_id
        prior = self._installed.get(revision)
        if prior is not None and (
            prior.manifest_bytes != published.manifest_bytes
            or dict(prior.blobs) != dict(published.blobs)
        ):
            _fail("publication.immutable_rebind", "offline CreationRevisionId cannot be rebound")
        self._installed[revision] = published
        return revision

    def get(self, revision: CreationRevisionId) -> PublishedCreation:
        value = self._installed.get(revision)
        if value is None:
            _fail("publication.offline_unavailable", "exact CreationRevisionId is not installed")
        return value


def bind_world_save(snapshot: WorldSaveSnapshot, prepared: PreparedCreation) -> WorldSaveBasis:
    """Anchor a WorldSave to an explicit creation basis without conflating IDs."""
    if snapshot.project_id != prepared.manifest.project_id:
        _fail("publication.world_basis_mismatch", "WorldSave project does not match creation basis")
    if snapshot.project_revision_id != prepared.manifest.project_revision_id:
        _fail("publication.world_basis_mismatch", "WorldSave project revision does not match creation basis")
    return WorldSaveBasis(
        snapshot.world_save_id,
        prepared.manifest.creation_revision_id,
        snapshot.project_id,
        snapshot.project_revision_id,
    )


def validate_world_save_basis(
    snapshot: WorldSaveSnapshot,
    basis: WorldSaveBasis,
    prepared: PreparedCreation,
) -> None:
    if snapshot.world_save_id != basis.world_save_id:
        _fail("publication.world_identity_mismatch", "WorldSaveId differs from explicit basis")
    if prepared.manifest.creation_revision_id != basis.creation_revision_id:
        _fail("publication.world_basis_mismatch", "WorldSave basis names another CreationRevisionId")
    if snapshot.project_id != basis.project_id or snapshot.project_revision_id != basis.project_revision_id:
        _fail("publication.world_basis_mismatch", "WorldSave authored basis differs from explicit creation basis")


def derive_target_media(
    prepared: PreparedCreation,
    asset_id: AssetId,
    target_profile: str,
    payload: bytes,
) -> TargetMediaDerivative:
    """Create target-private cache metadata without rewriting protected Asset data."""
    asset = prepared.protected_assets.get(asset_id)
    if asset is None:
        _fail("publication.unknown_asset", f"unknown protected AssetId {asset_id}")
    if not isinstance(target_profile, str) or not target_profile or len(target_profile) > 128:
        _fail("publication.invalid_target_profile", "target profile must be a bounded non-empty string")
    data = bytes(payload)
    return TargetMediaDerivative(
        asset_id,
        asset.revision_digest,
        target_profile,
        digest(data),
        len(data),
    )


def validate_target_media(prepared: PreparedCreation, derivative: TargetMediaDerivative) -> None:
    asset = prepared.protected_assets.get(derivative.asset_id)
    if asset is None or asset.revision_digest != derivative.canonical_asset_revision_digest:
        _fail("publication.target_media_basis_mismatch", "target derivative cannot substitute canonical Asset revision")


__all__ = [
    "BlobRef", "CREATION_ENVELOPE_SCHEMA", "CREATION_SCHEMA", "CreationId",
    "CreationManifest", "CreationRevisionId", "GENERIC_PLAYER_PROFILE", "GenericPlayer",
    "HostedReleaseId", "HostedReleaseStore", "NamedBlobRef", "OfflineLibrary",
    "PackageBlobRef", "PreparedCreation", "PublicationError", "PublishedCreation",
    "TargetMediaDerivative", "WorldSaveBasis", "bind_world_save",
    "decode_creation_manifest", "derive_target_media", "encode_creation_manifest",
    "publish_creation", "validate_target_media", "validate_world_save_basis",
]
