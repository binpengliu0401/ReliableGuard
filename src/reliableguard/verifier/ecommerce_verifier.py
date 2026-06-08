from __future__ import annotations

from typing import Any

from src.domain.ecommerce.tools import cursor
from src.reliableguard.schema import Claim, VerificationResult, Verifiability


# Status attributes whose value can legitimately change across a multi-step task
# (e.g. an order is created `pending`, then `confirmed`). The transition encoder
# attribute carries the trajectory itself (value like "pending->confirmed").
_STATUS_ATTRS = {"status", "payment_status"}
_TRANSITION_ATTRS = {"status_transition", "state_transition"}


def verify_ecommerce_claims(
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
) -> dict[str, VerificationResult]:
    """Ecommerce batch verifier with transition-aware state verification.

    Computes the per-claim baseline first (identical to the legacy path), then makes a
    joint judgment over the status claims of each order. The verifier checks every claim
    against the FINAL database snapshot, but a multi-step answer legitimately narrates
    intermediate states ("created as pending, then confirmed"). Comparing the
    intermediate `pending` claim to the final `confirmed` row yields a spurious
    `contradicted` -> BLOCK. When the answer's narrated end state matches the database,
    the intermediate state claims are reclassified `unverifiable` (a past state a single
    snapshot cannot confirm) instead of contradicted -- removing the false BLOCK while
    keeping detection: if the narrated end state disagrees with the database, every claim
    keeps its baseline result.
    """
    results: dict[str, VerificationResult] = {}
    for claim in claims:
        level = verifiability.get(claim.claim_id, "unverifiable")
        if level == "unverifiable":
            results[claim.claim_id] = VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                confidence=1.0,
                reason="No verification path is available for this claim.",
            )
        else:
            results[claim.claim_id] = verify_ecommerce_claim(claim, level)

    _apply_status_transitions(claims, results)
    return results


def _apply_status_transitions(
    claims: list[Claim],
    results: dict[str, VerificationResult],
) -> None:
    """Downgrade intermediate-state false contradictions for consistent trajectories."""
    by_order: dict[int, list[Claim]] = {}
    for claim in claims:
        order_id = _as_int(claim.entities.get("order_id"))
        if order_id is not None:
            by_order.setdefault(order_id, []).append(claim)

    for group in by_order.values():
        status_claims = [
            c
            for c in group
            if (c.attribute or "").lower() in _STATUS_ATTRS and c.value is not None
        ]
        if not status_claims:
            continue

        # The database snapshot the baseline already saw (no re-query, so the trajectory
        # check uses the exact same state the per-claim comparison used).
        db_status: str | None = None
        for c in status_claims:
            evidence = results[c.claim_id].evidence_value
            if isinstance(evidence, dict) and evidence.get("status") is not None:
                db_status = _normalize_status(evidence["status"])
                break
        if db_status is None:
            continue

        claimed_values = [_normalize_status(c.value) for c in status_claims]
        transition_targets = [
            target
            for c in group
            if (c.attribute or "").lower() in _TRANSITION_ATTRS and c.value is not None
            for target in [_transition_target(c.value)]
            if target
        ]

        # A transition is narrated when more than one distinct state is asserted (across
        # plain status claims and any explicit transition encoder).
        distinct_states = set(claimed_values) | set(transition_targets)
        if len(distinct_states) < 2:
            continue

        # The narrated end state: an explicit transition target wins, else the last
        # status claim in answer order.
        final_state = transition_targets[-1] if transition_targets else claimed_values[-1]

        # Only suppress intermediate contradictions when the trajectory actually ends at
        # the database state. If the narrated end state disagrees with the database, keep
        # every baseline result (preserves detection of a genuinely wrong final state).
        if final_state != db_status:
            continue

        for c in status_claims:
            if _normalize_status(c.value) == db_status:
                continue  # the final, correct state stays supported
            if results[c.claim_id].evidence_state != "contradicted":
                continue
            results[c.claim_id] = VerificationResult(
                claim_id=c.claim_id,
                evidence_state="unverifiable",
                evidence_value=results[c.claim_id].evidence_value,
                source="orders_db",
                source_mode="unavailable",
                confidence=0.0,
                reason=(
                    f"Transitional state '{_normalize_status(c.value)}' in a multi-step "
                    f"trajectory ending at database state '{db_status}'; a single snapshot "
                    "cannot confirm a past state."
                ),
            )


def _transition_target(value: Any) -> str | None:
    """Final state of a transition value such as 'pending->confirmed' or 'pending -> paid'."""
    text = str(value or "")
    for sep in ("->", "→", "=>"):
        if sep in text:
            return _normalize_status(text.rsplit(sep, 1)[-1])
    return None


def verify_ecommerce_claim(claim: Claim, verifiability: Verifiability) -> VerificationResult:
    order_id = _as_int(claim.entities.get("order_id"))
    if order_id is not None:
        row = cursor.execute("SELECT id, amount, status FROM orders WHERE id = ?", (order_id,)).fetchone()  # type: ignore
        if row is None:
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="not_found",
                source="orders_db",
                source_mode="not_found",
                confidence=1.0,
                reason=f"Order {order_id} was not found in orders_db.",
            )
        evidence = {"order_id": row[0], "amount": row[1], "status": row[2]}
        return _compare_order_claim(claim, evidence)

    if claim.attribute == "order_count":
        where_clause, params, unsupported = _build_order_filters(claim)
        if unsupported:
            return _unsupported_filter_result(claim, unsupported)
        actual = cursor.execute(f"SELECT COUNT(*) FROM orders{where_clause}", params).fetchone()[0]  # type: ignore
        return _compare_numeric(claim, actual, "orders_db")

    if claim.attribute in {"order_total", "total_amount"}:
        where_clause, params, unsupported = _build_order_filters(claim)
        if unsupported:
            return _unsupported_filter_result(claim, unsupported)
        actual = cursor.execute(f"SELECT COALESCE(SUM(amount), 0) FROM orders{where_clause}", params).fetchone()[0]  # type: ignore
        return _compare_numeric(claim, actual, "orders_db")

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="unverifiable" if verifiability == "unverifiable" else "unsupported",
        source="orders_db",
        source_mode="unavailable",
        confidence=0.0,
        reason="No ecommerce verifier rule matched this claim.",
    )


def _compare_order_claim(claim: Claim, evidence: dict[str, Any]) -> VerificationResult:
    attribute = (claim.attribute or "").lower()
    if attribute in {"status", "payment_status"}:
        expected = _normalize_status(claim.value)
        actual = _normalize_status(evidence["status"])
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported" if expected == actual else "contradicted",
            evidence_value=evidence,
            source="orders_db",
            source_mode="fixture",
            confidence=1.0,
            reason=f"Claimed {attribute}={expected}; database {attribute}={actual}.",
        )

    if attribute == "amount":
        return _compare_numeric(claim, evidence["amount"], "orders_db", evidence)

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=evidence,
        source="orders_db",
        source_mode="fixture",
        confidence=1.0,
        reason="Order entity exists in orders_db.",
    )


def _compare_numeric(
    claim: Claim,
    actual: Any,
    source: str,
    evidence_value: Any | None = None,
) -> VerificationResult:
    claimed = _as_float(claim.value)
    actual_number = _as_float(actual)
    if claimed is None or actual_number is None:
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unsupported",
            evidence_value=evidence_value if evidence_value is not None else actual,
            source=source,
            source_mode="fixture",
            confidence=0.5,
            reason="Numeric claim could not be parsed into a comparable value.",
        )
    supported = abs(claimed - actual_number) < 1e-6
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported" if supported else "contradicted",
        evidence_value=evidence_value if evidence_value is not None else actual,
        source=source,
        source_mode="fixture",
        confidence=1.0,
        reason=f"Claimed value={claimed}; database value={actual_number}.",
    )


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status == "paid":
        return "confirmed"
    return status


def _build_order_filters(claim: Claim) -> tuple[str, tuple[Any, ...], list[str]]:
    columns = _order_columns()
    clauses: list[str] = []
    params: list[Any] = []
    unsupported: list[str] = []

    customer = claim.entities.get("customer") or claim.entities.get("customer_id")
    if customer is not None:
        if "customer" in columns:
            clauses.append("customer = ?")
            params.append(customer)
        elif "customer_id" in columns:
            clauses.append("customer_id = ?")
            params.append(customer)
        else:
            unsupported.append("customer")

    if claim.time_range:
        if "created_at" in columns:
            clauses.append("substr(created_at, 1, 7) = ?")
            params.append(claim.time_range)
        elif "created_month" in columns:
            clauses.append("created_month = ?")
            params.append(claim.time_range)
        else:
            unsupported.append("time_range")

    if not clauses:
        return "", tuple(), unsupported
    return " WHERE " + " AND ".join(clauses), tuple(params), unsupported


def _order_columns() -> set[str]:
    rows = cursor.execute("PRAGMA table_info(orders)").fetchall()  # type: ignore
    return {str(row[1]) for row in rows}


def _unsupported_filter_result(claim: Claim, unsupported: list[str]) -> VerificationResult:
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="unverifiable",
        source="orders_db",
        source_mode="unavailable",
        confidence=1.0,
        reason=(
            "The claim requires filter(s) not present in the current orders schema: "
            + ", ".join(unsupported)
            + ". The verifier did not fall back to full-table aggregation."
        ),
    )
