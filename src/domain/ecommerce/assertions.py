from src.domain.registry import assertion


@assertion("order_created")
def order_created(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.order_created:
        return True, ""
    return False, "order_created: no new order found in DB after execution."


@assertion("status_is_pending")
def status_is_pending(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.new_order is not None and diff.new_order["status"] == "pending":
        return True, ""
    return False, "status_is_pending: new order status is not 'pending'."


@assertion("amount_is_positive")
def amount_is_positive(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.new_order is not None and diff.new_order["amount"] > 0:
        return True, ""
    return False, "amount_is_positive: new order amount is not positive."


@assertion("order_confirmed")
def order_confirmed(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.order_confirmed:
        return True, ""
    return False, "order_confirmed: order status did not transition to confirmed."


@assertion("updated_order_matches")
def updated_order_matches(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.updated_order is not None and diff.updated_order["id"] == tool_args.get(
        "order_id"
    ):
        return True, ""
    return (
        False,
        "updated_order_matches: updated order id does not match requested order_id.",
    )


@assertion("refund_reason_written")
def refund_reason_written(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if (
        diff.updated_order is not None
        and diff.updated_order.get("refund_reason") is not None
        and diff.updated_order["refund_reason"].strip() != ""
    ):
        return True, ""
    return False, "refund_reason_written: refund_reason not written to DB."


@assertion("order_refunded")
def order_refunded(tool_name: str, tool_args: dict, diff) -> tuple[bool, str]:
    if diff.order_refunded:
        return True, ""
    return False, "order_refunded: order status did not transition to refunded."
