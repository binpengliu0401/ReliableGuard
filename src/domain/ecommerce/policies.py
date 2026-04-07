from src.domain.registry import policy


@policy("amount_requires_approval")
def amount_requires_approval(args: dict) -> bool:
    return args.get("amount", 0) > 5000


@policy("refund_reason_not_empty")
def refund_reason_not_empty(args: dict) -> bool:
    return not args.get("reason", "").strip()
