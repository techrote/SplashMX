"""Production canonical semantic kernel for SplashMX Architecture v1.

SMX-023 owns logical identity, Thing/relationship/definition/instance records and
atomic authored-state transactions. Physical serialization, persistence, execution,
Godot/browser materialization and collaboration transport are deliberately outside
this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
import re
from typing import Any, ClassVar, Mapping, Protocol


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

# These are forbidden when they appear as durable host/runtime locator fields.
# A plain authored value named ``url`` is not itself a durable identity declaration,
# so URL is guarded at typed identity boundaries by MODULES.json rather than banned
# from arbitrary user-authored data.
_FORBIDDEN_DURABLE_FIELD_NAMES = {
    "nodepath",
    "rid",
    "resourceuid",
    "resourcepath",
    "domnodeidentity",
    "databaserowid",
    "cachekey",
    "transportpeerid",
    "connectionhandle",
    "socketid",
    "sessionid",
    "processhandle",
    "capabilitytoken",
    "capabilitygrant",
}


def _normalise_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


class SemanticError(ValueError):
    """Typed canonical-core failure suitable for later failure-envelope mapping."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _validate_identifier(value: str, role: str) -> None:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise SemanticError(
            "canonical.invalid_identity",
            f"{role} must be a non-empty path-independent semantic token",
        )


@dataclass(frozen=True, order=True)
class SemanticId:
    """Role-typed path-independent semantic identity."""

    value: str
    role: ClassVar[str] = "SemanticId"

    def __post_init__(self) -> None:
        _validate_identifier(self.value, self.role)

    def __str__(self) -> str:
        return self.value


class ThingId(SemanticId):
    role = "ThingId"


class DefinitionId(SemanticId):
    role = "DefinitionId"


class ElementId(SemanticId):
    role = "ElementId"


class BehaviourAttachmentId(SemanticId):
    role = "BehaviourAttachmentId"


class PortId(SemanticId):
    role = "PortId"


class ConnectionId(SemanticId):
    role = "ConnectionId"


class RelationId(SemanticId):
    role = "RelationId"


class AssetId(SemanticId):
    role = "AssetId"


class ProjectId(SemanticId):
    role = "ProjectId"


class ProjectRevisionId(SemanticId):
    role = "ProjectRevisionId"


class ReferenceState(str, Enum):
    LOADED = "loaded"
    KNOWN_UNLOADED = "known-unloaded"
    TOMBSTONED = "tombstoned"
    UNKNOWN = "unknown"


class PortKind(str, Enum):
    COMMAND = "command"
    EVENT = "event"
    VALUE = "value"


class PortDirection(str, Enum):
    IN = "in"
    OUT = "out"
    READ = "read"
    WRITE = "write"
    READWRITE = "readwrite"


class RelationshipKind(str, Enum):
    CONTAINS = "contains"
    TRANSFORM_LOCALITY = "transform-locality"
    REFERENCES = "references"
    OBSERVES = "observes"
    CONTROLLED_BY = "controlled-by"
    AUTHORITY_AT = "authority-at"
    PERSISTED_VIA = "persisted-via"
    REPLICATED_IN = "replicated-in"


@dataclass(frozen=True)
class PortRecord:
    port_id: PortId
    name: str
    kind: PortKind
    direction: PortDirection


@dataclass(frozen=True)
class BehaviourAttachmentRecord:
    attachment_id: BehaviourAttachmentId
    behaviour_revision: str
    authored_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThingRecord:
    thing_id: ThingId
    label: str
    authored_state: Mapping[str, Any] = field(default_factory=dict)
    ports: Mapping[PortId, PortRecord] = field(default_factory=dict)
    behaviours: Mapping[BehaviourAttachmentId, BehaviourAttachmentRecord] = field(default_factory=dict)
    tombstoned: bool = False


@dataclass(frozen=True)
class RelationshipRecord:
    relation_id: RelationId
    kind: RelationshipKind
    source: ThingId
    target: ThingId
    tombstoned: bool = False


@dataclass(frozen=True)
class ConnectionEndpoint:
    thing_id: ThingId
    port_id: PortId


@dataclass(frozen=True)
class ConnectionRecord:
    connection_id: ConnectionId
    source: ConnectionEndpoint
    target: ConnectionEndpoint
    tombstoned: bool = False


@dataclass(frozen=True)
class DefinitionElementRecord:
    element_id: ElementId
    label: str
    authored_state: Mapping[str, Any] = field(default_factory=dict)
    ports: Mapping[PortId, PortRecord] = field(default_factory=dict)
    parent_element_id: ElementId | None = None


@dataclass(frozen=True)
class DefinitionExposure:
    public_port_id: PortId
    element_id: ElementId
    element_port_id: PortId


@dataclass(frozen=True)
class DefinitionRecord:
    definition_id: DefinitionId
    revision: int
    root_element_id: ElementId
    elements: Mapping[ElementId, DefinitionElementRecord]
    exposures: Mapping[PortId, DefinitionExposure] = field(default_factory=dict)


@dataclass(frozen=True)
class InstanceRecord:
    root_thing_id: ThingId
    definition_id: DefinitionId
    base_revision: int
    thing_by_element: Mapping[ElementId, ThingId]
    state_overrides: Mapping[ElementId, Mapping[str, Any]] = field(default_factory=dict)
    parent_overrides: Mapping[ElementId, ElementId | None] = field(default_factory=dict)
    local_thing_ids: frozenset[ThingId] = field(default_factory=frozenset)


@dataclass
class CanonicalDocument:
    """Logical authored document; transient/runtime/world/collab planes are excluded."""

    project_id: ProjectId
    project_revision_id: ProjectRevisionId
    things: dict[ThingId, ThingRecord] = field(default_factory=dict)
    relationships: dict[RelationId, RelationshipRecord] = field(default_factory=dict)
    connections: dict[ConnectionId, ConnectionRecord] = field(default_factory=dict)
    definitions: dict[DefinitionId, DefinitionRecord] = field(default_factory=dict)
    instances: dict[ThingId, InstanceRecord] = field(default_factory=dict)
    known_unloaded_things: set[ThingId] = field(default_factory=set)

    def reference_state(self, thing_id: ThingId) -> ReferenceState:
        thing = self.things.get(thing_id)
        if thing is not None:
            return ReferenceState.TOMBSTONED if thing.tombstoned else ReferenceState.LOADED
        if thing_id in self.known_unloaded_things:
            return ReferenceState.KNOWN_UNLOADED
        return ReferenceState.UNKNOWN


@dataclass
class TransientContext:
    """Explicit non-canonical process/editor/network context."""

    runtime_handles: dict[ThingId, Any] = field(default_factory=dict)
    session_id: str | None = None
    transport_peer_id: str | None = None
    editor_selection: set[ThingId] = field(default_factory=set)


class Operation(Protocol):
    def apply(self, draft: CanonicalDocument) -> None: ...


@dataclass(frozen=True)
class SemanticTransaction:
    result_revision_id: ProjectRevisionId
    operations: tuple[Operation, ...]


@dataclass(frozen=True)
class AddThing:
    thing: ThingRecord

    def apply(self, draft: CanonicalDocument) -> None:
        if self.thing.thing_id in draft.things or self.thing.thing_id in draft.known_unloaded_things:
            raise SemanticError("canonical.duplicate_identity", f"ThingId already exists or is reserved: {self.thing.thing_id}")
        _validate_thing(self.thing)
        draft.things[self.thing.thing_id] = deepcopy(self.thing)


@dataclass(frozen=True)
class RenameThing:
    thing_id: ThingId
    label: str

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        draft.things[self.thing_id] = replace(thing, label=self.label)


@dataclass(frozen=True)
class SetAuthoredState:
    thing_id: ThingId
    authored_state: Mapping[str, Any]

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        _validate_authored_value(self.authored_state, f"Thing {self.thing_id} authored_state")
        draft.things[self.thing_id] = replace(thing, authored_state=deepcopy(dict(self.authored_state)))


@dataclass(frozen=True)
class AddPort:
    thing_id: ThingId
    port: PortRecord

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        if self.port.port_id in thing.ports:
            raise SemanticError("canonical.duplicate_identity", f"PortId already exists on Thing {self.thing_id}: {self.port.port_id}")
        ports = dict(thing.ports)
        ports[self.port.port_id] = self.port
        draft.things[self.thing_id] = replace(thing, ports=ports)


@dataclass(frozen=True)
class RemovePort:
    thing_id: ThingId
    port_id: PortId

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        if self.port_id not in thing.ports:
            raise SemanticError("canonical.unknown_port", f"Unknown PortId {self.port_id}")
        ports = dict(thing.ports)
        del ports[self.port_id]
        draft.things[self.thing_id] = replace(thing, ports=ports)


@dataclass(frozen=True)
class AddBehaviourAttachment:
    thing_id: ThingId
    attachment: BehaviourAttachmentRecord

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        if self.attachment.attachment_id in thing.behaviours:
            raise SemanticError("canonical.duplicate_identity", f"Behaviour attachment already exists: {self.attachment.attachment_id}")
        _validate_authored_value(self.attachment.authored_config, f"Behaviour {self.attachment.attachment_id} authored_config")
        behaviours = dict(thing.behaviours)
        behaviours[self.attachment.attachment_id] = deepcopy(self.attachment)
        draft.things[self.thing_id] = replace(thing, behaviours=behaviours)


@dataclass(frozen=True)
class ReplaceBehaviourAttachment:
    thing_id: ThingId
    attachment: BehaviourAttachmentRecord

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        if self.attachment.attachment_id not in thing.behaviours:
            raise SemanticError("canonical.unknown_behaviour", f"Unknown BehaviourAttachmentId {self.attachment.attachment_id}")
        _validate_authored_value(self.attachment.authored_config, f"Behaviour {self.attachment.attachment_id} authored_config")
        behaviours = dict(thing.behaviours)
        behaviours[self.attachment.attachment_id] = deepcopy(self.attachment)
        draft.things[self.thing_id] = replace(thing, behaviours=behaviours)


@dataclass(frozen=True)
class RemoveBehaviourAttachment:
    thing_id: ThingId
    attachment_id: BehaviourAttachmentId

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        if self.attachment_id not in thing.behaviours:
            raise SemanticError("canonical.unknown_behaviour", f"Unknown BehaviourAttachmentId {self.attachment_id}")
        behaviours = dict(thing.behaviours)
        del behaviours[self.attachment_id]
        draft.things[self.thing_id] = replace(thing, behaviours=behaviours)


@dataclass(frozen=True)
class AddRelationship:
    relationship: RelationshipRecord

    def apply(self, draft: CanonicalDocument) -> None:
        if self.relationship.relation_id in draft.relationships:
            raise SemanticError("canonical.duplicate_identity", f"RelationId already exists: {self.relationship.relation_id}")
        _live_thing(draft, self.relationship.source)
        _live_thing(draft, self.relationship.target)
        draft.relationships[self.relationship.relation_id] = self.relationship


@dataclass(frozen=True)
class SetContainment:
    child_id: ThingId
    parent_id: ThingId
    relation_id: RelationId

    def apply(self, draft: CanonicalDocument) -> None:
        _live_thing(draft, self.child_id)
        _live_thing(draft, self.parent_id)
        if self.child_id == self.parent_id:
            raise SemanticError("canonical.containment_cycle", "Thing cannot contain itself")
        active = [record for record in draft.relationships.values() if not record.tombstoned and record.kind is RelationshipKind.CONTAINS and record.target == self.child_id]
        if len(active) > 1:
            raise SemanticError("canonical.invalid_document", f"Thing {self.child_id} already has multiple active parents")
        if active:
            current = active[0]
            draft.relationships[current.relation_id] = replace(current, source=self.parent_id)
            return
        if self.relation_id in draft.relationships:
            raise SemanticError("canonical.duplicate_identity", f"RelationId already exists: {self.relation_id}")
        draft.relationships[self.relation_id] = RelationshipRecord(self.relation_id, RelationshipKind.CONTAINS, self.parent_id, self.child_id)


@dataclass(frozen=True)
class TombstoneRelationship:
    relation_id: RelationId

    def apply(self, draft: CanonicalDocument) -> None:
        record = draft.relationships.get(self.relation_id)
        if record is None:
            raise SemanticError("canonical.unknown_relationship", f"Unknown RelationId {self.relation_id}")
        if not record.tombstoned:
            draft.relationships[self.relation_id] = replace(record, tombstoned=True)


@dataclass(frozen=True)
class AddConnection:
    connection: ConnectionRecord

    def apply(self, draft: CanonicalDocument) -> None:
        if self.connection.connection_id in draft.connections:
            raise SemanticError("canonical.duplicate_identity", f"ConnectionId already exists: {self.connection.connection_id}")
        _validate_connection(draft, self.connection)
        draft.connections[self.connection.connection_id] = self.connection


@dataclass(frozen=True)
class ReplaceConnection:
    """Replace one live Connection while preserving its stable ConnectionId."""

    connection: ConnectionRecord

    def apply(self, draft: CanonicalDocument) -> None:
        current = draft.connections.get(self.connection.connection_id)
        if current is None or current.tombstoned:
            raise SemanticError(
                "canonical.unknown_connection",
                f"Unknown live ConnectionId {self.connection.connection_id}",
            )
        if self.connection.tombstoned:
            raise SemanticError(
                "canonical.invalid_connection",
                "A Connection replacement must remain live.",
            )
        _validate_connection(draft, self.connection)
        draft.connections[self.connection.connection_id] = self.connection


@dataclass(frozen=True)
class TombstoneConnection:
    connection_id: ConnectionId

    def apply(self, draft: CanonicalDocument) -> None:
        record = draft.connections.get(self.connection_id)
        if record is None:
            raise SemanticError("canonical.unknown_connection", f"Unknown ConnectionId {self.connection_id}")
        if not record.tombstoned:
            draft.connections[self.connection_id] = replace(record, tombstoned=True)


@dataclass(frozen=True)
class TombstoneThing:
    thing_id: ThingId

    def apply(self, draft: CanonicalDocument) -> None:
        thing = _live_thing(draft, self.thing_id)
        draft.things[self.thing_id] = replace(thing, tombstoned=True)
        for connection_id, connection in list(draft.connections.items()):
            if not connection.tombstoned and (connection.source.thing_id == self.thing_id or connection.target.thing_id == self.thing_id):
                draft.connections[connection_id] = replace(connection, tombstoned=True)
        for relation_id, relationship in list(draft.relationships.items()):
            if not relationship.tombstoned and (relationship.source == self.thing_id or relationship.target == self.thing_id):
                draft.relationships[relation_id] = replace(relationship, tombstoned=True)


@dataclass(frozen=True)
class AddDefinition:
    definition: DefinitionRecord

    def apply(self, draft: CanonicalDocument) -> None:
        if self.definition.definition_id in draft.definitions:
            raise SemanticError("canonical.duplicate_identity", f"DefinitionId already exists: {self.definition.definition_id}")
        _validate_definition(self.definition)
        draft.definitions[self.definition.definition_id] = deepcopy(self.definition)


@dataclass(frozen=True)
class AddInstance:
    instance: InstanceRecord

    def apply(self, draft: CanonicalDocument) -> None:
        if self.instance.root_thing_id in draft.instances:
            raise SemanticError("canonical.duplicate_identity", f"Instance root already registered: {self.instance.root_thing_id}")
        draft.instances[self.instance.root_thing_id] = deepcopy(self.instance)


@dataclass(frozen=True)
class SetInstanceStateOverride:
    instance_root_id: ThingId
    definition_id: DefinitionId
    element_id: ElementId
    key: str
    value: Any

    def apply(self, draft: CanonicalDocument) -> None:
        instance = draft.instances.get(self.instance_root_id)
        if instance is None:
            raise SemanticError("canonical.unknown_instance", f"Unknown instance root {self.instance_root_id}")
        if instance.definition_id != self.definition_id:
            raise SemanticError("canonical.definition_scope_mismatch", "DefinitionId does not match the instance conflict/override locus")
        definition = draft.definitions.get(self.definition_id)
        if definition is None or self.element_id not in definition.elements:
            raise SemanticError("canonical.unknown_definition_element", f"Unknown element {self.element_id} in {self.definition_id}")
        _validate_authored_value({self.key: self.value}, "instance state override")
        overrides = {key: dict(value) for key, value in instance.state_overrides.items()}
        element_overrides = overrides.setdefault(self.element_id, {})
        element_overrides[self.key] = deepcopy(self.value)
        draft.instances[self.instance_root_id] = replace(instance, state_overrides=overrides)


@dataclass(frozen=True)
class PromoteGroup:
    root_thing_id: ThingId
    definition_id: DefinitionId
    element_by_thing: Mapping[ThingId, ElementId]
    exposures: Mapping[PortId, DefinitionExposure] = field(default_factory=dict)

    def apply(self, draft: CanonicalDocument) -> None:
        if self.definition_id in draft.definitions:
            raise SemanticError("canonical.duplicate_identity", f"DefinitionId already exists: {self.definition_id}")
        if self.root_thing_id in draft.instances:
            raise SemanticError("canonical.duplicate_identity", f"Thing is already an instance root: {self.root_thing_id}")
        selected = _descendant_subgraph(draft, self.root_thing_id)
        if set(self.element_by_thing) != selected:
            raise SemanticError("canonical.invalid_promotion", "element_by_thing must cover the promoted containment subgraph exactly")
        element_ids = list(self.element_by_thing.values())
        if len(set(element_ids)) != len(element_ids):
            raise SemanticError("canonical.duplicate_identity", "Definition element identities must be unique")
        parent_by_child = _active_parent_map(draft)
        elements: dict[ElementId, DefinitionElementRecord] = {}
        for thing_id in selected:
            thing = _live_thing(draft, thing_id)
            parent_thing = parent_by_child.get(thing_id)
            parent_element = self.element_by_thing[parent_thing] if parent_thing in selected else None
            element_id = self.element_by_thing[thing_id]
            elements[element_id] = DefinitionElementRecord(element_id, thing.label, deepcopy(dict(thing.authored_state)), deepcopy(dict(thing.ports)), parent_element)
        definition = DefinitionRecord(self.definition_id, 1, self.element_by_thing[self.root_thing_id], elements, deepcopy(dict(self.exposures)))
        _validate_definition(definition)
        instance = InstanceRecord(self.root_thing_id, self.definition_id, 1, {element: thing for thing, element in self.element_by_thing.items()})
        draft.definitions[self.definition_id] = definition
        draft.instances[self.root_thing_id] = instance


@dataclass(frozen=True)
class InstantiateDefinition:
    definition_id: DefinitionId
    thing_by_element: Mapping[ElementId, ThingId]
    containment_relation_by_child_element: Mapping[ElementId, RelationId]

    def apply(self, draft: CanonicalDocument) -> None:
        definition = draft.definitions.get(self.definition_id)
        if definition is None:
            raise SemanticError("canonical.unknown_definition", f"Unknown DefinitionId {self.definition_id}")
        if set(self.thing_by_element) != set(definition.elements):
            raise SemanticError("canonical.invalid_instance", "thing_by_element must exactly cover Definition elements")
        values = list(self.thing_by_element.values())
        if len(values) != len(set(values)):
            raise SemanticError("canonical.duplicate_identity", "Each Definition element requires an independent concrete ThingId")
        expected_children = set(definition.elements) - {definition.root_element_id}
        if set(self.containment_relation_by_child_element) != expected_children:
            raise SemanticError("canonical.invalid_instance", "Containment RelationIds must cover each non-root Definition element")
        for element_id, thing_id in self.thing_by_element.items():
            if thing_id in draft.things or thing_id in draft.known_unloaded_things:
                raise SemanticError("canonical.duplicate_identity", f"ThingId already exists: {thing_id}")
            element = definition.elements[element_id]
            ports = deepcopy(dict(element.ports))
            if element_id == definition.root_element_id:
                for public_port_id, exposure in definition.exposures.items():
                    target = definition.elements[exposure.element_id].ports[exposure.element_port_id]
                    existing = ports.get(public_port_id)
                    public_record = PortRecord(public_port_id, existing.name if existing is not None else str(public_port_id), target.kind, target.direction)
                    if existing is not None and (existing.kind is not target.kind or existing.direction is not target.direction):
                        raise SemanticError("canonical.invalid_definition", f"Root port {public_port_id} conflicts with public exposure")
                    ports[public_port_id] = public_record
            draft.things[thing_id] = ThingRecord(thing_id, element.label, deepcopy(dict(element.authored_state)), ports)
        for child_element_id in expected_children:
            element = definition.elements[child_element_id]
            if element.parent_element_id is None:
                raise SemanticError("canonical.invalid_definition", f"Non-root element {child_element_id} has no parent")
            relation_id = self.containment_relation_by_child_element[child_element_id]
            if relation_id in draft.relationships:
                raise SemanticError("canonical.duplicate_identity", f"RelationId already exists: {relation_id}")
            draft.relationships[relation_id] = RelationshipRecord(relation_id, RelationshipKind.CONTAINS, self.thing_by_element[element.parent_element_id], self.thing_by_element[child_element_id])
        root_thing_id = self.thing_by_element[definition.root_element_id]
        if root_thing_id in draft.instances:
            raise SemanticError("canonical.duplicate_identity", f"Instance root already registered: {root_thing_id}")
        draft.instances[root_thing_id] = InstanceRecord(root_thing_id, definition.definition_id, definition.revision, deepcopy(dict(self.thing_by_element)))


@dataclass(frozen=True)
class ReplaceDefinition:
    """Conservative transactional same-lineage definition revision replacement."""

    definition: DefinitionRecord

    def apply(self, draft: CanonicalDocument) -> None:
        old = draft.definitions.get(self.definition.definition_id)
        if old is None:
            raise SemanticError("canonical.unknown_definition", f"Unknown DefinitionId {self.definition.definition_id}")
        if self.definition.revision <= old.revision:
            raise SemanticError("canonical.invalid_definition_revision", "Definition replacement revision must increase")
        _validate_definition(self.definition)
        old_ids = set(old.elements)
        new_ids = set(self.definition.elements)
        if new_ids - old_ids:
            raise SemanticError("canonical.definition_migration_required", "Adding definition elements requires an explicit identity-allocation migration")
        matching = [instance for instance in draft.instances.values() if instance.definition_id == old.definition_id]
        parent_by_child = _active_parent_map(draft)
        for instance in matching:
            if instance.base_revision != old.revision:
                raise SemanticError("canonical.definition_revision_mismatch", "Instance is not based on the current Definition revision")
            removed = old_ids - new_ids
            for element_id in removed:
                concrete_id = instance.thing_by_element[element_id]
                if element_id in instance.state_overrides or element_id in instance.parent_overrides:
                    raise SemanticError("canonical.definition_conflict", f"Removed element has an instance overlay: {element_id}")
                if concrete_id in instance.local_thing_ids:
                    raise SemanticError("canonical.definition_conflict", f"Removed element is protected by local instance semantics: {element_id}")
                if _has_live_noncontainment_relationship(draft, concrete_id):
                    raise SemanticError("canonical.definition_conflict", f"Removed element has durable relationships: {element_id}")
                if _has_live_connection(draft, concrete_id):
                    raise SemanticError("canonical.definition_conflict", f"Removed element has live Connections: {element_id}")
            for element_id, values in instance.state_overrides.items():
                if element_id not in self.definition.elements:
                    continue
                new_state = self.definition.elements[element_id].authored_state
                for key, value in values.items():
                    if key not in new_state:
                        raise SemanticError("canonical.definition_conflict", f"Override target was removed: {element_id}.{key}")
                    base_value = new_state[key]
                    if base_value is not None and value is not None and type(base_value) is not type(value):
                        raise SemanticError("canonical.definition_conflict", f"Override target changed type: {element_id}.{key}")
            for element_id, parent_override in instance.parent_overrides.items():
                if element_id not in self.definition.elements:
                    continue
                if parent_override is not None and parent_override not in self.definition.elements:
                    raise SemanticError("canonical.definition_conflict", f"Parent override target removed: {element_id}->{parent_override}")
            removed_public_ports = set(old.exposures) - set(self.definition.exposures)
            if removed_public_ports:
                for connection in draft.connections.values():
                    if connection.tombstoned:
                        continue
                    for endpoint in (connection.source, connection.target):
                        if endpoint.thing_id == instance.root_thing_id and endpoint.port_id in removed_public_ports:
                            raise SemanticError("canonical.definition_conflict", f"Connected public Definition port removed: {endpoint.port_id}")
            mapping = dict(instance.thing_by_element)
            for element_id in removed:
                concrete_id = mapping.pop(element_id)
                TombstoneThing(concrete_id).apply(draft)
            for element_id, new_element in self.definition.elements.items():
                if element_id == self.definition.root_element_id:
                    continue
                concrete_child = mapping[element_id]
                parent_element = instance.parent_overrides.get(element_id, new_element.parent_element_id)
                if parent_element is None:
                    continue
                concrete_parent = mapping[parent_element]
                current_parent = parent_by_child.get(concrete_child)
                if current_parent != concrete_parent:
                    existing = _active_containment_for_child(draft, concrete_child)
                    if existing is None:
                        raise SemanticError("canonical.definition_conflict", "Definition restructure needs an existing containment relation identity")
                    draft.relationships[existing.relation_id] = replace(existing, source=concrete_parent)
            draft.instances[instance.root_thing_id] = replace(instance, base_revision=self.definition.revision, thing_by_element=mapping)
        draft.definitions[self.definition.definition_id] = deepcopy(self.definition)


def definition_conflict_locus(definition_id: DefinitionId, element_id: ElementId, field_name: str) -> tuple[str, DefinitionId, ElementId, str]:
    """Return an R-018-01 conflict locus scoped by actual DefinitionId."""
    return ("definition", definition_id, element_id, field_name)


def apply_transaction(document: CanonicalDocument, transaction: SemanticTransaction) -> CanonicalDocument:
    """Stage all operations, validate the complete result, then publish by return."""
    if transaction.result_revision_id == document.project_revision_id:
        raise SemanticError("canonical.duplicate_revision", "A semantic transaction must publish a new ProjectRevisionId")
    draft = deepcopy(document)
    for operation in transaction.operations:
        operation.apply(draft)
    draft.project_revision_id = transaction.result_revision_id
    validate_document(draft)
    return draft


def validate_document(document: CanonicalDocument) -> None:
    _require_id(document.project_id, ProjectId, "project_id")
    _require_id(document.project_revision_id, ProjectRevisionId, "project_revision_id")
    overlap = set(document.things) & document.known_unloaded_things
    if overlap:
        raise SemanticError("canonical.invalid_document", f"Thing identities cannot be both materialized and known-unloaded: {sorted(map(str, overlap))}")
    for thing_id, thing in document.things.items():
        _require_id(thing_id, ThingId, "things key")
        if thing_id != thing.thing_id:
            raise SemanticError("canonical.identity_mismatch", "Thing map key mismatches ThingId")
        _validate_thing(thing)
    for known_id in document.known_unloaded_things:
        _require_id(known_id, ThingId, "known_unloaded ThingId")
    active_parent_by_child: dict[ThingId, ThingId] = {}
    for relation_id, relationship in document.relationships.items():
        _require_id(relation_id, RelationId, "relationships key")
        if relation_id != relationship.relation_id:
            raise SemanticError("canonical.identity_mismatch", "Relationship map key mismatches RelationId")
        _require_id(relationship.source, ThingId, "relationship source")
        _require_id(relationship.target, ThingId, "relationship target")
        if relationship.tombstoned:
            continue
        _live_thing(document, relationship.source)
        _live_thing(document, relationship.target)
        if relationship.kind is RelationshipKind.CONTAINS:
            if relationship.target in active_parent_by_child:
                raise SemanticError("canonical.multiple_parents", f"Thing has multiple containment parents: {relationship.target}")
            active_parent_by_child[relationship.target] = relationship.source
    _validate_containment_acyclic(active_parent_by_child)
    for connection_id, connection in document.connections.items():
        _require_id(connection_id, ConnectionId, "connections key")
        if connection_id != connection.connection_id:
            raise SemanticError("canonical.identity_mismatch", "Connection map key mismatches ConnectionId")
        if not connection.tombstoned:
            _validate_connection(document, connection)
    for thing in document.things.values():
        if thing.tombstoned:
            for connection in document.connections.values():
                if not connection.tombstoned and (connection.source.thing_id == thing.thing_id or connection.target.thing_id == thing.thing_id):
                    raise SemanticError("canonical.dangling_connection", "Tombstoned Thing has an incident live Connection")
    for definition_id, definition in document.definitions.items():
        _require_id(definition_id, DefinitionId, "definitions key")
        if definition_id != definition.definition_id:
            raise SemanticError("canonical.identity_mismatch", "Definition map key mismatches DefinitionId")
        _validate_definition(definition)
    seen_concrete: dict[ThingId, ThingId] = {}
    for root_id, instance in document.instances.items():
        _require_id(root_id, ThingId, "instances key")
        if root_id != instance.root_thing_id:
            raise SemanticError("canonical.identity_mismatch", "Instance map key mismatches root ThingId")
        definition = document.definitions.get(instance.definition_id)
        if definition is None:
            raise SemanticError("canonical.unknown_definition", f"Instance refers to unknown DefinitionId {instance.definition_id}")
        if instance.base_revision != definition.revision:
            raise SemanticError("canonical.definition_revision_mismatch", "Instance base revision does not match active Definition revision")
        if set(instance.thing_by_element) != set(definition.elements):
            raise SemanticError("canonical.invalid_instance", "Instance element mapping must exactly cover active Definition elements")
        if instance.thing_by_element[definition.root_element_id] != root_id:
            raise SemanticError("canonical.invalid_instance", "Definition root must map to instance root Thing")
        values = list(instance.thing_by_element.values())
        if len(values) != len(set(values)):
            raise SemanticError("canonical.duplicate_identity", "One instance cannot map multiple elements to the same ThingId")
        for element_id, thing_id in instance.thing_by_element.items():
            _require_id(element_id, ElementId, "instance element key")
            _live_thing(document, thing_id)
            prior_root = seen_concrete.get(thing_id)
            if prior_root is not None and prior_root != root_id:
                raise SemanticError("canonical.invalid_instance", f"Thing {thing_id} belongs to multiple Definition instances")
            seen_concrete[thing_id] = root_id
        for element_id, values in instance.state_overrides.items():
            if element_id not in definition.elements:
                raise SemanticError("canonical.invalid_instance", f"State override targets unknown element {element_id}")
            _validate_authored_value(values, "instance state override")
        for element_id, parent_element in instance.parent_overrides.items():
            if element_id not in definition.elements:
                raise SemanticError("canonical.invalid_instance", f"Parent override targets unknown element {element_id}")
            if parent_element is not None and parent_element not in definition.elements:
                raise SemanticError("canonical.invalid_instance", f"Parent override names unknown parent element {parent_element}")
        for local_thing_id in instance.local_thing_ids:
            _live_thing(document, local_thing_id)
        root = _live_thing(document, root_id)
        for public_port_id, exposure in definition.exposures.items():
            if public_port_id not in root.ports:
                raise SemanticError("canonical.invalid_instance", f"Instance root is missing public Definition PortId {public_port_id}")
            internal = definition.elements[exposure.element_id].ports[exposure.element_port_id]
            public = root.ports[public_port_id]
            if public.kind is not internal.kind or public.direction is not internal.direction:
                raise SemanticError("canonical.invalid_instance", f"Public port {public_port_id} is incompatible with Definition exposure target")


def empty_document(project_id: ProjectId, revision_id: ProjectRevisionId) -> CanonicalDocument:
    document = CanonicalDocument(project_id=project_id, project_revision_id=revision_id)
    validate_document(document)
    return document


def _require_id(value: Any, expected_type: type[SemanticId], label: str) -> None:
    if not isinstance(value, expected_type):
        raise SemanticError("canonical.identity_role_mismatch", f"{label} must be {expected_type.role}, got {type(value).__name__}")


def _validate_authored_value(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise SemanticError("canonical.invalid_authored_state", f"{path}: authored map keys must be strings")
            if _normalise_field_name(key) in _FORBIDDEN_DURABLE_FIELD_NAMES:
                raise SemanticError("canonical.forbidden_transient_identity", f"{path}: transient/host field {key!r} is forbidden in durable authored state")
            _validate_authored_value(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_authored_value(child, f"{path}[{index}]")
        return
    if isinstance(value, set):
        raise SemanticError("canonical.invalid_authored_state", f"{path}: unordered sets are not canonical authored values")
    if isinstance(value, SemanticId):
        return
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return
    raise SemanticError("canonical.invalid_authored_state", f"{path}: unsupported durable authored value type {type(value).__name__}")


def _validate_thing(thing: ThingRecord) -> None:
    _require_id(thing.thing_id, ThingId, "ThingRecord.thing_id")
    if not isinstance(thing.label, str):
        raise SemanticError("canonical.invalid_thing", "Thing label must be a string")
    _validate_authored_value(thing.authored_state, f"Thing {thing.thing_id} authored_state")
    for port_id, port in thing.ports.items():
        _require_id(port_id, PortId, "Thing port key")
        if port_id != port.port_id:
            raise SemanticError("canonical.identity_mismatch", "Port map key mismatches PortId")
    for attachment_id, attachment in thing.behaviours.items():
        _require_id(attachment_id, BehaviourAttachmentId, "Behaviour map key")
        if attachment_id != attachment.attachment_id:
            raise SemanticError("canonical.identity_mismatch", "Behaviour map key mismatches attachment ID")
        _validate_authored_value(attachment.authored_config, f"Behaviour {attachment_id} authored_config")


def _live_thing(document: CanonicalDocument, thing_id: ThingId) -> ThingRecord:
    _require_id(thing_id, ThingId, "Thing reference")
    thing = document.things.get(thing_id)
    if thing is None:
        if thing_id in document.known_unloaded_things:
            raise SemanticError("canonical.target_unloaded", f"Thing is known but not loaded: {thing_id}")
        raise SemanticError("canonical.unknown_thing", f"Unknown ThingId {thing_id}")
    if thing.tombstoned:
        raise SemanticError("canonical.target_tombstoned", f"Thing is tombstoned: {thing_id}")
    return thing


def _validate_connection(document: CanonicalDocument, connection: ConnectionRecord) -> None:
    if connection.tombstoned:
        return
    _require_id(connection.connection_id, ConnectionId, "ConnectionRecord.connection_id")
    source = _live_thing(document, connection.source.thing_id)
    target = _live_thing(document, connection.target.thing_id)
    _require_id(connection.source.port_id, PortId, "Connection source PortId")
    _require_id(connection.target.port_id, PortId, "Connection target PortId")
    source_port = source.ports.get(connection.source.port_id)
    target_port = target.ports.get(connection.target.port_id)
    if source_port is None or target_port is None:
        raise SemanticError("canonical.invalid_endpoint", f"Connection {connection.connection_id} references a missing PortId")
    allowed = (
        source_port.kind is PortKind.EVENT and source_port.direction is PortDirection.OUT
        and target_port.kind is PortKind.COMMAND and target_port.direction is PortDirection.IN
    ) or (
        source_port.kind is PortKind.VALUE
        and source_port.direction in {PortDirection.READ, PortDirection.READWRITE, PortDirection.OUT}
        and target_port.kind is PortKind.VALUE
        and target_port.direction in {PortDirection.WRITE, PortDirection.READWRITE, PortDirection.IN}
    )
    if not allowed:
        raise SemanticError("canonical.incompatible_ports", f"Connection {connection.connection_id} joins incompatible ports")


def _validate_definition(definition: DefinitionRecord) -> None:
    _require_id(definition.definition_id, DefinitionId, "DefinitionRecord.definition_id")
    if not isinstance(definition.revision, int) or definition.revision < 1:
        raise SemanticError("canonical.invalid_definition_revision", "Definition revision must be >= 1")
    if definition.root_element_id not in definition.elements:
        raise SemanticError("canonical.invalid_definition", "Definition root element does not exist")
    parent_by_child: dict[ElementId, ElementId] = {}
    for element_id, element in definition.elements.items():
        _require_id(element_id, ElementId, "Definition element key")
        if element_id != element.element_id:
            raise SemanticError("canonical.identity_mismatch", "Definition element map key mismatches ElementId")
        _validate_authored_value(element.authored_state, f"Definition {definition.definition_id} element {element_id}")
        for port_id, port in element.ports.items():
            _require_id(port_id, PortId, "Definition element port key")
            if port_id != port.port_id:
                raise SemanticError("canonical.identity_mismatch", "Definition port map key mismatches PortId")
        if element.parent_element_id is not None:
            if element.parent_element_id not in definition.elements:
                raise SemanticError("canonical.invalid_definition", f"Definition element {element_id} has unknown parent")
            parent_by_child[element_id] = element.parent_element_id
    if definition.elements[definition.root_element_id].parent_element_id is not None:
        raise SemanticError("canonical.invalid_definition", "Definition root cannot have a parent")
    _validate_element_containment_acyclic(parent_by_child)
    for public_port_id, exposure in definition.exposures.items():
        _require_id(public_port_id, PortId, "Definition exposure key")
        if exposure.public_port_id != public_port_id:
            raise SemanticError("canonical.identity_mismatch", "Exposure map key mismatches public PortId")
        element = definition.elements.get(exposure.element_id)
        if element is None or exposure.element_port_id not in element.ports:
            raise SemanticError("canonical.invalid_definition", f"Definition exposure {public_port_id} targets a missing element/port")


def _active_parent_map(document: CanonicalDocument) -> dict[ThingId, ThingId]:
    result: dict[ThingId, ThingId] = {}
    for relation in document.relationships.values():
        if relation.tombstoned or relation.kind is not RelationshipKind.CONTAINS:
            continue
        if relation.target in result:
            raise SemanticError("canonical.multiple_parents", f"Thing has multiple parents: {relation.target}")
        result[relation.target] = relation.source
    return result


def _active_containment_for_child(document: CanonicalDocument, child_id: ThingId) -> RelationshipRecord | None:
    matches = [relation for relation in document.relationships.values() if not relation.tombstoned and relation.kind is RelationshipKind.CONTAINS and relation.target == child_id]
    if len(matches) > 1:
        raise SemanticError("canonical.multiple_parents", f"Thing has multiple parents: {child_id}")
    return matches[0] if matches else None


def _descendant_subgraph(document: CanonicalDocument, root_id: ThingId) -> set[ThingId]:
    _live_thing(document, root_id)
    selected = {root_id}
    changed = True
    while changed:
        changed = False
        for relation in document.relationships.values():
            if relation.tombstoned or relation.kind is not RelationshipKind.CONTAINS:
                continue
            if relation.source in selected and relation.target not in selected:
                selected.add(relation.target)
                changed = True
    return selected


def _validate_containment_acyclic(parent_by_child: Mapping[ThingId, ThingId]) -> None:
    for child in parent_by_child:
        seen: set[ThingId] = set()
        current = child
        while current in parent_by_child:
            if current in seen:
                raise SemanticError("canonical.containment_cycle", "Containment graph contains a cycle")
            seen.add(current)
            current = parent_by_child[current]


def _validate_element_containment_acyclic(parent_by_child: Mapping[ElementId, ElementId]) -> None:
    for child in parent_by_child:
        seen: set[ElementId] = set()
        current = child
        while current in parent_by_child:
            if current in seen:
                raise SemanticError("canonical.definition_cycle", "Definition containment graph contains a cycle")
            seen.add(current)
            current = parent_by_child[current]


def _has_live_noncontainment_relationship(document: CanonicalDocument, thing_id: ThingId) -> bool:
    return any(not relation.tombstoned and relation.kind is not RelationshipKind.CONTAINS and (relation.source == thing_id or relation.target == thing_id) for relation in document.relationships.values())


def _has_live_connection(document: CanonicalDocument, thing_id: ThingId) -> bool:
    return any(not connection.tombstoned and (connection.source.thing_id == thing_id or connection.target.thing_id == thing_id) for connection in document.connections.values())
