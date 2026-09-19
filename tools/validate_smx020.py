#!/usr/bin/env python3
"""Validate the SMX-020 Architecture v1 freeze artefacts.

The audit validator is intentionally factored so adversarial tests can mutate an
in-memory audit and prove that incomplete or contradictory freezes are rejected.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs/architecture/ARCHITECTURE-V1.md"
ADR = ROOT / "docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md"
AUDIT = ROOT / "docs/architecture/ARCHITECTURE-V1-AUDIT.json"
ROADMAP = ROOT / "docs/architecture/IMPLEMENTATION-ROADMAP-V1.md"
HYPOTHESES = ROOT / "docs/02-ARCHITECTURE-HYPOTHESES.md"
RAG = ROOT / "docs/03-RAG-INDEX.md"
LOG = ROOT / "docs/05-DECISION-AND-EVIDENCE-LOG.md"
AGENTS = ROOT / "AGENTS.md"

EXPECTED_HYPOTHESES = [f"H-{n:03d}" for n in range(1, 19)]
ALLOWED_HYPOTHESIS_STATUS = {
    "accepted_as_decision",
    "accepted_with_narrowed_refined_scope",
    "rejected",
    "deferred_unresolved_blocker",
}
EXPECTED_PROTECTED_FIELDS = [
    "digest",
    "source_identity",
    "source_metadata",
    "audio_or_media_semantics",
    "provenance",
    "licence_attribution",
    "derivation_lineage",
]
EXPECTED_CORRECTIONS = {
    "R-016-01", "R-016-02", "R-016-03", "R-016-04",
    "R-018-01", "R-018-02", "R-018-03", "R-018-04", "R-019-01",
}
AUTHORITY_PATHS = {
    "constitution": "docs/00-PROJECT-CONSTITUTION.md",
    "architecture": "docs/architecture/ARCHITECTURE-V1.md",
    "freeze_adr": "docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md",
    "implementation_roadmap": "docs/architecture/IMPLEMENTATION-ROADMAP-V1.md",
    "research_index": "docs/03-RAG-INDEX.md",
}
HISTORICAL_PATHS = [
    "docs/01-RESEARCH-ROADMAP.pre-v1.md",
    "docs/02-ARCHITECTURE-HYPOTHESES.pre-v1.md",
    "docs/03-RAG-INDEX.pre-v1.md",
    "docs/05-DECISION-AND-EVIDENCE-LOG.pre-v1.md",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text(path: Path) -> str:
    require(path.is_file(), f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_audit(audit: dict[str, Any], *, check_paths: bool = True, root: Path = ROOT) -> tuple[int, int]:
    require(audit.get("schema") == "splashmx.architecture-v1-audit/1", "unexpected audit schema")
    require(audit.get("architecture_version") == "1.0", "architecture version must be 1.0")
    require(audit.get("freeze_date") == "2026-09-19", "freeze date mismatch")
    require(audit.get("prerequisite_range") == "SMX-001..SMX-019", "prerequisite range mismatch")

    hypotheses = audit.get("hypotheses")
    require(isinstance(hypotheses, list), "hypotheses must be a list")
    ids = [row.get("id") for row in hypotheses]
    require(ids == EXPECTED_HYPOTHESES, f"expected exactly {EXPECTED_HYPOTHESES}, got {ids}")
    for row in hypotheses:
        require(row.get("status") in ALLOWED_HYPOTHESIS_STATUS, f"invalid {row.get('id')} status: {row.get('status')}")
        require(row.get("decision"), f"{row.get('id')} lacks final decision text")
        require(isinstance(row.get("evidence"), list) and row["evidence"], f"{row.get('id')} lacks evidence references")
    blockers = [row["id"] for row in hypotheses if row["status"] == "deferred_unresolved_blocker"]
    require(not blockers, f"Architecture v1 cannot freeze with unresolved hypothesis blockers: {blockers}")

    seams = audit.get("contradiction_audit")
    require(isinstance(seams, list) and len(seams) >= 20, "contradiction audit must cover at least 20 cross-domain seams")
    seam_ids = [row.get("id") for row in seams]
    require(len(seam_ids) == len(set(seam_ids)), "duplicate contradiction-audit IDs")
    for row in seams:
        require(row.get("seam"), f"{row.get('id')} lacks seam name")
        require(row.get("resolution_status") == "resolved", f"{row.get('id')} is not resolved")
        require(row.get("resolution"), f"{row.get('id')} lacks resolution")
        require(isinstance(row.get("evidence"), list) and row["evidence"], f"{row.get('id')} lacks evidence")

    require(audit.get("protected_media_fields") == EXPECTED_PROTECTED_FIELDS, "protected-media field set/order changed")
    corrections = set(audit.get("incorporated_corrective_findings", []))
    require(EXPECTED_CORRECTIONS <= corrections, f"missing corrective findings: {sorted(EXPECTED_CORRECTIONS - corrections)}")
    require(len(audit.get("post_freeze_residual_classes", [])) >= 8, "residual implementation risks were collapsed or lost")

    authority = audit.get("authority", {})
    for key, expected in AUTHORITY_PATHS.items():
        require(authority.get(key) == expected, f"authority entry {key} changed")
        if check_paths:
            require((root / expected).is_file(), f"authority target does not exist: {expected}")

    return len(hypotheses), len(seams)


def validate_repository() -> tuple[int, int]:
    for path in [ARCH, ADR, AUDIT, ROADMAP, HYPOTHESES, RAG, LOG, AGENTS]:
        require(path.is_file(), f"missing required file: {path.relative_to(ROOT)}")
    for rel in HISTORICAL_PATHS:
        require((ROOT / rel).is_file(), f"historical pre-v1 authority snapshot missing: {rel}")

    counts = validate_audit(json.loads(text(AUDIT)))

    arch = text(ARCH)
    for needle in [
        "# SplashMX Architecture v1.0",
        "## 2. Product and authoring contract",
        "## 3. Canonical Object Fabric",
        "## 4. Execution model",
        "## 5. Document, lifecycle, streaming, and compatibility",
        "## 6. Security and trust boundaries",
        "## 7. Runtime networking and collaboration",
        "## 8. Godot and platform boundary",
        "## 9. Components and publishing",
        "## 10. Protected media/provenance invariant",
        "## 11. Hypothesis closure",
        "## 13. Production conformance gates",
        "**Thing**", "**Behaviour**", "**Connection**",
        "R-016-01", "R-018-01", "R-019-01",
        "CreationRevisionId", "WorldSave", "Godot 4.7.2",
    ]:
        require(needle in arch, f"Architecture v1 missing required concept/section: {needle}")
    for hid in EXPECTED_HYPOTHESES:
        require(hid in arch, f"Architecture v1 missing final disposition for {hid}")

    roadmap = text(ROADMAP).lower()
    for needle in [
        "canonical core and protected assets", "bounded execution and capabilities",
        "minimal browser editor/player", "components and generic publishing",
        "godot production binding and performance", "security hardening", "collaboration",
        "production multiplayer", "remaining research spikes", "protected media", "local/offline",
    ]:
        require(needle in roadmap, f"implementation roadmap missing gate/topic: {needle}")

    adr = text(ADR)
    require("Status:** Accepted" in adr, "freeze ADR must be Accepted")
    require("ARCHITECTURE-V1-AUDIT.json" in adr, "freeze ADR must point at machine-readable contradiction audit")
    require("research documents" in adr.lower() and "evidence" in adr.lower(), "freeze ADR must preserve historical research as evidence")

    hypothesis_text = text(HYPOTHESES)
    require("Architecture v1.0 final closure" in hypothesis_text, "hypothesis register lacks final Architecture-v1 closure")
    for hid in EXPECTED_HYPOTHESES:
        require(hid in hypothesis_text, f"hypothesis register missing {hid}")

    rag = text(RAG)
    require("Architecture v1.0 post-freeze retrieval rules" in rag, "RAG index lacks post-freeze authority chain")
    for path in [
        "docs/architecture/ARCHITECTURE-V1.md",
        "docs/architecture/ADR-0001-ARCHITECTURE-V1-FREEZE.md",
        "docs/architecture/ARCHITECTURE-V1-AUDIT.json",
        "docs/architecture/IMPLEMENTATION-ROADMAP-V1.md",
    ]:
        require(path in rag, f"RAG index does not retrieve {path}")

    require(
        "| Architecture contradiction or change | `docs/architecture/ARCHITECTURE-V1-AUDIT.json`"
        in rag,
        "RAG architecture-change route must use the explicit architecture audit path",
    )
    require(
        "not a self-contained frozen path namespace" in rag,
        "RAG must warn that historical snapshots can contain now-live unsuffixed paths",
    )

    log = text(LOG)
    require("SMX-020 Architecture v1.0 freeze register" in log, "decision/evidence log lacks SMX-020 freeze register")
    for marker in ["D-117", "D-118", "D-119", "D-120", "D-121", "D-122", "D-123", "E-088", "O-029"]:
        require(marker in log, f"decision/evidence log lacks {marker}")

    agents = text(AGENTS)
    require("docs/architecture/ARCHITECTURE-V1.md" in agents, "AGENTS.md lacks frozen Architecture v1 authority")
    require("docs/architecture/IMPLEMENTATION-ROADMAP-V1.md" in agents, "AGENTS.md lacks production roadmap")
    return counts


def main() -> None:
    hypothesis_count, seam_count = validate_repository()
    print(f"SMX-020 validation passed: {hypothesis_count} hypotheses closed, {seam_count} cross-domain seams resolved, protected-media contract intact.")


if __name__ == "__main__":
    main()
