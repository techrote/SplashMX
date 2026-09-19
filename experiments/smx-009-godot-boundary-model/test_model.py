from __future__ import annotations

import copy
import unittest

from model import (
    AssetDescriptor,
    CanonicalLeak,
    CapabilityDenied,
    CreationPackage,
    DuplicateIdentity,
    GenericPlayer,
    HEADLESS,
    IntegrityError,
    NATIVE,
    ThingRecord,
    UnsupportedRequiredFeature,
    WEB,
    reject_godot_identity_leaks,
    sha256_hex,
)


AUDIO = b"pretend-immutable-audio-bytes"
IMAGE = b"pretend-immutable-image-bytes"


def package(*, required=frozenset(), optional=frozenset({"render.compatibility"})) -> CreationPackage:
    return CreationPackage(
        revision_id="rev-demo-001",
        things=(
            ThingRecord("thing-player", {"x": 3, "health": 9}, {"asset_id": "asset-image"}),
            ThingRecord("thing-speaker", {"playing": False}, {"asset_id": "asset-audio"}),
        ),
        assets=(
            AssetDescriptor(
                "asset-image",
                sha256_hex(IMAGE),
                "image/png",
                "visual",
                source={"logical_source_id": "src-image-1"},
                provenance={"author": "fixture", "license": "CC0"},
            ),
            AssetDescriptor(
                "asset-audio",
                sha256_hex(AUDIO),
                "audio/ogg",
                "audio",
                source={"logical_source_id": "src-audio-1"},
                provenance={"author": "fixture", "license": "CC0"},
            ),
        ),
        required_features=frozenset(required),
        optional_features=frozenset(optional),
        network_semantics={"replication": "shared", "authority": "policy"},
        metadata={"title": "fixture"},
    )


PAYLOADS = {"asset-image": IMAGE, "asset-audio": AUDIO}


class GodotBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = GenericPlayer()

    def test_rebinding_never_changes_thing_identity_or_semantic_snapshot(self) -> None:
        runtime = self.player.load(package(), NATIVE, asset_payloads=PAYLOADS)
        before = runtime.semantic_snapshot()
        old = runtime.things["thing-player"].bindings[0]
        new = runtime.rebind("thing-player")
        self.assertNotEqual(old.handle, new.handle)
        self.assertEqual(new.thing_id, "thing-player")
        self.assertEqual(runtime.semantic_snapshot(), before)

    def test_same_canonical_package_loads_web_native_and_headless(self) -> None:
        spec = package()
        runtimes = [
            self.player.load(spec, target, asset_payloads=PAYLOADS)
            for target in (WEB, NATIVE, HEADLESS)
        ]
        self.assertEqual({runtime.canonical_digest for runtime in runtimes}, {spec.digest})
        self.assertEqual({runtime.revision_id for runtime in runtimes}, {spec.revision_id})
        self.assertEqual(len(runtimes[2].things["thing-player"].bindings), 0)

    def test_headless_can_omit_optional_presentation_without_rewriting_creation(self) -> None:
        spec = package(optional=frozenset({"render.compatibility", "audio.web_sample"}))
        runtime = self.player.load(spec, HEADLESS, asset_payloads=PAYLOADS)
        self.assertEqual(runtime.canonical_digest, spec.digest)
        self.assertEqual(
            runtime.omitted_optional_features,
            {"render.compatibility", "audio.web_sample"},
        )

    def test_required_presentation_fails_closed_on_headless(self) -> None:
        spec = package(required=frozenset({"render.compatibility"}))
        with self.assertRaises(UnsupportedRequiredFeature):
            self.player.load(spec, HEADLESS, asset_payloads=PAYLOADS)

    def test_web_low_level_network_requirement_fails_closed(self) -> None:
        spec = package(required=frozenset({"network.low_level"}))
        with self.assertRaises(UnsupportedRequiredFeature):
            self.player.load(spec, WEB, asset_payloads=PAYLOADS)

    def test_engine_identity_keys_are_rejected_anywhere_in_canonical_data(self) -> None:
        malicious = {"things": [{"thing_id": "x", "state": {"node_path": "/root/X"}}]}
        with self.assertRaises(CanonicalLeak):
            reject_godot_identity_leaks(malicious)

    def test_ordinary_content_cannot_request_host_escape_even_on_native(self) -> None:
        spec = package(required=frozenset({"host.gdextension"}))
        with self.assertRaises(CapabilityDenied):
            self.player.load(spec, NATIVE, asset_payloads=PAYLOADS)

    def test_optional_host_escape_request_is_not_silently_tolerated(self) -> None:
        spec = package(optional=frozenset({"host.javascript_bridge"}))
        with self.assertRaises(CapabilityDenied):
            self.player.load(spec, WEB, asset_payloads=PAYLOADS)

    def test_duplicate_thing_identity_fails_before_dict_collapse(self) -> None:
        base = package()
        duplicate = CreationPackage(
            revision_id=base.revision_id,
            things=(base.things[0], base.things[0]),
            assets=base.assets,
            required_features=base.required_features,
            optional_features=base.optional_features,
            network_semantics=base.network_semantics,
            metadata=base.metadata,
        )
        with self.assertRaises(DuplicateIdentity):
            self.player.load(duplicate, NATIVE, asset_payloads=PAYLOADS)

    def test_duplicate_asset_identity_fails_before_descriptor_overwrite(self) -> None:
        base = package()
        duplicate = CreationPackage(
            revision_id=base.revision_id,
            things=base.things,
            assets=(base.assets[0], base.assets[0]),
            required_features=base.required_features,
            optional_features=base.optional_features,
            network_semantics=base.network_semantics,
            metadata=base.metadata,
        )
        with self.assertRaises(DuplicateIdentity):
            self.player.load(duplicate, NATIVE, asset_payloads=PAYLOADS)

    def test_asset_integrity_is_checked_before_any_runtime_is_published(self) -> None:
        spec = package()
        tampered = dict(PAYLOADS)
        tampered["asset-audio"] = b"tampered"
        with self.assertRaises(IntegrityError):
            self.player.load(spec, NATIVE, asset_payloads=tampered)

    def test_audio_source_and_provenance_survive_headless_projection(self) -> None:
        runtime = self.player.load(package(), HEADLESS, asset_payloads=PAYLOADS)
        audio = runtime.assets["asset-audio"]
        self.assertEqual(audio.role, "audio")
        self.assertEqual(audio.source["logical_source_id"], "src-audio-1")
        self.assertEqual(audio.provenance["license"], "CC0")
        self.assertFalse(runtime.target.audio_enabled)

    def test_semantic_snapshot_never_serializes_substrate_bindings(self) -> None:
        runtime = self.player.load(package(), NATIVE, asset_payloads=PAYLOADS)
        runtime.add_binding("thing-player", adapter_kind="godot_audio_emitter")
        snapshot = runtime.semantic_snapshot()
        flattened = repr(snapshot)
        self.assertNotIn("godot_node", flattened)
        self.assertNotIn("godot_audio_emitter", flattened)
        self.assertNotIn("native:", flattened)

    def test_transport_selection_does_not_mutate_network_semantics(self) -> None:
        runtime = self.player.load(package(), NATIVE, asset_payloads=PAYLOADS)
        semantics = copy.deepcopy(runtime.network_semantics)
        runtime.select_transport("websocket_client")
        runtime.select_transport("enet")
        self.assertEqual(runtime.network_semantics, semantics)

    def test_target_specific_transport_is_explicit_and_rejected_when_unavailable(self) -> None:
        runtime = self.player.load(package(), WEB, asset_payloads=PAYLOADS)
        runtime.select_transport("webrtc")
        with self.assertRaises(UnsupportedRequiredFeature):
            runtime.select_transport("udp")

    def test_one_thing_can_have_multiple_private_bindings_without_becoming_multiple_things(self) -> None:
        runtime = self.player.load(package(), NATIVE, asset_payloads=PAYLOADS)
        runtime.add_binding("thing-player", adapter_kind="godot_audio_emitter")
        bindings = runtime.things["thing-player"].bindings
        self.assertEqual({binding.thing_id for binding in bindings}, {"thing-player"})
        self.assertEqual(len(bindings), 2)


if __name__ == "__main__":
    unittest.main()
