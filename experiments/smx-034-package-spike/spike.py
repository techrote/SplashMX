"""SMX-034 package-substrate selection spike.

This is falsification/reference evidence, not the production SMX-035 package module.
It exercises the selected semantic shape: a deliberately small version-requirement
language, one-revision-per-PackageId bounded resolution, and an SPB1 framing model
whose index reuses the production deterministic-CBOR profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
import struct
from typing import Any, Iterable, Mapping, Sequence

from splashmx.canonical.serialization import DecodeLimits, decode_canonical_cbor, encode_canonical_cbor


class PackageSpikeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise PackageSpikeError(code, message)


_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> "SemVer":
        match = _SEMVER_RE.fullmatch(text)
        if not match:
            _fail("package.invalid_version", f"SMX v1 package version must be X.Y.Z: {text!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Requirement:
    operator: str
    base: SemVer

    @classmethod
    def parse(cls, text: str) -> "Requirement":
        if text.startswith("="):
            return cls("exact", SemVer.parse(text[1:]))
        if text.startswith("^"):
            return cls("caret", SemVer.parse(text[1:]))
        _fail("package.invalid_requirement", "v1 requirements are exact (=X.Y.Z) or caret (^X.Y.Z)")

    def matches(self, version: SemVer) -> bool:
        if self.operator == "exact":
            return version == self.base
        lower = self.base
        if lower.major > 0:
            upper = SemVer(lower.major + 1, 0, 0)
        elif lower.minor > 0:
            upper = SemVer(0, lower.minor + 1, 0)
        else:
            upper = SemVer(0, 0, lower.patch + 1)
        return lower <= version < upper


@dataclass(frozen=True)
class Dependency:
    package_id: str
    requirement: Requirement
    kind: str = "required"  # required | optional | lazy
    fallback: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"required", "optional", "lazy"}:
            _fail("package.invalid_dependency_kind", self.kind)
        if self.kind == "optional" and not self.fallback:
            _fail("package.optional_missing_fallback", self.package_id)
        if self.kind != "optional" and self.fallback is not None:
            _fail("package.invalid_fallback", self.package_id)


@dataclass(frozen=True)
class Revision:
    package_id: str
    version: SemVer
    revision_id: str
    manifest_digest: str
    byte_size: int
    dependencies: tuple[Dependency, ...] = ()
    revoked: bool = False

    def __post_init__(self) -> None:
        if self.byte_size < 0:
            _fail("package.invalid_size", self.package_id)
        if not _DIGEST_RE.fullmatch(self.manifest_digest):
            _fail("package.invalid_digest", self.package_id)


@dataclass(frozen=True)
class ResolverLimits:
    max_packages: int = 128
    max_depth: int = 32
    max_decisions: int = 4096
    max_total_bytes: int = 512 * 1024 * 1024


@dataclass
class _State:
    selected: dict[str, Revision] = field(default_factory=dict)
    constraints: dict[str, list[Requirement]] = field(default_factory=dict)
    required: set[str] = field(default_factory=set)
    lazy: set[str] = field(default_factory=set)
    optional_fallbacks: dict[str, str] = field(default_factory=dict)
    depth: dict[str, int] = field(default_factory=dict)
    decisions: int = 0

    def clone(self) -> "_State":
        return _State(
            dict(self.selected),
            {key: list(value) for key, value in self.constraints.items()},
            set(self.required), set(self.lazy), dict(self.optional_fallbacks),
            dict(self.depth), self.decisions,
        )


@dataclass(frozen=True)
class Resolution:
    selected: Mapping[str, Revision]
    lazy: frozenset[str]
    optional_fallbacks: Mapping[str, str]


def resolve(catalog: Mapping[str, Sequence[Revision]], roots: Sequence[Dependency], *, limits: ResolverLimits = ResolverLimits()) -> Resolution:
    """Bounded deterministic reference search for the selected resolver semantics.

    SMX-035 may implement PubGrub rather than this DFS. This spike exists to pin
    observable behavior and hostile bounds, not to turn DFS into production policy.
    """
    state = _State()

    def add_need(target: _State, dep: Dependency, depth: int) -> None:
        if depth > limits.max_depth:
            _fail("package.depth_limit", dep.package_id)
        if dep.kind == "optional":
            target.optional_fallbacks.setdefault(dep.package_id, dep.fallback or "")
        elif dep.kind == "required":
            target.required.add(dep.package_id)
        else:
            target.lazy.add(dep.package_id)
        target.constraints.setdefault(dep.package_id, []).append(dep.requirement)
        target.depth[dep.package_id] = max(target.depth.get(dep.package_id, 0), depth)

    for root in roots:
        add_need(state, root, 0)

    def candidates(target: _State, package_id: str) -> list[Revision]:
        rows = [row for row in catalog.get(package_id, ()) if not row.revoked]
        constraints = target.constraints.get(package_id, ())
        rows = [row for row in rows if all(req.matches(row.version) for req in constraints)]
        return sorted(rows, key=lambda row: (row.version, row.revision_id), reverse=True)

    def check_bounds(target: _State) -> None:
        if len(target.selected) > limits.max_packages:
            _fail("package.package_limit", "resolved package count exceeds bound")
        if sum(row.byte_size for row in target.selected.values()) > limits.max_total_bytes:
            _fail("package.byte_limit", "resolved byte total exceeds bound")
        if target.decisions > limits.max_decisions:
            _fail("package.solver_work_limit", "solver decision bound exceeded")

    def search(target: _State) -> _State | None:
        check_bounds(target)
        # Selected revisions must continue satisfying every newly introduced constraint.
        for package_id, row in target.selected.items():
            if not all(req.matches(row.version) for req in target.constraints.get(package_id, ())):
                return None

        unresolved = sorted(set(target.constraints) - set(target.selected))
        if not unresolved:
            return target

        # Fail first on the narrowest domain; lexical PackageId is only a deterministic
        # resolver tie-break, never runtime/object identity or execution order.
        ranked = sorted((len(candidates(target, package_id)), package_id) for package_id in unresolved)
        count, package_id = ranked[0]
        rows = candidates(target, package_id)
        is_optional_only = package_id not in target.required and package_id not in target.lazy
        if count == 0:
            if is_optional_only:
                next_state = target.clone()
                next_state.constraints.pop(package_id, None)
                next_state.depth.pop(package_id, None)
                return search(next_state)
            return None

        for row in rows:
            next_state = target.clone()
            next_state.decisions += 1
            if next_state.decisions > limits.max_decisions:
                _fail("package.solver_work_limit", "solver decision bound exceeded")
            next_state.selected[package_id] = row
            parent_depth = next_state.depth.get(package_id, 0)
            try:
                for dep in row.dependencies:
                    add_need(next_state, dep, parent_depth + 1)
                check_bounds(next_state)
            except PackageSpikeError:
                raise
            solved = search(next_state)
            if solved is not None:
                return solved
        return None

    solved = search(state)
    if solved is None:
        _fail("package.version_conflict", "no coherent one-version-per-PackageId resolution")
    return Resolution(dict(sorted(solved.selected.items())), frozenset(solved.lazy), dict(sorted(solved.optional_fallbacks.items())))


# SPB1 is deliberately not a filesystem archive. There are no names/paths, links,
# extraction semantics, install scripts or compression in v1. The deterministic CBOR
# index describes tightly packed immutable blobs by type, offset, size and SHA-256.
SPB1_MAGIC = b"SPB1"
_HEADER = struct.Struct(">4sIQ")  # magic, index bytes, payload bytes


@dataclass(frozen=True)
class BundleLimits:
    max_container_bytes: int = 512 * 1024 * 1024
    max_index_bytes: int = 4 * 1024 * 1024
    max_entries: int = 4096
    max_entry_bytes: int = 256 * 1024 * 1024


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def build_spb1(entries: Sequence[tuple[str, bytes]]) -> bytes:
    offset = 0
    index_entries: list[dict[str, Any]] = []
    payload_parts: list[bytes] = []
    for kind, blob in entries:
        if not isinstance(blob, bytes):
            _fail("package.invalid_blob", kind)
        index_entries.append({"kind": kind, "offset": offset, "length": len(blob), "digest": _digest(blob)})
        payload_parts.append(blob)
        offset += len(blob)
    index = encode_canonical_cbor({"schema": "splashmx.package-bundle/1", "entries": index_entries})
    payload = b"".join(payload_parts)
    return _HEADER.pack(SPB1_MAGIC, len(index), len(payload)) + index + payload


def parse_spb1(data: bytes, *, limits: BundleLimits = BundleLimits()) -> tuple[Mapping[str, Any], tuple[bytes, ...]]:
    if not isinstance(data, bytes):
        _fail("package.invalid_container", "bundle must be bytes")
    if len(data) > limits.max_container_bytes:
        _fail("package.container_limit", "bundle exceeds maximum byte length")
    if len(data) < _HEADER.size:
        _fail("package.truncated_container", "missing SPB1 header")
    magic, index_len, payload_len = _HEADER.unpack_from(data)
    if magic != SPB1_MAGIC:
        _fail("package.invalid_magic", "not an SPB1 bundle")
    if index_len > limits.max_index_bytes:
        _fail("package.index_limit", "bundle index exceeds bound")
    expected = _HEADER.size + index_len + payload_len
    if expected != len(data):
        _fail("package.length_mismatch", "declared bundle lengths do not match input")
    index_bytes = data[_HEADER.size:_HEADER.size + index_len]
    try:
        index = decode_canonical_cbor(index_bytes, limits=DecodeLimits(max_bytes=limits.max_index_bytes, max_depth=16, max_items=limits.max_entries * 8 + 16, max_string_bytes=4096))
    except Exception as exc:
        _fail("package.invalid_index", str(exc))
    if not isinstance(index, dict) or set(index) != {"schema", "entries"} or index.get("schema") != "splashmx.package-bundle/1":
        _fail("package.invalid_index", "unexpected SPB1 index schema")
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) > limits.max_entries:
        _fail("package.entry_limit", "invalid or oversized SPB1 entry table")
    payload = data[_HEADER.size + index_len:]
    cursor = 0
    blobs: list[bytes] = []
    seen_digests: set[str] = set()
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"kind", "offset", "length", "digest"}:
            _fail("package.invalid_entry", "SPB1 entries have a closed schema")
        kind, offset, length, digest = row["kind"], row["offset"], row["length"], row["digest"]
        if not isinstance(kind, str) or not kind or not isinstance(offset, int) or not isinstance(length, int):
            _fail("package.invalid_entry", "entry type/offset/length invalid")
        if offset != cursor or length < 0 or length > limits.max_entry_bytes:
            _fail("package.invalid_layout", "entries must be bounded and tightly packed")
        end = offset + length
        if end > len(payload):
            _fail("package.invalid_layout", "entry extends beyond payload")
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest) or digest in seen_digests:
            _fail("package.invalid_digest", "entry digest invalid or duplicated")
        blob = payload[offset:end]
        if _digest(blob) != digest:
            _fail("package.digest_mismatch", kind)
        seen_digests.add(digest)
        blobs.append(blob)
        cursor = end
    if cursor != len(payload):
        _fail("package.invalid_layout", "unindexed payload bytes are forbidden")
    return index, tuple(blobs)


_FORBIDDEN_AUTHORITY_KEYS = {
    "capability_grant", "capability_token", "host_handle", "session_handle",
    "install_script", "native_extension", "javascript", "gdscript", "raw_socket",
}
_PROTECTED_ASSET_KEYS = {
    "asset_id", "revision_digest", "source_digest", "source_identity",
    "source_metadata", "media_semantics", "provenance", "licence_attribution",
    "derivation_lineage",
}


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate spike-level authority and protected-media invariants."""
    required = {
        "schema", "package_id", "package_revision_id", "human_version",
        "root_definition_id", "dependencies", "capability_requests",
        "protected_assets", "provenance", "licence",
    }
    if not isinstance(manifest, Mapping) or not required.issubset(manifest):
        _fail("package.invalid_manifest", "missing required package manifest fields")
    if manifest["schema"] != "splashmx.package-manifest/1":
        _fail("package.invalid_manifest", "unsupported manifest schema")
    SemVer.parse(str(manifest["human_version"]))

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in _FORBIDDEN_AUTHORITY_KEYS:
                    _fail("package.serialized_authority", f"forbidden authority/execution field {key!r}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(manifest)

    assets = manifest["protected_assets"]
    if not isinstance(assets, list):
        _fail("package.invalid_asset", "protected_assets must be a list")
    for asset in assets:
        if not isinstance(asset, Mapping) or set(asset) != _PROTECTED_ASSET_KEYS:
            _fail("package.incomplete_protected_asset", "protected Asset revision must be complete and indivisible")
        if not _DIGEST_RE.fullmatch(str(asset["revision_digest"])) or not _DIGEST_RE.fullmatch(str(asset["source_digest"])):
            _fail("package.invalid_asset", "protected Asset digests are invalid")
