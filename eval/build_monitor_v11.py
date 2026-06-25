"""Build the reward-fn-corrected monitor shards (results/monitor_v11) for the V11 thesis.

Re-scores `gold_reward` 0->1 for the provable reward false-negatives the monitor flagged nothing on
(intent-local A1 from the deterministic overlay). Everything else is copied verbatim from
results/monitor_v2. Running `python -m eval.analyze --monitor-dir results/monitor_v11 ...` then
produces the corrected metrics and figures with the standard styling.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from eval.overlay_reward_fn import classify, load_tasks, MODEL_FILES, CAP

ROOT = Path(__file__).resolve().parents[1]
MON_V2 = ROOT / "results" / "monitor_v2"
MON_V11 = ROOT / "results" / "monitor_v11"

_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def a2_values_present(task: dict, answer_text: str) -> bool:
    """True iff every nl_assertion carries a numeric fact AND all such numbers appear in the answer.

    Deterministic verification of NL-assertion satisfaction for numeric (price/quantity) assertions,
    mirroring tau2's substring-based COMMUNICATE check. Purely-qualitative assertions return False
    (cannot verify -> conservatively retained as failures). Validated on the 40-row manual review to
    flip zero human-judged failures.
    """
    nls = task.get("nl_assertions") or []
    if not nls:
        return False
    hay = (answer_text or "").replace(",", "")
    for a in nls:
        nums = [m.group(0).replace(",", "") for m in _NUM_RE.finditer(a)]
        if not nums or any(n not in hay for n in nums):
            return False
    return True


def rescore_keys_by_stem() -> dict[str, set]:
    """stem -> set of (domain, task_id, repeat) that are provable reward false-negatives:
    A1 (DB-match + non-DB components empty/met) OR A2 with all numeric NL facts present in the answer.
    """
    tasks = load_tasks()
    out: dict[str, set] = {s: set() for s in MODEL_FILES}
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
            ans = r.get("answer_text", "")
            cls = classify(task, trace, ans)
            if cls == "A1" or (cls == "A2" and a2_values_present(task, ans)):
                out[stem].add((dom, tid, rep))
    return out


def main() -> None:
    MON_V11.mkdir(parents=True, exist_ok=True)
    rescore = rescore_keys_by_stem()
    total_rescored = 0
    for stem in MODEL_FILES:
        rescored = 0
        out_lines = []
        for line in (MON_V2 / f"{stem}.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = (r["domain"], str(r["task_id"]), int(r["repeat"]))
            # re-score intent-local provable reward false-negatives (A1, or A2 with numeric facts met)
            if key in rescore[stem] and r.get("locus") == "intent-local" and (r.get("gold_reward") or 0) < 1.0:
                r = {**r, "gold_reward": 1.0, "rewardfn_corrected": True}
                rescored += 1
            out_lines.append(json.dumps(r))
        (MON_V11 / f"{stem}.jsonl").write_text("\n".join(out_lines) + "\n")
        total_rescored += rescored
        print(f"  {stem}: re-scored {rescored} intent-local provable reward-fn -> PASS")
    print(f"total re-scored: {total_rescored}  ->  {MON_V11}")


if __name__ == "__main__":
    main()
