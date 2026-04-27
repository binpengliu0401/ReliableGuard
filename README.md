# Reliable Guard

Reliable Guard is a LangGraph-based agent benchmark framework with a post-hoc,
domain-grounded reliability audit and intervention layer.

## Overview

Reliable Guard runs tool-using LLM agents and audits their final answers after
execution. The reliability pipeline extracts factual claims, checks them against
domain evidence, scores risk, and optionally blocks unsafe answers. The project
currently supports two domains: ecommerce workflows backed by SQLite order state,
and reference/citation workflows backed by parsed reference metadata. The
ablation study compares baseline execution, audit-only detection, and enforced
intervention. OpenRouter is used through the OpenAI-compatible client.

## Quick Start

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure LLM access:

```bash
export OPENROUTER_API_KEY=your_key_here
```

Run the main benchmark:

```bash
python scripts/run_ablation.py \
  --set both \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --output-dir results/
```

Scenario files under `tasks/` are local experiment data and are gitignored.

## Ablation Versions

| Key | `use_verifier` | `enforce_intervention` | Meaning |
| --- | --- | --- | --- |
| `V1_Baseline` | False | False | Agent-only baseline; no reliability audit or gate |
| `V2_AuditOnly` | True | False | Runs the reliability audit, but still releases the original answer |
| `V3_Intervention` | True | True | Runs the audit and enforces PASS/WARN/BLOCK intervention |

`V2_NoReliability` remains available only for cross-model baseline comparison,
for example DeepSeek-vs-Qwen experiments.

## Running Evaluations

Common `eval/benchmark.py` usage:

```bash
python eval/benchmark.py --scenarios main --domain all --model qwen
python eval/benchmark.py --scenarios verifier --domain all --model qwen
python eval/benchmark.py --scenarios main --domain reference --model deepseek
```

Common `scripts/run_ablation.py` usage:

```bash
python scripts/run_ablation.py --set A --versions V1 V2 V3 --seeds 42 123 7
python scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 123 7
python scripts/run_ablation.py --set both --versions V1 V2 V3 --seeds 42 123 7
```

## Project Structure

```text
src/
  agent/             # LangGraph agent runtime
  graph/             # Graph state, nodes, and routing
  reliableguard/     # Claim extraction, verification, scoring, intervention
  domain/            # Ecommerce and reference domain tools/verifiers
  db/                # Local database initialization and reset helpers
  config/            # Runtime configuration
eval/
  config/            # Ablation version definitions
  benchmark.py       # Benchmark entry point
  ablation_runner.py # Per-version scenario runner
  metrics.py         # Aggregate metrics
  fact_scorer.py     # Ground-truth fact scoring
scripts/             # Experiment runners and utility scripts
tests/               # Pytest unit tests
ReliableGuard.py     # Single-run CLI entry point
requirements.txt     # Python dependencies
```
