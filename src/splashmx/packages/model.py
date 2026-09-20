"""SMX-035 package semantic model.

Package metadata is distribution state around the existing Definition/Thing model.
It never creates a second object model and never serializes live authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import re
from typing import Any, Mapping, Sequence

from splashmx.canonical.core import DefinitionId, DefinitionRecord, PortId, SemanticId
from splashmx.canonical.serialization import ProtectedAssetRevision, encode_canonical_cbor
from splashmx.security.capabilities import CapabilityId, CapabilityRequirement, CapabilityScope, PrincipalId

MANIFEST_SCHEMA = "splashmx.package-manifest/1"
LOCK_SCHEMA = "splashmx.package-resolution-lock/1"
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_MANIFEST_FIELDS = {
    "capabilitygrant", "capabilitytoken", "grantid", "delegationgrant",
    "hosthandle", "hostobject", "sessionhandle", "sessionid", "processhandle",
    "socketid", "rawsocket", "connectionhandle", "transportpeerid",
    "javascriptbridge", "gdextension", "nativeextension", "installscript",
    "postinstall", "preinstall",
}


class PackageError(ValueError):
    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def fail(code: str, message: str) -> None:
    raise PackageError(code, message)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def token(value: str, role: str) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        fail("package.invalid_identity", f"{role} must be a bounded semantic token")


def require_digest(value: str, role: str) -> None:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        fail("package.invalid_digest", f"{role} must be sha256:<64 lowercase hex>")


def digest(payload: bytes) -> str:
    return "sha256:" + sha256(bytes(payload)).hexdigest()


def plain(value: Any, *, where: str = "manifest", depth: int = 0) -> Any:
    """Bounded recursively copied metadata with a live-authority firewall."""
    if depth > 64:
        fail("package.resource_exhausted", f"{where} exceeds nesting limit")
    if value is None or isinstance(value, (bool, str, bytes, int, float)):
        return bytes(value) if isinstance(value, bytes) else value
    if isinstance(value, (list, tuple)):
        return [plain(item, where=f"{where}[]", depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                fail("package.invalid_manifest", f"{where} keys must be strings")
            if _norm(key) in _FORBIDDEN_MANIFEST_FIELDS:
                fail("package.serialized_authority", f"{where} contains forbidden authority field {key!r}")
            out[key] = plain(child, where=f"{where}.{key}", depth=depth + 1)
        return out
    fail("package.invalid_manifest", f"{where} contains unsupported {type(value).__name__}")


class PackageId(SemanticId):
    role = "PackageId"


class PackageRevisionId(SemanticId):
    role = "PackageRevisionId"


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for value in (self.major, self.minor, self.patch):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail("package.invalid_version", "SemVer fields must be non-negative integers")

    @classmethod
    def parse(cls, text: str) -> "SemVer":
        match = _SEMVER_RE.fullmatch(text) if isinstance(text, str) else None
        if match is None:
            fail("package.invalid_version", "v1 versions must be normalized X.Y.Z")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Requirement:
    operator: str
    base: SemVer

    @classmethod
    def parse(cls, text: str) -> "Requirement":
        if not isinstance(text, str) or len(text) < 2 or text[0] not in "=^":
            fail("package.invalid_requirement", "v1 requirements are =X.Y.Z or ^X.Y.Z")
        return cls("exact" if text[0] == "=" else "caret", SemVer.parse(text[1:]))

    def matches(self, version: SemVer) -> bool:
        if self.operator == "exact":
            return version == self.base
        if self.operator != "caret":
            fail("package.invalid_requirement", "unknown requirement operator")
        low = self.base
        high = SemVer(low.major + 1, 0, 0) if low.major else (SemVer(0, low.minor + 1, 0) if low.minor else SemVer(0, 0, low.patch + 1))
        return low <= version < high

    def __str__(self) -> str:
        return ("=" if self.operator == "exact" else "^") + str(self.base)


class DependencyKind(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    LAZY = "lazy"


@dataclass(frozen=True)
class DependencySpec:
    package_id: PackageId
    requirement: Requirement
    kind: DependencyKind = DependencyKind.REQUIRED
    fallback: str | None = None

    def __post_init__(self) -> None:
        if self.kind is DependencyKind.OPTIONAL and (not isinstance(self.fallback, str) or not self.fallback):
            fail("package.optional_missing_fallback", "optional dependency requires an explicit fallback")
        if self.kind is not DependencyKind.OPTIONAL and self.fallback is not None:
            fail("package.invalid_fallback", "only optional dependencies may carry fallback")


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    kind: str
    digest: str
    size_bytes: int
    required_features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        token(self.artifact_id, "artifact_id")
        token(self.kind, "artifact kind")
        require_digest(self.digest, "artifact digest")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            fail("package.invalid_artifact", "artifact size must be non-negative")
        if len(set(self.required_features)) != len(self.required_features):
            fail("package.invalid_artifact", "duplicate required feature")


@dataclass(frozen=True)
class PublicPortSpec:
    port_id: PortId
    kind: str
    direction: str
    payload_contract: str = "any"

    def object(self) -> dict[str, Any]:
        return {"port_id": str(self.port_id), "kind": self.kind, "direction": self.direction, "payload_contract": self.payload_contract}


@dataclass(frozen=True)
class PortableComponent:
    definition_id: DefinitionId
    definition_revision: int
    root_element_id: str
    public_ports: tuple[PublicPortSpec, ...]
    public_interface_digest: str

    def __post_init__(self) -> None:
        require_digest(self.public_interface_digest, "public interface digest")
        if len({port.port_id for port in self.public_ports}) != len(self.public_ports):
            fail("package.invalid_component", "duplicate public PortId")


def promote_definition(definition: DefinitionRecord) -> PortableComponent:
    """Promote the existing Definition lineage; do not rewrite DefinitionId/PortId."""
    if not isinstance(definition, DefinitionRecord):
        fail("package.invalid_component", "promotion requires DefinitionRecord")
    ports: list[PublicPortSpec] = []
    for public_id, exposure in sorted(definition.exposures.items(), key=lambda item: str(item[0])):
        element = definition.elements.get(exposure.element_id)
        if element is None or exposure.element_port_id not in element.ports:
            fail("package.invalid_component", "definition exposure target is missing")
        port = element.ports[exposure.element_port_id]
        ports.append(PublicPortSpec(public_id, port.kind.value, port.direction.value))
    interface = [port.object() for port in ports]
    return PortableComponent(
        definition.definition_id,
        definition.revision,
        str(definition.root_element_id),
        tuple(ports),
        digest(encode_canonical_cbor(interface)),
    )


@dataclass(frozen=True)
class PackageCapabilityRequest:
    definition_id: DefinitionId
    capability_id: CapabilityId
    scope: CapabilityScope
    required: bool = True
    reduced_mode: str | None = None

    def requirement(self) -> CapabilityRequirement:
        return CapabilityRequirement(self.capability_id, self.scope, self.required, self.reduced_mode)


def principal_for_component(package_revision_id: PackageRevisionId, definition_id: DefinitionId) -> PrincipalId:
    """Package dependencies do not share a principal or inherit each other's grants."""
    return PrincipalId(f"package:{package_revision_id}:{definition_id}")


@dataclass(frozen=True)
class PackageManifest:
    package_id: PackageId
    package_revision_id: PackageRevisionId
    human_version: SemVer
    root_component: PortableComponent
    dependencies: tuple[DependencySpec, ...] = ()
    artifacts: tuple[ArtifactSpec, ...] = ()
    capability_requests: tuple[PackageCapabilityRequest, ...] = ()
    protected_assets: tuple[ProtectedAssetRevision, ...] = ()
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    licence_attribution: Mapping[str, Any] = field(default_factory=dict)
    remix_policy: Mapping[str, Any] = field(default_factory=dict)
    derivation_lineage: tuple[Mapping[str, Any], ...] = ()
    required_features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len({dep.package_id for dep in self.dependencies}) != len(self.dependencies):
            fail("package.invalid_manifest", "duplicate dependency PackageId")
        if len({row.artifact_id for row in self.artifacts}) != len(self.artifacts):
            fail("package.invalid_manifest", "duplicate artifact_id")
        if len({asset.asset_id for asset in self.protected_assets}) != len(self.protected_assets):
            fail("package.invalid_manifest", "duplicate protected AssetId")
        plain(self.source_metadata, where="source_metadata")
        plain(self.provenance, where="provenance")
        plain(self.licence_attribution, where="licence_attribution")
        plain(self.remix_policy, where="remix_policy")
        plain(self.derivation_lineage, where="derivation_lineage")


@dataclass(frozen=True)
class CatalogRow:
    package_id: PackageId
    package_revision_id: PackageRevisionId
    human_version: SemVer
    bundle_digest: str
    bundle_size: int
    dependencies: tuple[DependencySpec, ...] = ()
    revoked: bool = False

    def __post_init__(self) -> None:
        require_digest(self.bundle_digest, "bundle digest")
        if not isinstance(self.bundle_size, int) or isinstance(self.bundle_size, bool) or self.bundle_size < 0:
            fail("package.invalid_catalog", "bundle_size must be non-negative")


@dataclass(frozen=True)
class CatalogSnapshot:
    snapshot_id: str
    rows: tuple[CatalogRow, ...]

    def __post_init__(self) -> None:
        token(self.snapshot_id, "snapshot_id")
        seen: set[PackageRevisionId] = set()
        version_bindings: dict[tuple[PackageId, SemVer], PackageRevisionId] = {}
        for row in self.rows:
            if row.package_revision_id in seen:
                fail("package.invalid_catalog", "duplicate PackageRevisionId")
            seen.add(row.package_revision_id)
            key = (row.package_id, row.human_version)
            prior = version_bindings.get(key)
            if prior is not None and prior != row.package_revision_id:
                fail("package.ambiguous_version", f"{row.package_id} {row.human_version} binds multiple revisions")
            version_bindings[key] = row.package_revision_id


@dataclass(frozen=True)
class LockedPackage:
    package_id: PackageId
    package_revision_id: PackageRevisionId
    human_version: SemVer
    bundle_digest: str
    bundle_size: int
    dependencies: tuple[PackageRevisionId, ...] = ()
    lazy: bool = False

    def __post_init__(self) -> None:
        require_digest(self.bundle_digest, "locked bundle digest")


@dataclass(frozen=True)
class ResolutionLock:
    catalog_snapshot_id: str
    packages: Mapping[PackageId, LockedPackage]

    def require(self, package_id: PackageId) -> LockedPackage:
        result = self.packages.get(package_id)
        if result is None:
            fail("package.not_locked", f"{package_id} is not in the exact resolution lock")
        return result


__all__ = [
    "ArtifactSpec", "CatalogRow", "CatalogSnapshot", "DependencyKind", "DependencySpec",
    "LOCK_SCHEMA", "LockedPackage", "MANIFEST_SCHEMA", "PackageCapabilityRequest", "PackageError",
    "PackageId", "PackageManifest", "PackageRevisionId", "PortableComponent", "PublicPortSpec",
    "Requirement", "ResolutionLock", "SemVer", "digest", "fail", "plain", "principal_for_component",
    "promote_definition", "require_digest", "token", "_FORBIDDEN_MANIFEST_FIELDS",
]
