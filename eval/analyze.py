"""Phase 4 analysis: compute thesis metrics from monitor_pass JSONL results.

Reads results/monitor/*.jsonl produced by eval/monitor_pass.py, computes:
  FAR / RDR / FalseAlarmRate / ΔRDR per model, per locus, per domain
  π_ℓ  — locus distribution over failed tasks
  McNemar test (V_answer vs V_structural) per model, with continuity correction
  95% CIs for RDR, FalseAlarmRate, ΔRDR — task-level bootstrap (B=1000) when the rate is
    interior, Clopper-Pearson exact when it pins to the 0/1 boundary (degenerate bootstrap)
  CDR_κ at κ ∈ {5, 7, 9} for K=10 repeats (consistent detection rate)
  Per-repeat RDR (for box chart + within-model std)

Saves:
  results/metrics/<model_slug>.json  — per-model JSON summaries
  results/figures/figure6_*.png      — Figure 6: V_answer detection by locus (RQ1)
  results/figures/figure7_*.png      — Figure 7: cross-model RDR box chart (RQ2)
  results/figures/figure8_*.png      — Figure 8: detected/undetected stacked bar (RQ3)

Usage:
  .venv/bin/python -m eval.analyze
  .venv/bin/python -m eval.analyze --monitor-dir results/monitor --out-dir results/metrics
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCI = ("answer-local", "trace-local", "state-local", "intent-local")
CONFIGS = ("v_answer", "v_structural")
# Canonical model order for tables and figures (matches Table 7 / Table D in the thesis:
# 2 flagship then 2 low-end). Figures iterate all_metrics in this order so their x-axes line
# up with the tables; models not listed fall back to alphabetical after the known ones.
MODEL_ORDER = (
    "deepseek/deepseek-v4-pro",
    "xiaomi/mimo-v2.5-pro",
    "z-ai/glm-4.7-flash",
    "qwen/qwen3.6-flash",
)
K_DEFAULT = 10
CDR_KAPPAS = (5, 7, 9)
BOOTSTRAP_B = 1000
BOOTSTRAP_SEED = 42


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------

def _is_pass(verdict: str | None) -> bool:
    """True if the monitor passed this trajectory (PASS_VERIFIED or PASS_UNCHECKED)."""
    return verdict in {"PASS_VERIFIED", "PASS_UNCHECKED"}


def _is_fail_task(row: dict) -> bool:
    return (row.get("gold_reward") or 0.0) == 0.0


def _is_pass_task(row: dict) -> bool:
    return (row.get("gold_reward") or 0.0) == 1.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_rows(monitor_dir: Path) -> list[dict[str, Any]]:
    """Load all status='done' rows from all per-model JSONL shards."""
    rows: list[dict] = []
    for path in sorted(monitor_dir.glob("*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("status") == "done":
                    rows.append(row)
    print(f"Loaded {len(rows):,} rows from {monitor_dir}")
    return rows


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

def _bootstrap_mean_ci(
    values: list[float],
    b: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """95% bootstrap CI for the mean of a list of 0/1 flags or floats."""
    if not values:
        return (float("nan"), float("nan"))
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(b))
    alpha = (1.0 - confidence) / 2.0
    lo = means[max(0, int(alpha * b))]
    hi = means[min(b - 1, int((1.0 - alpha) * b) - 1)]
    return (lo, hi)


def _bootstrap_precision_ci(
    failed_rows: list[dict],
    passed_rows: list[dict],
    vkey: str,
    b: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """95% bootstrap CI for precision = TP / (TP + FP). Resamples the failed (positive) and passed
    (negative) pools independently, since precision mixes detections from both classes."""
    if not failed_rows and not passed_rows:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    nf, nps = len(failed_rows), len(passed_rows)
    precs = []
    for _ in range(b):
        tp = sum(1 for r in (rng.choices(failed_rows, k=nf) if nf else []) if not _is_pass(r.get(vkey)))
        fp = sum(1 for r in (rng.choices(passed_rows, k=nps) if nps else []) if not _is_pass(r.get(vkey)))
        precs.append(tp / (tp + fp) if (tp + fp) else 0.0)
    precs.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = precs[max(0, int(alpha * b))]
    hi = precs[min(b - 1, int((1.0 - alpha) * b) - 1)]
    return (lo, hi)


def _bootstrap_delta_rdr_ci(
    failed_rows: list[dict],
    b: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Bootstrap CI for ΔRDR = RDR(V_structural) − RDR(V_answer).

    Resamples paired rows so the correlation between configs is preserved.
    """
    if not failed_rows:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(failed_rows)
    deltas = []
    for _ in range(b):
        sample = rng.choices(failed_rows, k=n)
        rdr_ans = sum(1 for r in sample if not _is_pass(r.get("v_answer_verdict"))) / n
        rdr_str = sum(1 for r in sample if not _is_pass(r.get("v_structural_verdict"))) / n
        deltas.append(rdr_str - rdr_ans)
    deltas.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = deltas[max(0, int(alpha * b))]
    hi = deltas[min(b - 1, int((1.0 - alpha) * b) - 1)]
    return (lo, hi)


# ---------------------------------------------------------------------------
# Rate CI: bootstrap when interior, Clopper-Pearson exact at the 0/1 boundary
# ---------------------------------------------------------------------------

def _clopper_pearson_boundary_ci(
    k: int, n: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Clopper-Pearson exact binomial CI for a boundary count (k == 0 or k == n).

    At the boundary the closed form needs no incomplete-beta inverse (so no scipy):
      0/n  → [0, 1 - (alpha/2)^(1/n)]
      n/n  → [(alpha/2)^(1/n), 1]
    Used where the task-level bootstrap degenerates to a zero-width interval (every
    resample returns the same boundary value). See formal_definitions.md §2.8.
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    half_alpha = (1.0 - confidence) / 2.0
    if k <= 0:
        return (0.0, 1.0 - half_alpha ** (1.0 / n))
    if k >= n:
        return (half_alpha ** (1.0 / n), 1.0)
    # Interior count — not a boundary case; caller should route to the bootstrap.
    return (k / n, k / n)


def _rate_ci(flags: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """95% CI for a rate = mean of 0/1 flags.

    Interior rates use the task-level bootstrap (`_bootstrap_mean_ci`); rates pinned to the
    0/1 boundary use the Clopper-Pearson exact interval, because the bootstrap is degenerate
    there (e.g. V_answer RDR ≈ 0 on trace/state loci). Convention: formal_definitions.md §2.8.
    """
    if not flags:
        return (float("nan"), float("nan"))
    n = len(flags)
    k = int(round(sum(flags)))
    rate = k / n
    if 0.0 < rate < 1.0:
        return _bootstrap_mean_ci(flags, confidence=confidence)
    return _clopper_pearson_boundary_ci(k, n, confidence=confidence)


# ---------------------------------------------------------------------------
# McNemar test (no scipy; exact for df=1 via math.erfc)
# ---------------------------------------------------------------------------

def mcnemar_test(n01: int, n10: int) -> tuple[float, float]:
    """McNemar chi-squared test with continuity correction.

    n01: V_answer=PASS, V_structural=non-PASS  (structural gains a detection)
    n10: V_answer=non-PASS, V_structural=PASS  (structural loses a detection)
    Returns (chi2, p_value). p = erfc(sqrt(chi2/2)) for df=1 without scipy.
    """
    denom = n01 + n10
    if denom == 0:
        return (0.0, 1.0)
    chi2 = (abs(n01 - n10) - 1.0) ** 2 / denom
    chi2 = max(0.0, chi2)
    p = math.erfc(math.sqrt(chi2 / 2.0))
    return (chi2, p)


# ---------------------------------------------------------------------------
# Per-locus detection stats
# ---------------------------------------------------------------------------

def _locus_detection(rows: list[dict], verdict_key: str) -> dict[str, dict]:
    """Per-locus detection rate + bootstrap CI for one config over failed rows."""
    by_locus: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_locus[r.get("locus") or "unknown"].append(r)
    result: dict[str, dict] = {}
    for locus in LOCI:
        lf = by_locus.get(locus, [])
        if lf:
            flags = [0.0 if _is_pass(r.get(verdict_key)) else 1.0 for r in lf]
            rate = sum(flags) / len(flags)
            ci = _rate_ci(flags)
            detected = int(sum(flags))
        else:
            rate, ci, detected = 0.0, (float("nan"), float("nan")), 0
        result[locus] = {"n": len(lf), "detected": detected, "rate": rate, "ci_lo": ci[0], "ci_hi": ci[1]}
    return result


# ---------------------------------------------------------------------------
# CDR_κ (consistent detection rate across K repeats)
# ---------------------------------------------------------------------------

def _cdr(failed_rows: list[dict], verdict_key: str, k: int) -> dict[int, float]:
    """CDR_κ at κ ∈ CDR_KAPPAS: fraction of unique tasks detected in ≥ κ of K repeats."""
    task_groups: dict[tuple, list] = defaultdict(list)
    for r in failed_rows:
        task_groups[(r.get("task_id"), r.get("domain"))].append(r)
    cdr: dict[int, float] = {}
    for kappa in CDR_KAPPAS:
        threshold = kappa / k
        consistent = sum(
            1 for grp in task_groups.values()
            if sum(1 for r in grp if not _is_pass(r.get(verdict_key))) / len(grp) >= threshold
        )
        cdr[kappa] = consistent / len(task_groups) if task_groups else 0.0
    return cdr


# ---------------------------------------------------------------------------
# Per-repeat RDR (for box chart + noise estimate)
# ---------------------------------------------------------------------------

def _per_repeat_rdr(failed_rows: list[dict], verdict_key: str, k: int) -> list[float]:
    """RDR for each of the K repeats (index 0 … K-1). Missing repeats → nan."""
    by_repeat: dict[int, list] = defaultdict(list)
    for r in failed_rows:
        by_repeat[r.get("repeat", 0)].append(r)
    rdrs = []
    for rep in range(k):
        grp = by_repeat.get(rep, [])
        if grp:
            rdrs.append(sum(1 for r in grp if not _is_pass(r.get(verdict_key))) / len(grp))
        else:
            rdrs.append(float("nan"))
    return rdrs


# ---------------------------------------------------------------------------
# Core: per-model metrics
# ---------------------------------------------------------------------------

def _is_audit_failed(row: dict) -> bool:
    """True if both monitor configs produced AUDIT_FAILED (extractor returned no claims)."""
    return (
        row.get("v_answer_verdict") == "AUDIT_FAILED"
        and row.get("v_structural_verdict") == "AUDIT_FAILED"
    )


def compute_model_metrics(rows: list[dict], model: str, k: int = K_DEFAULT) -> dict[str, Any]:
    # Exclude rows where the extractor produced no output for both configs; these cannot
    # contribute to RDR or FAR and would otherwise inflate both by counting as detections.
    n_audit_failed = sum(1 for r in rows if _is_audit_failed(r))
    rows = [r for r in rows if not _is_audit_failed(r)]

    failed = [r for r in rows if _is_fail_task(r)]
    passed = [r for r in rows if _is_pass_task(r)]
    n_fail, n_pass, n_total = len(failed), len(passed), len(rows)

    # π_ℓ
    locus_counts: dict[str, int] = defaultdict(int)
    for r in failed:
        locus_counts[r.get("locus") or "unknown"] += 1
    pi_l = {
        l: round(locus_counts.get(l, 0) / n_fail, 4) if n_fail else 0.0
        for l in LOCI
    }

    metrics: dict[str, Any] = {
        "model": model,
        "n_total": n_total,
        "n_fail": n_fail,
        "n_pass": n_pass,
        "n_audit_failed": n_audit_failed,
        "pi_l": pi_l,
        "locus_counts": {l: locus_counts.get(l, 0) for l in LOCI},
    }

    for cfg in CONFIGS:
        vkey = f"{cfg}_verdict"

        # FAR / RDR
        detect_flags = [0.0 if _is_pass(r.get(vkey)) else 1.0 for r in failed]
        rdr = sum(detect_flags) / n_fail if n_fail else 0.0
        far = 1.0 - rdr
        rdr_ci = _rate_ci(detect_flags)

        # FalseAlarmRate (on reward-1 tasks)
        fa_flags = [0.0 if _is_pass(r.get(vkey)) else 1.0 for r in passed]
        false_alarm_rate = sum(fa_flags) / n_pass if n_pass else 0.0
        far_ci = _rate_ci(fa_flags)

        # Detector view: treat reward=0 as the positive class and a non-PASS verdict as a detection.
        # Precision / F1 / MCC make the recall-vs-false-alarm trade legible in a single number and
        # are robust to the differing failure base rates across the four models (MCC especially).
        tp = int(sum(detect_flags))
        fn = n_fail - tp
        fp = int(sum(fa_flags))
        tn = n_pass - fp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = rdr
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        mcc_denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = ((tp * tn - fp * fn) / mcc_denom) if mcc_denom > 0 else 0.0
        prec_ci = _bootstrap_precision_ci(failed, passed, vkey)

        # Per-locus detection
        locus_det = _locus_detection(failed, vkey)

        # CDR_κ
        cdr = _cdr(failed, vkey, k)

        # Per-repeat RDR (for box chart + std)
        repeat_rdrs = _per_repeat_rdr(failed, vkey, k)
        valid = [x for x in repeat_rdrs if not math.isnan(x)]
        if len(valid) > 1:
            mean_rep = sum(valid) / len(valid)
            std_rep = math.sqrt(sum((x - mean_rep) ** 2 for x in valid) / len(valid))
        elif len(valid) == 1:
            std_rep = 0.0
        else:
            std_rep = float("nan")

        metrics[cfg] = {
            "rdr": round(rdr, 4),
            "far": round(far, 4),
            "rdr_ci_lo": round(rdr_ci[0], 4),
            "rdr_ci_hi": round(rdr_ci[1], 4),
            "false_alarm_rate": round(false_alarm_rate, 4),
            "false_alarm_rate_ci_lo": round(far_ci[0], 4),
            "false_alarm_rate_ci_hi": round(far_ci[1], 4),
            "precision": round(precision, 4),
            "precision_ci_lo": round(prec_ci[0], 4),
            "precision_ci_hi": round(prec_ci[1], 4),
            "f1": round(f1, 4),
            "mcc": round(mcc, 4),
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "locus_detection": locus_det,
            "cdr": {str(kappa): round(v, 4) for kappa, v in cdr.items()},
            "per_repeat_rdr": [round(x, 4) if not math.isnan(x) else None for x in repeat_rdrs],
            "rdr_std_across_repeats": round(std_rep, 4) if not math.isnan(std_rep) else None,
        }

    # ΔRDR
    rdr_ans = metrics["v_answer"]["rdr"]
    rdr_str = metrics["v_structural"]["rdr"]
    delta_rdr = rdr_str - rdr_ans
    delta_ci = _bootstrap_delta_rdr_ci(failed)
    metrics["delta_rdr"] = round(delta_rdr, 4)
    metrics["delta_rdr_ci_lo"] = round(delta_ci[0], 4)
    metrics["delta_rdr_ci_hi"] = round(delta_ci[1], 4)

    # McNemar
    n01 = sum(
        1 for r in failed
        if _is_pass(r.get("v_answer_verdict")) and not _is_pass(r.get("v_structural_verdict"))
    )
    n10 = sum(
        1 for r in failed
        if not _is_pass(r.get("v_answer_verdict")) and _is_pass(r.get("v_structural_verdict"))
    )
    chi2, p_val = mcnemar_test(n01, n10)
    metrics["mcnemar"] = {
        "n01": n01,
        "n10": n10,
        "chi2": round(chi2, 4),
        "p_value": round(p_val, 6),
        "significant_p05": p_val < 0.05,
    }

    # Monitor-vs-oracle gap (RQ3): theoretical ceiling − achieved RDR(V_structural)
    ceiling = 1.0 - pi_l.get("intent-local", 0.0)
    metrics["theoretical_ceiling"] = round(ceiling, 4)
    metrics["monitor_oracle_gap"] = round(ceiling - rdr_str, 4)

    return metrics


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

def print_report(all_metrics: list[dict]) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print("RELIABLEGUARD — PHASE 4 METRICS REPORT")
    print(sep)

    for m in all_metrics:
        print(f"\n{'─' * 60}")
        print(f"  Model : {m['model']}")
        print(f"  N     : total={m['n_total']:,}  fail={m['n_fail']:,}  pass={m['n_pass']:,}")

        print("\n  Locus distribution π_ℓ (over reward-0 tasks):")
        for locus in LOCI:
            n = m["locus_counts"].get(locus, 0)
            pct = m["pi_l"].get(locus, 0.0) * 100
            print(f"    {locus:<22}  n={n:5d}  π={pct:5.1f}%")

        for cfg in CONFIGS:
            c = m[cfg]
            print(f"\n  {cfg.upper()}:")
            print(f"    RDR  = {c['rdr']:.4f}  95%CI=[{c['rdr_ci_lo']:.4f}, {c['rdr_ci_hi']:.4f}]")
            print(f"    FAR  = {c['far']:.4f}")
            print(f"    FalseAlarmRate = {c['false_alarm_rate']:.4f}  "
                  f"CI=[{c['false_alarm_rate_ci_lo']:.4f}, {c['false_alarm_rate_ci_hi']:.4f}]")
            print(f"    Precision = {c['precision']:.4f}  "
                  f"CI=[{c['precision_ci_lo']:.4f}, {c['precision_ci_hi']:.4f}]  "
                  f"F1 = {c['f1']:.4f}  MCC = {c['mcc']:.4f}")
            cdr = c["cdr"]
            print(f"    CDR_5={cdr.get('5', 0):.4f}  CDR_7={cdr.get('7', 0):.4f}  "
                  f"CDR_9={cdr.get('9', 0):.4f}")
            print(f"    RDR std across {K_DEFAULT} repeats = {c['rdr_std_across_repeats']}")
            print(f"    Per-locus detection:")
            for locus in LOCI:
                ld = c["locus_detection"].get(locus, {})
                if ld.get("n", 0) > 0:
                    print(f"      {locus:<22}  n={ld['n']:5d}  det={ld['detected']:5d}  "
                          f"rate={ld['rate']:.4f}  CI=[{ld['ci_lo']:.4f}, {ld['ci_hi']:.4f}]")

        mn = m["mcnemar"]
        sig = "***" if mn["significant_p05"] else "ns"
        print(f"\n  ΔRDR = {m['delta_rdr']:.4f}  "
              f"95%CI=[{m['delta_rdr_ci_lo']:.4f}, {m['delta_rdr_ci_hi']:.4f}]")
        print(f"  McNemar: n01={mn['n01']}  n10={mn['n10']}  "
              f"χ²={mn['chi2']:.4f}  p={mn['p_value']:.6f}  {sig}")
        print(f"  Theoretical ceiling (1 − π_intent-local) = {m['theoretical_ceiling']:.4f}")
        print(f"  Monitor-vs-oracle gap = {m['monitor_oracle_gap']:.4f}")

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def make_figures(all_metrics: list[dict], figures_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figures_dir.mkdir(parents=True, exist_ok=True)
    short_names = [m["model"].split("/")[-1] for m in all_metrics]
    n_models = len(all_metrics)
    loci_plot = ["answer-local", "trace-local", "state-local", "intent-local"]
    model_colors = ["#2166ac", "#4dac26", "#d73027", "#f4a582"]

    # -------------------------------------------------------------------
    # Figure 6 — V_answer detection rate by locus (RQ1)
    # -------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(loci_plot))
    bar_w = 0.72 / max(n_models, 1)
    for i, m in enumerate(all_metrics):
        ld = m["v_answer"]["locus_detection"]
        rates = [ld.get(l, {}).get("rate", 0.0) for l in loci_plot]
        ci_lo = [ld.get(l, {}).get("ci_lo", 0.0) for l in loci_plot]
        ci_hi = [ld.get(l, {}).get("ci_hi", 0.0) for l in loci_plot]
        yerr_lo = [max(0.0, r - lo) for r, lo in zip(rates, ci_lo)]
        yerr_hi = [max(0.0, hi - r) for r, hi in zip(rates, ci_hi)]
        offset = (i - n_models / 2 + 0.5) * bar_w
        ax.bar(x + offset, rates, bar_w, label=short_names[i], color=model_colors[i],
               alpha=0.85, yerr=[yerr_lo, yerr_hi], capsize=3,
               error_kw={"linewidth": 1, "ecolor": "black"})

    # Dashed ceiling line per locus based on π_ℓ averages
    for li, locus in enumerate(loci_plot):
        avg_pi = sum(m["pi_l"].get(locus, 0.0) for m in all_metrics) / n_models
        ax.plot([li - 0.4, li + 0.4], [avg_pi, avg_pi], "k--", linewidth=1.0,
                label="π_ℓ ceiling" if li == 0 else None)

    ax.set_xticks(x)
    ax.set_xticklabels(loci_plot, fontsize=12)
    ax.set_ylabel("Detection rate", fontsize=12)
    ax.set_ylim(0, 1.08)
    ax.set_title("Figure 6 — $V_{\\mathrm{answer}}$ Detection Rate by Locus (RQ1)", fontsize=13)
    ax.legend(fontsize=9, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = figures_dir / "figure6_rq1_locus_detection.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Figure 6 → {out}")

    # -------------------------------------------------------------------
    # Figure 7 — Cross-model RDR box chart (RQ2)
    # Two panels: left = RDR(V_answer) vs RDR(V_structural) per model (box over K repeats)
    #             right = ΔRDR per model (bar + CI)
    # -------------------------------------------------------------------
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(12, 5))
    x7 = np.arange(n_models)

    # Left: box plots from per-repeat RDR values
    ans_boxes, str_boxes = [], []
    for m in all_metrics:
        ans_rep = [v for v in (m["v_answer"]["per_repeat_rdr"] or []) if v is not None]
        str_rep = [v for v in (m["v_structural"]["per_repeat_rdr"] or []) if v is not None]
        ans_boxes.append(ans_rep if ans_rep else [m["v_answer"]["rdr"]])
        str_boxes.append(str_rep if str_rep else [m["v_structural"]["rdr"]])

    positions_ans = x7 - 0.2
    positions_str = x7 + 0.2
    bp_ans = ax_l.boxplot(ans_boxes, positions=positions_ans, widths=0.3,
                          patch_artist=True, medianprops={"color": "white", "linewidth": 2})
    bp_str = ax_l.boxplot(str_boxes, positions=positions_str, widths=0.3,
                          patch_artist=True, medianprops={"color": "white", "linewidth": 2})
    for patch in bp_ans["boxes"]:
        patch.set_facecolor("#74add1")
        patch.set_alpha(0.85)
    for patch in bp_str["boxes"]:
        patch.set_facecolor("#2166ac")
        patch.set_alpha(0.85)

    from matplotlib.patches import Patch
    ax_l.legend(
        handles=[Patch(facecolor="#74add1", label="$V_{answer}$"),
                 Patch(facecolor="#2166ac", label="$V_{structural}$")],
        fontsize=10,
    )
    ax_l.set_xticks(x7)
    ax_l.set_xticklabels(short_names, fontsize=9, rotation=15)
    ax_l.set_ylabel("RDR (over K=10 repeats)", fontsize=11)
    ax_l.set_ylim(0, 1.05)
    ax_l.set_title("RDR by model", fontsize=11)
    ax_l.grid(axis="y", alpha=0.3)

    # Right: ΔRDR bar + CI
    deltas = [m["delta_rdr"] for m in all_metrics]
    dlo = [m["delta_rdr_ci_lo"] for m in all_metrics]
    dhi = [m["delta_rdr_ci_hi"] for m in all_metrics]
    bar_cols = ["#1a9641" if d >= 0 else "#d7191c" for d in deltas]
    ax_r.bar(x7, deltas, color=bar_cols, alpha=0.82, width=0.55,
             yerr=[np.array(deltas) - np.array(dlo), np.array(dhi) - np.array(deltas)],
             capsize=6, error_kw={"linewidth": 1.5, "ecolor": "black"})
    ax_r.axhline(0, color="black", linewidth=0.9)
    ax_r.set_xticks(x7)
    ax_r.set_xticklabels(short_names, fontsize=9, rotation=15)
    ax_r.set_ylabel("ΔRDR", fontsize=11)
    ax_r.set_title("ΔRDR = RDR($V_{structural}$) − RDR($V_{answer}$)", fontsize=11)
    ax_r.grid(axis="y", alpha=0.3)

    fig.suptitle("Figure 7 — Cross-Model RDR Comparison (RQ2)", fontsize=13)
    fig.tight_layout()
    out = figures_dir / "figure7_rq2_cross_model_rdr.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Figure 7 → {out}")

    # -------------------------------------------------------------------
    # Figure 8 — Detected vs. undetected reward-0 tasks by locus (RQ3)
    # One stacked bar per model; red = intent-local (irreducible residual)
    # -------------------------------------------------------------------
    loci_seg_colors = {
        "answer-local": "#2166ac",
        "trace-local":  "#4dac26",
        "state-local":  "#74add1",
        "intent-local": "#d73027",
        "other-undet":  "#aaaaaa",
    }
    loci_det_order = ["answer-local", "trace-local", "state-local"]

    fig, axes = plt.subplots(1, n_models, figsize=(3.5 * n_models, 6), sharey=True)
    if n_models == 1:
        axes = [axes]

    for i, (m, ax8) in enumerate(zip(all_metrics, axes)):
        ld = m["v_structural"]["locus_detection"]
        bottom = 0
        for locus in loci_det_order:
            det = ld.get(locus, {}).get("detected", 0)
            ax8.bar(
                0, det, bottom=bottom, width=0.6,
                color=loci_seg_colors[locus],
                label=f"{locus} (det)" if i == 0 else None,
            )
            bottom += det

        # intent-local: undetected by construction
        n_intent = m["locus_counts"].get("intent-local", 0)
        ax8.bar(
            0, n_intent, bottom=bottom, width=0.6,
            color=loci_seg_colors["intent-local"],
            label="intent-local (undetected)" if i == 0 else None,
        )
        bottom += n_intent

        # any remaining undetected other than intent-local
        total_det = sum(ld.get(l, {}).get("detected", 0) for l in loci_det_order)
        # detected of answer-local that V_structural missed
        other_undet = m["n_fail"] - total_det - n_intent
        if other_undet > 0:
            ax8.bar(
                0, other_undet, bottom=bottom, width=0.6,
                color=loci_seg_colors["other-undet"],
                label="other undetected" if i == 0 else None,
            )

        # Theoretical ceiling dashed line
        ceiling_n = m["n_fail"] * m["theoretical_ceiling"]
        ax8.axhline(ceiling_n, color="black", linestyle="--", linewidth=1.3,
                    label=f"ceiling (1−π_intent)" if i == 0 else None)

        ax8.set_xticks([])
        ax8.set_title(short_names[i], fontsize=10)
        ax8.set_xlim(-0.5, 0.5)

    axes[0].set_ylabel("Count of reward-0 tasks", fontsize=11)
    axes[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.suptitle("Figure 8 — Detected vs. Undetected Reward-0 Tasks by Locus (RQ3)", fontsize=13)
    fig.tight_layout()
    out = figures_dir / "figure8_rq3_locus_stacked.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Figure 8 → {out}")

    # -------------------------------------------------------------------
    # Figure 9 — Detector quality: RDR / Precision / FalseAlarm / MCC (RQ2)
    # V_answer vs V_structural per model. Makes the recall-vs-false-alarm
    # trade legible (RDR alone hides the cost of the extra detections).
    # -------------------------------------------------------------------
    panels = [
        ("rdr", "RDR (recall)", False),
        ("precision", "Precision", False),
        ("false_alarm_rate", "False-alarm rate", True),
        ("mcc", "MCC", False),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6))
    x9 = np.arange(n_models)
    bw = 0.38
    for ax9, (key, title, lower_better) in zip(axes, panels):
        ans = [m["v_answer"][key] for m in all_metrics]
        str_ = [m["v_structural"][key] for m in all_metrics]
        ax9.bar(x9 - bw / 2, ans, bw, label="$V_{answer}$", color="#74add1", alpha=0.9)
        ax9.bar(x9 + bw / 2, str_, bw, label="$V_{structural}$", color="#2166ac", alpha=0.9)
        ax9.set_xticks(x9)
        ax9.set_xticklabels(short_names, fontsize=8, rotation=20)
        ax9.set_title(title + ("  (lower better)" if lower_better else ""), fontsize=11)
        ax9.grid(axis="y", alpha=0.3)
        top = max(ans + str_ + [0.01])
        ax9.set_ylim(0, max(0.3, top * 1.2) if key == "mcc" else 1.05 if key != "mcc" else top * 1.2)
    axes[0].legend(fontsize=9)
    fig.suptitle("Figure 9 — Detector Quality: $V_{answer}$ vs $V_{structural}$ (RQ2)", fontsize=13)
    fig.tight_layout()
    out = figures_dir / "figure9_rq2_detector_quality.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Figure 9 → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4: compute thesis metrics from monitor_pass JSONL results"
    )
    parser.add_argument("--monitor-dir", default="results/monitor",
                        help="Phase 3 monitor_pass output directory (default: results/monitor)")
    parser.add_argument("--out-dir", default="results/metrics",
                        help="output directory for per-model JSON summaries (default: results/metrics)")
    parser.add_argument("--figures-dir", default="results/figures",
                        help="output directory for PNG figures (default: results/figures)")
    parser.add_argument("--k", type=int, default=K_DEFAULT,
                        help="K repeats per (model, domain, task) (default: 10)")
    args = parser.parse_args()

    monitor_dir = Path(args.monitor_dir)
    out_dir = Path(args.out_dir)
    figures_dir = Path(args.figures_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(monitor_dir)
    if not rows:
        print(f"No rows found in {monitor_dir}. Check --monitor-dir.")
        return

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    def _model_rank(model: str) -> tuple[int, str]:
        try:
            return (MODEL_ORDER.index(model), "")
        except ValueError:
            return (len(MODEL_ORDER), model)

    all_metrics = []
    for model, model_rows in sorted(by_model.items(), key=lambda kv: _model_rank(kv[0])):
        print(f"\nComputing: {model} ({len(model_rows):,} rows)...")
        m = compute_model_metrics(model_rows, model, k=args.k)
        all_metrics.append(m)
        slug = model.replace("/", "_")
        out_path = out_dir / f"{slug}.json"
        with out_path.open("w") as fh:
            json.dump(m, fh, indent=2)
        print(f"  Saved JSON → {out_path}")

    print_report(all_metrics)

    print("Generating figures...")
    make_figures(all_metrics, figures_dir)
    print(f"\nDone.  Metrics → {out_dir}  |  Figures → {figures_dir}")


if __name__ == "__main__":
    main()
