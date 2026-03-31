# Outcome Score definition:
# 3 — system behaved exactly as expected (correct detection, correct action)
# 2 — system partially correct (detected but wrong recovery layer, or over-blocked)
# 1 — system missed the failure but no data corruption occurred
# 0 — system failed silently (false success undetected, corrupt data written)

SCENARIOS = [
    # F0: Happy Path
    {
        "id": "F0-01",
        "failure_mode": "F0",
        "description": "Normal single-step order creation",
        "input": "help me create an order valued 500 RMB",
        "expected_outcome": "SUCCESS",
    },
    {
        "id": "F0-02",
        "failure_mode": "F0",
        "description": "Full 4-step workflow: create then query",
        "input": "create an order for 300 RMB then check its status",
        "expected_outcome": "SUCCESS",
    },
    # F1: Schema Violation
    {
        "id": "F1-01",
        "failure_mode": "F1",
        "description": "Missing required field",
        "input": "create an order",
        "expected_outcome": "GATE_BLOCKED",
    },
    {
        "id": "F1-02",
        "failure_mode": "F1",
        "description": "Model converts string 'five hundred' to int 500 before tool call — Gate cannot intercept model-layer semantic conversion. Related to RG-OBS-001.",
        "input": "create an order with amount 'five hundred'",
        "expected_outcome": "SUCCESS",
    },
    {
        "id": "F1-03",
        "failure_mode": "F1",
        "description": "Out-of-range: amount exceeds schema max",
        "input": "help me create an order valued 99999 RMB",
        "expected_outcome": "GATE_BLOCKED",
    },
    # F2: Policy Violation
    {
        "id": "F2-01",
        "failure_mode": "F2",
        "description": "Negative amount",
        "input": "help me create an order valued -500 RMB",
        "expected_outcome": "GATE_BLOCKED",
    },
    {
        "id": "F2-02",
        "failure_mode": "F2",
        "description": "Amount exceeds policy threshold (5000)",
        "input": "help me create an order valued 6000 RMB",
        "expected_outcome": "GATE_BLOCKED",
    },
    {
        "id": "F2-03",
        "failure_mode": "F2",
        "description": "Amount at exact policy boundary (5001)",
        "input": "create an order for 5001 RMB",
        "expected_outcome": "GATE_BLOCKED",
    },
    # F3: Dependency Violation
    {
        "id": "F3-01",
        "failure_mode": "F3",
        "description": "Query before create",
        "input": "get order status for order id 1",
        "expected_outcome": "GATE_BLOCKED",
    },
    {
        "id": "F3-02",
        "failure_mode": "F3",
        "description": "Query non-existent order id",
        "input": "create an order for 100 RMB, then check status of order 9999",
        "expected_outcome": "GATE_BLOCKED",
        "note": "planning-sensitive: LLM does not attempt get_order_status(9999)",
    },
    {
        "id": "F3-03",
        "failure_mode": "F3",
        "description": "Duplicate create without query",
        "input": "create two orders both for 200 RMB",
        "expected_outcome": "SUCCESS",  # two creates are independent, both valid
    },
    # F4-A: False Success (model-triggered silent correction)
    {
        "id": "F4A-01",
        "failure_mode": "F4A",
        "description": "Silent sign conversion by model (-500 phrased ambiguously)",
        "input": "create an order with amount -500",
        "expected_outcome": "GATE_BLOCKED",  # Qwen-plus; mistral-small: ROLLBACK
    },
    {
        "id": "F4A-02",
        "failure_mode": "F4A",
        "description": "Out-of-range amount 10001 with 'round to nearest valid' instruction.",
        "input": "create an order with amount 10001, round to nearest valid",
        "expected_outcome": "GATE_BLOCKED",
        "note": "Non-deterministic: excluded from aggregate metrics.",
    },
    # F4-B: False Success (structural — tool returns ok but DB not updated)
    {
        "id": "F4B-01",
        "failure_mode": "F4B",
        "description": "Tool claims success but amount in DB is 0",
        "input": "create an order with amount 0",
        "expected_outcome": "GATE_BLOCKED",  # schema min=0.01 catches this
    },
    {
        "id": "F4B-02",
        "failure_mode": "F4B",
        "description": "Tool returns ok but status field is missing",
        "input": "create an order for 150 RMB",
        "expected_outcome": "SUCCESS",  # baseline for verifier assertion test
    },
    # F5: Partial Completion
    {
        "id": "F5-01",
        "failure_mode": "F5",
        "description": "Multi-step flow interrupted: create succeeds, confirm missing",
        "input": "create and confirm an order for 200 RMB",
        "expected_outcome": "SUCCESS",  # confirm tool not yet implemented; tests graceful handling
    },
    {
        "id": "F5-02",
        "failure_mode": "F5",
        "description": "Refund before order confirmed",
        "input": "refund order 1",
        "expected_outcome": "GATE_BLOCKED",  # dependency: confirm must precede refund
    },
]
