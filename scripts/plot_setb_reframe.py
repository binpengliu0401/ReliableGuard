#!/usr/bin/env python3
"""
Set B benign false-alarm reframe figure: the "43%" decomposed.

Reuses the independent re-derivation in recheck_setb_benign (requested order count vs. raw
db_state_after) to split the flagged benign ecommerce tasks into (a) the monitor correctly
catching agent under-execution and (b) the true false alarm. Writes a single stacked bar plus
the naive-vs-true rates -> figures/set_b_3seed/fig_setb_benign_reframe.{png,pdf}
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.recheck_setb_benign import requested_order_count, collapse  # noqa: E402

ROWS = REPO / "results/set_b_3seed/set_b_rows.csv"
CORPUS = REPO / "results/corpus/set_b_corpus.jsonl"
OUT = REPO / "figures/set_b_3seed"
VERSION = "V3_Intervention"
FLAGGED = {"WARN", "BLOCK", "AUDIT_FAILED"}


def main() -> None:
    corpus = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            corpus[(d["scenario_id"], str(d.get("seed")))] = d

    ac_f = ac_p = af_f = af_p = 0
    for r in csv.DictReader(ROWS.open()):
        if r["version"] != VERSION or r["domain"] != "ecommerce":
            continue
        if r["expected_outcome"] != "PASS" or r["actual_outcome"] == "ERROR":
            continue
        rec = corpus.get((r["scenario_id"], r["seed"]))
        if not rec:
            continue
        requested = requested_order_count(rec["task"].get("input") or "")
        agent_correct = len(rec.get("db_state_after") or []) >= requested
        flagged = collapse(r["actual_outcome"]) in FLAGGED
        if agent_correct and flagged:
            ac_f += 1
        elif agent_correct:
            ac_p += 1
        elif flagged:
            af_f += 1
        else:
            af_p += 1

    ac = ac_f + ac_p
    total = ac + af_f + af_p
    flagged_total = ac_f + af_f
    naive = flagged_total / total * 100
    true = ac_f / ac * 100

    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    fig.subplots_adjust(top=0.74, bottom=0.40, left=0.06, right=0.97)
    ax.barh(0, af_f, color="#2e7d32",
            label=f"Monitor correctly caught agent under-execution ({af_f})")
    ax.barh(0, ac_f, left=af_f, color="#c62828",
            label=f"True false alarm — agent executed correctly ({ac_f})")
    # in-bar count labels
    ax.text(af_f / 2, 0, str(af_f), ha="center", va="center", color="white", fontsize=11, weight="bold")
    ax.text(af_f + ac_f / 2, 0, str(ac_f), ha="center", va="center", color="white", fontsize=11, weight="bold")
    ax.set_xlim(0, flagged_total)
    ax.set_yticks([])
    ax.set_xlabel("Flagged benign ecommerce tasks (expected PASS)", fontsize=9)
    fig.suptitle("Set B: the “43% benign false-alarm” decomposed", fontsize=12, y=0.97)
    ax.set_title(
        f"Naive false-alarm vs expected-PASS: {flagged_total}/{total} = {naive:.0f}%      "
        f"→      True (agent-correct tasks only): {ac_f}/{ac} = {true:.0f}%",
        fontsize=9.5, color="#333", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.45), ncol=1, frameon=False, fontsize=9)

    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_setb_benign_reframe.{ext}", dpi=150, bbox_inches="tight")
    print(f"[OK] counts: correct-catch={af_f}, true-FP={ac_f}, total flagged={flagged_total}, "
          f"naive={naive:.0f}% true={true:.0f}%")
    print(f"[OK] wrote {OUT}/fig_setb_benign_reframe.(png|pdf)")


if __name__ == "__main__":
    main()
