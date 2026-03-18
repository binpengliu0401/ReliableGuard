from src.db.init_db import init_db
from mistralai.models import Tool, Function

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
]
