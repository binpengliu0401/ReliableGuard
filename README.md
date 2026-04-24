# ReliableGuard

A constraint-aware, environment-grounded governance framework for controllable tool-using LLM agents.

## Overview

ReliableGuard is a reliability enhancement layer for tool-using AI agents. Without replacing the underlying LLM, it introduces a closed-loop governance layer between the agent and external tools/environment, consisting of three core modules:

- **Constraint Gate**: pre-execution validation (Schema / Policy / Dependency)
- **Environment Verifier**: post-execution acceptance testing based on real environment state
- **Budgeted Recovery**: failure-driven retry, rollback, and escalation with loop protection

## Project Status

> Work in progress: LangGraph-based main path established; Gate + Verifier + Recovery integrated into a unified runtime.

- [x] Unified LangGraph runtime established as the official main path
- [x] Constraint Gate (schema, policy, dependency validation)
- [x] Environment Verifier (assertion-based postcondition checks)
- [x] Recovery controller (failure classification + retry/terminate/rollback)
- [x] Ecommerce domain integrated
- [x] Reference domain integrated
- [x] Curated scenario datasets for both domains
- [x] Ablation runner and benchmark metric pipeline
- [ ] Verifier v1: more generalized assertion templates
- [ ] Recovery v1: deterministic parameter repair policies
- [ ] Reproducibility packaging cleanup
- [ ] Docker workflow hardening

## Project Structure

```text
ReliableGuard/
|-- src/
|   |-- agent/             # Official LangGraph agent runtime
|   |-- graph/             # StateGraph nodes and control flow
|   |-- reliableguard/     # Constraint Gate / Verifier / Recovery modules
|   |-- domain/            # Domain-specific policies/assertions/tools/configs
|   |-- db/                # DB initialization and reset
|   |-- config/            # Runtime config
|-- tasks/                 # Scenario datasets
|-- eval/                  # Evaluation runners, metrics, and ablation presets
|   |-- config/            # Ablation version presets
|-- scripts/               # Utility scripts
|-- docs/findings/         # Empirical findings and design notes
|-- results/               # Experiment outputs
|-- logs/                  # Runtime traces and logs
|-- ReliableGuard.py       # Unified entry point
|-- requirements.txt
```

## Quickstart

### 1. Clone and install dependencies

```bash
git clone https://github.com/binpengliu0401/ReliableGuard.git
cd ReliableGuard
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Bash:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in project root and set `OPENROUTER_API_KEY`.

### 3. Run the unified runtime

```bash
python ReliableGuard.py --domain ecommerce --input "Please create an order with amount 100." --model qwen --version V4_Full --reset
```

Reference example:

```bash
python ReliableGuard.py --domain reference --input "Please parse the PDF at \"data/paper_f0.pdf\" with paper_id \"paper_ref_valid_001\"." --model deepseek --version V4_Full --reset
```

Useful flags:

- `--verbose`: show internal runtime logs
- `--full-result`: print full raw agent state (default prints concise result only)

## Reference Domain Modes

`src/domain/reference/api_client.py` supports three data modes:

- `REFERENCE_API_MODE=mock` (default): uses `src/domain/reference/fixtures/mock_data.json` for ablation and reproducibility.
- `REFERENCE_API_MODE=real`: uses `src/domain/reference/fixtures/real_data.json` generated from real PDFs.
- `REFERENCE_API_MODE=live`: DOI/authors queries call external APIs directly (live PDF parsing in `api_client` is intentionally not implemented).

Optional strict DOI matching toggle:

- `REFERENCE_STRICT_DOI_MATCH=1` forces title-based DOI semantic matching (default enabled in `real/live`).
- `REFERENCE_STRICT_DOI_MATCH=0` disables strict title matching and falls back to fixture `matches`.

## Build Real Fixture From PDFs

Generate `real_data.json` from one or more PDFs:

```bash
python scripts/build_real_fixture.py --pdf "reference 1.pdf" "reference 2.pdf"
```

Then run reference verification in real mode:

```bash
REFERENCE_API_MODE=real python ReliableGuard.py --domain reference --input "Please parse the PDF at \"reference 2.pdf\" with paper_id \"paper_ref2\" and verify DOI for all references."
```

The generated fixture keeps the same schema as `mock_data.json`:

- `pdfs`: parsed references by PDF filename
- `dois`: CrossRef-backed DOI metadata and `matches`
- `authors`: title-keyed author lists for `verify_authors`

## DOI Verification Semantics

Runtime keeps a binary `doi_status` for backward-compatible assertions:

- `verified`
- `failed`

It also writes `doi_verdict_code` for recovery routing:

- `verified`: DOI exists and semantically matches title
- `invalid`: DOI does not exist in CrossRef
- `uncertain`: DOI exists but title similarity is borderline (human review)
- `mismatch`: DOI exists but points to a different paper

Current recovery mapping in reference domain:

- `invalid -> retry` (within retry budget)
- `uncertain -> human_review` (continue pipeline, mark for manual check)
- `mismatch -> terminate`

## Evaluation

Run ablation on a scenario file:

```powershell
python -m eval.ablation_runner --input tasks/reference_scenarios.json --scenarios 20 --versions V3_Verifier --output results/reference_sample.json
```

Run from an offset using `--skip`:

```powershell
python -m eval.ablation_runner --input tasks/reference_scenarios.json --scenarios 20 --skip 100 --versions V3_Verifier --output results/reference_sample_skip100.json
```

Run benchmark on all main scenarios with a selected model backend:

```powershell
python -m eval.benchmark --scenarios main --model qwen
python -m eval.benchmark --scenarios main --model deepseek
```

Benchmark outputs:

- Scenario-level details: `results/{model}/scenario_results.csv`
- Ablation summary: `results/{model}/ablation.csv`
- Runtime log (append): `logs/{model}_run.log`

## Scenario Regeneration

Regenerate scenario datasets into `tasks/`:

```powershell
python scripts/ecommerce_scenario_generator.py
python scripts/reference_scenario_generator.py
```

## Core Research Problem

Existing tool-using agent frameworks often define task success at the text output level: the agent claims completion, but the actual environment state (database, filesystem, API side-effects) may not match the intended outcome.

ReliableGuard redefines task success as **environment acceptance**: a task is considered complete only when observable environment state satisfies predefined postcondition assertions.

## Architecture: Gate -> Verifier -> Recovery

The governance layer runs as a three-stage pipeline:

1. **Constraint Gate** validates tool calls before execution against schema, policy, and dependency rules.
2. **Environment Verifier** checks post-execution state via assertions against real environment data.
3. **Recovery Controller** classifies failures and applies retry/rollback/terminate strategies with budget limits.

Recovery outcomes are fed back into the interaction loop so final responses reflect actual system state.

## Evaluation Metrics

| Metric | Description |
|---|---|
| End-to-end Success Rate | Task completed successfully under expected outcome criteria |
| False Success Rate | Runs that ended as SUCCESS when expected outcome was non-SUCCESS |
| Invalid Call Rate | Fraction of blocked invalid calls (schema/dependency side) |
| Policy Violation Rate | Fraction of blocked policy-violating calls |
| Recovery Resolution Rate | Fraction of recovery-triggered cases resolved by retry path |
| Avg Outcome Score | Mean per-task outcome score (0-3) |

## Scenario Coverage

Current generated scenario sets:

| Domain | File | Total | Failure Modes |
|---|---|---:|---|
| Ecommerce | `tasks/ecommerce_scenarios.json` | 1000 | F0, F1, F2, F3, F4-B, F5 |
| Reference | `tasks/reference_scenarios.json` | 550 | F0, F1, F2, F3, F4, F5 |

## LLM Backend

| Backend | Status | Notes |
|---|---|---|
| qwen/qwen-plus | Active | OpenRouter backend via OpenAI-compatible API |
| deepseek/deepseek-chat-v3-0324 | Active | OpenRouter backend via OpenAI-compatible API |

## References

- Yao et al. (2023). ReAct: Synergizing Reasoning and Acting in Language Models.
- Yao et al. (2024). tau-bench: A Benchmark for Tool-Agent-User Interaction.
- Lu et al. (2025). ToolSandbox: A Stateful Evaluation Benchmark for LLM Tool Use.
- Liu et al. (2023). AgentBench: Evaluating LLMs as Agents.
- Rebedea et al. (2023). NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications.
- Shinn et al. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.

## Author

Binpeng Liu - PolyU DSAI, MSc Dissertation (2026)
Supervisor: Prof. Han Ruijian
