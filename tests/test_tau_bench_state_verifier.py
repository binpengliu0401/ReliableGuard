"""Phase 2: retail STATE verifier (state-local channel).

Synthetic `state_after` + claims pin the contract deterministically (zero API): a claim is
supported / contradicted / not_found / unverifiable against the agent-final DB, and the state
channel is consulted only when `channels.state` is on (V_structural), not for V_answer.
"""

from src.reliableguard.adapter import Trajectory
from src.reliableguard.schema import CHANNELS_ANSWER, CHANNELS_STRUCTURAL, Claim
from src.reliableguard.verifier import source_verifier
from src.reliableguard.verifier.source_verifier import verify_claims
from src.reliableguard.verifier.tau_bench_verifiers import register_tau_bench_verifiers

STATE = {
    "orders": {
        "#W100": {
            "order_id": "#W100",
            "status": "cancelled",
            "payment_history": [
                {"transaction_type": "payment", "amount": 45.0, "payment_method_id": "pp_1"},
                {"transaction_type": "refund", "amount": 45.0, "payment_method_id": "pp_1"},
            ],
        },
        "#W200": {
            "order_id": "#W200",
            "status": "pending",
            "payment_history": [
                {"transaction_type": "payment", "amount": 99.0, "payment_method_id": "pp_2"}
            ],
        },
        # delivered then exchange requested: "has been delivered" is historically true here
        "#W300": {"order_id": "#W300", "status": "exchange requested", "payment_history": []},
    }
}


def _traj() -> Trajectory:
    return Trajectory(task_id="t", domain="retail", model="m", state_after=STATE)


def _claim(text: str, **kw) -> Claim:  # noqa: ANN003
    kw.setdefault("claim_type", "attribute")
    return Claim(claim_id="c1", text=text, **kw)


def _verify(claim: Claim, channels) -> str:  # noqa: ANN001
    register_tau_bench_verifiers()
    ctx = _traj().verification_context(channels)
    return verify_claims("retail", [claim], {claim.claim_id: "fully_verifiable"}, ctx)["c1"].evidence_state


def test_status_supported_when_db_matches() -> None:
    c = _claim("Order #W100 is cancelled", entities={"order_id": "#W100"}, attribute="status", value="cancelled")
    assert _verify(c, CHANNELS_STRUCTURAL) == "supported"


def test_status_contradicted_when_db_differs() -> None:
    # agent claims cancelled, but #W200 is pending -> the state-local lie V_answer cannot catch
    c = _claim("Order #W200 is now cancelled", entities={"order_id": "#W200"}, attribute="status", value="cancelled")
    assert _verify(c, CHANNELS_STRUCTURAL) == "contradicted"


def test_order_not_found() -> None:
    c = _claim("Order #W999 is delivered", entities={"order_id": "#W999"}, attribute="status", value="delivered")
    assert _verify(c, CHANNELS_STRUCTURAL) == "not_found"


def test_refund_supported_with_matching_amount() -> None:
    c = _claim("A $45.00 refund was issued for order #W100", attribute="refund_amount", value=45.0)
    assert _verify(c, CHANNELS_STRUCTURAL) == "supported"


def test_refund_not_found_when_absent() -> None:
    # claimed refund with no record -> not_found (softer than contradicted; may be out-of-band)
    c = _claim("A refund was issued for order #W200", attribute="refund", value=None)
    assert _verify(c, CHANNELS_STRUCTURAL) == "not_found"


def test_status_historical_milestone_supported() -> None:
    # agent says "delivered"; order is now "exchange requested" (reached via delivered) -> supported
    c = _claim("Order #W300 has been delivered", attribute="status", value="delivered")
    assert _verify(c, CHANNELS_STRUCTURAL) == "supported"


def test_status_future_claim_contradicted() -> None:
    # agent claims delivered, but #W200 is still pending -> the effect was not realized
    c = _claim("Order #W200 has been delivered", attribute="status", value="delivered")
    assert _verify(c, CHANNELS_STRUCTURAL) == "contradicted"


def test_multi_order_claim_is_unverifiable() -> None:
    c = _claim("Your orders #W100 and #W200 are ready", attribute="status", value="ready")
    assert _verify(c, CHANNELS_STRUCTURAL) == "unverifiable"


def test_order_id_parsed_from_text_when_entities_empty() -> None:
    c = _claim("I cancelled order #W100 for you", attribute="status", value="cancelled")
    assert _verify(c, CHANNELS_STRUCTURAL) == "supported"


def test_unverifiable_when_no_order_id() -> None:
    c = _claim("Your refund will arrive in 5 days", attribute="refund_duration", value="5")
    assert _verify(c, CHANNELS_STRUCTURAL) == "unverifiable"


def test_answer_channel_does_not_consult_state() -> None:
    # same contradicting claim, but V_answer (state off) must not reach the DB -> unverifiable
    c = _claim("Order #W200 is now cancelled", entities={"order_id": "#W200"}, attribute="status", value="cancelled")
    assert _verify(c, CHANNELS_ANSWER) == "unverifiable"


def teardown_module(module) -> None:  # noqa: ANN001, ARG001
    source_verifier._VERIFIERS.pop("retail", None)
