#!/usr/bin/env python3
"""Export the SMX-038 production Godot target fixture from the SMX-031 core."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PRODUCTION = ROOT / "tests" / "production"
TOOLS = ROOT / "tools"
for path in (SRC, PRODUCTION, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from export_smx037_fixture import build_fixture as build_selection_fixture  # noqa: E402
from smx031_harness import CoreFixture  # noqa: E402
from splashmx.canonical.core import AssetId, ThingId  # noqa: E402
from splashmx.runtime.godot import (  # noqa: E402
    BROWSER_PROFILE,
    HEADLESS_PROFILE,
    NATIVE_PROFILE,
    ProtectedAssetRef,
    RuntimeProjection,
    ThingProjection,
    prepare_profile,
)
from splashmx.runtime.lifecycle import serialize_world_save  # noqa: E402

FORBIDDEN = {
    "NodePath", "RID", "ResourceUID", "resource_path", "DOM_node_identity",
    "database_row_id", "cache_key", "url", "transport_peer_id",
    "connection_handle", "socket_id", "session_id", "process_handle",
}


def build_fixture() -> dict[str, object]:
    selected = build_selection_fixture()
    core = CoreFixture.create()
    core.play()
    snapshot = core.world.snapshot("smx038-profile-probe")
    world_bytes = serialize_world_save(snapshot)

    things = tuple(
        ThingProjection(
            ThingId(str(row["thing_id"])),
            tuple(str(value) for value in row["facets"]),
            int(row["author_order"]),
        )
        for row in selected["things"]
    )
    assets = tuple(
        ProtectedAssetRef(
            AssetId(str(row["asset_id"])),
            str(row["revision_digest"]),
        )
        for row in selected["protected_asset_refs"]
    )
    runtime_projection = RuntimeProjection(
        things=things,
        protected_assets=assets,
        required_features=frozenset({"physics_2d"}),
        optional_features=frozenset({"render_2d", "input", "audio_basic"}),
    )
    prepared = {
        profile.name.value: prepare_profile(runtime_projection, profile)
        for profile in (NATIVE_PROFILE, BROWSER_PROFILE, HEADLESS_PROFILE)
    }
    profiles = {
        name: {"available": sorted(selected["target_profiles"][name]["available"])}
        for name in ("native", "browser", "headless")
    }
    return {
        "contract": "splashmx.godot-runtime-fixture/1",
        "project_id": selected["project_id"],
        "project_revision_id": selected["project_revision_id"],
        "things": selected["things"],
        "scheduler_events": selected["scheduler_events"],
        "protected_asset_refs": selected["protected_asset_refs"],
        "required_features": ["physics_2d"],
        "optional_features": ["render_2d", "input", "audio_basic"],
        "profiles": profiles,
        "prepared_profile_summary": {
            name: {
                "degraded_optional": list(row.degraded_optional_features),
                "bound_thing_count": len(row.things),
            }
            for name, row in prepared.items()
        },
        "churn_thing_id": "worker",
        "input_thing_id": "button",
        "worldsave_fingerprint": "sha256:" + sha256(world_bytes).hexdigest(),
        "worldsave_bytes": len(world_bytes),
        "worldsave_semantic_probe": {
            "worker_score": core.world.runtime.states[ThingId("worker")].public_state["score"],
            "button_clicks": core.world.runtime.states[ThingId("button")].public_state["clicks"],
        },
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def validate_fixture(fixture: dict[str, object]) -> None:
    if fixture.get("contract") != "splashmx.godot-runtime-fixture/1":
        raise RuntimeError("SMX-038 fixture contract mismatch")
    leaked = set(_walk_keys(fixture)) & FORBIDDEN
    if leaked:
        raise RuntimeError(f"SMX-038 fixture leaked transient identity fields: {sorted(leaked)}")
    ids = [row["thing_id"] for row in fixture["things"]]
    if len(ids) != len(set(ids)) or "worker" not in ids or "button" not in ids:
        raise RuntimeError("SMX-038 fixture Thing projection is incomplete or duplicated")
    refs = fixture["protected_asset_refs"]
    if len(refs) != 1 or refs[0]["asset_id"] != "protected-audio":
        raise RuntimeError("SMX-038 fixture lost protected Asset reference")
    if not str(fixture["worldsave_fingerprint"]).startswith("sha256:"):
        raise RuntimeError("SMX-038 fixture lacks exact WorldSave semantic fingerprint")
    if fixture["profiles"]["headless"]["available"] != ["physics_2d"]:
        raise RuntimeError("SMX-038 headless profile must omit optional presentation/audio/input")
    if fixture["required_features"] != ["physics_2d"]:
        raise RuntimeError("SMX-038 fixture required feature contract drifted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fixture = build_fixture()
    validate_fixture(fixture)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SMX-038 runtime fixture -> {path}")


if __name__ == "__main__":
    main()
