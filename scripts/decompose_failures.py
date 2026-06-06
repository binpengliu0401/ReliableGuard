#!/usr/bin/env python3
"""
T4 failure-attribution decomposer (RQ3 core evidence; also feeds RQ1).

For every risk-bearing task (expected verdict in {BLOCK, WARN}) this classifies
WHY the claim-level audit did or did not catch the risk, into four buckets:

  - correct        : the audit flagged the risk (audit verdict BLOCK/WARN).
  - not_extracted  : nothing usable was extracted to audit (claim_count == 0,
                     i.e. the AUDIT_FAILED / empty-pipeline case) -- a coverage
                     bottleneck in the extractor.
  - misjudged      : claims were extracted AND the verifier consulted a source
                     for at least one of them, but the risk still slipped through
                     (verifier had evidence and ruled it clean) -- a verifier
                     bottleneck.
  - no_evidence    : claims were extracted but no source could be consulted to
                     rule on them (all claims `source_mode=unavailable` / never
                     grounded) -- an evidence-availability bottleneck.

Input is one or more `*_rows.csv` produced by `scripts/run_ablation.py`. The
per-claim signal is read from the row's `trace_summary` column (added so the
decomposition is batch-exact and self-contained; the older authoritative batch
predates it and cannot be decomposed -- see CLAUDE.md T4 note).

source_mode (T1) is the primary misjudged/no_evidence discriminator. When it is
absent (pre-T1 rows) the script falls back to evidence_state: a definite
supported/contradicted ruling implies a source was consulted.

Usage:
    python3 scripts/decompose_failures.py results/.../set_a_rows.csv
    python3 scripts/decompose_failures.py --version V2_AuditOnly set_a_rows.csv
    python3 scripts/decompose_failures.py --json set_a_rows.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RISKY = {"BLOCK", "WARN"}
CATEGORIES = ["correct", "not_extracted", "misjudged", "no_evidence"]
_STRATUM_RE = re.compile(r"F(\d)")


def _stratum(scenario_id: str) -> str:
    m = _STRATUM_RE.search(scenario_id or "")
    return f"F{m.group(1)}" if m else "F?"


def _parse_trace_summary(raw: str) -> list[dict]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _had_evidence(claims: list[dict]) -> bool:
    """Whether the verifier consulted an evidence source for >= 1 claim.

    Primary signal: source_mode == "fixture" (a source was available and used).
    Pre-T1 fallback (source_mode is None): a definite supported/contradicted
    evidence_state implies the verifier compared against a source.
    """
    for c in claims:
        source_mode = c.get("source_mode")
        evidence_state = c.get("evidence_state")
        if source_mode == "fixture":
            return True
        if source_mode is None and evidence_state in {"supported", "contradicted"}:
            return True
    return False


def classify(row: dict) -> str:
    """Attribution bucket for one risk-bearing task row."""
    audit = row.get("actual_audit_outcome") or row.get("actual_outcome") or ""
    if audit in RISKY:
        return "correct"

    claims = _parse_trace_summary(row.get("trace_summary", ""))
    # Claim-level catch even if the aggregate verdict differs.
    if any(c.get("action") in RISKY for c in claims):
        return "correct"

    claim_count = row.get("claim_count")
    try:
        n_claims = int(claim_count) if claim_count not in (None, "") else len(claims)
    except (ValueError, TypeError):
        n_claims = len(claims)

    if audit == "AUDIT_FAILED" or n_claims == 0:
        return "not_extracted"
    return "misjudged" if _had_evidence(claims) else "no_evidence"


def _blank_counts() -> dict[str, int]:
    return {cat: 0 for cat in CATEGORIES}


def decompose(rows: list[dict]) -> dict:
    """Return nested counts: version -> domain -> stratum -> category counts."""
    tree: dict[str, dict] = {}
    for row in rows:
        if (row.get("expected_outcome") or "") not in RISKY:
            continue
        if (row.get("error") or "").strip():
            continue
        version = row.get("version") or "?"
        domain = row.get("domain") or "?"
        stratum = _stratum(row.get("scenario_id", ""))
        category = classify(row)
        node = (
            tree.setdefault(version, {})
            .setdefault(domain, {})
            .setdefault(stratum, _blank_counts())
        )
        node[category] += 1
    return tree


# --- reporting --------------------------------------------------------------


def _sum_counts(*counts: dict[str, int]) -> dict[str, int]:
    out = _blank_counts()
    for c in counts:
        for cat in CATEGORIES:
            out[cat] += c.get(cat, 0)
    return out


def _row_total(counts: dict[str, int]) -> int:
    return sum(counts.get(cat, 0) for cat in CATEGORIES)


def _fmt_cell(n: int, total: int) -> str:
    if total == 0:
        return f"{n} (--)"
    return f"{n} ({n / total * 100:.0f}%)"


def _print_table(title: str, by_stratum: dict[str, dict[str, int]]) -> None:
    print(f"\n{title}")
    header = f"  {'stratum':<8} {'n':>5}  " + "  ".join(f"{cat:<16}" for cat in CATEGORIES)
    print(header)
    print("  " + "-" * (len(header) - 2))
    domain_total = _blank_counts()
    for stratum in sorted(by_stratum):
        counts = by_stratum[stratum]
        total = _row_total(counts)
        cells = "  ".join(f"{_fmt_cell(counts[cat], total):<16}" for cat in CATEGORIES)
        print(f"  {stratum:<8} {total:>5}  {cells}")
        domain_total = _sum_counts(domain_total, counts)
    total = _row_total(domain_total)
    cells = "  ".join(f"{_fmt_cell(domain_total[cat], total):<16}" for cat in CATEGORIES)
    print("  " + "-" * (len(header) - 2))
    print(f"  {'ALL':<8} {total:>5}  {cells}")


def print_report(tree: dict) -> None:
    for version in sorted(tree):
        print("\n" + "=" * 78)
        print(f"VERSION: {version}  (risk-bearing tasks only)")
        for domain in sorted(tree[version]):
            _print_table(f"Domain: {domain}", tree[version][domain])


def _build_json(tree: dict) -> dict:
    out: dict = {}
    for version, domains in tree.items():
        out[version] = {}
        for domain, strata in domains.items():
            domain_total = _sum_counts(*strata.values())
            total = _row_total(domain_total)
            out[version][domain] = {
                "by_stratum": strata,
                "total": domain_total,
                "shares": {
                    cat: round(domain_total[cat] / total, 4) if total else None
                    for cat in CATEGORIES
                },
                "n": total,
            }
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decompose missed/caught risk detections into "
        "not_extracted / misjudged / no_evidence / correct (T4, RQ3).",
    )
    parser.add_argument(
        "rows_csv",
        nargs="+",
        help="One or more run_ablation row CSVs (must carry the trace_summary column).",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Restrict to a single version (e.g. V2_AuditOnly). Default: all present.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit nested counts + per-domain shares as JSON instead of tables.",
    )
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

    if not rows:
        print("No rows loaded.", file=sys.stderr)
        sys.exit(1)

    if "trace_summary" not in rows[0]:
        print(
            "ERROR: rows CSV has no 'trace_summary' column -- it predates the T4 "
            "per-row trace persistence and cannot be decomposed. Re-run with the "
            "current scripts/run_ablation.py.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.version:
        rows = [r for r in rows if r.get("version") == args.version]
        if not rows:
            print(f"No rows for version={args.version}.", file=sys.stderr)
            sys.exit(1)

    tree = decompose(rows)
    if not tree:
        print("No risk-bearing (expected BLOCK/WARN) tasks found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(_build_json(tree), indent=2))
    else:
        print_report(tree)


if __name__ == "__main__":
    main()
