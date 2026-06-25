"""Recompute thesis metrics after re-scoring provable reward-false-negatives (A1) as PASS.

Reuses eval.analyze.compute_model_metrics verbatim (so the baseline == results/metrics_v2) and only
flips gold_reward 0->1 for the A1 trajectories the deterministic overlay (eval.overlay_reward_fn)
identifies. Prints a before/after comparison per model.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/beike/Desktop/PolyU/semester_2/5902/code/reliable_guard")
sys.path.insert(0, str(ROOT))

from eval.analyze import compute_model_metrics, LOCI, CONFIGS  # noqa: E402
from eval.overlay_reward_fn import (  # noqa: E402
    classify, load_tasks, MODEL_FILES, CAP,
)
from eval.build_monitor_v11 import rescore_keys_by_stem  # noqa: E402  (the canonical V11 re-score set)

MON_V2 = ROOT / "results" / "monitor_v2"


def overlay_classes():
    """key (stem, domain, task_id, repeat) -> overlay class, for reward<1 trajectories."""
    tasks = load_tasks()
    out = {}
    for stem in MODEL_FILES:
        for line in (CAP / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            gr = r.get("gold_reward")
            if gr is None or gr >= 1.0:
                continue
            dom, tid, rep = r["domain"], str(r["task_id"]), int(r["repeat"])
            task = tasks.get((dom, tid))
            if task is None:
                continue
            trace = r["tool_trace"]
            if isinstance(trace, str):
                trace = json.loads(trace)
            out[(stem, dom, tid, rep)] = classify(task, trace, r.get("answer_text", ""))
    return out


def load_monitor():
    by_model = defaultdict(list)
    for stem in MODEL_FILES:
        for line in (MON_V2 / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("status") == "done":
                by_model[stem].append(r)
    return by_model


def key_of(stem, r):
    return (stem, r["domain"], str(r["task_id"]), int(r["repeat"]))


def main():
    cls_map = overlay_classes()
    a1_keys = {k for k, v in cls_map.items() if v == "A1"}
    a2_keys = {k for k, v in cls_map.items() if v == "A2"}
    by_model = load_monitor()

    # intent-local A1 = provable reward-fn the monitor flagged NOTHING on (pure termination artifact);
    # re-scoring these is the clean correction (all FN->TN, no false alarm added).
    locus_of = {}
    for stem in MODEL_FILES:
        for r in by_model[stem]:
            locus_of[key_of(stem, r)] = r.get("locus")
    a1_intent_keys = {k for k in a1_keys if locus_of.get(k) == "intent-local"}

    # V11 canonical correction = intent-local provable reward-fn (A1 + A2 with numeric NL facts met),
    # exactly the set re-scored by eval/build_monitor_v11.py.
    _rk = rescore_keys_by_stem()
    v11_keys = {
        (stem, dom, tid, rep)
        for stem in MODEL_FILES
        for (dom, tid, rep) in _rk[stem]
        if locus_of.get((stem, dom, tid, rep)) == "intent-local"
    }

    # --- diagnostics: among A1 monitor rows, locus + V_structural verdict split ---
    print("A1 diagnostics (how re-scoring moves the confusion matrix):")
    from eval.analyze import _is_pass, _is_audit_failed
    tot_fn2tn = tot_tp2fp = 0
    for stem in MODEL_FILES:
        loc = Counter(); flagged = 0; n = 0
        for r in by_model[stem]:
            if key_of(stem, r) in a1_keys and not _is_audit_failed(r):
                n += 1
                loc[r.get("locus")] += 1
                if not _is_pass(r.get("v_structural_verdict")):
                    flagged += 1  # was TP -> becomes FP
        fn2tn = n - flagged
        tot_tp2fp += flagged; tot_fn2tn += fn2tn
        print(f"  {stem.split('_',1)[-1]:16} A1={n:4}  loci={dict(loc)}  "
              f"Vs-flagged(TP->FP)={flagged}  not-flagged(FN->TN)={fn2tn}")
    print(f"  ALL: FN->TN={tot_fn2tn}  TP->FP={tot_tp2fp}\n")

    # --- baseline vs corrected metrics ---
    def variant(rescore_keys):
        res = {}
        for stem in MODEL_FILES:
            model = by_model[stem][0]["model"]
            rows = by_model[stem]
            if rescore_keys:
                rows = [
                    ({**r, "gold_reward": 1.0} if key_of(stem, r) in rescore_keys else r)
                    for r in rows
                ]
            res[stem] = compute_model_metrics(rows, model)
        return res

    base = variant(None)
    corr = variant(v11_keys)           # PRIMARY = V11: intent-local A1 + A2-numeric (build_monitor_v11)
    corr_all = variant(a1_keys)        # alt: re-score ALL A1 (non-intent A1 -> false alarms)
    ceil = variant(a1_keys | a2_keys)  # bracket: re-score A1+A2 all (upper bound; qualitative A2 is mixed)
    print(f"re-scored (PRIMARY=V11) = intent-local A1+A2-numeric = {len(v11_keys)} keys; "
          f"intent A1 only = {len(a1_intent_keys)}; all A1 = {len(a1_keys)}; A1+A2 = {len(a1_keys | a2_keys)}\n")

    short = [s.split("_", 1)[-1] for s in MODEL_FILES]

    def row(stem, m, cfg):
        c = m[cfg]
        return (c["rdr"], c["false_alarm_rate"], c["precision"], c["f1"], c["mcc"])

    print("=" * 108)
    print("BEFORE (V10 baseline)  vs  AFTER (re-score provable reward-fn A1 as PASS)")
    print("=" * 108)
    print(f"{'model':15}{'n_fail':>14}{'pi_intent':>12}{'config':>14}"
          f"{'RDR':>16}{'FalseAlarm':>12}{'MCC':>14}")
    for stem, sh in zip(MODEL_FILES, short):
        b, c = base[stem], corr[stem]
        nf = f"{b['n_fail']}->{c['n_fail']}"
        pii = f"{b['pi_l']['intent-local']:.3f}->{c['pi_l']['intent-local']:.3f}"
        for cfg in CONFIGS:
            br = row(stem, b, cfg); cr = row(stem, c, cfg)
            rdr = f"{br[0]:.3f}->{cr[0]:.3f}"
            fa = f"{br[1]:.3f}->{cr[1]:.3f}"
            mcc = f"{br[4]:.3f}->{cr[4]:.3f}"
            print(f"{sh if cfg==CONFIGS[0] else '':15}{nf if cfg==CONFIGS[0] else '':>14}"
                  f"{pii if cfg==CONFIGS[0] else '':>12}{cfg:>14}{rdr:>16}{fa:>12}{mcc:>14}")
    print()

    # ΔRDR + ceiling/gap before/after
    print("RQ2/RQ3 headline shifts:")
    print(f"{'model':15}{'ΔRDR(base->corr)':>22}{'ceiling 1-pi_int':>22}{'gap base->corr':>18}")
    for stem, sh in zip(MODEL_FILES, short):
        b, c = base[stem], corr[stem]
        d = f"{b['delta_rdr']:+.3f}->{c['delta_rdr']:+.3f}"
        ceil_s = f"{b['theoretical_ceiling']:.3f}->{c['theoretical_ceiling']:.3f}"
        gap = f"{b['monitor_oracle_gap']:.3f}->{c['monitor_oracle_gap']:.3f}"
        print(f"{sh:15}{d:>22}{ceil_s:>22}{gap:>18}")
    print()

    # full v_structural RDR for base/corr/all/ceiling
    print("V_structural RDR: base -> V11(PRIMARY: A1+A2-numeric) -> allA1 -> A1+A2-all ceiling:")
    for stem, sh in zip(MODEL_FILES, short):
        print(f"  {sh:16} {base[stem]['v_structural']['rdr']:.3f} -> "
              f"{corr[stem]['v_structural']['rdr']:.3f} -> "
              f"{corr_all[stem]['v_structural']['rdr']:.3f} -> {ceil[stem]['v_structural']['rdr']:.3f}")

    # dump corrected metrics json for reuse
    outdir = ROOT / "results" / "metrics_v2_rewardfn_corrected"
    outdir.mkdir(exist_ok=True)
    for stem in MODEL_FILES:
        (outdir / f"{stem}.json").write_text(json.dumps(corr[stem], indent=2))
    print(f"\nwrote corrected metrics -> {outdir}")

    # sanity: baseline must match results/metrics_v2
    print("\nsanity (baseline vs results/metrics_v2 v_structural rdr):")
    for stem in MODEL_FILES:
        m2 = json.load(open(ROOT / "results" / "metrics_v2" / f"{stem}.json"))
        ok = abs(m2["v_structural"]["rdr"] - base[stem]["v_structural"]["rdr"]) < 1e-9
        print(f"  {stem.split('_',1)[-1]:16} metrics_v2={m2['v_structural']['rdr']:.4f} "
              f"recomputed={base[stem]['v_structural']['rdr']:.4f}  {'OK' if ok else 'MISMATCH'}")


if __name__ == "__main__":
    main()
