#!/usr/bin/env python3
"""Fail closed if the SMX-044 production collaboration/People gate drifts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fixture = json.loads((ROOT / "spec/production/smx044-collaboration-gate-fixtures.json").read_text())
historical = json.loads((ROOT / "docs/research/SMX-018-COLLABORATION-HARNESS-FIXTURES.json").read_text())
doc = (ROOT / "docs/implementation/SMX-044-COLLABORATION-PEOPLE.md").read_text()
people = (ROOT / "src/splashmx/editor/people.py").read_text()
server = (ROOT / "src/splashmx/editor/browser_server.py").read_text()
html = (ROOT / "src/splashmx/editor/web/index.html").read_text()
js = (ROOT / "src/splashmx/editor/web/app.js").read_text()
workflow = (ROOT / ".github/workflows/smx044-collaboration-gate.yml").read_text()

expected = [f"CR-{index:03d}" for index in range(1, 29)]
historical_ids = [row["id"] for row in historical["fixtures"]]
production_rows = fixture["source_classes"]
production_ids = [row["id"] for row in production_rows]
assert historical_ids == expected, "historical CR-001..028 authority changed"
assert production_ids == expected, "SMX-044 must map every CR-001..028 class in order"
assert all(row.get("applicable") is True and row.get("production_evidence") for row in production_rows), "every current CR class must have production evidence"
assert fixture["delivery_dimensions"] == ["opposite-order", "duplicate", "disconnect-reconnect", "crash-restart", "explicit-frontier-compaction"]
assert fixture["planes"] == {"people": "collaboration", "together": "runtime-networking", "must_remain_distinct": True}

for anchor in (
    "People is collaboration. Together is runtime networking.",
    "R-018-01..04",
    "unsupported/future history",
    "Protected source/audio/provenance boundary",
    "field-wise merge",
):
    assert anchor.lower() in doc.lower(), f"missing SMX-044 contract anchor: {anchor}"
for anchor in ("MAX_RELAY_QUEUE = 64", "people.relay_backpressure", "people.relay_offline", "resolve_conflict", "alternative-a", "alternative-b", "protected", '"plane": "collaboration"'):
    assert anchor in people, f"missing People production anchor: {anchor}"
assert 'state["people"]' in server and 'state["together"]' in server
assert '"plane": "runtime-networking"' in server
assert "peopleIngest" not in server, "raw unauthenticated collaboration ingress must not be exposed as an authoring action"
assert 'id="people-panel"' in html and 'data-plane="collaboration"' in html
assert 'id="together-boundary"' in html and 'data-plane="runtime-networking"' in html
assert html.index('id="people-panel"') != html.index('id="together-boundary"')
for anchor in ("renderPeople", "peoplePresence", "peopleResolveConflict", "peopleRetryLocal"):
    assert anchor in js, f"missing browser People projection: {anchor}"
for anchor in (
    "tests.production.test_smx043",
    "tests.production.test_smx044",
    "experiments/smx-018-collaboration-harness",
    "smx044_browser_harness.mjs",
    "tools/validate_smx044.py",
):
    assert anchor in workflow, f"SMX-044 workflow must retain {anchor}"

print("SMX-044 collaboration/People production contract OK")
