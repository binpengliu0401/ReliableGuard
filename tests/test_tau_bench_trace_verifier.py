"""Phase 2 step 11: trajectory-level TRACE channel (`verify_trace`) over the retail wiki.md policy.

Pins the encoded rules (auth-before-action, status preconditions, call-once, modify-then-freeze,
single-user) and the channel gating: the trace channel is silent unless `channels.trace` is on, and
status preconditions additionally require `state_before`. The monitor reads only `tool_trace` +
`state_before` -- never the gold actions.
"""

from src.reliableguard.schema import (
    CHANNELS_ANSWER,
    CHANNELS_STRUCTURAL,
    ChannelConfig,
    Grounding,
    VerificationContext,
)
from src.reliableguard.verifier.tau_bench_verifiers import trace_verdict, verify_trace


def _ctx(trace, state_before=None, channels=CHANNELS_STRUCTURAL):  # noqa: ANN001
    return VerificationContext(
        grounding=Grounding(tool_trace=trace, state_before=state_before or {}),
        channels=channels,
    )


def _auth():
    return {"name": "find_user_id_by_email", "kwargs": {"email": "a@b.com"}}


def test_clean_trace_has_no_violations() -> None:
    trace = [
        _auth(),
        {"name": "get_order_details", "kwargs": {"order_id": "#W1"}},
        {"name": "cancel_pending_order", "kwargs": {"order_id": "#W1", "reason": "no longer needed"}},
    ]
    before = {"orders": {"#W1": {"status": "pending"}}}
    violations = verify_trace(_ctx(trace, before))
    assert violations == []
    assert trace_verdict(violations) == "PASS"


def test_answer_channel_does_not_consult_trace() -> None:
    trace = [{"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}}]  # unauthenticated
    assert verify_trace(_ctx(trace, channels=CHANNELS_ANSWER)) == []


def test_write_before_auth_flags_auth_rule() -> None:
    trace = [{"name": "cancel_pending_order", "kwargs": {"order_id": "#W1", "reason": "ordered by mistake"}}]
    before = {"orders": {"#W1": {"status": "pending"}}}
    violations = verify_trace(_ctx(trace, before))
    assert [v.rule for v in violations] == ["auth_before_action"]
    assert violations[0].step == 0 and violations[0].order_id == "#W1"
    assert trace_verdict(violations) == "BLOCK"


def test_cancel_non_pending_flags_status_precondition() -> None:
    trace = [_auth(), {"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}}]
    before = {"orders": {"#W1": {"status": "delivered"}}}
    rules = [v.rule for v in verify_trace(_ctx(trace, before))]
    assert rules == ["status_precondition"]


def test_return_requires_delivered() -> None:
    trace = [_auth(), {"name": "return_delivered_order_items", "kwargs": {"order_id": "#W1"}}]
    before = {"orders": {"#W1": {"status": "pending"}}}
    rules = [v.rule for v in verify_trace(_ctx(trace, before))]
    assert rules == ["status_precondition"]


def test_status_check_skipped_without_state_before() -> None:
    # trace channel on but no state_before -> precondition uncheckable, but auth still enforced
    trace = [_auth(), {"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}}]
    assert verify_trace(_ctx(trace, state_before=None)) == []


def test_exchange_called_twice_on_same_order() -> None:
    trace = [
        _auth(),
        {"name": "exchange_delivered_order_items", "kwargs": {"order_id": "#W1"}},
        {"name": "exchange_delivered_order_items", "kwargs": {"order_id": "#W1"}},
    ]
    before = {"orders": {"#W1": {"status": "delivered"}}}
    rules = [v.rule for v in verify_trace(_ctx(trace, before))]
    assert rules == ["called_twice"]


def test_modify_items_freezes_order_against_later_cancel() -> None:
    trace = [
        _auth(),
        {"name": "modify_pending_order_items", "kwargs": {"order_id": "#W1"}},
        {"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}},
    ]
    before = {"orders": {"#W1": {"status": "pending"}}}
    rules = [v.rule for v in verify_trace(_ctx(trace, before))]
    # the second modify_items would also be call-once, but here it's a cancel -> freeze rule
    assert rules == ["modify_after_freeze"]


def test_modify_items_twice_flags_both_once_and_freeze() -> None:
    trace = [
        _auth(),
        {"name": "modify_pending_order_items", "kwargs": {"order_id": "#W1"}},
        {"name": "modify_pending_order_items", "kwargs": {"order_id": "#W1"}},
    ]
    before = {"orders": {"#W1": {"status": "pending"}}}
    rules = {v.rule for v in verify_trace(_ctx(trace, before))}
    assert rules == {"called_twice", "modify_after_freeze"}


def test_serving_two_users_flags_multi_user() -> None:
    trace = [
        _auth(),
        {"name": "get_user_details", "kwargs": {"user_id": "u1"}},
        {"name": "get_user_details", "kwargs": {"user_id": "u2"}},
    ]
    violations = verify_trace(_ctx(trace))
    assert [v.rule for v in violations] == ["multi_user"]
    assert violations[0].step == -1


def test_order_id_normalized_without_hash() -> None:
    trace = [_auth(), {"name": "cancel_pending_order", "kwargs": {"order_id": "W1"}}]
    before = {"orders": {"#W1": {"status": "delivered"}}}  # stored with leading '#'
    rules = [v.rule for v in verify_trace(_ctx(trace, before))]
    assert rules == ["status_precondition"]  # 'W1' resolved to '#W1' and checked


def test_trace_disabled_via_explicit_flag() -> None:
    trace = [{"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}}]
    ctx = _ctx(trace, channels=ChannelConfig(answer=True, trace=False))
    assert verify_trace(ctx) == []
