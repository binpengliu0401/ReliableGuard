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

Run the main ablation runner:

```bash
python scripts/run_ablation.py \
  --set both \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --output-dir results/ \
  --timestamped-output
```

Scenario files under `tasks/`, logs under `logs/`, and benchmark outputs under
`results/` are local experiment artifacts and are gitignored.

## Ablation Versions

| Key | `use_verifier` | `enforce_intervention` | Meaning |
| --- | --- | --- | --- |
| `V1_Baseline` | False | False | Agent-only baseline; no reliability audit or gate |
| `V2_AuditOnly` | True | False | Runs the reliability audit, but still releases the original answer |
| `V3_Intervention` | True | True | Runs the audit and enforces PASS/WARN/BLOCK intervention |

## Running Evaluations

Recommended ablation commands:

```bash
python scripts/run_ablation.py --set A --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
python scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
python scripts/run_ablation.py --set both --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
```

Reusable full-run scripts:

```bash
./scripts/run_set_a_full.sh
./scripts/run_set_b_full.sh
./scripts/run_set_a_ecommerce_full.sh
```

These scripts run all three ablation versions with seeds `42 123 7` and write
timestamped outputs under `results/set_a_full/`, `results/set_b_full/`, or
`results/set_a_ecommerce_full/`. The ecommerce-only Set A script runs the full
ecommerce suite while passing an empty reference scenario file.

Useful debugging options:

```bash
python scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 --save-states false-alarms
python scripts/run_ablation.py --set B --versions V3 --seeds 42 --debug-false-alarms
```

The runner writes `summary.txt`, per-domain metrics JSON, and per-scenario CSV
rows into the selected output directory.

The CSV rows include structured fact-audit columns for later inspection:

- `fact_snapshot`: ground-truth facts captured from the domain state after the run.
- `fact_mismatch_summary`: direct expected-vs-actual mismatches, for example `status: expected=confirmed, actual=pending`.

`eval/benchmark.py` is kept as a lower-level benchmark entry point. For thesis
tables and Set A/Set B reporting, prefer `scripts/run_ablation.py`.

## Evaluation Sets

Set A measures known failure modes (`F0`-`F5`) across ecommerce and reference
tasks. Its summary emphasizes whether each version has the reliability gate
enabled, whether known-risk tasks are detected, and whether safe tasks are
preserved:

```text
Version  gate  avg_reliability  false_acceptance_rate  risk_detection_rate  false_alarm_rate  safe_pass_rate  pass_rate (95% CI)
```

Key Set A metrics:

- `false_acceptance_rate`: high-risk expected `WARN`/`BLOCK` rows that were released as `PASS`.
- `risk_detection_rate`: expected `WARN`/`BLOCK` rows that were handled as `WARN` or `BLOCK`.
- `false_alarm_rate`: expected `PASS` rows that were gated as `WARN` or `BLOCK`.
- `safe_pass_rate`: expected `PASS` rows that were released as `PASS`.

For ecommerce Set A, V3 also includes additive structural checks for failure
modes that are not well represented as final-answer text claims:

- `F2`: block `create_order` requests where `amount > 5000` using the named
  `amount_requires_approval` policy rule.
- `F4`: detect false-success tool executions where a tool reports success but
  the ecommerce database state is unchanged. F4 fault injection is limited to
  the evaluation runner for scenarios marked `note: f4_injection`.

Set B measures generalization stress tests from `tasks/tier_b_prompts.json`.
Its summary is organized as an audit-to-gate chain:

```text
Version  gate  avg_reliability  gate_action_rate  false_acceptance_rate  false_alarm_rate  fact_acc_blocked  fact_acc_passed  pass_rate (95% CI)
```

Key Set B metrics:

- `false_acceptance_rate`: high-risk expected `WARN`/`BLOCK` rows that were released as `PASS`.
- `false_alarm_rate`: expected `PASS` rows that were gated as `WARN` or `BLOCK`.
- `gate_action_rate`: all `WARN`/`BLOCK` outcomes over all rows.
- `fact_acc_blocked`: average fact accuracy for expected `PASS` rows that were gated.
- `fact_acc_passed`: average fact accuracy for expected `PASS` rows that were released.

The intended interpretation is: V3 should reduce `false_acceptance_rate`, while
`fact_acc_blocked` and `fact_acc_passed` diagnose whether its false alarms are
concentrated on lower-quality answers.

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
  metrics.py         # Aggregate metrics and summary statistics
  fact_scorer.py     # Ground-truth fact scoring
scripts/             # Experiment runners and utility scripts
tests/               # Pytest unit tests
ReliableGuard.py     # Single-run CLI entry point
requirements.txt     # Python dependencies
```
