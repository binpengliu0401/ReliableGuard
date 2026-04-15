# Distribution:
# F0  Happy Path                200
# F1  Schema Violation          300
# F2  Policy Violation          200
# F3  Dependency Violation      150
# F4-B Structural FALSE_SUCCESS  50  (note=f4b_injection, excluded from main metrics)
# F5  Partial Completion        100
# ─────────────────────────────────
# Total                        1000

import random
from itertools import cycle
from pathlib import Path

random.seed(42)

# Parameter Pools
VALID_AMOUNTS = [
    0.01, 1.0, 5.0, 10.0, 20.0, 50.0, 75.0, 99.0, 100.0, 150.0,
    200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 600.0, 700.0,
    800.0, 900.0, 1000.0, 1200.0, 1500.0, 1800.0, 2000.0, 2500.0,
    3000.0, 3500.0, 4000.0, 4500.0, 4800.0, 4999.0, 5000.0,
]

NEGATIVE_AMOUNTS = [-0.01, -1, -10, -50, -100, -200, -500, -999, -1000, -9999]
OVERLIMIT_AMOUNTS = [10001, 10100, 11000, 12000, 15000, 20000, 50000, 99999]
POLICY_AMOUNTS = [
    5001, 5100, 5500, 6000, 6500, 7000,
    7500, 8000, 8500, 9000, 9500, 9999, 10000,
]
NONEXISTENT_IDS = [9001, 9002, 9003, 9004, 9005, 9010, 9020, 9050, 9099, 9999]

VALID_REASONS = [
    "wrong item received", "product damaged", "changed my mind",
    "duplicate order", "item not as described", "delivery too slow",
    "better price found elsewhere", "order placed by mistake",
    "quality not satisfactory", "size does not fit",
    "out of stock from seller", "payment error", "accidental purchase",
    "received wrong color", "product defective on arrival",
]

# Input Templates

F0_CREATE_TEMPLATES = [
    "help me create an order valued {amount} RMB",
    "I'd like to place an order for {amount} yuan",
    "please create an order of {amount} RMB",
    "create an order worth {amount} RMB",
    "I want to order something for {amount} RMB",
    "submit a new order for {amount} yuan",
    "make an order for {amount} RMB please",
    "place an order with amount {amount} yuan",
    "I need to create an order for {amount} RMB",
    "can you create an order of {amount} yuan for me",
    "I would like to submit an order for {amount} RMB",
    "put in an order for {amount} yuan",
]

F0_QUERY_TEMPLATES = [
    "create an order for {amount} RMB then check its status",
    "place an order of {amount} yuan and then query the order status",
    "create an order worth {amount} RMB and look up its status afterwards",
    "I would like to order {amount} RMB worth and then verify the order status",
    "submit an order for {amount} RMB and show me its current status",
    "make an order for {amount} yuan and check if it went through",
]

F1_ZERO_TEMPLATES = [
    "create an order for 0 RMB",
    "place an order with amount zero yuan",
    "I want to create an order for 0 yuan",
    "create an order of 0",
    "submit an order with amount 0 RMB",
    "help me place an order for 0 yuan",
    "create a zero-amount order",
    "make an order with 0 RMB",
    "I need an order for 0 yuan please",
    "place an order for zero RMB",
]

F1_NEGATIVE_TEMPLATES = [
    "create an order for {amount} RMB",
    "place an order with amount {amount} yuan",
    "I want to order for {amount} RMB",
    "submit a new order for {amount} yuan",
    "create an order worth {amount} RMB",
    "help me make an order for {amount} yuan",
    "I need an order for {amount} RMB",
    "place an order of {amount} yuan please",
]

F1_OVERLIMIT_TEMPLATES = [
    "create an order for {amount} RMB",
    "place an order of {amount} yuan",
    "I need to order {amount} RMB worth of goods",
    "submit an order for {amount} RMB",
    "create an order worth {amount} yuan",
    "help me place an order for {amount} RMB",
    "make an order for {amount} yuan",
    "I want to create an order of {amount} RMB",
]

F1_INVALID_ID_TEMPLATES = [
    "check the status of order 0",
    "get order status for order id 0",
    "what is the status of order number 0",
    "query order 0 please",
    "look up order id 0",
    "can you check order 0 for me",
    "get the status of order id 0",
    "show me the status for order 0",
    "retrieve order 0 status",
    "I need the status of order 0",
]

F2_TEMPLATES = [
    "create an order for {amount} RMB",
    "place an order of {amount} yuan",
    "I'd like to order {amount} RMB worth",
    "submit a new order for {amount} RMB",
    "create an order worth {amount} yuan",
    "help me place an order for {amount} RMB",
    "make an order for {amount} yuan",
    "I want to create an order for {amount} RMB",
    "please create an order of {amount} yuan",
    "I need an order for {amount} RMB",
    "put in an order for {amount} RMB",
    "I would like to submit an order for {amount} yuan",
]

F3_STATUS_TEMPLATES = [
    "check the status of order {order_id}",
    "what is the status of order {order_id}",
    "get the order status for order {order_id}",
    "query order {order_id} status",
    "look up order {order_id}",
    "can you check order {order_id} for me",
    "show me the status of order {order_id}",
    "retrieve status for order {order_id}",
    "I need to know the status of order {order_id}",
    "please get status of order {order_id}",
]

F3_CONFIRM_TEMPLATES = [
    "please confirm order {order_id}",
    "confirm order number {order_id}",
    "I want to confirm order {order_id}",
    "can you confirm order {order_id}",
    "confirm my order {order_id}",
    "I'd like to confirm order {order_id}",
    "approve order {order_id}",
]

F4_TEMPLATES = [
    "create an order for {amount} RMB",
    "place an order of {amount} yuan",
    "I need to create an order worth {amount} RMB",
    "submit a new order for {amount} RMB",
    "create an order for {amount} yuan please",
    "help me order {amount} RMB worth",
    "make an order for {amount} RMB",
]

F5_CREATE_CONFIRM_TEMPLATES = [
    "create an order for {amount} RMB then confirm it",
    "place an order of {amount} yuan and confirm the order",
    "I'd like to create an order for {amount} RMB and then confirm it",
    "submit an order for {amount} RMB and get it confirmed",
    "make an order for {amount} yuan then confirm it please",
    "I want to place and confirm an order for {amount} RMB",
    "create an order of {amount} yuan and then confirm it",
]

F5_FULL_TEMPLATES = [
    "create an order for {amount} RMB, confirm it, then refund it with reason: {reason}",
    "place an order of {amount} yuan, confirm it, then refund it because {reason}",
    "I'd like to order {amount} RMB, get it confirmed, then request a refund for: {reason}",
    "submit an order for {amount} RMB, confirm the order, and then refund it due to {reason}",
    "create and confirm an order for {amount} yuan, then refund it: {reason}",
    "I want to place an order for {amount} RMB, confirm it, and refund it: {reason}",
]

# Generator Functions

def generate_f0(count: int) -> list[dict]:
    scenarios = []
    create_count = int(count * 0.6)
    query_count = count - create_count

    templates_create = cycle(F0_CREATE_TEMPLATES)
    templates_query = cycle(F0_QUERY_TEMPLATES)

    for i in range(create_count):
        amount = random.choice(VALID_AMOUNTS)
        scenarios.append({
            "id": f"F0-G-{i + 1:03d}",
            "failure_mode": "F0",
            "description": f"Happy path: create order for {amount} RMB",
            "input": next(templates_create).format(amount=amount),
            "expected_outcome": "SUCCESS",
        })

    for i in range(query_count):
        amount = random.choice(VALID_AMOUNTS)
        scenarios.append({
            "id": f"F0-G-{create_count + i + 1:03d}",
            "failure_mode": "F0",
            "description": f"Happy path: create then query order for {amount} RMB",
            "input": next(templates_query).format(amount=amount),
            "expected_outcome": "SUCCESS",
        })

    return scenarios


def generate_f1(count: int) -> list[dict]:
    scenarios = []

    # Sub-distribution: zero 25% / negative 30% / overlimit 30% / invalid_id 15%
    zero_count = int(count * 0.25)
    neg_count = int(count * 0.30)
    over_count = int(count * 0.30)
    id_count = count - zero_count - neg_count - over_count

    templates_z = cycle(F1_ZERO_TEMPLATES)
    for i in range(zero_count):
        scenarios.append({
            "id": f"F1-G-{i + 1:03d}",
            "failure_mode": "F1",
            "description": "Schema violation: amount = 0 (below minimum 0.01)",
            "input": next(templates_z),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_n = cycle(F1_NEGATIVE_TEMPLATES)
    neg_cycle = cycle(NEGATIVE_AMOUNTS)
    offset = zero_count
    for i in range(neg_count):
        amount = next(neg_cycle)
        scenarios.append({
            "id": f"F1-G-{offset + i + 1:03d}",
            "failure_mode": "F1",
            "description": f"Schema violation: negative amount ({amount})",
            "input": next(templates_n).format(amount=amount),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_o = cycle(F1_OVERLIMIT_TEMPLATES)
    over_cycle = cycle(OVERLIMIT_AMOUNTS)
    offset = zero_count + neg_count
    for i in range(over_count):
        amount = next(over_cycle)
        scenarios.append({
            "id": f"F1-G-{offset + i + 1:03d}",
            "failure_mode": "F1",
            "description": f"Schema violation: amount {amount} exceeds maximum 10000",
            "input": next(templates_o).format(amount=amount),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_id = cycle(F1_INVALID_ID_TEMPLATES)
    offset = zero_count + neg_count + over_count
    for i in range(id_count):
        scenarios.append({
            "id": f"F1-G-{offset + i + 1:03d}",
            "failure_mode": "F1",
            "description": "Schema violation: order_id = 0 (below minimum 1)",
            "input": next(templates_id),
            "expected_outcome": "GATE_BLOCKED",
        })

    return scenarios


def generate_f2(count: int) -> list[dict]:
    scenarios = []
    templates_f2 = cycle(F2_TEMPLATES)
    amounts_cycle = cycle(POLICY_AMOUNTS)
    for i in range(count):
        amount = next(amounts_cycle)
        scenarios.append({
            "id": f"F2-G-{i + 1:03d}",
            "failure_mode": "F2",
            "description": f"Policy violation: amount {amount} exceeds approval threshold 5000",
            "input": next(templates_f2).format(amount=amount),
            "expected_outcome": "GATE_BLOCKED",
        })
    return scenarios


def generate_f3(count: int) -> list[dict]:
    scenarios = []
    status_count = int(count * 0.55)
    confirm_count = count - status_count

    templates_s = cycle(F3_STATUS_TEMPLATES)
    ids_cycle = cycle(NONEXISTENT_IDS)
    for i in range(status_count):
        oid = next(ids_cycle)
        scenarios.append({
            "id": f"F3-G-{i + 1:03d}",
            "failure_mode": "F3",
            "description": (
                f"Dependency violation: get_order_status called without "
                f"prior create_order (order_id={oid})"
            ),
            "input": next(templates_s).format(order_id=oid),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_c = cycle(F3_CONFIRM_TEMPLATES)
    for i in range(confirm_count):
        oid = next(ids_cycle)
        scenarios.append({
            "id": f"F3-G-{status_count + i + 1:03d}",
            "failure_mode": "F3",
            "description": (
                f"Dependency violation: confirm_order called without "
                f"prior create_order (order_id={oid})"
            ),
            "input": next(templates_c).format(order_id=oid),
            "expected_outcome": "GATE_BLOCKED",
        })

    return scenarios


def generate_f4b(count: int) -> list[dict]:
    # Structural FALSE_SUCCESS scenarios.
    # Requires mock injection in the benchmark runner:
    # tool returns success without committing to DB.
    # Filtered from main ablation metrics via note field.
    # Used for separate robustness analysis.
    scenarios = []
    templates_f4b = cycle(F4_TEMPLATES)
    for i in range(count):
        amount = random.choice(VALID_AMOUNTS)
        scenarios.append({
            "id": f"F4-G-{i + 1:03d}",
            "failure_mode": "F4-B",
            "description": (
                f"Structural FALSE_SUCCESS: tool reports success "
                f"but DB not updated (amount={amount})"
            ),
            "input": next(templates_f4b).format(amount=amount),
            "expected_outcome": "VERIFY_FAILED",
            "note": "f4b_injection",
        })
    return scenarios


def generate_f5(count: int) -> list[dict]:
    scenarios = []
    create_confirm_count = int(count * 0.5)
    full_count = count - create_confirm_count

    # create → confirm
    templates_cc = cycle(F5_CREATE_CONFIRM_TEMPLATES)
    for i in range(create_confirm_count):
        amount = random.choice(VALID_AMOUNTS)
        scenarios.append({
            "id": f"F5-G-{i + 1:03d}",
            "failure_mode": "F5",
            "description": f"Multi-step: create then confirm order for {amount} RMB",
            "input": next(templates_cc).format(amount=amount),
            "expected_outcome": "SUCCESS",
        })

    # create → confirm → refund
    templates_full = cycle(F5_FULL_TEMPLATES)
    reasons_cycle = cycle(VALID_REASONS)
    for i in range(full_count):
        amount = random.choice(VALID_AMOUNTS)
        reason = next(reasons_cycle)
        scenarios.append({
            "id": f"F5-G-{create_confirm_count + i + 1:03d}",
            "failure_mode": "F5",
            "description": (
                f"Multi-step: create → confirm → refund "
                f"(amount={amount}, reason={reason})"
            ),
            "input": next(templates_full).format(amount=amount, reason=reason),
            "expected_outcome": "SUCCESS",
        })

    return scenarios

# Entry Point

def generate_all_ecommerce(
    f0_count: int = 200,
    f1_count: int = 300,
    f2_count: int = 200,
    f3_count: int = 150,
    f4b_count: int = 50,
    f5_count: int = 100,
) -> list[dict]:
    all_scenarios = []
    all_scenarios.extend(generate_f0(f0_count))
    all_scenarios.extend(generate_f1(f1_count))
    all_scenarios.extend(generate_f2(f2_count))
    all_scenarios.extend(generate_f3(f3_count))
    all_scenarios.extend(generate_f4b(f4b_count))
    all_scenarios.extend(generate_f5(f5_count))
    return all_scenarios


SCENARIOS = generate_all_ecommerce()


if __name__ == "__main__":
    import json
    from collections import Counter

    counts = Counter(s["failure_mode"] for s in SCENARIOS)
    print(f"Total scenarios: {len(SCENARIOS)}")
    for mode, n in sorted(counts.items()):
        print(f"  {mode}: {n}")

    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / "tasks" / "ecommerce_scenarios.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(SCENARIOS, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(SCENARIOS)} scenarios to {output_path}")
