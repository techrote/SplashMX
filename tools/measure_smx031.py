#!/usr/bin/env python3
"""Emit SMX-031 production-core integration evidence using the SMX-021 schema."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PRODUCTION = ROOT / "tests" / "production"
for path in (SRC, PRODUCTION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from smx031_harness import complete_vertical_flow  # noqa: E402


def memory_bytes() -> int:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def run_sample() -> tuple[float, int, int]:
    with tempfile.TemporaryDirectory() as tmp:
        start = time.perf_counter()
        result = complete_vertical_flow(tmp)
        elapsed = time.perf_counter() - start
        db_bytes = Path(result["project_db"]).stat().st_size
        world_bytes = Path(result["world_save"]).stat().st_size
        if result["before_stop"] != {"clicks": 1, "score": 1, "count": 1}:
            raise SystemExit("SMX-031 measurement vertical produced unexpected semantic result")
        return elapsed, db_bytes, world_bytes


def build_evidence(samples: int) -> dict[str, object]:
    rows = [run_sample() for _ in range(samples)]
    latencies = [row[0] for row in rows]
    db_sizes = [row[1] for row in rows]
    world_sizes = [row[2] for row in rows]
    return {
        "contract": "splashmx.benchmark-evidence/1",
        "evidence_id": "SMX-031-production-core-vertical",
        "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_profile": "headless",
        "runtime": {
            "name": "CPython production-core integration gate",
            "version": platform.python_version(),
            "build_id": os.environ.get("GITHUB_SHA", "local-uncommitted"),
        },
        "environment": {
            "os": platform.platform(),
            "arch": platform.machine() or "unknown",
            "hardware": {
                "cpu": platform.processor() or os.environ.get("RUNNER_ARCH", "unknown"),
                "gpu": "not-applicable-non-ui-gate",
                "memory_bytes": memory_bytes(),
                "note": "SMX-031 conformance/footprint evidence; not a GATE-10 supported-target claim",
            },
        },
        "workload": {
            "id": "smx031.local-core-vertical",
            "description": "Production create/reuse/behave/connect/play/stop/save/reload vertical over canonical, execution, persistence and lifecycle modules",
        },
        "sample_count": samples,
        "metrics": [
            {
                "name": "vertical_flow_seconds",
                "unit": "seconds",
                "statistic": "mean",
                "value": statistics.fmean(latencies),
            },
            {
                "name": "project_store_bytes",
                "unit": "bytes",
                "statistic": "mean",
                "value": statistics.fmean(db_sizes),
            },
            {
                "name": "worldsave_bytes",
                "unit": "bytes",
                "statistic": "mean",
                "value": statistics.fmean(world_sizes),
            },
        ],
    }


def validate_shape(evidence: dict[str, object]) -> None:
    required = {
        "contract", "evidence_id", "captured_at_utc", "target_profile", "runtime",
        "environment", "workload", "sample_count", "metrics",
    }
    if set(evidence) != required:
        raise SystemExit("SMX-031 evidence root does not match benchmark-evidence/1 shape")
    if evidence["contract"] != "splashmx.benchmark-evidence/1":
        raise SystemExit("SMX-031 evidence contract drift")
    if evidence["target_profile"] not in {"browser", "native", "headless"}:
        raise SystemExit("SMX-031 evidence target profile is invalid")
    if not isinstance(evidence["sample_count"], int) or evidence["sample_count"] < 1:
        raise SystemExit("SMX-031 evidence sample_count is invalid")
    if not isinstance(evidence["metrics"], list) or not evidence["metrics"]:
        raise SystemExit("SMX-031 evidence requires metrics")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/smx031-core-evidence.json")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    if args.samples < 1 or args.samples > 100:
        raise SystemExit("--samples must be between 1 and 100")
    evidence = build_evidence(args.samples)
    validate_shape(evidence)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SMX-031 evidence: {args.samples} samples -> {output}")


if __name__ == "__main__":
    main()
