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

**Benchmark source (2026-06-16 decision): tau2-bench (τ³-bench) replaces the original tau-bench.**
A systematic bug audit found that 27/50 airline tasks (54%) and 26/114 retail tasks (23%) in the
original `sierra-research/tau-bench` had incorrect gold expected actions, impossible constraints,
ambiguous user instructions, or policy-loophole tasks scored as failures despite correct agent
behaviour. Running our monitor on these tasks produces misleading RDR numbers. We adopt
`sierra-research/tau2-bench` (v1.0.0), which ships fixed retail + airline tasks. The capture driver
moves from the `tau_bench` package API to the `tau2` package API (different runner architecture; see
architecture.md). **Formal experiment scope: retail + airline.** `banking_knowledge` (tau2) was
explored in a smoke test (45 trajectories) and found structurally incompatible with the monitor's
observable channels: tau2-bench evaluates banking tasks via tool-call optimality
(reward_basis="DB"/"ACTION"), `communicate_info=[]` for all 97 tasks — the monitor cannot verify
factual correctness because the benchmark does not evaluate it. Banking is documented in the thesis
as Future Work (action-centric domains; see thesis_scope.md §6.2). Evidence-local locus is therefore
removed from the formal taxonomy (no KB in retail/airline; no evidence detection surface).

## Non-circularity (the spine's defense)

τ-bench reward needs the goal annotation `r_actions`; the monitor reads ONLY deployment-observable
artifacts (final answer + `env.actions` + `env.data` before/after) and NEVER `r_actions`. Reward and
monitor signals come from disjoint inputs → not circular. The failures the monitor cannot reach are
exactly those where observable consistency ≠ goal (intent-local) — this is RQ3.

---

## The two monitor configurations (what we compare)

All are black-box, monitor-only; they share ONE claim extraction per trajectory (fixed extractor
model) and differ only in which observation channel the verifier uses (this intra-run reuse is not
the rejected freeze-as-evidence; it just avoids re-extracting):

- **V_answer** (baseline, RQ1): verify claims using the answer + conversation only (answer-local),
  PLUS the answer-completeness check (the answer terminates on an unanswered substantive question =>
  non-completion; `verifier/answer_completeness.detect_incomplete_answer`). Completeness is a pure
  answer-text signal, so it belongs to the answer-only baseline (and lifts V_answer off the
  structural RDR≈0 floor seen in execution-grounded domains).
- **V_structural** (RQ2): V_answer + state channel (claims vs `env.data` after) + trace channel
  (`env.actions` vs `wiki.md` policy/preconditions, PLUS the domain-agnostic agent-loop guard:
  a tool call re-issued with identical kwargs >= 2x => `agent_loop` violation) + post-state-change
  assertion (tool reported success but state unchanged). Because completeness is in BOTH configs, the
  V_structural-over-V_answer lift (ΔRDR, RQ2) is attributable purely to the state + trace channels.

V_evidence (evidence channel via KB re-retrieval) was designed for banking_knowledge but is
removed from the formal experiment along with that domain. See thesis_scope.md §6.2.

**Three control-group-validated corrections (2026-06-17), all deterministic over captured artifacts:**
(1) **agent-loop guard** — repeated-identical tool call (trace channel; threshold = 2, chosen by F1/MCC
across the 4 models); (2) **answer-completeness** — terminal substantive question excluding polite
closers (answer channel, fed to both configs); (3) **retail state-framing fix** — a status word framed
as capability/negation ("cannot be cancelled", "can no longer be modified") is NOT a current-state
assertion and routes to `unverifiable` (`_is_nonstate_status_framing`, Route 2; mirrors the airline
verifier). The state fix removed ~73% of retail state-channel false alarms (it was a misparse, not a
boundary); state-local is consequently minor (~2% of failures) and the V_structural lift is now driven
mainly by the trace channel (policy + loop).

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

Note: **evidence-local** (claim unsupported by KB documents) is removed from the formal taxonomy.
No KB exists in retail/airline (zero evidence detection surface without banking_knowledge, which
is out of scope). The locus priority is: pass > trace-local > state-local > intent-local.

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
  locus; expectation = catches answer-local (incl. completeness — high precision 87–96%, RDR ~12%
  pooled), near-blind on trace/state/intent. Ceiling argument: a small extraction-quality spot-check
  (precision on a sample of trajectories) shows the blind spot is a channel limit, not extraction
  failure. Result (monitor_v2): V_answer is high-precision but structurally capped — it cannot reach
  trace/state failures.
- **RQ2** (trace/state recovery + robustness): V_structural vs V_answer detection lift by locus,
  FalseAlarmRate; significance by McNemar; **robustness across the 4 models** (box chart + MCC).
  Reported with the detector-classifier metrics (Precision / F1 / MCC, §2.3a) so the recall gain is
  not read in isolation from its false-alarm cost. Result (monitor_v2): V_structural RDR ~30% /
  false-alarm ~8% / precision 66–79%; **ΔRDR positive on all 4 models (+8 … +27, McNemar p≈0)** —
  sign-consistent generality (4 points carry generality, not significance).
- **RQ3** (boundary): the residual reward-0 tasks V_structural still misses ≈ intent-local; show the
  monitor saturates and the gap to the τ-bench oracle reward is exactly the intent-local class
  (truth not in any observable artifact). Corrected π_ℓ (monitor_v2): answer ~6% / trace ~20% /
  state ~2% / intent ~60–88%. The intent-local residual is characterized (right action on the wrong
  object, plus ambiguous queries) to support the irreducibility claim non-circularly.

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
5. **Domain scope decision:** core = **retail (114 tasks) + airline (50 tasks)** via tau2-bench;
   telecom excluded (2285 tasks — scope too large); banking_knowledge excluded (action-centric
   domain structurally incompatible with the monitor's observable channels — see thesis Future Work).
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

9. **Adapter (updated 2026-06-16):** new `eval/capture_tau2.py` using the `tau2` package API (not
   the old `tau_bench` API). The tau2 runner is fundamentally different: simulation runs as a whole
   via `build_environment` + `build_orchestrator` + `run_simulation`; there is no step-level loop.
   Key extraction points: `state_before = task.initial_state` (available pre-run); `state_after =
   env.db.model_dump()` (accessed after sim completes); `tool_trace` from `AssistantMessage.tool_calls`
   in `sim.messages`; `gold_reward = sim.reward_info.reward`. For banking_knowledge only: `evidence`
   = the list of KB documents referenced by `task.required_documents`, loaded from the domain's
   document store and passed through the `Trajectory.evidence` field into `Grounding.evidence`.
   Old `eval/capture.py` (old tau_bench API) is retired after migration; the output JSONL schema is
   unchanged (same `Trajectory` model) so the monitor pass requires no changes for retail/airline.
   JSONL streaming, resume by `(model, domain, repeat, task_id)` key, same shard discipline.
10. **τ-bench state verifier** (state-local): check claimed entities/effects against `state_after`.
11. **Structural / trace port** (trace-local): encode the `wiki.md` rules as checks over
    `tool_trace` (cancel only pending; auth before action; confirm before write; no modify-then-
    cancel; returns/exchanges only on delivered; etc.); plus the post-state-change assertion.
    DONE (`verify_trace(context, *, domain)`, trajectory-level → `list[TraceViolation]`;
    `trace_verdict` = BLOCK on any violation; trajectory verdict = `max(claim verdict,
    trace_verdict)`). Domain-dispatched:
    Retail rules = `auth_before_action`, `status_precondition` (cancel/modify→pending,
    return/exchange→delivered via `state_before`), `called_twice` (modify-items / exchange once
    per order), `modify_after_freeze`, `multi_user`.
    Airline rules = `auth_before_action`, `basic_economy_no_flight_modify`, `baggage_only_increase`.
    Banking rules = `user_info_before_log_verification` (get_user_information_* must precede
    log_verification — agent needs retrieved field values to confirm 2-of-4 identity fields),
    `auth_before_write` (log_verification must precede call_discoverable_agent_tool /
    change_user_email / give_discoverable_user_tool / apply_for_credit_card / submit_referral),
    `unlock_before_call` (unlock_discoverable_agent_tool(agent_tool_name=X) must precede
    call_discoverable_agent_tool(agent_tool_name=X)).
    **Deliberately NOT encoded for any domain:** *confirm-before-write* (needs user-turn
    observations) and the strict *post-state-change assertion*; banking-specific *2-of-4 identity
    field check* (needs the actual values the user provided — not in `tool_trace`). See
    architecture.md "Structural-audit pattern (ported)".
12. **Locus annotator:** native fault type → locus, else the rule-based classifier above; emit a
    locus tag per failure. Unit-test on a few hand-traced tasks.
    DONE (`src/reliableguard/locus.py`). tau-bench `RewardResult` has no structured fault type
    (only `reward` 0/1 + `r_actions` fraction), so `native_fault=None` always; annotator is
    purely rule-based with `override` for manual annotation studies. Priority (updated 2026-06-17):
    pass > trace-local (verify_trace violations, including `agent_loop`) > state-local (state-channel
    contradictions, source="tau_bench_state") > answer-local (`answer_incomplete`, the completeness
    signal) > intent-local (residual; working label — requires independent spot-check before RQ3
    claims). Loci are defined by which **observation channel** reaches the ground truth (per the
    observability spine): trace-local = observable in `tool_trace` (policy violation OR loop),
    answer-local = observable in the answer text (false claim OR non-completion). Helpers:
    `locus_is_monitor_detectable` (trace/state/answer), `locus_needs_structural` (now trace/state/
    answer — answer-local completeness is recovered in the V_structural pass, not by V_answer's
    claim verification alone).

### Phase 3 — Main experiment run (RQ1 + RQ2)

14. **Agent runs:** retail + airline × 4 models × K=10 repeats × all in-scope tasks via the τ2
    runner → capture trajectories (the expensive, parallelizable step; shard like the old harness).
15. **Monitor pass** (cheap, zero extra agent cost): per trajectory, 1 extraction (fixed extractor)
    → apply V_answer, V_structural → record reward, locus, each config's verdict.

### Phase 4 — Metrics & statistics

16. Per (model, domain): RDR / FalseAlarmRate + the detector-classifier metrics
    **Precision / F1 / MCC** (+ `confusion` matrix) for V_answer and V_structural, + per-locus
    breakdown. (Definitions: formal_definitions.md §2.3a. MCC is the cross-model axis.)
    DONE — emitted in `eval/analyze.py` per config.
17. **McNemar** per-task (V_answer vs V_structural) within each model; **bootstrap CIs** over tasks
    (RDR, FalseAlarmRate, Precision, ΔRDR).
18. **Cross-model** mean±std; **within-model** std across K repeats.
19. **RQ3:** quantify the intent-local residual (reward=0 ∧ no inconsistency found); show the
    monitor-vs-oracle gap = intent-local share.
    Note (2026-06-17): the two new signals (loop, completeness) + the state-framing fix are applied
    by `eval/reannotate_signals.py` as a deterministic overlay on the captured artifacts (no
    re-extraction); reported results live in `results/monitor_v2` → `results/metrics_v2`. No
    authoritative full re-run: the extractor is non-deterministic, so reproducibility is
    distributional (CIs), not point-exact; the overlay is a valid representative draw.

### Phase 5 — Figures & demo (per RQ)

20. RQ1: V_answer detection-by-locus bar (high answer-local, ≈0 trace/state). → `figure6`.
21. RQ2: cross-model box V_answer vs V_structural + ΔRDR panel (`figure7`); **detector-quality
    money chart** RDR / Precision / FalseAlarm / MCC, V_answer vs V_structural (`figure9`).
22. RQ3: stacked detected-vs-undetected by locus with intent-local as the irreducible residual;
    oracle-vs-monitor gap (`figure8`). Figures emitted by `eval/analyze.py` → `results/figures_v2`.
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
3. **Cost/time of the matrix.** retail+airline ×4 models ×10 repeats ≈ 6,560 multi-turn runs
   (~4-8 h parallelized). Mitigation: shard + resume the capture.
4. **Locus annotation could be contested.** Mitigated: prefer τ-bench native fault types; document
   the rule-based mapping; hand-validate a sample. Correctness label is never the locus tag.
5. **Significance vs sample size.** 4 models is too few for significance → significance comes from
   per-task McNemar (hundreds of pairs); models carry only generality. Explicitly separated.
6. **Circularity.** Monitor must never read `r_actions`; snapshot final state before
   `calculate_reward()`. Stated and enforced in the adapter.
7. **RQ3 operationalization.** intent-local = reward=0 ∧ V_structural finds no inconsistency — sound
   because if the task failed yet everything observable is consistent, the fault lives in the
   unobservable goal/intent. Documented.
8. **"Schema" (old F1) under-covered.** Accepted by user (low impact); trace-local carried by
   policy + dependency, which are richer in τ-bench.
9. **Extractor reuse across configs** is intra-run, not the rejected freeze-as-evidence — noted.

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

Domain scope: **retail (114 tasks) + airline (50 tasks) = 164 tasks/repeat**. Both via
`tau2-bench`; telecom excluded (2285 tasks, scope too large); banking_knowledge excluded (see
Context above). Source: `sierra-research/tau2-bench` v1.0.0. Seed 42. K = 10.
Total trajectories: 4 models × 164 tasks × 10 repeats = **6,560**.

Budget (Phase 0 calibrated on retail/airline):

| Model | $/task (retail/airline) | full-matrix (K=10, 164 tasks) | data |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | 0.080 / 0.072 | **~$126** | firm |
| `qwen/qwen3.6-flash` | 0.029 | ~$48 | n=1 |
| `xiaomi/mimo-v2.5-pro` | 0.011 | ~$18 | n=1 |
| `z-ai/glm-4.7-flash` | 0.0029 | ~$5 | n=1 |
| user-sim + extractor (`minimax-m3`) | — | ~$16 | scaled |

Total ≈ **$213**. Cost driver = `deepseek-v4-pro` (~60%). Wall-clock: ~4-8 h with concurrency 5-20.
**Run-harness correctness/robustness spec (snapshot order, shard+resume, retry vs. spurious
failure, max_tokens caps) is in [architecture.md](architecture.md) → "Run-harness correctness &
robustness"; it applies to the tau2 driver as well.**

## Open items (updated 2026-06-16)

- **Intent-local independent annotation**: the locus annotator currently uses the rule-based
  classifier (residual after trace/state checks). For RQ3 the thesis needs a spot-check showing the
  residual *coincides with* an independently-derived intent-local class. A small sample manual
  annotation is required before the RQ3 boundary claim can be stated non-circularly.
- **tau2 API probe**: verify `env.db.model_dump()` is accessible after `run_simulation()` and that
  the state schema matches what retail/airline verifiers expect. Smoke runs on 5+5 tasks confirm
  this before the full run.

### Resolved (previously open)
- ~~Extractor model ID~~ — locked: `minimax/minimax-m3` with reasoning disabled (Phase 1).
- ~~Grounding-injection design~~ — implemented: `VerificationContext` + `ChannelConfig` (Phase 1).
- ~~banking_knowledge usability~~ — resolved: promoted to core (2026-06-16); tau2-bench v1.0.0 confirmed stable.
