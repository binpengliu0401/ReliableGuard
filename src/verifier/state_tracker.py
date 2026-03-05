from dataclasses import dataclass
from typing import Any


@dataclass
class Snapshot:
    order_count: int
    last_order: dict | None  # {id, amount, status} or none


@dataclass
class StateDiff:
    order_count_before: int
    order_count_after: int
    new_order: dict | None

    @property
    def order_created(self) -> bool:
        return self.order_count_after > self.order_count_before


def take_snapshot(cursor) -> Snapshot:
    count = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    last = cursor.execute(
        "SELECT id, amount, status FROM orders ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_order = {"id": last[0], "amount": last[1], "status": last[2]}

    return Snapshot(order_count=count, last_order=last_order)


def compute_diff(before: Snapshot, after: Snapshot) -> StateDiff:
    new_order = None
    if after.order_count > before.order_count:
        new_order = after.last_order
    return StateDiff(
        order_count_before=before.order_count,
        order_count_after=after.order_count,
        new_order=new_order,
    )
