"""Phase 2: airline domain state + trace verifiers.

Pins the reservation-level state checks and the three airline-specific trace rules:
auth_before_action, basic_economy_no_flight_modify, baggage_only_increase.
"""

from src.reliableguard.schema import (
    CHANNELS_ANSWER,
    CHANNELS_STRUCTURAL,
    Claim,
    Grounding,
    VerificationContext,
)
from src.reliableguard.verifier.tau_bench_verifiers import (
    airline_verifier,
    register_tau_bench_verifiers,
    verify_trace,
)
from src.reliableguard.verifier.source_verifier import verify_claims

RESERVATION = {
    "reservations": {
        "4WQ150": {
            "reservation_id": "4WQ150",
            "user_id": "u1",
            "cabin": "business",
            "total_baggages": 4,
            "nonfree_baggages": 0,
            "insurance": "yes",
            "flights": [{"flight_number": "HAT170"}],
            "passengers": [{"first_name": "A"}],
            "payment_history": [],
        },
        "BASIC1": {
            "reservation_id": "BASIC1",
            "user_id": "u1",
            "cabin": "basic_economy",
            "total_baggages": 1,
            "nonfree_baggages": 1,
            "insurance": "no",
            "flights": [],
            "passengers": [],
            "payment_history": [],
        },
    }
}


def _claim(text: str, claim_id: str = "c1", attribute: str = "", value: str = "") -> Claim:
    return Claim(
        claim_id=claim_id, text=text, claim_type="attribute",
        attribute=attribute, value=value,
        entities={"reservation_id": text.split()[0] if text[:6].isalnum() else ""},
    )


def _ctx_state(state_after: dict, channels=CHANNELS_STRUCTURAL):
    return VerificationContext(
        grounding=Grounding(state_after=state_after, state_before={}, tool_trace=[]),
        channels=channels,
    )


def _trace_ctx(trace, state_before=None):
    return VerificationContext(
        grounding=Grounding(tool_trace=trace, state_before=state_before or {}),
        channels=CHANNELS_STRUCTURAL,
    )


# --- State verifier ---

def test_state_existence_claim_found() -> None:
    c = Claim(claim_id="c1", text="Reservation 4WQ150 was booked", claim_type="existence",
              entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


def test_state_reservation_not_found() -> None:
    c = Claim(claim_id="c1", text="Your reservation ZZZZZZ is confirmed", claim_type="existence",
              entities={"reservation_id": "ZZZZZZ"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "not_found"


def test_state_cancellation_supported_when_absent() -> None:
    state_without_reservation = {"reservations": {}}
    c = Claim(claim_id="c1", text="Reservation 4WQ150 has been cancelled", claim_type="attribute",
              attribute="status", entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(state_without_reservation)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


def test_state_cancellation_supported_when_status_cancelled() -> None:
    state = {"reservations": {"4WQ150": {**RESERVATION["reservations"]["4WQ150"], "status": "cancelled"}}}
    c = Claim(claim_id="c1", text="I cancelled reservation 4WQ150", claim_type="attribute",
              attribute="status", entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(state)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


def test_state_cancellation_contradicted_when_active() -> None:
    c = Claim(claim_id="c1", text="Reservation 4WQ150 is cancelled", claim_type="attribute",
              attribute="status", entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "contradicted"


def test_state_cabin_claim_supported() -> None:
    c = Claim(claim_id="c1", text="Your reservation 4WQ150 is in business class",
              claim_type="attribute", attribute="cabin", value="business",
              entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


def test_state_cabin_claim_contradicted() -> None:
    c = Claim(claim_id="c1", text="Reservation 4WQ150 is economy class",
              claim_type="attribute", attribute="cabin", value="economy",
              entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "contradicted"


def test_state_baggage_claim_supported() -> None:
    c = Claim(claim_id="c1", text="4WQ150 now has 4 checked bags", claim_type="numeric",
              attribute="total_baggages", value="4", entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


def test_state_answer_only_returns_unverifiable() -> None:
    c = Claim(claim_id="c1", text="Reservation 4WQ150 is in business class",
              claim_type="attribute", entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION, channels=CHANNELS_ANSWER)
    results = airline_verifier([c], {}, ctx)
    assert results["c1"].evidence_state == "unverifiable"


def test_register_airline_verifier_routes_correctly() -> None:
    register_tau_bench_verifiers()
    c = Claim(claim_id="c1", text="Reservation 4WQ150 exists", claim_type="existence",
              entities={"reservation_id": "4WQ150"})
    ctx = _ctx_state(RESERVATION)
    results = verify_claims("airline", [c], {}, ctx)
    assert results["c1"].evidence_state == "supported"


# --- Trace verifier ---

def _auth():
    return {"name": "get_user_details", "kwargs": {"user_id": "u1"}}


def test_clean_airline_trace_no_violations() -> None:
    trace = [
        _auth(),
        {"name": "get_reservation_details", "kwargs": {"reservation_id": "4WQ150"}},
        {"name": "cancel_reservation", "kwargs": {"reservation_id": "4WQ150"}},
    ]
    violations = verify_trace(_trace_ctx(trace), domain="airline")
    assert violations == []


def test_airline_write_before_auth() -> None:
    trace = [{"name": "cancel_reservation", "kwargs": {"reservation_id": "4WQ150"}}]
    violations = verify_trace(_trace_ctx(trace), domain="airline")
    assert [v.rule for v in violations] == ["auth_before_action"]


def test_basic_economy_no_flight_modify() -> None:
    trace = [
        _auth(),
        {"name": "update_reservation_flights", "kwargs": {"reservation_id": "BASIC1", "cabin": "economy", "flights": []}},
    ]
    violations = verify_trace(_trace_ctx(trace, RESERVATION), domain="airline")
    rules = [v.rule for v in violations]
    assert "basic_economy_no_flight_modify" in rules


def test_business_cabin_flight_modify_allowed() -> None:
    trace = [
        _auth(),
        {"name": "update_reservation_flights", "kwargs": {"reservation_id": "4WQ150", "cabin": "business", "flights": []}},
    ]
    violations = verify_trace(_trace_ctx(trace, RESERVATION), domain="airline")
    assert all(v.rule != "basic_economy_no_flight_modify" for v in violations)


def test_baggage_decrease_forbidden() -> None:
    trace = [
        _auth(),
        {"name": "update_reservation_baggages", "kwargs": {"reservation_id": "4WQ150", "total_baggages": 2, "nonfree_baggages": 0}},
    ]
    violations = verify_trace(_trace_ctx(trace, RESERVATION), domain="airline")
    rules = [v.rule for v in violations]
    assert "baggage_only_increase" in rules


def test_baggage_increase_allowed() -> None:
    trace = [
        _auth(),
        {"name": "update_reservation_baggages", "kwargs": {"reservation_id": "4WQ150", "total_baggages": 6, "nonfree_baggages": 2}},
    ]
    violations = verify_trace(_trace_ctx(trace, RESERVATION), domain="airline")
    assert all(v.rule != "baggage_only_increase" for v in violations)


def test_airline_trace_channel_off_returns_empty() -> None:
    trace = [{"name": "cancel_reservation", "kwargs": {"reservation_id": "4WQ150"}}]
    ctx = VerificationContext(
        grounding=Grounding(tool_trace=trace, state_before={}),
        channels=CHANNELS_ANSWER,
    )
    assert verify_trace(ctx, domain="airline") == []


def test_retail_rules_not_triggered_by_airline_domain() -> None:
    # find_user_id_by_email is a RETAIL auth tool; calling it with domain="airline" should
    # not count as authentication for airline (get_user_details is the airline auth tool).
    trace = [
        {"name": "find_user_id_by_email", "kwargs": {"email": "x@y.com"}},
        {"name": "cancel_reservation", "kwargs": {"reservation_id": "4WQ150"}},
    ]
    violations = verify_trace(_trace_ctx(trace), domain="airline")
    assert any(v.rule == "auth_before_action" for v in violations)
