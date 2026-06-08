from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.domain.ecommerce.tools import cursor


CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass(frozen=True)
class StructuralIssue:
    rule_name: str
    action: str
    reason: str
    phase: str
    tool_name: str


def check_pre_execution(tool_name: str, args: dict[str, Any]) -> list[StructuralIssue]:
    tool_config = _tool_config(tool_name)
    issues: list[StructuralIssue] = []
    for policy in tool_config.get("policies", []) or []:
        condition = policy.get("condition") or {}
        if condition and _condition_matches(condition, args):
            issues.append(
                StructuralIssue(
                    rule_name=str(policy.get("name", "unnamed_policy")),
                    action=str(policy.get("action", "WARN")),
                    reason=str(policy.get("reason", "policy rule matched")),
                    phase="pre_execution",
                    tool_name=tool_name,
                )
            )
    return issues


def snapshot_ecommerce_state() -> dict[str, Any]:
    rows = cursor.execute(  # type: ignore[union-attr]
        "SELECT id, amount, status, refund_reason FROM orders ORDER BY id"
    ).fetchall()
    state: dict[str, Any] = {
        str(row[0]): {
            "id": row[0],
            "amount": row[1],
            "status": row[2],
            "refund_reason": row[3],
        }
        for row in rows
    }
    # Inventory rows are namespaced ("inv:<product_id>") so they never collide with
    # order ids. Empty inventory adds nothing, so the authoritative orders-only behaviour
    # is preserved; it only matters for the clean state-local F4 experiment.
    try:
        inv = cursor.execute(  # type: ignore[union-attr]
            "SELECT product_id, name, stock FROM inventory ORDER BY product_id"
        ).fetchall()
        for prod in inv:
            state[f"inv:{prod[0]}"] = {
                "product_id": prod[0],
                "name": prod[1],
                "stock": prod[2],
            }
    except Exception:
        pass
    return state


def check_post_execution(
    tool_name: str,
    args: dict[str, Any],
    result: Any,
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[StructuralIssue]:
    tool_config = _tool_config(tool_name)
    issues: list[StructuralIssue] = []
    if not _tool_reported_success(result):
        return issues

    for assertion in tool_config.get("assertions", []) or []:
        if assertion.get("name") != "tool_success_requires_state_change":
            continue
        if _state_unchanged_for_successful_tool(tool_name, args, result, before, after):
            issues.append(
                StructuralIssue(
                    rule_name=str(assertion.get("name")),
                    action=str(assertion.get("action", "BLOCK")),
                    reason=str(
                        assertion.get(
                            "failure",
                            "tool reported success but environment state unchanged",
                        )
                    ),
                    phase="post_execution",
                    tool_name=tool_name,
                )
            )
    return issues


def issue_to_dict(issue: StructuralIssue) -> dict[str, Any]:
    return {
        "rule_name": issue.rule_name,
        "action": issue.action,
        "reason": issue.reason,
        "phase": issue.phase,
        "tool_name": issue.tool_name,
    }


def _load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    return loaded if isinstance(loaded, dict) else {}


def _tool_config(tool_name: str) -> dict[str, Any]:
    tools = _load_config().get("tools", {})
    config = tools.get(tool_name, {}) if isinstance(tools, dict) else {}
    return config if isinstance(config, dict) else {}


def _condition_matches(condition: dict[str, Any], args: dict[str, Any]) -> bool:
    argument = condition.get("argument")
    operator = condition.get("operator")
    expected = condition.get("value")
    actual = args.get(argument)
    if actual is None:
        return False
    try:
        actual_num = float(actual)
        expected_num = float(expected)
    except (TypeError, ValueError):
        return False

    if operator == ">":
        return actual_num > expected_num
    if operator == ">=":
        return actual_num >= expected_num
    if operator == "<":
        return actual_num < expected_num
    if operator == "<=":
        return actual_num <= expected_num
    if operator == "==":
        return actual_num == expected_num
    return False


def _tool_reported_success(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("success") is True:
        return True
    if result.get("success") is False or result.get("error") or result.get("Error"):
        return False
    return bool(result.get("order_id") and result.get("status"))


def _state_unchanged_for_successful_tool(
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> bool:
    if before == after:
        return True

    if tool_name == "update_stock":
        product_id = args.get("product_id")
        return before.get(f"inv:{product_id}") == after.get(f"inv:{product_id}")

    order_id = result.get("order_id") or args.get("order_id")
    if order_id is None:
        return False
    before_row = before.get(str(order_id))
    after_row = after.get(str(order_id))

    if tool_name == "create_order":
        return after_row is None
    if tool_name == "confirm_order":
        return before_row == after_row or not after_row or after_row.get("status") != "confirmed"
    if tool_name == "refund_order":
        return before_row == after_row or not after_row or after_row.get("status") != "refunded"
    return before == after
