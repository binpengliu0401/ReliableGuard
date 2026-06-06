#!/usr/bin/env python3
"""
Post-hoc threshold sensitivity analysis for the score-based WARN decision.

The policy engine issues WARN when reliability_score < threshold (currently 0.6).
This script re-applies that decision at threshold values {0.5, 0.6, 0.7} over
existing result CSVs and reports how FAR and RDR change.

Scope: this is a score-only counterfactual using CSV rows. Recorded BLOCK rows
are kept as BLOCK. Non-BLOCK rows are recomputed as WARN/PASS from
reliability_score. Claim-level WARN causes cannot be reconstructed from CSV
without saved reliability traces.

By default, only V3_Intervention rows are analyzed so the output is not confused
with baseline or audit-only behavior. Pass --version all to include every
version in the CSV.

Usage:
    python3 scripts/threshold_sensitivity.py [--version V3_Intervention] <rows_csv> [<rows_csv> ...]

Example:
    python3 scripts/threshold_sensitivity.py \\
        results/set_a_full/20260526/173346/set_a_rows.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

THRESHOLDS = [0.5, 0.6, 0.7]
CURRENT_THRESHOLD = 0.6


def _adjusted_outcome(actual: str, score_str: str, threshold: float) -> str:
    if actual in {"BLOCK", "AUDIT_FAILED"} or not score_str:
        return actual
    try:
        score = float(score_str)
    except ValueError:
        return actual
    return "WARN" if score < threshold else "PASS"


def _compute(rows: list[dict], threshold: float) -> dict:
    risky_total = 0
    false_accept = 0
    risk_detected = 0
    for row in rows:
        expected = row.get("expected_outcome", "")
        actual = _adjusted_outcome(
            row.get("actual_outcome", ""),
            row.get("reliability_score", ""),
            threshold,
        )
        if expected in {"BLOCK", "WARN"}:
            risky_total += 1
            if actual == "PASS":
                false_accept += 1
            elif actual in {"BLOCK", "WARN", "AUDIT_FAILED"}:
                risk_detected += 1
    far = round(false_accept / risky_total, 3) if risky_total else None
    rdr = round(risk_detected / risky_total, 3) if risky_total else None
    return {"far": far, "rdr": rdr, "n": risky_total}


def _print_table(rows: list[dict], label: str) -> None:
    print(f"\n{label}  (n={len(rows)} total rows)")
    print(f"  {'Threshold':<12} {'FAR':<8} {'RDR':<8} {'Risky tasks'}")
    print("  " + "-" * 42)
    for t in THRESHOLDS:
        s = _compute(rows, t)
        marker = "  ← current" if t == CURRENT_THRESHOLD else ""
        print(
            f"  {t:<12.1f} {str(s['far']):<8} {str(s['rdr']):<8} {s['n']}{marker}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-hoc score-threshold sensitivity over result CSV rows.",
    )
    parser.add_argument(
        "rows_csv",
        nargs="+",
        help="One or more run_ablation row CSV files, such as set_a_rows.csv.",
    )
    parser.add_argument(
        "--version",
        default="V3_Intervention",
        help="Version to analyze; pass 'all' to include every version.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    all_rows: list[dict] = []
    for path_str in args.rows_csv:
        path = Path(path_str)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, newline="", encoding="utf-8") as f:
            all_rows.extend(list(csv.DictReader(f)))

    if not all_rows:
        print("No rows loaded.", file=sys.stderr)
        sys.exit(1)

    if args.version != "all":
        all_rows = [row for row in all_rows if row.get("version") == args.version]
        if not all_rows:
            print(f"No rows found for version={args.version}.", file=sys.stderr)
            sys.exit(1)

    versions = sorted({r["version"] for r in all_rows if r.get("version")})
    domains = sorted({r["domain"] for r in all_rows if r.get("domain")})

    print(f"Loaded {len(all_rows)} rows | versions: {versions} | domains: {domains}")
    print(
        "\nNote: this is a score-only counterfactual from CSV rows. "
        "Recorded BLOCK rows are unchanged; non-BLOCK rows are recomputed "
        "from reliability_score."
    )

    _print_table(all_rows, "ALL")

    if len(domains) > 1:
        for domain in domains:
            d_rows = [r for r in all_rows if r.get("domain") == domain]
            _print_table(d_rows, f"Domain: {domain}")

    if len(versions) > 1:
        for version in versions:
            v_rows = [r for r in all_rows if r.get("version") == version]
            _print_table(v_rows, f"Version: {version}")


if __name__ == "__main__":
    main()
