# ReliableGuard

A black-box, monitor-only runtime auditing harness for tool-using LLM agents. It audits an agent's
answers, tool traces, and environment state post-hoc, without modifying, fine-tuning, or re-prompting
the underlying model.

## Overview

ReliableGuard audits a tool-using agent's outputs through a 6-stage reliability pipeline: claim
extraction → verifiability classification → verification → risk scoring → intervention decision
(PASS / WARN / BLOCK / AUDIT_FAILED) → traceable report.

Conceptually, the project studies black-box agent auditing as an **observability problem**: an
agent's final answer is only a partial, self-reported observation of its execution, so a failure is
detectable **iff the monitor has an observation channel that reaches the locus of its ground truth**:

- **answer-local** — checkable from the answer itself
- **trace-local** — a policy / precondition violation in the tool calls
- **state-local** — a claimed effect not realized in the environment state
- **evidence-local** — in an external source (source-available is recoverable; source-unavailable is a boundary)
- **intent-local** — a valid action that is not what the user wanted (the irreducible black-box boundary)

See [docs/thesis_scope.md](docs/thesis_scope.md) for the full framing and
[docs/tau_bench_experiment_design.md](docs/tau_bench_experiment_design.md) for the experiment design.

## Evaluation on τ-bench

The evaluation is grounded on **τ²-bench** (`sierra-research/tau2-bench` v1.0.0), a recognized
tool-agent benchmark whose ground truth is execution-based (final database state vs an annotated
goal). Formal domains: **retail (114 tasks) + airline (50 tasks) = 164 tasks/repeat**. τ²-bench
is the environment and the gold-truth oracle, not a competing method: ReliableGuard is the monitor
under study and reads only deployment-observable artifacts (final answer, `env.actions`, `env.data`
before/after), never the goal annotation, so the comparison is non-circular.

The monitor runs in two configurations that differ only in the verifier's observation channel:

| Config | Channels | Serves |
| --- | --- | --- |
| `V_answer` | answer / conversation only (incl. answer-completeness) | RQ1 baseline (answer-local) |
| `V_structural` | + state (`env.data`) + trace (`env.actions` vs `wiki.md` policy + agent-loop guard) + post-state-change assertion | RQ2 (trace/state recovery) |

(An evidence channel `V_evidence` was designed for `banking_knowledge`, but that domain is
action-centric — `communicate_info=[]` for all tasks — so it is out of the formal experiment and
documented as Future Work. Evidence-local is therefore excluded from the formal taxonomy.)

Research questions: **RQ1** answer-only ceiling; **RQ2** (primary) trace/state recovery, robust
across base models; **RQ3** the intent-local boundary.

The statistical design uses **unseeded K = 10 repeats** (at temperature 0 a fixed seed does not
control provider non-determinism, so the repeats absorb run-to-run variance), four audited base
agent models (with the monitor extractor and the τ²-bench user-simulator fixed as controls), with
significance from per-task paired McNemar tests, generality from the cross-model distribution, and
noise from within-model variance. Headline rates carry 95% CIs (Clopper-Pearson exact at the 0/1
boundary, bootstrap otherwise).

## Project Structure

```text
src/
  reliableguard/   # the monitor: claim extraction, verification, scoring, intervention, trace
    pipeline.py    # run_reliability_pipeline(domain, query, agent_answer, ...)
    schema.py classifier/ extractor/ scorer/ intervention/ trace/ verifier/
  config/          # RuntimeConfig
eval/
  run_capture_tau2.py  # CLI: agent × domain × repeat matrix → results/capture/*.jsonl
  capture_tau2.py      # tau2-bench capture driver (from tau2.runner import ...)
  monitor_pass.py      # extract → V_answer + V_structural → locus → results/monitor/*.jsonl
  reannotate_signals.py# deterministic overlay (loop + completeness + state-framing) → results/monitor_v2
  analyze.py           # RDR / FAR / McNemar / locus + CIs (bootstrap, Clopper-Pearson at boundary) → metrics + figures
docs/
  tau_bench_experiment_design.md  # authoritative experiment design
  thesis_scope.md formal_definitions.md related_work_skeleton.md architecture.md
  thesis/          # the written thesis (gitignored — see "Data" below)
tasks/papers/      # PDFs of cited papers
tests/             # pytest
requirements.txt
CHANGELOG.md
```

The τ²-bench adapter, the state/trace verifiers, the locus annotator, and the multi-LLM
run/monitor drivers live under `src/reliableguard/` and `eval/` (see `docs/architecture.md`).

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=your_key_here
```

τ²-bench is installed separately from its own repository (it bundles its task suites, databases,
and `wiki.md` policies — no separate dataset download is required):

```bash
git clone https://github.com/sierra-research/tau2-bench
pip install -e ./tau2-bench        # provides the `tau2` package the capture driver imports
```

The reusable monitor core is invoked via `run_reliability_pipeline(...)` in
[src/reliableguard/pipeline.py](src/reliableguard/pipeline.py) — pass it your own answer / tool
trace / state and it returns a verdict, no benchmark required.

## Data

**Cloning this repository does not give you any data.** Both the benchmark inputs and the captured
trajectories live outside git:

- **Benchmark data** (tasks, DBs, policies) ships *inside* `tau2-bench` and is reached through the
  `tau2` package — install it as above; nothing else to download.
- **Captured trajectories and results** (`results/capture/`, `results/monitor*/`, `results/metrics*/`,
  `results/figures*/`) and the **written thesis** (`docs/thesis/`) are **gitignored** (large /
  binary / reproducible), so a fresh clone has none of them.

To regenerate the results end-to-end (needs `OPENROUTER_API_KEY`; the agent runs are the expensive,
~hours/$ part):

```bash
# 1. capture: run the agent × domain × repeat matrix  → results/capture/*.jsonl
python -m eval.run_capture_tau2 --domain retail airline \
    --models deepseek/deepseek-v4-pro xiaomi/mimo-v2.5-pro z-ai/glm-4.7-flash qwen/qwen3.6-flash \
    --repeats 10 --workers 4

# 2. monitor pass: extract + V_answer/V_structural verdicts  → results/monitor/*.jsonl
python -m eval.monitor_pass --capture-dir results/capture --out-dir results/monitor

# 3. signal overlay (loop + completeness + state-framing fix) → results/monitor_v2/*.jsonl
python -m eval.reannotate_signals --monitor-dir results/monitor --capture-dir results/capture \
    --out-dir results/monitor_v2

# 4. metrics + figures (the reported set)
python -m eval.analyze --monitor-dir results/monitor_v2 \
    --out-dir results/metrics_v2 --figures-dir results/figures_v2
```

A cheap smoke test: add `--tasks 0 1 2 3 4 --repeats 1` to step 1. Capture is resumable — re-running
skips rows already marked `ok`.
