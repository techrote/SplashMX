"""SMX-032 production authoring projection over the SplashMX canonical core.

This module deliberately does not define a browser-side shadow document model.  Every
ordinary author operation is translated into SMX-023 semantic transactions, while
Rule and Behaviour projections lower to the SMX-026 constrained IR.  Selection and
other editor-only state live in :class:`EditorState` and never enter the canonical
project revision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import math
import re
from typing import Any, Mapping, Sequence

from splashmx.canonical.core import (
    AddBehaviourAttachment,
    AddConnection,
    AddPort,
    AddThing,
    AssetId,
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    CanonicalDocument,
    ConnectionEndpoint,
    ConnectionId,
    ConnectionRecord,
    DefinitionId,
    ElementId,
    InstantiateDefinition,
    PortDirection,
    PortId,
    PortKind,
    PortRecord,
    ProjectId,
    ProjectRevisionId,
    PromoteGroup,
    RemoveBehaviourAttachment,
    ReplaceBehaviourAttachment,
    RelationId,
    RelationshipKind,
    SemanticError,
    SemanticTransaction,
    SetAuthoredState,
    SetContainment,
    ThingId,
    ThingRecord,
    apply_transaction,
    empty_document,
)
from splashmx.canonical.serialization import (
    CanonicalProjectRevision,
    ProtectedAssetRevision,
    SerializationError,
)
from splashmx.execution.ir import IRProgram, compile_rule


_FORBIDDEN_AUTHOR_VOCABULARY = (
    "nodepath",
    "scenetree",
    "resourceuid",
    "godot rpc",
    "package manager",
    "build pipeline",
    "export preset",
)
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9._:-]+")
_VISUAL_FILL = re.compile(r"#[0-9A-Fa-f]{6}")
_VISUAL_SHAPES = {"rectangle", "ellipse"}
POINTER_CLICK_EVENT = "pointer_click"
VISUAL_FILL_RULE_KIND = "visual-fill"
_VISUAL_DEFAULTS = {
    "x": 64.0,
    "y": 64.0,
    "width": 160.0,
    "height": 100.0,
    "rotation": 0.0,
    "shape": "rectangle",
    "fill": "#5b7cfa",
}


def _visual_number(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise AuthoringError("authoring.invalid_visual", f"{label} must be a finite number.")
    result = float(value)
    if result < minimum or result > maximum:
        raise AuthoringError("authoring.invalid_visual", f"{label} is outside the supported Stage range.")
    return result


def _normalise_visual_state(value: Mapping[str, Any], *, base: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AuthoringError("authoring.invalid_visual", "Visual properties must be an object.")
    allowed = set(_VISUAL_DEFAULTS)
    unknown = sorted(set(map(str, value)) - allowed)
    if unknown:
        raise AuthoringError("authoring.invalid_visual", "Unsupported visual properties: " + ", ".join(unknown))
    merged = dict(_VISUAL_DEFAULTS)
    if isinstance(base, Mapping):
        merged.update({key: base[key] for key in allowed if key in base})
    merged.update(dict(value))
    shape = merged["shape"]
    fill = merged["fill"]
    if shape not in _VISUAL_SHAPES:
        raise AuthoringError("authoring.invalid_visual", "Choose rectangle or ellipse.")
    if not isinstance(fill, str) or _VISUAL_FILL.fullmatch(fill) is None:
        raise AuthoringError("authoring.invalid_visual", "Fill must be a six-digit colour such as #5b7cfa.")
    return {
        "x": _visual_number(merged["x"], "X position", minimum=-10000, maximum=10000),
        "y": _visual_number(merged["y"], "Y position", minimum=-10000, maximum=10000),
        "width": _visual_number(merged["width"], "Width", minimum=12, maximum=4096),
        "height": _visual_number(merged["height"], "Height", minimum=12, maximum=4096),
        "rotation": _visual_number(merged["rotation"], "Rotation", minimum=-3600, maximum=3600),
        "shape": shape,
        "fill": fill.lower(),
    }


class AuthoringError(ValueError):
    """Typed author-facing failure without leaking substrate/toolchain terminology."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class EditorState:
    """Process-local editor state; never serialized into authored project semantics."""

    selection: set[ThingId] = field(default_factory=set)
    inspect_open: bool = False


class AuthoringSession:
    """One browser editor session backed directly by production semantic modules."""

    def __init__(self, project: CanonicalProjectRevision, *, revision_counter: int = 0):
        self.project = project
        self.editor = EditorState()
        self.programs: dict[str, IRProgram] = {}
        self._revision_counter = revision_counter
        self._identity_counter = 0

    @classmethod
    def blank(cls, project_id: str = "local-project") -> "AuthoringSession":
        document = empty_document(ProjectId(project_id), ProjectRevisionId("author-000000"))
        return cls(CanonicalProjectRevision(document, {}))

    @property
    def document(self) -> CanonicalDocument:
        return self.project.document

    def _next_revision(self) -> ProjectRevisionId:
        self._revision_counter += 1
        return ProjectRevisionId(f"author-{self._revision_counter:06d}")

    def allocate_id(self, prefix: str) -> str:
        self._identity_counter += 1
        clean = _SAFE_TOKEN.sub("-", prefix).strip("-._:") or "item"
        clean = clean[:72]
        return f"{clean}-{self._identity_counter:06d}"

    def _commit(self, *operations: Any, assets: Mapping[AssetId, ProtectedAssetRevision] | None = None) -> None:
        try:
            candidate_document = apply_transaction(
                self.project.document,
                SemanticTransaction(self._next_revision(), tuple(operations)),
            )
            candidate_assets = dict(self.project.assets if assets is None else assets)
            candidate = CanonicalProjectRevision(candidate_document, candidate_assets)
        except (SemanticError, SerializationError) as exc:
            code = getattr(exc, "code", "authoring.invalid_edit")
            raise AuthoringError(code, str(exc)) from exc
        self.project = candidate

    def create_thing(
        self,
        *,
        label: str,
        thing_id: str | None = None,
        authored_state: Mapping[str, Any] | None = None,
    ) -> ThingId:
        identifier = ThingId(thing_id or self.allocate_id("thing"))
        state = dict(authored_state or {})
        if "visual" in state:
            state["visual"] = _normalise_visual_state(state["visual"])
        self._commit(AddThing(ThingRecord(identifier, str(label), state)))
        return identifier

    def add_port(
        self,
        thing_id: str | ThingId,
        *,
        port_id: str,
        name: str,
        kind: str,
        direction: str,
    ) -> PortId:
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        try:
            record = PortRecord(PortId(port_id), str(name), PortKind(kind), PortDirection(direction))
        except ValueError as exc:
            raise AuthoringError("authoring.invalid_port", "Choose a supported port kind and direction.") from exc
        self._commit(AddPort(tid, record))
        return record.port_id

    def group_things(
        self,
        member_ids: Sequence[str | ThingId],
        *,
        label: str = "Group",
        group_id: str | None = None,
    ) -> ThingId:
        members = [value if isinstance(value, ThingId) else ThingId(value) for value in member_ids]
        if not members or len(set(members)) != len(members):
            raise AuthoringError("authoring.invalid_group", "Select one or more distinct Things to group.")
        group = ThingId(group_id or self.allocate_id("group"))
        operations: list[Any] = [AddThing(ThingRecord(group, label, {}))]
        for member in members:
            relation = RelationId(self.allocate_id("contains"))
            operations.append(SetContainment(member, group, relation))
        self._commit(*operations)
        self.editor.selection = {group}
        return group

    def _descendants(self, root: ThingId) -> set[ThingId]:
        live = self.document.things.get(root)
        if live is None or live.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        children: dict[ThingId, list[ThingId]] = {}
        for relation in self.document.relationships.values():
            if relation.tombstoned or relation.kind is not RelationshipKind.CONTAINS:
                continue
            children.setdefault(relation.source, []).append(relation.target)
        result: set[ThingId] = set()
        pending = [root]
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            pending.extend(children.get(current, ()))
        return result

    def make_reusable(self, root_id: str | ThingId, *, definition_id: str | None = None) -> DefinitionId:
        root = root_id if isinstance(root_id, ThingId) else ThingId(root_id)
        selected = sorted(self._descendants(root), key=str)
        definition = DefinitionId(definition_id or self.allocate_id("definition"))
        mapping = {thing_id: ElementId(f"element-{index:04d}") for index, thing_id in enumerate(selected)}
        self._commit(PromoteGroup(root, definition, mapping, {}))
        return definition

    def instantiate_reusable(self, definition_id: str | DefinitionId) -> ThingId:
        definition = definition_id if isinstance(definition_id, DefinitionId) else DefinitionId(definition_id)
        record = self.document.definitions.get(definition)
        if record is None:
            raise AuthoringError("authoring.unknown_reusable", "That reusable part is not available.")
        thing_by_element = {
            element_id: ThingId(self.allocate_id("thing")) for element_id in record.elements
        }
        relations = {
            element_id: RelationId(self.allocate_id("contains"))
            for element_id in record.elements
            if element_id != record.root_element_id
        }
        self._commit(InstantiateDefinition(definition, thing_by_element, relations))
        return thing_by_element[record.root_element_id]

    def attach_rule(
        self,
        thing_id: str | ThingId,
        *,
        attachment_id: str | None = None,
        event: str = "activate",
        actions: Sequence[Mapping[str, Any]] | None = None,
    ) -> BehaviourAttachmentId:
        return self._attach_projection(
            thing_id,
            projection="Rule",
            attachment_id=attachment_id,
            event=event,
            actions=actions or ({"action": "emit", "event": "activated", "payload": True},),
        )

    def attach_behaviour(
        self,
        thing_id: str | ThingId,
        *,
        attachment_id: str | None = None,
        event: str = "activate",
        actions: Sequence[Mapping[str, Any]] | None = None,
    ) -> BehaviourAttachmentId:
        return self._attach_projection(
            thing_id,
            projection="Behaviour",
            attachment_id=attachment_id,
            event=event,
            actions=actions or ({"action": "emit", "event": "activated", "payload": True},),
        )

    def _attach_projection(
        self,
        thing_id: str | ThingId,
        *,
        projection: str,
        attachment_id: str | None,
        event: str,
        actions: Sequence[Mapping[str, Any]],
        authored_metadata: Mapping[str, Any] | None = None,
    ) -> BehaviourAttachmentId:
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        attachment = BehaviourAttachmentId(attachment_id or self.allocate_id("behaviour"))
        revision = self.allocate_id("ir") + ":1"
        plain_actions = [dict(action) for action in actions]
        try:
            program = compile_rule(
                f"author-{projection.lower()}",
                str(event),
                plain_actions,
                behaviour_revision=revision,
            )
        except Exception as exc:
            raise AuthoringError("authoring.invalid_behaviour", "This Rule or Behaviour cannot be represented safely.") from exc
        config: dict[str, Any] = {
            "projection": projection,
            "event": str(event),
            "actions": plain_actions,
        }
        if authored_metadata:
            config.update(dict(authored_metadata))
        record = BehaviourAttachmentRecord(attachment, revision, config)
        self._commit(AddBehaviourAttachment(tid, record))
        self.programs[revision] = program
        return attachment

    def attach_visual_rule(
        self,
        thing_id: str | ThingId,
        *,
        fill: str,
        attachment_id: str | None = None,
    ) -> BehaviourAttachmentId:
        """Attach the first beginner visual Rule through the common constrained IR."""
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        thing = self.document.things.get(tid)
        if thing is None or thing.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        if any(
            behaviour.authored_config.get("projection") == "Rule"
            and behaviour.authored_config.get("author_kind") == VISUAL_FILL_RULE_KIND
            for behaviour in thing.behaviours.values()
        ):
            raise AuthoringError(
                "authoring.rule_exists",
                "This Thing already has a click colour Rule. Edit the existing Rule below.",
            )
        visual = thing.authored_state.get("visual")
        if not isinstance(visual, Mapping):
            raise AuthoringError("authoring.rule_requires_visual", "Choose a visible Thing for this Rule.")
        target_visual = _normalise_visual_state({"fill": fill}, base=visual)
        return self._attach_projection(
            tid,
            projection="Rule",
            attachment_id=attachment_id,
            event=POINTER_CLICK_EVENT,
            actions=({"action": "set_public", "key": "visual.fill", "value": target_visual["fill"]},),
            authored_metadata={"author_kind": VISUAL_FILL_RULE_KIND},
        )

    def update_visual_rule(
        self,
        thing_id: str | ThingId,
        attachment_id: str | BehaviourAttachmentId,
        *,
        fill: str,
    ) -> BehaviourAttachmentId:
        """Edit a beginner visual Rule while retaining its stable attachment identity."""
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        aid = attachment_id if isinstance(attachment_id, BehaviourAttachmentId) else BehaviourAttachmentId(attachment_id)
        thing = self.document.things.get(tid)
        if thing is None or thing.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        prior = thing.behaviours.get(aid)
        if prior is None:
            raise AuthoringError("authoring.unknown_rule", "That Rule is no longer attached to this Thing.")
        config = dict(prior.authored_config)
        if config.get("projection") != "Rule" or config.get("author_kind") != VISUAL_FILL_RULE_KIND:
            raise AuthoringError("authoring.unsupported_rule_edit", "This advanced Behaviour cannot be edited with the beginner Rule controls.")
        visual = thing.authored_state.get("visual")
        if not isinstance(visual, Mapping):
            raise AuthoringError("authoring.rule_requires_visual", "Choose a visible Thing for this Rule.")
        target_visual = _normalise_visual_state({"fill": fill}, base=visual)
        actions = [{"action": "set_public", "key": "visual.fill", "value": target_visual["fill"]}]
        revision = self.allocate_id("ir") + ":1"
        try:
            program = compile_rule("author-rule", POINTER_CLICK_EVENT, actions, behaviour_revision=revision)
        except Exception as exc:
            raise AuthoringError("authoring.invalid_behaviour", "This Rule cannot be represented safely.") from exc
        replacement = BehaviourAttachmentRecord(
            aid,
            revision,
            {
                "projection": "Rule",
                "event": POINTER_CLICK_EVENT,
                "actions": actions,
                "author_kind": VISUAL_FILL_RULE_KIND,
            },
        )
        self._commit(ReplaceBehaviourAttachment(tid, replacement))
        self.programs.pop(prior.behaviour_revision, None)
        self.programs[revision] = program
        return aid

    def remove_rule(
        self,
        thing_id: str | ThingId,
        attachment_id: str | BehaviourAttachmentId,
    ) -> None:
        """Remove a Rule through a canonical semantic transaction."""
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        aid = attachment_id if isinstance(attachment_id, BehaviourAttachmentId) else BehaviourAttachmentId(attachment_id)
        thing = self.document.things.get(tid)
        if thing is None or thing.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        prior = thing.behaviours.get(aid)
        if prior is None or prior.authored_config.get("projection") != "Rule":
            raise AuthoringError("authoring.unknown_rule", "That Rule is no longer attached to this Thing.")
        self._commit(RemoveBehaviourAttachment(tid, aid))
        self.programs.pop(prior.behaviour_revision, None)

    def connect(
        self,
        *,
        source_thing_id: str | ThingId,
        source_port_id: str | PortId,
        target_thing_id: str | ThingId,
        target_port_id: str | PortId,
        connection_id: str | None = None,
    ) -> ConnectionId:
        source_thing = source_thing_id if isinstance(source_thing_id, ThingId) else ThingId(source_thing_id)
        source_port = source_port_id if isinstance(source_port_id, PortId) else PortId(source_port_id)
        target_thing = target_thing_id if isinstance(target_thing_id, ThingId) else ThingId(target_thing_id)
        target_port = target_port_id if isinstance(target_port_id, PortId) else PortId(target_port_id)
        connection = ConnectionId(connection_id or self.allocate_id("connection"))
        self._commit(
            AddConnection(
                ConnectionRecord(
                    connection,
                    ConnectionEndpoint(source_thing, source_port),
                    ConnectionEndpoint(target_thing, target_port),
                )
            )
        )
        return connection

    def add_timeline_track(
        self,
        thing_id: str | ThingId,
        *,
        property_name: str,
        keyframes: Sequence[Mapping[str, Any]],
        track_id: str | None = None,
    ) -> str:
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        thing = self.document.things.get(tid)
        if thing is None or thing.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        if not property_name or any(word in property_name.lower() for word in ("nodepath", "resourceuid")):
            raise AuthoringError("authoring.invalid_timeline_target", "Timeline tracks must target an authored Thing property.")
        identifier = track_id or self.allocate_id("track")
        state = dict(thing.authored_state)
        tracks = [dict(row) for row in state.get("timeline_tracks", [])]
        if any(row.get("track_id") == identifier for row in tracks):
            raise AuthoringError("authoring.duplicate_timeline_track", "That Timeline track already exists.")
        clean_keyframes = [dict(row) for row in keyframes]
        tracks.append(
            {
                "track_id": identifier,
                "target_thing_id": str(tid),
                "property": str(property_name),
                "keyframes": clean_keyframes,
            }
        )
        state["timeline_tracks"] = tracks
        self._commit(SetAuthoredState(tid, state))
        return identifier

    def update_visual_state(
        self,
        thing_id: str | ThingId,
        *,
        visual: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Transactionally update the author-facing visual projection of one Thing."""
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        thing = self.document.things.get(tid)
        if thing is None or thing.tombstoned:
            raise AuthoringError("authoring.unknown_thing", "That Thing is no longer available to edit.")
        state = dict(thing.authored_state)
        previous = state.get("visual")
        state["visual"] = _normalise_visual_state(
            visual,
            base=previous if isinstance(previous, Mapping) else None,
        )
        self._commit(SetAuthoredState(tid, state))
        return dict(state["visual"])

    def import_asset_thing(
        self,
        *,
        content: bytes,
        source_name: str,
        media_type: str,
        media_semantics: Mapping[str, Any],
        provenance: Mapping[str, Any],
        licence_attribution: Mapping[str, Any],
        derivation_lineage: Sequence[Mapping[str, Any]],
        asset_id: str | None = None,
        thing_id: str | None = None,
        label: str | None = None,
    ) -> tuple[ThingId, AssetId]:
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise AuthoringError("authoring.empty_import", "Choose a non-empty source file to import.")
        required_maps = (media_semantics, provenance, licence_attribution)
        if any(not isinstance(value, Mapping) or not value for value in required_maps):
            raise AuthoringError(
                "authoring.incomplete_protected_asset",
                "Imported media needs complete media, provenance and licence information.",
            )
        if not derivation_lineage:
            raise AuthoringError(
                "authoring.incomplete_protected_asset",
                "Imported media needs explicit derivation lineage.",
            )
        aid = AssetId(asset_id or self.allocate_id("asset"))
        if aid in self.project.assets:
            raise AuthoringError("authoring.asset_exists", "That Asset already has an immutable revision in this project.")
        digest = "sha256:" + sha256(bytes(content)).hexdigest()
        try:
            asset = ProtectedAssetRevision.create(
                aid,
                source_digest=digest,
                source_identity={"name": str(source_name), "origin": "author-import"},
                source_metadata={"media_type": str(media_type), "byte_length": len(content)},
                media_semantics=dict(media_semantics),
                provenance=dict(provenance),
                licence_attribution=dict(licence_attribution),
                derivation_lineage=tuple(dict(row) for row in derivation_lineage),
            )
        except SerializationError as exc:
            raise AuthoringError(exc.code, str(exc)) from exc
        tid = ThingId(thing_id or self.allocate_id("thing"))
        state = {"asset_id": str(aid), "asset_revision_digest": asset.revision_digest}
        assets = dict(self.project.assets)
        assets[aid] = asset
        self._commit(AddThing(ThingRecord(tid, label or source_name, state)), assets=assets)
        return tid, aid

    def select(self, thing_ids: Sequence[str | ThingId]) -> None:
        selected = {value if isinstance(value, ThingId) else ThingId(value) for value in thing_ids}
        for thing_id in selected:
            thing = self.document.things.get(thing_id)
            if thing is None or thing.tombstoned:
                raise AuthoringError("authoring.unknown_thing", "Selection contains a Thing that is no longer available.")
        self.editor.selection = selected

    def set_inspect_open(self, value: bool) -> None:
        self.editor.inspect_open = bool(value)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-ready projection, with transient editor state explicitly separate."""
        parent_by_child: dict[ThingId, ThingId] = {}
        for relation in self.document.relationships.values():
            if not relation.tombstoned and relation.kind is RelationshipKind.CONTAINS:
                parent_by_child[relation.target] = relation.source
        things = []
        for thing_id in sorted(self.document.things, key=str):
            thing = self.document.things[thing_id]
            if thing.tombstoned:
                continue
            things.append(
                {
                    "thing_id": str(thing_id),
                    "label": thing.label,
                    "authored_state": _json_value(dict(thing.authored_state)),
                    "parent_thing_id": None if thing_id not in parent_by_child else str(parent_by_child[thing_id]),
                    "ports": [
                        {
                            "port_id": str(port.port_id),
                            "name": port.name,
                            "kind": port.kind.value,
                            "direction": port.direction.value,
                        }
                        for port in sorted(thing.ports.values(), key=lambda row: str(row.port_id))
                    ],
                    "behaviours": [
                        {
                            "attachment_id": str(behaviour.attachment_id),
                            "behaviour_revision": behaviour.behaviour_revision,
                            "authored_config": _json_value(dict(behaviour.authored_config)),
                        }
                        for behaviour in sorted(thing.behaviours.values(), key=lambda row: str(row.attachment_id))
                    ],
                }
            )
        definitions = [
            {
                "definition_id": str(definition.definition_id),
                "revision": definition.revision,
                "root_thing_id": str(root_id),
                "element_count": len(definition.elements),
            }
            for root_id, instance in sorted(self.document.instances.items(), key=lambda row: str(row[0]))
            for definition in (self.document.definitions[instance.definition_id],)
        ]
        connections = [
            {
                "connection_id": str(connection.connection_id),
                "source": {"thing_id": str(connection.source.thing_id), "port_id": str(connection.source.port_id)},
                "target": {"thing_id": str(connection.target.thing_id), "port_id": str(connection.target.port_id)},
            }
            for connection in sorted(self.document.connections.values(), key=lambda row: str(row.connection_id))
            if not connection.tombstoned
        ]
        assets = [
            {
                "asset_id": str(asset.asset_id),
                "revision_digest": asset.revision_digest,
                "source_digest": asset.source_digest,
                "source_identity": _json_value(dict(asset.source_identity)),
                "source_metadata": _json_value(dict(asset.source_metadata)),
                "media_semantics": _json_value(dict(asset.media_semantics)),
                "provenance": _json_value(dict(asset.provenance)),
                "licence_attribution": _json_value(dict(asset.licence_attribution)),
                "derivation_lineage": _json_value(list(asset.derivation_lineage)),
            }
            for asset in sorted(self.project.assets.values(), key=lambda row: str(row.asset_id))
        ]
        return {
            "canonical": {
                "project_id": str(self.document.project_id),
                "project_revision_id": str(self.document.project_revision_id),
                "things": things,
                "definitions": definitions,
                "connections": connections,
                "assets": assets,
            },
            "editor": {
                "selection": sorted(map(str, self.editor.selection)),
                "inspect_open": self.editor.inspect_open,
            },
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(child) for child in value]
    if isinstance(value, (ThingId, AssetId, PortId, BehaviourAttachmentId, DefinitionId, ConnectionId, ElementId, RelationId)):
        return str(value)
    if isinstance(value, bytes):
        return {"byte_length": len(value)}
    return value


def assert_author_surface_vocabulary(text: str) -> None:
    """Fail a production UI contract if ordinary surface copy leaks substrate jargon."""
    lowered = text.lower()
    leaked = [term for term in _FORBIDDEN_AUTHOR_VOCABULARY if term in lowered]
    if leaked:
        raise AuthoringError(
            "authoring.substrate_vocabulary_leak",
            "Ordinary authoring copy contains implementation terminology: " + ", ".join(leaked),
        )
