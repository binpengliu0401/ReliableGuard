"""Phase 2 step 13: locus annotator.

Pins the rule-based priority chain and the two helper predicates. Also covers the
thesis-critical contracts: intent-local is the residual (reward<1.0, no detectable signal),
override bypasses rule logic for independent annotation studies, and reward=1.0 always
wins regardless of spurious violations in the inputs.
"""

from src.reliableguard.locus import (
    Locus,
    annotate_locus,
    locus_is_monitor_detectable,
    locus_needs_structural,
)
from src.reliableguard.schema import TraceViolation, VerificationResult


def _state_contradicted(claim_id: str = "c1") -> VerificationResult:
    return VerificationResult(
        claim_id=claim_id, evidence_state="contradicted", source="tau_bench_state", reason="mismatch"
    )


def _state_supported(claim_id: str = "c1") -> VerificationResult:
    return VerificationResult(
        claim_id=claim_id, evidence_state="supported", source="tau_bench_state", reason="ok"
    )


def _state_unverifiable(claim_id: str = "c1") -> VerificationResult:
    return VerificationResult(
        claim_id=claim_id, evidence_state="unverifiable", source=None, reason="answer-only"
    )


def _violation(rule: str = "auth_before_action") -> TraceViolation:
    return TraceViolation(rule=rule, action="cancel_pending_order", step=0)


# --- Priority chain ---

def test_reward_1_is_pass_regardless_of_other_signals() -> None:
    v = [_violation()]
    r = {"c1": _state_contradicted()}
    assert annotate_locus(1.0, v, r) == "pass"


def test_violations_beat_state_contradictions() -> None:
    r = {"c1": _state_contradicted()}
    assert annotate_locus(0.0, [_violation()], r) == "trace-local"


def test_state_contradiction_without_violations() -> None:
    assert annotate_locus(0.0, [], {"c1": _state_contradicted()}) == "state-local"


def test_residual_is_intent_local() -> None:
    assert annotate_locus(0.0, [], {}) == "intent-local"
    assert annotate_locus(0.0, [], {"c1": _state_unverifiable()}) == "intent-local"
    assert annotate_locus(0.0, [], {"c1": _state_supported()}) == "intent-local"


def test_partial_reward_follows_rule_logic() -> None:
    assert annotate_locus(0.5, [_violation()], {}) == "trace-local"
    assert annotate_locus(0.5, [], {"c1": _state_contradicted()}) == "state-local"
    assert annotate_locus(0.5, [], {}) == "intent-local"


def test_override_bypasses_all_rules() -> None:
    assert annotate_locus(0.0, [], {}, override="evidence-local") == "evidence-local"
    assert annotate_locus(1.0, [_violation()], {}, override="trace-local") == "trace-local"
    assert annotate_locus(0.0, [_violation()], {}, override="intent-local") == "intent-local"


def test_non_state_source_does_not_trigger_state_local() -> None:
    r = {"c1": VerificationResult(
        claim_id="c1", evidence_state="contradicted", source="some_other_source", reason="x"
    )}
    assert annotate_locus(0.0, [], r) == "intent-local"


def test_multiple_claims_any_contradiction_triggers_state_local() -> None:
    r = {
        "c1": _state_supported("c1"),
        "c2": _state_unverifiable("c2"),
        "c3": _state_contradicted("c3"),
    }
    assert annotate_locus(0.0, [], r) == "state-local"


# --- Helper predicates ---

def test_locus_is_monitor_detectable() -> None:
    assert locus_is_monitor_detectable("trace-local")
    assert locus_is_monitor_detectable("state-local")
    assert locus_is_monitor_detectable("evidence-local")
    assert locus_is_monitor_detectable("answer-local")
    assert not locus_is_monitor_detectable("pass")
    assert not locus_is_monitor_detectable("intent-local")


def test_locus_needs_structural() -> None:
    assert locus_needs_structural("trace-local")
    assert locus_needs_structural("state-local")
    assert not locus_needs_structural("answer-local")
    assert not locus_needs_structural("evidence-local")
    assert not locus_needs_structural("pass")
    assert not locus_needs_structural("intent-local")
