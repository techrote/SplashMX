#!/usr/bin/env python3
"""Small dependency-free repository integrity check for SplashMX research PRs."""
from __future__ import annotations

import json
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
    "docs/research/SMX-001-RESEARCH-BASELINE.md",
    "docs/research/SMX-001-EVALUATION-CORPUS.json",
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

# SMX-001 establishes stable machine-addressable research case IDs. Validate the
# small companion corpus so later agents can safely use IDs in fixtures and RAG.
corpus_path = ROOT / "docs/research/SMX-001-EVALUATION-CORPUS.json"
baseline_path = ROOT / "docs/research/SMX-001-RESEARCH-BASELINE.md"
if corpus_path.is_file():
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"invalid SMX-001 corpus JSON: {exc}")
    else:
        if corpus.get("schema") != "splashmx-research-corpus-v1":
            errors.append("unexpected SMX-001 corpus schema")
        case_groups = (
            ("cases", re.compile(r"^C-\d{3}$")),
            ("adversarial_cases", re.compile(r"^A-\d{3}$")),
        )
        all_ids: list[str] = []
        domains: set[str] = set()
        for key, id_re in case_groups:
            values = corpus.get(key)
            if not isinstance(values, list) or not values:
                errors.append(f"SMX-001 corpus {key} must be a non-empty list")
                continue
            for item in values:
                if not isinstance(item, dict):
                    errors.append(f"SMX-001 corpus {key} contains a non-object entry")
                    continue
                case_id = item.get("id")
                if not isinstance(case_id, str) or not id_re.fullmatch(case_id):
                    errors.append(f"invalid SMX-001 case id in {key}: {case_id!r}")
                else:
                    all_ids.append(case_id)
                if not item.get("name"):
                    errors.append(f"SMX-001 case {case_id!r} has no name")
                stresses = item.get("stresses")
                if not isinstance(stresses, list) or not stresses:
                    errors.append(f"SMX-001 case {case_id!r} has no stresses")
                if key == "cases":
                    item_domains = item.get("domains")
                    if not isinstance(item_domains, list) or not item_domains:
                        errors.append(f"SMX-001 representative case {case_id!r} has no domains")
                    else:
                        domains.update(str(value) for value in item_domains)
        if len(all_ids) != len(set(all_ids)):
            errors.append("duplicate SMX-001 corpus case IDs")

        required_domains = corpus.get("required_domain_coverage")
        if not isinstance(required_domains, list) or not required_domains:
            errors.append("SMX-001 corpus required_domain_coverage must be non-empty")
        else:
            missing_domains = sorted(set(map(str, required_domains)) - domains)
            if missing_domains:
                errors.append(
                    "SMX-001 representative corpus misses required domains: "
                    + ", ".join(missing_domains)
                )

        scorecard_ids = corpus.get("scorecard_ids")
        score_re = re.compile(r"^S-\d{2}$")
        if (
            not isinstance(scorecard_ids, list)
            or not scorecard_ids
            or any(not isinstance(value, str) or not score_re.fullmatch(value) for value in scorecard_ids)
            or len(scorecard_ids) != len(set(scorecard_ids))
        ):
            errors.append("SMX-001 scorecard_ids must be unique S-## identifiers")

        if baseline_path.is_file():
            baseline = baseline_path.read_text(encoding="utf-8")
            for identifier in all_ids + list(scorecard_ids or []):
                if identifier not in baseline:
                    errors.append(f"SMX-001 baseline does not reference corpus id {identifier}")

if errors:
    print("SplashMX repository validation failed:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("SplashMX repository validation passed")
