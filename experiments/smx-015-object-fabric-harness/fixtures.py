from __future__ import annotations

from model import ArtifactStore, BehaviorSpec, FabricWorld

def asset_bundle(*, revision: str = "asset-rev-1", digest: str = "sha256:source") -> dict:
    return {
        "asset_id": "asset:voice",
        "revision_id": revision,
        "digest": digest,
        "source_identity": "source:master-wav",
        "source_metadata": {"filename": "voice.wav", "rate": 48000, "channels": 2},
        "media_semantics": {"kind": "audio", "loop": False, "gain_db": -2.0},
        "provenance": {"author": "alice", "capture": "original"},
        "licence": "CC-BY-4.0",
        "derivation": ["import:decode-only"],
    }

def make_world() -> tuple[FabricWorld, ArtifactStore, dict[tuple[str, int], BehaviorSpec]]:
    store = ArtifactStore()
    store.add("artifact:move-v1", b"move-v1")
    store.add("artifact:move-v2", b"move-v2", revision="2")
    store.add("artifact:move-v3", b"move-v3", revision="3")
    store.add("artifact:audio", b"audio-decoder")
    catalog = {
        ("move", 1): BehaviorSpec("move", 1, ("speed",), ("tick", "resume"), "artifact:move-v1"),
        ("move", 2): BehaviorSpec("move", 2, ("speed",), ("tick", "continue"), "artifact:move-v2"),
        ("move", 3): BehaviorSpec("move", 3, ("velocity", "mode"), ("tick", "continue"), "artifact:move-v3"),
    }
    return FabricWorld(artifact_store=store, behavior_catalog=catalog), store, catalog
