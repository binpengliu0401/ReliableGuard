"""False-alarm detail analysis — reads monitor JSONL files and categorises every
blocked-but-passing trajectory (gold_reward=1, v_structural_verdict=BLOCK) by the
type of claim that triggered the block.

Requires monitor files produced with block_detail logging (eval/monitor_pass.py ≥ this PR).

Usage:
  .venv/bin/python -m eval.false_alarm_analysis
  .venv/bin/python -m eval.false_alarm_analysis --model deepseek_deepseek-v4-pro
  .venv/bin/python -m eval.false_alarm_analysis --detail   # print every case
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


_MONITOR_DIR = Path("results/monitor")


def _classify_block_cause(row: dict) -> str:
    """Return a short label for why this BLOCK fired."""
    detail = row.get("block_detail") or {}
    violations = detail.get("trace_violations", [])
    contradicted = detail.get("contradicted_claims", [])

    if not contradicted and violations:
        return "trace_only"

    if not contradicted:
        return "unknown"

    # Inspect the first (and usually only) contradicted claim
    # All claims should have time_range='after_action' after the scope fix.
    # Remaining causes: verifier precision errors (format, rounding, etc.)
    causes = []
    for c in contradicted:
        tr = c.get("time_range") or "null"
        reason = (c.get("reason") or "").lower()
        if tr in ("before_action", "future_plan", "during_action"):
            causes.append("scope_leak")          # scope filter missed this
        elif "not found" in reason or "missing" in reason:
            causes.append("missing_field")        # verifier couldn't locate the attribute
        elif "mismatch" in reason or "expected" in reason or "got" in reason:
            causes.append("value_mismatch")       # value was present but differed
        else:
            causes.append("other")

    # Return the dominant cause
    counter = Counter(causes)
    return counter.most_common(1)[0][0]


def analyse(monitor_dir: Path, model_filter: str | None, print_detail: bool) -> None:
    paths = sorted(monitor_dir.glob("*.jsonl"))
    if model_filter:
        slug = model_filter.replace("/", "_")
        paths = [p for p in paths if slug in p.stem]

    for path in paths:
        rows = []
        for line in path.open():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        false_alarms = [
            r for r in rows
            if r.get("gold_reward") == 1 and r.get("v_structural_verdict") == "BLOCK"
        ]
        total_pass = sum(1 for r in rows if r.get("gold_reward") == 1
                         and r.get("v_structural_verdict") != "AUDIT_FAILED")

        print(f"\n{'='*70}")
        print(f"  {path.stem}")
        print(f"  false alarms: {len(false_alarms)} / {total_pass} passing tasks "
              f"({len(false_alarms)/total_pass:.1%} FPR)")

        if not false_alarms:
            continue

        has_detail = any(r.get("block_detail") is not None for r in false_alarms)
        if not has_detail:
            print("  [no block_detail — run monitor_pass again to get per-claim breakdown]")
            _print_n_contradicted_dist(false_alarms)
            continue

        cause_counts: Counter[str] = Counter()
        cause_by_n: dict[str, list[int]] = defaultdict(list)
        for r in false_alarms:
            cause = _classify_block_cause(r)
            cause_counts[cause] += 1
            cause_by_n[cause].append(r.get("n_contradicted", 0))

        print(f"\n  Block-cause breakdown:")
        for cause, count in cause_counts.most_common():
            ns = cause_by_n[cause]
            avg_n = sum(ns) / len(ns)
            print(f"    {cause:<20} {count:>4}  ({count/len(false_alarms):.0%})  "
                  f"avg n_contradicted={avg_n:.1f}")

        if print_detail:
            print(f"\n  Individual false alarms:")
            for r in sorted(false_alarms, key=lambda x: (x["task_id"], x["repeat"])):
                cause = _classify_block_cause(r)
                detail = r.get("block_detail") or {}
                print(f"\n    task={r['task_id']} repeat={r['repeat']} "
                      f"n_contra={r['n_contradicted']} cause={cause}")
                for c in detail.get("contradicted_claims", []):
                    print(f"      [{c.get('time_range','?'):>15}] {c.get('text','')[:80]}")
                    print(f"        attr={c.get('attribute')}  value={c.get('value')}")
                    print(f"        reason: {c.get('reason','')[:120]}")
                for v in detail.get("trace_violations", []):
                    print(f"      [trace] {v[:120]}")


def _print_n_contradicted_dist(false_alarms: list[dict]) -> None:
    dist: Counter[int] = Counter(r.get("n_contradicted", 0) for r in false_alarms)
    print(f"\n  n_contradicted distribution:")
    for k in sorted(dist):
        print(f"    n={k}: {dist[k]} ({dist[k]/len(false_alarms):.0%})")


def main() -> None:
    parser = argparse.ArgumentParser(description="False-alarm detail analysis")
    parser.add_argument("--monitor-dir", default="results/monitor")
    parser.add_argument("--model", default=None, help="filter to one model slug")
    parser.add_argument("--detail", action="store_true",
                        help="print every false-alarm case with claim text")
    args = parser.parse_args()
    analyse(Path(args.monitor_dir), args.model, args.detail)


if __name__ == "__main__":
    main()
