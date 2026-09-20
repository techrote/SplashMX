"""SMX-035 exact acquisition and transactional package/component update owner."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol

from splashmx.canonical.core import DefinitionId
from splashmx.runtime.streaming import ArtifactKind, ExactAcquirer, ExactArtifactDescriptor, ImmutableArtifactCache, StreamingError
from splashmx.security.capabilities import CapabilityBroker

from .bundle import decode_manifest, parse_spb1
from .model import (
    LockedPackage, PackageError, PackageId, PackageManifest, PortableComponent,
    ResolutionLock, fail, principal_for_component,
)


class PackageSource(Protocol):
    def __call__(self, descriptor: ExactArtifactDescriptor) -> bytes | None: ...


class MappingPackageSource:
    """Exact local/test package source keyed by PackageRevisionId text."""
    def __init__(self, payloads: Mapping[str, bytes]):
        self.payloads = {str(key): bytes(value) for key, value in payloads.items()}

    def __call__(self, descriptor: ExactArtifactDescriptor) -> bytes | None:
        prefix = "package-bundle:"
        key = descriptor.artifact_id[len(prefix):] if descriptor.artifact_id.startswith(prefix) else descriptor.artifact_id
        value = self.payloads.get(key)
        return None if value is None else bytes(value)


@dataclass(frozen=True)
class ValidatedPackage:
    locked: LockedPackage
    manifest: PackageManifest
    bundle_bytes: bytes
    cache_hit: bool = False


@dataclass(frozen=True)
class PackageRuntimeState:
    lock: ResolutionLock
    packages: Mapping[PackageId, ValidatedPackage]
    components: Mapping[DefinitionId, PortableComponent]
    live_state: Any = None

    @classmethod
    def empty(cls) -> "PackageRuntimeState":
        return cls(ResolutionLock("empty", {}), {}, {}, None)


MigrationPrepare = Callable[[PackageRuntimeState, Mapping[PackageId, ValidatedPackage]], Any]


def _descriptor(locked: LockedPackage) -> ExactArtifactDescriptor:
    return ExactArtifactDescriptor(
        f"package-bundle:{locked.package_revision_id}", ArtifactKind.OPAQUE_EXACT,
        locked.bundle_digest, locked.bundle_size,
    )


def acquire_locked_bundle(locked: LockedPackage, source: PackageSource, cache: ImmutableArtifactCache) -> tuple[bytes, bool]:
    """Acquire exactly the revision named by the lock; no range/catalog lookup exists here."""
    descriptor = _descriptor(locked)
    was_cached = cache.get(descriptor) is not None
    try:
        result = ExactAcquirer({descriptor.artifact_id: descriptor}, source, cache).acquire((descriptor.artifact_id,))
    except StreamingError as exc:
        code = "package.offline_unavailable" if exc.code == "streaming.dependency_unavailable" else "package.integrity_failure"
        raise PackageError(code, str(exc), cause=exc) from exc
    return result.payloads[descriptor.artifact_id], was_cached


def validate_locked_bundle(locked: LockedPackage, bundle_bytes: bytes, *, supported_features: Iterable[str] = ()) -> ValidatedPackage:
    """Complete physical+manifest+artifact validation before any migration/IR can run."""
    bundle = parse_spb1(bundle_bytes)
    if not bundle.entries or bundle.entries[0].artifact_id != "manifest" or bundle.entries[0].kind != "manifest":
        fail("package.manifest_missing", "SPB1 package must start with exactly one manifest entry")
    if sum(1 for row in bundle.entries if row.artifact_id == "manifest") != 1:
        fail("package.manifest_missing", "SPB1 package requires exactly one manifest")
    manifest = decode_manifest(bundle.payloads["manifest"])
    if manifest.package_id != locked.package_id or manifest.package_revision_id != locked.package_revision_id or manifest.human_version != locked.human_version:
        fail("package.lock_identity_mismatch", "package manifest does not match exact lock identity/version")
    unknown = set(manifest.required_features) - set(supported_features)
    if unknown:
        fail("package.unsupported_feature", f"package requires unsupported features {sorted(unknown)}")
    expected_children = {
        str(dep.package_id): dep for dep in manifest.dependencies if dep.kind.value != "optional"
    }
    # The exact lock stores child revisions, while the manifest stores requirements;
    # cardinality must agree. Resolution owns the PackageId->revision binding.
    if len(locked.dependencies) != len(expected_children):
        fail("package.lock_dependency_mismatch", "locked dependency closure differs from manifest")
    expected_artifacts = {spec.artifact_id: spec for spec in manifest.artifacts}
    actual_artifacts = {entry.artifact_id: entry for entry in bundle.entries if entry.artifact_id != "manifest"}
    if set(actual_artifacts) != set(expected_artifacts):
        fail("package.artifact_set_mismatch", "package artifact set differs from manifest")
    for artifact_id, spec in expected_artifacts.items():
        entry = actual_artifacts[artifact_id]
        if entry.kind != spec.kind or entry.digest != spec.digest or entry.length != spec.size_bytes:
            fail("package.artifact_mismatch", f"artifact {artifact_id} differs from exact manifest descriptor")
        if set(spec.required_features) - set(supported_features):
            fail("package.unsupported_feature", f"artifact {artifact_id} requires unsupported feature")
    # decode_manifest has already reconstructed and revalidated each complete
    # ProtectedAssetRevision, which rejects cross-revision field synthesis.
    return ValidatedPackage(locked, manifest, bytes(bundle_bytes), False)


def reconcile_components(previous: PortableComponent | None, candidate: PortableComponent, *, allow_interface_change: bool = False) -> None:
    if previous is None:
        return
    if previous.definition_id != candidate.definition_id:
        fail("package.lineage_mismatch", "update cannot replace root DefinitionId lineage")
    if previous.public_interface_digest != candidate.public_interface_digest and not allow_interface_change:
        fail("package.interface_incompatible", "stable public interface changed without explicit reconciliation")


def _preflight(package: ValidatedPackage, broker: CapabilityBroker | None, *, policy_time: int) -> dict[DefinitionId, Any]:
    if not package.manifest.capability_requests:
        return {}
    if broker is None:
        fail("package.capability_denied", "package requests capabilities but no trusted broker was supplied")
    grouped: dict[DefinitionId, list[Any]] = {}
    for request in package.manifest.capability_requests:
        grouped.setdefault(request.definition_id, []).append(request.requirement())
    plans = {}
    for definition_id, requirements in grouped.items():
        principal = principal_for_component(package.manifest.package_revision_id, definition_id)
        try:
            plans[definition_id] = broker.resolve_requirements(principal, tuple(requirements), now=policy_time)
        except Exception as exc:
            raise PackageError("package.capability_denied", str(exc), cause=exc) from exc
    return plans


class PackageSystem:
    """Prepare-before-publish package state.

    Acquisition, SPB1 parse, manifest validation, protected-asset reconstruction,
    artifact closure, feature checks, capability preflight and public-interface
    reconciliation all finish before ``migration_prepare`` is called. Only a fully
    prepared candidate replaces ``state``; failure leaves the previous exact lock
    and live state coherent. Immutable cache population is explicitly non-semantic.
    """
    def __init__(
        self, *, source: PackageSource, cache: ImmutableArtifactCache | None = None,
        capability_broker: CapabilityBroker | None = None,
        supported_features: Iterable[str] = (), migration_prepare: MigrationPrepare | None = None,
        initial_state: PackageRuntimeState | None = None,
    ):
        self.source = source
        self.cache = cache if cache is not None else ImmutableArtifactCache()
        self.capability_broker = capability_broker
        self.supported_features = frozenset(supported_features)
        self.migration_prepare = migration_prepare
        self.state = initial_state or PackageRuntimeState.empty()

    def apply_lock(self, lock: ResolutionLock, *, policy_time: int = 0, allow_interface_change: bool = False) -> PackageRuntimeState:
        if not isinstance(lock, ResolutionLock):
            fail("package.invalid_lock", "apply_lock requires ResolutionLock")
        staged: dict[PackageId, ValidatedPackage] = {}
        for package_id, locked in sorted(lock.packages.items(), key=lambda item: str(item[0])):
            descriptor = _descriptor(locked)
            if locked.lazy and self.cache.get(descriptor) is None:
                continue
            payload, cache_hit = acquire_locked_bundle(locked, self.source, self.cache)
            validated = validate_locked_bundle(locked, payload, supported_features=self.supported_features)
            staged[package_id] = ValidatedPackage(validated.locked, validated.manifest, validated.bundle_bytes, cache_hit)
        for package_id, locked in lock.packages.items():
            if not locked.lazy and package_id not in staged:
                fail("package.update_incomplete", f"non-lazy locked package {package_id} was not staged")
        for package in staged.values():
            _preflight(package, self.capability_broker, policy_time=policy_time)
        components: dict[DefinitionId, PortableComponent] = {}
        for package in staged.values():
            component = package.manifest.root_component
            reconcile_components(self.state.components.get(component.definition_id), component, allow_interface_change=allow_interface_change)
            if component.definition_id in components:
                fail("package.definition_conflict", f"multiple packages provide {component.definition_id}")
            components[component.definition_id] = component
        previous = self.state
        live_state = deepcopy(previous.live_state)
        if self.migration_prepare is not None:
            try:
                live_state = self.migration_prepare(previous, staged)
            except PackageError:
                raise
            except Exception as exc:
                raise PackageError("package.migration_failed", "package Behaviour/state migration preparation failed", cause=exc) from exc
        candidate = PackageRuntimeState(lock, dict(staged), components, deepcopy(live_state))
        self.state = candidate
        return candidate

    def demand_lazy(self, package_id: PackageId, *, policy_time: int = 0) -> ValidatedPackage:
        """Materialize only the exact revision already in the active lock; never re-solve."""
        locked = self.state.lock.require(package_id)
        existing = self.state.packages.get(package_id)
        if existing is not None:
            return existing
        if not locked.lazy:
            fail("package.update_incomplete", "non-lazy package is absent from active state")
        payload, cache_hit = acquire_locked_bundle(locked, self.source, self.cache)
        validated = validate_locked_bundle(locked, payload, supported_features=self.supported_features)
        package = ValidatedPackage(validated.locked, validated.manifest, validated.bundle_bytes, cache_hit)
        _preflight(package, self.capability_broker, policy_time=policy_time)
        component = package.manifest.root_component
        reconcile_components(self.state.components.get(component.definition_id), component)
        packages = dict(self.state.packages); packages[package_id] = package
        components = dict(self.state.components)
        if component.definition_id in components and components[component.definition_id] != component:
            fail("package.definition_conflict", f"lazy package conflicts on {component.definition_id}")
        components[component.definition_id] = component
        self.state = PackageRuntimeState(self.state.lock, packages, components, deepcopy(self.state.live_state))
        return package


__all__ = [
    "MappingPackageSource", "MigrationPrepare", "PackageRuntimeState", "PackageSource", "PackageSystem",
    "ValidatedPackage", "acquire_locked_bundle", "reconcile_components", "validate_locked_bundle",
]
