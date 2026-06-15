"""tau-bench domain verifiers, registered into `source_verifier._VERIFIERS`.

Each domain verifier is channel-gated by `context.channels`: it consults a channel only when that
flag is on, so the SAME claims + grounding yield V_answer / V_structural verdicts. This module adds
the retail STATE channel (claims vs `state_after`, the agent-final DB dict captured before the reward
step) and the retail TRACE channel (`verify_trace`: `tool_trace` + `state_before` vs `wiki.md`
policy, a trajectory-level check).

All checks are pure local dict operations on `state_after` -- no database engine, no network. The
data is tau-bench's own (orders/products/users JSON loaded into `env.data`), never a gold annotation.

Status checks respect the wiki.md order lifecycle so a true *historical* statement is not flagged:
  pending -> processed -> delivered -> {return requested | exchange requested}
  pending -> cancelled ;  pending -> "pending (items modifed)"
A claim of an earlier milestone than the current status (e.g. "delivered" when now "exchange
requested") is SUPPORTED (the milestone was reached); a claim of a later/incompatible status is
CONTRADICTED (the claimed effect was not realized).
"""

from __future__ import annotations

import re
from typing import Any

from src.reliableguard.schema import (
    Claim,
    TraceViolation,
    Verifiability,
    VerificationContext,
    VerificationResult,
)
from src.reliableguard.verifier import source_verifier

_ORDER_RE = re.compile(r"#?W\d{2,}", re.I)
_AMOUNT_RE = re.compile(r"\$?\s*(\d+(?:\.\d{1,2})?)")

# Forward reachability over the retail order lifecycle: status -> states reachable by progression.
_REACHABLE: dict[str, set[str]] = {
    "pending": {
        "processed", "delivered", "return requested", "exchange requested",
        "cancelled", "pending (items modifed)",
    },
    "processed": {"delivered", "return requested", "exchange requested"},
    "delivered": {"return requested", "exchange requested"},
    "cancelled": set(),
    "return requested": set(),
    "exchange requested": set(),
    "pending (items modifed)": set(),
}
# Recognised status phrases, longest first so "exchange requested" wins over "requested".
_STATUS_PHRASES = sorted(_REACHABLE, key=len, reverse=True)


def _norm_status(value: str) -> str:
    value = value.strip().lower()
    # tolerate the corrected spelling of the data's "pending (items modifed)" typo
    return "pending (items modifed)" if value.startswith("pending (item") else value


def _order_id_from_claim(claim: Claim) -> str | None:
    """Resolve the single retail order id a claim is about. A multi-order claim (a list entity or
    several distinct ids in the text) is not a single-order assertion -> return None (unverifiable)."""
    entities = claim.entities or {}
    for key in ("order_id", "order", "id"):
        value = entities.get(key)
        if isinstance(value, (list, tuple, set)):
            return None
        if value:
            text = str(value)
            return text if text.startswith("#") else "#" + text.lstrip("#")
    ids = {("#" + m.lstrip("#")).upper() for m in _ORDER_RE.findall(claim.text or "")}
    return next(iter(ids)) if len(ids) == 1 else None


def _result(claim: Claim, state: str, *, value: Any = None, reason: str) -> VerificationResult:
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state=state,  # type: ignore[arg-type]
        evidence_value=value,
        source="tau_bench_state",
        reason=reason,
    )


def _claimed_status(claim: Claim) -> str | None:
    candidate = _norm_status(str(claim.value or ""))
    if candidate in _REACHABLE:
        return candidate
    text = (claim.text or "").lower()
    for phrase in _STATUS_PHRASES:
        if phrase in text:
            return phrase
    return None


def _claimed_amount(claim: Claim) -> float | None:
    if isinstance(claim.value, (int, float)):
        return float(claim.value)
    match = _AMOUNT_RE.search(str(claim.value or "")) or _AMOUNT_RE.search(claim.text or "")
    return float(match.group(1)) if match else None


def _status_relation(claimed: str, actual: str) -> str:
    """supported if the claimed status equals or is an earlier milestone of the actual one;
    contradicted if it claims a later/incompatible status (effect not realized)."""
    if claimed == actual or actual in _REACHABLE.get(claimed, set()):
        return "supported"
    return "contradicted"


def _check_state_retail(
    claim: Claim,
    state_after: dict[str, Any],
    state_before: dict[str, Any] | None = None,
) -> VerificationResult:
    orders = state_after.get("orders", {})
    order_id = _order_id_from_claim(claim)
    if order_id is None:
        return _result(claim, "unverifiable", reason="no single order id resolvable from claim")
    order = orders.get(order_id)
    if order is None:
        return _result(claim, "not_found", reason=f"order {order_id} absent from state_after")

    text = (claim.text or "").lower()
    attribute = (claim.attribute or "").lower()

    # Refund claim: a claimed refund must appear in payment_history (with the right amount).
    if "refund" in attribute or "refund" in text:
        refunds = [
            p for p in order.get("payment_history", []) if p.get("transaction_type") == "refund"
        ]
        if not refunds:
            return _result(
                claim, "not_found",
                reason=f"claimed refund but none recorded in {order_id} payment_history",
            )
        amount = _claimed_amount(claim)
        if amount is None:
            return _result(claim, "supported", reason=f"refund present on {order_id}")
        if any(abs(float(p.get("amount", 0)) - amount) <= 0.01 for p in refunds):
            return _result(claim, "supported", value=amount, reason=f"refund ${amount} matches")
        # Amount mismatch: check whether the claimed figure is an item price from state_before
        # (extractor often captures item prices during exchange conversations as refund claims).
        if state_before is not None:
            order_before = state_before.get("orders", {}).get(order_id, {})
            item_prices = {
                round(float(item.get("price", 0)), 2)
                for item in order_before.get("items", [])
                if item.get("price") is not None
            }
            if any(abs(price - amount) <= 0.01 for price in item_prices):
                return _result(
                    claim, "unverifiable",
                    reason=f"claimed amount ${amount} matches an item price in {order_id}; not a refund figure",
                )
        return _result(
            claim, "not_found", value=[p.get("amount") for p in refunds],
            reason=f"claimed refund ${amount} != recorded refunds on {order_id} (amount unconfirmed)",
        )

    # Status claim: compare against the actual status, respecting the lifecycle.
    claimed = _claimed_status(claim)
    if claimed is not None and (attribute in {"status", "order_status"} or claimed in text):
        actual = _norm_status(str(order.get("status", "")))
        state = _status_relation(claimed, actual)
        reason = (
            f"{order_id} status={actual}; claimed '{claimed}'"
            if state == "supported"
            else f"claimed status '{claimed}' but {order_id} is '{actual}'"
        )
        return _result(claim, state, value=actual, reason=reason)

    if claim.claim_type == "existence":
        return _result(claim, "supported", value=order_id, reason=f"{order_id} exists")

    return _result(claim, "unverifiable", reason="claim attribute not checkable against state")


def retail_verifier(
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
    context: VerificationContext,
) -> dict[str, VerificationResult]:
    """Retail verifier, channel-gated. STATE channel: claims vs `state_after`."""
    grounding = context.grounding
    state_after = grounding.state_after if grounding is not None else None
    state_before = grounding.state_before if grounding is not None else None
    results: dict[str, VerificationResult] = {}
    for claim in claims:
        if context.channels.state and state_after is not None:
            results[claim.claim_id] = _check_state_retail(claim, state_after, state_before)
        else:
            results[claim.claim_id] = _result(
                claim, "unverifiable", reason="answer-only: state channel not consulted"
            )
    return results


# --- TRACE channel (trajectory-level): tool_trace + state_before vs wiki.md policy ------------
#
# Unlike the state verifier (per-claim), the trace channel audits the *sequence of actions* against
# the retail policy. It encodes only rules decidable from the observable trace -- the tool name, its
# kwargs, and (for preconditions) the order's status in `state_before`. Rules that need the dialogue
# (e.g. "obtain explicit user confirmation (yes)") are NOT encoded here: `tool_trace` carries no
# observations/user turns, so encoding them would only manufacture false positives. The realized
# effect is covered separately by the state channel; this channel covers the *process*.

# Consequential tools that write the DB (wiki: "cancel, modify, return, exchange").
_WRITE_TOOLS = {
    "cancel_pending_order",
    "modify_pending_order_address",
    "modify_pending_order_items",
    "modify_pending_order_payment",
    "return_delivered_order_items",
    "exchange_delivered_order_items",
    "modify_user_address",
}
# Authentication tools (wiki: locate the user id by email, or name + zip, before anything).
_AUTH_TOOLS = {"find_user_id_by_email", "find_user_id_by_name_zip"}
# Precondition: an order-status the order must hold in `state_before` for the action to be legal.
_REQUIRES_STATUS = {
    "cancel_pending_order": "pending",
    "modify_pending_order_address": "pending",
    "modify_pending_order_items": "pending",
    "modify_pending_order_payment": "pending",
    "return_delivered_order_items": "delivered",
    "exchange_delivered_order_items": "delivered",
}
# Tools the wiki says may be called at most once (per order).
_ONCE_TOOLS = {"modify_pending_order_items", "exchange_delivered_order_items"}
# After this action an order is frozen: "the agent will not be able to modify or cancel it anymore".
_FREEZE_TOOL = "modify_pending_order_items"
_FROZEN_FORBIDS = {
    "cancel_pending_order",
    "modify_pending_order_address",
    "modify_pending_order_items",
    "modify_pending_order_payment",
}


def _norm_order_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if text.startswith("#") else "#" + text.lstrip("#")


def _verify_trace_retail(context: VerificationContext) -> list[TraceViolation]:
    trace = context.grounding.tool_trace or []  # type: ignore[union-attr]
    state_before = context.grounding.state_before or {}  # type: ignore[union-attr]
    orders_before = state_before.get("orders", {})

    violations: list[TraceViolation] = []
    authenticated = False
    once_seen: dict[str, set[str]] = {tool: set() for tool in _ONCE_TOOLS}
    frozen_orders: set[str] = set()
    user_ids: set[str] = set()

    for step, action in enumerate(trace):
        name = action.get("name", "")
        kwargs = action.get("kwargs", {}) or {}
        order_id = _norm_order_id(kwargs.get("order_id"))
        if kwargs.get("user_id"):
            user_ids.add(str(kwargs["user_id"]))

        if name in _AUTH_TOOLS:
            authenticated = True
            continue
        if name not in _WRITE_TOOLS:
            continue

        if not authenticated:
            violations.append(TraceViolation(
                rule="auth_before_action", action=name, step=step, order_id=order_id,
                reason="consequential action taken before authenticating the user",
            ))

        required = _REQUIRES_STATUS.get(name)
        if required is not None and order_id is not None and order_id in orders_before:
            actual = _norm_status(str(orders_before[order_id].get("status", "")))
            if actual != required:
                violations.append(TraceViolation(
                    rule="status_precondition", action=name, step=step, order_id=order_id,
                    reason=f"{name} requires status '{required}' but {order_id} was '{actual}'",
                ))

        if order_id is not None and order_id in frozen_orders and name in _FROZEN_FORBIDS:
            violations.append(TraceViolation(
                rule="modify_after_freeze", action=name, step=step, order_id=order_id,
                reason=f"{order_id} was item-modified (frozen); {name} can no longer touch it",
            ))

        if name in _ONCE_TOOLS and order_id is not None:
            if order_id in once_seen[name]:
                violations.append(TraceViolation(
                    rule="called_twice", action=name, step=step, order_id=order_id,
                    reason=f"{name} may be called at most once per order; {order_id} repeated",
                ))
            once_seen[name].add(order_id)

        if name == _FREEZE_TOOL and order_id is not None:
            frozen_orders.add(order_id)

    if len(user_ids) > 1:
        violations.append(TraceViolation(
            rule="multi_user", action="(trajectory)", step=-1, order_id=None,
            reason=f"served more than one user in one conversation: {sorted(user_ids)}",
        ))
    return violations


# --- Airline state verifier -------------------------------------------------------------------
#
# Airline reservations have no lifecycle status (unlike retail orders). Active reservations have no
# "status" key; cancelled ones get `status="cancelled"`. Key checkable fields: `cabin`,
# `total_baggages`, `insurance`. Reservation IDs are 6-char uppercase alphanumeric strings.

_RESERVATION_RE = re.compile(r"\b[A-Z0-9]{6}\b")
_CABIN_PHRASES = {"basic_economy", "economy", "business"}
_CABIN_ALIASES: dict[str, str] = {
    "basic economy": "basic_economy",
    "basic": "basic_economy",
}


def _norm_reservation_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if re.fullmatch(r"[A-Z0-9]{6}", text) else None


def _reservation_id_from_claim(claim: Claim) -> str | None:
    entities = claim.entities or {}
    for key in ("reservation_id", "reservation", "id"):
        value = entities.get(key)
        if isinstance(value, (list, tuple, set)):
            return None
        rid = _norm_reservation_id(value)
        if rid:
            return rid
    ids = {m.group() for m in _RESERVATION_RE.finditer(claim.text or "")}
    return next(iter(ids)) if len(ids) == 1 else None


def _norm_cabin(value: str) -> str:
    text = value.strip().lower()
    return _CABIN_ALIASES.get(text, text.replace(" ", "_"))


def _claimed_cabin(claim: Claim) -> str | None:
    candidate = _norm_cabin(str(claim.value or ""))
    if candidate in _CABIN_PHRASES:
        return candidate
    text = (claim.text or "").lower()
    # longest-first to avoid "economy" matching inside "basic_economy"
    for phrase in sorted(_CABIN_PHRASES, key=len, reverse=True):
        if phrase in text:
            return phrase
    return None


def _check_state_airline(
    claim: Claim,
    state_after: dict[str, Any],
    state_before: dict[str, Any] | None = None,
) -> VerificationResult:
    reservations = state_after.get("reservations", {})
    rid = _reservation_id_from_claim(claim)
    if rid is None:
        return _result(claim, "unverifiable", reason="no single reservation id resolvable from claim")

    reservation = reservations.get(rid)
    text = (claim.text or "").lower()
    attribute = (claim.attribute or "").lower()

    if reservation is None:
        if "cancel" in text or attribute in {"status", "cancelled"}:
            return _result(claim, "supported", value="absent",
                           reason=f"{rid} absent from state_after (cancelled)")
        return _result(claim, "not_found", reason=f"reservation {rid} absent from state_after")

    # Cancellation claim on a present reservation: must have status="cancelled".
    if "cancel" in text or attribute in {"status", "cancelled"}:
        actual_status = reservation.get("status", "active")
        if actual_status == "cancelled":
            return _result(claim, "supported", value="cancelled", reason=f"{rid} is cancelled")
        return _result(claim, "contradicted", value=actual_status,
                       reason=f"claimed cancelled but {rid} status={actual_status!r}")

    # Cabin claim.
    claimed = _claimed_cabin(claim)
    if claimed is not None and (attribute in {"cabin", "cabin_class"} or claimed in text):
        actual = _norm_cabin(str(reservation.get("cabin", "")))
        # "economy" is colloquially used by agents for "basic_economy" reservations; not a factual
        # error — the reservation is still an economy-class product.
        if claimed == actual or (actual == "basic_economy" and claimed == "economy"):
            state = "supported"
        else:
            state = "contradicted"
        reason = (
            f"{rid} cabin={actual}" if state == "supported"
            else f"claimed cabin '{claimed}' but {rid} cabin='{actual}'"
        )
        return _result(claim, state, value=actual, reason=reason)

    # Baggage count claim.
    if "bag" in attribute or "bag" in text:
        claimed_bags = _claimed_amount(claim)
        if claimed_bags is not None:
            actual_bags = reservation.get("total_baggages")
            if actual_bags is None:
                return _result(claim, "not_found", reason=f"no baggages field on {rid}")
            if abs(float(actual_bags) - claimed_bags) <= 0.5:
                return _result(claim, "supported", value=actual_bags, reason=f"{rid} has {actual_bags} bags")
            # Count mismatch: check if the claimed figure is the delta (bags added/removed) rather
            # than the final total, using state_before to compute the session delta.
            if state_before is not None:
                prev_bags = state_before.get("reservations", {}).get(rid, {}).get("total_baggages")
                if prev_bags is not None:
                    delta = float(actual_bags) - float(prev_bags)
                    if abs(claimed_bags - delta) <= 0.5:
                        return _result(
                            claim, "supported", value=actual_bags,
                            reason=f"{rid} bags: added {delta:.0f} (delta matches claimed {claimed_bags:.0f})",
                        )
            return _result(claim, "not_found", value=actual_bags,
                           reason=f"claimed {claimed_bags} bags but {rid} has {actual_bags} (count unconfirmed)")

    if claim.claim_type == "existence":
        return _result(claim, "supported", value=rid, reason=f"{rid} exists")

    return _result(claim, "unverifiable", reason="claim attribute not checkable against state")


def airline_verifier(
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
    context: VerificationContext,
) -> dict[str, VerificationResult]:
    """Airline verifier, channel-gated. STATE channel: claims vs reservation `state_after`."""
    grounding = context.grounding
    state_after = grounding.state_after if grounding is not None else None
    state_before = grounding.state_before if grounding is not None else None
    results: dict[str, VerificationResult] = {}
    for claim in claims:
        if context.channels.state and state_after is not None:
            results[claim.claim_id] = _check_state_airline(claim, state_after, state_before)
        else:
            results[claim.claim_id] = _result(
                claim, "unverifiable", reason="answer-only: state channel not consulted"
            )
    return results


# --- Airline TRACE channel -------------------------------------------------------------------
#
# Feasible rules from name+kwargs+state_before only:
# - auth_before_action: get_user_details must precede all write ops (wiki: "must first obtain
#   the user id" before booking, modifying, or cancelling)
# - basic_economy_no_flight_modify: update_reservation_flights on a basic_economy reservation
#   (wiki: "Basic economy flights cannot be modified")
# - baggage_only_increase: update_reservation_baggages where new total < old total
#   (wiki: "The user can add but not remove checked bags")
#
# NOT encoded: confirm-before-write (needs observation strings), cancellation eligibility checks
# (need booking time + cabin + insurance -- complex to evaluate from state_before alone without
# reproducing the full eligibility logic; any error would manufacture false positives).

_AIRLINE_WRITE_TOOLS = {
    "book_reservation",
    "cancel_reservation",
    "update_reservation_flights",
    "update_reservation_baggages",
    "update_reservation_passengers",
    "send_certificate",
}
_AIRLINE_AUTH_TOOL = "get_user_details"


def _verify_trace_airline(context: VerificationContext) -> list[TraceViolation]:
    trace = context.grounding.tool_trace or []  # type: ignore[union-attr]
    state_before = context.grounding.state_before or {}  # type: ignore[union-attr]
    reservations_before = state_before.get("reservations", {})

    violations: list[TraceViolation] = []
    authenticated = False

    for step, action in enumerate(trace):
        name = action.get("name", "")
        kwargs = action.get("kwargs", {}) or {}
        rid = _norm_reservation_id(kwargs.get("reservation_id"))

        if name == _AIRLINE_AUTH_TOOL:
            authenticated = True
            continue
        if name not in _AIRLINE_WRITE_TOOLS:
            continue

        if not authenticated:
            violations.append(TraceViolation(
                rule="auth_before_action", action=name, step=step, order_id=rid,
                reason="consequential action taken before identifying the user via get_user_details",
            ))

        if name == "update_reservation_flights" and rid is not None and rid in reservations_before:
            cabin = str(reservations_before[rid].get("cabin", "")).strip().lower()
            if cabin == "basic_economy":
                violations.append(TraceViolation(
                    rule="basic_economy_no_flight_modify", action=name, step=step, order_id=rid,
                    reason=f"{rid} is basic_economy; flight changes are forbidden by policy",
                ))

        if name == "update_reservation_baggages" and rid is not None and rid in reservations_before:
            old_total = reservations_before[rid].get("total_baggages")
            new_total = kwargs.get("total_baggages")
            if old_total is not None and new_total is not None and int(new_total) < int(old_total):
                violations.append(TraceViolation(
                    rule="baggage_only_increase", action=name, step=step, order_id=rid,
                    reason=(
                        f"{rid}: new total_baggages={new_total} < old {old_total}; "
                        "policy only allows adding, not removing bags"
                    ),
                ))

    return violations


def verify_trace(context: VerificationContext, *, domain: str = "retail") -> list[TraceViolation]:
    """Trajectory-level trace audit: return the `wiki.md` policy violations in `tool_trace`. Reads
    only the observable trace and `state_before` (never gold actions / reward). Empty list = clean.

    Gated on `context.channels.trace`; status-precondition checks additionally require
    `state_before` (present in the V_structural preset, which turns state + trace on together).
    `domain` selects the domain-specific rule set ("retail" or "airline").
    """
    if not context.channels.trace or context.grounding is None:
        return []
    if domain == "airline":
        return _verify_trace_airline(context)
    return _verify_trace_retail(context)


def trace_verdict(violations: list[TraceViolation]) -> str:
    """The trace channel's contribution to the V_structural verdict: BLOCK if any policy violation,
    else PASS. The trajectory verdict is max(claim-level verdict, this) -- a clean answer that was
    produced by a policy-violating process is still escalated."""
    return "BLOCK" if violations else "PASS"


def register_tau_bench_verifiers() -> None:
    """Register the tau-bench domain verifiers. Explicit (no import-time global mutation)."""
    source_verifier._VERIFIERS["retail"] = retail_verifier
    source_verifier._VERIFIERS["airline"] = airline_verifier
