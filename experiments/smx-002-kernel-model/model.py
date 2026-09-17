"""Disposable SMX-002 semantic model.

This is a falsification harness, not production SplashMX architecture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any


@dataclass(frozen=True)
class Port:
    name: str
    kind: str  # command | event | value
    direction: str  # in | out | read | write | readwrite


@dataclass
class Facet:
    facet_id: str
    role: str
    implementation: str
    config: dict[str, Any] = field(default_factory=dict)
    private_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class Thing:
    thing_id: str
    label: str
    authored_state: dict[str, Any] = field(default_factory=dict)
    live_state: dict[str, Any] = field(default_factory=dict)
    facets: dict[str, Facet] = field(default_factory=dict)
    ports: dict[str, Port] = field(default_factory=dict)

    def semantic_snapshot(self) -> dict[str, Any]:
        """Return intrinsic semantic data only, intentionally excluding context."""
        return {
            "thing_id": self.thing_id,
            "label": self.label,
            "authored_state": deepcopy(self.authored_state),
            "live_state": deepcopy(self.live_state),
            "facets": deepcopy(self.facets),
            "ports": deepcopy(self.ports),
        }


@dataclass(frozen=True)
class Relation:
    relation_id: str
    kind: str
    source: str
    target: str
    scope: str = "authored"  # authored | runtime | persistent-world
    source_port: str | None = None
    target_port: str | None = None


@dataclass
class RuntimeContext:
    capability_grants: dict[tuple[str, str], bool] = field(default_factory=dict)
    runtime_handles: dict[str, str] = field(default_factory=dict)

    def grant(self, thing_id: str, capability: str, allowed: bool) -> None:
        self.capability_grants[(thing_id, capability)] = allowed

    def is_granted(self, thing_id: str, capability: str) -> bool:
        return self.capability_grants.get((thing_id, capability), False)


class Fabric:
    """Tiny explicit Thing/relation graph used only by SMX-002 tests."""

    def __init__(self) -> None:
        self.things: dict[str, Thing] = {}
        self.relations: dict[str, Relation] = {}
        self.context = RuntimeContext()

    def add_thing(self, thing: Thing) -> None:
        if thing.thing_id in self.things:
            raise ValueError(f"duplicate ThingId: {thing.thing_id}")
        self.things[thing.thing_id] = thing

    def add_relation(self, relation: Relation) -> None:
        if relation.relation_id in self.relations:
            raise ValueError(f"duplicate relation id: {relation.relation_id}")
        self.relations[relation.relation_id] = relation

    def relations_for(self, thing_id: str, kind: str | None = None) -> list[Relation]:
        values = [
            relation
            for relation in self.relations.values()
            if relation.source == thing_id or relation.target == thing_id
        ]
        if kind is not None:
            values = [relation for relation in values if relation.kind == kind]
        return sorted(values, key=lambda relation: relation.relation_id)

    def reparent(self, child_id: str, new_parent_id: str) -> None:
        """Mutate containment only; no unrelated semantic relationship is touched."""
        stale = [
            relation_id
            for relation_id, relation in self.relations.items()
            if relation.kind == "contains" and relation.target == child_id
        ]
        for relation_id in stale:
            del self.relations[relation_id]
        self.add_relation(
            Relation(
                relation_id=f"contains:{new_parent_id}:{child_id}",
                kind="contains",
                source=new_parent_id,
                target=child_id,
                scope="authored",
            )
        )

    def replace_facet(self, thing_id: str, facet_id: str, replacement: Facet) -> None:
        if replacement.facet_id != facet_id:
            raise ValueError("replacement facet must preserve attachment identity")
        self.things[thing_id].facets[facet_id] = replacement

    def connect(self, relation_id: str, source_id: str, source_port: str, target_id: str, target_port: str) -> None:
        source = self.things[source_id].ports[source_port]
        target = self.things[target_id].ports[target_port]
        allowed = (
            source.kind == "event" and source.direction == "out" and target.kind == "command" and target.direction == "in"
        ) or (
            source.kind == "value"
            and source.direction in {"read", "readwrite", "out"}
            and target.kind == "value"
            and target.direction in {"write", "readwrite", "in"}
        )
        if not allowed:
            raise ValueError(f"incompatible port connection: {source} -> {target}")
        self.add_relation(
            Relation(
                relation_id=relation_id,
                kind="connects",
                source=source_id,
                target=target_id,
                source_port=source_port,
                target_port=target_port,
            )
        )
