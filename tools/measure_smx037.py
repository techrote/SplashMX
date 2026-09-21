#!/usr/bin/env python3
"""Run the real Godot SMX-037 binding-selection campaign and emit CI evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

from export_smx037_fixture import build_fixture, validate_fixture

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "experiments" / "smx-037-godot-binding-spike"


def memory_bytes() -> int:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def godot_version(godot: str) -> str:
    result = subprocess.run([godot, "--version"], check=True, text=True, capture_output=True)
    return result.stdout.strip().splitlines()[0]


def startup_samples(godot: str, samples: int) -> list[float]:
    values: list[float] = []
    probe = PROJECT / "startup_probe.gd"
    for _ in range(samples):
        start = time.perf_counter()
        result = subprocess.run(
            [godot, "--headless", "--path", str(PROJECT), "--script", str(probe)],
            text=True,
            capture_output=True,
        )
        elapsed = time.perf_counter() - start
        if result.returncode != 0 or "SMX037_STARTUP_READY" not in result.stdout:
            raise SystemExit(
                "SMX-037 Godot startup probe failed:\n" + result.stdout + "\n" + result.stderr
            )
        values.append(elapsed)
    return values


def run_godot_campaign(godot: str, samples: int, fixture_path: Path, raw_path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            godot,
            "--headless",
            "--path",
            str(PROJECT),
            "--",
            f"--fixture={fixture_path}",
            f"--output={raw_path}",
            f"--samples={samples}",
        ],
        text=True,
        capture_output=True,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(f"SMX-037 Godot campaign failed with exit {result.returncode}")
    if not raw_path.exists():
        raise SystemExit("SMX-037 Godot campaign produced no raw evidence")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("contract") != "splashmx.smx037-godot-raw-evidence/1":
        raise SystemExit("SMX-037 raw evidence contract mismatch")
    if raw.get("selected_candidate") != "facet_sparse":
        raise SystemExit("SMX-037 raw campaign did not select facet_sparse")
    if not all(raw.get("boundary_results", {}).values()):
        raise SystemExit("SMX-037 raw boundary campaign failed")
    return raw


def metric(row: dict[str, object], name: str, unit: str) -> dict[str, object]:
    return {"name": name, "unit": unit, "statistic": "median", "value": float(row[name])}


def benchmark_record(
    *, candidate: dict[str, object], version: str, samples: int, startup_median: float
) -> dict[str, object]:
    candidate_id = str(candidate["candidate"])
    return {
        "contract": "splashmx.benchmark-evidence/1",
        "evidence_id": f"SMX-037-{candidate_id}",
        "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_profile": "headless",
        "runtime": {
            "name": "Godot SMX-037 binding spike",
            "version": version,
            "build_id": os.environ.get("GITHUB_SHA", "local-uncommitted"),
        },
        "environment": {
            "os": platform.platform(),
            "arch": platform.machine() or "unknown",
            "hardware": {
                "cpu": platform.processor() or os.environ.get("RUNNER_ARCH", "unknown"),
                "gpu": "headless-ci-no-render-performance-claim",
                "memory_bytes": memory_bytes(),
                "note": "GitHub Actions ubuntu-24.04 Godot 4.7.2 container; selection evidence, not a supported-hardware GATE-10 SLO",
            },
        },
        "workload": {
            "id": "smx037.godot-binding-selection",
            "description": "SMX-031 production-core Thing projection into alternative private Godot realization layouts with binding churn and centralized scheduler bridge",
        },
        "sample_count": samples,
        "metrics": [
            {"name": "headless_process_startup_to_exit_seconds", "unit": "seconds", "statistic": "median", "value": startup_median},
            metric(candidate, "create_usec_median", "microseconds"),
            metric(candidate, "churn_usec_median", "microseconds"),
            metric(candidate, "scheduler_usec_median", "microseconds"),
            metric(candidate, "node_delta_median", "nodes"),
            metric(candidate, "object_delta_median", "objects"),
            metric(candidate, "memory_delta_bytes_median", "bytes"),
            metric(candidate, "engine_binding_count_median", "objects"),
        ],
    }


def validate_benchmark(record: dict[str, object]) -> None:
    expected = {
        "contract", "evidence_id", "captured_at_utc", "target_profile", "runtime",
        "environment", "workload", "sample_count", "metrics",
    }
    if set(record) != expected or record["contract"] != "splashmx.benchmark-evidence/1":
        raise SystemExit("SMX-037 benchmark record drifted from benchmark-evidence/1")
    if record["target_profile"] not in {"browser", "native", "headless"}:
        raise SystemExit("SMX-037 benchmark target profile invalid")
    if not isinstance(record["sample_count"], int) or record["sample_count"] < 1:
        raise SystemExit("SMX-037 benchmark sample count invalid")
    if not record["metrics"]:
        raise SystemExit("SMX-037 benchmark contains no metrics")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", default="godot")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--output", default="artifacts/smx037-godot-binding-evidence.json")
    args = parser.parse_args()
    if args.samples < 3 or args.samples > 50:
        raise SystemExit("SMX-037 --samples must be between 3 and 50")

    fixture = build_fixture()
    validate_fixture(fixture)
    version = godot_version(args.godot)
    startup = startup_samples(args.godot, min(args.samples, 7))

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        fixture_path = tmpdir / "fixture.json"
        raw_path = tmpdir / "raw.json"
        fixture_path.write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
        raw = run_godot_campaign(args.godot, args.samples, fixture_path, raw_path)

    startup_median = statistics.median(startup)
    benchmarks = [
        benchmark_record(candidate=row, version=version, samples=args.samples, startup_median=startup_median)
        for row in raw["candidate_results"]
    ]
    for record in benchmarks:
        validate_benchmark(record)

    evidence = {
        "contract": "splashmx.smx037-godot-selection-evidence/1",
        "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": os.environ.get("GITHUB_SHA", "local-uncommitted"),
        "godot_version": version,
        "fixture_contract": fixture["contract"],
        "fixture_revision": fixture["project_revision_id"],
        "selected_candidate": raw["selected_candidate"],
        "scheduler_integration": raw["scheduler_integration"],
        "selection_rule": "all semantic/adversarial gates pass; choose facet_sparse when its private engine-binding count is no greater than node_per_thing or scene_subtree; timing is recorded but is not a universal SLO",
        "benchmarks": benchmarks,
        "candidate_results": raw["candidate_results"],
        "boundary_results": raw["boundary_results"],
        "target_profile_checks": raw["target_profile_checks"],
        "protected_asset_refs": raw["protected_asset_refs"],
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "smx037_selected": evidence["selected_candidate"],
        "godot_version": version,
        "startup_median_seconds": startup_median,
        "candidate_bindings": {row["candidate"]: row["engine_binding_count_median"] for row in raw["candidate_results"]},
    }, sort_keys=True))
    print(f"SMX-037 evidence -> {out}")


if __name__ == "__main__":
    main()
