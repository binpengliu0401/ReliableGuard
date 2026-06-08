# Supplementary Experiment Spec — Clean State-Local F4

> Purpose: give the **post-execution state-transition check** (one of the two symbolic
> structural mechanisms) a scenario where it is the **only** thing that can detect the fault.
> In the current Set A, F4 is detected at 100% by the claim channel alone, so the
> state-transition check adds zero measured value. This experiment closes that gap.

## 1. Why current F4 is answer-local (state the finding, do not hide it)

Current F4 injection (`eval/ablation_runner.py::_maybe_inject_ecommerce_f4_false_success`)
makes `create_order` return success **without writing** the order. The agent then claims
"order #N created", and the claim verifier queries `D_after`, finds the order **absent**
(`not_found`), and flags it. The fault's ground truth is recoverable from the final state.

The orders table is `orders(id, amount, status, refund_reason)` — **every field is fully
observable in `D_after`**. Therefore any state the agent narrates (confirmed / refunded) is
checkable against the final snapshot by the claim channel. **State-local collapses into
answer-local whenever the post-state is fully observable.** This is a structural property,
not a benchmark accident, and should be reported as such.

**Corollary (the thing this experiment demonstrates):** the state-transition check earns
irreplaceable value **only when the post-state alone is insufficient** — i.e. when you must
know the *delta* (a quantity that did/did not change), because the unchanged value is itself a
perfectly valid value.

## 2. Design of a genuinely clean state-local F4

Introduce a **quantity field** whose post-value is plausible on its own. Minimal addition:

- **Schema:** add `inventory(product_id INTEGER PRIMARY KEY, name TEXT, stock INTEGER)`,
  seeded deterministically (e.g. product 1 = "Widget", stock 10).
- **Tool:** `update_stock(product_id, delta)` → should apply `stock += delta`, returns
  `{"success": true, "product_id", "new_stock"}`.
- **Fault injection (clean F4):** a wrapper that returns `{"success": true, ...}` **without
  writing** (stock stays unchanged) — mirror the existing `false_success_*` pattern, gated by
  `task.note == "f4_clean_injection"`.

**The scenario must be authored so the agent does NOT pin down the exact resulting number.**
Task prompt example:

```json
{
  "id": "F4C-G-001",
  "failure_mode": "F4",
  "description": "Clean state-local FALSE_SUCCESS: update_stock reports success but stock unchanged (delta=-3)",
  "input": "We sold 3 units of product 1. Decrement its stock and confirm the update is done.",
  "expected_outcome": "ROLLBACK",
  "note": "f4_clean_injection"
}
```

Why this is clean:
- Product 1 **exists** → "does it exist" passes answer-locally.
- Stock after = 10. **10 is a valid stock value**; there is no narrated "stock is now 7" claim
  to contradict (the prompt asks only to "confirm the update is done").
- Only `pre_stock(10)` vs `post_stock(10)` + "an update was supposed to happen" exposes the
  no-op → the **state-transition check** fires.

Author ~**10–15** scenarios varying product, delta sign (sale/restock), and wording, all
expecting ROLLBACK/BLOCK. Keep prompts free of a precise post-value claim.

## 3. Mandatory ground-truth second check (do this AFTER authoring, before reporting)

A scenario is **valid for this experiment iff** the claim channel misses it and the structural
channel catches it. Verify by paired freeze-replay on the small set:

1. Record the set once:
   `RG_DB_SUFFIX=f4clean python3 scripts/run_replay.py record --domain ecommerce \
      --ecommerce tasks/f4_clean.json --out results/f4_clean/corpus.jsonl`
2. Replay the two arms:
   `python3 scripts/run_replay.py replay --corpus results/f4_clean/corpus.jsonl \
      --versions V3_NoStructural V3_Intervention --set A --out results/f4_clean/replay`
3. **Acceptance gate (the ground-truth check):** for every scenario,
   - `V3_NoStructural` (claim-only) outcome **= PASS** (it must MISS — proving answer-local
     blindness), AND
   - `V3_Intervention` (+structural) outcome **= BLOCK** (it must CATCH — proving the
     state-transition check fired).
   - Any scenario where `V3_NoStructural` already BLOCKs is **NOT clean** → fix the wording
     (it leaked a checkable post-state claim) or drop it.
4. Confirm the structural reason in the trace: `V3_Intervention` BLOCK must carry a
   state-transition / false-success structural issue, not a claim contradiction.

## 4. Reporting

One small paired table (claim-only vs +structural) on the clean-F4 set, expected to read
≈ 0% vs ≈ 100%. Pair it in the thesis with the Set A F4 result (100% vs 100%) and the
collapse argument from §1: *F4 is answer-local when state is observable (Set A); the
state-transition check is necessary and sufficient exactly when the post-state is ambiguous
(this set).* Position as a **mechanism demonstration**, not a headline rate.

## 5. Scope / honesty

- This is a **constructed demonstration** of an existing mechanism, not a discovered field
  result. Say so.
- It requires a minimal schema/tool addition; keep it isolated (`RG_DB_SUFFIX=f4clean`) so the
  authoritative Set A batch is untouched.
- Offline + deterministic; no network. Lower effort than the citation experiment.
