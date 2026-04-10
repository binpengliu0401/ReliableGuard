from dataclasses import dataclass, field
from typing import Any


@dataclass
class Snapshot:
    order_count: int
    last_order: dict | None 
    # id → {id, amount, status, refund_reason}
    all_orders: dict[int, dict]


@dataclass
class StateDiff:
    order_count_before: int
    order_count_after: int
    new_order: dict | None  
    updated_order: dict | None  
    status_before: str | None  
    status_after: str | None 

    @property
    def order_created(self) -> bool:
        return self.order_count_after > self.order_count_before

    @property
    def order_confirmed(self) -> bool:
        return self.status_before == "pending" and self.status_after == "confirmed"

    @property
    def order_refunded(self) -> bool:
        return self.status_before == "confirmed" and self.status_after == "refunded"


def take_snapshot(cursor) -> Snapshot:
    count = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    last = cursor.execute(
        "SELECT id, amount, status FROM orders ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_order = {"id": last[0], "amount": last[1], "status": last[2]} if last else None

    rows = cursor.execute(
        "SELECT id, amount, status, refund_reason FROM orders"
    ).fetchall()
    all_orders = {
        row[0]: {
            "id": row[0],
            "amount": row[1],
            "status": row[2],
            "refund_reason": row[3],
        }
        for row in rows
    }

    return Snapshot(order_count=count, last_order=last_order, all_orders=all_orders)


def compute_diff(before: Snapshot, after: Snapshot) -> StateDiff:
    # INSERT detection (backward compat)
    new_order = None
    if after.order_count > before.order_count:
        new_order = after.last_order

    # UPDATE detection: find first order whose status changed
    updated_order = None
    status_before = None
    status_after = None
    for order_id, after_order in after.all_orders.items():
        if order_id in before.all_orders:
            b_status = before.all_orders[order_id]["status"]
            a_status = after_order["status"]
            if b_status != a_status:
                updated_order = after_order
                status_before = b_status
                status_after = a_status
                break

    return StateDiff(
        order_count_before=before.order_count,
        order_count_after=after.order_count,
        new_order=new_order,
        updated_order=updated_order,
        status_before=status_before,
        status_after=status_after,
    )
