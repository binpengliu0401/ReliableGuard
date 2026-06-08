#!/usr/bin/env python3
"""RQ-aligned result figures from a freeze-replay rows CSV.

Reads one `*_rows.csv` (default: results/replay/set_a_v8/set_a_rows.csv) and emits
four figures + a CSV summary into an output directory. Everything is computed
directly from the per-task rows (robust, self-contained), so the figures track
whatever batch is passed in.

Figures (mapped to the thesis RQs):
  fig_rq2_structural   - ecommerce detection by F-class, claim-only vs +structural
                         (the RQ2 "trace/state restores observability" result).
  fig_rq1_claim_only   - both domains, claim-only detection by F-class
                         (the RQ1 answer-local vs trace-local ceiling).
  fig_rq3_locus        - per-domain locus decomposition of risk-bearing tasks
                         (correct / not_extracted / misjudged / not_observable /
                         no_evidence) -- the RQ3 boundary evidence.
  fig_benign_far       - per-domain benign false-alarm rate (the FAR baseline the
                         citation/transition fixes produce).

Usage:
    python3 scripts/plot_results.py
    python3 scripts/plot_results.py results/replay/set_a_v8/set_a_rows.csv --out figures/v8
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

_CACHE = Path(tempfile.gettempdir()) / "reliable_guard_figure_cache"
(_CACHE / "mpl").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE / "mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decompose_failures import CATEGORIES, classify  # noqa: E402

DOMAINS = ["ecommerce", "reference"]
FAULTS = ["F1", "F2", "F3", "F4"]
BENIGN = ["F0", "F5"]
CAUGHT = {"BLOCK", "WARN", "AUDIT_FAILED", "ROLLBACK"}

DOMAIN_TITLE = {"ecommerce": "Ecommerce", "reference": "Reference"}
CAT_LABEL = {
    "correct": "correct",
    "not_extracted": "not_extracted",
    "misjudged": "misjudged",
    "not_observable": "not_observable",
    "no_evidence": "no_evidence",
}
CAT_COLOR = {
    "correct": "#6ACC65",
    "not_extracted": "#EE854A",
    "misjudged": "#D65F5F",
    "not_observable": "#4878CF",
    "no_evidence": "#B47CC7",
}
FAULT_COLOR = {"claim_only": "#B47CC7", "full": "#D65F5F"}


def _fclass(scenario_id: str) -> str:
    sid = scenario_id or ""
    return sid.split("-")[1] if sid.startswith("REF") else sid.split("-")[0]


def _load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _detection_by_f(rows, domain, version):
    """caught-rate per fault F-class for a version (uses audit col for V2)."""
    col = "actual_audit_outcome" if version == "V2_AuditOnly" else "actual_outcome"
    agg = defaultdict(Counter)
    for r in rows:
        if r["domain"] != domain or r["version"] != version:
            continue
        c = agg[_fclass(r["scenario_id"])]
        c["n"] += 1
        if r.get(col) in CAUGHT:
            c["caught"] += 1
    return {f: (agg[f]["caught"] / agg[f]["n"] if agg[f]["n"] else 0.0) for f in FAULTS}


def _benign_far(rows, domain, version):
    col = "actual_audit_outcome" if version == "V2_AuditOnly" else "actual_outcome"
    n = caught = 0
    for r in rows:
        if r["domain"] != domain or r["version"] != version:
            continue
        if _fclass(r["scenario_id"]) not in BENIGN:
            continue
        n += 1
        if r.get(col) in CAUGHT:
            caught += 1
    return caught / n if n else 0.0


def _annotate(ax, bars):
    for b in bars:
        h = b.get_height()
        ax.annotate(
            f"{h:.2f}",
            xy=(b.get_x() + b.get_width() / 2, h),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def _despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_rq2_structural(rows, out: Path):
    claim = _detection_by_f(rows, "ecommerce", "V3_NoStructural")
    full = _detection_by_f(rows, "ecommerce", "V3_Intervention")
    x = range(len(FAULTS))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.5, 4))
    b1 = ax.bar([i - w / 2 for i in x], [claim[f] for f in FAULTS], w,
                label="Claim-only (V3_NoStructural)", color=FAULT_COLOR["claim_only"])
    b2 = ax.bar([i + w / 2 for i in x], [full[f] for f in FAULTS], w,
                label="+ Trace/State (V3_Intervention)", color=FAULT_COLOR["full"])
    _annotate(ax, b1)
    _annotate(ax, b2)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{f}\n{n}" for f, n in
                        zip(FAULTS, ["schema", "policy", "depend", "state"])])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Detection rate")
    ax.set_title("RQ2 (Ecommerce): trace/state restores observability")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=2)
    _despine(ax)
    fig.subplots_adjust(bottom=0.26)
    fig.savefig(out / "fig_rq2_structural.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / "fig_rq2_structural.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_rq1_claim_only(rows, out: Path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, domain in zip(axes, DOMAINS):
        rates = _detection_by_f(rows, domain, "V2_AuditOnly")
        bars = ax.bar(FAULTS, [rates[f] for f in FAULTS], 0.6, color="#6ACC65")
        _annotate(ax, bars)
        ax.set_title(f"{DOMAIN_TITLE[domain]}")
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("Failure mode")
        _despine(ax)
    axes[0].set_ylabel("Detection rate (claim-only, V2)")
    fig.suptitle("RQ1: claim-channel detection by failure mode "
                 "(answer-local vs trace-local)")
    fig.savefig(out / "fig_rq1_claim_only.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / "fig_rq1_claim_only.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_rq3_locus(rows, out: Path, version="V3_Intervention"):
    # decompose risk-bearing tasks per domain into the 5 locus buckets
    by_domain = {d: Counter() for d in DOMAINS}
    for r in rows:
        if r["version"] != version:
            continue
        if (r.get("expected_outcome") or "") not in {"BLOCK", "WARN"}:
            continue
        if (r.get("error") or "").strip():
            continue
        if r["domain"] in by_domain:
            by_domain[r["domain"]][classify(r)] += 1

    fig, ax = plt.subplots(figsize=(8, 4.2))
    y = range(len(DOMAINS))
    left = {d: 0.0 for d in DOMAINS}
    totals = {d: sum(by_domain[d].values()) for d in DOMAINS}
    for cat in CATEGORIES:
        widths = []
        for d in DOMAINS:
            t = totals[d] or 1
            widths.append(by_domain[d][cat] / t)
        bars = ax.barh(list(y), widths, left=[left[d] for d in DOMAINS],
                       color=CAT_COLOR[cat], label=CAT_LABEL[cat])
        for i, d in enumerate(DOMAINS):
            frac = widths[i]
            if frac > 0.04:
                ax.text(left[d] + frac / 2, i, f"{frac*100:.0f}%",
                        ha="center", va="center", fontsize=8,
                        color="white" if cat != "not_extracted" else "black")
        for i, d in enumerate(DOMAINS):
            left[d] += widths[i]
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{DOMAIN_TITLE[d]}\n(n={totals[d]})" for d in DOMAINS])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of risk-bearing tasks")
    ax.set_title("RQ3: locus decomposition of detection bottleneck "
                 f"({version})")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncols=5)
    _despine(ax)
    fig.subplots_adjust(bottom=0.24, left=0.16)
    fig.savefig(out / "fig_rq3_locus.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / "fig_rq3_locus.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_benign_far(rows, out: Path, version="V3_Intervention"):
    far = {d: _benign_far(rows, d, version) for d in DOMAINS}
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar([DOMAIN_TITLE[d] for d in DOMAINS],
                  [far[d] for d in DOMAINS], 0.5, color="#EE854A")
    _annotate(ax, bars)
    ax.set_ylim(0, max(0.1, max(far.values()) * 1.3))
    ax.set_ylabel("Benign false-alarm rate (F0+F5)")
    ax.set_title(f"Benign FAR ({version})")
    _despine(ax)
    fig.savefig(out / "fig_benign_far.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / "fig_benign_far.pdf", bbox_inches="tight")
    plt.close(fig)


def write_summary_csv(rows, out: Path):
    path = out / "summary.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "version", "metric", "F", "value"])
        for d in DOMAINS:
            for v in ["V2_AuditOnly", "V3_NoStructural", "V3_Intervention"]:
                det = _detection_by_f(rows, d, v)
                for fc in FAULTS:
                    w.writerow([d, v, "detection", fc, f"{det[fc]:.4f}"])
                w.writerow([d, v, "benign_far", "F0+F5", f"{_benign_far(rows, d, v):.4f}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows_csv", nargs="?",
                    default="results/replay/set_a_v8/set_a_rows.csv")
    ap.add_argument("--out", default="figures/v8")
    args = ap.parse_args()

    rows_path = Path(args.rows_csv)
    if not rows_path.exists():
        print(f"ERROR: {rows_path} not found", file=sys.stderr)
        sys.exit(1)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = _load(rows_path)

    fig_rq2_structural(rows, out)
    fig_rq1_claim_only(rows, out)
    fig_rq3_locus(rows, out)
    fig_benign_far(rows, out)
    write_summary_csv(rows, out)
    print(f"WROTE figures + summary.csv to {out}/")


if __name__ == "__main__":
    main()
