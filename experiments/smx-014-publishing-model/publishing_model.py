from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping


FORBIDDEN_CANONICAL_KEYS = {
    "nodepath",
    "rid",
    "resourceuid",
    "godot_resource_path",
    "godot_scene_path",
    "peer_id",
    "socket",
    "javascript_object",
    "capability_handle",
}


def digest_bytes(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return digest_bytes(payload)


class PublishError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ProtectedAssetRevision:
    asset_id: str
    blob_digest: str
    source_id: str
    source_metadata: str
    media_semantics: str
    provenance: str
    licence: str
    derivation: str

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, str) or not value:
                raise PublishError("invalid_protected_asset_revision", name)
        if not self.blob_digest.startswith("sha256:"):
            raise PublishError("invalid_protected_asset_revision", "blob_digest")

    def record(self) -> dict[str, str]:
        self.validate()
        return dict(self.__dict__)


@dataclass(frozen=True)
class AssetUse:
    revision: ProtectedAssetRevision
    role: str  # simulation_required | presentation_required | presentation_optional

    def validate(self) -> None:
        self.revision.validate()
        if self.role not in {"simulation_required", "presentation_required", "presentation_optional"}:
            raise PublishError("invalid_asset_role", self.role)

    def record(self) -> dict[str, object]:
        self.validate()
        return {"role": self.role, "revision": self.revision.record()}


@dataclass(frozen=True)
class LockedDependency:
    package_id: str
    package_revision_id: str
    blob_digest: str
    byte_size: int

    def validate(self) -> None:
        if not self.package_id or not self.package_revision_id:
            raise PublishError("invalid_dependency_lock")
        if not self.blob_digest.startswith("sha256:") or self.byte_size < 0:
            raise PublishError("invalid_dependency_lock", self.package_id)

    def record(self) -> dict[str, object]:
        self.validate()
        return dict(self.__dict__)


@dataclass(frozen=True)
class CapabilityRequest:
    name: str
    required: bool

    def record(self) -> dict[str, object]:
        if not self.name:
            raise PublishError("invalid_capability_request")
        return {"name": self.name, "required": self.required}


@dataclass(frozen=True)
class EditableProject:
    project_id: str
    project_revision_id: str
    creation_id: str
    canonical_records: Mapping[str, object]
    schema_version: int
    ir_version: int
    required_features: tuple[str, ...] = ()
    optional_features: tuple[str, ...] = ()
    dependencies: tuple[LockedDependency, ...] = ()
    assets: tuple[AssetUse, ...] = ()
    capability_requests: tuple[CapabilityRequest, ...] = ()
    network_declaration: Mapping[str, object] = field(default_factory=dict)
    optional_extensions: Mapping[str, object] = field(default_factory=dict)
    required_extensions: Mapping[str, object] = field(default_factory=dict)

    def semantic_record(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "project_revision_id": self.project_revision_id,
            "creation_id": self.creation_id,
            "canonical_records": dict(self.canonical_records),
            "schema_version": self.schema_version,
            "ir_version": self.ir_version,
            "required_features": sorted(self.required_features),
            "optional_features": sorted(self.optional_features),
            "dependencies": [d.record() for d in sorted(self.dependencies, key=lambda d: d.package_id)],
            "assets": [a.record() for a in sorted(self.assets, key=lambda a: a.revision.asset_id)],
            "capability_requests": [c.record() for c in sorted(self.capability_requests, key=lambda c: c.name)],
            "network_declaration": dict(self.network_declaration),
            "optional_extensions": dict(self.optional_extensions),
            "required_extensions": dict(self.required_extensions),
        }


@dataclass(frozen=True)
class PublishedCreation:
    creation_id: str
    creation_revision_id: str
    source_project_revision_id: str
    semantic_digest: str
    schema_version: int
    ir_version: int
    required_features: tuple[str, ...]
    optional_features: tuple[str, ...]
    dependencies: tuple[LockedDependency, ...]
    assets: tuple[AssetUse, ...]
    capability_requests: tuple[CapabilityRequest, ...]
    network_declaration: Mapping[str, object]
    optional_extensions: Mapping[str, object]
    required_extensions: Mapping[str, object]

    def manifest_record(self) -> dict[str, object]:
        return {
            "creation_id": self.creation_id,
            "creation_revision_id": self.creation_revision_id,
            "source_project_revision_id": self.source_project_revision_id,
            "semantic_digest": self.semantic_digest,
            "schema_version": self.schema_version,
            "ir_version": self.ir_version,
            "required_features": list(self.required_features),
            "optional_features": list(self.optional_features),
            "dependencies": [d.record() for d in self.dependencies],
            "assets": [a.record() for a in self.assets],
            "capability_requests": [c.record() for c in self.capability_requests],
            "network_declaration": dict(self.network_declaration),
            "optional_extensions": dict(self.optional_extensions),
            "required_extensions": dict(self.required_extensions),
        }

    @property
    def manifest_digest(self) -> str:
        return canonical_digest(self.manifest_record())


@dataclass(frozen=True)
class RuntimeContract:
    runtime_id: str
    runtime_version: str
    build_digest: str
    target: str  # web | native | headless
    supported_schema_versions: tuple[int, ...]
    supported_ir_versions: tuple[int, ...]
    features: frozenset[str]
    understood_optional_extensions: frozenset[str] = frozenset()
    hardened: bool = True

    def validate(self) -> None:
        if self.target not in {"web", "native", "headless"}:
            raise PublishError("invalid_runtime_target", self.target)
        if not self.build_digest.startswith("sha256:"):
            raise PublishError("invalid_runtime_build")


@dataclass(frozen=True)
class Migration:
    from_schema: int
    to_schema: int
    capability_free: bool
    transform: Callable[[PublishedCreation], PublishedCreation]


@dataclass(frozen=True)
class LaunchPlan:
    creation: PublishedCreation
    runtime: RuntimeContract
    omitted_features: tuple[str, ...]
    omitted_assets: tuple[str, ...]
    denied_optional_capabilities: tuple[str, ...]
    target_payload_digests: tuple[str, ...]
    migration_path: tuple[tuple[int, int], ...]

    def reproducibility_record(self) -> dict[str, object]:
        return {
            "creation_id": self.creation.creation_id,
            "creation_revision_id": self.creation.creation_revision_id,
            "manifest_digest": self.creation.manifest_digest,
            "runtime_id": self.runtime.runtime_id,
            "runtime_version": self.runtime.runtime_version,
            "runtime_build_digest": self.runtime.build_digest,
            "target": self.runtime.target,
            "dependency_lock": [d.record() for d in self.creation.dependencies],
            "target_payload_digests": list(self.target_payload_digests),
            "migration_path": [list(x) for x in self.migration_path],
        }


@dataclass(frozen=True)
class WorldSave:
    world_id: str
    world_revision_id: str
    basis_creation_id: str
    basis_creation_revision_id: str
    world_schema_version: int
    state: Mapping[str, object]

    def validate(self) -> None:
        forbidden = {k.lower() for k in self.state}.intersection(FORBIDDEN_CANONICAL_KEYS)
        if forbidden:
            raise PublishError("transient_context_in_world_save", sorted(forbidden)[0])


@dataclass(frozen=True)
class HostedRelease:
    release_id: str
    creation_id: str
    creation_revision_id: str
    runtime_channel: str


@dataclass(frozen=True)
class OfflineBundle:
    creation: PublishedCreation
    runtime_build_digest: str
    blobs: Mapping[str, bytes]


class Publisher:
    """Non-production deterministic publisher. It never compiles or exports Godot projects."""

    def __init__(self) -> None:
        self.export_tool_invocations = 0

    @staticmethod
    def _reject_engine_identity(value: object) -> None:
        def walk(v: object) -> None:
            if isinstance(v, Mapping):
                for key, child in v.items():
                    if str(key).lower() in FORBIDDEN_CANONICAL_KEYS:
                        raise PublishError("engine_identity_leak", str(key))
                    walk(child)
            elif isinstance(v, (list, tuple)):
                for child in v:
                    walk(child)
        walk(value)

    def publish(self, project: EditableProject) -> PublishedCreation:
        record = project.semantic_record()
        self._reject_engine_identity(record)
        for asset in project.assets:
            asset.validate()
        for dep in project.dependencies:
            dep.validate()
        if project.schema_version <= 0 or project.ir_version <= 0:
            raise PublishError("invalid_version")
        semantic_digest = canonical_digest(record)
        revision_id = "creationrev:" + semantic_digest.split(":", 1)[1][:24]
        return PublishedCreation(
            creation_id=project.creation_id,
            creation_revision_id=revision_id,
            source_project_revision_id=project.project_revision_id,
            semantic_digest=semantic_digest,
            schema_version=project.schema_version,
            ir_version=project.ir_version,
            required_features=tuple(sorted(project.required_features)),
            optional_features=tuple(sorted(project.optional_features)),
            dependencies=tuple(sorted(project.dependencies, key=lambda d: d.package_id)),
            assets=tuple(sorted(project.assets, key=lambda a: a.revision.asset_id)),
            capability_requests=tuple(sorted(project.capability_requests, key=lambda c: c.name)),
            network_declaration=dict(project.network_declaration),
            optional_extensions=dict(project.optional_extensions),
            required_extensions=dict(project.required_extensions),
        )


class GenericPlayer:
    """Precompiled-runtime proof: prepare validates everything before activate() counts execution."""

    def __init__(self, contract: RuntimeContract) -> None:
        contract.validate()
        self.contract = contract
        self.activation_count = 0

    @staticmethod
    def _verify_blob(blob_digest: str, expected_size: int | None, blobs: Mapping[str, bytes]) -> None:
        if blob_digest not in blobs:
            raise PublishError("required_blob_missing", blob_digest)
        data = blobs[blob_digest]
        if expected_size is not None and len(data) != expected_size:
            raise PublishError("blob_size_mismatch", blob_digest)
        if digest_bytes(data) != blob_digest:
            raise PublishError("blob_digest_mismatch", blob_digest)

    def _migrate(
        self,
        creation: PublishedCreation,
        migrations: Iterable[Migration],
    ) -> tuple[PublishedCreation, tuple[tuple[int, int], ...]]:
        if creation.schema_version in self.contract.supported_schema_versions:
            return creation, ()
        by_source: dict[int, list[Migration]] = {}
        for migration in migrations:
            by_source.setdefault(migration.from_schema, []).append(migration)
        current = creation
        path: list[tuple[int, int]] = []
        seen: set[int] = set()
        while current.schema_version not in self.contract.supported_schema_versions:
            if current.schema_version in seen:
                raise PublishError("migration_cycle")
            seen.add(current.schema_version)
            choices = sorted(by_source.get(current.schema_version, []), key=lambda m: m.to_schema)
            if not choices:
                raise PublishError("runtime_schema_incompatible", str(current.schema_version))
            migration = choices[0]
            if not migration.capability_free:
                raise PublishError("migration_requires_capability")
            before_revision = current.creation_revision_id
            staged = migration.transform(current)
            if staged.creation_id != current.creation_id or staged.creation_revision_id != before_revision:
                raise PublishError("migration_rewrites_creation_identity")
            if staged.schema_version != migration.to_schema:
                raise PublishError("invalid_migration_result")
            current = staged
            path.append((migration.from_schema, migration.to_schema))
            if len(path) > 16:
                raise PublishError("migration_budget_exceeded")
        return current, tuple(path)

    def prepare(
        self,
        creation: PublishedCreation,
        blobs: Mapping[str, bytes],
        granted_capabilities: Iterable[str] = (),
        migrations: Iterable[Migration] = (),
    ) -> LaunchPlan:
        creation, migration_path = self._migrate(creation, migrations)
        if creation.ir_version not in self.contract.supported_ir_versions:
            raise PublishError("runtime_ir_incompatible", str(creation.ir_version))
        missing_required = set(creation.required_features) - set(self.contract.features)
        if missing_required:
            raise PublishError("required_feature_unsupported", sorted(missing_required)[0])
        unknown_required_ext = set(creation.required_extensions) - set(self.contract.understood_optional_extensions)
        if unknown_required_ext:
            raise PublishError("required_extension_unsupported", sorted(unknown_required_ext)[0])
        omitted_features = tuple(sorted(set(creation.optional_features) - set(self.contract.features)))

        for dep in creation.dependencies:
            dep.validate()
            self._verify_blob(dep.blob_digest, dep.byte_size, blobs)

        omitted_assets: list[str] = []
        payload_digests: list[str] = []
        for use in creation.assets:
            use.validate()
            asset = use.revision
            if self.contract.target == "headless" and use.role in {"presentation_required", "presentation_optional"}:
                omitted_assets.append(asset.asset_id)
                continue
            if use.role == "presentation_optional" and asset.blob_digest not in blobs:
                omitted_assets.append(asset.asset_id)
                continue
            self._verify_blob(asset.blob_digest, None, blobs)
            payload_digests.append(asset.blob_digest)

        grants = set(granted_capabilities)
        denied_optional: list[str] = []
        for request in creation.capability_requests:
            if request.name in grants:
                continue
            if request.required:
                raise PublishError("required_capability_denied", request.name)
            denied_optional.append(request.name)

        return LaunchPlan(
            creation=creation,
            runtime=self.contract,
            omitted_features=omitted_features,
            omitted_assets=tuple(sorted(omitted_assets)),
            denied_optional_capabilities=tuple(sorted(denied_optional)),
            target_payload_digests=tuple(sorted(payload_digests)),
            migration_path=migration_path,
        )

    def activate(self, plan: LaunchPlan) -> dict[str, object]:
        if plan.runtime != self.contract:
            raise PublishError("plan_runtime_mismatch")
        self.activation_count += 1
        return {
            "active": True,
            "creation_id": plan.creation.creation_id,
            "creation_revision_id": plan.creation.creation_revision_id,
            "target": self.contract.target,
        }

    def launch_offline(self, bundle: OfflineBundle, granted_capabilities: Iterable[str] = ()) -> LaunchPlan:
        if bundle.runtime_build_digest != self.contract.build_digest:
            raise PublishError("offline_runtime_mismatch")
        return self.prepare(bundle.creation, bundle.blobs, granted_capabilities=granted_capabilities)


class ShareRegistry:
    """Tiny hosted-link model: aliases are mutable; resolved releases are immutable records."""

    def __init__(self) -> None:
        self.releases: dict[str, HostedRelease] = {}
        self.aliases: dict[str, str] = {}

    def add_release(self, release: HostedRelease) -> None:
        if release.release_id in self.releases and self.releases[release.release_id] != release:
            raise PublishError("release_identity_collision", release.release_id)
        self.releases[release.release_id] = release

    def point_alias(self, alias: str, release_id: str) -> None:
        if release_id not in self.releases:
            raise PublishError("unknown_release", release_id)
        self.aliases[alias] = release_id

    def resolve(self, alias_or_release: str) -> HostedRelease:
        release_id = self.aliases.get(alias_or_release, alias_or_release)
        if release_id not in self.releases:
            raise PublishError("unknown_release", alias_or_release)
        return self.releases[release_id]


def validate_world_basis(world: WorldSave, creation: PublishedCreation) -> None:
    world.validate()
    if world.basis_creation_id != creation.creation_id:
        raise PublishError("world_creation_mismatch")
    if world.basis_creation_revision_id != creation.creation_revision_id:
        raise PublishError("world_migration_required")


def per_creation_build_allowed(*, ordinary_content: bool, trusted_extension_requirement: bool) -> bool:
    """Exceptional path only: never a fallback for ordinary unsupported content."""
    return (not ordinary_content) and trusted_extension_requirement
