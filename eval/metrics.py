from typing import Any


def normalize_expected(task: dict[str, Any]) -> str:
    expected = task.get("expected_verdict") or task.get("expected_outcome") or "PASS"
    mapping = {
        "SUCCESS": "PASS",
        "NOT_TRIGGERED": "PASS",
        "VERIFY_FAILED": "BLOCK",
        "GATE_BLOCKED": "BLOCK",
        "ROLLBACK": "BLOCK",
        "RECOVERY_SUCCESS": "PASS",
    }
    return mapping.get(str(expected), str(expected))


def derive_outcome(state: dict | None) -> str:
    if state is None:
        return "ERROR"
    verdict = state.get("reliability_verdict")
    if verdict:
        return str(verdict)
    if state.get("final_answer") is not None or state.get("executed_tools"):
        return "PASS"
    return "NOT_TRIGGERED"


def derive_audit_outcome(state: dict | None) -> str:
    """Return true audit verdict when reliability ran, otherwise normal outcome."""
    if state is None:
        return "ERROR"
    audit = state.get("reliability_verdict_audit")
    if audit:
        return str(audit)
    return derive_outcome(state)


def compute_outcome_score(expected: str, actual: str) -> int:
    if actual == "ERROR":
        return 0
    if actual == expected:
        return 3
    if expected == "BLOCK" and actual == "WARN":
        return 2
    if expected == "WARN" and actual in {"BLOCK", "PASS"}:
        return 1
    if expected == "PASS" and actual in {"WARN", "BLOCK"}:
        return 1
    if expected in {"BLOCK", "WARN"} and actual == "PASS":
        return 0
    return 1


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {}

    passed = 0
    audit_passed = 0
    false_accept = 0
    audit_false_accept = 0
    false_accept_denominator = 0
    blocked = 0
    warned = 0
    outcome_scores = []
    reliability_scores = []
    detection_by_type: dict[str, dict[str, int]] = {}

    for item in results:
        state = item.get("state")
        task = item.get("task", {})
        actual = derive_outcome(state)
        audit_actual = derive_audit_outcome(state)
        expected = normalize_expected(task)
        score = compute_outcome_score(expected, actual)
        outcome_scores.append(score)

        if actual == expected:
            passed += 1
        if audit_actual == expected:
            audit_passed += 1
        if expected in {"BLOCK", "WARN"}:
            false_accept_denominator += 1
        if expected in {"BLOCK", "WARN"} and actual == "PASS":
            false_accept += 1
        if expected in {"BLOCK", "WARN"} and audit_actual == "PASS":
            audit_false_accept += 1
        if actual == "BLOCK":
            blocked += 1
        if actual == "WARN":
            warned += 1
        if state is not None and state.get("reliability_score") is not None:
            reliability_scores.append(float(state["reliability_score"]))

        claim_type = task.get("injected_error_type") or task.get("claim_type")
        if claim_type:
            bucket = detection_by_type.setdefault(str(claim_type), {"total": 0, "detected": 0})
            bucket["total"] += 1
            if expected in {"BLOCK", "WARN"} and actual in {"BLOCK", "WARN"}:
                bucket["detected"] += 1

    detection_rates = {
        claim_type: round(data["detected"] / data["total"], 3) if data["total"] else 0.0
        for claim_type, data in detection_by_type.items()
    }

    return {
        "total_tasks": total,
        "pass_rate": round(passed / total, 3),
        "audit_pass_rate": round(audit_passed / total, 3),
        "false_acceptance_rate": round(false_accept / false_accept_denominator, 3)
        if false_accept_denominator
        else 0.0,
        "audit_false_acceptance_rate": round(
            audit_false_accept / false_accept_denominator, 3
        )
        if false_accept_denominator
        else 0.0,
        "block_rate": round(blocked / total, 3),
        "warn_rate": round(warned / total, 3),
        "avg_reliability_score": round(sum(reliability_scores) / len(reliability_scores), 3)
        if reliability_scores
        else 0.0,
        "avg_outcome_score": round(sum(outcome_scores) / total, 3),
        "detection_rate_by_type": detection_rates,
        "outcome_scores": outcome_scores,
    }


def derive_failure_type(state: dict | None, expected: str, actual: str) -> str:
    if state is None:
        return "runtime_error"
    if actual == expected:
        return "none"
    if expected in {"BLOCK", "WARN"} and actual == "PASS":
        return "false_acceptance"
    if expected == "PASS" and actual in {"WARN", "BLOCK"}:
        return "false_alarm"
    return "verdict_mismatch"


def build_result_row(
    task: dict, state: dict | None, version: str, error: str | None = None
) -> dict:
    actual = derive_outcome(state)
    actual_audit = derive_audit_outcome(state)
    expected = normalize_expected(task)
    score = compute_outcome_score(expected, actual)

    executed_tools = []
    total_tokens = 0
    reliability_score = None
    reliability_summary = None
    if state is not None:
        executed_tools = state.get("executed_tools", []) or []
        total_tokens = state.get("total_tokens", 0) or 0
        reliability_score = state.get("reliability_score")
        report = state.get("reliability_report") or {}
        if isinstance(report, dict):
            reliability_summary = report.get("summary")

    return {
        "scenario_id": task.get("id"),
        "domain": task.get("domain", "unknown"),
        "version": version,
        "expected_outcome": expected,
        "actual_outcome": actual,
        "actual_audit_outcome": actual_audit,
        "pass_fail": actual == expected,
        "audit_pass_fail": actual_audit == expected,
        "outcome_score": score,
        "failure_type": task.get("failure_type")
        or task.get("injected_error_type")
        or derive_failure_type(state, expected, actual),
        "tool_calls": len(executed_tools),
        "tokens": total_tokens,
        "reliability_score": reliability_score,
        "reliability_summary": reliability_summary,
        "error": error,
    }
