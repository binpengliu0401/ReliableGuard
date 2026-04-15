from src.db.init_db import init_db

cursor, conn = init_db()


def create_order(amount):
    cursor.execute("INSERT INTO orders(amount, status) VALUES(?, 'pending')", (amount,))  # type: ignore
    conn.commit()
    return {"order_id": cursor.lastrowid, "amount": amount, "status": "pending"}  # type: ignore


def get_order_status(order_id):
    result = cursor.execute(  # type: ignore
        "SELECT status FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    if result:
        return {"order_id": order_id, "status": result[0]}
    return {"Error": "Order is not exist"}


def confirm_order(order_id: int) -> dict:
    try:
        cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))  # type: ignore
        row = cursor.fetchone()  # type: ignore
        if row is None:
            return {"success": False, "error": f"Order {order_id} not found."}
        if row[0] != "pending":
            return {
                "success": False,
                "error": f"Order {order_id} cannot be confirmed: current status is '{row[0]}'.",
            }
        cursor.execute(  # type: ignore
            "UPDATE orders SET status = 'confirmed' WHERE id = ?", (order_id,)
        )
        conn.commit()
        return {"success": True, "order_id": order_id, "status": "confirmed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def refund_order(order_id: int, reason: str) -> dict:
    try:
        cursor.execute(  # type: ignore
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        )
        row = cursor.fetchone()  # type: ignore
        if row is None:
            return {"success": False, "error": f"Order {order_id} not found."}
        if row[0] != "confirmed":
            return {
                "success": False,
                "error": f"Order {order_id} cannot be refunded: current status is '{row[0]}'.",
            }
        cursor.execute(  # type: ignore
            "UPDATE orders SET status = 'refunded', refund_reason = ? WHERE id = ?",
            (reason, order_id),
        )
        conn.commit()
        return {"success": True, "order_id": order_id, "status": "refunded"}
    except Exception as e:
        return {"success": False, "error": str(e)}


tools = [
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Creat An Order",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Order Amount"}
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Check Order Status",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Order ID"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order",
            "description": "Confirm a pending order, transitioning its status to confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to confirm",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refund_order",
            "description": "Refund a confirmed order, transitioning its status to refunded.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to refund",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the refund",
                    },
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]

TOOL_REGISTRY = {
    "create_order": create_order,
    "get_order_status": get_order_status,
    "confirm_order": confirm_order,
    "refund_order": refund_order,
}
