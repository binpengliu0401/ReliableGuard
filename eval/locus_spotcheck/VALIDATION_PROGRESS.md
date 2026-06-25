# Intent-local spot-check — final findings (handoff)

Working note for the RQ3 intent-local validity review (40-row manual spot-check over
`intent_local_review.md` / `.csv`). Verdicts are decided by the human reviewer; this file records
what we found. **Status: 40 of 40 rows reviewed — COMPLETE.** The authoritative per-row labels live
in `intent_local_review.csv`; the consolidated tally is in "Final tally" below.

## The headline finding (this changes RQ3)

The intent-local residual is **NOT** just `{true-intent-local, missed-detection}`. A large share of
it is **reward-oracle false negatives**: trajectories where the agent actually succeeded (reached the
gold DB end-state and communicated the required info) but tau2 scored `reward=0`. The deterministic
locus rule (`reward<1` + no trace/state/answer signal -> intent-local) faithfully inherits this bad
`reward=0`, so these false-0s land in the intent-local bucket.

**Of the 40 sampled "intent-local" rows, only 4 (10%) are a genuine irreducible boundary.** The rest
decompose into: 19 (47.5%) reward false-negatives (agent actually succeeded), 13 (32.5%) real
failures the monitor could catch with a new rule (recoverable, NOT a boundary), and 4 (10%) unsure
(hinge on uncaptured user-sim turns). So the raw residual **overstates the intent-local boundary by
~5-10x**.

**Root cause is upstream of `locus.py`, in the tau2 reward, via two mechanisms:**

1. **Premature-termination guard** (`tau2-bench/src/tau2/evaluator/evaluator.py:113-123`):
   if `termination_reason not in {AGENT_STOP, USER_STOP}` the reward is forced to `0.0` regardless of
   DB/NL correctness. A conversation ends cleanly ONLY when:
   - the **user-sim** emits the literal token `###STOP###` or `###TRANSFER###`
     (`user_simulator.py:193`, constants in `user_simulator_base.py:51-52`; the user-sim is
     instructed to do so in `data/tau2/user_simulator/simulation_guidelines.md:14-16`), OR
   - the **agent** calls the `done` tool / emits `###STOP###` (`llm_agent.py:329-331,418,431`).
   - A natural-language goodbye ("Bye! 👋") is NOT a stop. `transfer_to_human_agents` is NOT a stop
     either (only `done` is). So termination usually depends on the user-sim (minimax-m3) emitting
     `###STOP###`/`###TRANSFER###`. When it doesn't -> `MAX_STEPS` -> reward 0 even for a perfect run.

2. **NL-assertion judge false negative** (`evaluator_nl_assertions.py`): when a task has non-empty
   `nl_assertions` and `NL_ASSERTION` in `reward_basis`, an LLM judge grades them
   (patched to `openrouter/deepseek/deepseek-v4-pro` in `capture_tau2.py:121-125` — a flaky model,
   cf. `project_llm_nondeterminism`). It can score `met=false` on info the agent plainly stated.
   - Note: **empty** `nl_assertions` returns reward=1 vacuously (`evaluator_nl_assertions.py:38-44`).

Reward aggregation: `reward = product of components in reward_basis` (`evaluator.py:189-248`).

## Two data-capture gaps (both "thrown away at capture time", not fundamental)

These cap what we can decide from the frozen `results/capture/*.jsonl`:

1. **User-sim intermediate turns not saved.** `capture_tau2.py` keeps only assistant turns
   (`answer_text`), assistant tool calls (`tool_trace`), and the *first* user message (`query`);
   intermediate user-sim turns are dropped (`capture_tau2.py:166-182`). => any verdict that hinges on
   what the user said mid-conversation must be `unsure`. NOT recoverable (tau2 `run_simulation` does
   not persist `sim`; `data/tau2/results/final/` is upstream's own GPT-4/Claude runs, not ours;
   re-running would generate different conversations due to non-determinism).

2. **`termination_reason` and `reward_breakdown` not saved.** `capture_tau2.py:184` stores only the
   scalar `gold_reward`. => for a reward-fn with non-empty NL we cannot tell **termination-artifact**
   from **nl-judge-fn**; record subtype `undetermined`. (When NL is empty, NL=1 is forced, so the
   subtype is provably termination-artifact.)

## reward-fn subtypes (verdict vocabulary, decided with the reviewer)

- `true-intent-local` — legal action + consistent state, just not what the user wanted; only gold reveals it.
- `missed-detection(<channel>)` — a real observable trace/state/answer failure the verifier lacked a rule for.
- `reward-fn(termination-artifact)` — agent succeeded; reward=0 forced by the termination guard (provable when NL empty).
- `reward-fn(nl-judge-fn)` — agent succeeded incl. NL; reward=0 from a judge false negative.
- `reward-fn(undetermined: termination | nl-judge-fn)` — reward-fn but the two cannot be separated (no breakdown saved + non-empty NL).
- `unsure` — genuinely undecidable from artifacts (esp. depends on uncaptured user turns).

## Final tally (40 rows, reorganized by what `reward=0` actually means)

Authoritative per-row labels are in `intent_local_review.csv`. Grouped:

| Category | Meaning | Rows | n | % |
|---|---|---|---|---|
| **A. Agent actually succeeded (reward false-negative)** | should be `reward=1`; remove from failure set | — | **19** | 47.5% |
| &nbsp;&nbsp;A1 termination-artifact (provable) | DB=gold + NL empty/satisfied; only the termination guard zeroed it | R6,7,9,16,17,22,31,32,39,40 (+R5*) | 10-11 | |
| &nbsp;&nbsp;A2 undetermined (term or nl-fn) | DB=gold + NL info stated; no breakdown saved -> can't split | R8,10,20,23,24,27,34,38 (+R5*) | 8-9 | |
| **B. Real failure, monitor MISSED it (recoverable)** | a rule gap, NOT a boundary | — | **13** | 32.5% |
| &nbsp;&nbsp;B-answer | omitted sub-request / wrong stated number / promised-but-undone / delivered != spec | R3,14,15,18,19,28,29,35,36 | 9 | |
| &nbsp;&nbsp;B-trace | unauthorized compensation (R13) + degenerate NL-loop (R11,21,37) | R13,11,21,37 | 4 | |
| **C. True intent-local (irreducible boundary)** | legal action + consistent state; only gold reveals it | R1,2,4,12 | **4** | 10% |
| **D. Unsure** | hinges on uncaptured user-sim turns | R25,26,30,33 | **4** | 10% |

\* **R5 cleanup item (defer to reviewer):** its CSV label is `termination-artifact`, but its basis
argues nl-judge false-negative (task has non-empty NL). By our own rule (non-empty NL + no breakdown
-> can't prove termination) R5 should be `undetermined`, matching R8/R10/R24. Reclassifying it does
not change the reward-fn total (19); it only moves A1->A2 (11/8 becomes 10/9).

**Why A is not the agent's fault (max_steps + stop-token protocol).** Every A-row has DB=gold, so the
agent finished the task; reward=0 comes only from `evaluator.py:113` because no stop token appeared.
Two compounding harness causes, neither attributable to the agent: (a) the stop token
(`###STOP###`/`###TRANSFER###`) is mainly the user-sim's (minimax-m3) job and it often never emits it
(prose goodbye / `transfer_to_human_agents` do NOT count); (b) `max_steps=30` (`capture_tau2.py:102`,
vs tau2 default 100) caps the window before a late token could arrive. Fix for v3: raise max_steps
AND/OR treat a clean DB=gold completion as success without requiring the token.

**Important distinction (justifies R11/R21/R37 -> B, not A):** the degenerate-LOOP rows are NOT "just
missing a stop sign" — the agent actively spammed "please hold"/"Take care"/"momentarily" 7-12x
instead of ending. That is an observable agent defect -> `missed-detection(trace)`. Clean completion
with no token = A (success); active loop = B (real failure). R31/R32 are clean refuses (not loops),
so they stay in A.

## Implications / next steps

- **Corrected π_intent.** The true irreducible boundary is C only: **4/40 = 10%** of the raw
  intent-local bucket (upper bound 8/40 = 20% if all D resolve to intent-local). Report this, not the
  raw residual, for the "intent-local = irreducible black-box boundary" claim.
- **Intent-local contamination is locatable.** High-suspicion (= reward-fn) subset is exactly the
  rows where `agent_writes == gold_writes` (A-rows). Rows with `agent_writes != gold`
  (omitted/extra/partial) are the genuine failures + boundary (B/C). This split is mechanical, so a
  deterministic overlay can scale it past the 40 samples.
- **Deterministic overlay — DONE** (`eval/overlay_reward_fn.py`, results in `reward_fn_overlay.{md,json}`).
  See the next section for the full-population numbers.
- **v3 capture fix (when re-running):** add `termination_reason` + `reward_breakdown` (+ full
  `messages` incl. user turns) to the Trajectory -> separates termination vs nl-judge-fn at source
  and kills most `unsure`/`undetermined`. Also raise `max_steps` from 30 toward the tau2 default 100.

## Population overlay (full reward<1, deterministic — `eval/overlay_reward_fn.py`)

Scales the 40-row spot-check to all 2992 `reward<1` trajectories (intent-local subset 2134), no LLM,
no re-capture. Classes: **A1** provable reward-fn (DB-match + every non-DB component provably 1 ->
only the termination guard can zero it), **A2** undetermined (DB-match but LLM-judged NL), **B_loop/
B_comm** observable defect, **RESIDUAL** DB-mismatch (genuine: missed + true-intent + unsure).

Intent-local (n=2134): **A1 412 (19.3%)** | A2 370 (17.3%) | B_loop+B_comm 31 (1.5%) | RESIDUAL 1321
(61.9%). Reward-fn floor 19.3%, ceiling (A1+A2) 36.6%, point estimate ~33% (manual A2 ~82% reward-fn).

Per model A1 (intent-local): deepseek 46/334, mimo 130/596, glm 68/477, qwen 168/727.

Full `reward<1` (n=2992): **A1 539 = 18.0%** are provable reward-fn -> RQ1/RQ2 failure sets are
contaminated too, not just RQ3.

**Corrected agent success rate** (re-scoring A1 as success): deepseek 71.3%->75.2%, mimo
43.5%->**56.3%**, glm 52.9%->58.1%, qwen 49.9%->60.9% (floor; ceiling adds A2). Flash models are
under-reported most (they finish the task but never emit the stop token / loop).

**Validation:** overlay class vs the 40 manual verdicts — the deterministic classes (A1, B_loop,
B_comm, RESIDUAL) are 100% consistent (29/29); only A2 is intentionally ambiguous (the human split it
9 reward-fn / 2 answer-fail using the LLM-judged channel the overlay refuses to guess). The overlay
independently corrected the one inconsistent manual label (R5 -> A2, not termination-artifact).

**Caveat:** the 40-row sample's 47.5% reward-fn OVERSTATES the population — stratified sampling (one
repeat per task, 10/model) over-weighted no-write refuse/info tasks, which are A1/A2. The defensible
population number is the **19.3% provable floor** (~33% point estimate), not 47.5%. Counts are the
`monitor_v2`/`capture` draw; LLM non-determinism -> representative, not bit-reproducible.
