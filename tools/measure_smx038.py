#!/usr/bin/env python3
"""Measure SMX-038 semantic save/load preparation on production modules."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PRODUCTION = ROOT / "tests" / "production"
for path in (SRC, PRODUCTION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from smx031_harness import (  # noqa: E402
    AUDIO,
    DEFAULT_BUDGETS,
    WORKER,
    WORKER_SLOT,
    CoreFixture,
)
from splashmx.runtime.lifecycle import (  # noqa: E402
    deserialize_world_save,
    restore_world_save,
    serialize_world_save,
)


def _usec(start: int) -> int:
    return max(0, (perf_counter_ns() - start) // 1000)


def measure(samples: int, commit_sha: str) -> dict[str, object]:
    if samples < 1 or samples > 50:
        raise ValueError("samples must be 1..50")
    startup_rows = []
    save_rows = []
    load_rows = []
    roundtrip_rows = []
    fingerprints = []
    sizes = []
    final_probe = None
    protected_ref = None

    for index in range(samples):
        started = perf_counter_ns()
        fixture = CoreFixture.create()
        startup_rows.append(_usec(started))
        fixture.play()

        save_started = perf_counter_ns()
        snapshot = fixture.world.snapshot(f"smx038-measure-{index}")
        encoded = serialize_world_save(snapshot)
        save_rows.append(_usec(save_started))

        load_started = perf_counter_ns()
        decoded = deserialize_world_save(encoded)
        restored = restore_world_save(
            decoded,
            fixture.project.document,
            fixture.programs,
            budgets=DEFAULT_BUDGETS,
        ).world
        load_rows.append(_usec(load_started))
        roundtrip_rows.append(save_rows[-1] + load_rows[-1])

        probe = {
            "worker_score": restored.runtime.states[WORKER].public_state["score"],
            "worker_private_count": restored.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"],
            "reference_state": restored.reference_state(WORKER).value,
        }
        expected = {
            "worker_score": fixture.world.runtime.states[WORKER].public_state["score"],
            "worker_private_count": fixture.world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"],
            "reference_state": fixture.world.reference_state(WORKER).value,
        }
        if probe != expected:
            raise RuntimeError(f"SMX-038 WorldSave round-trip changed semantic state: {probe} != {expected}")
        final_probe = probe
        fingerprints.append("sha256:" + sha256(encoded).hexdigest())
        sizes.append(len(encoded))

        asset = fixture.project.assets[AUDIO]
        current_ref = {
            "asset_id": str(asset.asset_id),
            "revision_digest": asset.revision_digest,
            "source_digest": asset.source_digest,
        }
        if protected_ref is None:
            protected_ref = current_ref
        elif protected_ref != current_ref:
            raise RuntimeError("SMX-038 protected Asset reference drifted across samples")

    return {
        "contract": "splashmx.smx038-semantic-performance-evidence/1",
        "commit_sha": commit_sha,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "samples": samples,
        "production_fixture": "SMX-031",
        "startup_usec_median": median(startup_rows),
        "worldsave_serialize_usec_median": median(save_rows),
        "worldsave_restore_usec_median": median(load_rows),
        "worldsave_roundtrip_usec_median": median(roundtrip_rows),
        "worldsave_bytes_median": median(sizes),
        "worldsave_fingerprint_stable": len(set(fingerprints)) == 1,
        "restored_semantic_probe": final_probe,
        "protected_asset_ref": protected_ref,
        "measurement_class": (
            "named CI semantic save/load evidence; not a universal hardware performance SLO"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--commit-sha", default="unknown")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    evidence = measure(args.samples, args.commit_sha)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
