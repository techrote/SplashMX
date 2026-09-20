#!/usr/bin/env python3
"""Static production-contract validation for SMX-026."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "MODULES.json"
REGISTRY = ROOT / "spec" / "production" / "conformance-registry.json"
SOURCE = ROOT / "src" / "splashmx" / "execution" / "ir.py"
TESTS = ROOT / "tests" / "production" / "test_smx026.py"
DOC = ROOT / "docs" / "implementation" / "SMX-026-EXECUTION-IR.md"
WORKFLOW = ROOT / ".github" / "workflows" / "smx026-execution-ir.yml"
RAG = ROOT / "docs" / "03-RAG-INDEX.md"
LOG = ROOT / "docs" / "05-DECISION-AND-EVIDENCE-LOG.md"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    for path in (MANIFEST, REGISTRY, SOURCE, TESTS, DOC, WORKFLOW, RAG, LOG):
        require(path.is_file(), f"missing SMX-026 artefact: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = {row["module_id"]: row for row in manifest["modules"]}
    require("execution.ir" in modules, "execution.ir missing from module manifest")
    module = modules["execution.ir"]
    require(module["owner_issue"] == "SMX-026", "execution.ir owner drifted")
    require(module["status"] == "implemented", "execution.ir is not implemented")
    require(module["gate_ids"] == ["GATE-02"], "execution.ir gate ownership drifted")
    for identity in ("ThingId", "BehaviourAttachmentId"):
        require(identity in module["canonical_identity_inputs"], f"missing execution identity role {identity}")
    for responsibility in (
        "common bounded IR",
        "Rule compilation",
        "scheduler and resource budgets",
        "deterministic activation ordering",
        "explicit timer and service-request work",
    ):
        require(responsibility in module["responsibilities"], f"execution.ir missing responsibility: {responsibility}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    gate02 = next(row for row in registry["gate_entries"] if row["id"] == "GATE-02")
    for current in ("tools/validate_smx026.py", "tests/production/test_smx026.py"):
        require(current in gate02["current_tests"], f"GATE-02 missing SMX-026 production evidence: {current}")
    require("SMX-026" not in gate02["future_issue_codes"], "GATE-02 still treats completed SMX-026 coverage as future")
    require(
        any(row["path"] == "docs/implementation/SMX-026-EXECUTION-IR.md" for row in gate02["evidence"]),
        "GATE-02 missing SMX-026 implementation evidence",
    )
    r01602 = next(row for row in registry["non_droppable_regressions"] if row["id"] == "R-016-02")
    require("execution.ir" in r01602["owner_modules"], "R-016-02 lost execution.ir recursive-authority ownership")

    source = SOURCE.read_text(encoding="utf-8")
    for marker in (
        'IR_VERSION = "splashmx.behaviour-ir/1"',
        "class IRProgram",
        "def compile_rule",
        "class ExecutionRuntime",
        "class BudgetLimits",
        "instruction_steps",
        "recursion_depth",
        "allocations",
        "emitted_work",
        "timers_per_activation",
        "pending_timers",
        "queue_entries",
        "service_requests",
        "pending_service_requests",
        "activations_per_run",
        "execution.attachment_order_required",
        "execution.forbidden_opcode",
        "execution.unknown_opcode",
        "execution.forbidden_transient_identity",
        '"request_service"',
        "PendingTimer",
        "ServiceRequest",
    ):
        require(marker in source, f"execution IR missing contract marker: {marker}")
    for raw_host in ("gdscript", "javascript", "host_call", "raw_socket", "set_other_state"):
        require(raw_host in source, f"execution validator missing explicit raw-host denial: {raw_host}")

    tests = TESTS.read_text(encoding="utf-8")
    for marker in (
        "test_beginner_rule_and_advanced_behaviour_share_ir_program_and_executor",
        "test_commit_precedes_follow_on_event_activation",
        "test_attachment_order_must_be_explicit_and_is_not_uuid_or_lexical_order",
        "test_runtime_play_state_does_not_mutate_canonical_authored_document",
        "test_fault_rolls_back_public_private_effects_and_random_stream",
        "test_instruction_cpu_proxy_budget_is_independent",
        "test_recursion_budget_is_independent",
        "test_allocation_budget_is_independent",
        "test_emitted_work_budget_is_independent_and_rolls_back_all_effects",
        "test_timer_creation_budget_is_independent_and_rolls_back",
        "test_pending_timer_budget_is_checked_before_state_commit",
        "test_queue_budget_is_checked_before_state_commit",
        "test_service_request_budget_is_independent",
        "test_pending_service_budget_rolls_back_before_publication",
        "test_activation_event_storm_terminates_under_deterministic_run_budget",
        "test_unknown_required_opcode_fails_closed_before_launch",
        "test_raw_host_and_foreign_state_opcodes_fail_closed_before_launch",
        "test_nested_transient_authority_external_payload_is_rejected",
        "test_service_opcode_only_emits_mediated_request_and_never_invokes_host",
        "test_timer_is_explicit_pending_work_and_can_be_cancelled",
        "test_duplicate_timer_identity_fault_is_atomic",
        "test_same_inputs_seed_and_program_produce_same_trace",
    ):
        require(marker in tests, f"SMX-026 tests missing regression: {marker}")

    doc = DOC.read_text(encoding="utf-8").lower()
    for marker in (
        "one ir/executor",
        "commit state, then publish staged work",
        "instruction_steps",
        "recursion_depth",
        "allocations",
        "emitted_work",
        "pending_timers",
        "queue_entries",
        "service_requests",
        "no api for ir content to register or invoke host callables",
        "refuses to invent order",
        "source digest",
        "source identity",
        "source metadata",
        "audio/media semantics",
        "provenance",
        "licence/attribution",
        "derivation lineage",
        "architecture v1.0 remains unchanged",
    ):
        require(marker in doc, f"SMX-026 documentation missing: {marker}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "python tools/validate_smx004.py",
        "experiments/smx-004-behaviour-model",
        "python tools/validate_smx016.py",
        "python tools/validate_smx026.py",
        "test_smx023.py",
        "test_smx026.py",
    ):
        require(marker in workflow, f"SMX-026 workflow missing: {marker}")

    rag = RAG.read_text(encoding="utf-8")
    require("SMX-026-EXECUTION-IR.md" in rag, "RAG index missing SMX-026 production retrieval anchor")
    log = LOG.read_text(encoding="utf-8")
    for marker in ("D-125", "E-090", "O-031", "SMX-026"):
        require(marker in log, f"decision/evidence log missing SMX-026 marker: {marker}")

    print(
        "SMX-026 execution contract valid: common IR, Rule compiler, deterministic scheduler, independent budgets, docs and production evidence present."
    )


if __name__ == "__main__":
    main()
