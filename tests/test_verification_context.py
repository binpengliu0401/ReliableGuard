"""Phase 1: grounding injection (decision B) plumbing.

Verifies that a VerificationContext (grounding + channels) threads through verify_claims to a
registered verifier, that the channel presets map to the three monitor configs, that a
Trajectory builds the context, and that the no-verifier / no-context paths are unchanged.
"""

from src.reliableguard.adapter import Trajectory
from src.reliableguard.schema import (
    CHANNELS_ANSWER,
    CHANNELS_EVIDENCE,
    CHANNELS_STRUCTURAL,
    ChannelConfig,
    Claim,
    VerificationContext,
    VerificationResult,
)
from src.reliableguard.verifier import source_verifier
from src.reliableguard.verifier.source_verifier import verify_claims


def _claim() -> Claim:
    return Claim(claim_id="c1", text="Order 1 is cancelled", claim_type="attribute")


def test_channel_presets_map_to_three_configs() -> None:
    assert (CHANNELS_ANSWER.answer, CHANNELS_ANSWER.state, CHANNELS_ANSWER.trace) == (
        True,
        False,
        False,
    )
    assert CHANNELS_STRUCTURAL.state and CHANNELS_STRUCTURAL.trace and not CHANNELS_STRUCTURAL.evidence
    assert CHANNELS_EVIDENCE.evidence and not CHANNELS_EVIDENCE.state


def test_default_context_is_answer_only_no_grounding() -> None:
    ctx = VerificationContext()
    assert ctx.grounding is None
    assert ctx.channels == ChannelConfig()  # answer-only
    assert ctx.channels.answer and not ctx.channels.state


def test_trajectory_builds_context_reusing_grounding() -> None:
    traj = Trajectory(
        task_id="3",
        domain="retail",
        model="m",
        state_after={"orders": {"1": {"status": "cancelled"}}},
        tool_trace=[{"name": "cancel_order", "kwargs": {"order_id": "1"}}],
        gold_reward=1.0,
    )
    g = traj.grounding()
    assert g.state_after == {"orders": {"1": {"status": "cancelled"}}}
    assert g.tool_trace[0]["name"] == "cancel_order"
    ctx = traj.verification_context(CHANNELS_STRUCTURAL)
    assert ctx.channels is CHANNELS_STRUCTURAL
    assert ctx.grounding.state_after == g.state_after


def test_unknown_domain_is_unverifiable_with_and_without_context() -> None:
    claims = [_claim()]
    verifiability = {"c1": "fully_verifiable"}
    for ctx in (None, VerificationContext(channels=CHANNELS_STRUCTURAL)):
        results = verify_claims("retail", claims, verifiability, ctx)
        assert results["c1"].evidence_state == "unverifiable"


def test_registered_verifier_receives_context() -> None:
    seen: dict[str, object] = {}

    def fake_verifier(claims, verifiability, context):  # noqa: ANN001
        seen["context"] = context
        return {
            c.claim_id: VerificationResult(claim_id=c.claim_id, evidence_state="supported")
            for c in claims
        }

    source_verifier._VERIFIERS["retail"] = fake_verifier
    try:
        ctx = VerificationContext(channels=CHANNELS_STRUCTURAL)
        results = verify_claims("retail", [_claim()], {"c1": "fully_verifiable"}, ctx)
        assert results["c1"].evidence_state == "supported"
        assert seen["context"] is ctx
        assert seen["context"].channels.state is True
    finally:
        del source_verifier._VERIFIERS["retail"]
