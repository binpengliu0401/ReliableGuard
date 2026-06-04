# ReliableGuard

A LangGraph-based runtime verification harness for tool-using LLM agents. It audits agent answers, tool traces, and domain evidence post-hoc, without modifying the underlying model.

## Overview

ReliableGuard runs tool-using LLM agents and audits their outputs through a 6-stage reliability pipeline: claim extraction → verifiability classification → domain verification → risk scoring → intervention decision → report generation.

Two domains are supported:

- **Ecommerce**: SQLite-backed order state with tool trace and policy checks.
- **Reference**: DOI/PDF-backed academic citation verification.

Ablation versions compare baseline execution, audit-only detection, and enforced PASS/WARN/BLOCK intervention.

## Latest Experiment Snapshot

The current consolidated experiment batch was run on git commit `3759744`.

| Output | Directory |
| --- | --- |
| Set A full ablation | `results/set_a_full/20260526/173346/` |
| Set B full ablation | `results/set_b_full/20260531/045635/` |
| Structural ablation (paper RQ2) | `results/rq3_ablation/20260531/073500/` |
| Final figures and LaTeX tables | `figures/` |
| Protected archive copy | `results/_archive/final_experiment_snapshot_20260602_3759744/` |
| Compressed archive | `results/_archive/final_experiment_snapshot_20260602_3759744.tar.gz` |

Key Set A results:

- Overall V3 false acceptance rate: `0.389`; risk detection rate: `0.466`.
- Ecommerce V3 risk detection rate: `0.640`; false acceptance rate: `0.231`.
- Reference V3 risk detection rate: `0.162`; false acceptance rate: `0.666`.

Structural ablation (ecommerce, paper RQ2 — directory historically named `rq3_ablation`):

- `V3_NoStructural`: risk detection `0.237`, false acceptance `0.762`.
- `V3_Intervention`: risk detection `0.640`, false acceptance `0.231`.
- F2 detection improved from `0.225` to `0.735`; F4 detection improved from `0.353` to `0.827`.

Set B remains a stress test rather than the main success claim: V3 overall false acceptance is `0.783`, with `0.178` gate action rate. Use these results to discuss generalization limits.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=your_key_here
```

Run the full ablation:

```bash
./scripts/run_full_experiment_sequence.sh
```

This runs Set A, Set B, the structural ablation, and figure generation in sequence. Output is written to `results/` and `figures/`. Use `scripts/run_ablation.py --timestamped-output` for targeted runs; pass `--overwrite` only for scratch diagnostics.

## Ablation Versions

| Key | `use_verifier` | `enforce_intervention` | Purpose |
| --- | --- | --- | --- |
| `V1_Baseline` | False | False | Agent-only baseline |
| `V2_AuditOnly` | True | False | Audit without enforcement |
| `V3_Intervention` | True | True | Audit with PASS/WARN/BLOCK gate |
| `V3_NoStructural` | True | True | V3 without structural audit (structural ablation, paper RQ2) |

## Running Evaluations

```bash
# Set A — known failure modes (F0–F5)
python3 scripts/run_ablation.py --set A --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output

# Set B — generalization stress test
python3 scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output

# Structural audit ablation (ecommerce only, paper RQ2)
python3 scripts/run_ablation.py --set A --versions V3_NoStructural --seeds 42 123 7 --domain ecommerce --timestamped-output
```

Convenience shell scripts:

```bash
./scripts/run_set_a_full.sh
./scripts/run_set_b_full.sh
./scripts/run_structural_ablation.sh
```

Each run writes `summary.txt`, `*_metrics.json`, and `*_rows.csv` to the output directory.

## Generating Figures

```bash
python3 scripts/generate_figures.py
```

Reads the latest timestamped results under `results/set_a_full/`, `results/set_b_full/`, and `results/rq3_ablation/`. Writes Figure 1–4 and three LaTeX tables to `figures/`.

Current generated artifacts:

- `figures/fig1_set_a_main.pdf`
- `figures/fig2_set_a_failure_modes.pdf`
- `figures/fig3_structural.pdf`
- `figures/fig4_set_b_generalization.pdf`
- `figures/table_main_ablation.tex`
- `figures/table_evidence_state.tex`
- `figures/table_latency.tex`

## Project Structure

```text
src/
  graph/           # Graph state, nodes, and routing
  reliableguard/   # Claim extraction, verification, scoring, intervention
  domain/          # Ecommerce and reference domain tools and verifiers
  config/          # Runtime configuration (RuntimeConfig dataclass)
eval/
  ablation_runner.py # Per-version scenario runner; ExperimentAbort on infra errors
  metrics.py         # Aggregate metrics and summary statistics
  benchmark.py       # Lower-level entry point (use scripts/run_ablation.py for thesis runs)
  annotation/        # Extractor-annotation workbook (claim P/R/F1 + coverage study)
scripts/
  run_ablation.py              # Primary benchmark entry point (Set A / Set B)
  run_full_experiment_sequence.sh  # Runs Set A → Set B → structural ablation → figures
  run_set_a_full.sh / run_set_b_full.sh / run_structural_ablation.sh
  build_extractor_annotation.py    # Builds the extractor-annotation workbook from run traces
  generate_figures.py          # Produces thesis figures and LaTeX tables
tasks/             # Scenario files (ecommerce and reference)
docs/              # Thesis documents (thesis_scope, formal_definitions, related_work)
tests/             # Pytest unit tests
ReliableGuard.py   # Single-run CLI entry point
requirements.txt   # Python dependencies
CHANGELOG.md       # Feature and change history (updated before every push)
```
