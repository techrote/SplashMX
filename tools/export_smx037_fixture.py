#!/usr/bin/env python3
"""Export the SMX-037 Godot projection fixture from the SMX-031 production core.

The exported data is deliberately a target projection: stable SplashMX identities,
requested private adapter facets, deterministic scheduler inputs and exact protected
Asset revision references.  It contains no Godot/runtime handle and cannot redefine
canonical protected-media fields.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PRODUCTION = ROOT / "tests" / "production"
for path in (SRC, PRODUCTION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from smx031_harness import (  # noqa: E402
    AUDIO,
    BOMB,
    BUTTON,
    GROUP,
    CHILD,
    COPY_GROUP,
    COPY_CHILD,
    INVENTORY,
    WORKER,
    build_project,
)

FORBIDDEN_HANDLE_FIELDS = (
    "NodePath", "RID", "ResourceUID", "resource_path", "transport_peer_id",
    "connection_handle", "socket_id", "session_id", "process_handle",
)

# Private target realization requests for the measured spike only.  They are not a
# new canonical Thing taxonomy.  Every key is verified against the actual production
# SMX-031 document before export.
FACETS = {
    str(GROUP): ("render_2d",),
    str(CHILD): ("render_2d",),
    str(COPY_GROUP): ("render_2d",),
    str(COPY_CHILD): ("render_2d",),
    str(BUTTON): ("render_2d", "input"),
    str(WORKER): ("render_2d", "physics_2d", "audio_basic"),
    str(INVENTORY): (),
    str(BOMB): (),
}


def build_fixture() -> dict[str, object]:
    project = build_project()
    document = project.document
    actual_ids = {str(thing_id) for thing_id in document.things}
    if set(FACETS) != actual_ids:
        raise RuntimeError(
            "SMX-037 production fixture drift: target projection does not exactly cover SMX-031 Things"
        )

    things = []
    for author_order, thing_id in enumerate(sorted(actual_ids)):
        record = document.things[next(key for key in document.things if str(key) == thing_id)]
        things.append(
            {
                "thing_id": thing_id,
                "label": record.label,
                "author_order": author_order,
                "facets": list(FACETS[thing_id]),
            }
        )

    protected = project.assets[AUDIO]
    events = [
        {
            "logical_tick": 0,
            "author_order": 0,
            "sequence": 0,
            "thing_id": str(BUTTON),
            "attachment_id": "rule",
            "event": "clicked",
        },
        {
            "logical_tick": 0,
            "author_order": 1,
            "sequence": 1,
            "thing_id": str(WORKER),
            "attachment_id": "worker",
            "event": "step",
        },
        {
            "logical_tick": 1,
            "author_order": 1,
            "sequence": 2,
            "thing_id": str(WORKER),
            "attachment_id": "worker",
            "event": "continuation",
        },
    ]
    return {
        "contract": "splashmx.godot-binding-fixture/1",
        "project_id": str(document.project_id),
        "project_revision_id": str(document.project_revision_id),
        "things": things,
        "scheduler_events": events,
        "protected_asset_refs": [
            {
                "asset_id": str(protected.asset_id),
                "revision_digest": protected.revision_digest,
            }
        ],
        "target_profiles": {
            "native": {
                "available": ["render_2d", "input", "physics_2d", "audio_basic"],
                "required": ["render_2d", "physics_2d"],
                "optional": ["audio_basic", "input"],
            },
            "browser": {
                "available": ["render_2d", "input", "physics_2d", "audio_basic"],
                "required": ["render_2d", "physics_2d"],
                "optional": ["audio_basic", "input"],
            },
            "headless": {
                "available": ["physics_2d"],
                "required": ["physics_2d"],
                "optional": ["render_2d", "audio_basic", "input"],
            },
        },
        "forbidden_handle_fields": list(FORBIDDEN_HANDLE_FIELDS),
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def validate_fixture(fixture: dict[str, object]) -> None:
    leaked = set(_walk_keys(fixture)) & set(FORBIDDEN_HANDLE_FIELDS)
    if leaked:
        raise RuntimeError(f"SMX-037 fixture leaked runtime-handle fields: {sorted(leaked)}")
    thing_ids = [row["thing_id"] for row in fixture["things"]]
    if len(thing_ids) != len(set(thing_ids)):
        raise RuntimeError("SMX-037 fixture contains duplicate ThingId")
    if not any(not row["facets"] for row in fixture["things"]):
        raise RuntimeError("SMX-037 fixture requires semantic-only Things to test zero-binding layout")
    protected = fixture["protected_asset_refs"]
    if len(protected) != 1 or protected[0]["asset_id"] != str(AUDIO):
        raise RuntimeError("SMX-037 fixture lost exact protected Asset revision reference")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fixture = build_fixture()
    validate_fixture(fixture)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SMX-037 fixture -> {path}")


if __name__ == "__main__":
    main()
