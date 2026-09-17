#!/usr/bin/env python3
"""Small dependency-free repository integrity check for SplashMX research PRs."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "AGENTS.md",
    "docs/00-PROJECT-CONSTITUTION.md",
    "docs/01-RESEARCH-ROADMAP.md",
    "docs/02-ARCHITECTURE-HYPOTHESES.md",
    "docs/03-RAG-INDEX.md",
    "docs/04-ISSUE-EXECUTION-PROTOCOL.md",
    "docs/05-DECISION-AND-EVIDENCE-LOG.md",
]

errors: list[str] = []

for rel in REQUIRED:
    if not (ROOT / rel).is_file():
        errors.append(f"missing required file: {rel}")

conflict_tokens = ("<<<<<<<", "=======", ">>>>>>>")
link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

for path in ROOT.rglob("*.md"):
    text = path.read_text(encoding="utf-8")
    for token in conflict_tokens:
        if token in text:
            errors.append(f"merge-conflict marker {token!r} in {path.relative_to(ROOT)}")
    for target in link_re.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"local link escapes repository in {path.relative_to(ROOT)}: {target}")
            continue
        if not resolved.exists():
            errors.append(f"broken local link in {path.relative_to(ROOT)}: {target}")

if errors:
    print("SplashMX repository validation failed:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SplashMX repository validation passed")
