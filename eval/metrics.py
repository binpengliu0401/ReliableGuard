import random
from typing import Any


EVIDENCE_STATE_COUNT_FIELDS = (
    "supported_count",
    "contradicted_count",
    "unsupported_count",
    "unverifiable_count",
    "not_found_count",
)

STAGE_LATENCY_KEYS = (
    "extract_claims",
    "classify_verifiability",
    "verify_claims",
    "score_risks",
    "decide_interventions",
    "generate_report",
    "total_pipeline",
)


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


def bootstrap_ci(
    values: list[float],
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Return a bootstrap confidence interval for the sample mean."""
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])

    rng = random.Random(seed)
    n_values = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n_values)] for _ in range(n_values)]
        means.append(sum(sample) / n_values)

    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lower_index = max(0, min(n_resamples - 1, int(alpha * n_resamples)))
    upper_index = max(
        0,
        min(n_resamples - 1, int((1.0 - alpha) * n_resamples) - 1),
    )
    return (means[lower_index], means[upper_index])


def _pass_and_far(results: list[dict]) -> tuple[float, float]:
    total = len(results)
    if total == 0:
        return (0.0, 0.0)

    passed = 0
    false_accept = 0
    false_accept_denominator = 0

    for item in results:
        state = item.get("state")
        task = item.get("task", {})
        actual = derive_outcome(state)
        expected = normalize_expected(task)
        if actual == expected:
            passed += 1
        if expected in {"BLOCK", "WARN"}:
            false_accept_denominator += 1
        if expected in {"BLOCK", "WARN"} and actual == "PASS":
            false_accept += 1

    far = (
        false_accept / false_accept_denominator
        if false_accept_denominator
        else 0.0
    )
    return (passed / total, far)


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {}

    passed = 0
    audit_passed = 0
    false_accept = 0
    audit_false_accept = 0
    false_accept_denominator = 0
    false_alarm = 0
    false_alarm_denominator = 0
    risk_detected = 0
    safe_passed = 0
    blocked = 0
    warned = 0
    tccr_count = 0
    evidence_state_task_count = 0
    verifier_ran_count = 0
    zero_claim_count = 0
    zero_claim_pass = 0
    pass_with_claim = 0
    pass_without_claim = 0
    evidence_state_totals = dict.fromkeys(EVIDENCE_STATE_COUNT_FIELDS, 0)
    # source_mode == "unavailable" aggregate. Tracked separately from evidence states
    # so it does not pollute evidence_state_coverage (a claim can be unavailable while
    # carrying no positive evidence state).
    unavailable_total = 0
    unavailable_task_count = 0
    stage_latency_lists: dict[str, list[float]] = {
        stage: [] for stage in STAGE_LATENCY_KEYS
    }
    token_values: list[int] = []
    outcome_scores = []
    reliability_scores = []
    fact_accuracy_blocked: list[float] = []
    fact_accuracy_correct_pass: list[float] = []
    fact_accuracy_values = [
        item["fact_accuracy"]
        for item in results
        if item.get("fact_accuracy") is not None
    ]
    all_trace_scores = [
        value
        for item in results
        for value in (item.get("trace_fact_scores") or {}).values()
        if value is not None
    ]
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
        if expected in {"BLOCK", "WARN"} and actual in {"BLOCK", "WARN"}:
            risk_detected += 1
        if expected in {"BLOCK", "WARN"} and actual == "PASS":
            false_accept += 1
        if expected in {"BLOCK", "WARN"} and audit_actual == "PASS":
            audit_false_accept += 1
        if actual == "BLOCK":
            blocked += 1
        if actual == "WARN":
            warned += 1
        if expected == "PASS":
            false_alarm_denominator += 1
            fa = item.get("fact_accuracy")
            if actual in {"WARN", "BLOCK"}:
                false_alarm += 1
                if fa is not None:
                    fact_accuracy_blocked.append(float(fa))
            elif actual == "PASS":
                safe_passed += 1
                if fa is not None:
                    fact_accuracy_correct_pass.append(float(fa))
        if state is not None and state.get("reliability_score") is not None:
            reliability_scores.append(float(state["reliability_score"]))
        report = state.get("reliability_report") if state is not None else None
        if isinstance(report, dict):
            verifier_ran_count += 1
            claim_count = len(report.get("traces", []))
            if claim_count == 0:
                zero_claim_count += 1
                if actual == "PASS":
                    zero_claim_pass += 1
            if actual == "PASS":
                if claim_count == 0:
                    pass_without_claim += 1
                else:
                    pass_with_claim += 1

            evidence_counts = {
                key: int(report.get(key) or 0)
                for key in EVIDENCE_STATE_COUNT_FIELDS
            }
            if any(evidence_counts.values()):
                evidence_state_task_count += 1
                for key, value in evidence_counts.items():
                    evidence_state_totals[key] += value

            unavailable_count = int(report.get("unavailable_count") or 0)
            if unavailable_count > 0:
                unavailable_total += unavailable_count
                unavailable_task_count += 1

            grounded_count = sum(
                int(report.get(key) or 0)
                for key in (
                    "supported_count",
                    "contradicted_count",
                    "unsupported_count",
                    "not_found_count",
                )
            )
            if grounded_count > 0:
                tccr_count += 1

            stage_latencies = report.get("stage_latencies")
            if isinstance(stage_latencies, dict):
                for key, value in stage_latencies.items():
                    if value is not None:
                        stage_latency_lists.setdefault(str(key), []).append(
                            float(value)
                        )

        tokens = item.get("tokens")
        if tokens is None and state is not None:
            tokens = state.get("total_tokens")
        if tokens is not None and int(tokens) > 0:
            token_values.append(int(tokens))

        claim_type = task.get("failure_mode") or task.get("injected_error_type") or task.get("claim_type")
        if claim_type:
            bucket = detection_by_type.setdefault(str(claim_type), {"total": 0, "detected": 0})
            bucket["total"] += 1
            if expected in {"BLOCK", "WARN"} and actual in {"BLOCK", "WARN"}:
                bucket["detected"] += 1

    detection_rates = {
        claim_type: round(data["detected"] / data["total"], 3) if data["total"] else 0.0
        for claim_type, data in detection_by_type.items()
    }
    by_seed: dict[int, list[dict]] = {}
    for item in results:
        raw_seed = item.get("seed")
        group_seed = int(raw_seed) if raw_seed is not None else 0
        by_seed.setdefault(group_seed, []).append(item)
    pass_values = []
    far_values = []
    for seed_results in by_seed.values():
        seed_pass_rate, seed_far = _pass_and_far(seed_results)
        pass_values.append(seed_pass_rate)
        far_values.append(seed_far)
    pass_rate_ci = bootstrap_ci(pass_values)
    false_acceptance_rate_ci = bootstrap_ci(far_values)
    stage_latency_mean_ms = {}
    stage_latency_p95_ms = {}
    for stage, vals in stage_latency_lists.items():
        if not vals:
            continue
        sorted_vals = sorted(vals)
        p95_index = max(0, min(len(sorted_vals) - 1, int(0.95 * len(sorted_vals))))
        stage_latency_mean_ms[stage] = round(sum(vals) / len(vals) * 1000, 1)
        stage_latency_p95_ms[stage] = round(sorted_vals[p95_index] * 1000, 1)

    return {
        "total_tasks": total,
        "pass_rate": round(passed / total, 3),
        "pass_rate_ci": tuple(round(value, 3) for value in pass_rate_ci),
        "audit_pass_rate": round(audit_passed / total, 3),
        "false_acceptance_rate": round(false_accept / false_accept_denominator, 3)
        if false_accept_denominator
        else 0.0,
        "risk_detection_rate": round(risk_detected / false_accept_denominator, 3)
        if false_accept_denominator
        else None,
        "false_acceptance_rate_ci": tuple(
            round(value, 3) for value in false_acceptance_rate_ci
        ),
        "audit_false_acceptance_rate": round(
            audit_false_accept / false_accept_denominator, 3
        )
        if false_accept_denominator
        else 0.0,
        "block_rate": round(blocked / total, 3),
        "gate_action_rate": round((blocked + warned) / total, 3),
        "warn_rate": round(warned / total, 3),
        "avg_reliability_score": round(sum(reliability_scores) / len(reliability_scores), 3)
        if reliability_scores
        else 0.0,
        "avg_fact_accuracy": round(
            sum(fact_accuracy_values) / len(fact_accuracy_values), 3
        )
        if fact_accuracy_values
        else None,
        "avg_supported_count": round(
            evidence_state_totals["supported_count"] / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "avg_contradicted_count": round(
            evidence_state_totals["contradicted_count"] / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "avg_unsupported_count": round(
            evidence_state_totals["unsupported_count"] / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "avg_unverifiable_count": round(
            evidence_state_totals["unverifiable_count"] / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "avg_not_found_count": round(
            evidence_state_totals["not_found_count"] / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "avg_unavailable_count": round(
            unavailable_total / evidence_state_task_count, 3
        )
        if evidence_state_task_count
        else None,
        "unavailable_task_rate": round(unavailable_task_count / total, 3) if total else None,
        "evidence_state_coverage": round(evidence_state_task_count / total, 3),
        "false_alarm_rate": round(false_alarm / false_alarm_denominator, 3)
        if false_alarm_denominator
        else None,
        "safe_pass_rate": round(safe_passed / false_alarm_denominator, 3)
        if false_alarm_denominator
        else None,
        "avg_fact_accuracy_blocked": round(
            sum(fact_accuracy_blocked) / len(fact_accuracy_blocked), 3
        )
        if fact_accuracy_blocked
        else None,
        "avg_fact_accuracy_correct_pass": round(
            sum(fact_accuracy_correct_pass) / len(fact_accuracy_correct_pass), 3
        )
        if fact_accuracy_correct_pass
        else None,
        "fact_accuracy_coverage": round(len(fact_accuracy_values) / total, 3),
        "tccr": round(tccr_count / total, 3),
        "avg_trace_fact_accuracy": round(
            sum(1 for value in all_trace_scores if value) / len(all_trace_scores), 3
        )
        if all_trace_scores
        else None,
        "stage_latency_mean_ms": stage_latency_mean_ms,
        "stage_latency_p95_ms": stage_latency_p95_ms,
        "avg_tokens": round(sum(token_values) / len(token_values), 1)
        if token_values
        else None,
        "total_tokens_sum": sum(token_values) if token_values else None,
        "avg_outcome_score": round(sum(outcome_scores) / total, 3),
        "detection_rate_by_type": detection_rates,
        "outcome_scores": outcome_scores,
        "zero_claim_rate": round(zero_claim_count / verifier_ran_count, 3)
        if verifier_ran_count
        else None,
        "zero_claim_pass_rate": round(zero_claim_pass / zero_claim_count, 3)
        if zero_claim_count
        else None,
        "pass_with_claim_rate": round(
            pass_with_claim / (pass_with_claim + pass_without_claim), 3
        )
        if (pass_with_claim + pass_without_claim)
        else None,
        "pass_without_claim_rate": round(
            pass_without_claim / (pass_with_claim + pass_without_claim), 3
        )
        if (pass_with_claim + pass_without_claim)
        else None,
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
    task: dict,
    state: dict | None,
    version: str,
    error: str | None = None,
    seed: int | None = None,
    fact_accuracy: float | None = None,
    fact_snapshot: dict | None = None,
    trace_fact_scores: dict | None = None,
) -> dict:
    actual = derive_outcome(state)
    actual_audit = derive_audit_outcome(state)
    expected = normalize_expected(task)
    score = compute_outcome_score(expected, actual)

    executed_tools = []
    total_tokens = 0
    reliability_score = None
    reliability_summary = None
    claim_count = None
    if state is not None:
        executed_tools = state.get("executed_tools", []) or []
        total_tokens = state.get("total_tokens", 0) or 0
        reliability_score = state.get("reliability_score")
        report = state.get("reliability_report") or {}
        if isinstance(report, dict):
            reliability_summary = report.get("summary")
            claim_count = len(report.get("traces", []))

    return {
        "scenario_id": task.get("id"),
        "domain": task.get("domain", "unknown"),
        "version": version,
        "seed": seed,
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
        "claim_count": claim_count,
        "reliability_summary": reliability_summary,
        "fact_accuracy": fact_accuracy,
        "fact_snapshot": fact_snapshot or {},
        "trace_fact_scores": trace_fact_scores or {},
        "error": error,
    }
