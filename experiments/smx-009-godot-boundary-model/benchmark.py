from __future__ import annotations

import json
import platform
import statistics
import time

from model import EphemeralBinding, RuntimeThing


def run(count: int, rounds: int = 7) -> dict[str, object]:
    samples = []
    for _ in range(rounds):
        things = {f"thing-{i}": RuntimeThing(f"thing-{i}", {"v": i}) for i in range(count)}
        start = time.perf_counter_ns()
        for i, runtime in enumerate(things.values()):
            runtime.bindings.append(EphemeralBinding(runtime.thing_id, "godot_node", f"node:{i}", 1))
        for i in range(count):
            assert things[f"thing-{i}"].bindings[0].thing_id == f"thing-{i}"
        elapsed = time.perf_counter_ns() - start
        samples.append(elapsed / 1_000_000)
    return {
        "thing_count": count,
        "rounds": rounds,
        "median_ms": round(statistics.median(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
    }


if __name__ == "__main__":
    print(json.dumps({
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or "not-reported",
        "workload": "create private ThingId->ephemeral-binding records and verify lookup",
        "measurements": [run(n) for n in (1_000, 10_000, 100_000)],
        "warning": "Python semantic-adapter microbenchmark only; not a Godot Node/frame-cost benchmark",
    }, indent=2, sort_keys=True))
