from src.domain.registry import policy


@policy("amount_requires_approval")
def amount_requires_approval(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    amount = tool_args.get("amount", 0)
    if amount > 5000:
        return (
            False,
            f"amount_requires_approval: amount {amount} exceeds 5000 and requires approval.",
        )
    return True, ""


@policy("refund_reason_not_empty")
def refund_reason_not_empty(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    reason = tool_args.get("reason", "")
    if not isinstance(reason, str) or not reason.strip():
        return (
            False,
            "refund_reason_not_empty: refund reason must be a non-empty string.",
        )
    return True, ""
