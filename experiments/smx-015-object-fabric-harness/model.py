"""Disposable SMX-015 integrated Object Fabric falsification harness.

This model intentionally re-expresses only the accepted semantic contracts needed
to run P0-P4 together.  It is NOT Architecture v1.0, a production runtime, a
canonical byte format, a Godot binding, or a security boundary.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, asdict
import hashlib
import json
from typing import Any, Mapping


class FabricError(Exception):
    pass


class IdentityError(FabricError):
    pass


class CompatibilityError(FabricError):
    pass


class SwapError(FabricError):
    pass


class AcquisitionError(FabricError):
    pass


class DefinitionConflict(FabricError):
    pass


PROTECTED_ASSET_FIELDS = {
    "asset_id",
    "revision_id",
    "digest",
    "source_identity",
    "source_metadata",
    "media_semantics",
    "provenance",
    "licence",
    "derivation",
}


@dataclass(frozen=True)
class AssetRevision:
    asset_id: str
    revision_id: str
    digest: str
    source_identity: str
    source_metadata: dict[str, Any]
    media_semantics: dict[str, Any]
    provenance: dict[str, Any]
    licence: str
    derivation: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AssetRevision":
        missing = PROTECTED_ASSET_FIELDS - set(value)
        extra = set(value) - PROTECTED_ASSET_FIELDS
        if missing or extra:
            raise CompatibilityError(
                f"asset revision must be an indivisible protected bundle; "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )
        if not all(value.get(k) for k in ("asset_id", "revision_id", "digest", "source_identity", "licence")):
            raise CompatibilityError("protected asset identity fields must be non-empty")
        return cls(
            asset_id=str(value["asset_id"]),
            revision_id=str(value["revision_id"]),
            digest=str(value["digest"]),
            source_identity=str(value["source_identity"]),
            source_metadata=deepcopy(dict(value["source_metadata"])),
            media_semantics=deepcopy(dict(value["media_semantics"])),
            provenance=deepcopy(dict(value["provenance"])),
            licence=str(value["licence"]),
            derivation=tuple(value["derivation"]),
        )


@dataclass(frozen=True)
class ArtifactDescriptor:
    artifact_id: str
    revision: str
    digest: str
    size: int


class ArtifactStore:
    """Exact immutable research artifact acquisition with an atomic publication edge."""

    def __init__(self) -> None:
        self.descriptors: dict[str, ArtifactDescriptor] = {}
        self.payloads: dict[str, bytes] = {}
        self.tampered: dict[str, bytes] = {}
        self.availability: dict[str, str] = {}
        self.resident: set[str] = set()

    def add(self, artifact_id: str, payload: bytes, *, revision: str = "1") -> ArtifactDescriptor:
        payload = bytes(payload)
        desc = ArtifactDescriptor(
            artifact_id=artifact_id,
            revision=revision,
            digest=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        self.descriptors[artifact_id] = desc
        self.payloads[artifact_id] = payload
        self.availability[artifact_id] = "ok"
        return desc

    def set_availability(self, artifact_id: str, status: str) -> None:
        self.availability[artifact_id] = status

    def tamper(self, artifact_id: str, payload: bytes) -> None:
        self.tampered[artifact_id] = bytes(payload)

    def acquire(self, artifact_ids: list[str] | tuple[str, ...] | set[str]) -> tuple[str, ...]:
        requested = sorted(set(artifact_ids))
        staged: list[str] = []
        for artifact_id in requested:
            desc = self.descriptors.get(artifact_id)
            if desc is None:
                raise AcquisitionError(f"missing:{artifact_id}")
            status = self.availability.get(artifact_id, "ok")
            if status != "ok":
                raise AcquisitionError(f"{status}:{artifact_id}")
            payload = self.tampered.get(artifact_id, self.payloads[artifact_id])
            if len(payload) != desc.size or hashlib.sha256(payload).hexdigest() != desc.digest:
                raise AcquisitionError(f"invalid_or_malicious:{artifact_id}")
            staged.append(artifact_id)
        self.resident.update(staged)
        return tuple(staged)


@dataclass(frozen=True)
class BehaviorSpec:
    behavior_id: str
    revision: int
    private_schema: tuple[str, ...]
    handlers: tuple[str, ...]
    artifact_id: str


@dataclass
class Attachment:
    attachment_id: str
    behavior_id: str
    revision: int
    private_schema: tuple[str, ...]
    private_state: dict[str, Any]
    artifact_id: str


@dataclass
class PendingWork:
    work_id: str
    thing_id: str
    attachment_id: str
    handler: str
    payload: dict[str, Any]
    due_tick: int
    order: int
    durable: bool = True


@dataclass
class Thing:
    thing_id: str
    state: dict[str, Any] = field(default_factory=dict)
    facets: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)
    refs: dict[str, str] = field(default_factory=dict)
    attachments: dict[str, Attachment] = field(default_factory=dict)
    assets: dict[str, AssetRevision] = field(default_factory=dict)
    runtime_required_artifacts: set[str] = field(default_factory=set)


@dataclass
class DefinitionElement:
    element_id: str
    state: dict[str, Any] = field(default_factory=dict)
    facets: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)
    parent_element: str | None = None


@dataclass
class Definition:
    definition_id: str
    revision: int
    root_element_id: str
    elements: dict[str, DefinitionElement]
    exposures: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class Instance:
    instance_id: str
    definition_id: str
    base_revision: int
    root_element_id: str
    root_thing_id: str
    thing_by_element: dict[str, str]
    state_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_overrides: dict[str, str | None] = field(default_factory=dict)
    connected_public_ports: set[str] = field(default_factory=set)


class FabricWorld:
    """Integrated semantic world used only by the SMX-015 destructive campaign."""

    SNAPSHOT_SCHEMA = "smx015-object-fabric-snapshot-v1"

    def __init__(
        self,
        *,
        authored_revision: str = "creation:1",
        artifact_store: ArtifactStore | None = None,
        behavior_catalog: dict[tuple[str, int], BehaviorSpec] | None = None,
    ) -> None:
        self.authored_revision = authored_revision
        self.artifacts = artifact_store or ArtifactStore()
        self.behavior_catalog = dict(behavior_catalog or {})
        self.things: dict[str, Thing] = {}
        self.resident: set[str] = set()
        self.tombstones: set[str] = set()
        self.parent_by_child: dict[str, str] = {}
        self.controller_by_thing: dict[str, str] = {}
        self.authority_by_thing: dict[str, str] = {}
        self.persistence_by_thing: dict[str, str] = {}
        self.replication_by_thing: dict[str, str] = {}
        self.observer_by_thing: dict[str, str] = {}
        self.definitions: dict[str, Definition] = {}
        self.instances: dict[str, Instance] = {}
        self.context: dict[str, dict[str, Any]] = {}
        self.pending_work: list[PendingWork] = []
        self.tick = 0
        self._next_order = 0

    def register_behavior(self, spec: BehaviorSpec) -> None:
        self.behavior_catalog[(spec.behavior_id, spec.revision)] = spec

    def add_thing(self, thing: Thing, *, resident: bool = True) -> None:
        if thing.thing_id in self.things or thing.thing_id in self.tombstones:
            raise IdentityError(f"duplicate or reused ThingId: {thing.thing_id}")
        candidate = deepcopy(thing)
        if resident:
            self._acquire_for(candidate)
        self.things[candidate.thing_id] = candidate
        if resident:
            self.resident.add(candidate.thing_id)

    def set_context(self, thing_id: str, **values: Any) -> None:
        if thing_id not in self.things:
            raise IdentityError(thing_id)
        self.context.setdefault(thing_id, {}).update(deepcopy(values))

    def replace_asset(self, thing_id: str, candidate: Mapping[str, Any]) -> AssetRevision:
        thing = self.things[thing_id]
        revision = AssetRevision.from_mapping(candidate)
        existing = thing.assets.get(revision.asset_id)
        if existing is not None and existing.asset_id != revision.asset_id:
            raise CompatibilityError("AssetId cannot be rewritten")
        thing.assets[revision.asset_id] = revision
        return revision

    def reparent(self, child_id: str, parent_id: str | None) -> None:
        if child_id not in self.things:
            raise IdentityError(child_id)
        if parent_id is not None and parent_id not in self.things:
            raise IdentityError(parent_id)
        if parent_id is None:
            self.parent_by_child.pop(child_id, None)
        else:
            cur = parent_id
            seen = {child_id}
            while cur is not None:
                if cur in seen:
                    raise FabricError("containment cycle")
                seen.add(cur)
                cur = self.parent_by_child.get(cur)
            self.parent_by_child[child_id] = parent_id

    def resolve_ref(self, target_id: str) -> str:
        if target_id in self.tombstones:
            return "tombstoned"
        if target_id not in self.things:
            return "unknown"
        return "loaded" if target_id in self.resident else "known_unloaded"

    def destroy(self, thing_id: str) -> None:
        if thing_id not in self.things:
            raise IdentityError(thing_id)
        self.things.pop(thing_id)
        self.resident.discard(thing_id)
        self.context.pop(thing_id, None)
        self.parent_by_child.pop(thing_id, None)
        self.pending_work = [w for w in self.pending_work if w.thing_id != thing_id]
        self.tombstones.add(thing_id)

    def attach_behavior(self, thing_id: str, attachment_id: str, behavior_id: str, revision: int) -> None:
        thing = self.things[thing_id]
        if attachment_id in thing.attachments:
            raise IdentityError(f"duplicate attachment: {attachment_id}")
        spec = self.behavior_catalog.get((behavior_id, revision))
        if spec is None:
            raise CompatibilityError(f"missing behavior {behavior_id}@{revision}")
        self.artifacts.acquire([spec.artifact_id])
        thing.attachments[attachment_id] = Attachment(
            attachment_id=attachment_id,
            behavior_id=behavior_id,
            revision=revision,
            private_schema=tuple(spec.private_schema),
            private_state={name: None for name in spec.private_schema},
            artifact_id=spec.artifact_id,
        )

    def schedule(
        self,
        *,
        work_id: str,
        thing_id: str,
        attachment_id: str,
        handler: str,
        payload: dict[str, Any] | None = None,
        delay: int = 0,
        durable: bool = True,
    ) -> None:
        thing = self.things[thing_id]
        if attachment_id not in thing.attachments:
            raise IdentityError(attachment_id)
        self.pending_work.append(
            PendingWork(
                work_id=work_id,
                thing_id=thing_id,
                attachment_id=attachment_id,
                handler=handler,
                payload=deepcopy(payload or {}),
                due_tick=self.tick + delay,
                order=self._next_order,
                durable=durable,
            )
        )
        self._next_order += 1

    def swap_behavior(
        self,
        thing_id: str,
        attachment_id: str,
        new_behavior_id: str,
        new_revision: int,
        *,
        migration: dict[str, Any] | None = None,
        continuation_map: dict[str, str] | None = None,
        cancel_pending: bool = False,
    ) -> None:
        thing = self.things[thing_id]
        old = thing.attachments[attachment_id]
        spec = self.behavior_catalog.get((new_behavior_id, new_revision))
        if spec is None:
            raise SwapError("new behavior is unavailable")
        try:
            self.artifacts.acquire([spec.artifact_id])
        except AcquisitionError as exc:
            raise SwapError(str(exc)) from exc

        planned_work: list[PendingWork] = []
        for work in self.pending_work:
            candidate = deepcopy(work)
            if work.thing_id == thing_id and work.attachment_id == attachment_id:
                mapped = (continuation_map or {}).get(
                    work.handler,
                    work.handler if work.handler in spec.handlers else None,
                )
                if mapped is None:
                    if cancel_pending:
                        continue
                    raise SwapError(f"pending continuation is incompatible: {work.handler}")
                candidate.handler = mapped
            planned_work.append(candidate)

        old_schema = tuple(old.private_schema)
        new_schema = tuple(spec.private_schema)
        if old_schema == new_schema:
            planned_private = deepcopy(old.private_state)
        elif migration is None:
            raise SwapError("private state schema is incompatible")
        else:
            if set(migration) != set(new_schema):
                raise SwapError("migration must produce exactly the new private schema")
            planned_private: dict[str, Any] = {}
            for key, source in migration.items():
                if isinstance(source, str) and source.startswith("$old."):
                    source_key = source[5:]
                    if source_key not in old.private_state:
                        raise SwapError(f"migration source missing: {source_key}")
                    planned_private[key] = deepcopy(old.private_state[source_key])
                else:
                    planned_private[key] = deepcopy(source)

        old.behavior_id = spec.behavior_id
        old.revision = spec.revision
        old.private_schema = tuple(spec.private_schema)
        old.private_state = planned_private
        old.artifact_id = spec.artifact_id
        self.pending_work = planned_work

    def _descendants(self, root_id: str) -> set[str]:
        selected = {root_id}
        changed = True
        while changed:
            changed = False
            for child, parent in self.parent_by_child.items():
                if parent in selected and child not in selected:
                    selected.add(child)
                    changed = True
        return selected

    def promote_group(
        self,
        root_thing_id: str,
        definition_id: str,
        element_ids: dict[str, str],
        *,
        instance_id: str,
    ) -> tuple[Definition, Instance]:
        if definition_id in self.definitions:
            raise IdentityError(f"duplicate DefinitionId: {definition_id}")
        if instance_id in self.instances:
            raise IdentityError(f"duplicate InstanceId: {instance_id}")
        if len(set(element_ids.values())) != len(element_ids):
            raise IdentityError("ElementIds must be unique within a definition")
        selected = self._descendants(root_thing_id)
        if selected != set(element_ids):
            raise DefinitionConflict("element_ids must cover the promoted subgraph exactly")
        elements: dict[str, DefinitionElement] = {}
        for thing_id in selected:
            thing = self.things[thing_id]
            parent = self.parent_by_child.get(thing_id)
            elements[element_ids[thing_id]] = DefinitionElement(
                element_id=element_ids[thing_id],
                state=deepcopy(thing.state),
                facets=set(thing.facets),
                ports=set(thing.ports),
                parent_element=element_ids[parent] if parent in selected else None,
            )
        definition = Definition(
            definition_id=definition_id,
            revision=1,
            root_element_id=element_ids[root_thing_id],
            elements=elements,
        )
        instance = Instance(
            instance_id=instance_id,
            definition_id=definition_id,
            base_revision=1,
            root_element_id=definition.root_element_id,
            root_thing_id=root_thing_id,
            thing_by_element={element_id: thing_id for thing_id, element_id in element_ids.items()},
        )
        self.definitions[definition_id] = deepcopy(definition)
        self.instances[instance_id] = deepcopy(instance)
        return deepcopy(definition), deepcopy(instance)

    def instantiate(self, definition_id: str, *, instance_id: str, prefix: str) -> Instance:
        if instance_id in self.instances:
            raise IdentityError(f"duplicate InstanceId: {instance_id}")
        definition = self.definitions[definition_id]
        mapping = {element_id: f"{prefix}:{element_id}" for element_id in definition.elements}
        generated = list(mapping.values())
        if len(generated) != len(set(generated)):
            raise IdentityError("generated ThingIds are not unique")
        collisions = [
            thing_id for thing_id in generated
            if thing_id in self.things or thing_id in self.tombstones
        ]
        if collisions:
            raise IdentityError(f"instance ThingId collision: {sorted(collisions)}")
        for element_id, element in definition.elements.items():
            self.add_thing(
                Thing(
                    thing_id=mapping[element_id],
                    state=deepcopy(element.state),
                    facets=set(element.facets),
                    ports=set(element.ports),
                )
            )
        for element_id, element in definition.elements.items():
            if element.parent_element is not None:
                self.reparent(mapping[element_id], mapping[element.parent_element])
        instance = Instance(
            instance_id=instance_id,
            definition_id=definition_id,
            base_revision=definition.revision,
            root_element_id=definition.root_element_id,
            root_thing_id=mapping[definition.root_element_id],
            thing_by_element=mapping,
        )
        self.instances[instance_id] = instance
        return deepcopy(instance)

    def resolve_exposure(self, instance_id: str, public_port: str) -> tuple[str, str]:
        instance = self.instances[instance_id]
        definition = self.definitions[instance.definition_id]
        element_id, port_id = definition.exposures[public_port]
        return instance.thing_by_element[element_id], port_id

    def update_definition(self, new: Definition) -> None:
        old = self.definitions.get(new.definition_id)
        if old is None:
            raise DefinitionConflict("unknown definition")
        if new.revision <= old.revision:
            raise DefinitionConflict("definition revision must increase")
        affected = [i for i in self.instances.values() if i.definition_id == new.definition_id]
        staged_instances = deepcopy(affected)
        old_ids, new_ids = set(old.elements), set(new.elements)

        for inst in staged_instances:
            if inst.base_revision != old.revision:
                raise DefinitionConflict("instance base revision mismatch")
            removed = old_ids - new_ids
            for element_id in removed:
                if element_id in inst.state_overrides or element_id in inst.parent_overrides:
                    raise DefinitionConflict(f"removed element has instance override: {element_id}")
                if any(
                    public_port in inst.connected_public_ports and target[0] == element_id
                    for public_port, target in old.exposures.items()
                ):
                    raise DefinitionConflict(f"removed element backs connected public port: {element_id}")
                inst.thing_by_element.pop(element_id, None)
            for public_port in inst.connected_public_ports:
                if public_port in old.exposures and public_port not in new.exposures:
                    raise DefinitionConflict(f"connected public port removed: {public_port}")
            for public_port, (element_id, port_id) in new.exposures.items():
                if element_id not in new.elements or port_id not in new.elements[element_id].ports:
                    raise DefinitionConflict(f"invalid public exposure: {public_port}")
            for element_id in sorted(new_ids - old_ids):
                inst.thing_by_element[element_id] = (
                    f"{inst.root_thing_id}::gen::{new.revision}::{element_id}"
                )
            inst.base_revision = new.revision

        self.definitions[new.definition_id] = deepcopy(new)
        for staged in staged_instances:
            self.instances[staged.instance_id] = staged

    def _required_artifacts(self, thing: Thing) -> set[str]:
        result = set(thing.runtime_required_artifacts)
        for attachment in thing.attachments.values():
            result.add(attachment.artifact_id)
        return result

    def _acquire_for(self, thing: Thing) -> tuple[str, ...]:
        required = self._required_artifacts(thing)
        return self.artifacts.acquire(required) if required else ()

    def unload(self, thing_ids: list[str] | tuple[str, ...]) -> None:
        for thing_id in thing_ids:
            if thing_id not in self.things:
                raise IdentityError(thing_id)
        for thing_id in thing_ids:
            self.resident.discard(thing_id)
            self.context.pop(thing_id, None)

    def load(self, thing_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        staged: set[str] = set()
        required: set[str] = set()
        for thing_id in thing_ids:
            if thing_id not in self.things:
                raise AcquisitionError(f"missing_thing:{thing_id}")
            if thing_id not in self.resident:
                staged.add(thing_id)
                required.update(self._required_artifacts(self.things[thing_id]))
        acquired = self.artifacts.acquire(required) if required else ()
        self.resident.update(staged)
        return acquired

    def snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
        def asset_record(asset: AssetRevision) -> dict[str, Any]:
            record = asdict(asset)
            record["derivation"] = list(asset.derivation)
            return record

        things = []
        for thing_id in sorted(self.things):
            thing = self.things[thing_id]
            things.append(
                {
                    "thing_id": thing.thing_id,
                    "state": deepcopy(thing.state),
                    "facets": sorted(thing.facets),
                    "ports": sorted(thing.ports),
                    "refs": deepcopy(thing.refs),
                    "attachments": [
                        {
                            "attachment_id": a.attachment_id,
                            "behavior_id": a.behavior_id,
                            "revision": a.revision,
                            "private_schema": list(a.private_schema),
                            "private_state": deepcopy(a.private_state),
                            "artifact_id": a.artifact_id,
                        }
                        for a in sorted(thing.attachments.values(), key=lambda x: x.attachment_id)
                    ],
                    "assets": [
                        asset_record(a)
                        for a in sorted(thing.assets.values(), key=lambda x: x.asset_id)
                    ],
                    "runtime_required_artifacts": sorted(thing.runtime_required_artifacts),
                    "residency": "resident" if thing_id in self.resident else "unloaded",
                }
            )

        definitions = []
        for definition_id in sorted(self.definitions):
            d = self.definitions[definition_id]
            definitions.append(
                {
                    "definition_id": d.definition_id,
                    "revision": d.revision,
                    "root_element_id": d.root_element_id,
                    "elements": [
                        {
                            "element_id": e.element_id,
                            "state": deepcopy(e.state),
                            "facets": sorted(e.facets),
                            "ports": sorted(e.ports),
                            "parent_element": e.parent_element,
                        }
                        for e in sorted(d.elements.values(), key=lambda x: x.element_id)
                    ],
                    "exposures": {
                        key: list(value) for key, value in sorted(d.exposures.items())
                    },
                }
            )

        instances = []
        for instance_id in sorted(self.instances):
            i = self.instances[instance_id]
            instances.append(
                {
                    "instance_id": i.instance_id,
                    "definition_id": i.definition_id,
                    "base_revision": i.base_revision,
                    "root_element_id": i.root_element_id,
                    "root_thing_id": i.root_thing_id,
                    "thing_by_element": dict(sorted(i.thing_by_element.items())),
                    "state_overrides": deepcopy(i.state_overrides),
                    "parent_overrides": deepcopy(i.parent_overrides),
                    "connected_public_ports": sorted(i.connected_public_ports),
                }
            )

        return {
            "schema": self.SNAPSHOT_SCHEMA,
            "snapshot_id": snapshot_id,
            "authored_revision": self.authored_revision,
            "tick": self.tick,
            "next_order": self._next_order,
            "things": things,
            "tombstones": sorted(self.tombstones),
            "parent_by_child": dict(sorted(self.parent_by_child.items())),
            "controller_by_thing": dict(sorted(self.controller_by_thing.items())),
            "authority_by_thing": dict(sorted(self.authority_by_thing.items())),
            "persistence_by_thing": dict(sorted(self.persistence_by_thing.items())),
            "replication_by_thing": dict(sorted(self.replication_by_thing.items())),
            "observer_by_thing": dict(sorted(self.observer_by_thing.items())),
            "definitions": definitions,
            "instances": instances,
            "pending_work": [
                asdict(w)
                for w in sorted(
                    (w for w in self.pending_work if w.durable),
                    key=lambda w: (w.due_tick, w.order, w.work_id),
                )
            ],
        }

    @classmethod
    def restore(
        cls,
        snapshot: dict[str, Any],
        *,
        artifact_store: ArtifactStore,
        behavior_catalog: dict[tuple[str, int], BehaviorSpec],
    ) -> "FabricWorld":
        snapshot = json.loads(json.dumps(snapshot, sort_keys=True))
        if snapshot.get("schema") != cls.SNAPSHOT_SCHEMA:
            raise CompatibilityError("unsupported snapshot schema")
        staged = cls(
            authored_revision=str(snapshot["authored_revision"]),
            artifact_store=artifact_store,
            behavior_catalog=behavior_catalog,
        )
        staged.tick = int(snapshot["tick"])
        staged._next_order = int(snapshot.get("next_order", 0))

        seen: set[str] = set()
        residency: dict[str, str] = {}
        for record in snapshot.get("things", []):
            thing_id = str(record["thing_id"])
            if thing_id in seen:
                raise IdentityError(f"duplicate ThingId in snapshot: {thing_id}")
            seen.add(thing_id)
            thing = Thing(
                thing_id=thing_id,
                state=deepcopy(record.get("state", {})),
                facets=set(record.get("facets", [])),
                ports=set(record.get("ports", [])),
                refs=deepcopy(record.get("refs", {})),
                runtime_required_artifacts=set(record.get("runtime_required_artifacts", [])),
            )
            for arec in record.get("assets", []):
                asset = AssetRevision.from_mapping(arec)
                if asset.asset_id in thing.assets:
                    raise IdentityError(f"duplicate AssetId in snapshot: {asset.asset_id}")
                thing.assets[asset.asset_id] = asset
            for brec in record.get("attachments", []):
                key = (str(brec["behavior_id"]), int(brec["revision"]))
                spec = behavior_catalog.get(key)
                if spec is None:
                    raise CompatibilityError(f"missing behavior on restore: {key[0]}@{key[1]}")
                if tuple(brec["private_schema"]) != tuple(spec.private_schema):
                    raise CompatibilityError(f"behavior private schema mismatch: {key[0]}")
                if str(brec["artifact_id"]) != spec.artifact_id:
                    raise CompatibilityError(f"behavior artifact mismatch: {key[0]}")
                thing.attachments[str(brec["attachment_id"])] = Attachment(
                    attachment_id=str(brec["attachment_id"]),
                    behavior_id=key[0],
                    revision=key[1],
                    private_schema=tuple(brec["private_schema"]),
                    private_state=deepcopy(brec.get("private_state", {})),
                    artifact_id=str(brec["artifact_id"]),
                )
            staged.things[thing_id] = thing
            residency[thing_id] = str(record["residency"])

        staged.tombstones = set(snapshot.get("tombstones", []))
        if staged.tombstones & set(staged.things):
            raise IdentityError("snapshot contains live/tombstoned identity collision")

        for name in (
            "parent_by_child",
            "controller_by_thing",
            "authority_by_thing",
            "persistence_by_thing",
            "replication_by_thing",
            "observer_by_thing",
        ):
            setattr(staged, name, deepcopy(snapshot.get(name, {})))

        for child_id, parent_id in staged.parent_by_child.items():
            if child_id not in staged.things or parent_id not in staged.things:
                raise CompatibilityError("containment references unknown ThingId")
        for child_id in staged.parent_by_child:
            cursor = child_id
            seen_chain: set[str] = set()
            while cursor in staged.parent_by_child:
                if cursor in seen_chain:
                    raise CompatibilityError("containment cycle in snapshot")
                seen_chain.add(cursor)
                cursor = staged.parent_by_child[cursor]

        for drec in snapshot.get("definitions", []):
            elements = {}
            for erec in drec.get("elements", []):
                element = DefinitionElement(
                    element_id=str(erec["element_id"]),
                    state=deepcopy(erec.get("state", {})),
                    facets=set(erec.get("facets", [])),
                    ports=set(erec.get("ports", [])),
                    parent_element=erec.get("parent_element"),
                )
                if element.element_id in elements:
                    raise IdentityError(f"duplicate ElementId: {element.element_id}")
                elements[element.element_id] = element
            definition = Definition(
                definition_id=str(drec["definition_id"]),
                revision=int(drec["revision"]),
                root_element_id=str(drec["root_element_id"]),
                elements=elements,
                exposures={
                    key: (str(value[0]), str(value[1]))
                    for key, value in drec.get("exposures", {}).items()
                },
            )
            if definition.definition_id in staged.definitions:
                raise IdentityError(f"duplicate DefinitionId: {definition.definition_id}")
            staged.definitions[definition.definition_id] = definition

        for irec in snapshot.get("instances", []):
            instance = Instance(
                instance_id=str(irec["instance_id"]),
                definition_id=str(irec["definition_id"]),
                base_revision=int(irec["base_revision"]),
                root_element_id=str(irec["root_element_id"]),
                root_thing_id=str(irec["root_thing_id"]),
                thing_by_element={str(k): str(v) for k, v in irec["thing_by_element"].items()},
                state_overrides=deepcopy(irec.get("state_overrides", {})),
                parent_overrides=deepcopy(irec.get("parent_overrides", {})),
                connected_public_ports=set(irec.get("connected_public_ports", [])),
            )
            if instance.instance_id in staged.instances:
                raise IdentityError(f"duplicate InstanceId: {instance.instance_id}")
            definition = staged.definitions.get(instance.definition_id)
            if definition is None or instance.base_revision != definition.revision:
                raise CompatibilityError("instance/definition revision mismatch on restore")
            staged.instances[instance.instance_id] = instance

        staged.pending_work = [
            PendingWork(
                work_id=str(w["work_id"]),
                thing_id=str(w["thing_id"]),
                attachment_id=str(w["attachment_id"]),
                handler=str(w["handler"]),
                payload=deepcopy(w.get("payload", {})),
                due_tick=int(w["due_tick"]),
                order=int(w["order"]),
                durable=bool(w.get("durable", True)),
            )
            for w in snapshot.get("pending_work", [])
        ]

        required: set[str] = set()
        for thing_id, status in residency.items():
            if status not in {"resident", "unloaded"}:
                raise CompatibilityError(f"invalid residency: {status}")
            if status == "resident":
                required.update(staged._required_artifacts(staged.things[thing_id]))
        artifact_store.acquire(required)
        staged.resident = {thing_id for thing_id, status in residency.items() if status == "resident"}
        return staged
