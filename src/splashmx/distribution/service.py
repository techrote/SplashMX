"""SMX-050 production distribution, retention and recovery boundary.

Distribution is deliberately downstream of immutable SplashMX publication.  URLs,
CDN placement, aliases, installer state and service health are operational state;
none become canonical identity or weaken the SMX-036 exact-closure contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping, Sequence

from splashmx.canonical.core import AssetId
from splashmx.canonical.serialization import (
    DecodeLimits,
    ProtectedAssetRevision,
    SerializedProjectRevision,
    decode_canonical_cbor,
    deserialize_project,
    encode_canonical_cbor,
)
from splashmx.publishing.generic import (
    CreationRevisionId,
    GenericPlayer,
    HostedReleaseId,
    HostedReleaseStore,
    PublishedCreation,
    decode_creation_manifest,
)
from splashmx.runtime.lifecycle import (
    WorldSaveSnapshot,
    deserialize_world_save,
    serialize_world_save,
)

DISTRIBUTION_RELEASE_SCHEMA = "splashmx.hosted-distribution/1"
OFFLINE_BUNDLE_SCHEMA = "splashmx.offline-distribution/1"
PROTECTED_DISCLOSURE_SCHEMA = "splashmx.protected-asset-disclosure/1"
RECOVERY_ARCHIVE_SCHEMA = "splashmx.recovery-archive/1"
MAX_DISTRIBUTION_BYTES = 256 * 1024 * 1024
MAX_DISTRIBUTION_ITEMS = 32768
MAX_OPERATIONAL_EVENTS = 512
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~:/-]{0,255}")
_TARGET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class DistributionError(ValueError):
    """Stable typed distribution/recovery failure."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _fail(code: str, message: str) -> None:
    raise DistributionError(code, message)


def _digest(payload: bytes) -> str:
    return "sha256:" + sha256(bytes(payload)).hexdigest()


def _expect(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _fail("distribution.invalid_format", f"{where} must contain exactly {sorted(keys)}")
    return value


def _bounded_decode(raw: bytes, *, where: str) -> Any:
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_DISTRIBUTION_BYTES:
        _fail("distribution.resource_limit", f"{where} is invalid or exceeds the byte limit")
    try:
        return decode_canonical_cbor(
            bytes(raw),
            limits=DecodeLimits(
                max_bytes=MAX_DISTRIBUTION_BYTES,
                max_depth=64,
                max_items=MAX_DISTRIBUTION_ITEMS * 16,
                max_string_bytes=16 * 1024 * 1024,
            ),
        )
    except DistributionError:
        raise
    except Exception as exc:
        raise DistributionError("distribution.invalid_format", f"{where} is not bounded canonical CBOR", cause=exc) from exc


def _valid_digest(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail("distribution.invalid_digest", f"{where} must be sha256:<64 lowercase hex>")
    return value


@dataclass(frozen=True)
class RuntimeArtifact:
    """One exact generic-runtime artifact; profile identity is not engine identity."""

    profile: str
    digest: str
    payload: bytes

    @classmethod
    def create(cls, profile: str, payload: bytes) -> "RuntimeArtifact":
        data = bytes(payload)
        return cls(profile, _digest(data), data)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, str) or not self.profile or len(self.profile) > 128:
            _fail("distribution.invalid_runtime", "runtime profile must be a bounded non-empty string")
        _valid_digest(self.digest, where="runtime digest")
        if not isinstance(self.payload, (bytes, bytearray)):
            _fail("distribution.invalid_runtime", "runtime payload must be bytes")
        data = bytes(self.payload)
        if _digest(data) != self.digest:
            _fail("distribution.runtime_integrity", "runtime digest does not match runtime bytes")
        object.__setattr__(self, "payload", data)


class RuntimeRegistry:
    """Content-addressed runtime retention with explicit eligibility/revocation."""

    def __init__(self) -> None:
        self._artifacts: dict[str, RuntimeArtifact] = {}
        self._eligible: dict[str, bool] = {}
        self._revoked: set[str] = set()

    def register(self, artifact: RuntimeArtifact, *, eligible: bool = True) -> None:
        if not isinstance(artifact, RuntimeArtifact):
            _fail("distribution.invalid_runtime", "runtime registration requires RuntimeArtifact")
        prior = self._artifacts.get(artifact.digest)
        if prior is not None and prior != artifact:
            _fail("distribution.immutable_rebind", "runtime digest cannot be rebound to different profile/bytes")
        self._artifacts[artifact.digest] = artifact
        self._eligible.setdefault(artifact.digest, bool(eligible))

    def set_eligible(self, digest: str, eligible: bool) -> None:
        _valid_digest(digest, where="runtime digest")
        if digest not in self._artifacts:
            _fail("distribution.runtime_unavailable", "unknown retained runtime")
        self._eligible[digest] = bool(eligible)

    def revoke(self, digest: str) -> None:
        _valid_digest(digest, where="runtime digest")
        if digest not in self._artifacts:
            _fail("distribution.runtime_unavailable", "unknown retained runtime")
        self._revoked.add(digest)

    def resolve(self, profile: str, digest: str) -> RuntimeArtifact:
        _valid_digest(digest, where="runtime digest")
        artifact = self._artifacts.get(digest)
        if artifact is None or artifact.profile != profile:
            _fail("distribution.runtime_unavailable", "exact retained runtime profile/digest is unavailable")
        if digest in self._revoked:
            _fail("distribution.runtime_revoked", "retained runtime is revoked by current security policy")
        if not self._eligible.get(digest, False):
            _fail("distribution.runtime_ineligible", "retained runtime is not eligible for distribution")
        return artifact

    @property
    def retained_bytes(self) -> int:
        return sum(len(row.payload) for row in self._artifacts.values())


@dataclass(frozen=True)
class HostedDistributionRecord:
    release_id: HostedReleaseId
    creation_revision_id: CreationRevisionId
    creation_manifest_digest: str
    runtime_profile: str
    runtime_digest: str
    disclosure_digest: str

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": DISTRIBUTION_RELEASE_SCHEMA,
            "creation_revision_id": str(self.creation_revision_id),
            "creation_manifest_digest": self.creation_manifest_digest,
            "runtime_profile": self.runtime_profile,
            "runtime_digest": self.runtime_digest,
            "disclosure_digest": self.disclosure_digest,
        }


def _record_for(
    creation_revision_id: CreationRevisionId,
    creation_manifest_digest: str,
    runtime_profile: str,
    runtime_digest: str,
    disclosure_digest: str,
) -> HostedDistributionRecord:
    payload = {
        "schema": DISTRIBUTION_RELEASE_SCHEMA,
        "creation_revision_id": str(creation_revision_id),
        "creation_manifest_digest": _valid_digest(creation_manifest_digest, where="creation manifest digest"),
        "runtime_profile": runtime_profile,
        "runtime_digest": _valid_digest(runtime_digest, where="runtime digest"),
        "disclosure_digest": _valid_digest(disclosure_digest, where="disclosure digest"),
    }
    release_id = HostedReleaseId(_digest(encode_canonical_cbor(payload)))
    return HostedDistributionRecord(
        release_id,
        creation_revision_id,
        creation_manifest_digest,
        runtime_profile,
        runtime_digest,
        disclosure_digest,
    )


def _asset_disclosure(asset: ProtectedAssetRevision) -> dict[str, Any]:
    return {
        "asset_id": str(asset.asset_id),
        "revision_digest": asset.revision_digest,
        "source_digest": asset.source_digest,
        "source_identity": dict(asset.source_identity),
        "source_metadata": dict(asset.source_metadata),
        "media_semantics": dict(asset.media_semantics),
        "provenance": dict(asset.provenance),
        "licence_attribution": dict(asset.licence_attribution),
        "derivation_lineage": [dict(row) for row in asset.derivation_lineage],
    }


def build_protected_disclosure(assets: Iterable[ProtectedAssetRevision]) -> bytes:
    rows = sorted((_asset_disclosure(row) for row in assets), key=lambda row: row["asset_id"])
    if len(rows) > MAX_DISTRIBUTION_ITEMS:
        _fail("distribution.resource_limit", "protected disclosure exceeds asset-count limit")
    if len({row["asset_id"] for row in rows}) != len(rows):
        _fail("distribution.protected_asset_conflict", "duplicate protected AssetId disclosure")
    return encode_canonical_cbor({"schema": PROTECTED_DISCLOSURE_SCHEMA, "assets": rows})


def validate_protected_disclosure(raw: bytes) -> tuple[ProtectedAssetRevision, ...]:
    value = _expect(_bounded_decode(raw, where="protected disclosure"), {"schema", "assets"}, "protected disclosure")
    if value["schema"] != PROTECTED_DISCLOSURE_SCHEMA or not isinstance(value["assets"], list):
        _fail("distribution.invalid_disclosure", "unsupported or malformed protected disclosure")
    if len(value["assets"]) > MAX_DISTRIBUTION_ITEMS:
        _fail("distribution.resource_limit", "protected disclosure exceeds asset-count limit")
    result: list[ProtectedAssetRevision] = []
    for index, item in enumerate(value["assets"]):
        item = _expect(
            item,
            {
                "asset_id", "revision_digest", "source_digest", "source_identity",
                "source_metadata", "media_semantics", "provenance", "licence_attribution",
                "derivation_lineage",
            },
            f"protected disclosure asset[{index}]",
        )
        if not isinstance(item["derivation_lineage"], list):
            _fail("distribution.invalid_disclosure", "derivation lineage must be an array")
        try:
            result.append(
                ProtectedAssetRevision(
                    AssetId(item["asset_id"]),
                    item["revision_digest"],
                    item["source_digest"],
                    item["source_identity"],
                    item["source_metadata"],
                    item["media_semantics"],
                    item["provenance"],
                    item["licence_attribution"],
                    tuple(item["derivation_lineage"]),
                )
            )
        except Exception as exc:
            raise DistributionError(
                "distribution.invalid_disclosure",
                "protected disclosure does not describe a complete valid immutable Asset revision",
                cause=exc,
            ) from exc
    if len({row.asset_id for row in result}) != len(result):
        _fail("distribution.protected_asset_conflict", "duplicate protected AssetId disclosure")
    return tuple(result)


@dataclass(frozen=True)
class OperationalEvent:
    sequence: int
    service: str
    state: str
    detail: str


class OperationalHealth:
    """Bounded operational telemetry, never semantic/capability state."""

    def __init__(self, max_events: int = MAX_OPERATIONAL_EVENTS) -> None:
        if max_events < 1 or max_events > MAX_OPERATIONAL_EVENTS:
            _fail("distribution.invalid_operational_limit", "operational event limit is invalid")
        self.max_events = max_events
        self._sequence = 0
        self._events: list[OperationalEvent] = []
        self._states: dict[str, str] = {}

    def record(self, service: str, state: str, detail: str = "") -> OperationalEvent:
        if not isinstance(service, str) or not service or len(service) > 128:
            _fail("distribution.invalid_operational_event", "service name is invalid")
        if state not in {"available", "degraded", "unavailable", "recovering"}:
            _fail("distribution.invalid_operational_event", "operational state is invalid")
        if not isinstance(detail, str) or len(detail.encode("utf-8")) > 4096:
            _fail("distribution.invalid_operational_event", "operational detail is invalid or unbounded")
        self._sequence += 1
        event = OperationalEvent(self._sequence, service, state, detail)
        self._events.append(event)
        if len(self._events) > self.max_events:
            del self._events[: len(self._events) - self.max_events]
        self._states[service] = state
        return event

    def state(self, service: str) -> str | None:
        return self._states.get(service)

    @property
    def events(self) -> tuple[OperationalEvent, ...]:
        return tuple(self._events)


@dataclass(frozen=True)
class DistributionMetrics:
    immutable_object_count: int
    immutable_object_bytes: int
    retained_runtime_bytes: int
    release_count: int
    alias_count: int
    operational_event_count: int


@dataclass(frozen=True)
class InstalledOfflineContent:
    """A self-contained exact install with no online lookup dependency."""

    bundle_bytes: bytes
    record: HostedDistributionRecord
    published: PublishedCreation
    runtime: RuntimeArtifact
    disclosure_bytes: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_bytes", bytes(self.bundle_bytes))
        object.__setattr__(self, "disclosure_bytes", bytes(self.disclosure_bytes))


@dataclass(frozen=True)
class NativePackagePlan:
    """Installer input only; it introduces no new creation/runtime identity."""

    target_profile: str
    creation_revision_id: CreationRevisionId
    release_id: HostedReleaseId
    runtime_profile: str
    runtime_digest: str
    offline_bundle_digest: str


def plan_native_package(installed: InstalledOfflineContent, target_profile: str) -> NativePackagePlan:
    if not isinstance(target_profile, str) or _TARGET_RE.fullmatch(target_profile) is None:
        _fail("distribution.invalid_target", "native target profile is invalid")
    return NativePackagePlan(
        target_profile,
        installed.record.creation_revision_id,
        installed.record.release_id,
        installed.runtime.profile,
        installed.runtime.digest,
        _digest(installed.bundle_bytes),
    )


class DistributionService:
    """Hosted immutable objects, mutable aliases, placement and outage observability."""

    def __init__(self, verifier: GenericPlayer | None = None) -> None:
        self.verifier = verifier or GenericPlayer()
        self.runtime_registry = RuntimeRegistry()
        self.hosted = HostedReleaseStore()
        self.health = OperationalHealth()
        self._service_available = True
        self._objects: dict[str, bytes] = {}
        self._locations: dict[str, set[str]] = {}
        self._records: dict[HostedReleaseId, HostedDistributionRecord] = {}
        self._aliases: dict[str, HostedReleaseId] = {}
        self._alias_epoch: dict[str, int] = {}
        self.health.record("hosting", "available", "distribution service initialized")

    def _require_online(self) -> None:
        if not self._service_available:
            _fail("distribution.service_unavailable", "hosted distribution service is unavailable")

    def set_service_available(self, available: bool, detail: str = "") -> None:
        self._service_available = bool(available)
        self.health.record("hosting", "available" if available else "unavailable", detail)

    def record_dependency_state(self, service: str, state: str, detail: str = "") -> OperationalEvent:
        return self.health.record(service, state, detail)

    def _put_object(self, payload: bytes) -> str:
        data = bytes(payload)
        digest = _digest(data)
        prior = self._objects.get(digest)
        if prior is not None and prior != data:
            _fail("distribution.digest_collision", "immutable object digest was rebound")
        self._objects[digest] = data
        return digest

    def publish_release(self, published: PublishedCreation, runtime: RuntimeArtifact) -> HostedDistributionRecord:
        self._require_online()
        prepared = self.verifier.prepare(published)
        if prepared.manifest.player_profile != runtime.profile:
            _fail("distribution.runtime_profile_mismatch", "creation and retained runtime profile differ")
        self.runtime_registry.register(runtime)
        self.runtime_registry.resolve(runtime.profile, runtime.digest)

        disclosure = build_protected_disclosure(prepared.protected_assets.values())
        manifest_digest = self._put_object(published.manifest_bytes)
        for expected_digest, blob in published.blobs.items():
            if _digest(blob) != expected_digest:
                _fail("distribution.creation_integrity", "creation blob map contains a digest mismatch")
            self._put_object(blob)
        runtime_digest = self._put_object(runtime.payload)
        disclosure_digest = self._put_object(disclosure)
        if runtime_digest != runtime.digest:
            _fail("distribution.runtime_integrity", "retained runtime object digest changed")

        record = _record_for(
            prepared.manifest.creation_revision_id,
            manifest_digest,
            runtime.profile,
            runtime.digest,
            disclosure_digest,
        )
        prior = self._records.get(record.release_id)
        if prior is not None and prior != record:
            _fail("distribution.immutable_rebind", "HostedReleaseId cannot be rebound")
        self.hosted.publish_release(record.release_id, published)
        self._records[record.release_id] = record
        return record

    def retarget_alias(self, alias: str, release_id: HostedReleaseId) -> int:
        self._require_online()
        if not isinstance(alias, str) or _ALIAS_RE.fullmatch(alias) is None:
            _fail("distribution.invalid_alias", "friendly alias is invalid or unbounded")
        if release_id not in self._records:
            _fail("distribution.unknown_release", "friendly alias must target an existing immutable release")
        self.hosted.retarget_alias(alias, release_id)
        self._aliases[alias] = release_id
        self._alias_epoch[alias] = self._alias_epoch.get(alias, 0) + 1
        return self._alias_epoch[alias]

    def resolve_alias(self, alias: str) -> HostedDistributionRecord:
        self._require_online()
        release_id = self._aliases.get(alias)
        if release_id is None:
            _fail("distribution.unknown_alias", "unknown friendly alias")
        return self._records[release_id]

    def get_release(self, release_id: HostedReleaseId) -> HostedDistributionRecord:
        self._require_online()
        record = self._records.get(release_id)
        if record is None:
            _fail("distribution.unknown_release", "unknown immutable hosted release")
        return record

    def get_object(self, digest: str) -> bytes:
        self._require_online()
        _valid_digest(digest, where="object digest")
        payload = self._objects.get(digest)
        if payload is None:
            _fail("distribution.object_unavailable", "immutable distribution object is unavailable")
        if _digest(payload) != digest:
            _fail("distribution.object_integrity", "immutable object failed digest verification")
        return payload

    def record_cdn_location(self, digest: str, location: str) -> None:
        _valid_digest(digest, where="object digest")
        if digest not in self._objects:
            _fail("distribution.object_unavailable", "cannot place an unknown immutable object")
        if not isinstance(location, str) or not location.startswith("https://") or len(location) > 2048:
            _fail("distribution.invalid_location", "CDN location must be a bounded HTTPS locator")
        self._locations.setdefault(digest, set()).add(location)

    def locations(self, digest: str) -> tuple[str, ...]:
        _valid_digest(digest, where="object digest")
        return tuple(sorted(self._locations.get(digest, set())))

    def immutable_cache_headers(self, digest: str) -> Mapping[str, str]:
        _valid_digest(digest, where="object digest")
        return {
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{digest}"',
        }

    def alias_cache_headers(self, alias: str) -> Mapping[str, str]:
        if alias not in self._aliases:
            _fail("distribution.unknown_alias", "unknown friendly alias")
        return {
            "Cache-Control": "no-cache",
            "ETag": f'"alias-{self._alias_epoch[alias]}"',
        }

    def export_offline_bundle(self, release_id: HostedReleaseId) -> bytes:
        self._require_online()
        record = self.get_release(release_id)
        published = self.hosted.get(record.creation_revision_id)
        runtime = self.runtime_registry.resolve(record.runtime_profile, record.runtime_digest)
        disclosure = self.get_object(record.disclosure_digest)
        payload = {
            "schema": OFFLINE_BUNDLE_SCHEMA,
            "release_id": str(record.release_id),
            "creation_revision_id": str(record.creation_revision_id),
            "creation_manifest_digest": record.creation_manifest_digest,
            "creation_manifest": published.manifest_bytes,
            "creation_blobs": [
                {"digest": digest, "payload": blob}
                for digest, blob in sorted(published.blobs.items())
            ],
            "runtime": {
                "profile": runtime.profile,
                "digest": runtime.digest,
                "payload": runtime.payload,
            },
            "disclosure_digest": record.disclosure_digest,
            "protected_disclosure": disclosure,
        }
        encoded = encode_canonical_cbor(payload)
        if len(encoded) > MAX_DISTRIBUTION_BYTES:
            _fail("distribution.resource_limit", "offline bundle exceeds byte limit")
        return encoded

    def metrics(self) -> DistributionMetrics:
        return DistributionMetrics(
            len(self._objects),
            sum(len(value) for value in self._objects.values()),
            self.runtime_registry.retained_bytes,
            len(self._records),
            len(self._aliases),
            len(self.health.events),
        )


def import_offline_bundle(raw: bytes, verifier: GenericPlayer | None = None) -> InstalledOfflineContent:
    verifier = verifier or GenericPlayer()
    value = _expect(
        _bounded_decode(raw, where="offline bundle"),
        {
            "schema", "release_id", "creation_revision_id", "creation_manifest_digest",
            "creation_manifest", "creation_blobs", "runtime", "disclosure_digest",
            "protected_disclosure",
        },
        "offline bundle",
    )
    if value["schema"] != OFFLINE_BUNDLE_SCHEMA:
        _fail("distribution.unsupported_schema", "unsupported offline bundle schema")
    if not isinstance(value["creation_blobs"], list) or len(value["creation_blobs"]) > MAX_DISTRIBUTION_ITEMS:
        _fail("distribution.resource_limit", "offline creation blob list is invalid or unbounded")

    blobs: dict[str, bytes] = {}
    for index, row in enumerate(value["creation_blobs"]):
        row = _expect(row, {"digest", "payload"}, f"offline creation blob[{index}]")
        digest = _valid_digest(row["digest"], where="creation blob digest")
        if digest in blobs:
            _fail("distribution.invalid_format", "offline bundle contains duplicate creation blob digest")
        if not isinstance(row["payload"], (bytes, bytearray)) or _digest(row["payload"]) != digest:
            _fail("distribution.creation_integrity", "offline creation blob failed exact digest verification")
        blobs[digest] = bytes(row["payload"])

    manifest = value["creation_manifest"]
    if not isinstance(manifest, (bytes, bytearray)):
        _fail("distribution.invalid_format", "offline creation manifest must be bytes")
    manifest = bytes(manifest)
    if _digest(manifest) != _valid_digest(value["creation_manifest_digest"], where="creation manifest digest"):
        _fail("distribution.creation_integrity", "offline creation manifest failed digest verification")

    published = PublishedCreation(manifest, blobs)
    prepared = verifier.prepare(published)
    if str(prepared.manifest.creation_revision_id) != value["creation_revision_id"]:
        _fail("distribution.creation_integrity", "offline creation revision identity differs from verified creation")

    runtime_row = _expect(value["runtime"], {"profile", "digest", "payload"}, "offline runtime")
    runtime = RuntimeArtifact(runtime_row["profile"], runtime_row["digest"], runtime_row["payload"])
    if runtime.profile != prepared.manifest.player_profile:
        _fail("distribution.runtime_profile_mismatch", "offline runtime profile differs from creation")

    disclosure = value["protected_disclosure"]
    if not isinstance(disclosure, (bytes, bytearray)):
        _fail("distribution.invalid_disclosure", "offline protected disclosure must be bytes")
    disclosure = bytes(disclosure)
    disclosure_digest = _valid_digest(value["disclosure_digest"], where="disclosure digest")
    if _digest(disclosure) != disclosure_digest:
        _fail("distribution.invalid_disclosure", "offline protected disclosure digest mismatch")
    validate_protected_disclosure(disclosure)
    expected_disclosure = build_protected_disclosure(prepared.protected_assets.values())
    if disclosure != expected_disclosure:
        _fail("distribution.protected_asset_conflict", "offline disclosure differs from exact creation protected assets")

    record = _record_for(
        prepared.manifest.creation_revision_id,
        _digest(manifest),
        runtime.profile,
        runtime.digest,
        disclosure_digest,
    )
    if str(record.release_id) != value["release_id"]:
        _fail("distribution.release_integrity", "offline HostedReleaseId does not match exact creation/runtime/disclosure")
    return InstalledOfflineContent(bytes(raw), record, published, runtime, disclosure)


@dataclass(frozen=True)
class RecoveryWorldSave:
    raw: bytes
    snapshot: WorldSaveSnapshot


@dataclass(frozen=True)
class RecoveryArchiveContents:
    projects: tuple[SerializedProjectRevision, ...]
    offline_installs: tuple[InstalledOfflineContent, ...]
    world_saves: tuple[RecoveryWorldSave, ...]


def build_recovery_archive(
    *,
    projects: Sequence[SerializedProjectRevision] = (),
    offline_bundles: Sequence[bytes] = (),
    world_saves: Sequence[WorldSaveSnapshot] = (),
    verifier: GenericPlayer | None = None,
) -> bytes:
    verifier = verifier or GenericPlayer()
    project_rows: list[tuple[str, str, dict[str, Any]]] = []
    for serialized in projects:
        restored = deserialize_project(serialized)
        project_rows.append(
            (
                str(restored.document.project_id),
                str(restored.document.project_revision_id),
                {
                    "root_manifest": bytes(serialized.root_manifest),
                    "shards": [
                        {"key": key, "payload": bytes(payload)}
                        for key, payload in sorted(serialized.shards.items())
                    ],
                },
            )
        )

    offline_rows: list[tuple[str, bytes]] = []
    for raw in offline_bundles:
        installed = import_offline_bundle(raw, verifier)
        offline_rows.append((str(installed.record.creation_revision_id), bytes(raw)))

    world_rows: list[tuple[str, str, bytes]] = []
    for snapshot in world_saves:
        raw = serialize_world_save(snapshot)
        world_rows.append((str(snapshot.world_save_id), str(snapshot.world_revision_id), raw))

    if len(project_rows) + len(offline_rows) + len(world_rows) > MAX_DISTRIBUTION_ITEMS:
        _fail("distribution.resource_limit", "recovery archive exceeds item-count limit")
    if len({(a, b) for a, b, _ in project_rows}) != len(project_rows):
        _fail("distribution.duplicate_recovery_item", "duplicate project revision in recovery archive")
    if len({a for a, _ in offline_rows}) != len(offline_rows):
        _fail("distribution.duplicate_recovery_item", "duplicate offline creation in recovery archive")
    if len({(a, b) for a, b, _ in world_rows}) != len(world_rows):
        _fail("distribution.duplicate_recovery_item", "duplicate WorldSave revision in recovery archive")

    payload = {
        "schema": RECOVERY_ARCHIVE_SCHEMA,
        "projects": [row for _, _, row in sorted(project_rows)],
        "offline_bundles": [raw for _, raw in sorted(offline_rows)],
        "world_saves": [raw for _, _, raw in sorted(world_rows)],
    }
    encoded = encode_canonical_cbor(payload)
    if len(encoded) > MAX_DISTRIBUTION_BYTES:
        _fail("distribution.resource_limit", "recovery archive exceeds byte limit")
    return encoded


def import_recovery_archive(raw: bytes, verifier: GenericPlayer | None = None) -> RecoveryArchiveContents:
    verifier = verifier or GenericPlayer()
    value = _expect(
        _bounded_decode(raw, where="recovery archive"),
        {"schema", "projects", "offline_bundles", "world_saves"},
        "recovery archive",
    )
    if value["schema"] != RECOVERY_ARCHIVE_SCHEMA:
        _fail("distribution.unsupported_schema", "unsupported recovery archive schema")
    if not all(isinstance(value[name], list) for name in ("projects", "offline_bundles", "world_saves")):
        _fail("distribution.invalid_format", "recovery archive collections must be arrays")
    if sum(len(value[name]) for name in ("projects", "offline_bundles", "world_saves")) > MAX_DISTRIBUTION_ITEMS:
        _fail("distribution.resource_limit", "recovery archive exceeds item-count limit")

    projects: list[SerializedProjectRevision] = []
    project_keys: set[tuple[str, str]] = set()
    for index, row in enumerate(value["projects"]):
        row = _expect(row, {"root_manifest", "shards"}, f"recovery project[{index}]")
        if not isinstance(row["root_manifest"], (bytes, bytearray)) or not isinstance(row["shards"], list):
            _fail("distribution.invalid_format", "recovery project bytes/shards are malformed")
        shards: dict[str, bytes] = {}
        for shard in row["shards"]:
            shard = _expect(shard, {"key", "payload"}, "recovery project shard")
            if not isinstance(shard["key"], str) or shard["key"] in shards or not isinstance(shard["payload"], (bytes, bytearray)):
                _fail("distribution.invalid_format", "recovery project shard is invalid or duplicated")
            shards[shard["key"]] = bytes(shard["payload"])
        serialized = SerializedProjectRevision(bytes(row["root_manifest"]), shards)
        restored = deserialize_project(serialized)
        key = (str(restored.document.project_id), str(restored.document.project_revision_id))
        if key in project_keys:
            _fail("distribution.duplicate_recovery_item", "duplicate project revision in recovery archive")
        project_keys.add(key)
        projects.append(serialized)

    installs: list[InstalledOfflineContent] = []
    creation_ids: set[CreationRevisionId] = set()
    for item in value["offline_bundles"]:
        if not isinstance(item, (bytes, bytearray)):
            _fail("distribution.invalid_format", "recovery offline bundle must be bytes")
        installed = import_offline_bundle(bytes(item), verifier)
        if installed.record.creation_revision_id in creation_ids:
            _fail("distribution.duplicate_recovery_item", "duplicate offline creation in recovery archive")
        creation_ids.add(installed.record.creation_revision_id)
        installs.append(installed)

    worlds: list[RecoveryWorldSave] = []
    world_keys: set[tuple[str, str]] = set()
    for item in value["world_saves"]:
        if not isinstance(item, (bytes, bytearray)):
            _fail("distribution.invalid_format", "recovery WorldSave must be bytes")
        world_raw = bytes(item)
        snapshot = deserialize_world_save(world_raw)
        key = (str(snapshot.world_save_id), str(snapshot.world_revision_id))
        if key in world_keys:
            _fail("distribution.duplicate_recovery_item", "duplicate WorldSave revision in recovery archive")
        world_keys.add(key)
        worlds.append(RecoveryWorldSave(world_raw, snapshot))

    return RecoveryArchiveContents(tuple(projects), tuple(installs), tuple(worlds))


__all__ = [
    "DISTRIBUTION_RELEASE_SCHEMA", "DistributionError", "DistributionMetrics",
    "DistributionService", "HostedDistributionRecord", "InstalledOfflineContent",
    "NativePackagePlan", "OFFLINE_BUNDLE_SCHEMA", "OperationalEvent", "OperationalHealth",
    "PROTECTED_DISCLOSURE_SCHEMA", "RECOVERY_ARCHIVE_SCHEMA", "RecoveryArchiveContents",
    "RecoveryWorldSave", "RuntimeArtifact", "RuntimeRegistry", "build_protected_disclosure",
    "build_recovery_archive", "import_offline_bundle", "import_recovery_archive",
    "plan_native_package", "validate_protected_disclosure",
]
