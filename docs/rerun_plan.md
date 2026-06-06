# Authoritative Rerun Plan (parameter-locked, single source of truth)

This document locks every parameter for the next full experiment run and defines
the smoke -> validate -> full procedure. After this run, **all RQs read from this
single batch**; the older `set_a_full/20260526` and `rq3_ablation/20260531`
batches are superseded and must be archived.

## Why a clean rerun

The two prior "authoritative" batches are internally inconsistent: claim-level
detection on the same scenarios, same code commit, same seeds disagreed sharply
(e.g. ecommerce F4 audit detection 97.8% in `set_a_full` vs 35.3% in
`rq3_ablation`). Root causes found:

1. **Stochastic agent.** The runner hardcoded `llm_temperature=0.7`, so agent
   answers varied run-to-run; wording-dependent claim detection (F4 especially)
   swung with it. Fixed: the runner now inherits the configured temperature
   (default **0.0**).
2. **Truncation skips.** `claim_extraction_max_tokens=2048` truncated long
   reference answers / multi-claim JSON, skipping up to ~36% of reference V2
   tasks (`LLMResponseTruncatedError`). Fixed: ceilings raised (cost-free; billed
   per generated token, not per ceiling).
3. **Traces never persisted.** The ablation runner used `write_logs=False`, so
   per-claim evidence for those batches is unrecoverable. Fixed: result rows now
   carry a compact `trace_summary` (per-claim `evidence_state` + `source_mode` +
   `risk_level` + `action`), making the new batch self-contained and decomposable.

F4 is caught deterministically by the structural layer (pre/post snapshot, no
LLM); its claim-only detection being unstable is the RQ2 point, not a number to
rely on.

## Locked configuration

| Parameter | Value | Source |
| --- | --- | --- |
| Model | `deepseek/deepseek-v4-flash` | `RuntimeConfig.DEFAULT_MODEL` (VERSIONS use defaults; `with_deepseek` NOT applied) |
| Agent temperature | **0.0** | `RuntimeConfig.llm_temperature` (runner no longer overrides) |
| Claim-extraction temperature | 0.0 | `RuntimeConfig.claim_extraction_temperature` |
| Agent `max_tokens` | 4096 | `RuntimeConfig.llm_max_tokens` |
| Claim-extraction `max_tokens` | 8192 | `RuntimeConfig.claim_extraction_max_tokens` |
| Seeds | 42, 123, 7 | CLI `--seeds` |
| Versions | V1_Baseline, V2_AuditOnly, V3_Intervention, V3_NoStructural | CLI `--versions` |
| Sets | A (+ B) | CLI `--set` |
| F4 fault injection | ON | default (no `--disable-fault-injection`) |
| Structural audit | runs only when `enforce_intervention` (V3 family) | `execute_node` gate |

Version semantics (resolved): V1 = no verifier / no structural (pure agent
baseline); V2 = verifier on, no enforcement, no structural (pure claim audit);
V3_Intervention = verifier + enforcement + structural; V3_NoStructural = verifier
+ enforcement, structural off (RQ2 ablation).

## Procedure (record / replay — implemented)

Direct re-running of `run_ablation.py` per version is **not reproducible**: it
re-samples the agent for every version, and a smoke determinism check (two
identical runs) flipped ~1/3 of per-task outcomes — provider-level LLM
non-determinism that temperature 0 does not fix. The methodology therefore uses
`scripts/run_replay.py`: record the agent behaviour once, then replay every
monitor configuration on the frozen corpus with no LLM calls (`record_corpus` /
`replay_corpus` in `eval/ablation_runner.py`).

### Step 1 — Smoke the record path (cheap; validate before the full record)

```bash
python3 scripts/run_replay.py record --set A --seeds 42 \
  --ecommerce tasks/smoke_ecommerce.json \
  --reference tasks/smoke_reference.json \
  --out results/smoke/corpus.json
python3 scripts/run_replay.py replay --corpus results/smoke/corpus.json \
  --out results/smoke/replay
```

Validate from `results/smoke/corpus.json` and `results/smoke/replay/set_a_rows.csv`:

- **Error rate ~0** in the corpus (`error` fields empty) — confirms the max_tokens fix.
- **Claims + structural captured** — corpus records have non-empty `claims`; F2/F4
  ecommerce records carry `structural_issues`.
- **Paired structural** — in replay, F2/F4 rows are `BLOCK` under `V3_Intervention`
  and `PASS`/miss under `V3_NoStructural` (the only difference is structural).
- Replay is deterministic by construction (no LLM); re-replaying the same corpus is
  byte-identical.

### Step 2 — Archive the superseded batches

```bash
mkdir -p results/_archive
git mv results/set_a_full results/_archive/ 2>/dev/null || mv results/set_a_full results/_archive/
mv results/rq3_ablation results/_archive/
```

### Step 3 — Record once, then replay all versions (the authoritative run)

```bash
# (a) The only LLM cost: one agent pass over Set A. Sequential is ~13h (reference
#     is the multi-step bottleneck). Prefer the parallel, crash-safe launcher:
scripts/record_sharded.sh 4 results/corpus 42      # 4 shards -> ~3-4h, auto-merge
#   -> results/corpus/set_a_corpus.jsonl
# (sequential equivalent, resumable JSONL checkpoint:)
# python3 scripts/run_replay.py record --set A --seeds 42 --resume \
#   --out results/corpus/set_a_corpus.jsonl

# (b) Free, deterministic: audit the frozen corpus under every version.
python3 scripts/run_replay.py replay \
  --corpus results/corpus/set_a_corpus.jsonl \
  --versions V1_Baseline V2_AuditOnly V3_Intervention V3_NoStructural \
  --out results/replay/set_a
```

Sharding runs N independent processes over disjoint scenario slices, each with its
own SQLite files (`RG_DB_SUFFIX`); raise N cautiously (OpenRouter rate limits ->
error rows). Each shard streams a JSONL checkpoint and `--resume`s, so a crash only
re-does that shard's tail. For the agent-variance sensitivity panel, record a second
seed on a subset and compare verdict flip rates.

This is the single source of truth: `results/replay/set_a/set_a_rows.csv` (with
`trace_summary`) + `set_a_metrics.json`. The structural ablation (RQ2) is now a
paired contrast over identical agent behaviour.

Set B records/replays the same way (loader implemented + validated):

```bash
python3 scripts/run_replay.py record --set B --seeds 42 --resume \
  --out results/corpus/set_b_corpus.jsonl
python3 scripts/run_replay.py replay --corpus results/corpus/set_b_corpus.jsonl \
  --set B --out results/replay/set_b      # -> set_b_rows.csv / set_b_metrics.json
```

### Harness validation status (2026-06-06, isolated `RG_DB_SUFFIX=devtest`)

Before committing the full record, the record/replay path was functionally
validated end-to-end on isolated DB files (real `ecommerce.db`/`references.db`
untouched): `pytest` 44 green; tiny real record streams JSONL with claims +
structural captured (0 errors); `--resume` skips completed `(id, seed)` pairs
with no LLM calls; two parallel shard processes use disjoint DBs over disjoint
scenario slices and `merge` concatenates them; split -> merge -> replay is
byte-identical to single-file replay; the paired structural ablation isolates
(F2 -> `V3_Intervention` BLOCK vs `V3_NoStructural` PASS); `Set B` record/replay
emits `set_b_*`; T5 produces `PASS_UNCHECKED` on a low-coverage replay
(collapsing to `PASS` for FAR/RDR); T8 `eval_policy_violation.py` renders the
naive x policy-aware 2x2 from frozen `tool_trace`.

### Step 4 — Analysis (all from the one replayed batch)

```bash
RUN=results/replay/set_a/set_a_rows.csv
python3 scripts/eval_rq1_audit.py --version V2_AuditOnly $RUN      # RQ1 audit-by-stratum
python3 scripts/decompose_failures.py --version V2_AuditOnly $RUN  # RQ3/T4 bottleneck
python3 scripts/eval_extractor.py                                  # RQ1 coverage ceiling (T3, separate)
```

T8 (policy-aware F2 experiment) is a deliberately separate second batch and does
not block this run. It records the adversarial F2 file twice (with and without
the approval policy in the agent prompt), then tabulates violations from the
frozen `tool_trace`:

```bash
python3 scripts/run_replay.py record --domain ecommerce \
  --ecommerce tasks/f2_policy_adversarial.json --disable-fault-injection \
  --out results/policy/corpus_naive.jsonl
python3 scripts/run_replay.py record --domain ecommerce --policy-aware \
  --ecommerce tasks/f2_policy_adversarial.json --disable-fault-injection \
  --out results/policy/corpus_pa.jsonl
python3 scripts/eval_policy_violation.py \
  --naive results/policy/corpus_naive.jsonl \
  --policy-aware results/policy/corpus_pa.jsonl
```

The evidentiary value depends on the adversarial cell: if policy-aware prompting
drives violations to zero, the structural check looks redundant; the 15
adversarial prompts exist to surface cases where the policy-aware agent still
issues the over-threshold order, which is what motivates the deterministic
structural layer.
