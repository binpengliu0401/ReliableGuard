from src.domain.registry import assertion


@assertion("order_created")
def order_created(diff, args) -> bool:
    return diff.order_created


@assertion("status_is_pending")
def status_is_pending(diff, args) -> bool:
    return diff.new_order is not None and diff.new_order["status"] == "pending"


@assertion("amount_is_positive")
def amount_is_positive(diff, args) -> bool:
    return diff.new_order is not None and diff.new_order["amount"] > 0


@assertion("order_confirmed")
def order_confirmed(diff, args) -> bool:
    return diff.order_confirmed


@assertion("updated_order_matches")
def updated_order_matches(diff, args) -> bool:
    return diff.updated_order is not None and diff.updated_order["id"] == args.get(
        "order_id"
    )


@assertion("refund_reason_written")
def refund_reason_written(diff, args) -> bool:
    return (
        diff.updated_order is not None
        and diff.updated_order.get("refund_reason") is not None
        and diff.updated_order["refund_reason"].strip() != ""
    )


@assertion("order_refunded")
def order_refunded(diff, args) -> bool:
    return diff.order_refunded
