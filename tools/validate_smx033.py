#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec" / "production" / "smx033-browser-runtime-fixtures.json"
DOC = ROOT / "docs" / "implementation" / "SMX-033-BROWSER-RUNTIME.md"
INDEX = ROOT / "src" / "splashmx" / "editor" / "web" / "index.html"
APP = ROOT / "src" / "splashmx" / "editor" / "web" / "app.js"
SERVER = ROOT / "src" / "splashmx" / "editor" / "browser_server.py"
RUNTIME = ROOT / "src" / "splashmx" / "editor" / "browser_runtime.py"
WORKFLOW = ROOT / ".github" / "workflows" / "smx033-browser-runtime.yml"
REQUIRED = [FIXTURES, DOC, INDEX, APP, SERVER, RUNTIME, WORKFLOW, ROOT / "tests" / "production" / "test_smx033.py", ROOT / "tests" / "production" / "smx033_browser_harness.mjs"]
EXPECTED = [f"BRW-{i:03d}" for i in range(1, 21)]


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    for path in REQUIRED:
        require(path.is_file(), f"missing SMX-033 file: {path.relative_to(ROOT)}")
    fixture = json.loads(FIXTURES.read_text())
    require(fixture.get("schema") == "splashmx.smx033-browser-runtime-fixtures/1", "fixture schema drift")
    require([row.get("id") for row in fixture.get("fixtures", [])] == EXPECTED, "BRW fixture set drift")
    upstream = set(fixture.get("upstream_contracts", []))
    for marker in ("R-019-01", "SMX-025", "SMX-029", "SMX-031", "SMX-032"):
        require(marker in upstream, f"lost upstream contract {marker}")
    index = INDEX.read_text()
    for marker in ('id="play"', 'id="stop"', 'id="save"', 'id="reload"', 'role="log"', 'aria-label="Project actions"', 'class="skip-link"', 'aria-keyshortcuts="Control+S"', 'aria-keyshortcuts="Alt+I"'):
        require(marker in index, f"accessibility/runtime surface missing {marker}")
    app = APP.read_text()
    for action in ('"play"', '"stop"', '"save"', '"reload"', 'event.ctrlKey', 'event.altKey', 'event.key.toLowerCase()', 'window.splashmxState'):
        require(action in app, f"browser integration missing {action}")
    server = SERVER.read_text()
    for marker in ("connectionhandle", "transportpeerid", "BrowserRuntimeSession"):
        require(marker in server, f"browser ingress boundary missing {marker}")
    runtime = RUNTIME.read_text()
    for marker in ("WorldRuntime.create", "SQLiteProjectStore", "storage.quota_exceeded", "storage.permission_denied", "rebuild_program_catalog"):
        require(marker in runtime, f"runtime/store contract missing {marker}")
    doc = DOC.read_text()
    for marker in ("R-019-01", "not universal performance SLOs", "Protected source/audio/provenance boundary", "BRW-001", "BRW-020"):
        require(marker in doc, f"documentation missing {marker}")
    workflow = WORKFLOW.read_text()
    for command in ("python tools/validate_smx033.py", "test_smx033.py", "smx033_browser_harness.mjs", "playwright@1.55.0"):
        require(command in workflow, f"workflow missing {command}")
    print("SMX-033 browser runtime contract valid: 20 BRW fixtures, Play/Stop, persistence, diagnostics, accessibility and measured-browser gate.")


if __name__ == "__main__":
    main()
