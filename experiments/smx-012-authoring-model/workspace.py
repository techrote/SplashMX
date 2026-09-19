from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib, json
from typing import Any, Iterable, Mapping

class AuthoringValidationError(ValueError): pass
class ProtectedAssetError(AuthoringValidationError): pass

PROTECTED_ASSET_KEYS = frozenset({"digest", "source", "audio", "provenance"})
PRESETS = {
    "local_only": {"spawn_scope":"one_creation","control":"local","authority":"local","replication":"none","relevance":"local"},
    "one_per_player": {"spawn_scope":"per_principal","control":"owning_principal","authority":"topology_policy","replication":"state_and_events","relevance":"participants"},
    "shared": {"spawn_scope":"one_creation","control":"declared_controllers","authority":"topology_policy","replication":"state_and_events","relevance":"participants"},
    "authority_controlled": {"spawn_scope":"one_creation","control":"intent_only","authority":"authoritative_runtime","replication":"authoritative_state","relevance":"policy"},
}

def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    if set(value) != PROTECTED_ASSET_KEYS:
        raise ProtectedAssetError("asset revision requires digest/source/audio/provenance")
    if not isinstance(value.get("digest"), str) or not value["digest"]:
        raise ProtectedAssetError("digest required")
    if any(not isinstance(value.get(key), Mapping) for key in ("source", "audio", "provenance")):
        raise ProtectedAssetError("metadata objects required")
    return deepcopy(dict(value))

@dataclass
class Workspace:
    canonical: dict[str, Any] = field(default_factory=lambda: {"things":{},"definitions":{},"connections":{},"timelines":{},"assets":{}})
    transient: dict[str, Any] = field(default_factory=lambda: {"presence":{},"play_session":None,"selection":None})
    collaboration: dict[str, Any] = field(default_factory=lambda: {"history":[],"conflicts":{}})

    def digest(self) -> str:
        return hashlib.sha256(_canon(self.canonical).encode()).hexdigest()
    def snapshot(self) -> dict[str, Any]:
        return json.loads(_canon(self.canonical))
    def thing(self, thing_id: str) -> dict[str, Any]:
        if thing_id not in self.canonical["things"]:
            raise AuthoringValidationError(f"unknown Thing {thing_id}")
        return self.canonical["things"][thing_id]
    def create(self, thing_id: str, label: str, kind: str = "visual") -> None:
        if thing_id in self.canonical["things"]:
            raise AuthoringValidationError("duplicate ThingId")
        self.canonical["things"][thing_id] = {"label":label,"kind":kind,"parent":None,"ports":{},"behaviours":{},"definition":None,"overlays":{},"network":deepcopy(PRESETS["local_only"])}
    def group(self, group_id: str, members: Iterable[str], label: str) -> None:
        members = tuple(members)
        if not members:
            raise AuthoringValidationError("empty group")
        self.create(group_id, label, "group")
        for thing_id in members:
            self.thing(thing_id)["parent"] = group_id
    def reparent(self, thing_id: str, parent: str | None) -> None:
        thing = self.thing(thing_id)
        before = deepcopy({key:thing[key] for key in ("behaviours","network","definition","overlays")})
        if parent is not None:
            self.thing(parent)
        thing["parent"] = parent
        if before != {key:thing[key] for key in before}:
            raise AssertionError("containment mutated unrelated semantics")
    def behaviour(self, thing_id: str, attachment_id: str, behaviour_id: str, ir_target: str = "smx-ir") -> None:
        if ir_target != "smx-ir":
            raise AuthoringValidationError("one accepted IR target")
        self.thing(thing_id)["behaviours"][attachment_id] = {"behaviour_id":behaviour_id,"ir_target":ir_target}
    def rule(self, thing_id: str, attachment_id: str, when: str, do: str) -> None:
        self.behaviour(thing_id, attachment_id, "rule-projection")
        self.thing(thing_id)["behaviours"][attachment_id]["rule"] = {"when":when,"do":do}
    def port(self, thing_id: str, port_id: str, direction: str, kind: str) -> None:
        if direction not in {"in","out"}:
            raise AuthoringValidationError("bad direction")
        self.thing(thing_id)["ports"][port_id] = {"direction":direction,"kind":kind}
    def connect(self, connection_id: str, source: tuple[str,str], target: tuple[str,str]) -> None:
        source_thing, target_thing = self.thing(source[0]), self.thing(target[0])
        if source[1] not in source_thing["ports"] or target[1] not in target_thing["ports"]:
            raise AuthoringValidationError("missing port")
        if source_thing["ports"][source[1]]["direction"] != "out" or target_thing["ports"][target[1]]["direction"] != "in":
            raise AuthoringValidationError("direction mismatch")
        self.canonical["connections"][connection_id] = {"source":list(source),"target":list(target)}
    def animate(self, thing_id: str, prop: str, keys: list[tuple[float,Any]]) -> None:
        self.thing(thing_id)
        if not keys:
            raise AuthoringValidationError("empty track")
        self.canonical["timelines"][f"track:{thing_id}:{prop}"] = {"thing":thing_id,"property":prop,"keys":deepcopy(keys)}
    def reusable(self, group_id: str, definition_id: str) -> None:
        group = self.thing(group_id)
        if group["kind"] != "group":
            raise AuthoringValidationError("reuse promotion starts from ordinary group")
        members = sorted(key for key,value in self.canonical["things"].items() if value.get("parent") == group_id)
        self.canonical["definitions"][definition_id] = {"elements":members,"public_ports":deepcopy(group["ports"])}
        group["definition"] = definition_id
    def overlay(self, thing_id: str, locus: str, value: Any) -> None:
        thing = self.thing(thing_id)
        if not thing["definition"]:
            raise AuthoringValidationError("not reusable")
        thing["overlays"][locus] = deepcopy(value)
    def preset(self, thing_id: str, name: str) -> None:
        if name not in PRESETS:
            raise AuthoringValidationError("unknown preset")
        self.thing(thing_id)["network"] = deepcopy(PRESETS[name])
    def advanced_network(self, thing_id: str, declaration: Mapping[str,Any]) -> None:
        if set(declaration) != set(PRESETS["shared"]):
            raise AuthoringValidationError("advanced view edits same semantic fields")
        self.thing(thing_id)["network"] = deepcopy(dict(declaration))
