from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Mapping
import copy
import re


class PackageError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> "Version":
        match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", text)
        if not match:
            raise PackageError("invalid_version", text)
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def satisfies(version: Version, requirement: str) -> bool:
    """Tiny research-only exact/caret range language; production syntax remains open."""
    if requirement.startswith("="):
        return version == Version.parse(requirement[1:])
    base = Version.parse(requirement[1:] if requirement.startswith("^") else requirement)
    if version < base:
        return False
    if base.major > 0:
        return version.major == base.major
    if base.minor > 0:
        return version.major == 0 and version.minor == base.minor
    return version.major == 0 and version.minor == 0 and version.patch == base.patch


def frozen_scope(values: Iterable[str]) -> frozenset[str]:
    return frozenset(str(value) for value in values)


@dataclass(frozen=True)
class AssetRevision:
    asset_id: str
    digest: str
    source_identity: str
    source_metadata: tuple[str, ...]
    media_semantics: tuple[str, ...]
    provenance: tuple[str, ...]
    license_expression: str
    derivation: tuple[str, ...]

    def validate(self) -> None:
        fields = {
            "asset_id": self.asset_id, "digest": self.digest,
            "source_identity": self.source_identity, "source_metadata": self.source_metadata,
            "media_semantics": self.media_semantics, "provenance": self.provenance,
            "license_expression": self.license_expression, "derivation": self.derivation,
        }
        missing = [name for name, value in fields.items() if not value]
        if missing:
            raise PackageError("incomplete_asset_revision", ",".join(missing))
        if not self.digest.startswith("sha256:"):
            raise PackageError("invalid_asset_digest", self.asset_id)


@dataclass(frozen=True)
class DependencyRequirement:
    package_id: str
    constraint: str
    mode: str = "required"
    requested_interfaces: tuple[str, ...] = ()
    fallback: str | None = None

    def validate(self) -> None:
        if self.mode not in {"required", "optional", "lazy"}:
            raise PackageError("invalid_dependency_mode", self.mode)
        if self.mode == "optional" and not self.fallback:
            raise PackageError("optional_dependency_requires_fallback", self.package_id)
        sample = self.constraint[1:] if self.constraint[:1] in {"=", "^"} else self.constraint
        Version.parse(sample)


@dataclass(frozen=True)
class CapabilityRequest:
    name: str
    scope: frozenset[str]
    required: bool = True
    rationale: str = ""

    def validate(self) -> None:
        if not self.name or not self.scope:
            raise PackageError("invalid_capability_request", self.name)


@dataclass(frozen=True)
class PackageRevision:
    package_id: str
    version: Version
    revision_id: str
    content_digest: str
    byte_size: int
    root_definition_id: str
    root_definition_revision: str
    element_ids: tuple[str, ...]
    public_ports: tuple[str, ...]
    public_properties: tuple[str, ...] = ()
    dependencies: tuple[DependencyRequirement, ...] = ()
    capabilities: tuple[CapabilityRequest, ...] = ()
    assets: tuple[AssetRevision, ...] = ()
    state_schema: int = 1
    required_features: tuple[str, ...] = ()
    source_visibility: str = "included"
    remix_permission: str = "allowed"
    license_expression: str = "NOASSERTION"
    attribution: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    signature_key_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        required_text = (self.package_id, self.revision_id, self.content_digest,
                         self.root_definition_id, self.root_definition_revision,
                         self.license_expression)
        if any(not value for value in required_text):
            raise PackageError("invalid_manifest", self.package_id)
        if not self.content_digest.startswith("sha256:") or self.byte_size <= 0:
            raise PackageError("invalid_descriptor", self.package_id)
        if self.state_schema < 1:
            raise PackageError("invalid_state_schema", self.package_id)
        if self.source_visibility not in {"included", "linked", "sealed"}:
            raise PackageError("invalid_source_visibility", self.source_visibility)
        if self.remix_permission not in {"allowed", "restricted", "forbidden"}:
            raise PackageError("invalid_remix_permission", self.remix_permission)
        if len(set(self.element_ids)) != len(self.element_ids):
            raise PackageError("duplicate_element_id", self.package_id)
        if len(set(self.public_ports)) != len(self.public_ports):
            raise PackageError("duplicate_public_port", self.package_id)
        if len(set(self.public_properties)) != len(self.public_properties):
            raise PackageError("duplicate_public_property", self.package_id)
        dep_ids = [dep.package_id for dep in self.dependencies]
        if len(set(dep_ids)) != len(dep_ids):
            raise PackageError("duplicate_dependency", self.package_id)
        for dep in self.dependencies:
            dep.validate()
        for cap in self.capabilities:
            cap.validate()
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise PackageError("duplicate_asset_id", self.package_id)
        for asset in self.assets:
            asset.validate()


@dataclass(frozen=True)
class LocalDefinition:
    definition_id: str
    revision_id: str
    element_ids: tuple[str, ...]
    public_ports: tuple[str, ...]
    public_properties: tuple[str, ...]
    first_instance_thing_ids: tuple[str, ...]


@dataclass(frozen=True)
class PromotionResult:
    package: PackageRevision
    preserved_definition_id: str
    preserved_element_ids: tuple[str, ...]
    preserved_port_ids: tuple[str, ...]
    preserved_first_instance_thing_ids: tuple[str, ...]


def promote_local_definition(local: LocalDefinition, *, package_id: str, version: str,
                             package_revision_id: str, content_digest: str,
                             byte_size: int = 1024,
                             dependencies: tuple[DependencyRequirement, ...] = (),
                             capabilities: tuple[CapabilityRequest, ...] = (),
                             assets: tuple[AssetRevision, ...] = (),
                             source_visibility: str = "included",
                             remix_permission: str = "allowed",
                             license_expression: str = "NOASSERTION",
                             attribution: tuple[str, ...] = (),
                             provenance: tuple[str, ...] = (),
                             signature_key_ids: tuple[str, ...] = ()) -> PromotionResult:
    package = PackageRevision(
        package_id=package_id, version=Version.parse(version), revision_id=package_revision_id,
        content_digest=content_digest, byte_size=byte_size,
        root_definition_id=local.definition_id, root_definition_revision=local.revision_id,
        element_ids=local.element_ids, public_ports=local.public_ports,
        public_properties=local.public_properties, dependencies=dependencies,
        capabilities=capabilities, assets=assets, source_visibility=source_visibility,
        remix_permission=remix_permission, license_expression=license_expression,
        attribution=attribution, provenance=provenance, signature_key_ids=signature_key_ids,
    )
    package.validate()
    return PromotionResult(package, local.definition_id, local.element_ids,
                           local.public_ports, local.first_instance_thing_ids)


class PackageRepository:
    def __init__(self) -> None:
        self._revisions: dict[str, list[PackageRevision]] = {}

    def add(self, package: PackageRevision) -> None:
        package.validate()
        revisions = self._revisions.setdefault(package.package_id, [])
        for existing in revisions:
            if existing.revision_id == package.revision_id and existing.content_digest != package.content_digest:
                raise PackageError("revision_identity_collision", package.revision_id)
            if existing.version == package.version and existing.revision_id != package.revision_id:
                raise PackageError("ambiguous_version", f"{package.package_id}@{package.version}")
            if existing == package:
                return
        revisions.append(package)
        revisions.sort(key=lambda candidate: candidate.version, reverse=True)

    def candidates(self, package_id: str, constraint: str) -> list[PackageRevision]:
        return [revision for revision in self._revisions.get(package_id, ())
                if satisfies(revision.version, constraint)]


@dataclass(frozen=True)
class LockEntry:
    package_id: str
    version: str
    revision_id: str
    digest: str
    byte_size: int
    required_features: tuple[str, ...]
    provenance: tuple[str, ...]
    mode_from_parent: str

    @property
    def cache_key(self) -> tuple[str, str, str]:
        return (self.package_id, self.revision_id, self.digest)


@dataclass
class Resolution:
    root_package_id: str
    packages: dict[str, PackageRevision]
    lock: dict[str, LockEntry]
    dependency_paths: dict[str, tuple[str, ...]]
    optional_fallbacks: dict[tuple[str, str], str]
    lazy_requirements: list[tuple[str, DependencyRequirement]]

    def clone(self) -> "Resolution":
        return copy.deepcopy(self)


class Resolver:
    def __init__(self, repository: PackageRepository, *,
                 revoked_revisions: set[tuple[str, str]] | None = None,
                 max_depth: int = 8, max_packages: int = 32,
                 max_total_bytes: int = 64 * 1024 * 1024) -> None:
        self.repository = repository
        self.revoked_revisions = revoked_revisions or set()
        self.max_depth = max_depth
        self.max_packages = max_packages
        self.max_total_bytes = max_total_bytes

    def resolve(self, package_id: str, constraint: str) -> Resolution:
        packages: dict[str, PackageRevision] = {}
        lock: dict[str, LockEntry] = {}
        paths: dict[str, tuple[str, ...]] = {}
        optional: dict[tuple[str, str], str] = {}
        lazy: list[tuple[str, DependencyRequirement]] = []
        requested_constraints: dict[str, list[str]] = {}
        total_bytes = 0

        def visit(current_id: str, current_constraint: str,
                  path: tuple[str, ...], mode: str) -> None:
            nonlocal total_bytes
            if len(path) > self.max_depth:
                raise PackageError("dependency_depth_exceeded", " -> ".join(path))
            if current_id in path[:-1]:
                raise PackageError("dependency_cycle", " -> ".join(path))
            requested_constraints.setdefault(current_id, []).append(current_constraint)
            if current_id in packages:
                chosen = packages[current_id]
                if not all(satisfies(chosen.version, req) for req in requested_constraints[current_id]):
                    raise PackageError("version_conflict", current_id)
                return
            candidates = self.repository.candidates(current_id, current_constraint)
            if not candidates:
                raise PackageError("missing_dependency", f"{current_id} {current_constraint}")
            usable = [candidate for candidate in candidates
                      if (candidate.package_id, candidate.revision_id) not in self.revoked_revisions]
            if not usable:
                raise PackageError("revoked_package", current_id)
            chosen = usable[0]
            if not all(satisfies(chosen.version, req) for req in requested_constraints[current_id]):
                raise PackageError("version_conflict", current_id)
            if len(packages) + 1 > self.max_packages:
                raise PackageError("dependency_count_exceeded", current_id)
            if total_bytes + chosen.byte_size > self.max_total_bytes:
                raise PackageError("dependency_bytes_exceeded", current_id)
            chosen.validate()
            packages[current_id] = chosen
            paths[current_id] = path
            lock[current_id] = LockEntry(current_id, str(chosen.version), chosen.revision_id,
                                         chosen.content_digest, chosen.byte_size,
                                         chosen.required_features, chosen.provenance, mode)
            total_bytes += chosen.byte_size
            for dep in chosen.dependencies:
                if dep.mode == "lazy":
                    lazy.append((current_id, dep))
                    continue
                dep_candidates = self.repository.candidates(dep.package_id, dep.constraint)
                dep_usable = [candidate for candidate in dep_candidates
                              if (candidate.package_id, candidate.revision_id) not in self.revoked_revisions]
                if not dep_usable:
                    if dep.mode == "optional":
                        optional[(current_id, dep.package_id)] = dep.fallback or "degraded"
                        continue
                    if dep_candidates:
                        raise PackageError("revoked_package", dep.package_id)
                    raise PackageError("missing_dependency", dep.package_id)
                visit(dep.package_id, dep.constraint, path + (dep.package_id,), dep.mode)

        visit(package_id, constraint, (package_id,), "root")
        for resolved_id, constraints in requested_constraints.items():
            if not all(satisfies(packages[resolved_id].version, req) for req in constraints):
                raise PackageError("version_conflict", resolved_id)
        return Resolution(package_id, packages, lock, paths, optional, lazy)

    def validate_lock(self, resolution: Resolution) -> None:
        for package_id, package in resolution.packages.items():
            entry = resolution.lock[package_id]
            if (package_id, entry.revision_id) in self.revoked_revisions:
                raise PackageError("revoked_package", package_id)
            if package.revision_id != entry.revision_id or package.content_digest != entry.digest:
                raise PackageError("lock_mismatch", package_id)
            package.validate()


@dataclass
class Cache:
    available: set[tuple[str, str, str]] = field(default_factory=set)

    def add_resolution(self, resolution: Resolution) -> None:
        self.available.update(entry.cache_key for entry in resolution.lock.values())

    def evict(self, entry: LockEntry) -> None:
        self.available.discard(entry.cache_key)


def validate_offline(resolution: Resolution, cache: Cache) -> None:
    for package_id, entry in resolution.lock.items():
        if entry.cache_key not in cache.available:
            raise PackageError("offline_unavailable", package_id)


def verify_observed_digest(entry: LockEntry, observed_digest: str) -> None:
    if observed_digest != entry.digest:
        raise PackageError("digest_mismatch", entry.package_id)


@dataclass(frozen=True)
class CapabilityPlanItem:
    package_id: str
    attribution_path: tuple[str, ...]
    request: CapabilityRequest


def capability_plan(resolution: Resolution) -> tuple[CapabilityPlanItem, ...]:
    plan: list[CapabilityPlanItem] = []
    for package_id in sorted(resolution.packages):
        for request in resolution.packages[package_id].capabilities:
            plan.append(CapabilityPlanItem(package_id, resolution.dependency_paths[package_id], request))
    return tuple(plan)


@dataclass
class CapabilityPolicy:
    grants: dict[tuple[str, str], frozenset[str]] = field(default_factory=dict)

    def grant(self, package_id: str, capability: str, scope: Iterable[str]) -> None:
        self.grants[(package_id, capability)] = frozen_scope(scope)

    def permits(self, package_id: str, request: CapabilityRequest) -> bool:
        grant = self.grants.get((package_id, request.name))
        return grant is not None and request.scope.issubset(grant)


def authorize(resolution: Resolution, policy: CapabilityPolicy) -> tuple[tuple[str, str], ...]:
    degraded: list[tuple[str, str]] = []
    for item in capability_plan(resolution):
        if policy.permits(item.package_id, item.request):
            continue
        if item.request.required:
            raise PackageError("capability_denied", f"{item.package_id}:{item.request.name}")
        degraded.append((item.package_id, item.request.name))
    return tuple(degraded)


@dataclass(frozen=True)
class DelegatedGrant:
    principal: str
    capability: str
    scope: frozenset[str]


def delegate_capability(*, source_principal: str, target_principal: str,
                        capability: str, source_scope: frozenset[str],
                        requested_scope: frozenset[str], delegable: bool) -> DelegatedGrant:
    if not delegable:
        raise PackageError("delegation_forbidden", source_principal)
    if not requested_scope.issubset(source_scope):
        raise PackageError("delegation_widens_scope", target_principal)
    return DelegatedGrant(target_principal, capability, requested_scope)


@dataclass
class ComponentInstance:
    thing_id: str
    package_id: str
    definition_id: str
    base_definition_revision: str
    overlays: dict[str, object]
    persistent_state: dict[str, object]
    protected_ports: set[str] = field(default_factory=set)


class Project:
    def __init__(self) -> None:
        self.resolution: Resolution | None = None
        self.instances: dict[str, ComponentInstance] = {}
        self.degraded_capabilities: tuple[tuple[str, str], ...] = ()

    def install(self, resolution: Resolution, policy: CapabilityPolicy) -> None:
        for package in resolution.packages.values():
            package.validate()
        degraded = authorize(resolution, policy)
        self.resolution = resolution.clone()
        self.degraded_capabilities = degraded

    def add_instance(self, *, thing_id: str, package_id: str,
                     overlays: Mapping[str, object] | None = None,
                     persistent_state: Mapping[str, object] | None = None,
                     protected_ports: Iterable[str] = ()) -> None:
        if self.resolution is None or package_id not in self.resolution.packages:
            raise PackageError("package_not_installed", package_id)
        if thing_id in self.instances:
            raise PackageError("duplicate_thing_id", thing_id)
        package = self.resolution.packages[package_id]
        self.instances[thing_id] = ComponentInstance(
            thing_id, package_id, package.root_definition_id,
            package.root_definition_revision, dict(overlays or {}),
            dict(persistent_state or {}), set(protected_ports))

    def update(self, new_resolution: Resolution, policy: CapabilityPolicy, *,
               state_migrators: Mapping[tuple[str, int, int],
                                        Callable[[dict[str, object]], dict[str, object]]] | None = None) -> None:
        if self.resolution is None:
            raise PackageError("nothing_installed")
        degraded = authorize(new_resolution, policy)
        state_migrators = state_migrators or {}
        staged_instances = copy.deepcopy(self.instances)
        for thing_id, instance in staged_instances.items():
            if instance.package_id not in new_resolution.packages:
                raise PackageError("update_drops_installed_package", instance.package_id)
            old_package = self.resolution.packages[instance.package_id]
            new_package = new_resolution.packages[instance.package_id]
            if old_package.root_definition_id != new_package.root_definition_id:
                raise PackageError("definition_identity_changed", instance.package_id)
            if (set(old_package.public_ports) - set(new_package.public_ports)) & instance.protected_ports:
                raise PackageError("interface_incompatible", thing_id)
            valid_loci = {
                *(f"property:{name}" for name in new_package.public_properties),
                *(f"element:{element_id}" for element_id in new_package.element_ids),
                *(f"port:{port_id}" for port_id in new_package.public_ports),
            }
            invalid = set(instance.overlays) - valid_loci
            if invalid:
                raise PackageError("overlay_incompatible", f"{thing_id}:{sorted(invalid)}")
            if old_package.state_schema != new_package.state_schema:
                key = (instance.package_id, old_package.state_schema, new_package.state_schema)
                migrator = state_migrators.get(key)
                if migrator is None:
                    raise PackageError("migration_required", instance.package_id)
                migrated = migrator(copy.deepcopy(instance.persistent_state))
                if not isinstance(migrated, dict):
                    raise PackageError("migration_invalid_result", instance.package_id)
                instance.persistent_state = migrated
            instance.base_definition_revision = new_package.root_definition_revision
        self.resolution = new_resolution.clone()
        self.instances = staged_instances
        self.degraded_capabilities = degraded

    def remove_package(self, package_id: str) -> None:
        if self.resolution is None or package_id not in self.resolution.packages:
            return
        if any(instance.package_id == package_id for instance in self.instances.values()):
            raise PackageError("package_in_use", package_id)
        for owner_id, package in self.resolution.packages.items():
            if owner_id != package_id and any(dep.package_id == package_id for dep in package.dependencies):
                raise PackageError("package_required_by_dependency", f"{owner_id}->{package_id}")
        del self.resolution.packages[package_id]
        self.resolution.lock.pop(package_id, None)
        self.resolution.dependency_paths.pop(package_id, None)


def replace_asset_revision(package: PackageRevision, replacement: AssetRevision) -> PackageRevision:
    replacement.validate()
    assets = list(package.assets)
    for index, existing in enumerate(assets):
        if existing.asset_id == replacement.asset_id:
            assets[index] = replacement
            updated = replace(package, assets=tuple(assets))
            updated.validate()
            return updated
    raise PackageError("unknown_asset", replacement.asset_id)


def reconcile_concurrent_asset_replacements(left: AssetRevision, right: AssetRevision) -> tuple[AssetRevision, AssetRevision]:
    left.validate(); right.validate()
    if left.asset_id != right.asset_id:
        raise PackageError("different_asset_ids")
    if left == right:
        return (left, left)
    return (left, right)
