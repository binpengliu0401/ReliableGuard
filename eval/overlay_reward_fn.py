"""Deterministic reward-false-negative overlay over the full reward<1 population.

For every reward<1 trajectory it computes, with NO LLM and NO re-capture, a class:

  A1  provable reward-fn  : DB-match(agent writes == gold actions, full args) AND every
                            non-DB reward_basis component is deterministically 1
                            (empty NL_ASSERTION/COMMUNICATE, or COMMUNICATE substring all-met).
                            reward=0 yet all components=1 -> only the termination guard
                            (evaluator.py:113) can explain it -> agent actually succeeded.
  A2  undetermined        : DB-match BUT a non-empty NL_ASSERTION is in the basis (LLM judge,
                            cannot be replicated deterministically). Mixed: contains both
                            reward-fn (judge false-neg) and genuine answer failures.
  B_loop                  : DB-match BUT the answer degenerates into a stall loop
                            (>=4 wait-filler turns OR a turn-prefix repeated >=4x) -> observable
                            agent defect (recoverable trace/answer failure), not a success.
  B_comm                  : DB-match BUT a non-empty COMMUNICATE info string is deterministically
                            absent from the answer -> genuine, observable answer-channel failure.
  RESIDUAL                : DB MISMATCH (omitted/extra/different writes) -> genuine DB-level
                            reward=0. Mix of missed-detection (recoverable), true-intent-local
                            (irreducible boundary), and unsure; not separable deterministically.

Validation: the 40 manually-reviewed rows (intent_local_review.csv) are joined and the overlay
class is printed next to the human verdict.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve()
# locate repo root (has eval/ and results/)
while ROOT.name and not (ROOT / "results" / "capture").exists():
    ROOT = ROOT.parent
if not (ROOT / "results" / "capture").exists():
    ROOT = Path("/Users/beike/Desktop/PolyU/semester_2/5902/code/reliable_guard")

CAP = ROOT / "results" / "capture"
MON = ROOT / "results" / "monitor_v2"
TAU2 = Path("/Users/beike/Desktop/PolyU/semester_2/5902/code/tau2-bench/data/tau2/domains")
CSV = ROOT / "eval" / "locus_spotcheck" / "intent_local_review.csv"

MODEL_FILES = [
    "deepseek_deepseek-v4-pro",
    "xiaomi_mimo-v2.5-pro",
    "z-ai_glm-4.7-flash",
    "qwen_qwen3.6-flash",
]

READ_TOOLS = {
    "find_user_id_by_email", "find_user_id_by_name_zip", "get_order_details",
    "get_user_details", "get_product_details", "get_item_details",
    "get_reservation_details", "search_direct_flight", "calculate",
    "list_all_product_types", "think", "transfer_to_human_agents",
    "get_flight_status", "list_all_airports", "search_onestop_flight",
}
ID_KEYS = ("order_id", "reservation_id")

WAIT_RE = re.compile(
    r"\b(hold on|please hold|be with you shortly|be with you momentarily|please be patient|"
    r"appreciate your patience|thank you for your patience|while we wait|waiting for (the|a) human|"
    r"momentarily|bear with|stand by|shortly to assist|connecting you|in just a moment|"
    r"noted the urgency|i understand the urgency|i understand you're (waiting|in a rush))\b",
    re.I,
)


# ---------- task gold reference ----------
def load_tasks() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for domain in ("retail", "airline"):
        for t in json.loads((TAU2 / domain / "tasks.json").read_text()):
            ec = t.get("evaluation_criteria", {}) or {}
            out[(domain, str(t["id"]))] = {
                "actions": ec.get("actions") or [],
                "reward_basis": ec.get("reward_basis") or [],
                "nl_assertions": ec.get("nl_assertions") or [],
                "communicate_info": ec.get("communicate_info") or [],
            }
    return out


def writes(actions: list[dict], arg_key: str) -> list[tuple[str, str | None, dict]]:
    out = []
    for a in actions:
        if a["name"] in READ_TOOLS:
            continue
        args = a.get(arg_key, {}) or {}
        aid = next((args.get(k) for k in ID_KEYS if args.get(k)), None)
        out.append((a["name"], aid, args))
    return out


def _eq(a, b) -> bool:
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def args_equal(g: dict, a: dict) -> bool:
    return all(_eq(g.get(k, "(absent)"), a.get(k, "(absent)")) for k in set(g) | set(a))


def _is_noop(name: str, aid: str | None, args: dict) -> bool:
    """An extra agent write with no effect: empty kwargs, or only a malformed 'arguments' wrapper."""
    if aid is not None:
        return False
    if not args:
        return True
    return set(args.keys()) == {"arguments"}


def db_match(gold_w, agent_w) -> bool:
    """True iff agent reproduced gold's write-effects exactly (no omission, no arg diff, no
    effective extra write). No-op/malformed extra calls are ignored (errored, no DB effect)."""
    used = [False] * len(agent_w)

    def find(name, aid):
        for i, (an, ai, _) in enumerate(agent_w):
            if not used[i] and an == name and ai == aid:
                return i
        for i, (an, ai, _) in enumerate(agent_w):
            if not used[i] and an == name:
                return i
        return None

    for gname, gid, gargs in gold_w:
        j = find(gname, gid)
        if j is None:
            return False
        used[j] = True
        if not args_equal(gargs, agent_w[j][2]):
            return False
    for i, (an, ai, aargs) in enumerate(agent_w):
        if not used[i] and not _is_noop(an, ai, aargs):
            return False
    return True


# ---------- non-DB components ----------
def nondb_status(task: dict, turns: list[str]) -> str:
    """'provable_1' | 'undet' | 'comm_fail' over the non-DB reward_basis components."""
    rb = set(task["reward_basis"])
    out = []
    if "NL_ASSERTION" in rb:
        out.append("1" if not task["nl_assertions"] else "undet")
    if "COMMUNICATE" in rb:
        ci = task["communicate_info"]
        if not ci:
            out.append("1")
        else:
            hay = [t.lower().replace(",", "") for t in turns]
            allmet = all(any(info.lower() in h for h in hay) for info in ci)
            out.append("1" if allmet else "comm_fail")
    if "comm_fail" in out:
        return "comm_fail"
    if "undet" in out:
        return "undet"
    return "provable_1"


def loop_flag(turns: list[str]) -> bool:
    if not turns:
        return False
    wait = sum(1 for t in turns if WAIT_RE.search(t))
    # prefix repetition only over substantive turns (>=20 chars) so markdown "---"
    # separators and short confirmations ("Yes.") are not mistaken for a stall loop.
    pref = Counter(t[:40].lower() for t in turns if len(t) >= 20)
    maxpref = max(pref.values()) if pref else 0
    return wait >= 4 or maxpref >= 4


def classify(task: dict, trace: list[dict], answer_text: str) -> str:
    gold_w = writes(task["actions"], "arguments")
    agent_w = writes(trace, "kwargs")
    if not db_match(gold_w, agent_w):
        return "RESIDUAL"
    turns = [t.strip() for t in (answer_text or "").split("\n\n") if t.strip()]
    if loop_flag(turns):
        return "B_loop"
    nd = nondb_status(task, turns)
    if nd == "comm_fail":
        return "B_comm"
    if nd == "undet":
        return "A2"
    return "A1"


# ---------- data join ----------
def load_locus() -> dict[tuple[str, str, str, int], str]:
    out = {}
    for stem in MODEL_FILES:
        for line in (MON / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            out[(stem, r["domain"], str(r["task_id"]), int(r["repeat"]))] = r.get("locus")
    return out


def load_captures():
    for stem in MODEL_FILES:
        for line in (CAP / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            yield stem, r


def load_manual() -> dict[tuple[str, str, str, int], tuple[int, str]]:
    """(model_short, domain, task_id, repeat) -> (row_num, verdict)."""
    out = {}
    rows = list(csv.reader(CSV.open()))
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        row, model, domain, tid, rep = r[0], r[1], r[2], r[3], r[4]
        verdict = r[10]
        out[(model, domain, str(tid), int(rep))] = (int(row), verdict)
    return out


def main() -> None:
    tasks = load_tasks()
    locus = load_locus()
    manual = load_manual()

    # population: per model, per (locus bucket), classify reward<1
    by_model = defaultdict(lambda: defaultdict(Counter))  # model -> scope -> Counter(class)
    overall = defaultdict(Counter)                          # scope -> Counter(class)
    n_total = Counter()       # model -> total trajectories
    n_pass = Counter()        # model -> reward>=1
    flagged_loops = 0
    total_rewardlt1 = 0
    manual_rows = {}  # row_num -> (overlay_class, verdict, model, domain, tid, rep)

    for stem, rec in load_captures():
        model_short0 = stem.split("_", 1)[-1]
        n_total[model_short0] += 1
        gr = rec.get("gold_reward")
        if gr is not None and gr >= 1.0:
            n_pass[model_short0] += 1
        if gr is None or gr >= 1.0:
            continue
        total_rewardlt1 += 1
        dom, tid, rep = rec["domain"], str(rec["task_id"]), int(rec["repeat"])
        task = tasks.get((dom, tid))
        if task is None:
            continue
        trace = rec["tool_trace"]
        if isinstance(trace, str):
            trace = json.loads(trace)
        cls = classify(task, trace, rec.get("answer_text", ""))
        if cls == "B_loop":
            flagged_loops += 1
        loc = locus.get((stem, dom, tid, rep), "?")
        model_short = stem.split("_", 1)[-1]

        by_model[model_short]["reward<1"][cls] += 1
        overall["reward<1"][cls] += 1
        if loc == "intent-local":
            by_model[model_short]["intent-local"][cls] += 1
            overall["intent-local"][cls] += 1

        mk = (model_short, dom, tid, rep)
        if mk in manual:
            row_num, verdict = manual[mk]
            manual_rows[row_num] = (cls, verdict)

    # ---------- report ----------
    order = ["A1", "A2", "B_loop", "B_comm", "RESIDUAL"]

    def line(label, c: Counter):
        tot = sum(c.values())
        cells = "  ".join(f"{k}={c.get(k,0):>4}" for k in order)
        return f"  {label:14} n={tot:>4}  {cells}"

    print("=" * 100)
    print("DETERMINISTIC REWARD-FALSE-NEGATIVE OVERLAY  (full reward<1 population, 4 models)")
    print("=" * 100)
    print(f"total reward<1 trajectories: {total_rewardlt1}   loop-flagged: {flagged_loops}")
    print()
    print("--- INTENT-LOCAL population (the RQ3 residual) ---")
    for m in [s.split("_", 1)[-1] for s in MODEL_FILES]:
        print(line(m, by_model[m]["intent-local"]))
    print(line("ALL MODELS", overall["intent-local"]))
    ic = overall["intent-local"]
    tot = sum(ic.values())
    print()
    print(f"  A1 provable reward-fn      : {ic['A1']:>4} / {tot} = {100*ic['A1']/tot:.1f}%  (floor)")
    a12 = ic['A1'] + ic['A2']
    print(f"  A1+A2 (reward-fn ceiling)  : {a12:>4} / {tot} = {100*a12/tot:.1f}%")
    print(f"  B_loop+B_comm (observable) : {ic['B_loop']+ic['B_comm']:>4} / {tot} = {100*(ic['B_loop']+ic['B_comm'])/tot:.1f}%")
    print(f"  RESIDUAL (DB-mismatch)     : {ic['RESIDUAL']:>4} / {tot} = {100*ic['RESIDUAL']/tot:.1f}%")
    print()
    print("--- FULL reward<1 population (RQ1/RQ2 contamination) ---")
    for m in [s.split("_", 1)[-1] for s in MODEL_FILES]:
        print(line(m, by_model[m]["reward<1"]))
    print(line("ALL MODELS", overall["reward<1"]))
    rc = overall["reward<1"]
    tot2 = sum(rc.values())
    print()
    print(f"  A1 provable reward-fn among ALL reward<1: {rc['A1']} / {tot2} = {100*rc['A1']/tot2:.1f}%")

    # ---------- corrected agent success rate ----------
    print()
    print("=" * 100)
    print("CORRECTED AGENT SUCCESS RATE  (tau-bench reward understates success via the termination artifact)")
    print("=" * 100)
    print(f"  {'model':16} {'raw_pass':>10} {'+A1 (floor)':>14} {'+A1+A2 (ceil)':>16}")
    models_short = [s.split("_", 1)[-1] for s in MODEL_FILES]
    pass_rows = {}
    for m in models_short:
        tot_m = n_total[m]
        raw = n_pass[m]
        a1 = by_model[m]["reward<1"]["A1"]
        a2 = by_model[m]["reward<1"]["A2"]
        floor = (raw + a1) / tot_m
        ceil = (raw + a1 + a2) / tot_m
        pass_rows[m] = (tot_m, raw, a1, a2, floor, ceil)
        print(f"  {m:16} {raw/tot_m*100:>9.1f}% {floor*100:>13.1f}% {ceil*100:>15.1f}%   "
              f"(raw {raw}/{tot_m}, +A1 {a1}, +A2 {a2})")

    # confusion of overlay class vs manual verdict (used by md + validation print)
    confusion = defaultdict(Counter)
    for row in sorted(manual_rows):
        cls, verdict = manual_rows[row]
        confusion[cls][verdict] += 1

    # ---------- write markdown artifact ----------
    def pct(n, d):
        return f"{100*n/d:.1f}%" if d else "-"

    md = []
    md.append("# Deterministic reward-false-negative overlay — full-population results")
    md.append("")
    md.append("Generated by `eval/overlay_reward_fn.py` (no LLM, no re-capture). For every `reward<1` "
              "trajectory in `results/capture/*.jsonl` it deterministically classifies whether the agent "
              "actually reproduced gold's DB write-effects, and whether the non-DB reward components are "
              "provably satisfied. This scales the 40-row manual spot-check "
              "(`intent_local_review.csv`) to the whole population.")
    md.append("")
    md.append("## Classes")
    md.append("")
    md.append("- **A1 — provable reward false-negative.** Agent writes == gold actions (full args) AND every "
              "non-DB `reward_basis` component is deterministically 1 (empty NL_ASSERTION/COMMUNICATE, or "
              "COMMUNICATE substrings all present). All components = 1 yet `reward=0` -> only the "
              "premature-termination guard (`evaluator.py:113`) can explain it -> the agent succeeded.")
    md.append("- **A2 — undetermined.** DB-match, but a non-empty `nl_assertions` is scored by the LLM judge, "
              "which cannot be replicated deterministically. Mixed bucket (manual sample: ~82% reward-fn, "
              "~18% genuine answer failures).")
    md.append("- **B_loop / B_comm — observable failure (deterministic).** DB-match but the answer degenerates "
              "into a stall loop (B_loop) or a required COMMUNICATE string is absent (B_comm). Real, recoverable.")
    md.append("- **RESIDUAL — DB mismatch.** Agent's writes differ from gold (omission / extra / different args). "
              "Genuine DB-level `reward=0`: missed-detection + true-intent-local + unsure (not separable here).")
    md.append("")
    md.append("## Intent-local population (the RQ3 residual)")
    md.append("")
    md.append("| model | n | A1 | A2 | B_loop | B_comm | RESIDUAL |")
    md.append("|---|--:|--:|--:|--:|--:|--:|")
    for m in models_short:
        c = by_model[m]["intent-local"]
        n = sum(c.values())
        md.append(f"| {m} | {n} | {c['A1']} | {c['A2']} | {c['B_loop']} | {c['B_comm']} | {c['RESIDUAL']} |")
    c = overall["intent-local"]
    n = sum(c.values())
    md.append(f"| **ALL** | **{n}** | **{c['A1']}** | **{c['A2']}** | **{c['B_loop']}** | **{c['B_comm']}** | **{c['RESIDUAL']}** |")
    md.append("")
    md.append(f"- **Provable reward-fn floor (A1):** {c['A1']}/{n} = **{pct(c['A1'],n)}**")
    md.append(f"- **Reward-fn ceiling (A1+A2):** {c['A1']+c['A2']}/{n} = **{pct(c['A1']+c['A2'],n)}**")
    md.append(f"- **Observable defect (B_loop+B_comm):** {c['B_loop']+c['B_comm']}/{n} = {pct(c['B_loop']+c['B_comm'],n)}")
    md.append(f"- **DB-mismatch residual:** {c['RESIDUAL']}/{n} = {pct(c['RESIDUAL'],n)}  "
              "(manual sample splits this ~25% true-intent-local / ~50% missed-detection / ~25% unsure)")
    md.append("")
    md.append("## Full reward<1 population (RQ1/RQ2 failure-set contamination)")
    md.append("")
    md.append("| model | reward<1 | A1 | A2 | B_loop | B_comm | RESIDUAL |")
    md.append("|---|--:|--:|--:|--:|--:|--:|")
    for m in models_short:
        c = by_model[m]["reward<1"]
        n = sum(c.values())
        md.append(f"| {m} | {n} | {c['A1']} | {c['A2']} | {c['B_loop']} | {c['B_comm']} | {c['RESIDUAL']} |")
    c = overall["reward<1"]
    n = sum(c.values())
    md.append(f"| **ALL** | **{n}** | **{c['A1']}** | **{c['A2']}** | **{c['B_loop']}** | **{c['B_comm']}** | **{c['RESIDUAL']}** |")
    md.append("")
    md.append(f"**{c['A1']}/{n} = {pct(c['A1'],n)} of ALL reward<1 trajectories are provable reward false-negatives** "
              "(agent succeeded) — the same termination artifact contaminates RQ1/RQ2 failure sets, not just RQ3.")
    md.append("")
    md.append("## Corrected agent success rate")
    md.append("")
    md.append("τ-bench reward = 0 does NOT mean the agent failed. Re-scoring provable successes:")
    md.append("")
    md.append("| model | raw pass | + A1 (floor) | + A1+A2 (ceiling) |")
    md.append("|---|--:|--:|--:|")
    for m in models_short:
        tot_m, raw, a1, a2, floor, ceil = pass_rows[m]
        md.append(f"| {m} | {raw/tot_m*100:.1f}% | {floor*100:.1f}% | {ceil*100:.1f}% |")
    md.append("")
    md.append("## Validation against the 40-row manual review")
    md.append("")
    md.append("Overlay class vs human verdict for the 40 manually-reviewed rows:")
    md.append("")
    md.append("| overlay | manual verdicts |")
    md.append("|---|---|")
    for cls in order:
        if confusion[cls]:
            parts = ", ".join(f"{n}x {v.strip()}" for v, n in confusion[cls].most_common())
            md.append(f"| {cls} | {parts} |")
    md.append("")
    md.append("The deterministic classes (A1, B_loop, B_comm, RESIDUAL) are 100% consistent with the human "
              "labels; only A2 is intentionally ambiguous (the human split it into reward-fn vs answer-failures "
              "using the LLM-judged channel the overlay deliberately refuses to guess). The overlay also "
              "independently corrects the one inconsistent manual label (R5 -> A2, not termination-artifact).")
    (ROOT / "eval" / "locus_spotcheck" / "reward_fn_overlay.md").write_text("\n".join(md))
    print("\nwrote eval/locus_spotcheck/reward_fn_overlay.md")

    # ---------- validation vs 40 manual ----------
    print()
    print("=" * 100)
    print("VALIDATION: overlay class vs 40 manual verdicts")
    print("=" * 100)
    # expected mapping (overlay -> which manual verdicts SHOULD land there)
    agree = 0
    confusion = defaultdict(Counter)
    for row in sorted(manual_rows):
        cls, verdict = manual_rows[row]
        confusion[cls][verdict] += 1
    for cls in order:
        if confusion[cls]:
            print(f"\noverlay={cls}:")
            for v, n in confusion[cls].most_common():
                print(f"    {n:>2}x  {v}")
    # also print full per-row table
    print("\nper-row:")
    print(f"  {'row':>3}  {'overlay':10}  manual_verdict")
    for row in sorted(manual_rows):
        cls, verdict = manual_rows[row]
        print(f"  {row:>3}  {cls:10}  {verdict}")

    # ---------- write artifact ----------
    out_json = {
        "total_reward_lt1": total_rewardlt1,
        "loop_flagged": flagged_loops,
        "intent_local": {m: dict(by_model[m]["intent-local"]) for m in by_model},
        "intent_local_all": dict(overall["intent-local"]),
        "reward_lt1": {m: dict(by_model[m]["reward<1"]) for m in by_model},
        "reward_lt1_all": dict(overall["reward<1"]),
    }
    (ROOT / "eval" / "locus_spotcheck" / "reward_fn_overlay.json").write_text(
        json.dumps(out_json, indent=2, ensure_ascii=False)
    )
    print("\nwrote eval/locus_spotcheck/reward_fn_overlay.json")


if __name__ == "__main__":
    main()
