#!/usr/bin/env python3
"""Validate SMX-032 production browser-authoring contracts and evidence wiring."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.editor.authoring import assert_author_surface_vocabulary  # noqa: E402

FIXTURES = ROOT / "spec" / "production" / "smx032-editor-fixtures.json"
MODULES = ROOT / "src" / "MODULES.json"
DOC = ROOT / "docs" / "implementation" / "SMX-032-BROWSER-AUTHORING.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx032-browser-authoring.yml"
INDEX = ROOT / "src" / "splashmx" / "editor" / "web" / "index.html"
APP = ROOT / "src" / "splashmx" / "editor" / "web" / "app.js"
REQUIRED = [
    FIXTURES,
    MODULES,
    DOC,
    WORKFLOW,
    INDEX,
    APP,
    ROOT / "src" / "splashmx" / "editor" / "authoring.py",
    ROOT / "src" / "splashmx" / "editor" / "browser_server.py",
    ROOT / "tests" / "production" / "test_smx032.py",
    ROOT / "tests" / "production" / "smx032_browser_harness.mjs",
]
EXPECTED = [f"EDT-{index:03d}" for index in range(1, 25)]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    for path in REQUIRED:
        require(path.is_file(), f"missing SMX-032 required file: {path.relative_to(ROOT)}")

    fixture = json.loads(FIXTURES.read_text(encoding="utf-8"))
    require(fixture.get("schema") == "splashmx.smx032-editor-fixtures/1", "unexpected SMX-032 fixture schema")
    require(fixture.get("issue") == "SMX-032", "fixture issue mismatch")
    require(fixture.get("architecture_version") == "1.0", "fixture Architecture-v1 mismatch")
    rows = fixture.get("fixtures")
    require(isinstance(rows, list), "fixtures must be a list")
    ids = [row.get("id") for row in rows]
    require(ids == EXPECTED, f"SMX-032 fixtures must be exactly {EXPECTED}; got {ids}")
    for row in rows:
        require(row.get("kind") and row.get("action") and row.get("expect"), f"{row.get('id')} lacks a complete contract")

    upstream = set(fixture.get("upstream_contracts", []))
    for marker in ("AUTH-006", "AUTH-008", "AUTH-022", "AUTH-027", "UXG-001", "UXG-012", "R-019-01"):
        require(marker in upstream, f"SMX-032 fixture lost upstream authoring contract {marker}")

    modules = json.loads(MODULES.read_text(encoding="utf-8"))
    browser = next((row for row in modules.get("modules", []) if row.get("module_id") == "browser.editor"), None)
    require(browser is not None, "browser.editor module ownership missing")
    require(browser.get("owner_issue") == "SMX-032", "browser.editor ownership drifted")
    require(browser.get("status") == "implemented", "browser.editor must be implemented after SMX-032")
    require("GATE-04" in browser.get("gate_ids", []), "browser.editor must retain GATE-04 ownership")
    require(set(browser.get("canonical_identity_inputs", [])) == {"ThingId", "DefinitionId", "ConnectionId", "AssetId"}, "browser.editor canonical identity input set drifted")

    ordinary_copy = INDEX.read_text(encoding="utf-8")
    assert_author_surface_vocabulary(ordinary_copy)
    for word in ("Stage", "Thing", "Rule", "Behaviour", "Connect", "Timeline", "Inspect", "Import media"):
        require(word in ordinary_copy, f"ordinary browser surface missing author vocabulary: {word}")

    app = APP.read_text(encoding="utf-8")
    for action in ("createThing", "group", "makeReusable", "attachRule", "attachBehaviour", "connect", "timeline", "importAsset"):
        require(f'"{action}"' in app, f"browser application missing action projection {action}")
    require("window.splashmxState" in app, "browser campaign state probe missing")

    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "Production contract",
        "No browser shadow document model",
        "Protected source/audio/provenance boundary",
        "Transient editor state",
        "EDT-001",
        "EDT-024",
        "SMX-033",
    ):
        require(marker in doc, f"SMX-032 implementation doc missing marker {marker!r}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for command in (
        "python tools/validate_smx032.py",
        "python -m unittest discover -s tests/production -p 'test_smx032.py' -v",
        "node tests/production/smx032_browser_harness.mjs",
    ):
        require(command in workflow, f"SMX-032 workflow missing command: {command}")
    require("playwright@1.55.0" in workflow, "SMX-032 real-browser harness must pin Playwright")

    print(f"SMX-032 browser authoring contract valid: {len(rows)} EDT fixtures, production module ownership, real-browser gate wiring.")


if __name__ == "__main__":
    main()
