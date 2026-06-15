# ReliableGuard (re-grounded on τ-bench) — Full Experimental Design

## Context

The graded deliverable is the defense presentation; the central challengeable weakness was
**self-made data** (the student authored scenarios + answer key + monitor in Set A/Set B, and F0–F5
was an injection recipe bound to it). Decision (2026-06-09): **drop Set A/Set B entirely** and
re-base the whole evaluation on **τ-bench** (Yao et al. 2024; sierra-research/tau-bench +
tau2/tau3), a recognized agent benchmark whose ground truth is **execution-based** (final DB state
vs an annotated goal) and **not authored by the student**. The genuine, data-independent
contribution is preserved: the **locus-of-ground-truth taxonomy + channel-matching principle**.
F0–F5 is retired and replaced by **locus error-analysis over real τ-bench failures** (correctness
always comes from τ-bench's reward; we only add a locus tag).

Key verified facts: τ-bench domains = retail / airline / telecom / banking_knowledge(RAG); model
backend = LiteLLM → OpenRouter (multi-LLM native); per task it exposes tool trace (`env.actions`),
DB state (`env.data`), and gold reward (`calculate_reward()` using the goal annotation
`info.r_actions`); each domain ships an explicit **policy** (`wiki.md`) with preconditions and
action-ordering (e.g. retail: cancel only if status='pending'; auth before any action; confirm
before any DB write; modify-items permanently blocks later modify/cancel). Retail has **no
free order creation** (operates on pre-existing orders) — so custom adversarial probes (e.g. a
-1000 order) are NOT injected; that would reintroduce self-made data and is allowed only as an
illustrative demo, never as headline evidence.

## Non-circularity (the spine's defense)

τ-bench reward needs the goal annotation `r_actions`; the monitor reads ONLY deployment-observable
artifacts (final answer + `env.actions` + `env.data` before/after) and NEVER `r_actions`. Reward and
monitor signals come from disjoint inputs → not circular. The failures the monitor cannot reach are
exactly those where observable consistency ≠ goal (intent-local) — this is RQ3.

---

## The three monitor configurations (what we compare)

All are black-box, monitor-only; they share ONE claim extraction per trajectory (fixed extractor
model) and differ only in which observation channel the verifier uses (this intra-run reuse is not
the rejected freeze-as-evidence; it just avoids re-extracting):

- **V_answer** (baseline, RQ1): verify claims using the answer + conversation only (answer-local).
- **V_structural** (RQ2): V_answer + state channel (claims vs `env.data` after) + trace channel
  (`env.actions` vs `wiki.md` policy/preconditions) + post-state-change assertion (tool reported
  success but state unchanged).
- **V_evidence** (RQ2 extension, banking_knowledge only): V_answer + re-retrieve from the KB and
  check claims against retrieved documents (evidence-local, source-available case).

**Answer-local input (channel hygiene, decided Phase 1).** The text fed to the extractor for the
answer-local channel is the **concatenation of all the agent's natural-language `respond` turns**
(everything it told the user across the conversation), NOT just the last message (a chatty closer is
claim-poor — verified on a real retail trajectory: 1 weak claim) and **NOT the tool calls** (those are
the trace channel). Mixing tool calls into the answer-local extraction would let V_answer read the
trace channel and collapse the RQ1-vs-RQ2 contrast. So: answer = what the agent *said* (V_answer);
`tool_trace` = what it *did* (V_structural); `state_after` = the realized effect (V_structural). An
agent that does the right action but says nothing → few answer-local claims → the RQ1 ceiling.

Gold label for every task = τ-bench reward (1 pass / 0 fail). Detection = monitor non-PASS on a
reward-0 task; false alarm = monitor non-PASS on a reward-1 task.

## Locus assignment for each failure (the analysis lens, not the ground truth)

Correctness is always τ-bench's reward. For each reward-0 task we add a **locus tag**, preferring
τ-bench's native fault type where present, else a documented rule-based classifier:

- **answer-local**: claim self-inconsistent / impossible on its face.
- **trace-local**: an `env.actions` step violates a `wiki.md` rule/precondition.
- **state-local**: `env.data` after diverges from the claimed effect (e.g. "cancelled" but status≠cancelled).
- **intent-local**: claim is self-consistent AND state matches the claim, yet reward=0 (valid action,
  wrong goal). **Identify it INDEPENDENTLY** from τ-bench's native fault types (e.g.
  `used_wrong_tool` / `goal_partially_completed`), NOT merely as "what V_structural missed" — then
  show the monitor's residual *coincides* with this independently-tagged class. (Defining
  intent-local as the residual and then concluding the monitor misses intent-local would be
  circular; the RQ3 boundary claim requires the independent tag.)
- **evidence-local**: claim unsupported by the KB documents (banking_knowledge).

---

## Statistical design (advisor's single-seed multi-LLM, done correctly)

- **Single seed** (42), sent to the API. (Honest caveat: at temp 0 the provider is still
  non-deterministic — the seed barely controls variance; repeats below carry the noise estimate.)
- **4 base agent models** (the audited models), locked Phase 0 (2026-06-10) — a 2x2 capability
  spread across 4 mainland vendors; see the **Locked configuration** section below for exact IDs.
  **Monitor extractor model fixed** and **user-simulator model fixed** (`minimax/minimax-m3`) across
  all runs (two controls, so only the audited agent varies).
- **K = 10 repeats** per (domain, model) to estimate run-to-run noise.
- Three statistics, each at the right level:
  1. **Significance → per-task paired McNemar test** (V_answer vs V_structural) within each model,
     plus bootstrap CIs over tasks. Hundreds of paired tasks → high power on a single model/seed.
  2. **Generality → cross-model distribution** (mean±std, p25/p75) → the box/violin money chart.
     (4 model points carry generality, NOT significance — do not claim significance from 4 points.)
  3. **Noise → within-model std across the K repeats** → shows cross-model separation > repeat jitter.

---

## RQ → experiment mapping

- **RQ1** (answer-only ceiling): V_answer detection / precision / FAR on τ-bench, broken out by
  locus; expectation = catches answer-local, near-blind on trace/state/intent. Ceiling argument:
  a small extraction-quality spot-check (precision on a sample of trajectories) shows the blind spot
  is a channel limit, not extraction failure.
- **RQ2** (trace/state recovery + robustness): V_structural vs V_answer detection lift by locus,
  FAR unchanged; significance by McNemar; **robustness across the 4 models** (box chart); evidence
  channel (banking_knowledge) extends the recovery to source-available evidence-local.
- **RQ3** (boundary): the residual reward-0 tasks V_structural still misses ≈ intent-local (+ any
  source-unavailable evidence-local); show the monitor saturates and the gap to the τ-bench oracle
  reward is exactly the intent-local class (truth not in any observable artifact).

---

## Execution steps (detailed)

### Phase 0 — Environment & data setup

1. `git clone https://github.com/sierra-research/tau-bench` (and check tau2/tau3 branches for
   telecom + banking_knowledge). Create a Python venv; `pip install -e .` (pulls litellm).
2. Set `OPENROUTER_API_KEY`; point τ-bench's LiteLLM backend at OpenRouter. Resolve and **lock the
   exact OpenRouter model IDs** for DeepSeek / GLM / MiMo / Qwen; smoke-run one retail task per model
   to confirm each drives the agent end-to-end.
3. The domain DBs + task suites ship with the repo — verify they load; **record task counts per
   domain** (retail/airline/telecom/banking_knowledge). Pick the user-simulator model and fix it.
4. Confirm capture: `env.actions`, `env.data` (initial via `data_load_func()`, final snapshot
   **before** `calculate_reward()` since it reloads `env.data` to ground truth), `reward`, native
   fault type.
5. **Domain scope decision:** core = retail + airline; stretch (for full locus coverage) = telecom
   + banking_knowledge (banking_knowledge supplies evidence-local). If banking_knowledge (newest) is
   unstable, evidence-local stays conceptual and intent-local carries RQ3.
   Deliverable: feasibility note + locked model IDs + domain/task scope + time estimate.

### Phase 1 — Repo refactor

6. Remove `src/domain/ecommerce`, `src/domain/reference`, `tasks/*scenarios*.json`,
   `tier_b_prompts.json`, F0–F5 injection, Set A/B generators + results.
7. Keep `src/reliableguard/pipeline.py`, extractor, classifier, scorer, `schema.py` verdicts,
   `eval/metrics.py`. (The old `structural_audit.py` was deleted in the pivot; its pre/post
   state-change pattern is re-implemented in the Phase 2 trace verifier, not kept as a file.)
8. Add a benchmark-adapter interface — a `Trajectory` record
   `{task_id, domain, model, repeat, seed, query, final_answer, answer_text, tool_trace,
   state_before, state_after, gold_reward, native_fault, status}` — and make `verify_claims` dispatch
   take grounding from the adapter via `VerificationContext` (so they are benchmark-pluggable).
   (`answer_text` = concatenated agent respond turns = the answer-local input; `status` = ok|error.)

### Phase 2 — τ-bench integration

9. **Adapter:** wrap the τ-bench runner to emit one `Trajectory` (JSONL, streaming, resumable) per
   (task, model, repeat); correct snapshot order.
10. **τ-bench state verifier** (state-local): check claimed entities/effects against `state_after`.
11. **Structural / trace port** (trace-local): encode the `wiki.md` rules as checks over
    `tool_trace` (cancel only pending; auth before action; confirm before write; no modify-then-
    cancel; returns/exchanges only on delivered; etc.); plus the post-state-change assertion.
    DONE (`verify_trace(context, *, domain)`, trajectory-level → `list[TraceViolation]`;
    `trace_verdict` = BLOCK on any violation; trajectory verdict = `max(claim verdict,
    trace_verdict)`). Domain-dispatched: retail rules = `auth_before_action`,
    `status_precondition` (cancel/modify→pending, return/exchange→delivered via `state_before`),
    `called_twice` (modify-items / exchange once per order), `modify_after_freeze`, `multi_user`.
    Airline rules = `auth_before_action`, `basic_economy_no_flight_modify`,
    `baggage_only_increase`. **Deliberately NOT encoded for either domain:** *confirm-before-write*
    and the strict *post-state-change assertion* — both need per-tool observations / user turns
    (not in `tool_trace`). Realized-effect side covered by state channel (step 10). See
    architecture.md "Structural-audit pattern (ported)".
12. **Evidence channel** (banking_knowledge): re-retrieve from the KB and check claims vs documents.
13. **Locus annotator:** native fault type → locus, else the rule-based classifier above; emit a
    locus tag per failure. Unit-test on a few hand-traced tasks.
    DONE (`src/reliableguard/locus.py`). tau-bench `RewardResult` has no structured fault type
    (only `reward` 0/1 + `r_actions` fraction), so `native_fault=None` always; annotator is
    purely rule-based with `override` for manual annotation studies. Priority: pass > trace-local
    (verify_trace violations) > state-local (state-channel contradictions, source="tau_bench_state")
    > intent-local (residual; working label — requires independent spot-check before RQ3 claims).
    Helpers: `locus_is_monitor_detectable` (trace/state/evidence/answer), `locus_needs_structural`
    (trace/state only; these are the two loci that drive the V_structural vs V_answer lift in RQ2).

### Phase 3 — Main experiment run (RQ1 + RQ2)

14. **Agent runs:** domains × 4 models × K=10 repeats × all in-scope tasks via the τ-bench runner →
    capture trajectories (the expensive, parallelizable step; shard like the old record harness).
15. **Monitor pass** (cheap, zero extra agent cost): per trajectory, 1 extraction (fixed extractor)
    → apply V_answer, V_structural (+ V_evidence for banking_knowledge) → record reward, locus,
    each config's verdict.

### Phase 4 — Metrics & statistics

16. Per (model, domain): detection / precision / FAR for V_answer and V_structural, + per-locus
    breakdown.
17. **McNemar** per-task (V_answer vs V_structural) within each model; **bootstrap CIs** over tasks.
18. **Cross-model** mean±std + p25/p75; **within-model** std across K repeats.
19. **RQ3:** quantify the intent-local residual (reward=0 ∧ no inconsistency found); show the
    monitor-vs-oracle gap = intent-local share.

### Phase 5 — Figures & demo (per RQ)

20. RQ1: V_answer detection-by-locus bar (high answer-local, ≈0 trace/state).
21. RQ2: cross-model box/violin V_answer vs V_structural (money chart) + per-locus lift table +
    McNemar p-values + FAR-unchanged panel.
22. RQ3: stacked detected-vs-undetected by locus with intent-local as the irreducible residual;
    oracle-vs-monitor gap.
23. **Live demo:** one retail task where V_structural BLOCKs (e.g. "cancelled" but state unchanged,
    or cancelled a non-pending order) while V_answer PASSes; pre-record a fallback.

### Phase 6 — Thesis rewrite & records

24. Rewrite RQ1/2/3 grounded on τ-bench; remove Set A/B chapters + F0–F5; locus error-analysis
    replaces injection; raise figure/formula/table density.
25. Update CLAUDE.md + memory (τ-bench re-grounding, self-made data dropped, statistical design).

---

## Self-review — logic holes / gaps checked

1. **Does V_answer have anything to verify against?** It checks self-consistency + answer/
   conversation-checkable claims. τ-bench failures may be dominated by trace/state/intent with few
   pure answer-local cases → V_answer detection may be near-zero across the board. This is the
   honest, expected RQ1 result (answer-only is structurally limited); the extraction spot-check
   (step RQ1) keeps it from being read as a weak extractor. Watch: confirm a non-trivial answer-local
   count exists for a positive RQ1 data point; if not, frame RQ1 as the ceiling = answer-local only.
2. **User-simulator is itself an LLM (extra nondeterminism).** Mitigated: fix the user-sim model
   across all runs (control); the K repeats absorb its variance.
3. **Cost/time of the matrix.** retail+airline ×4 models ×5 repeats ≈ thousands of multi-turn runs
   (~1–2 days parallelized). Mitigation: core = retail+airline; telecom/banking_knowledge are
   stretch; shard + resume the capture.
4. **Locus annotation could be contested.** Mitigated: prefer τ-bench native fault types; document
   the rule-based mapping; hand-validate a sample. Correctness label is never the locus tag.
5. **Significance vs sample size.** 4 models is too few for significance → significance comes from
   per-task McNemar (hundreds of pairs); models carry only generality. Explicitly separated.
6. **banking_knowledge maturity.** It is the newest (tau3); if unstable, drop evidence-local to
   conceptual and let intent-local carry RQ3 — RQ1/RQ2 unaffected (they live on retail/airline).
7. **Circularity.** Monitor must never read `r_actions`; snapshot final state before
   `calculate_reward()`. Stated and enforced in the adapter.
8. **RQ3 operationalization.** intent-local = reward=0 ∧ V_structural finds no inconsistency — sound
   because if the task failed yet everything observable is consistent, the fault lives in the
   unobservable goal/intent (or unavailable evidence). Documented.
9. **"Schema" (old F1) under-covered.** Accepted by user (low impact); trace-local carried by
   policy + dependency, which are richer in τ-bench.
10. **Extractor reuse across configs** is intra-run, not the rejected freeze-as-evidence — noted.

## Locked configuration (Phase 0, 2026-06-10)

Backend: OpenRouter via LiteLLM (`--model-provider openrouter`; the model ID is the full OpenRouter
slug). **OpenAI models are NOT reachable on this account** (403 "violation of provider Terms Of
Service"), so the user-simulator cannot be gpt-4o — it is a mainland model (below).

Audited agent models (4 vendors, 2 flagship + 2 low-end spread), all verified `tools=True`:

| Model ID | Vendor | Tier | $/1M in/out | ctx |
| --- | --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | DeepSeek (baseline) | flagship | 0.435 / 0.87 | 1M |
| `xiaomi/mimo-v2.5-pro` | Xiaomi | flagship | 0.435 / 0.87 | 1M |
| `z-ai/glm-4.7-flash` | Zhipu | low-end | 0.06 / 0.40 | 203K |
| `qwen/qwen3.6-flash` | Alibaba | low-end | 0.1875 / 1.125 | 1M |

User-simulator (fixed control): `minimax/minimax-m3` (0.30 / 1.20, 1M) — non-audited vendor (no
cross-model coupling with the audited set), reachable, emits clean text. Extractor model (fixed
control): **also `minimax/minimax-m3` with reasoning DISABLED** (`reasoning:{enabled:false}`, locked
Phase 1) — extraction is structured parsing, and the model's reasoning tokens are unbounded and
truncated even at `max_tokens=8192` on some trajectories; disabling reasoning makes the output bounded
(~2168 tok) with no claim-count loss. Reused for consistency and to keep both controls off the audited
vendor set. The two controls share a model but operate in disjoint roles (conversation-time user-sim
vs. post-hoc claim extraction) with no information sharing, so this introduces no confound. The
answer-local input fed to the extractor is the agent's concatenated `respond` turns (see above).

Domain scope: core = retail (115 test tasks) + airline (50 test tasks) = **165 tasks/repeat**.
`sierra-research/tau-bench` main ships only retail + airline; telecom + banking_knowledge live in the
separate `tau2-bench` repo (stretch, supplies evidence-local). Seed 42. K = 10.

Budget (Phase 0 smoke-calibrated, real OpenRouter spend; all 11 smoke/calib tasks passed with valid
tool calls, concurrency 5 verified clean):

| Model | $/task (retail / airline) | full-matrix (K=10) | data |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | 0.080 / 0.072 | **$128** | firm (n=8) |
| `qwen/qwen3.6-flash` | 0.029 | ~$47 | n=1 |
| `xiaomi/mimo-v2.5-pro` | 0.011 | ~$18 | n=1 |
| `z-ai/glm-4.7-flash` | 0.0029 | ~$5 | n=1 |
| user-sim + extractor (`minimax-m3`) | — | ~$15 | extractor reasoning ≈ $13 |

Total ≈ **$213** (airline/retail cost ratio measured 0.92). Cost driver = `deepseek-v4-pro` (63%),
because it is a reasoning model and the agent re-sends full history + the ~2.4-2.9k-token tool
schemas every step (~80k input tok/task); output is small (per-call ≤1259 tok), so caps don't reduce
cost. Wall-clock: the two reasoning flagships are slow (raw 170-220 s/task); concurrency 5 is verified
safe, can ramp to 20-30 — expect ~4-8 h depending on achieved concurrency, less if models run in
parallel. **Run-harness correctness/robustness spec (snapshot order, shard+resume, retry vs. spurious
failure, max_tokens caps) is in [architecture.md](architecture.md) → "Run-harness correctness &
robustness"; it is a Phase 2 prerequisite.**

## Open items (still pending)

- Extractor model ID (set in Phase 1) + grounding-injection design (see architecture.md).
- Intent-local independent annotation source.
- banking_knowledge usability for the evidence channel (stretch / tau2-bench).
