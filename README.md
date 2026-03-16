# ReliableGuard

A constraint-aware, environment-grounded governance framework for controllable tool-using LLM agents.

## Overview

ReliableGuard is a reliability enhancement layer for tool-using AI Agents. Without replacing the underlying LLM, it introduces a closed-loop governance layer between the Agent and external tools/environment, consisting of three core modules:

- **Constraint Gate**: Pre-execution validation (Schema / Policy / Dependency)
- **Environment Verifier**: Post-execution acceptance testing based on real environment state
- **Budgeted Recovery**: Failure-driven retry, rollback, and escalation with loop protection

## Project Status

> Work in Progress — Gate v1 + Verifier v0 + Recovery v0 complete

- [x] Project structure initialized
- [x] Mistral API connected and verified
- [x] SQLite database initialized
- [x] Baseline ReAct Agent implemented
- [x] Tool calling loop verified (`create_order`, `get_order_status`)
- [x] Gate v0: Schema validator (type, range, required fields)
- [x] Gate v1: Policy + Dependency validator
- [x] Verifier v0: DB state diff + false-success detection
- [x] Reset environment for reproducible experiments
- [x] Baseline vs ReliableGuard comparison experiment
- [x] Recovery v0: Failure classifier + recovery controller + loop guard
- [x] Recovery-to-LLM feedback with business context injection
- [ ] Verifier v1: General assertion templates
- [ ] Recovery v1: Deterministic param fix + semantic-level retry
- [ ] LangGraph refactoring
- [ ] LLM backend upgrade (Gemini Flash / Qwen-plus)
- [ ] Benchmark scoring system (Outcome Score per task)
- [ ] Ablation experiments (4 versions × 5 metrics)

## Project Structure

```
RELIABLE_GUARD/
├── src/
│   ├── agent/          # ReAct Agent (with and without ReliableGuard)
│   ├── gate/           # Constraint Gate (Schema / Policy / Dependency)
│   ├── verifier/       # Environment Verifier + State Tracker
│   ├── recovery/       # Failure Classifier + Recovery Controller + Loop Guard
│   ├── config/         # Centralized tool config (rules, policies, assertions)
│   ├── tools/          # Tool definitions and executors
│   └── db/             # Database initialization + reset
├── tasks/              # Experiment task set
├── tests/              # Reproducibility tests (RG-OBS-001)
├── eval/               # Evaluation and ablation scripts
├── scripts/            # Plotting and analysis scripts
├── logs/               # Trace logs and experiment results
├── docs/findings/      # Empirical findings and design insights
├── .env                # API Keys (gitignored)
├── requirements.txt
├── Dockerfile
├── ReliableGuard.py    # Main entry — runs with full governance
└── Baseline.py         # Baseline entry — runs without governance
```

## Quickstart

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/reliable_guard.git
cd reliable_guard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your MISTRAL_API_KEY
```

### 3. Run

```bash
# Run with full ReliableGuard governance
python ReliableGuard.py

# Run baseline (no governance) for comparison
python Baseline.py
```

## Core Research Problem

Existing tool-using Agent frameworks define task success at the **text output level** — the Agent claims completion, but the actual environment state (database, file system, API) may not reflect the intended outcome. This is referred to as **false success**.

ReliableGuard redefines task success as **environment acceptance**: a task is considered complete only when the observable environment state satisfies predefined postcondition assertions.

## Architecture: Gate → Verifier → Recovery Closed Loop

The governance layer operates as a three-stage pipeline between the Agent and external environment:

1. **Constraint Gate** validates tool calls before execution against schema rules, business policies, and dependency ordering. Invalid or unauthorized calls are blocked with structured reasons.
2. **Environment Verifier** captures database snapshots before and after execution, computes state diffs, and runs postcondition assertions to determine whether the task truly completed. Detects false successes where the agent reports completion but the environment state disagrees.
3. **Recovery Controller** classifies failures from Gate or Verifier into typed categories (schema/policy/dependency/false-success/verify-fail), selects the appropriate recovery strategy (rollback, terminate, or retry), and enforces budget limits via loop guard to prevent infinite retries.

Recovery results, including business context, are fed back to the LLM so its final response reflects the actual system state rather than the original (potentially corrupted) tool output.

## Key Findings

### RG-OBS-001: Surface-form Sensitive Constraint Bypass

> The input `"create an order with amount -500"` causes mistral-small to silently convert `-500` to `500` in tool-call arguments. The Gate receives `500`, passes it as valid, and corrupt data is written to the database. No error is raised and the agent reports success. The Verifier detects this as FALSE_SUCCESS by comparing user intent signals against database state.

This finding demonstrates that model-layer constraints are surface-form sensitive and unreliable. See `docs/findings/RG-OBS-001.md` for full details.

### RG-DESIGN-001: Recovery-to-LLM Feedback Requires Business Context

> After Recovery rolled back a false-success order, the LLM suggested users "contact support to create negative amount orders" — a nonsensical recommendation. Root cause: Recovery only told the LLM what happened, not what the business rule says. Fix: include business-level guidance in recovery feedback so LLM generates appropriate responses.

See `docs/findings/RG-DESIGN-001.md` for full details.

## Baseline vs ReliableGuard Comparison

| Task | Input | Baseline | ReliableGuard |
|------|-------|----------|---------------|
| T01 | Normal order (500 RMB) | SUCCESS | SUCCESS |
| T02 | Negative amount (-500 RMB) | NOT_TRIGGERED | NOT_TRIGGERED |
| T03 | Exceeds limit (99999 RMB) | CORRUPT_DATA | GATE_BLOCKED |
| T04 | Silent sign conversion (-500) | FALSE_SUCCESS | FALSE_SUCCESS → ROLLBACK |
| T05 | Policy violation (6000 RMB) | POLICY_BYPASS | GATE_BLOCKED |
| T06 | Dependency violation (query before create) | DEPENDENCY_BYPASS | GATE_BLOCKED |

Out of 6 test cases, the baseline produced **4 failures**. ReliableGuard detected or blocked all 4, and for T04 performed automatic rollback of corrupted data.

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| End-to-end Success Rate | Task truly completed (verified by environment state) |
| False Success Rate | Agent claims success but environment assertion fails |
| Invalid Call Rate | Tool calls rejected due to schema/policy violations |
| Policy Violation Rate | Calls violating business rules or permission boundaries |
| Cost per Success | Token consumption per successfully completed task |

## Ablation Study Design

| Version | Description |
|---------|-------------|
| V1 Baseline | Pure ReAct Agent, no ReliableGuard |
| V2 +Gate | Baseline + Constraint Gate |
| V3 +Verifier | V2 + Environment Verifier |
| V4 Full | V3 + Recovery Controller |

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
