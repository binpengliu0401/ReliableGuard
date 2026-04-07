from typing import Any


# Derive system outcome label from final state
def derive_outcome(state: dict) -> str:
    if state is None:
        return "ERROR"

    tool_call = state.get("tool_call")
    gate_status = state.get("gate_status")
    verifier_status = state.get("verifier_status")
    recovery_action = state.get("recovery_action")
    executed_tools = state.get("executed_tools", [])

    # Multi-turn completed: tools were executed, last plan found no more calls
    if tool_call is None and executed_tools:
        if verifier_status == "PASSED" or verifier_status is None:
            return "SUCCESS"

    # Single-turn: no tool was ever called
    if tool_call is None:
        return "NOT_TRIGGERED"

    if gate_status == "BLOCKED":
        return "GATE_BLOCKED"
    if recovery_action == "rollback":
        return "ROLLBACK"
    if verifier_status == "PASSED":
        return "SUCCESS"
    if verifier_status == "FAILED":
        return "VERIFY_FAILED"
    if gate_status in ("PASSED", None) and verifier_status is None:
        return "SUCCESS"
    return "UNKNOWN"


# Outcome Score 0-3 per task
def compute_outcome_score(expected: str, actual: str) -> int:
    if actual == "ERROR":
        return 0

    if actual == expected:
        return 3

    # Partial credit: system caught a real failure but via wrong layer
    partial_correct_pairs = {
        ("GATE_BLOCKED", "ROLLBACK"),
        ("ROLLBACK", "GATE_BLOCKED"),
        ("GATE_BLOCKED", "VERIFY_FAILED"),
    }
    if (expected, actual) in partial_correct_pairs:
        return 2

    # System did not trigger at all when it should have acted
    if actual == "NOT_TRIGGERED" and expected != "NOT_TRIGGERED":
        return 1

    # Silent failure: task reported success but should have been caught
    if actual == "SUCCESS" and expected != "SUCCESS":
        return 0

    return 1


# Aggregate metrics across a list of (task_spec, final_state) pairs
def compute_metrics(results: list[dict]) -> dict:
    results = [r for r in results if not r["task"].get("note")]

    total = len(results)
    if total == 0:
        return {}

    success_count = 0
    false_success_count = 0
    gate_schema_blocked = 0
    gate_policy_blocked = 0
    total_tool_calls = 0
    outcome_scores = []

    for r in results:
        state = r["state"]
        task = r["task"]

        actual = derive_outcome(state)
        expected = task["expected_outcome"]
        score = compute_outcome_score(expected, actual)
        outcome_scores.append(score)

        if state is not None:
            # execute + gate
            total_tool_calls += len(state.get("executed_tools", []))
            if state.get("gate_status") == "BLOCKED":
                total_tool_calls += 1

        if actual == "SUCCESS":
            success_count += 1

        if actual == "SUCCESS" and expected != "SUCCESS":
            false_success_count += 1

        gate_detail = (state.get("gate_detail", "") if state else "") or ""
        if state is not None and state.get("gate_status") == "BLOCKED":
            if "Policy violation" in gate_detail:
                gate_policy_blocked += 1
            else:
                gate_schema_blocked += 1

    call_base = total_tool_calls if total_tool_calls > 0 else 1

    return {
        "total_tasks": total,
        "end_to_end_success_rate": round(success_count / total, 3),
        "false_success_rate": round(false_success_count / total, 3),
        "invalid_call_rate": round(gate_schema_blocked / call_base, 3),
        "policy_violation_rate": round(gate_policy_blocked / call_base, 3),
        "avg_outcome_score": round(sum(outcome_scores) / total, 3),
        "outcome_scores": outcome_scores,
    }


def derive_failure_type(state: dict | None, expected: str, actual: str) -> str:
    if state is None:
        return "runtime_error"

    if actual == expected:
        return "none"

    gate_status = state.get("gate_status")
    gate_detail = (state.get("gate_detail", "") or "").lower()
    verifier_status = state.get("verifier_status")
    recovery_action = state.get("recovery_action")

    if gate_status == "BLOCKED":
        if "policy violation" in gate_detail or "dependency" in gate_detail:
            return "rules_violation"
        return "invalid_call"

    if verifier_status == "FAILED":
        return "verification_failed"

    if recovery_action == "rollback":
        return "rollback"

    if actual == "NOT_TRIGGERED":
        return "not_triggered"

    if actual == "SUCCESS" and expected != "SUCCESS":
        return "false_success"

    return "unknown"


def build_result_row(
    task: dict, state: dict | None, version: str, error: str | None = None
) -> dict:
    actual = derive_outcome(state)  # type: ignore
    expected = task["expected_outcome"]
    score = compute_outcome_score(expected, actual)

    executed_tools = []
    if state is not None:
        executed_tools = state.get("executed_tools", []) or []

    return {
        "scenario_id": task.get("id"),
        "domain": task.get("domain", "unknown"),
        "version": version,
        "expected_outcome": expected,
        "actual_outcome": actual,
        "pass_fail": actual == expected,
        "outcome_score": score,
        "failure_type": derive_failure_type(state, expected, actual),
        "tool_calls": len(executed_tools),
        "gate_status": state.get("gate_status") if state else None,
        "gate_detail": state.get("gate_detail") if state else None,
        "verifier_status": state.get("verifier_status") if state else None,
        "recovery_action": state.get("recovery_action") if state else None,
        "error": error,
    }
