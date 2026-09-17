"""Disposable SMX-003 composition/definition research model.

This is intentionally not a production schema or runtime implementation. It exists
only to exercise the semantic invariants documented by SMX-003.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Thing:
    thing_id: str
    state: dict[str, Any] = field(default_factory=dict)
    facets: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)


@dataclass
class ConcreteGraph:
    things: dict[str, Thing]
    parent_by_child: dict[str, str] = field(default_factory=dict)
    controller_by_thing: dict[str, str] = field(default_factory=dict)
    authority_by_thing: dict[str, str] = field(default_factory=dict)
    persistence_by_thing: dict[str, str] = field(default_factory=dict)
    replication_by_thing: dict[str, str] = field(default_factory=dict)


@dataclass
class DefinitionElement:
    element_id: str
    label: str
    state: dict[str, Any] = field(default_factory=dict)
    facets: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)
    parent_element: Optional[str] = None


@dataclass
class Definition:
    definition_id: str
    revision: int
    root_element_id: str
    elements: dict[str, DefinitionElement]
    exposures: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class LocalElement:
    local_id: str
    thing_id: str
    state: dict[str, Any] = field(default_factory=dict)
    facets: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)
    parent_base_element: Optional[str] = None
    parent_local_id: Optional[str] = None


@dataclass
class Instance:
    definition_id: str
    base_revision: int
    root_element_id: str
    root_thing_id: str
    thing_by_element: dict[str, str]
    state_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_overrides: dict[str, Optional[str]] = field(default_factory=dict)
    local_elements: dict[str, LocalElement] = field(default_factory=dict)
    suppressed: set[str] = field(default_factory=set)
    controller_by_thing: dict[str, str] = field(default_factory=dict)
    authority_by_thing: dict[str, str] = field(default_factory=dict)
    persistence_by_thing: dict[str, str] = field(default_factory=dict)
    replication_by_thing: dict[str, str] = field(default_factory=dict)
    connected_public_ports: set[str] = field(default_factory=set)


@dataclass
class ReconcilePlan:
    conflicts: list[str]
    new_revision: int
    new_mapping: dict[str, str]
    retired_thing_ids: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return not self.conflicts


def _descendants(graph: ConcreteGraph, root: str) -> set[str]:
    selected = {root}
    changed = True
    while changed:
        changed = False
        for child, parent in graph.parent_by_child.items():
            if parent in selected and child not in selected:
                selected.add(child)
                changed = True
    return selected


def promote_group(
    graph: ConcreteGraph,
    root_thing_id: str,
    definition_id: str,
    element_ids: dict[str, str],
) -> tuple[Definition, Instance]:
    """Promote an existing concrete subgraph without reconstructing its Things."""
    selected = _descendants(graph, root_thing_id)
    if set(element_ids) != selected:
        raise ValueError("element_ids must cover promoted subgraph exactly")

    elements: dict[str, DefinitionElement] = {}
    for thing_id in selected:
        thing = graph.things[thing_id]
        parent = graph.parent_by_child.get(thing_id)
        elements[element_ids[thing_id]] = DefinitionElement(
            element_id=element_ids[thing_id],
            label=thing_id,
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
        definition_id=definition_id,
        base_revision=1,
        root_element_id=definition.root_element_id,
        root_thing_id=root_thing_id,
        thing_by_element={element_id: thing_id for thing_id, element_id in element_ids.items()},
        controller_by_thing={k: v for k, v in graph.controller_by_thing.items() if k in selected},
        authority_by_thing={k: v for k, v in graph.authority_by_thing.items() if k in selected},
        persistence_by_thing={k: v for k, v in graph.persistence_by_thing.items() if k in selected},
        replication_by_thing={k: v for k, v in graph.replication_by_thing.items() if k in selected},
    )
    return definition, instance


def instantiate(definition: Definition, prefix: str) -> Instance:
    """Create concrete identities for all current definition elements."""
    mapping = {element_id: f"{prefix}:{element_id}" for element_id in definition.elements}
    return Instance(
        definition_id=definition.definition_id,
        base_revision=definition.revision,
        root_element_id=definition.root_element_id,
        root_thing_id=mapping[definition.root_element_id],
        thing_by_element=mapping,
    )


def effective_state(definition: Definition, instance: Instance, element_id: str) -> dict[str, Any]:
    state = deepcopy(definition.elements[element_id].state)
    state.update(instance.state_overrides.get(element_id, {}))
    return state


def effective_parent(definition: Definition, instance: Instance, element_id: str) -> Optional[str]:
    return instance.parent_overrides.get(element_id, definition.elements[element_id].parent_element)


def public_target(instance: Instance, public_port: str) -> tuple[str, str]:
    """External connections target the root/public port, never an internal path."""
    return instance.root_thing_id, public_port


def resolve_exposure(
    definition: Definition, instance: Instance, public_port: str
) -> tuple[str, str]:
    element_id, port_id = definition.exposures[public_port]
    return instance.thing_by_element[element_id], port_id


def plan_reconcile(
    old: Definition,
    new: Definition,
    instance: Instance,
    inbound_refs: frozenset[str] | set[str] = frozenset(),
) -> ReconcilePlan:
    """Plan a definition revision update without mutating the instance.

    The model is deliberately conservative: invalidated overlay targets, local
    attachment points, connected public interfaces, and referenced removals are
    explicit conflicts rather than guessed migrations.
    """
    if old.definition_id != new.definition_id or instance.definition_id != old.definition_id:
        return ReconcilePlan(
            ["definition identity mismatch"], new.revision, dict(instance.thing_by_element)
        )
    if instance.base_revision != old.revision:
        return ReconcilePlan(
            ["instance base revision mismatch"], new.revision, dict(instance.thing_by_element)
        )

    conflicts: list[str] = []
    mapping = dict(instance.thing_by_element)
    retired: set[str] = set()
    old_ids = set(old.elements)
    new_ids = set(new.elements)

    for element_id in sorted(old_ids - new_ids):
        thing_id = mapping.get(element_id)
        local_child = any(
            local.parent_base_element == element_id for local in instance.local_elements.values()
        )
        protected = (
            element_id in instance.state_overrides
            or element_id in instance.parent_overrides
            or local_child
            or (thing_id in inbound_refs if thing_id else False)
        )

        for public_port, (old_target, _) in old.exposures.items():
            if (
                old_target == element_id
                and public_port in instance.connected_public_ports
                and public_port not in new.exposures
            ):
                protected = True
                conflicts.append(f"public exposure removed while connected: {public_port}")

        if protected:
            conflicts.append(f"removed element has protected instance semantics: {element_id}")
        elif thing_id:
            retired.add(thing_id)
            mapping.pop(element_id, None)

    for element_id, overrides in instance.state_overrides.items():
        if element_id not in new.elements:
            continue
        for key, value in overrides.items():
            if key not in new.elements[element_id].state:
                conflicts.append(f"override target key removed: {element_id}.{key}")
            else:
                base_value = new.elements[element_id].state[key]
                if (
                    base_value is not None
                    and value is not None
                    and type(base_value) is not type(value)
                ):
                    conflicts.append(f"override target type changed: {element_id}.{key}")

    for element_id, parent in instance.parent_overrides.items():
        if element_id not in new.elements:
            continue
        if parent is not None and parent not in new.elements:
            conflicts.append(f"parent override target removed: {element_id}->{parent}")

    for local in instance.local_elements.values():
        if local.parent_base_element is not None and local.parent_base_element not in new.elements:
            conflicts.append(
                f"local element parent removed: {local.local_id}->{local.parent_base_element}"
            )
        if local.parent_local_id is not None and local.parent_local_id not in instance.local_elements:
            conflicts.append(f"local element parent missing: {local.local_id}->{local.parent_local_id}")

    for public_port, (element_id, port_id) in new.exposures.items():
        if element_id not in new.elements:
            conflicts.append(f"exposure target element missing: {public_port}->{element_id}")
        elif port_id not in new.elements[element_id].ports:
            conflicts.append(f"exposure target port missing: {public_port}->{element_id}.{port_id}")

    for public_port in instance.connected_public_ports:
        if public_port in old.exposures and public_port not in new.exposures:
            message = f"public exposure removed while connected: {public_port}"
            if message not in conflicts:
                conflicts.append(message)

    for element_id in sorted(new_ids - old_ids):
        mapping[element_id] = (
            f"{instance.root_thing_id}::gen::{new.revision}::{element_id}"
        )

    return ReconcilePlan(
        conflicts=sorted(set(conflicts)),
        new_revision=new.revision,
        new_mapping=mapping,
        retired_thing_ids=retired,
    )


def apply_plan(instance: Instance, plan: ReconcilePlan) -> None:
    """Atomically commit a conflict-free research reconciliation plan."""
    if not plan.ok:
        raise ValueError("cannot apply conflicting reconciliation")
    instance.base_revision = plan.new_revision
    instance.thing_by_element = dict(plan.new_mapping)
