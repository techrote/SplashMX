from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Callable


class StreamingError(Exception):
    pass


class PinnedArtifactError(StreamingError):
    pass


class ReplacementError(StreamingError):
    pass


class IdentityError(StreamingError):
    pass


@dataclass(frozen=True)
class DependencyEdge:
    target_id: str
    mode: str = "required"  # required | optional | lazy
    fallback: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"required", "optional", "lazy"}:
            raise ValueError(f"unsupported dependency mode: {self.mode}")


@dataclass(frozen=True)
class ArtifactDescriptor:
    logical_id: str
    kind: str
    revision: str
    digest: str
    size: int
    dependencies: tuple[DependencyEdge, ...] = ()
    required_features: tuple[str, ...] = ()


@dataclass
class ArtifactRecord:
    descriptor: ArtifactDescriptor
    payload: bytes
    semantic: dict[str, Any] = field(default_factory=dict)
    availability: str = "ok"  # ok | denied | incompatible | invalid | offline
    tampered_payload: bytes | None = None


class ArtifactRepository:
    def __init__(self) -> None:
        self.records: dict[str, ArtifactRecord] = {}
        self.fetch_count: dict[str, int] = {}

    def add(
        self,
        logical_id: str,
        *,
        kind: str,
        revision: str,
        payload: bytes,
        dependencies: tuple[DependencyEdge, ...] = (),
        semantic: dict[str, Any] | None = None,
        availability: str = "ok",
        required_features: tuple[str, ...] = (),
    ) -> ArtifactDescriptor:
        digest = hashlib.sha256(payload).hexdigest()
        descriptor = ArtifactDescriptor(
            logical_id=logical_id,
            kind=kind,
            revision=revision,
            digest=digest,
            size=len(payload),
            dependencies=dependencies,
            required_features=required_features,
        )
        self.records[logical_id] = ArtifactRecord(
            descriptor=descriptor,
            payload=bytes(payload),
            semantic=deepcopy(semantic or {}),
            availability=availability,
        )
        self.fetch_count.setdefault(logical_id, 0)
        return descriptor

    def tamper(self, logical_id: str, tampered_payload: bytes) -> None:
        self.records[logical_id].tampered_payload = bytes(tampered_payload)

    def descriptor(self, logical_id: str) -> ArtifactDescriptor | None:
        record = self.records.get(logical_id)
        return None if record is None else record.descriptor

    def semantic(self, logical_id: str) -> dict[str, Any]:
        return deepcopy(self.records[logical_id].semantic)

    def fetch(self, logical_id: str) -> tuple[str, bytes | None]:
        record = self.records.get(logical_id)
        if record is None:
            return "missing", None
        self.fetch_count[logical_id] = self.fetch_count.get(logical_id, 0) + 1
        if record.availability == "denied":
            return "denied", None
        if record.availability == "incompatible":
            return "incompatible", None
        if record.availability == "invalid":
            return "invalid_or_malicious", None
        if record.availability == "offline":
            return "offline_or_unreachable", None
        payload = record.tampered_payload if record.tampered_payload is not None else record.payload
        return "ok", bytes(payload)


@dataclass
class AcquisitionResult:
    status: str
    published: tuple[str, ...] = ()
    optional_failures: dict[str, str] = field(default_factory=dict)
    verified_this_attempt: tuple[str, ...] = ()
    failure_target: str | None = None


class ArtifactManager:
    def __init__(
        self,
        repository: ArtifactRepository,
        *,
        supported_features: set[str] | None = None,
        max_artifacts: int = 64,
        max_total_bytes: int = 16_000_000,
    ) -> None:
        self.repository = repository
        self.supported_features = set(supported_features or {"core.v1"})
        self.max_artifacts = max_artifacts
        self.max_total_bytes = max_total_bytes
        self.verified_cache: dict[str, bytes] = {}
        self.resident_artifacts: set[str] = set()
        self.pin_counts: dict[str, int] = {}
        self.attempt_counter = 0

    def _descriptor_status(self, logical_id: str) -> tuple[str, ArtifactDescriptor | None]:
        descriptor = self.repository.descriptor(logical_id)
        if descriptor is None:
            return "missing", None
        if not set(descriptor.required_features).issubset(self.supported_features):
            return "incompatible", descriptor
        record = self.repository.records[logical_id]
        if record.availability == "denied":
            return "denied", descriptor
        if record.availability == "incompatible":
            return "incompatible", descriptor
        if record.availability == "invalid":
            return "invalid_or_malicious", descriptor
        if record.availability == "offline":
            return "offline_or_unreachable", descriptor
        return "ok", descriptor

    def acquire(
        self,
        roots: list[str] | tuple[str, ...],
        *,
        request_optional: bool = True,
        request_lazy: bool = False,
        cancel_after_verifications: int | None = None,
    ) -> AcquisitionResult:
        self.attempt_counter += 1

        closure: list[str] = []
        processed_requiredness: dict[str, bool] = {}
        optional_failures: dict[str, str] = {}
        required_stack: list[tuple[str, bool]] = [(root, True) for root in roots]

        while required_stack:
            logical_id, required = required_stack.pop()
            previous = processed_requiredness.get(logical_id)
            if previous is True:
                continue
            if previous is False and not required:
                continue
            processed_requiredness[logical_id] = required or bool(previous)

            status, descriptor = self._descriptor_status(logical_id)
            if status != "ok" or descriptor is None:
                if required:
                    return AcquisitionResult(
                        status=status,
                        optional_failures=optional_failures,
                        failure_target=logical_id,
                    )
                optional_failures[logical_id] = status
                continue

            if logical_id not in closure:
                closure.append(logical_id)
            if len(closure) > self.max_artifacts:
                return AcquisitionResult(
                    status="resource_exhausted",
                    optional_failures=optional_failures,
                    failure_target=logical_id,
                )

            for edge in reversed(descriptor.dependencies):
                if edge.mode == "required":
                    required_stack.append((edge.target_id, True))
                elif edge.mode == "optional" and request_optional:
                    required_stack.append((edge.target_id, False))
                elif edge.mode == "lazy" and request_lazy:
                    required_stack.append((edge.target_id, False))

        total_bytes = sum(self.repository.records[item].descriptor.size for item in closure)
        if total_bytes > self.max_total_bytes:
            return AcquisitionResult(
                status="resource_exhausted",
                optional_failures=optional_failures,
            )

        verified: list[str] = []
        for logical_id in sorted(closure):
            descriptor = self.repository.records[logical_id].descriptor
            if descriptor.digest in self.verified_cache:
                payload = self.verified_cache[descriptor.digest]
            else:
                status, payload = self.repository.fetch(logical_id)
                if status != "ok" or payload is None:
                    return AcquisitionResult(
                        status=status,
                        optional_failures=optional_failures,
                        verified_this_attempt=tuple(verified),
                        failure_target=logical_id,
                    )
                if len(payload) != descriptor.size:
                    return AcquisitionResult(
                        status="invalid_or_malicious",
                        optional_failures=optional_failures,
                        verified_this_attempt=tuple(verified),
                        failure_target=logical_id,
                    )
                digest = hashlib.sha256(payload).hexdigest()
                if digest != descriptor.digest:
                    return AcquisitionResult(
                        status="invalid_or_malicious",
                        optional_failures=optional_failures,
                        verified_this_attempt=tuple(verified),
                        failure_target=logical_id,
                    )
                self.verified_cache[descriptor.digest] = bytes(payload)
                verified.append(logical_id)

            if (
                cancel_after_verifications is not None
                and len(verified) >= cancel_after_verifications
            ):
                return AcquisitionResult(
                    status="cancelled",
                    optional_failures=optional_failures,
                    verified_this_attempt=tuple(verified),
                )

        # Atomic visibility point.
        self.resident_artifacts.update(closure)
        return AcquisitionResult(
            status="published",
            published=tuple(sorted(closure)),
            optional_failures=optional_failures,
            verified_this_attempt=tuple(verified),
        )

    def pin(self, logical_id: str) -> None:
        if logical_id not in self.resident_artifacts:
            raise StreamingError(f"cannot pin non-resident artifact: {logical_id}")
        self.pin_counts[logical_id] = self.pin_counts.get(logical_id, 0) + 1

    def unpin(self, logical_id: str) -> None:
        count = self.pin_counts.get(logical_id, 0)
        if count <= 1:
            self.pin_counts.pop(logical_id, None)
        else:
            self.pin_counts[logical_id] = count - 1

    def evict(self, logical_id: str) -> bool:
        if self.pin_counts.get(logical_id, 0) > 0:
            raise PinnedArtifactError(logical_id)
        existed = logical_id in self.resident_artifacts
        self.resident_artifacts.discard(logical_id)
        return existed

    def is_resident(self, logical_id: str) -> bool:
        return logical_id in self.resident_artifacts


@dataclass
class BehaviorAttachment:
    attachment_id: str
    implementation_id: str
    revision: int
    private_schema: int
    private_state: dict[str, Any] = field(default_factory=dict)
    continuations: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class DetachedStateCapsule:
    attachment_id: str
    behavior_lineage: str
    revision: int
    private_schema: int
    private_state: dict[str, Any]


@dataclass
class ThingRecord:
    thing_id: str
    state: dict[str, Any] = field(default_factory=dict)
    refs: dict[str, str] = field(default_factory=dict)
    region: str | None = None
    physical_chunk: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    public_ports: dict[str, tuple[str, str]] = field(default_factory=dict)
    connections: dict[str, tuple[str, str]] = field(default_factory=dict)
    behaviors: dict[str, BehaviorAttachment] = field(default_factory=dict)
    detached_capsules: dict[str, DetachedStateCapsule] = field(default_factory=dict)
    activity: str = "active"
    context: dict[str, Any] = field(default_factory=dict)


MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


class StreamingWorld:
    def __init__(self, artifacts: ArtifactManager) -> None:
        self.artifacts = artifacts
        self.resident: dict[str, ThingRecord] = {}
        self.storage: dict[str, ThingRecord] = {}
        self.tombstones: set[str] = set()
        self.catalog: set[str] = set()
        self.creation_events: list[str] = []

    def create(self, thing: ThingRecord, *, first_creation: bool = True) -> None:
        if thing.thing_id in self.catalog or thing.thing_id in self.tombstones:
            raise IdentityError(thing.thing_id)
        copied = deepcopy(thing)
        self.catalog.add(copied.thing_id)
        self.resident[copied.thing_id] = copied
        if first_creation:
            self.creation_events.append(copied.thing_id)
        for attachment in copied.behaviors.values():
            if attachment.active:
                result = self.artifacts.acquire([attachment.implementation_id])
                if result.status != "published":
                    del self.resident[copied.thing_id]
                    self.catalog.remove(copied.thing_id)
                    if first_creation and self.creation_events and self.creation_events[-1] == copied.thing_id:
                        self.creation_events.pop()
                    raise StreamingError(
                        f"required behavior unavailable: {attachment.implementation_id} ({result.status})"
                    )
                self.artifacts.pin(attachment.implementation_id)

    def status(self, thing_id: str) -> str:
        if thing_id in self.tombstones:
            return "tombstoned"
        if thing_id in self.resident:
            return "loaded"
        if thing_id in self.storage or thing_id in self.catalog:
            return "known_unloaded"
        return "unknown"

    def unload(self, thing_ids: list[str] | tuple[str, ...]) -> None:
        staged: dict[str, ThingRecord] = {}
        for thing_id in thing_ids:
            thing = self.resident.get(thing_id)
            if thing is None:
                continue
            staged[thing_id] = deepcopy(thing)

        # Atomic semantic cut for this research model.
        for thing_id, snapshot in staged.items():
            thing = self.resident.pop(thing_id)
            for attachment in thing.behaviors.values():
                if attachment.active:
                    self.artifacts.unpin(attachment.implementation_id)
            snapshot.context = {}
            self.storage[thing_id] = snapshot

    def _hard_artifacts_for(self, thing: ThingRecord) -> list[str]:
        result: list[str] = []
        for attachment in thing.behaviors.values():
            if attachment.active and thing.activity == "active":
                result.append(attachment.implementation_id)
        for value in thing.provenance.values():
            if isinstance(value, str) and value.startswith(("def:", "component:")):
                # Source provenance is not normally runtime-hard. Explicit marker below only.
                pass
        for dependency in thing.state.get("_runtime_required_artifacts", []):
            result.append(dependency)
        return sorted(set(result))

    def load(self, thing_ids: list[str] | tuple[str, ...]) -> AcquisitionResult:
        staged_things: dict[str, ThingRecord] = {}
        hard_artifacts: list[str] = []

        for thing_id in thing_ids:
            if thing_id in self.resident:
                continue
            snapshot = self.storage.get(thing_id)
            if snapshot is None:
                return AcquisitionResult(status="missing", failure_target=thing_id)
            staged = deepcopy(snapshot)
            staged.context = {}
            staged_things[thing_id] = staged
            hard_artifacts.extend(self._hard_artifacts_for(staged))

        result = self.artifacts.acquire(sorted(set(hard_artifacts))) if hard_artifacts else AcquisitionResult(status="published")
        if result.status != "published":
            return result

        for thing in staged_things.values():
            for attachment in thing.behaviors.values():
                if attachment.active and thing.activity == "active":
                    self.artifacts.pin(attachment.implementation_id)

        # Atomic publication point for requested Thing set.
        for thing_id, staged in staged_things.items():
            self.resident[thing_id] = staged
            self.storage.pop(thing_id, None)

        return result

    def set_dormant(self, thing_id: str, dormant: bool) -> AcquisitionResult:
        thing = self.resident[thing_id]
        if dormant and thing.activity != "dormant":
            for attachment in thing.behaviors.values():
                if attachment.active:
                    self.artifacts.unpin(attachment.implementation_id)
            thing.activity = "dormant"
            return AcquisitionResult(status="published")

        if not dormant and thing.activity == "dormant":
            implementations = [
                attachment.implementation_id
                for attachment in thing.behaviors.values()
                if attachment.active
            ]
            result = self.artifacts.acquire(sorted(set(implementations)))
            if result.status != "published":
                return result
            for implementation in implementations:
                self.artifacts.pin(implementation)
            thing.activity = "active"
            return result

        return AcquisitionResult(status="published")

    def instantiate_component(
        self,
        *,
        definition_id: str,
        new_thing_id: str,
    ) -> AcquisitionResult:
        result = self.artifacts.acquire([definition_id])
        if result.status != "published":
            return result
        semantic = self.artifacts.repository.semantic(definition_id)
        behavior_id = semantic.get("behavior_id")
        thing = ThingRecord(
            thing_id=new_thing_id,
            state=deepcopy(semantic.get("default_state", {})),
            provenance={
                "definition_id": definition_id,
                "definition_revision": self.artifacts.repository.records[definition_id].descriptor.revision,
            },
        )
        if behavior_id is not None:
            behavior_semantic = self.artifacts.repository.semantic(behavior_id)
            thing.behaviors["attach:main"] = BehaviorAttachment(
                attachment_id="attach:main",
                implementation_id=behavior_id,
                revision=int(behavior_semantic["revision"]),
                private_schema=int(behavior_semantic["private_schema"]),
                private_state=deepcopy(behavior_semantic.get("default_private_state", {})),
            )
        self.create(thing, first_creation=True)
        return result

    def hot_replace_behavior(
        self,
        *,
        thing_id: str,
        attachment_id: str,
        new_implementation_id: str,
        migration: MigrationFn | None = None,
        continuation_map: dict[str, str] | None = None,
    ) -> AcquisitionResult:
        thing = self.resident[thing_id]
        old = thing.behaviors[attachment_id]
        old_snapshot = deepcopy(old)

        result = self.artifacts.acquire([new_implementation_id])
        if result.status != "published":
            return result

        new_semantic = self.artifacts.repository.semantic(new_implementation_id)
        new_revision = int(new_semantic["revision"])
        new_schema = int(new_semantic["private_schema"])
        new_state = deepcopy(old.private_state)

        try:
            if new_schema != old.private_schema:
                if migration is None:
                    raise ReplacementError("private-state migration required")
                new_state = migration(deepcopy(old.private_state))

            mapped_continuations: list[str] = []
            for continuation in old.continuations:
                if continuation_map is None or continuation not in continuation_map:
                    raise ReplacementError(f"unmapped continuation: {continuation}")
                mapped_continuations.append(continuation_map[continuation])

            candidate = BehaviorAttachment(
                attachment_id=old.attachment_id,
                implementation_id=new_implementation_id,
                revision=new_revision,
                private_schema=new_schema,
                private_state=new_state,
                continuations=mapped_continuations,
                active=old.active,
            )
        except Exception as exc:
            thing.behaviors[attachment_id] = old_snapshot
            raise ReplacementError(str(exc)) from exc

        if old.active and thing.activity == "active":
            self.artifacts.pin(new_implementation_id)

        thing.behaviors[attachment_id] = candidate

        if old.active and thing.activity == "active":
            self.artifacts.unpin(old.implementation_id)

        return result

    def detach_behavior(self, thing_id: str, attachment_id: str, *, state_policy: str) -> None:
        if state_policy not in {"discard_state", "retain_capsule"}:
            raise ValueError(state_policy)
        thing = self.resident[thing_id]
        attachment = thing.behaviors.pop(attachment_id)
        if attachment.active and thing.activity == "active":
            self.artifacts.unpin(attachment.implementation_id)

        if state_policy == "retain_capsule":
            thing.detached_capsules[attachment_id] = DetachedStateCapsule(
                attachment_id=attachment.attachment_id,
                behavior_lineage=attachment.implementation_id,
                revision=attachment.revision,
                private_schema=attachment.private_schema,
                private_state=deepcopy(attachment.private_state),
            )
        else:
            thing.detached_capsules.pop(attachment_id, None)

    def destroy(self, thing_id: str) -> None:
        if thing_id in self.resident:
            thing = self.resident.pop(thing_id)
            for attachment in thing.behaviors.values():
                if attachment.active and thing.activity == "active":
                    self.artifacts.unpin(attachment.implementation_id)
        self.storage.pop(thing_id, None)
        self.catalog.discard(thing_id)
        self.tombstones.add(thing_id)

    def export_migration_capsule(self, thing_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
        things = []
        dependencies: set[str] = set()
        for thing_id in thing_ids:
            source = self.resident.get(thing_id) or self.storage.get(thing_id)
            if source is None:
                raise StreamingError(f"unknown migration Thing: {thing_id}")
            copied = deepcopy(source)
            copied.context = {}
            things.append(_thing_to_dict(copied))
            dependencies.update(self._hard_artifacts_for(copied))
        descriptors = [
            _descriptor_to_dict(self.artifacts.repository.records[item].descriptor)
            for item in sorted(dependencies)
        ]
        return {
            "schema": "smx008-migration-capsule-research-v1",
            "things": things,
            "resolved_artifacts": descriptors,
        }

    def import_migration_capsule(self, capsule: dict[str, Any]) -> AcquisitionResult:
        if capsule.get("schema") != "smx008-migration-capsule-research-v1":
            return AcquisitionResult(status="incompatible")

        required = [item["logical_id"] for item in capsule.get("resolved_artifacts", [])]
        for item in capsule.get("resolved_artifacts", []):
            current = self.artifacts.repository.descriptor(item["logical_id"])
            if current is None:
                return AcquisitionResult(status="missing", failure_target=item["logical_id"])
            if current.digest != item["digest"] or current.size != item["size"]:
                return AcquisitionResult(status="incompatible", failure_target=item["logical_id"])

        result = self.artifacts.acquire(required)
        if result.status != "published":
            return result

        staged = [_thing_from_dict(item) for item in capsule.get("things", [])]
        for thing in staged:
            if thing.thing_id in self.catalog or thing.thing_id in self.tombstones:
                return AcquisitionResult(status="incompatible", failure_target=thing.thing_id)

        for thing in staged:
            thing.context = {}
            self.catalog.add(thing.thing_id)
            self.resident[thing.thing_id] = thing
            for attachment in thing.behaviors.values():
                if attachment.active and thing.activity == "active":
                    self.artifacts.pin(attachment.implementation_id)

        return result


def _descriptor_to_dict(descriptor: ArtifactDescriptor) -> dict[str, Any]:
    return {
        "logical_id": descriptor.logical_id,
        "kind": descriptor.kind,
        "revision": descriptor.revision,
        "digest": descriptor.digest,
        "size": descriptor.size,
    }


def _thing_to_dict(thing: ThingRecord) -> dict[str, Any]:
    return {
        "thing_id": thing.thing_id,
        "state": deepcopy(thing.state),
        "refs": deepcopy(thing.refs),
        "region": thing.region,
        "physical_chunk": thing.physical_chunk,
        "provenance": deepcopy(thing.provenance),
        "public_ports": {
            key: list(value)
            for key, value in thing.public_ports.items()
        },
        "connections": {
            key: list(value)
            for key, value in thing.connections.items()
        },
        "behaviors": [
            {
                "attachment_id": value.attachment_id,
                "implementation_id": value.implementation_id,
                "revision": value.revision,
                "private_schema": value.private_schema,
                "private_state": deepcopy(value.private_state),
                "continuations": list(value.continuations),
                "active": value.active,
            }
            for value in thing.behaviors.values()
        ],
        "detached_capsules": [
            {
                "attachment_id": value.attachment_id,
                "behavior_lineage": value.behavior_lineage,
                "revision": value.revision,
                "private_schema": value.private_schema,
                "private_state": deepcopy(value.private_state),
            }
            for value in thing.detached_capsules.values()
        ],
        "activity": thing.activity,
    }


def _thing_from_dict(data: dict[str, Any]) -> ThingRecord:
    thing = ThingRecord(
        thing_id=data["thing_id"],
        state=deepcopy(data.get("state", {})),
        refs=deepcopy(data.get("refs", {})),
        region=data.get("region"),
        physical_chunk=data.get("physical_chunk"),
        provenance=deepcopy(data.get("provenance", {})),
        public_ports={
            key: tuple(value)
            for key, value in data.get("public_ports", {}).items()
        },
        connections={
            key: tuple(value)
            for key, value in data.get("connections", {}).items()
        },
        activity=data.get("activity", "active"),
        context={},
    )
    for raw in data.get("behaviors", []):
        thing.behaviors[raw["attachment_id"]] = BehaviorAttachment(
            attachment_id=raw["attachment_id"],
            implementation_id=raw["implementation_id"],
            revision=int(raw["revision"]),
            private_schema=int(raw["private_schema"]),
            private_state=deepcopy(raw.get("private_state", {})),
            continuations=list(raw.get("continuations", [])),
            active=bool(raw.get("active", True)),
        )
    for raw in data.get("detached_capsules", []):
        thing.detached_capsules[raw["attachment_id"]] = DetachedStateCapsule(
            attachment_id=raw["attachment_id"],
            behavior_lineage=raw["behavior_lineage"],
            revision=int(raw["revision"]),
            private_schema=int(raw["private_schema"]),
            private_state=deepcopy(raw.get("private_state", {})),
        )
    return thing


def canonical_capsule_roundtrip(capsule: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(capsule, sort_keys=True))
