# ReliableGuard — Code Architecture

How the monitor is built and how it plugs into a benchmark. For *why* / experiment design / RQs /
statistics / phases see [tau_bench_experiment_design.md](tau_bench_experiment_design.md); for the
thesis framing see [thesis_scope.md](thesis_scope.md); for metric formulas see
[formal_definitions.md](formal_definitions.md).

## Repository layout

```text
src/
  reliableguard/        # the monitor (reusable, benchmark-agnostic core)
    pipeline.py         # run_reliability_pipeline(domain, query, agent_answer, ...)
    schema.py           # Pydantic models: Claim, VerificationResult, ReliabilityReport, OverallVerdict
    adapter.py          # Trajectory record (benchmark-adapter interface)
    locus.py            # annotate_locus() → answer/trace/state/evidence/intent-local
    extractor/          # claim_extractor.py (LLM, OpenAI client → OpenRouter), prompts.py
    classifier/         # verifiability_classifier.py, taxonomy.py
    verifier/           # source_verifier.py (verifier registry; tau_bench_verifiers.py registered here)
    scorer/             # risk_scorer.py
    intervention/       # policy_engine.py → PASS / WARN / BLOCK / AUDIT_FAILED
    trace/              # trace_logger.py, report_generator.py, artifacts.py
  config/runtime_config.py   # RuntimeConfig dataclass (verifier / channel flags)
eval/
  capture.py            # RETIRED — old tau_bench API capture driver (retail+airline, 6600 trajs done)
  capture_tau2.py       # PLANNED — new tau2 API capture driver (retail+airline+banking, 10480 trajs)
  run_capture_tau2.py   # PLANNED — CLI wrapper for capture_tau2
  monitor_pass.py       # monitor pipeline driver: extract → V_answer + V_structural → locus → JSONL
  analyze.py            # metrics: FAR/RDR/McNemar/bootstrap/locus-distribution → JSON + figures
  metrics.py            # RDR / FAR / distribution metrics (McNemar / bootstrap)
results/
  capture/              # per-model Trajectory JSONL shards (gitignored)
  monitor/              # per-model monitor result rows (gitignored)
  metrics/              # per-model JSON metric summaries + figures
```

## The reliability pipeline (6 stages)

Orchestrated by `src/reliableguard/pipeline.py`,
`run_reliability_pipeline(domain, query, agent_answer, *, model, base_url, claims=None, ...)`
(accepts pre-extracted `claims` to skip stage 1):

1. `extract_claims` — LLM extracts factual claims from the agent answer (neural).
2. `classify_verifiability` — taxonomy labels each claim.
3. `verify_claims` — the benchmark verifier checks the claim-set against grounding artifacts.
4. `score_risks` — per-claim risk → aggregate `reliability_score ∈ [0, 1]`.
5. `decide_interventions` — policy engine → `OverallVerdict` (PASS / WARN / BLOCK / AUDIT_FAILED).
6. `generate_report` — `ReliabilityReport` + trace JSON.

Returns a `ReliabilityReport` with `stage_latencies` and `token_usage`. Everything after stage 1 is
deterministic and symbolic; the only neural component is extraction (validated separately).

## The three monitor configurations

All are black-box, monitor-only, and share ONE claim extraction per trajectory (fixed extractor
model). They differ only in which observation channel the verifier consults:

| Config | Channels | Serves |
| --- | --- | --- |
| `V_answer` | answer / conversation only | RQ1 baseline (answer-local) |
| `V_structural` | `V_answer` + state (`env.data`) + trace (`env.actions` vs `wiki.md` policy) + post-state-change assertion | RQ2 (trace/state recovery) |
| `V_evidence` | `V_answer` + re-retrieve from a knowledge base (banking_knowledge) | RQ2 extension (evidence-local) |

Gold label = τ-bench reward (1 pass / 0 fail). Detection = monitor non-PASS on reward-0; false alarm
= monitor non-PASS on reward-1.

## Verifier registry

`src/reliableguard/verifier/source_verifier.py` holds
`verify_claims(domain, claims, verifiability, context)` and a `_VERIFIERS` registry keyed by domain.
Each registered verifier judges the claim-set jointly (not claim-by-claim) against that benchmark's
observable artifacts and returns `{claim_id: VerificationResult}`. Unregistered domains return
`unverifiable` for every claim. The legacy self-made ecommerce + reference verifiers were removed in
the 2026-06-09 pivot; the τ-bench verifiers register here in Phase 2 (`retail` and `airline` state
channels done; trace channel = the standalone `verify_trace(context, *, domain)`, below).

**Grounding injection (decision B — IMPLEMENTED).** `verify_claims` and the registered verifiers
take a `VerificationContext` (`src/reliableguard/schema.py`): `grounding` (the trajectory's
observable `state_before/after`, `tool_trace`, `evidence`) plus a `ChannelConfig` gating which
channels may be read. The three monitor configs are presets over those flags — `CHANNELS_ANSWER`,
`CHANNELS_STRUCTURAL`, `CHANNELS_EVIDENCE` — so the same claims + trajectory yield the V_answer /
V_structural / V_evidence verdicts with no re-extraction and no hidden global state. A verifier
consults a channel **only** when its flag is on (answer-only verifiers return `unverifiable` for the
state/trace channels). The `Trajectory.verification_context(channels)` adapter helper builds the
context from a captured trajectory.

**Trace channel — `verify_trace(context, *, domain)` (trajectory-level).** The state channel is
per-claim (claims vs `state_after`); the trace channel is per-**trajectory**:
`verify_trace(context, domain=...)` dispatches to domain-specific rule sets and returns a list of
`TraceViolation` (no `claim_id`; `locus="trace-local"`).
Retail rules: **auth_before_action** (write before authentication),
**status_precondition** (cancel/modify need order `pending`, return/exchange need `delivered`),
**called_twice** (`modify_pending_order_items`/`exchange_delivered_order_items` once per order),
**modify_after_freeze** (item-modified order frozen against further modify/cancel),
**multi_user** (multiple users in one conversation).
Airline rules: **auth_before_action** (write before `get_user_details`),
**basic_economy_no_flight_modify** (`update_reservation_flights` on a basic_economy reservation),
**baggage_only_increase** (`update_reservation_baggages` with new `total_baggages` < old).
Rules that need the dialogue (e.g. "obtain explicit user confirmation") are deliberately NOT encoded — `tool_trace`
carries no observations/user turns, so encoding them would only manufacture false positives; the
realized effect is covered by the state channel instead. Gated on `channels.trace`; status
preconditions additionally need `state_before` (present in the V_structural preset, which turns
state + trace on together). The structural verdict combines the two channels:
`trace_verdict(violations)` returns BLOCK on any violation, and the trajectory verdict is
`max(claim-level verdict, trace_verdict)` — a clean answer produced by a policy-violating process is
still escalated to BLOCK.

## τ-bench integration

**Current status (2026-06-16): migrating from old `tau_bench` to `tau2` package (τ³-bench).**
The old retail+airline capture (6600 trajectories) used `tau_bench`; new capture for all three
domains (retail + airline + banking_knowledge, 10480 trajectories) uses `tau2`.

**Old `tau_bench` API (capture.py — retired):**
- `from tau_bench.envs import get_env` → step-level loop
- `state_before / state_after`: deepcopy of `env.data` before the terminal `env.step()`
- `tool_trace`: `list(env.actions)` before terminal step
- `gold_reward`: returned by the terminal `env.step()`
- Non-circularity: `env.data` and `env.actions` are snapshotted BEFORE `calculate_reward()` runs
  inside the terminal step (which would reload `env.data` to ground truth and append gold actions)

**New `tau2` API (capture_tau2.py — planned):**
- `from tau2.runner import build_environment, build_orchestrator, run_simulation`
- Simulation runs as a whole: `sim = run_simulation(orchestrator)`; no step-level loop
- `state_before`: `task.initial_state` (available before run, from task metadata)
- `state_after`: `env.db.model_dump()` (accessed after sim completes)
- `tool_trace`: extract from `sim.messages` — `AssistantMessage.tool_calls` → `[{name, arguments}]`
- `answer_text`: concatenate `AssistantMessage.content` across conversation
- `gold_reward`: `sim.reward_info.reward`
- `evidence` (banking_knowledge only): KB documents for `task.required_documents`, loaded from
  the domain document store, stored as `list[{id, title, content}]` in `Trajectory.evidence`
- Both packages coexist in the same venv (different names: `tau_bench` vs `tau2`); the old retail
  + airline verifiers work unchanged against the same `state_after` DB schema.

Each domain ships an explicit policy `wiki.md` (preconditions + action-ordering). The trace channel
encodes these rules over `tool_trace`, so even the rules are the benchmark's own (not self-made).

## Benchmark-adapter interface (Phase 1, extended 2026-06-16)

A `Trajectory` record decouples the monitor from any one benchmark:

```text
Trajectory{ task_id, domain, model, repeat, seed, query, final_answer, answer_text,
            tool_trace, state_before, state_after, gold_reward, native_fault, status,
            evidence }        ← added 2026-06-16: banking_knowledge KB documents
```

`answer_text` = the answer-local channel input (concatenated agent `respond` turns); `final_answer` =
only the last respond turn (demo/reference). `status` = `ok` | `error` (an `error` trajectory is an
infra failure excluded from metrics and re-run by resume). `native_fault` stays `None` on
`tau-bench` main (no fault annotation; the locus annotator uses the rule-based classifier instead).
`evidence` = `list[{id, title, content}] | None` — KB documents for the task's `required_documents`
(banking_knowledge only; `None` for retail/airline, backward compatible).

The adapter runs an agent in the benchmark harness and emits `Trajectory` records (streaming JSONL,
resumable); the monitor pass consumes them, applies the configs, and records verdict + locus + reward.

`Grounding` (in `schema.py`) mirrors the Trajectory fields: `state_before`, `state_after`,
`tool_trace`, `evidence`. The `ChannelConfig.evidence` flag gates whether the banking verifier may
read the evidence field; it is `False` for retail/airline and `True` for banking_knowledge.

## Run-harness correctness & robustness (Phase 2 prerequisites)

Settled in Phase 0 (2026-06-10) and verified on smoke runs; **not yet implemented** — the capture
driver that wraps the τ-bench runner must honor all four before the full run.

1. **Snapshot order (correctness).** `calculate_reward()` runs INSIDE the terminal `env.step()` and
   both reloads `env.data` to ground truth and appends the gold `task.actions` to `env.actions`. So
   the driver must `deepcopy(env.data)` and `list(env.actions)` after each non-terminal step and use
   the last pre-terminal snapshot as `state_after` / `tool_trace`. Never read `env.data` /
   `env.actions` after the run (both ground-truth-polluted), and never read `task.actions` /
   `reward_info` (the gold annotation) into a `Trajectory` — that is the non-circularity guarantee.

2. **Shard + resume (idempotent, crash-safe).** Work unit / dedup key = `(model, domain, repeat,
   task_id)` (4 models × 2 domains × K=10 × 165 tasks = 6,600 trajectories). Output = append-only
   JSONL, one `Trajectory` per line, flushed per record (a crash loses at most the in-flight task).
   Shard granularity: one file per `model` minimum, optionally per `(model, repeat)` for parallel
   runs — one writer per shard file (no lock contention). Resume = on start, scan the shard, build the
   done-set of keys, run only the complement. The stock τ-bench runner does NOT resume (it writes a
   new timestamped file and re-runs the whole range), so resume is added in the driver.

3. **Retry vs. spurious failure (label integrity — the critical one).** The stock runner wraps
   `agent.solve` in try/except and records a transient API error (429 / timeout / 5xx) as
   `reward=0.0` — a real infra hiccup becomes a fake task failure that contaminates the gold label
   and the monitor's detection/FAR stats. The driver must set litellm globals (`num_retries=4`, a
   `request_timeout`) so transient errors retry with backoff (but NOT a 400 bad-request, which is a
   real error); and on retry exhaustion mark the trajectory `status=error`, EXCLUDE it from metrics,
   and let resume re-run it — never record it as reward-0.

4. **max_tokens cap + truncation alarm (anti-runaway, no truncation).** Per-call output caps: **agent
   = 4096, user-sim = 2048**. Phase 0 measured per-call output max 1259 (agent) / 489 (user-sim)
   across the two reasoning agents + the minimax-m3 user-sim with zero `finish_reason="length"`, so
   the caps give 3-4× margin and will not truncate normal operation; they only guard runaway. Cost is
   input-driven (re-sent history + tool schemas), not output, so the cap is not a cost lever. The
   driver must log `finish_reason` and ALARM on any `"length"` (a cap too low for some edge task)
   rather than silently emit a truncated tool call. `max_num_steps` stays 30 (τ-bench standard).

## Structural-audit pattern (ported)

The legacy self-made structural audit followed a generic pattern: a pre-execution policy check (a
condition over tool arguments vs the policy), a post-execution state-change assertion (tool reported
success but the pre/post snapshot is unchanged), and a `snapshot_*_state()` function. The τ-bench
port realizes it as two channels: the **pre-execution policy check** is `verify_trace` (tool-arg /
action-sequence conditions over `tool_trace` + `state_before` vs `wiki.md`), and the **realized-effect
check** is the state channel (`_check_state_retail` vs `state_after`). The *snapshot* is
`eval/capture.py` deepcopying `env.data` before the terminal reward step. **Known gap:** the strict
"tool reported success but state unchanged" assertion needs the per-tool observation strings, which
the current capture does not record (`tool_trace` is name+kwargs only); the state channel covers the
effect from the claim side instead. Enhancing capture to retain observations would let `verify_trace`
add that assertion directly — deferred unless a failure mode demands it.

## Banking knowledge verifier (planned, 2026-06-16)

`banking_knowledge_verifier` will be registered in `source_verifier._VERIFIERS["banking_knowledge"]`
alongside the existing retail and airline verifiers. It handles two claim categories differently:

**State claims** (transactional assertions: account balance, transfer amounts, fee charges):
routed to the same DB state-check logic as retail/airline — compare claimed value against
`state_after` fields.

**Policy/feature claims** (KB-policy assertions: "the annual fee for the Gold card is $X",
"there is a 30-day dispute window"):
1. **BM25 retrieval** — tokenize the claim text, score all 698 documents by keyword overlap, take
   top-k=3. No external dependency: pure Python `Counter` over `re.findall(r'\w+', ...)`.
2. **LLM judge** — call minimax-m3 with a compact prompt: claim text + retrieved document excerpts
   (≤500 chars each) → JSON response `{state: "supported"|"contradicted"|"unsupported", reason, evidence_snippet}`.
3. Map to `VerificationResult.evidence_state`: `contradicted` → locus annotator sees evidence-local.

The judge adds ~1 API call per policy claim per trajectory. Claims with `time_range` in
`_NON_CURRENT_SCOPES` are filtered by `source_verifier.verify_claims` before reaching the verifier.

**Locus annotation for evidence-local** (`src/reliableguard/locus.py`): after the state-local
check, add: if any `VerificationResult` has `evidence_state="contradicted"` and `source="banking_kb"`
→ return `"evidence-local"`. Priority order becomes: pass → trace-local → state-local →
**evidence-local** → intent-local (residual).

## Temporal-scope filter (implemented 2026-06-16)

`src/reliableguard/verifier/source_verifier.py` defines
`_NON_CURRENT_SCOPES = {"before_action", "future_plan", "during_action"}`.

`verify_claims` applies this filter before routing to any domain verifier: claims whose `time_range`
falls in this set are returned immediately as `unverifiable` with reason `"Temporal scope excluded"`.
This is an enforcement layer complementing the prompt instruction in `prompts.py` (which asks the
extractor to discard these claims). The two-layer approach is robust: even if the extractor
occasionally emits a `before_action` claim, the verifier will not contradict it against `state_after`
and produce a false alarm.

## Operational conventions

- Default to deterministic, offline behavior where possible. τ-bench runs are the LLM-bound step:
  shard + stream + resume the capture.
- Trace artifacts → `logs/` (gitignored); benchmark results → `results/` (gitignored).
- Do not fabricate experiment numbers — read from result files, or state that data is pending.
- Repository content is English only (see [AGENTS.md](../AGENTS.md)).
