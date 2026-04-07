# ReliableGuard

A constraint-aware, environment-grounded governance framework for controllable tool-using LLM agents.

## Overview

ReliableGuard is a reliability enhancement layer for tool-using AI Agents. Without replacing the underlying LLM, it introduces a closed-loop governance layer between the Agent and external tools/environment, consisting of three core modules:

- **Constraint Gate**: Pre-execution validation (Schema / Policy / Dependency)
- **Environment Verifier**: Post-execution acceptance testing based on real environment state
- **Budgeted Recovery**: Failure-driven retry, rollback, and escalation with loop protection

## Project Status

> Work in Progress — LangGraph-based main path established; Gate v1 + Verifier v0 + Recovery v0 integrated into a unified runtime

- [x] Project structure initialized
- [x] SQLite database initialized
- [x] Unified LangGraph runtime established as the official main path
- [x] Tool calling loop verified (`create_order`, `get_order_status`)
- [x] Gate v0: Schema validator (type, range, required fields)
- [x] Gate v1: Policy + Dependency validator
- [x] Verifier v0: DB state diff + environment-grounded acceptance
- [x] Reset environment for reproducible experiments
- [x] Recovery v0: Failure classifier + recovery controller + loop guard
- [x] Recovery-to-LLM feedback with business context injection
- [x] LangGraph refactoring (StateGraph-based control flow)
- [x] LLM backend upgrade — Qwen-plus via OpenAI-compatible API
- [x] Scenario document v0.1 (17 scenarios, F0–F5 failure mode coverage)
- [x] Legacy ReAct prototype archived under `legacy/`
- [ ] Verifier v1: General assertion templates
- [ ] Recovery v1: Deterministic param fix + semantic-level retry
- [ ] Benchmark scoring system (Outcome Score per task)
- [ ] Ablation experiments (4 versions × 5 metrics)
- [ ] Reference domain integration into the unified framework
- [ ] README / reproducibility packaging cleanup
- [ ] Docker packaging

## Project Structure

```text
RELIABLE_GUARD/
├── src/
│   ├── agent/          # Official LangGraph Agent runtime
│   ├── graph/          # StateGraph nodes and control flow
│   ├── gate/           # Constraint Gate (Schema / Policy / Dependency)
│   ├── verifier/       # Environment Verifier + State Tracker
│   ├── recovery/       # Failure Classifier + Recovery Controller + Loop Guard
│   ├── config/         # Centralized configs for ablation / rules / assertions
│   ├── tools/          # Tool definitions and executors
│   ├── domain/         # Domain-specific policies / assertions / configs
│   └── db/             # Database initialization + reset
├── tasks/              # Main experiment task set
├── eval/               # Evaluation and ablation scripts
├── scripts/            # Utility scripts for analysis / plotting
├── logs/               # Trace logs and experiment results
├── docs/findings/      # Empirical findings and design insights
├── legacy/             # Archived ReAct prototypes and historical diagnostics
├── .env                # API Keys (gitignored)
├── requirements.txt
├── Dockerfile
└── ReliableGuard.py    # Unified entry point for the official runtime
Quickstart
1. Clone and install dependencies
git clone https://github.com/binpengliu0401/ReliableGuard.git
cd reliable_guard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
2. Configure environment
cp .env.example .env
# Edit .env and add your LLM_API_KEY (Qwen-plus via DashScope)
3. Run
# Run ReliableGuard with the official unified runtime
python ReliableGuard.py

Note:
Baseline / +Gate / +Verifier / Full ReliableGuard are treated as ablation settings within the same evaluation harness, rather than separate standalone systems.

Core Research Problem

Existing tool-using Agent frameworks often define task success at the text output level — the Agent claims completion, but the actual environment state (database, file system, API) may not reflect the intended outcome.

ReliableGuard redefines task success as environment acceptance: a task is considered complete only when the observable environment state satisfies predefined postcondition assertions.

This shifts the evaluation target from “the model says it is done” to “the environment confirms it is done”.

Architecture: Gate → Verifier → Recovery Closed Loop

The governance layer operates as a three-stage pipeline between the Agent and external environment:

Constraint Gate validates tool calls before execution against schema rules, business policies, and dependency ordering. Invalid or unauthorized calls are blocked with structured reasons.
Environment Verifier captures database snapshots before and after execution, computes state diffs, and runs postcondition assertions to determine whether the task truly completed.
Recovery Controller classifies failures from Gate or Verifier into typed categories (schema/policy/dependency/verify-fail/partial-completion/etc.), selects the appropriate recovery strategy (terminate, retry, repair, rollback, or escalation), and enforces budget limits via loop guard to prevent infinite retries.

Recovery results, including business context, are fed back to the LLM so its final response reflects the actual system state rather than the original or incomplete tool outcome.

Key Findings
RG-OBS-001: Surface-form Sensitive Constraint Bypass

In earlier ReAct-based experiments with older models, the input "create an order with amount -500" could trigger silent parameter correction, causing invalid user intent to be transformed into valid-looking tool arguments. This demonstrated that model-layer constraints can be surface-form sensitive and unreliable.

This finding is retained as a historical diagnostic case and supports the motivation for environment-grounded verification. It is not the central evaluation focus of the current Qwen-plus based main path. See docs/findings/RG-OBS-001.md for details.

RG-DESIGN-001: Recovery-to-LLM Feedback Requires Business Context

After Recovery corrected or rolled back a failed execution, the LLM could still generate poor user-facing explanations if it only received low-level error signals. Root cause: Recovery told the LLM what happened, but not what the business rule meant. Fix: include business-level guidance in recovery feedback so LLM generates appropriate responses.

See docs/findings/RG-DESIGN-001.md for full details.

Evaluation Philosophy

ReliableGuard is evaluated as a unified task harness, where all versions share the same environment, task set, and execution harness.

The core comparison is not “two completely different agents”, but rather:

V1 Baseline: governance disabled
V2 +Gate: Gate enabled
V3 +Gate +Verifier: Gate and Verifier enabled
V4 Full ReliableGuard: Gate, Verifier, and Recovery enabled

This design makes ablation results more interpretable and fair.

Evaluation Metrics
Metric Description
End-to-end Success Rate Task truly completed (verified by environment state)
Acceptance Pass Rate Fraction of runs whose final environment state satisfies task assertions
Invalid Call Rate Tool calls rejected due to schema/policy/dependency violations
Policy Violation Rate Calls violating business rules or permission boundaries
Cost per Success Token / tool-call cost per successfully completed task
Ablation Study Design
Version Description
V1 Baseline Unified runtime with governance modules disabled
V2 +Gate V1 + Constraint Gate
V3 +Gate +Verifier V2 + Environment Verifier
V4 Full ReliableGuard V3 + Recovery Controller
Scenario Coverage

17 core scenarios defined across 6 failure mode categories:

Category Count Description
F0 Happy Path 2 Normal completion, single-step and full workflow
F1 Schema Violation 3 Missing field, wrong type, out-of-range value
F2 Policy Violation 3 Rule-breaking or unauthorized operations
F3 Dependency Violation 3 Wrong order, non-existent resource, duplicate operation
F4 Structural Verification Failure 4 Environment state does not match expected completion
F5 Partial Completion 2 Multi-step flow terminates prematurely
LLM Backend
Backend Status Notes
mistral-small-latest Archived Used in earlier ReAct-based prototype experiments
qwen-plus Active Current official backend via DashScope OpenAI-compatible API
Notes on Legacy Archive

The legacy/ folder contains earlier ReAct-based prototypes and historical diagnostic scripts.

These archived files are retained for:

historical observations
early failure case studies
design evolution records

They are not part of the current official evaluation path.

References
Yao et al. (2023). ReAct: Synergizing Reasoning and Acting in Language Models.
Yao et al. (2024). τ-bench: A Benchmark for Tool-Agent-User Interaction.
Lu et al. (2025). ToolSandbox: A Stateful Evaluation Benchmark for LLM Tool Use.
Liu et al. (2023). AgentBench: Evaluating LLMs as Agents.
Rebedea et al. (2023). NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications.
Shinn et al. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.
Author

Binpeng Liu — PolyU DSAI, MSc Dissertation 2026
Supervisor: Prof. Han Ruijian
# ReliableGuard

A constraint-aware, environment-grounded governance framework for controllable tool-using LLM agents.

## Overview

ReliableGuard is a reliability enhancement layer for tool-using AI Agents. Without replacing the underlying LLM, it introduces a closed-loop governance layer between the Agent and external tools/environment, consisting of three core modules:

- **Constraint Gate**: Pre-execution validation (Schema / Policy / Dependency)
- **Environment Verifier**: Post-execution acceptance testing based on real environment state
- **Budgeted Recovery**: Failure-driven retry, rollback, and escalation with loop protection

## Project Status

> Work in Progress — LangGraph-based main path established; Gate v1 + Verifier v0 + Recovery v0 integrated into a unified runtime

- [x] Project structure initialized
- [x] SQLite database initialized
- [x] Unified LangGraph runtime established as the official main path
- [x] Tool calling loop verified (`create_order`, `get_order_status`)
- [x] Gate v0: Schema validator (type, range, required fields)
- [x] Gate v1: Policy + Dependency validator
- [x] Verifier v0: DB state diff + environment-grounded acceptance
- [x] Reset environment for reproducible experiments
- [x] Recovery v0: Failure classifier + recovery controller + loop guard
- [x] Recovery-to-LLM feedback with business context injection
- [x] LangGraph refactoring (StateGraph-based control flow)
- [x] LLM backend upgrade — Qwen-plus via OpenAI-compatible API
- [x] Scenario document v0.1 (17 scenarios, F0–F5 failure mode coverage)
- [x] Legacy ReAct prototype archived under `legacy/`
- [ ] Verifier v1: General assertion templates
- [ ] Recovery v1: Deterministic param fix + semantic-level retry
- [ ] Benchmark scoring system (Outcome Score per task)
- [ ] Ablation experiments (4 versions × 5 metrics)
- [ ] Reference domain integration into the unified framework
- [ ] README / reproducibility packaging cleanup
- [ ] Docker packaging

## Project Structure

```text
RELIABLE_GUARD/
├── src/
│   ├── agent/          # Official LangGraph Agent runtime
│   ├── graph/          # StateGraph nodes and control flow
│   ├── gate/           # Constraint Gate (Schema / Policy / Dependency)
│   ├── verifier/       # Environment Verifier + State Tracker
│   ├── recovery/       # Failure Classifier + Recovery Controller + Loop Guard
│   ├── config/         # Centralized configs for ablation / rules / assertions
│   ├── tools/          # Tool definitions and executors
│   ├── domain/         # Domain-specific policies / assertions / configs
│   └── db/             # Database initialization + reset
├── tasks/              # Main experiment task set
├── eval/               # Evaluation and ablation scripts
├── scripts/            # Utility scripts for analysis / plotting
├── logs/               # Trace logs and experiment results
├── docs/findings/      # Empirical findings and design insights
├── legacy/             # Archived ReAct prototypes and historical diagnostics
├── .env                # API Keys (gitignored)
├── requirements.txt
├── Dockerfile
└── ReliableGuard.py    # Unified entry point for the official runtime
```

## Quickstart

### 1. Clone and install dependencies

```bash
git clone https://github.com/binpengliu0401/ReliableGuard.git
cd reliable_guard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your LLM_API_KEY (Qwen-plus via DashScope)
```

### 3. Run

```bash
python ReliableGuard.py
```

> Note:  
> Baseline / +Gate / +Verifier / Full ReliableGuard are treated as ablation settings within the same evaluation harness, rather than separate standalone systems.

## Core Research Problem

Existing tool-using Agent frameworks often define task success at the **text output level** — the Agent claims completion, but the actual environment state (database, file system, API) may not reflect the intended outcome.

ReliableGuard redefines task success as **environment acceptance**: a task is considered complete only when the observable environment state satisfies predefined postcondition assertions.

This shifts the evaluation target from “the model says it is done” to “the environment confirms it is done”.

## Architecture: Gate → Verifier → Recovery Closed Loop

The governance layer operates as a three-stage pipeline between the Agent and external environment:

1. **Constraint Gate** validates tool calls before execution against schema rules, business policies, and dependency ordering. Invalid or unauthorized calls are blocked with structured reasons.
2. **Environment Verifier** captures database snapshots before and after execution, computes state diffs, and runs postcondition assertions to determine whether the task truly completed.
3. **Recovery Controller** classifies failures from Gate or Verifier into typed categories (schema/policy/dependency/verify-fail/partial-completion/etc.), selects the appropriate recovery strategy (terminate, retry, repair, rollback, or escalation), and enforces budget limits via loop guard to prevent infinite retries.

Recovery results, including business context, are fed back to the LLM so its final response reflects the actual system state rather than the original or incomplete tool outcome.

## Key Findings

### RG-OBS-001: Surface-form Sensitive Constraint Bypass

> In earlier ReAct-based experiments with older models, the input `"create an order with amount -500"` could trigger silent parameter correction, causing invalid user intent to be transformed into valid-looking tool arguments. This demonstrated that model-layer constraints can be surface-form sensitive and unreliable.

This finding is retained as a **historical diagnostic case** and supports the motivation for environment-grounded verification. It is not the central evaluation focus of the current Qwen-plus based main path. See `docs/findings/RG-OBS-001.md` for details.

### RG-DESIGN-001: Recovery-to-LLM Feedback Requires Business Context

> After Recovery corrected or rolled back a failed execution, the LLM could still generate poor user-facing explanations if it only received low-level error signals. Root cause: Recovery told the LLM what happened, but not what the business rule meant. Fix: include business-level guidance in recovery feedback so LLM generates appropriate responses.

See `docs/findings/RG-DESIGN-001.md` for full details.

## Evaluation Philosophy

ReliableGuard is evaluated as a **unified task harness**, where all versions share the same environment, task set, and execution harness.

The core comparison is not “two completely different agents”, but rather:

- **V1 Baseline**: governance disabled
- **V2 +Gate**: Gate enabled
- **V3 +Gate +Verifier**: Gate and Verifier enabled
- **V4 Full ReliableGuard**: Gate, Verifier, and Recovery enabled

This design makes ablation results more interpretable and fair.

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| End-to-end Success Rate | Task truly completed (verified by environment state) |
| Acceptance Pass Rate | Fraction of runs whose final environment state satisfies task assertions |
| Invalid Call Rate | Tool calls rejected due to schema/policy/dependency violations |
| Policy Violation Rate | Calls violating business rules or permission boundaries |
| Cost per Success | Token / tool-call cost per successfully completed task |

## Ablation Study Design

| Version | Description |
|---------|-------------|
| V1 Baseline | Unified runtime with governance modules disabled |
| V2 +Gate | V1 + Constraint Gate |
| V3 +Gate +Verifier | V2 + Environment Verifier |
| V4 Full ReliableGuard | V3 + Recovery Controller |

## Scenario Coverage

17 core scenarios defined across 6 failure mode categories:

| Category | Count | Description |
|----------|-------|-------------|
| F0 Happy Path | 2 | Normal completion, single-step and full workflow |
| F1 Schema Violation | 3 | Missing field, wrong type, out-of-range value |
| F2 Policy Violation | 3 | Rule-breaking or unauthorized operations |
| F3 Dependency Violation | 3 | Wrong order, non-existent resource, duplicate operation |
| F4 Structural Verification Failure | 4 | Environment state does not match expected completion |
| F5 Partial Completion | 2 | Multi-step flow terminates prematurely |

## LLM Backend

| Backend | Status | Notes |
|---------|--------|-------|
| mistral-small-latest | Archived | Used in earlier ReAct-based prototype experiments |
| qwen-plus | Active | Current official backend via DashScope OpenAI-compatible API |

## Notes on Legacy Archive

The `legacy/` folder contains earlier ReAct-based prototypes and historical diagnostic scripts.

These archived files are retained for:

- historical observations
- early failure case studies
- design evolution records

They are **not** part of the current official evaluation path.

## References

- Yao et al. (2023). ReAct: Synergizing Reasoning and Acting in Language Models.
- Yao et al. (2024). τ-bench: A Benchmark for Tool-Agent-User Interaction.
- Lu et al. (2025). ToolSandbox: A Stateful Evaluation Benchmark for LLM Tool Use.
- Liu et al. (2023). AgentBench: Evaluating LLMs as Agents.
- Rebedea et al. (2023). NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications.
- Shinn et al. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.

## Author

Binpeng Liu — PolyU DSAI, MSc Dissertation 2026  
Supervisor: Prof. Han Ruijian
