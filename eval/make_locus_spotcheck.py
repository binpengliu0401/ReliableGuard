"""Generate a reproducible intent-local spot-check review sheet.

Purpose (RQ3 validity): the intent-local locus is the *residual* of the
deterministic annotator (src/reliableguard/locus.py) -- a trajectory is labelled
intent-local iff no trace violation, no state contradiction, and no answer
incompleteness fired. Its purity therefore depends on verifier *coverage*: a
real trace/state failure for which no rule exists would be mis-labelled
intent-local, inflating pi_intent. This script samples intent-local trajectories
and lays out, per row, everything a human needs to judge:

    true intent-local  (legal + state-consistent action, just not what the
                         user wanted)
            vs.
    missed-violation   (the verifier lacked a rule; it is really trace/state-local)

Sampling is SEEDED-RANDOM and stratified (fixed SEED -> fully reproducible):
  - 4 audited models x N_PER_MODEL rows.
  - Within a model, take intent-local trajectories, keep one representative
    repeat (lowest repeat index) per distinct (domain, task_id), then draw
    N_PER_MODEL via random.Random(f"{SEED}:{model}").sample(...). Each model
    draws independently; re-running with the same SEED reproduces the draw.

Inputs : results/monitor_v2/*.jsonl  (carries the `locus` tag)
         results/capture/*.jsonl     (carries query / answer_text / tool_trace)
         tau2-bench retail+airline tasks.json (user intent + gold actions)
Outputs: eval/locus_spotcheck/intent_local_review.md   (full context + verdict line)
         eval/locus_spotcheck/intent_local_review.csv  (tally sheet)
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

N_PER_MODEL = 10
# Fixed sampling seed — recorded so the 40-row draw is fully reproducible.
# Per-model seed = f"{SEED}:{model}" so models draw independently.
SEED = 20260623
ROOT = Path(__file__).resolve().parents[1]
MONITOR_DIR = ROOT / "results" / "monitor_v2"
CAPTURE_DIR = ROOT / "results" / "capture"
OUT_DIR = ROOT / "eval" / "locus_spotcheck"
TAU2 = Path("/Users/beike/Desktop/PolyU/semester_2/5902/code/tau2-bench/data/tau2/domains")

# Canonical model order (matches tables/figures); file stems in results/.
MODEL_FILES = [
    "deepseek_deepseek-v4-pro",
    "xiaomi_mimo-v2.5-pro",
    "z-ai_glm-4.7-flash",
    "qwen_qwen3.6-flash",
]

# Read-only / non-state-changing tools -> excluded from "write" summaries.
READ_TOOLS = {
    "find_user_id_by_email", "find_user_id_by_name_zip", "get_order_details",
    "get_user_details", "get_product_details", "get_item_details",
    "get_reservation_details", "search_direct_flight", "calculate",
    "list_all_product_types", "think", "transfer_to_human_agents",
    # airline read-only tools (state-changing send_certificate stays a "write")
    "get_flight_status", "list_all_airports", "search_onestop_flight",
}
ID_KEYS = ("order_id", "reservation_id")


def load_tasks() -> dict[tuple[str, str], dict]:
    """(domain, task_id) -> task dict, for retail + airline."""
    out: dict[tuple[str, str], dict] = {}
    for domain in ("retail", "airline"):
        for t in json.loads((TAU2 / domain / "tasks.json").read_text()):
            out[(domain, str(t["id"]))] = t
    return out


def gold_writes(task: dict) -> list[str]:
    rows = []
    for a in task["evaluation_criteria"].get("actions") or []:
        if a["name"] in READ_TOOLS:
            continue
        oid = next((a["arguments"].get(k) for k in ID_KEYS if a["arguments"].get(k)), None)
        rows.append(f"{a['name']}({oid})" if oid else a["name"])
    return rows


def gold_full(task: dict) -> list[str]:
    """Gold write actions with their FULL arguments (the intent-level reference)."""
    rows = []
    for a in task["evaluation_criteria"].get("actions") or []:
        if a["name"] in READ_TOOLS:
            continue
        rows.append(f"{a['name']}({json.dumps(a['arguments'], ensure_ascii=False)})")
    return rows


def agent_writes(trace: list[dict]) -> list[str]:
    rows = []
    for c in trace:
        if c["name"] in READ_TOOLS:
            continue
        kw = c.get("kwargs", {})
        oid = next((kw.get(k) for k in ID_KEYS if kw.get(k)), None)
        rows.append(f"{c['name']}({oid})" if oid else c["name"])
    return rows


def _raw_writes(actions: list[dict], arg_key: str) -> list[tuple[str, str | None, dict]]:
    """[(name, id, args)] for non-read actions. arg_key='arguments' (gold) | 'kwargs' (agent)."""
    out = []
    for a in actions:
        if a["name"] in READ_TOOLS:
            continue
        args = a.get(arg_key, {}) or {}
        aid = next((args.get(k) for k in ID_KEYS if args.get(k)), None)
        out.append((a["name"], aid, args))
    return out


def _fmt(v) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 60 else s[:57] + "..."


def _eq(a, b) -> bool:
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def param_diff_table(task: dict, trace: list[dict]) -> list[str]:
    """Markdown lines: per write action, the argument fields where gold and agent differ.

    Matches gold<->agent write actions by (name, id), falling back to name only; reports
    gold actions the agent omitted and agent writes with no gold counterpart.
    """
    gold = _raw_writes(task.get("evaluation_criteria", {}).get("actions") or [], "arguments")
    agent = _raw_writes(trace, "kwargs")
    used = [False] * len(agent)

    def find(name: str, aid: str | None) -> int | None:
        for i, (an, ai, _) in enumerate(agent):
            if not used[i] and an == name and ai == aid:
                return i
        for i, (an, _ai, _) in enumerate(agent):
            if not used[i] and an == name:
                return i
        return None

    lines: list[str] = []
    for gname, gid, gargs in gold:
        label = f"{gname}({gid})" if gid else gname
        j = find(gname, gid)
        if j is None:
            lines.append(f"**{label}** — GOLD action has NO matching agent call (agent omitted it).")
            lines.append("")
            continue
        used[j] = True
        aargs = agent[j][2]
        diffs = [(k, gargs.get(k, "(absent)"), aargs.get(k, "(absent)"))
                 for k in sorted(set(gargs) | set(aargs))
                 if not _eq(gargs.get(k, "(absent)"), aargs.get(k, "(absent)"))]
        if not diffs:
            lines.append(f"**{label}** — agent args identical to gold.")
            lines.append("")
            continue
        lines.append(f"**{label}** — differing fields:")
        lines.append("")
        lines.append("| field | gold | agent |")
        lines.append("|---|---|---|")
        for k, gv, av in diffs:
            lines.append(f"| {k} | {_fmt(gv)} | {_fmt(av)} |")
        lines.append("")
    for i, (an, ai, _) in enumerate(agent):
        if not used[i]:
            label = f"{an}({ai})" if ai else an
            lines.append(f"**{label}** — agent write with NO gold counterpart (extra action).")
            lines.append("")
    return lines or ["(no write actions on either side)"]


def intent_for(task: dict) -> str:
    return task["user_scenario"]["instructions"].get("reason_for_call", "").strip()


def seeded_sample(items: list, k: int, model_seed: str) -> list:
    """Pick k items by seeded random sampling (reproducible for a fixed seed)."""
    if len(items) <= k:
        return list(items)
    return random.Random(model_seed).sample(items, k)


def main() -> None:
    tasks = load_tasks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for stem in MODEL_FILES:
        # 1) intent-local (task_id, domain, repeat) from monitor_v2
        intent_keys: list[tuple[str, str, int]] = []
        for line in (MONITOR_DIR / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("locus") == "intent-local":
                intent_keys.append((str(r["task_id"]), r["domain"], int(r["repeat"])))

        # 2) one representative repeat (lowest) per (domain, task_id)
        rep: dict[tuple[str, str], int] = {}
        for tid, dom, repeat in intent_keys:
            key = (dom, tid)
            if key not in rep or repeat < rep[key]:
                rep[key] = repeat
        uniq = sorted(rep.items(), key=lambda kv: (kv[0][0], int(kv[0][1])))
        picked = seeded_sample(uniq, N_PER_MODEL, f"{SEED}:{stem}")
        picked = sorted(picked, key=lambda kv: (kv[0][0], int(kv[0][1])))
        picked_set = {(dom, tid, repeat) for (dom, tid), repeat in picked}

        # 3) join with capture for query / answer / trace
        cap: dict[tuple[str, str, int], dict] = {}
        for line in (CAPTURE_DIR / f"{stem}.jsonl").read_text().splitlines():
            r = json.loads(line)
            k = (r["domain"], str(r["task_id"]), int(r["repeat"]))
            if k in picked_set:
                cap[k] = r

        for (dom, tid), repeat in picked:
            c = cap.get((dom, tid, repeat))
            if c is None:
                continue
            task = tasks.get((dom, tid), {})
            trace = c["tool_trace"]
            if isinstance(trace, str):
                trace = json.loads(trace)
            rows.append({
                "model": stem.split("_", 1)[-1],
                "domain": dom,
                "task_id": tid,
                "repeat": repeat,
                "gold_reward": c.get("gold_reward"),
                "user_intent": intent_for(task) if task else "(task not found)",
                "query": c.get("query", ""),
                "answer_text": c.get("answer_text", ""),
                "gold_writes": gold_writes(task) if task else [],
                "gold_full": gold_full(task) if task else [],
                "param_diff": param_diff_table(task, trace) if task else ["(task not found)"],
                "agent_writes": agent_writes(trace),
                "full_trace": [
                    f"{c['name']}({json.dumps(c.get('kwargs', {}), ensure_ascii=False)})"
                    for c in trace
                ],
            })

    # ---- CSV tally sheet (columns follow the manual-review template) ----
    csv_path = OUT_DIR / "intent_local_review.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "row", "model", "domain", "task_id", "repeat", "gold_reward",
            "gold_writes", "agent_writes",
            "counterfactual_holds",        # same trace + different task -> reward flips? (Y/N)
            "discriminator_only_in_gold",  # is the failing signal visible ONLY via gold? (Y/N)
            "verdict",                     # true-intent-local / missed-detection
            "true_class_if_missed",        # trace / state / answer  (only if verdict=missed)
            "basis",                       # which gold action + which dialogue cue (REQUIRED)
        ])
        for i, r in enumerate(rows, 1):
            w.writerow([i, r["model"], r["domain"], r["task_id"], r["repeat"],
                        r["gold_reward"], " ; ".join(r["gold_writes"]),
                        " ; ".join(r["agent_writes"]), "", "", "", "", ""])

    # ---- Markdown review sheet ----
    md = [
        "# Intent-local spot-check review sheet",
        "",
        f"**Sample:** {len(rows)} intent-local trajectories, {N_PER_MODEL} per model, "
        f"seeded random stratified sampling (SEED={SEED}, per-model seed = f\"{{SEED}}:{{model}}\"; "
        "see make_locus_spotcheck.py). Re-running with the same seed reproduces this exact draw.",
        "",
        "**The one thing to check per row:** against the gold r_actions, is the failure judgeable "
        "*only* from gold — i.e. invisible in the trace, state, and answer channels?",
        "",
        "- `true-intent-local` — yes: the agent's actions are legal AND the resulting state is "
        "consistent; it is simply not what the user wanted (wrong object, or a goal the user "
        "expressed only implicitly). The annotator is correct. (Counterfactual: the *same* trace "
        "under a task that wanted this action would score reward=1.)",
        "- `missed-detection` — no: there IS an observable trace/state/answer failure (a policy "
        "rule was broken, a claimed effect is absent from the state, or the answer is incomplete) "
        "that the verifier lacked a rule for. This is really trace/state/answer-local; the "
        "annotator mis-labelled it. Record which class it really is.",
        "- `unsure` — cannot decide from the artifacts shown.",
        "",
        "This `.md` is for reading. **Record your verdicts in `intent_local_review.csv`** "
        "(columns: counterfactual_holds, discriminator_only_in_gold, verdict, true_class_if_missed, "
        "basis). `basis` is required — cite the specific gold action and the specific dialogue/trace "
        "cue, not just the conclusion.",
        "",
        "Note: only the agent's turns and the *first* user message are captured; the user-sim's "
        "intermediate replies are not. If a verdict hinges on what the user said mid-conversation, "
        "mark it `unsure`.",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(rows, 1):
        md += [
            f"## Row {i} — {r['model']} | {r['domain']} | task {r['task_id']} "
            f"(repeat {r['repeat']}, gold_reward={r['gold_reward']})",
            "",
            f"**User intent (reason_for_call):** {r['user_intent']}",
            "",
            f"**First user message:** {r['query']}",
            "",
            f"**GOLD write actions:** {r['gold_writes'] or '(none)'}",
            "",
            "**GOLD actions with full arguments (intent-level reference — compare these "
            "against the agent's call args):**",
            "",
            "```",
            *([f"{j:2}. {g}" for j, g in enumerate(r["gold_full"], 1)] or ["(no gold write actions)"]),
            "```",
            "",
            f"**AGENT write actions:** {r['agent_writes'] or '(none)'}",
            "",
            "**▶ PARAM DIFF (gold vs agent — auto-computed; this is where intent-local "
            "divergences usually live):**",
            "",
            *r["param_diff"],
            "",
            "**Full tool-call sequence (agent — with full arguments):**",
            "",
            "```",
            *[f"{j:2}. {call}" for j, call in enumerate(r["full_trace"], 1)],
            "```",
            "",
            "**Agent conversation (all assistant turns, in order — user-sim replies not captured; "
            "only the first user message above is available):**",
            "",
            r["answer_text"] or "(empty)",
            "",
            "---",
            "",
        ]
    (OUT_DIR / "intent_local_review.md").write_text("\n".join(md))

    print(f"Wrote {len(rows)} rows:")
    print(f"  {csv_path}")
    print(f"  {OUT_DIR / 'intent_local_review.md'}")
    by_dom: dict[str, int] = {}
    for r in rows:
        by_dom[r["domain"]] = by_dom.get(r["domain"], 0) + 1
    print(f"  domain split: {by_dom}")


if __name__ == "__main__":
    main()
