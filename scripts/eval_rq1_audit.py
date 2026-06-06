#!/usr/bin/env python3
"""
T6 RQ1 analysis: pure claim-level audit ability, by failure stratum.

RQ1 asks how well the claim pipeline *detects* a risk on its own, independent of
enforcement. The right signal is the audit verdict (`actual_audit_outcome`,
i.e. `derive_audit_outcome`) of `V2_AuditOnly` -- enforcement is off there, so the
enforced `actual_outcome` is forced PASS while the audit verdict still records what
the pipeline would have flagged. (Do not use V3 numbers for RQ1: those fold in the
structural trace/state checks, which is RQ2.)

For each domain x failure stratum this reports:
  - risky strata (expected BLOCK/WARN): audit detection rate = caught / evaluable,
    where "caught" = audit verdict in {BLOCK, WARN};
  - benign strata (expected PASS): audit false-alarm rate = flagged / evaluable.
Tasks that errored (audit verdict ERROR -- LLM infra / truncation) are excluded
from rate denominators and reported separately as error_rate, since a crashed task
is not an audit decision.

This reads the existing authoritative `set_a_rows.csv` (no rerun needed; the audit
verdict is already recorded there). The extractor coverage ceiling (the other half
of RQ1) comes from `scripts/eval_extractor.py` and is referenced, not recomputed.

Usage:
    python3 scripts/eval_rq1_audit.py results/set_a_full/.../set_a_rows.csv
    python3 scripts/eval_rq1_audit.py --version V2_AuditOnly --json <rows_csv>
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RISKY = {"BLOCK", "WARN"}
_STRATUM_RE = re.compile(r"F(\d)")


def _stratum(scenario_id: str) -> str:
    m = _STRATUM_RE.search(scenario_id or "")
    return f"F{m.group(1)}" if m else "F?"


def _blank() -> dict:
    return {"n": 0, "error": 0, "caught": 0, "expected_risky": 0, "expected_benign": 0}


def analyze(rows: list[dict], version: str) -> dict:
    """domain -> stratum -> counts, for the chosen version."""
    tree: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(_blank))
    for row in rows:
        if row.get("version") != version:
            continue
        domain = row.get("domain") or "?"
        stratum = _stratum(row.get("scenario_id", ""))
        expected = row.get("expected_outcome") or ""
        audit = row.get("actual_audit_outcome") or ""
        cell = tree[domain][stratum]
        cell["n"] += 1
        if expected in RISKY:
            cell["expected_risky"] += 1
        else:
            cell["expected_benign"] += 1
        if audit == "ERROR" or (row.get("error") or "").strip():
            cell["error"] += 1
            continue
        if audit in RISKY:
            cell["caught"] += 1
    return {d: dict(s) for d, s in tree.items()}


def _rates(cell: dict) -> dict:
    evaluable = cell["n"] - cell["error"]
    risky = cell["expected_risky"] > 0
    rate = (cell["caught"] / evaluable) if evaluable else None
    return {
        "kind": "risky" if risky else "benign",
        "n": cell["n"],
        "evaluable": evaluable,
        "error": cell["error"],
        "error_rate": round(cell["error"] / cell["n"], 3) if cell["n"] else None,
        # For risky strata `rate` is the audit detection rate; for benign strata it
        # is the audit false-alarm rate (both = flagged / evaluable).
        "detection_rate": round(rate, 3) if (rate is not None and risky) else None,
        "false_alarm_rate": round(rate, 3) if (rate is not None and not risky) else None,
        "flagged": cell["caught"],
    }


def _pct(x) -> str:
    return "  --  " if x is None else f"{x * 100:5.1f}%"


def print_report(tree: dict, version: str) -> None:
    print(f"\nVERSION: {version}  — pure claim-level audit verdict (RQ1)")
    print("Risky strata report detection rate; benign strata (F0/F5) report false-alarm rate.")
    for domain in sorted(tree):
        print(f"\nDomain: {domain}")
        print(f"  {'stratum':<8} {'expect':<7} {'n':>5} {'err':>5} {'eval':>5} "
              f"{'detect':>8} {'falarm':>8}")
        print("  " + "-" * 56)
        agg_risky = {"evaluable": 0, "caught": 0}
        agg_benign = {"evaluable": 0, "caught": 0}
        for stratum in sorted(tree[domain]):
            cell = tree[domain][stratum]
            r = _rates(cell)
            exp = "BLOCK" if r["kind"] == "risky" else "PASS"
            print(f"  {stratum:<8} {exp:<7} {r['n']:>5} {r['error']:>5} {r['evaluable']:>5} "
                  f"{_pct(r['detection_rate'])} {_pct(r['false_alarm_rate'])}")
            target = agg_risky if r["kind"] == "risky" else agg_benign
            target["evaluable"] += r["evaluable"]
            target["caught"] += r["flagged"]
        print("  " + "-" * 56)
        dr = agg_risky["caught"] / agg_risky["evaluable"] if agg_risky["evaluable"] else None
        far = agg_benign["caught"] / agg_benign["evaluable"] if agg_benign["evaluable"] else None
        print(f"  audit detection rate (risky, eval={agg_risky['evaluable']}): {_pct(dr)}")
        print(f"  audit false-alarm rate (benign, eval={agg_benign['evaluable']}): {_pct(far)}")


def _build_json(tree: dict) -> dict:
    out: dict = {}
    for domain, strata in tree.items():
        out[domain] = {"by_stratum": {}}
        agg_risky = {"evaluable": 0, "caught": 0}
        agg_benign = {"evaluable": 0, "caught": 0}
        for stratum, cell in strata.items():
            r = _rates(cell)
            out[domain]["by_stratum"][stratum] = r
            target = agg_risky if r["kind"] == "risky" else agg_benign
            target["evaluable"] += r["evaluable"]
            target["caught"] += r["flagged"]
        out[domain]["audit_detection_rate"] = (
            round(agg_risky["caught"] / agg_risky["evaluable"], 4)
            if agg_risky["evaluable"] else None
        )
        out[domain]["audit_false_alarm_rate"] = (
            round(agg_benign["caught"] / agg_benign["evaluable"], 4)
            if agg_benign["evaluable"] else None
        )
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RQ1 pure-audit detection by failure stratum (T6).",
    )
    parser.add_argument("rows_csv", nargs="+", help="run_ablation rows CSV(s).")
    parser.add_argument("--version", default="V2_AuditOnly", help="Version to analyze.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of tables.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rows: list[dict] = []
    for path_str in args.rows_csv:
        path = Path(path_str)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(list(csv.DictReader(f)))

    tree = analyze(rows, args.version)
    if not tree:
        print(f"No rows for version={args.version}.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(_build_json(tree), indent=2))
    else:
        print_report(tree, args.version)


if __name__ == "__main__":
    main()
