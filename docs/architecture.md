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
    extractor/          # claim_extractor.py (LLM, OpenAI client → OpenRouter), prompts.py
    classifier/         # verifiability_classifier.py, taxonomy.py
    verifier/           # source_verifier.py (verifier registry; benchmark verifiers register here)
    scorer/             # risk_scorer.py
    intervention/       # policy_engine.py → PASS / WARN / BLOCK / AUDIT_FAILED
    trace/              # trace_logger.py, report_generator.py, artifacts.py
  config/runtime_config.py   # RuntimeConfig dataclass (verifier / channel flags)
eval/
  metrics.py            # RDR / FAR / distribution metrics (McNemar / bootstrap added in Phase 4)
```

To be added in Phases 1–2: a benchmark-adapter (the `Trajectory` record), the τ-bench adapter, the
τ-bench state/trace/evidence verifiers (registered in `source_verifier`), the locus annotator, and
the multi-LLM run + monitor drivers.

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

`src/reliableguard/verifier/source_verifier.py` holds `verify_claims(domain, claims, verifiability)`
and a `_VERIFIERS` registry keyed by domain. Each registered verifier judges the claim-set jointly
(not claim-by-claim) against that benchmark's observable artifacts and returns
`{claim_id: VerificationResult}`. Unregistered domains return `unverifiable` for every claim. The
legacy self-made ecommerce + reference verifiers were removed in the 2026-06-09 pivot; the τ-bench
state / trace / evidence verifiers are registered here in Phase 2.

## τ-bench integration

- Per task τ-bench exposes: tool trace `env.actions` (list of name+kwargs), DB state `env.data`,
  gold `calculate_reward()` (uses the goal annotation `info.r_actions`).
- **The monitor reads ONLY `env.actions` + `env.data` + the final answer, never `r_actions`**
  → non-circular by construction.
- **Snapshot the agent-final `env.data` BEFORE calling `calculate_reward()`** — it reloads
  `env.data` to ground truth and would overwrite the agent-final state.
- Each domain ships an explicit policy `wiki.md` (preconditions + action-ordering). The trace channel
  encodes these rules over `env.actions`, so even the rules are the benchmark's own (not self-made).

## Benchmark-adapter interface (Phase 1)

A `Trajectory` record decouples the monitor from any one benchmark:

```text
Trajectory{ task_id, domain, model, repeat, seed, query, final_answer,
            tool_trace, state_before, state_after, gold_reward, native_fault }
```

The adapter runs an agent in the benchmark harness and emits `Trajectory` records (streaming JSONL,
resumable); the monitor pass consumes them, applies the configs, and records verdict + locus + reward.

## Structural-audit pattern (port target)

The state/trace checks follow a generic pattern: a pre-execution policy check (a condition over tool
arguments vs the policy), a post-execution state-change assertion (tool reported success but the
pre/post snapshot is unchanged), and a `snapshot_*_state()` function. This pattern is ported to
τ-bench by snapshotting `env.data` and checking `env.actions` against `wiki.md`.

## Operational conventions

- Default to deterministic, offline behavior where possible. τ-bench runs are the LLM-bound step:
  shard + stream + resume the capture.
- Trace artifacts → `logs/` (gitignored); benchmark results → `results/` (gitignored).
- Do not fabricate experiment numbers — read from result files, or state that data is pending.
- Repository content is English only (see [AGENTS.md](../AGENTS.md)).
