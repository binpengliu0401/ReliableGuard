"""Frozen-corpus replay: determinism + paired structural isolation (no LLM calls)."""
from eval.ablation_runner import replay_corpus


def _ecommerce_record(scenario_id, expected, failure_mode, *, structural, amount):
    """A synthetic frozen record: a supported existence claim, with or without a
    frozen structural BLOCK, over a re-seedable post-execution order state."""
    return {
        "record_version": 1,
        "scenario_id": scenario_id,
        "domain": "ecommerce",
        "seed": 42,
        "input": f"create an order of {amount}",
        "task": {
            "id": scenario_id,
            "domain": "ecommerce",
            "input": f"create an order of {amount}",
            "expected_outcome": expected,
            "failure_mode": failure_mode,
        },
        "final_answer": f"Order created. ID 1, amount {amount}.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "Order 1 was created",
                "claim_type": "existence",
                "entities": {"order_id": 1},
            }
        ],
        "tool_trace": [],
        "structural_issues": (
            [{"action": "BLOCK", "rule_name": "amount_threshold", "reason": "x"}]
            if structural
            else []
        ),
        "executed_tools": ["create_order"],
        "db_state_after": [
            {"id": 1, "amount": float(amount), "status": "pending", "refund_reason": None}
        ],
        "db_seed": {},
        "error": None,
    }


def test_replay_is_deterministic():
    corpus = [_ecommerce_record("F2-G-001", "GATE_BLOCKED", "F2", structural=True, amount=8000)]
    first = replay_corpus(corpus, "V3_Intervention", verbose=False)[0]["scored_row"]
    second = replay_corpus(corpus, "V3_Intervention", verbose=False)[0]["scored_row"]
    assert first == second


def test_paired_structural_isolation():
    # The same frozen behaviour: structural-augmented catches the policy block,
    # the claim-only variant does not. The agent answer is identical for both.
    corpus = [_ecommerce_record("F2-G-001", "GATE_BLOCKED", "F2", structural=True, amount=8000)]
    v3 = replay_corpus(corpus, "V3_Intervention", verbose=False)[0]["state"]
    v3_nostruct = replay_corpus(corpus, "V3_NoStructural", verbose=False)[0]["state"]

    assert v3["reliability_verdict_audit"] == "BLOCK"
    # PASS-like under the coverage-aware split (PASS_VERIFIED / PASS_UNCHECKED, T5).
    assert v3_nostruct["reliability_verdict_audit"] in {
        "PASS",
        "PASS_VERIFIED",
        "PASS_UNCHECKED",
    }
    # The only difference is the structural verdict; the claim-pipeline score is shared.
    assert v3["reliability_score"] == v3_nostruct["reliability_score"]


def test_coverage_aware_pass_split():
    # Pure policy-engine logic (no DB): a PASS with grounded evidence is
    # PASS_VERIFIED; a PASS where the claim could not be checked is PASS_UNCHECKED.
    from src.reliableguard.intervention.policy_engine import decide_interventions
    from src.reliableguard.schema import Claim, RiskResult, VerificationResult

    claim = Claim(claim_id="c1", text="x", claim_type="existence")
    risks = {"c1": RiskResult(claim_id="c1", risk_level="low", score=0.0)}

    grounded = {"c1": VerificationResult(claim_id="c1", evidence_state="supported")}
    _, verdict_v = decide_interventions([claim], grounded, risks, reliability_score=1.0)
    assert verdict_v == "PASS_VERIFIED"

    ungrounded = {"c1": VerificationResult(claim_id="c1", evidence_state="unverifiable")}
    _, verdict_u = decide_interventions([claim], ungrounded, risks, reliability_score=1.0)
    assert verdict_u == "PASS_UNCHECKED"


def test_benign_record_passes_under_all_versions():
    corpus = [_ecommerce_record("F0-G-001", "SUCCESS", "F0", structural=False, amount=99)]
    for version in ("V2_AuditOnly", "V3_Intervention", "V3_NoStructural"):
        row = replay_corpus(corpus, version, verbose=False)[0]["scored_row"]
        assert row["actual_outcome"] == "PASS"
        assert row["pass_fail"] is True


def test_zero_claim_record_is_audit_failed_without_extraction():
    # Empty claims must NOT trigger a live extraction call; the pipeline fails closed.
    record = _ecommerce_record("F1-G-001", "GATE_BLOCKED", "F1", structural=False, amount=0)
    record["claims"] = []
    state = replay_corpus([record], "V3_Intervention", verbose=False)[0]["state"]
    assert state["reliability_verdict_audit"] == "AUDIT_FAILED"


def test_replay_carries_trace_summary_for_decomposition():
    corpus = [_ecommerce_record("F2-G-001", "GATE_BLOCKED", "F2", structural=True, amount=8000)]
    row = replay_corpus(corpus, "V2_AuditOnly", verbose=False)[0]["scored_row"]
    # build_result_row populates trace_summary from the replayed reliability_report.
    assert isinstance(row["trace_summary"], list)
    assert row["trace_summary"] and row["trace_summary"][0]["evidence_state"]
