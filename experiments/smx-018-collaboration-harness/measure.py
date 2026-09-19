from __future__ import annotations

import json
import platform
import statistics
import time

from model import Operation, Relay, Replica, Transaction, canonical_json, synchronize
from test_harness import base_state


def main() -> None:
    left = Replica("left", base_state())
    right = Replica("right", base_state())
    relay = Relay()
    left.disconnect()
    for index in range(256):
        left.author(
            Transaction(
                f"tx:{index:03d}",
                "alice",
                (Operation("set_property", "x", {"key": f"offline_{index:03d}", "value": index}),),
            )
        )
    left.reconnect()
    synchronize(relay, [left, right])
    snapshot = left.persisted_snapshot()

    timings = []
    for _ in range(15):
        start = time.perf_counter()
        left.materialize()
        timings.append((time.perf_counter() - start) * 1000.0)

    result = {
        "status": "non-production-cpython-model-measurement",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "transactions": len(relay.ids()),
        "encoded_transaction_bytes": relay.encoded_bytes,
        "persisted_collaboration_snapshot_bytes": len(canonical_json(snapshot).encode("utf-8")),
        "canonical_snapshot_bytes": len(canonical_json(snapshot["canonical"]).encode("utf-8")),
        "materialize_ms_median_15": round(statistics.median(timings), 3),
        "materialize_ms_min_15": round(min(timings), 3),
        "materialize_ms_max_15": round(max(timings), 3),
        "warning": "This is a deterministic research-model footprint/timing only, not a production CRDT/database/browser benchmark.",
    }
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
