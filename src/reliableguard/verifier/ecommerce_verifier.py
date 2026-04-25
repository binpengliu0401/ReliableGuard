from __future__ import annotations

from typing import Any

from src.domain.ecommerce.tools import cursor
from src.reliableguard.schema import Claim, VerificationResult, Verifiability


def verify_ecommerce_claim(claim: Claim, verifiability: Verifiability) -> VerificationResult:
    order_id = _as_int(claim.entities.get("order_id"))
    if order_id is not None:
        row = cursor.execute("SELECT id, amount, status FROM orders WHERE id = ?", (order_id,)).fetchone()  # type: ignore
        if row is None:
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="not_found",
                source="orders_db",
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
            confidence=0.5,
            reason="Numeric claim could not be parsed into a comparable value.",
        )
    supported = abs(claimed - actual_number) < 1e-6
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported" if supported else "contradicted",
        evidence_value=evidence_value if evidence_value is not None else actual,
        source=source,
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
        confidence=1.0,
        reason=(
            "The claim requires filter(s) not present in the current orders schema: "
            + ", ".join(unsupported)
            + ". The verifier did not fall back to full-table aggregation."
        ),
    )
