# Reliable Guard

Reliable Guard is a LangGraph-based agent benchmark framework with a post-hoc,
domain-grounded reliability audit and intervention layer. It is a black-box,
monitor-only system: it audits tool-using LLM agents but does not fine-tune,
optimize, or otherwise modify the underlying model.

## Overview

Reliable Guard runs tool-using LLM agents and audits their behavior after or
during execution. The reliability pipeline extracts factual claims, checks them
against domain evidence, scores risk, and optionally blocks unsafe answers. The
thesis positioning is **claim-level runtime auditing**, not general hallucination
detection.

The project currently supports two complementary deployment-style domains:

- **Ecommerce**: an industrial, state-grounded workflow backed by SQLite order
  state, tool execution traces, and high-value operation policies.
- **Academic reference**: an evidence-grounded scholarly workflow backed by DOI
  values, PDF reference lists, and bibliographic metadata.

The ablation study compares baseline execution, audit-only detection, and
enforced intervention. OpenRouter is used through the OpenAI-compatible client.

## Quick Start

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure LLM access:

```bash
export OPENROUTER_API_KEY=your_key_here
```

Run the main ablation runner:

```bash
python3 scripts/run_ablation.py \
  --set both \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --output-dir results/ \
  --timestamped-output
```

Scenario files under `tasks/`, logs under `logs/`, and benchmark outputs under
`results/` are local experiment artifacts and are gitignored.

## Ablation Versions

| Key | `use_verifier` | `enforce_intervention` | `use_structural_audit` | Meaning |
| --- | --- | --- | --- | --- |
| `V1_Baseline` | False | False | True | Agent-only baseline; no reliability audit or gate |
| `V2_AuditOnly` | True | False | True | Runs the reliability audit, but still releases the original answer |
| `V3_Intervention` | True | True | True | Runs the audit and enforces PASS/WARN/BLOCK intervention |
| `V3_NoStructural` | True | True | False | Same as V3, but disables ecommerce structural audit for RQ3 |

## Running Evaluations

Recommended ablation commands:

```bash
python3 scripts/run_ablation.py --set A --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
python3 scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
python3 scripts/run_ablation.py --set both --versions V1 V2 V3 --seeds 42 123 7 --timestamped-output
python3 scripts/run_ablation.py --set A --versions V3_NoStructural --seeds 42 123 7 --domain ecommerce --timestamped-output
```

Reusable full-run scripts:

```bash
./scripts/run_set_a_full.sh
./scripts/run_set_b_full.sh
./scripts/run_rq3_ablation.sh
./scripts/run_set_a_ecommerce_full.sh
```

The Set A and Set B full-run scripts run V1/V2/V3 with seeds `42 123 7` and
write timestamped outputs under `results/set_a_full/` and
`results/set_b_full/`. `run_rq3_ablation.sh` runs the controlled ecommerce-only
`V3_NoStructural` condition under `results/rq3_ablation/`. The ecommerce-only
Set A script is kept for focused diagnostics.

Useful debugging options:

```bash
python3 scripts/run_ablation.py --set B --versions V1 V2 V3 --seeds 42 --save-states false-alarms
python3 scripts/run_ablation.py --set B --versions V3 --seeds 42 --debug-false-alarms
```

The runner writes `summary.txt`, per-domain metrics JSON, and per-scenario CSV
rows into the selected output directory.

The CSV rows include structured fact-audit columns for later inspection:

- `fact_snapshot`: ground-truth facts captured from the domain state after the run.
- `fact_mismatch_summary`: direct expected-vs-actual mismatches, for example `status: expected=confirmed, actual=pending`.

`eval/benchmark.py` is kept as a lower-level benchmark entry point. For thesis
tables and Set A/Set B reporting, prefer `scripts/run_ablation.py`.

Additional focused runs:

```bash
./scripts/run_ecommerce_holdout.sh
python3 scripts/check_references_external.py
python3 scripts/check_papers_external.py
```

The external reference check scripts use live bibliographic sources and write
diagnostic artifacts under `results/`; they are intended for case-study
inspection rather than deterministic benchmark tables.

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
- `tccr`: task claim coverage rate; proportion of tasks with at least one
  grounded non-unverifiable claim.
- `avg_supported_count`, `avg_contradicted_count`, `avg_unsupported_count`,
  `avg_unverifiable_count`, `avg_not_found_count`: evidence-state distribution
  averages over tasks where the verifier processed at least one claim.
- `stage_latency_mean` and `stage_latency_p95`: per-stage audit latency
  summaries from `ReliabilityReport.stage_latencies`.
- `avg_tokens` and `total_tokens_sum`: positive token counts aggregated from
  result rows or `state["total_tokens"]`.

Set A scenario counts:

| Domain | Raw scenarios | Distribution |
| --- | ---: | --- |
| ecommerce | 1000 | F0=200, F1=300, F2=200, F3=150, F4=50, F5=100 |
| reference | 550 | F0=100, F1=150, F2=100, F3=100, F4=50, F5=50 |

Full Set A runs normally use three seeds (`42`, `123`, `7`), so one version
evaluates 3000 ecommerce rows and 1650 reference rows.

## Ecommerce Structural Audit and RQ3

For ecommerce Set A, `V3_Intervention` currently includes additive structural
checks for failure modes that are not well represented as final-answer text
claims:

- `F2`: block `create_order` requests where `amount > 5000` using the named
  `amount_requires_approval` policy rule.
- `F4`: detect false-success tool executions where a tool reports success but
  the ecommerce database state is unchanged. F4 fault injection is limited to
  the evaluation runner for scenarios marked `note: f4_injection`.

These checks are implemented in `src/domain/ecommerce/structural_audit.py` and
are wired through `execute_node`, then merged into the final verdict in
`reliability_node`.

For thesis interpretation, structural audit is the symbolic trace/state
component that answers RQ3: final-answer-only auditing versus
trace/state-augmented auditing. It should be reported separately from the
LLM-based claim pipeline:

- `V3_Intervention` with structural audit disabled: LLM claim pipeline only.
- `V3_Intervention` with structural audit enabled: LLM claim pipeline plus
  symbolic trace/state checks.

Use `V3_NoStructural` for the structural-audit-disabled condition. It keeps
`use_verifier=True` and `enforce_intervention=True`, but sets
`use_structural_audit=False`. The previous RQ3 run from 2026-05-14 has been
archived under `results/_archive/rq3_ablation_20260514/`; re-run
`./scripts/run_rq3_ablation.sh` with the current code before reporting final
TCCR, evidence-state, latency, and token metrics.

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

Set B is not organized by F0-F5. It contains 120 raw prompts, split evenly
between ecommerce and reference. Each domain has 40 expected-PASS prompts, 10
expected-WARN prompts, and 10 expected-BLOCK prompts. Scenarios are grouped by
task category, expected difficulty, anticipated failure type, and explicit
`verifiable_facts`.

## Reference Verifier Sources

Reference verification first uses deterministic fixture metadata and local
reference DB state. It also has an optional `verifier_sources` registry for
external bibliographic evidence:

- `src.domain.reference.sources.crossref:CrossRefSource`
- `src.domain.reference.sources.semantic_scholar:SemanticScholarSource`
- `src.domain.reference.sources.url:UrlSource`

The registry is configured in `src/domain/reference/config.yaml` and loaded by
`src/reliableguard/verifier/sources/loader.py`. Sources are disabled by default
to keep ablation runs deterministic and offline; enable them for deployment
experiments or case-study checks where network-backed evidence is acceptable.

## Figures and Tables

After experiments are complete, generate thesis artifacts with:

```bash
python3 scripts/generate_figures.py
```

The script reads the latest timestamped outputs under `results/set_a_full/`,
`results/set_b_full/`, and `results/rq3_ablation/`. It writes Figure 1-4 plus
`table_main_ablation.tex`, `table_evidence_state.tex`, and `table_latency.tex`
under `figures/`. Missing result directories or metrics from older runs are
skipped with a warning instead of failing the whole generation step.

## Current Local Artifacts

`results/` is gitignored. Old RQ3 data has been archived locally so it does not
affect automatic figure discovery:

- `results/_archive/rq3_ablation_20260514/`

New thesis runs should recreate `results/set_a_full/`, `results/set_b_full/`,
and `results/rq3_ablation/` from the scripts above. Thesis planning documents
such as `thesis_scope.md`, `formal_definitions.md`,
`related_work_skeleton.md`, and `thesis_outline.md` are tracked so the
experimental protocol and thesis framing remain versioned with the code.

## Pending Thesis Work

- Re-run Set A, Set B, and RQ3 with this frozen code version, then record the
  commit hash in the experiment report.
- Manually annotate about 50-80 samples to measure claim extraction precision,
  recall, and F1.
- Use the newly aggregated evidence-state, latency, and token fields to fill
  the RQ2 and runtime/cost tables.

## Project Structure

```text
src/
  agent/             # LangGraph agent runtime
  graph/             # Graph state, nodes, and routing
  reliableguard/     # Claim extraction, verification, scoring, intervention
    verifier/sources # Optional external verifier source registry
  domain/            # Ecommerce and reference domain tools/verifiers
    reference/sources # CrossRef, Semantic Scholar, and URL source adapters
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
