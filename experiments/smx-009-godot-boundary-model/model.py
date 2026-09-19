from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


class BoundaryError(ValueError):
    """Base error for a rejected substrate-boundary operation."""


class CanonicalLeak(BoundaryError):
    pass


class UnsupportedRequiredFeature(BoundaryError):
    pass


class IntegrityError(BoundaryError):
    pass


class CapabilityDenied(BoundaryError):
    pass


class DuplicateIdentity(BoundaryError):
    pass


FORBIDDEN_CANONICAL_KEYS = frozenset(
    {
        "node_path",
        "rid",
        "resource_uid",
        "godot_node",
        "engine_handle",
        "scene_tree_path",
        "peer_id",
        "os_permission_handle",
    }
)

FORBIDDEN_ORDINARY_CONTENT_FEATURES = frozenset(
    {
        "host.gdscript",
        "host.csharp",
        "host.gdextension",
        "host.javascript_bridge",
        "host.eval",
        "host.raw_filesystem",
        "host.raw_socket",
        "host.executable_pck",
        "host.engine_reflection",
    }
)


@dataclass(frozen=True)
class TargetProfile:
    name: str
    features: frozenset[str]
    transports: frozenset[str]
    presentation_enabled: bool
    audio_enabled: bool


WEB = TargetProfile(
    name="web",
    features=frozenset(
        {
            "render.compatibility",
            "audio.web_sample",
            "storage.user_persistent",
            "network.http",
            "network.websocket_client",
            "network.webrtc",
            "input.pointer_keyboard_gamepad",
        }
    ),
    transports=frozenset({"websocket_client", "webrtc"}),
    presentation_enabled=True,
    audio_enabled=True,
)

NATIVE = TargetProfile(
    name="native",
    features=frozenset(
        {
            "render.native",
            "audio.native",
            "storage.user_persistent",
            "network.http",
            "network.websocket_client",
            "network.webrtc",
            "network.low_level",
            "input.pointer_keyboard_gamepad",
        }
    ),
    transports=frozenset({"websocket_client", "webrtc", "enet", "udp"}),
    presentation_enabled=True,
    audio_enabled=True,
)

HEADLESS = TargetProfile(
    name="headless",
    features=frozenset(
        {
            "storage.user_persistent",
            "network.http",
            "network.websocket_client",
            "network.webrtc",
            "network.low_level",
        }
    ),
    transports=frozenset({"websocket_client", "webrtc", "enet", "udp"}),
    presentation_enabled=False,
    audio_enabled=False,
)


@dataclass(frozen=True)
class AssetDescriptor:
    asset_id: str
    digest: str
    media_type: str
    role: str
    source: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThingRecord:
    thing_id: str
    state: Mapping[str, Any]
    presentation: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreationPackage:
    revision_id: str
    things: tuple[ThingRecord, ...]
    assets: tuple[AssetDescriptor, ...] = ()
    required_features: frozenset[str] = frozenset()
    optional_features: frozenset[str] = frozenset()
    network_semantics: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def canonical_projection(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "things": [
                {
                    "thing_id": thing.thing_id,
                    "state": dict(thing.state),
                    "presentation": dict(thing.presentation),
                }
                for thing in self.things
            ],
            "assets": [
                {
                    "asset_id": asset.asset_id,
                    "digest": asset.digest,
                    "media_type": asset.media_type,
                    "role": asset.role,
                    "source": dict(asset.source),
                    "provenance": dict(asset.provenance),
                }
                for asset in self.assets
            ],
            "required_features": sorted(self.required_features),
            "optional_features": sorted(self.optional_features),
            "network_semantics": dict(self.network_semantics),
            "metadata": dict(self.metadata),
        }

    def canonical_bytes(self) -> bytes:
        projection = self.canonical_projection()
        reject_godot_identity_leaks(projection)
        return json.dumps(
            projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class EphemeralBinding:
    thing_id: str
    adapter_kind: str
    handle: str
    generation: int


@dataclass
class RuntimeThing:
    thing_id: str
    state: dict[str, Any]
    bindings: list[EphemeralBinding] = field(default_factory=list)


@dataclass
class RuntimeCreation:
    revision_id: str
    canonical_digest: str
    target: TargetProfile
    things: dict[str, RuntimeThing]
    assets: dict[str, AssetDescriptor]
    network_semantics: dict[str, Any]
    metadata: dict[str, Any]
    selected_transport: str | None = None
    omitted_optional_features: set[str] = field(default_factory=set)

    def semantic_snapshot(self) -> dict[str, Any]:
        """Persist semantic state only; substrate handles are deliberately absent."""
        return {
            "revision_id": self.revision_id,
            "canonical_digest": self.canonical_digest,
            "things": {
                thing_id: {"state": dict(runtime.state)}
                for thing_id, runtime in sorted(self.things.items())
            },
            "network_semantics": dict(self.network_semantics),
        }

    def rebind(self, thing_id: str, *, adapter_kind: str = "godot_node") -> EphemeralBinding:
        runtime = self.things[thing_id]
        generation = 1 + max((binding.generation for binding in runtime.bindings), default=0)
        binding = EphemeralBinding(
            thing_id=thing_id,
            adapter_kind=adapter_kind,
            handle=f"{self.target.name}:{adapter_kind}:{thing_id}:g{generation}",
            generation=generation,
        )
        runtime.bindings = [binding]
        return binding

    def add_binding(self, thing_id: str, *, adapter_kind: str) -> EphemeralBinding:
        runtime = self.things[thing_id]
        generation = 1 + max((binding.generation for binding in runtime.bindings), default=0)
        binding = EphemeralBinding(
            thing_id=thing_id,
            adapter_kind=adapter_kind,
            handle=f"{self.target.name}:{adapter_kind}:{thing_id}:g{generation}",
            generation=generation,
        )
        runtime.bindings.append(binding)
        return binding

    def select_transport(self, transport: str) -> None:
        if transport not in self.target.transports:
            raise UnsupportedRequiredFeature(
                f"transport {transport!r} is unavailable on target {self.target.name!r}"
            )
        self.selected_transport = transport


class GenericPlayer:
    def load(
        self,
        package: CreationPackage,
        target: TargetProfile,
        *,
        asset_payloads: Mapping[str, bytes],
    ) -> RuntimeCreation:
        # Validate the complete canonical shape before any substrate object is bound.
        canonical_digest = package.digest

        thing_ids = [record.thing_id for record in package.things]
        if len(thing_ids) != len(set(thing_ids)):
            raise DuplicateIdentity("duplicate ThingId in canonical package")

        asset_ids = [descriptor.asset_id for descriptor in package.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise DuplicateIdentity("duplicate AssetId in canonical package")

        requested_features = package.required_features | package.optional_features
        forbidden = sorted(requested_features & FORBIDDEN_ORDINARY_CONTENT_FEATURES)
        if forbidden:
            raise CapabilityDenied(
                "ordinary content requested permanently forbidden host feature(s): "
                + ", ".join(forbidden)
            )

        missing = sorted(package.required_features - target.features)
        if missing:
            raise UnsupportedRequiredFeature(
                f"target {target.name!r} lacks required feature(s): " + ", ".join(missing)
            )

        verified_assets: dict[str, AssetDescriptor] = {}
        for descriptor in package.assets:
            if descriptor.asset_id not in asset_payloads:
                raise IntegrityError(f"missing exact asset payload {descriptor.asset_id!r}")
            actual = sha256(asset_payloads[descriptor.asset_id]).hexdigest()
            if actual != descriptor.digest:
                raise IntegrityError(
                    f"digest mismatch for {descriptor.asset_id!r}: expected {descriptor.digest}, got {actual}"
                )
            verified_assets[descriptor.asset_id] = descriptor

        runtime = RuntimeCreation(
            revision_id=package.revision_id,
            canonical_digest=canonical_digest,
            target=target,
            things={
                record.thing_id: RuntimeThing(record.thing_id, dict(record.state))
                for record in package.things
            },
            assets=verified_assets,
            network_semantics=dict(package.network_semantics),
            metadata=dict(package.metadata),
            omitted_optional_features=set(package.optional_features - target.features),
        )

        # Bind only after validation. A Thing is not a Node: headless Things may have zero
        # bindings and presentation-rich Things may have multiple private substrate bindings.
        if target.presentation_enabled:
            for thing_id in runtime.things:
                runtime.rebind(thing_id)
        return runtime


def reject_godot_identity_leaks(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in FORBIDDEN_CANONICAL_KEYS:
                raise CanonicalLeak(f"Godot/runtime identity key {key!r} at {path}")
            reject_godot_identity_leaks(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_godot_identity_leaks(item, path=f"{path}[{index}]")


def sha256_hex(payload: bytes) -> str:
    return sha256(payload).hexdigest()
