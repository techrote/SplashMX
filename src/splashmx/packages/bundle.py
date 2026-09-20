"""SMX-035 deterministic package manifest/lock and SPB1 physical boundary."""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any, Mapping, Sequence

from splashmx.canonical.core import AssetId, DefinitionId, PortId
from splashmx.canonical.serialization import DecodeLimits, ProtectedAssetRevision, decode_canonical_cbor, encode_canonical_cbor
from splashmx.security.capabilities import CapabilityId, CapabilityScope

from .model import (
    ArtifactSpec, DependencyKind, DependencySpec, LOCK_SCHEMA, LockedPackage, MANIFEST_SCHEMA,
    PackageCapabilityRequest, PackageError, PackageId, PackageManifest, PackageRevisionId,
    PortableComponent, PublicPortSpec, Requirement, ResolutionLock, SemVer, digest, fail, plain,
)

BUNDLE_SCHEMA = "splashmx.package-bundle/1"
SPB1_MAGIC = b"SPB1"
_HEADER = struct.Struct(">4sIQ")


@dataclass(frozen=True)
class BundleLimits:
    max_bundle_bytes: int = 512 * 1024 * 1024
    max_index_bytes: int = 8 * 1024 * 1024
    max_entries: int = 4096
    max_entry_bytes: int = 256 * 1024 * 1024


@dataclass(frozen=True)
class BundleEntry:
    artifact_id: str
    kind: str
    digest: str
    offset: int
    length: int


@dataclass(frozen=True)
class ParsedBundle:
    entries: tuple[BundleEntry, ...]
    payloads: Mapping[str, bytes]


def _dep_object(dep: DependencySpec) -> dict[str, Any]:
    return {"package_id": str(dep.package_id), "requirement": str(dep.requirement), "kind": dep.kind.value, "fallback": dep.fallback}


def _asset_object(asset: ProtectedAssetRevision) -> dict[str, Any]:
    return {
        "asset_id": str(asset.asset_id), "revision_digest": asset.revision_digest,
        "source_digest": asset.source_digest, "source_identity": plain(asset.source_identity),
        "source_metadata": plain(asset.source_metadata), "media_semantics": plain(asset.media_semantics),
        "provenance": plain(asset.provenance), "licence_attribution": plain(asset.licence_attribution),
        "derivation_lineage": plain(list(asset.derivation_lineage)),
    }


def _component_object(component: PortableComponent) -> dict[str, Any]:
    return {
        "definition_id": str(component.definition_id), "definition_revision": component.definition_revision,
        "root_element_id": component.root_element_id,
        "public_ports": [port.object() for port in component.public_ports],
        "public_interface_digest": component.public_interface_digest,
    }


def manifest_to_object(manifest: PackageManifest) -> dict[str, Any]:
    requests = []
    for request in manifest.capability_requests:
        requests.append({
            "definition_id": str(request.definition_id), "capability_id": str(request.capability_id),
            "scope": {"targets": sorted(request.scope.targets), "operations": sorted(request.scope.operations), "max_bytes": request.scope.max_bytes},
            "required": request.required, "reduced_mode": request.reduced_mode,
        })
    return {
        "schema": MANIFEST_SCHEMA,
        "package_id": str(manifest.package_id), "package_revision_id": str(manifest.package_revision_id),
        "human_version": str(manifest.human_version), "root_component": _component_object(manifest.root_component),
        "dependencies": [_dep_object(dep) for dep in manifest.dependencies],
        "artifacts": [{"artifact_id": row.artifact_id, "kind": row.kind, "digest": row.digest, "size_bytes": row.size_bytes, "required_features": list(row.required_features)} for row in manifest.artifacts],
        "capability_requests": requests,
        "protected_assets": [_asset_object(asset) for asset in manifest.protected_assets],
        "source_metadata": plain(manifest.source_metadata), "provenance": plain(manifest.provenance),
        "licence_attribution": plain(manifest.licence_attribution), "remix_policy": plain(manifest.remix_policy),
        "derivation_lineage": plain(list(manifest.derivation_lineage)), "required_features": list(manifest.required_features),
    }


def encode_manifest(manifest: PackageManifest) -> bytes:
    return encode_canonical_cbor(manifest_to_object(manifest))


def _exact_keys(value: Any, expected: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        fail("package.invalid_manifest", f"{where} must have exactly {sorted(expected)}")
    return value


def decode_manifest(data: bytes, *, limits: DecodeLimits | None = None) -> PackageManifest:
    try:
        obj = decode_canonical_cbor(data, limits=limits or DecodeLimits())
    except Exception as exc:
        raise PackageError("package.invalid_manifest", "manifest is not valid canonical CBOR", cause=exc) from exc
    keys = {"schema","package_id","package_revision_id","human_version","root_component","dependencies","artifacts","capability_requests","protected_assets","source_metadata","provenance","licence_attribution","remix_policy","derivation_lineage","required_features"}
    obj = _exact_keys(obj, keys, "manifest")
    if obj["schema"] != MANIFEST_SCHEMA:
        fail("package.unsupported_manifest", "unsupported package manifest schema")
    root = _exact_keys(obj["root_component"], {"definition_id","definition_revision","root_element_id","public_ports","public_interface_digest"}, "root_component")
    ports = []
    for row in root["public_ports"]:
        row = _exact_keys(row, {"port_id","kind","direction","payload_contract"}, "public_port")
        ports.append(PublicPortSpec(PortId(row["port_id"]), row["kind"], row["direction"], row["payload_contract"]))
    component = PortableComponent(DefinitionId(root["definition_id"]), root["definition_revision"], root["root_element_id"], tuple(ports), root["public_interface_digest"])
    deps = []
    for row in obj["dependencies"]:
        row = _exact_keys(row, {"package_id","requirement","kind","fallback"}, "dependency")
        deps.append(DependencySpec(PackageId(row["package_id"]), Requirement.parse(row["requirement"]), DependencyKind(row["kind"]), row["fallback"]))
    artifacts = []
    for row in obj["artifacts"]:
        row = _exact_keys(row, {"artifact_id","kind","digest","size_bytes","required_features"}, "artifact")
        artifacts.append(ArtifactSpec(row["artifact_id"], row["kind"], row["digest"], row["size_bytes"], tuple(row["required_features"])))
    requests = []
    for row in obj["capability_requests"]:
        row = _exact_keys(row, {"definition_id","capability_id","scope","required","reduced_mode"}, "capability_request")
        scope = _exact_keys(row["scope"], {"targets","operations","max_bytes"}, "capability_scope")
        if not isinstance(row["required"], bool):
            fail("package.invalid_manifest", "capability required must be boolean")
        requests.append(PackageCapabilityRequest(
            DefinitionId(row["definition_id"]), CapabilityId(row["capability_id"]),
            CapabilityScope(frozenset(scope["targets"]), frozenset(scope["operations"]), scope["max_bytes"]),
            row["required"], row["reduced_mode"],
        ))
    assets = []
    asset_keys = {"asset_id","revision_digest","source_digest","source_identity","source_metadata","media_semantics","provenance","licence_attribution","derivation_lineage"}
    for row in obj["protected_assets"]:
        row = _exact_keys(row, asset_keys, "protected_asset")
        # Constructor revalidates revision_digest against the complete indivisible fields.
        assets.append(ProtectedAssetRevision(
            AssetId(row["asset_id"]), row["revision_digest"], row["source_digest"],
            row["source_identity"], row["source_metadata"], row["media_semantics"], row["provenance"],
            row["licence_attribution"], tuple(row["derivation_lineage"]),
        ))
    return PackageManifest(
        PackageId(obj["package_id"]), PackageRevisionId(obj["package_revision_id"]), SemVer.parse(obj["human_version"]), component,
        tuple(deps), tuple(artifacts), tuple(requests), tuple(assets), obj["source_metadata"], obj["provenance"], obj["licence_attribution"],
        obj["remix_policy"], tuple(obj["derivation_lineage"]), tuple(obj["required_features"]),
    )


def lock_to_object(lock: ResolutionLock) -> dict[str, Any]:
    rows = []
    for package_id, row in sorted(lock.packages.items(), key=lambda item: str(item[0])):
        rows.append({
            "package_id": str(package_id), "package_revision_id": str(row.package_revision_id), "human_version": str(row.human_version),
            "bundle_digest": row.bundle_digest, "bundle_size": row.bundle_size,
            "dependencies": [str(value) for value in row.dependencies], "lazy": row.lazy,
        })
    return {"schema": LOCK_SCHEMA, "catalog_snapshot_id": lock.catalog_snapshot_id, "packages": rows}


def encode_lock(lock: ResolutionLock) -> bytes:
    return encode_canonical_cbor(lock_to_object(lock))


def decode_lock(data: bytes) -> ResolutionLock:
    try:
        obj = decode_canonical_cbor(data)
    except Exception as exc:
        raise PackageError("package.invalid_lock", "lock is not valid canonical CBOR", cause=exc) from exc
    obj = _exact_keys(obj, {"schema","catalog_snapshot_id","packages"}, "lock")
    if obj["schema"] != LOCK_SCHEMA:
        fail("package.invalid_lock", "unsupported resolution lock schema")
    packages = {}
    for row in obj["packages"]:
        row = _exact_keys(row, {"package_id","package_revision_id","human_version","bundle_digest","bundle_size","dependencies","lazy"}, "locked_package")
        if not isinstance(row["lazy"], bool):
            fail("package.invalid_lock", "lazy must be boolean")
        pid = PackageId(row["package_id"])
        if pid in packages:
            fail("package.invalid_lock", "duplicate PackageId in lock")
        packages[pid] = LockedPackage(pid, PackageRevisionId(row["package_revision_id"]), SemVer.parse(row["human_version"]), row["bundle_digest"], row["bundle_size"], tuple(PackageRevisionId(value) for value in row["dependencies"]), row["lazy"])
    return ResolutionLock(obj["catalog_snapshot_id"], packages)


def build_spb1(entries: Sequence[tuple[str, str, bytes]]) -> bytes:
    """Build a pathless, tightly packed, deterministic-CBOR indexed SPB1 bundle."""
    seen: set[str] = set()
    rows = []
    offset = 0
    payload_parts = []
    for artifact_id, kind, payload in entries:
        if artifact_id in seen:
            fail("package.bundle_duplicate_entry", "duplicate artifact_id")
        seen.add(artifact_id)
        data = bytes(payload)
        rows.append({"artifact_id": artifact_id, "kind": kind, "digest": digest(data), "offset": offset, "length": len(data)})
        payload_parts.append(data)
        offset += len(data)
    index = encode_canonical_cbor({"schema": BUNDLE_SCHEMA, "entries": rows})
    return _HEADER.pack(SPB1_MAGIC, len(index), offset) + index + b"".join(payload_parts)


def parse_spb1(data: bytes, *, limits: BundleLimits | None = None) -> ParsedBundle:
    limits = limits or BundleLimits()
    data = bytes(data)
    if len(data) > limits.max_bundle_bytes or len(data) < _HEADER.size:
        fail("package.bundle_size", "SPB1 bundle length is invalid or exceeds bound")
    magic, index_len, payload_len = _HEADER.unpack_from(data)
    if magic != SPB1_MAGIC or index_len > limits.max_index_bytes:
        fail("package.bundle_header", "invalid SPB1 header")
    expected = _HEADER.size + index_len + payload_len
    if expected != len(data):
        fail("package.bundle_framing", "SPB1 must contain no truncation or trailing chaff")
    index_bytes = data[_HEADER.size:_HEADER.size + index_len]
    payload = data[_HEADER.size + index_len:]
    try:
        index = decode_canonical_cbor(index_bytes, limits=DecodeLimits(max_bytes=limits.max_index_bytes, max_items=limits.max_entries * 8))
    except Exception as exc:
        raise PackageError("package.bundle_index", "invalid SPB1 deterministic-CBOR index", cause=exc) from exc
    index = _exact_keys(index, {"schema","entries"}, "bundle index")
    if index["schema"] != BUNDLE_SCHEMA or not isinstance(index["entries"], list) or len(index["entries"]) > limits.max_entries:
        fail("package.bundle_index", "unsupported or oversized SPB1 index")
    entries = []
    payloads = {}
    expected_offset = 0
    digests: set[str] = set()
    for raw in index["entries"]:
        row = _exact_keys(raw, {"artifact_id","kind","digest","offset","length"}, "bundle entry")
        if row["offset"] != expected_offset or not isinstance(row["length"], int) or isinstance(row["length"], bool) or row["length"] < 0 or row["length"] > limits.max_entry_bytes:
            fail("package.bundle_layout", "SPB1 payload must be tightly packed in index order")
        if row["artifact_id"] in payloads or row["digest"] in digests:
            fail("package.bundle_duplicate_entry", "SPB1 duplicates artifact or digest")
        end = row["offset"] + row["length"]
        if end > len(payload):
            fail("package.bundle_layout", "SPB1 entry exceeds payload")
        item = payload[row["offset"]:end]
        if digest(item) != row["digest"]:
            fail("package.bundle_digest", f"digest mismatch for {row['artifact_id']}")
        entry = BundleEntry(row["artifact_id"], row["kind"], row["digest"], row["offset"], row["length"])
        entries.append(entry); payloads[row["artifact_id"]] = item; digests.add(row["digest"]); expected_offset = end
    if expected_offset != len(payload):
        fail("package.bundle_layout", "SPB1 contains unindexed payload bytes")
    return ParsedBundle(tuple(entries), payloads)


def package_bundle_for_manifest(manifest: PackageManifest, artifacts: Mapping[str, bytes]) -> bytes:
    manifest_bytes = encode_manifest(manifest)
    rows: list[tuple[str, str, bytes]] = [("manifest", "manifest", manifest_bytes)]
    by_id = {spec.artifact_id: spec for spec in manifest.artifacts}
    if set(artifacts) != set(by_id):
        fail("package.artifact_set_mismatch", "bundle artifact set differs from manifest")
    for artifact_id in sorted(artifacts):
        spec = by_id[artifact_id]; payload = bytes(artifacts[artifact_id])
        if len(payload) != spec.size_bytes or digest(payload) != spec.digest:
            fail("package.artifact_mismatch", f"artifact {artifact_id} differs from manifest")
        rows.append((artifact_id, spec.kind, payload))
    return build_spb1(rows)


__all__ = [
    "BUNDLE_SCHEMA", "BundleEntry", "BundleLimits", "ParsedBundle", "SPB1_MAGIC", "build_spb1",
    "decode_lock", "decode_manifest", "encode_lock", "encode_manifest", "lock_to_object", "manifest_to_object",
    "package_bundle_for_manifest", "parse_spb1",
]
