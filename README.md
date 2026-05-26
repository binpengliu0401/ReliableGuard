# ReliableGuard

A LangGraph-based runtime verification harness for tool-using LLM agents. It audits agent answers post-hoc using domain evidence — without modifying the underlying model.

## Overview

ReliableGuard runs tool-using LLM agents and audits their outputs through a 6-stage reliability pipeline: claim extraction → verifiability classification → domain verification → risk scoring → intervention decision → report generation.

Two domains are supported:

- **Ecommerce**: SQLite-backed order state with tool trace and policy checks.
- **Reference**: DOI/PDF-backed academic citation verification.

Ablation versions compare baseline execution, audit-only detection, and enforced PASS/WARN/BLOCK intervention.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=your_key_here
```

Run the full ablation:

```bash
python3 scripts/run_ablation.py \
  --set both \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --timestamped-output
```

Output is written to `results/` (gitignored). Use `--timestamped-output` to avoid overwriting previous runs; pass `--overwrite` only for scratch diagnostics.

## Ablation Versions

| Key | `use_verifier` | `enforce_intervention` | Purpose |
| --- | --- | --- | --- |
| `V1_Baseline` | False | False | Agent-only baseline |
| `V2_AuditOnly` | True | False | Audit without enforcement |
| `V3_Intervention` | True | True | Audit with PASS/WARN/BLOCK gate |
| `V3_NoStructural` | True | True | V3 without structural audit (RQ3 ablation) |

## Running Evaluations

```bash
# Set A — known failure modes (F0–F5)
python3 scripts/run_ablation.py --set A --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output

# Set B — generalization stress test
python3 scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output

# RQ3 — structural audit ablation (ecommerce only)
python3 scripts/run_ablation.py --set A --versions V3_NoStructural --seeds 42 123 7 --domain ecommerce --timestamped-output
```

Convenience shell scripts:

```bash
./scripts/run_set_a_full.sh
./scripts/run_set_b_full.sh
./scripts/run_rq3_ablation.sh
```

Each run writes `summary.txt`, `*_metrics.json`, and `*_rows.csv` to the output directory.

## Generating Figures

```bash
python3 scripts/generate_figures.py
```

Reads the latest timestamped results under `results/set_a_full/`, `results/set_b_full/`, and `results/rq3_ablation/`. Writes Figure 1–4 and three LaTeX tables to `figures/`.

## Project Structure

```text
src/
  agent/           # LangGraph agent runtime
  graph/           # Graph state, nodes, and routing
  reliableguard/   # Claim extraction, verification, scoring, intervention
  domain/          # Ecommerce and reference domain tools and verifiers
  db/              # Database initialization helpers
  config/          # Runtime configuration (RuntimeConfig dataclass)
eval/
  ablation_runner.py # Per-version scenario runner; ExperimentAbort on infra errors
  metrics.py         # Aggregate metrics and summary statistics
  benchmark.py       # Lower-level entry point (use scripts/run_ablation.py for thesis runs)
scripts/
  run_ablation.py              # Primary benchmark entry point (Set A / Set B)
  run_full_experiment_sequence.sh  # Runs Set A → Set B → RQ3 → figures in sequence
  run_set_a_full.sh / run_set_b_full.sh / run_rq3_ablation.sh
  generate_figures.py          # Produces thesis figures and LaTeX tables
tasks/             # Scenario files (ecommerce and reference)
tests/             # Pytest unit tests
ReliableGuard.py   # Single-run CLI entry point
requirements.txt   # Python dependencies
```
