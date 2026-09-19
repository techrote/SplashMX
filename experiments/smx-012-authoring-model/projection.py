from __future__ import annotations
from dataclasses import dataclass

LEVELS = ("canvas", "interactive", "reuse", "together", "advanced")

@dataclass(frozen=True)
class Surface:
    name: str
    purpose: str
    semantics: tuple[str, ...]

SURFACES = {
    "Stage": Surface("Stage", "arrange and inspect Things", ("thing", "containment", "presentation")),
    "Timeline": Surface("Timeline", "author values and cues over time", ("timeline", "value", "event")),
    "Behaviours": Surface("Behaviours", "attach reusable intent to a Thing", ("behaviour", "attachment")),
    "Rules": Surface("Rules", "edit readable trigger-condition-action projections", ("behaviour", "connection", "port")),
    "Connections": Surface("Connections", "connect stable Thing interfaces", ("connection", "port")),
    "Components": Surface("Components", "reuse ordinary authored structure", ("definition", "instance", "overlay")),
    "Together": Surface("Together", "configure runtime play relationships", ("control", "authority", "replication", "relevance")),
    "People": Surface("People", "show collaboration presence, history and conflicts", ("collaboration", "presence", "conflict")),
    "Publish": Surface("Publish", "validate a creation for a generic player", ("revision", "target_profile", "capability")),
    "Inspect": Surface("Inspect", "reveal stable SplashMX semantic details", ("identity", "port", "authority", "replication", "diagnostic")),
}
LEVEL_SURFACES = {
    "canvas": ("Stage", "Publish"),
    "interactive": ("Stage", "Timeline", "Behaviours", "Rules", "Publish"),
    "reuse": ("Stage", "Timeline", "Behaviours", "Rules", "Connections", "Components", "Publish"),
    "together": ("Stage", "Timeline", "Behaviours", "Rules", "Connections", "Components", "Together", "People", "Publish"),
    "advanced": tuple(SURFACES),
}

def visible_text(level: str) -> tuple[str, ...]:
    if level not in LEVEL_SURFACES:
        raise ValueError("unknown disclosure level")
    labels = list(LEVEL_SURFACES[level]) + ["Thing", "Behaviour", "Connection"]
    if level == "together":
        labels += ["Local only", "One per player", "Shared", "Authority controlled", "People", "History", "Conflicts"]
    if level == "advanced":
        labels += ["Control", "Authority", "Replication", "Relevance", "Stable ID", "Ports", "Capabilities"]
    return tuple(labels)

def semantic_union(level: str) -> frozenset[str]:
    return frozenset(kind for name in LEVEL_SURFACES[level] for kind in SURFACES[name].semantics)
