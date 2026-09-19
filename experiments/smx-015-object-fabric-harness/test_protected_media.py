from __future__ import annotations

from copy import deepcopy
import unittest

from fixtures import asset_bundle, make_world
from model import CompatibilityError, Thing

class ProtectedMediaBoundaryTests(unittest.TestCase):
    def test_partial_asset_revision_is_rejected_without_mutating_old_revision(self) -> None:
        world, _, _ = make_world(); world.add_thing(Thing("speaker")); world.replace_asset("speaker", asset_bundle())
        old = deepcopy(world.things["speaker"].assets["asset:voice"])
        partial = asset_bundle(revision="asset-rev-2", digest="sha256:new"); del partial["provenance"]
        with self.assertRaises(CompatibilityError): world.replace_asset("speaker", partial)
        self.assertEqual(world.things["speaker"].assets["asset:voice"], old)

    def test_competing_asset_revision_replaces_as_whole_bundle_not_field_merge(self) -> None:
        world, _, _ = make_world(); world.add_thing(Thing("speaker")); world.replace_asset("speaker", asset_bundle())
        replacement = asset_bundle(revision="asset-rev-2", digest="sha256:new")
        replacement["source_identity"] = "source:new-master-wav"
        replacement["provenance"] = {"author": "bob", "capture": "resampled-from-owned-source"}
        replacement["media_semantics"] = {"kind": "audio", "loop": True, "gain_db": -4.0}
        world.replace_asset("speaker", replacement); got = world.things["speaker"].assets["asset:voice"]
        self.assertEqual(got.revision_id, "asset-rev-2")
        self.assertEqual(got.source_identity, "source:new-master-wav")
        self.assertEqual(got.provenance["author"], "bob")
        self.assertTrue(got.media_semantics["loop"])

    def test_streaming_residency_does_not_mutate_protected_asset_bundle(self) -> None:
        world, _, _ = make_world(); world.add_thing(Thing("speaker")); world.replace_asset("speaker", asset_bundle())
        before = deepcopy(world.things["speaker"].assets["asset:voice"])
        world.set_context("speaker", decoded_audio="target-private:AudioStream#55")
        world.unload(["speaker"]); world.load(["speaker"])
        self.assertEqual(world.things["speaker"].assets["asset:voice"], before)
        self.assertNotIn("speaker", world.context)
