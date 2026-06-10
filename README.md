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

The evaluation is grounded on **τ-bench** (`sierra-research/tau-bench`), a recognized tool-agent
benchmark whose ground truth is execution-based (final database state vs an annotated goal). τ-bench
is the environment and the gold-truth oracle, not a competing method: ReliableGuard is the monitor
under study and reads only deployment-observable artifacts (final answer, `env.actions`, `env.data`
before/after), never the goal annotation, so the comparison is non-circular.

The monitor runs in three configurations that differ only in the verifier's observation channel:

| Config | Channels | Serves |
| --- | --- | --- |
| `V_answer` | answer / conversation only | RQ1 baseline (answer-local) |
| `V_structural` | + state (`env.data`) + trace (`env.actions` vs `wiki.md` policy) + post-state-change assertion | RQ2 (trace/state recovery) |
| `V_evidence` | + re-retrieval from a knowledge base (banking_knowledge) | RQ2 extension (evidence-local) |

Research questions: **RQ1** answer-only ceiling; **RQ2** (primary) trace/state recovery, robust
across base models; **RQ3** the intent-local boundary.

The statistical design uses one seed, four audited base agent models (with the monitor extractor and
the τ-bench user-simulator fixed as controls) and K repeats, with significance from per-task paired
McNemar tests, generality from the cross-model distribution, and noise from within-model variance.

## Project Structure

```text
src/
  reliableguard/   # the monitor: claim extraction, verification, scoring, intervention, trace
    pipeline.py    # run_reliability_pipeline(domain, query, agent_answer, ...)
    schema.py classifier/ extractor/ scorer/ intervention/ trace/ verifier/
  config/          # RuntimeConfig
eval/
  metrics.py       # RDR / FAR / distribution metrics (McNemar / bootstrap added in Phase 4)
docs/
  tau_bench_experiment_design.md  # authoritative experiment design
  thesis_scope.md formal_definitions.md related_work_skeleton.md
  thesis/          # the written thesis
tasks/papers/      # PDFs of cited papers
tests/             # pytest
requirements.txt
CHANGELOG.md
```

The τ-bench adapter, the state/trace/evidence verifiers, the locus annotator, and the multi-LLM
run/monitor drivers are added during the experiment phases described in the design doc.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=your_key_here
```

τ-bench is installed separately from its own repository (it bundles its datasets):

```bash
git clone https://github.com/sierra-research/tau-bench
pip install -e ./tau-bench
```

The reusable monitor core is invoked via `run_reliability_pipeline(...)` in
[src/reliableguard/pipeline.py](src/reliableguard/pipeline.py).
