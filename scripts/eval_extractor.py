#!/usr/bin/env python3
"""
T3 extractor-quality scorer for the RQ1 coverage-ceiling study.

Reads the two human-annotated workbooks under eval/annotation/ and reports
claim-extraction precision / recall / F1 plus the headline "not-extracted
coverage ceiling". See eval/annotation/README.md ("How it is scored") for the
authoritative definitions; this script implements them.

Scoring (per README):
  - Precision = valid predicted / all predicted            (File 1, claim-level)
  - Recall    = valid predicted / (valid predicted + missed)
                missed comes from File 2 (missed risk claims + extra
                other_missed items, de-duplicated; see _count_missed)
  - F1        = harmonic mean of precision and recall
  - Not-extracted coverage ceiling = share of risk-bearing samples
                (risk_claim_in_answer=1) whose risk claim was NOT extracted
                (risk_claim_extracted=0) -- the headline RQ1 number (File 2)

De-duplication note: when a sample's risk claim was missed
(risk_claim_extracted=0) the annotators often restate that same miss in
other_missed. To avoid double counting, other_missed items are only added to
the missed total for rows whose risk claim WAS extracted (or that carry no risk
claim); rows that already missed their risk claim contribute exactly one miss.

Usage:
    python3 scripts/eval_extractor.py
    python3 scripts/eval_extractor.py \\
        --claims eval/annotation/extractor_annotation_claims.csv \\
        --coverage eval/annotation/extractor_annotation_coverage.csv
    python3 scripts/eval_extractor.py --json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLAIMS = REPO_ROOT / "eval" / "annotation" / "extractor_annotation_claims.csv"
DEFAULT_COVERAGE = REPO_ROOT / "eval" / "annotation" / "extractor_annotation_coverage.csv"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or (precision + recall) == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _split_other_missed(value: str) -> list[str]:
    """Semicolon-separated other_missed items, dropping blanks and 'none'."""
    return [
        item.strip()
        for item in value.split(";")
        if item.strip() and item.strip().lower() != "none"
    ]


# --- precision (File 1) -----------------------------------------------------


def precision_stats(claims: list[dict]) -> dict:
    total = len(claims)
    valid = sum(1 for r in claims if r["valid"].strip() == "1")
    return {
        "total_predicted": total,
        "valid_predicted": valid,
        "invalid_predicted": total - valid,
        "precision": (valid / total) if total else None,
    }


def precision_by(claims: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = {}
    for r in claims:
        groups.setdefault(r[key], []).append(r)
    return {g: precision_stats(rows) for g, rows in sorted(groups.items())}


# --- coverage / recall (File 2) ---------------------------------------------


def _count_missed(coverage: list[dict]) -> int:
    """Total de-duplicated missed claims used in the recall denominator.

    A row whose risk claim was missed contributes exactly one miss (its
    other_missed text restates that same miss, so it is not added again). A row
    whose risk claim was extracted (or that has no risk claim) contributes one
    miss per distinct other_missed item.
    """
    missed = 0
    for r in coverage:
        if r["risk_claim_extracted"].strip() == "0":
            missed += 1
        else:
            missed += len(_split_other_missed(r["other_missed"]))
    return missed


def coverage_stats(coverage: list[dict]) -> dict:
    risk_bearing = [r for r in coverage if r["risk_claim_in_answer"].strip() == "1"]
    extracted = sum(1 for r in risk_bearing if r["risk_claim_extracted"].strip() == "1")
    missed = sum(1 for r in risk_bearing if r["risk_claim_extracted"].strip() == "0")
    n = len(risk_bearing)
    return {
        "samples": len(coverage),
        "risk_bearing": n,
        "risk_extracted": extracted,
        "risk_missed": missed,
        "risk_recall": (extracted / n) if n else None,
        "coverage_ceiling": (missed / n) if n else None,
    }


def coverage_by(coverage: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = {}
    for r in coverage:
        groups.setdefault(r[key], []).append(r)
    return {g: coverage_stats(rows) for g, rows in sorted(groups.items())}


# --- reporting --------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


def _print_precision_block(claims: list[dict]) -> None:
    overall = precision_stats(claims)
    print("\n=== PRECISION (File 1, one row per predicted claim) ===")
    print(
        f"  Overall: {overall['valid_predicted']}/{overall['total_predicted']} valid "
        f"= {_pct(overall['precision'])}  "
        f"({overall['invalid_predicted']} invalid)"
    )

    print("\n  By domain:")
    print(f"    {'domain':<12} {'valid/total':<14} {'precision'}")
    print("    " + "-" * 40)
    for g, s in precision_by(claims, "domain").items():
        ratio = f"{s['valid_predicted']}/{s['total_predicted']}"
        print(f"    {g:<12} {ratio:<14} {_pct(s['precision'])}")

    print("\n  By stratum:")
    print(f"    {'stratum':<12} {'valid/total':<14} {'precision'}")
    print("    " + "-" * 40)
    for g, s in precision_by(claims, "stratum").items():
        ratio = f"{s['valid_predicted']}/{s['total_predicted']}"
        print(f"    {g:<12} {ratio:<14} {_pct(s['precision'])}")

    invalid = [r for r in claims if r["valid"].strip() != "1"]
    if invalid:
        print(f"\n  Invalid claims ({len(invalid)}):")
        for r in invalid:
            note = r["note"].strip() or "(no note)"
            print(
                f"    {r['sample_id']} idx{r['claim_idx']} "
                f"[{r['domain']}/{r['stratum']}] -- {note}"
            )


def _print_coverage_block(coverage: list[dict]) -> None:
    overall = coverage_stats(coverage)
    print("\n=== COVERAGE CEILING (File 2, one row per sample) ===")
    print(
        f"  Risk-bearing samples: {overall['risk_bearing']}/{overall['samples']} "
        f"(remaining {overall['samples'] - overall['risk_bearing']} have no risk claim)"
    )
    print(
        f"  Risk claim extracted: {overall['risk_extracted']}/{overall['risk_bearing']} "
        f"= {_pct(overall['risk_recall'])} (risk-claim recall)"
    )
    print(
        f"  >> Not-extracted coverage ceiling: "
        f"{overall['risk_missed']}/{overall['risk_bearing']} "
        f"= {_pct(overall['coverage_ceiling'])}  [headline RQ1 number]"
    )

    print("\n  By domain:")
    print(f"    {'domain':<12} {'missed/risk':<14} {'ceiling'}")
    print("    " + "-" * 40)
    for g, s in coverage_by(coverage, "domain").items():
        ratio = f"{s['risk_missed']}/{s['risk_bearing']}"
        print(f"    {g:<12} {ratio:<14} {_pct(s['coverage_ceiling'])}")

    print("\n  By stratum:")
    print(f"    {'stratum':<14} {'missed/risk':<14} {'ceiling'}")
    print("    " + "-" * 42)
    for g, s in coverage_by(coverage, "stratum").items():
        ratio = f"{s['risk_missed']}/{s['risk_bearing']}"
        print(f"    {g:<14} {ratio:<14} {_pct(s['coverage_ceiling'])}")

    missed = [r for r in coverage if r["risk_claim_extracted"].strip() == "0"]
    if missed:
        print(f"\n  Missed risk claims ({len(missed)}):")
        for r in missed:
            text = r["risk_claim_text"].strip() or "(no text)"
            print(f"    {r['sample_id']} [{r['domain']}/{r['stratum']}] -- {text}")


def _print_summary_block(claims: list[dict], coverage: list[dict]) -> None:
    p = precision_stats(claims)["precision"]
    valid = precision_stats(claims)["valid_predicted"]
    missed = _count_missed(coverage)
    recall = (valid / (valid + missed)) if (valid + missed) else None
    f1 = _f1(p, recall)
    print("\n=== CLAIM-LEVEL PRECISION / RECALL / F1 ===")
    print(f"  Precision = {_pct(p)}")
    print(
        f"  Recall    = {_pct(recall)}  "
        f"(valid {valid} / (valid {valid} + missed {missed}))"
    )
    print(f"  F1        = {_pct(f1)}")


def _build_json(claims: list[dict], coverage: list[dict]) -> dict:
    p = precision_stats(claims)
    cov = coverage_stats(coverage)
    valid = p["valid_predicted"]
    missed = _count_missed(coverage)
    recall = (valid / (valid + missed)) if (valid + missed) else None
    return {
        "precision": {
            "overall": p,
            "by_domain": precision_by(claims, "domain"),
            "by_stratum": precision_by(claims, "stratum"),
        },
        "coverage": {
            "overall": cov,
            "by_domain": coverage_by(coverage, "domain"),
            "by_stratum": coverage_by(coverage, "stratum"),
        },
        "claim_level": {
            "precision": p["precision"],
            "recall": recall,
            "f1": _f1(p["precision"], recall),
            "valid_predicted": valid,
            "missed": missed,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score extractor precision / recall / F1 + coverage ceiling "
        "from the eval/annotation workbooks (RQ1).",
    )
    parser.add_argument(
        "--claims",
        type=Path,
        default=DEFAULT_CLAIMS,
        help="File 1 (per predicted claim) CSV. Default: eval/annotation/...",
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=DEFAULT_COVERAGE,
        help="File 2 (per sample) CSV. Default: eval/annotation/...",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full metric tree as JSON instead of the text report.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    claims = _load(args.claims)
    coverage = _load(args.coverage)

    unscored = [r for r in claims if r["valid"].strip() not in {"0", "1"}]
    if unscored:
        print(
            f"WARNING: {len(unscored)} claim rows have no valid label (0/1); "
            "they are counted as invalid. Annotation may be incomplete.",
            file=sys.stderr,
        )

    if args.json:
        print(json.dumps(_build_json(claims, coverage), indent=2))
        return

    print(
        f"Loaded {len(claims)} predicted claims and {len(coverage)} samples "
        f"from:\n  {args.claims}\n  {args.coverage}"
    )
    _print_summary_block(claims, coverage)
    _print_precision_block(claims)
    _print_coverage_block(coverage)


if __name__ == "__main__":
    main()
