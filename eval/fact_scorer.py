import json
import re
from typing import Any


FactValue = str | int | float | bool | None

_ORDER_KEY_RE = re.compile(r"^order_(\d+)$")
_TOOL_CALLED_RE = re.compile(r"^(.+)_called$")


def parse_expected_facts(verifiable_facts: list[str]) -> dict[str, str]:
    """Parse ["order_id=1", "amount=100"] into {"order_id": "1", "amount": "100"}."""
    expected: dict[str, str] = {}
    for fact in verifiable_facts:
        if "=" not in fact:
            continue
        key, value = fact.split("=", 1)
        key = key.strip()
        if key:
            expected[key] = value.strip()
    return expected


def snapshot_facts(domain: str, expected_keys: set[str]) -> dict[str, FactValue]:
    """
    Query the domain DB for supported fact keys and silently omit unsupported keys.
    """
    if domain == "ecommerce":
        return _snapshot_ecommerce(expected_keys)
    if domain == "reference":
        return _snapshot_reference(expected_keys)
    return {}


def score_facts(expected: dict[str, str], snapshot: dict[str, FactValue]) -> float | None:
    """
    Compare expected facts against a DB snapshot.

    Only keys present in both inputs are scored. Values are compared as stripped,
    case-insensitive strings.
    """
    compared = 0
    matched = 0
    for key, expected_value in expected.items():
        if key not in snapshot:
            continue
        compared += 1
        actual_str = str(snapshot[key]).strip().lower()
        expected_str = str(expected_value).strip().lower()
        if actual_str == expected_str:
            matched += 1
            continue
        try:
            if float(actual_str) == float(expected_str):
                matched += 1
        except (TypeError, ValueError):
            pass

    if compared == 0:
        return None
    return matched / compared


def score_trace_facts(
    expected: dict[str, str],
    state: dict,
    domain: str,
) -> dict[str, bool | None]:
    """
    Score fact keys that depend on the agent trace or reference verifier state.
    """
    scores: dict[str, bool | None] = {}
    executed_tools = set(state.get("executed_tools", []) or [])

    for key, expected_value in expected.items():
        tool_match = _TOOL_CALLED_RE.match(key)
        if tool_match:
            tool_name = tool_match.group(1)
            scores[key] = _matches_expected_bool(
                actual=tool_name in executed_tools,
                expected=expected_value,
            )
            continue

        if key not in _TRACE_REFERENCE_KEYS:
            continue
        if domain != "reference":
            scores[key] = None
            continue

        actual = _snapshot_trace_reference_value(key)
        if actual is None:
            scores[key] = None
        else:
            scores[key] = _values_match(actual, expected_value)

    return scores


def _snapshot_ecommerce(expected_keys: set[str]) -> dict[str, FactValue]:
    simple_queries = {
        "order_id": "SELECT MAX(id) FROM orders",
        "max_order_id": "SELECT MAX(id) FROM orders",
        "amount": "SELECT amount FROM orders WHERE id = (SELECT MAX(id) FROM orders)",
        "status": "SELECT status FROM orders WHERE id = (SELECT MAX(id) FROM orders)",
        "total_amount": "SELECT COALESCE(SUM(amount), 0) FROM orders",
        "order_count": "SELECT COUNT(*) FROM orders",
        "total_orders": "SELECT COUNT(*) FROM orders",
        "confirmed_count": "SELECT COUNT(*) FROM orders WHERE status='confirmed'",
        "refunded_count": "SELECT COUNT(*) FROM orders WHERE status='refunded'",
        "pending_count": "SELECT COUNT(*) FROM orders WHERE status='pending'",
        "refund_success": "SELECT COUNT(*) > 0 FROM orders WHERE status='refunded'",
        "average_amount": "SELECT AVG(amount) FROM orders",
        "max_amount": "SELECT MAX(amount) FROM orders",
        "count_less_than_30": "SELECT COUNT(*) FROM orders WHERE amount < 30",
        "pending_total": "SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status='pending'",
        "confirmed_total": "SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status='confirmed'",
    }
    has_supported_key = any(
        key in simple_queries or key == "error" or _ORDER_KEY_RE.match(key)
        for key in expected_keys
    )
    if not has_supported_key:
        return {}

    from src.domain.ecommerce.tools import cursor

    snapshot: dict[str, FactValue] = {}
    for key in expected_keys:
        if key in simple_queries:
            try:
                snapshot[key] = _fetch_one_value(cursor.execute(simple_queries[key]))
            except Exception:
                continue
            continue

        if key == "error":
            snapshot[key] = _snapshot_ecommerce_error(cursor)
            continue

        order_match = _ORDER_KEY_RE.match(key)
        if order_match:
            order_id = int(order_match.group(1))
            try:
                row = cursor.execute(
                    f"SELECT id, amount, status FROM orders WHERE id = {order_id}",
                ).fetchone()
            except Exception:
                continue
            if row is not None:
                snapshot[key] = f"{row[0]},{row[1]},{row[2]}"

    return snapshot


def _snapshot_ecommerce_error(cursor: Any) -> int:
    try:
        row = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()
        return 0 if row and row[0] > 0 else 1
    except Exception:
        return 1


def _snapshot_reference(expected_keys: set[str]) -> dict[str, FactValue]:
    scalar_queries = {
        "doi_status": 'SELECT doi_status FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "ref_count": 'SELECT COUNT(*) FROM "references"',
        "ref_year": 'SELECT year FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "doi_exists": 'SELECT COUNT(*) > 0 FROM "references" WHERE doi_status != \'not_found\'',
        "total_refs": 'SELECT COUNT(*) FROM "references"',
        "ref_title": 'SELECT title FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "ref_doi": 'SELECT doi FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "canonical_title": 'SELECT title FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "doi_string": 'SELECT doi FROM "references" ORDER BY ref_id DESC LIMIT 1',
        "newer_ref": 'SELECT ref_id FROM "references" ORDER BY year DESC LIMIT 1',
    }
    json_author_keys = {"author_count", "author"}
    has_supported_key = any(
        key in scalar_queries or key in json_author_keys for key in expected_keys
    )
    if not has_supported_key:
        return {}

    from src.domain.reference.tools import init_reference_db

    snapshot: dict[str, FactValue] = {}
    db = init_reference_db()
    try:
        for key in expected_keys:
            if key in scalar_queries:
                try:
                    snapshot[key] = _fetch_one_value(db.execute(scalar_queries[key]))
                except Exception:
                    continue
                continue

            if key in json_author_keys:
                try:
                    row = db.execute(
                        'SELECT authors FROM "references" ORDER BY ref_id DESC LIMIT 1'
                    ).fetchone()
                except Exception:
                    continue
                authors = _parse_authors(row[0] if row else None)
                if key == "author_count":
                    snapshot[key] = len(authors)
                elif key == "author":
                    snapshot[key] = authors[0] if authors else None
    finally:
        db.close()

    return snapshot


_TRACE_REFERENCE_KEYS = {
    "parse_status",
    "verified_doi_count",
    "verified_count",
    "failed_count",
    "failed_parses",
    "doi_verdict_code",
    "successful_parses",
    "matches",
}


def _snapshot_trace_reference_value(key: str) -> FactValue:
    from src.domain.reference.tools import init_reference_db

    db = init_reference_db()
    try:
        if key == "parse_status":
            count = _fetch_one_value(
                db.execute('SELECT COUNT(*) FROM "references" WHERE doi_status=\'valid\'')
            )
            return "ok" if int(count or 0) > 0 else "error"
        if key in {"verified_doi_count", "verified_count", "successful_parses"}:
            return _fetch_one_value(
                db.execute('SELECT COUNT(*) FROM "references" WHERE doi_status=\'valid\'')
            )
        if key in {"failed_count", "failed_parses"}:
            return _fetch_one_value(
                db.execute('SELECT COUNT(*) FROM "references" WHERE doi_status=\'not_found\'')
            )
        if key == "doi_verdict_code":
            return _fetch_one_value(
                db.execute(
                    'SELECT doi_verdict_code FROM "references" ORDER BY ref_id DESC LIMIT 1'
                )
            )
        if key == "matches":
            row = db.execute(
                'SELECT doi_status FROM "references" ORDER BY ref_id DESC LIMIT 1'
            ).fetchone()
            return 1 if row and row[0] == "valid" else 0
    except Exception:
        return None
    finally:
        db.close()

    return None


def _parse_authors(raw_authors: Any) -> list[Any]:
    if not raw_authors:
        return []
    try:
        authors = json.loads(raw_authors)
    except Exception:
        return []
    return authors if isinstance(authors, list) else []


def _fetch_one_value(cursor_result: Any) -> FactValue:
    row = cursor_result.fetchone()
    if row is None:
        return None
    return row[0]


def _matches_expected_bool(actual: bool, expected: str) -> bool:
    expected_normalized = str(expected).strip().lower()
    if expected_normalized in {"true", "1", "yes", "called"}:
        return actual is True
    if expected_normalized in {"false", "0", "no", "not_called"}:
        return actual is False
    return str(actual).strip().lower() == expected_normalized


def _values_match(actual: FactValue, expected: str) -> bool:
    return str(actual).strip().lower() == str(expected).strip().lower()
