#!/usr/bin/env python3
"""
Smoke-run validator: checks the three pre-full-run gates from docs/rerun_plan.md.

Given the smoke `set_a_rows.csv`, reports PASS/FAIL on:
  1. Error rate ~0          -- confirms the max_tokens truncation fix.
  2. trace_summary populated -- confirms decomposition input is captured (V2/V3
                                rows that extracted >=1 claim must carry it).
  3. (optional) Determinism  -- pass a second CSV; per-scenario actual_audit_outcome
                                must match, confirming agent temperature=0.0.

Usage:
    python3 scripts/validate_smoke.py results/smoke/.../set_a_rows.csv
    python3 scripts/validate_smoke.py run1.csv --compare run2.csv   # determinism
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ERROR_RATE_GATE = 0.02  # smoke should have ~0 errors after the max_tokens fix


def _load(path_str: str) -> list[dict]:
    path = Path(path_str)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _key(row: dict) -> tuple:
    return (row.get("scenario_id"), row.get("version"), row.get("seed"))


def check_errors(rows: list[dict]) -> bool:
    errs = [r for r in rows if (r.get("error") or "").strip()]
    rate = len(errs) / len(rows) if rows else 0.0
    ok = rate <= ERROR_RATE_GATE
    print(f"[{'PASS' if ok else 'FAIL'}] error rate: {len(errs)}/{len(rows)} = {rate*100:.1f}% "
          f"(gate <= {ERROR_RATE_GATE*100:.0f}%)")
    if errs:
        kinds = Counter(r["error"].strip()[:60] for r in errs)
        for k, c in kinds.most_common(5):
            print(f"        {c:4d}  {k}")
    return ok


def check_trace_summary(rows: list[dict]) -> bool:
    if "trace_summary" not in (rows[0] if rows else {}):
        print("[FAIL] trace_summary: column missing (old code path?)")
        return False
    # Rows where a claim pipeline ran and extracted >=1 claim should carry it.
    pipeline_rows = [
        r for r in rows
        if r.get("version") in {"V2_AuditOnly", "V3_Intervention", "V3_NoStructural"}
        and not (r.get("error") or "").strip()
        and (r.get("claim_count") or "0") not in ("", "0")
    ]
    if not pipeline_rows:
        print("[WARN] trace_summary: no pipeline rows with claims to check (smoke too small / all 0-claim)")
        return True
    populated = 0
    for r in pipeline_rows:
        try:
            ts = json.loads(r.get("trace_summary") or "[]")
        except (ValueError, TypeError):
            ts = []
        if isinstance(ts, list) and ts:
            populated += 1
    ok = populated == len(pipeline_rows)
    print(f"[{'PASS' if ok else 'FAIL'}] trace_summary populated: "
          f"{populated}/{len(pipeline_rows)} pipeline rows with claims")
    return ok


def check_determinism(rows_a: list[dict], rows_b: list[dict]) -> bool:
    a = {_key(r): r.get("actual_audit_outcome") for r in rows_a}
    b = {_key(r): r.get("actual_audit_outcome") for r in rows_b}
    common = set(a) & set(b)
    if not common:
        print("[FAIL] determinism: no overlapping (scenario, version, seed) keys")
        return False
    mismatches = [k for k in common if a[k] != b[k]]
    ok = not mismatches
    print(f"[{'PASS' if ok else 'FAIL'}] determinism: "
          f"{len(common) - len(mismatches)}/{len(common)} audit outcomes match")
    for k in mismatches[:8]:
        print(f"        {k}: {a[k]} != {b[k]}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a smoke run against the rerun gates.")
    parser.add_argument("rows_csv", help="Smoke set_a_rows.csv")
    parser.add_argument("--compare", help="Second run's CSV for the determinism check.")
    args = parser.parse_args()

    rows = _load(args.rows_csv)
    print(f"Loaded {len(rows)} rows from {args.rows_csv}\n")

    results = [check_errors(rows), check_trace_summary(rows)]
    if args.compare:
        results.append(check_determinism(rows, _load(args.compare)))
    else:
        print("[SKIP] determinism: pass --compare <run2.csv> (re-run smoke once) to check temp=0.0")

    print()
    if all(results):
        print("SMOKE OK — safe to archive old batches and launch the full run.")
        sys.exit(0)
    print("SMOKE NOT CLEAN — do not launch the full run; address the FAIL(s) above.")
    sys.exit(1)


if __name__ == "__main__":
    main()
