MAX_RETRIES = 3

TOOL_CONFIG = {
    "create_order": {
        # Gate: Schema
        "required": ["amount"],
        "rules": {
            "amount": {
                "type": int,
                "min": 0.01,
                "max": 10000,
            }
        },
        # Gate: Policy
        "policies": [
            {
                "condition": lambda args: args.get("amount", 0) > 5000,
                "reason": "amount exceeds 5000, requires approval before order creation",
            }
        ],
        # Gate: Dependency
        "dependencies": [],
        # Verifier: Postcondition assertions
        "assertions": [
            {
                "name": "order_created",
                "check": lambda diff, args: diff.order_created,
                "failure": "No new order found in DB after execution",
            },
            {
                "name": "status_is_pending",
                "check": lambda diff, args: diff.new_order is not None
                and diff.new_order["status"] == "pending",
                "failure": "Order status is not pending",
            },
            {
                "name": "amount_is_positive",
                "check": lambda diff, args: diff.new_order is not None
                and diff.new_order["amount"] > 0,
                "failure": "Order amount in DB is not positive",
            },
        ],
    },
    "get_order_status": {
        "required": ["order_id"],
        "rules": {
            "order_id": {
                "type": int,
                "min": 1,
            }
        },
        "policies": [],
        "dependencies": ["create_order"],
        "assertions": [],
    },
    "confirm_order": {
        "required": ["order_id"],
        "rules": {
            "order_id": {
                "type": int,
                "min": 1,
            }
        },
        "policies": [],
        "dependencies": ["create_order"],
        "assertions": [
            {
                "name": "order_confirmed",
                "check": lambda diff, args: diff.order_confirmed,
                "failure": "Order status did not transition to confirmed in DB",
            },
            {
                "name": "updated_order_matches",
                "check": lambda diff, args: diff.updated_order is not None
                and diff.updated_order["id"] == args.get("order_id"),
                "failure": "Confirmed order ID in DB does not match requested order_id",
            },
        ],
    },
    "refund_order": {
        "required": ["order_id", "reason"],
        "rules": {
            "order_id": {
                "type": int,
                "min": 1,
            },
            "reason": {
                "type": str,
            },
        },
        "policies": [
            {
                "condition": lambda args: not args.get("reason", "").strip(),
                "reason": "refund reason must be a non-empty string",
            }
        ],
        "dependencies": ["confirm_order"],
        "assertions": [
            {
                "name": "order_refunded",
                "check": lambda diff, args: diff.order_refunded,
                "failure": "Order status did not transition to refunded in DB",
            },
            {
                "name": "refund_reason_written",
                "check": lambda diff, args: diff.updated_order is not None
                and diff.updated_order.get("refund_reason") is not None
                and diff.updated_order["refund_reason"].strip() != "",
                "failure": "refund_reason not written to DB",
            },
        ],
    },
}
