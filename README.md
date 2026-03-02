# ReliableGuard

A constraint-aware, environment-grounded governance framework for controllable tool-using LLM agents.

## Overview

ReliableGuard is a reliability enhancement layer for tool-using AI Agents. Without replacing the underlying LLM, it introduces a closed-loop governance layer between the Agent and external tools/environment, consisting of three core modules:

- **Constraint Gate**: Pre-execution validation (Schema / Policy / Dependency)
- **Environment Verifier**: Post-execution acceptance testing based on real environment state
- **Budgeted Recovery**: Failure-driven retry, rollback, and escalation with loop protection

## Project Status

> Work in Progress — Currently at Baseline stage

- [x] Project structure initialized
- [x] Mistral API connected and verified
- [x] SQLite database initialized
- [x] Baseline ReAct Agent implemented
- [x] Tool calling loop verified (`create_order`, `get_order_status`)
- [ ] Gate v0: Schema validator
- [ ] Gate v1: Policy + Dependency validator
- [ ] Verifier v0: DB state diff + postcondition assertion
- [ ] Verifier v1: False-success detection
- [ ] Recovery: Failure classifier + budgeted retry
- [ ] Ablation experiments (4 versions × 5 metrics)

## Project Structure

```
RELIABLE_GUARD/
├── src/
│   ├── agent/          # ReAct Agent main loop
│   ├── gate/           # Constraint Gate (Schema / Policy / Dependency)
│   ├── verifier/       # Environment Verifier
│   ├── recovery/       # Recovery Controller
│   ├── tools/          # Tool definitions and executors
│   └── db/             # Database initialization
├── tasks/              # Experiment task set
├── eval/               # Evaluation and ablation scripts
├── scripts/            # One-click reset and run scripts
├── logs/               # Trace logs (gitignored)
├── .env                # API Keys (gitignored)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
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
python ReliableGuard.py
```

## Core Research Problem

Existing tool-using Agent frameworks define task success at the **text output level** — the Agent claims completion, but the actual environment state (database, file system, API) may not reflect the intended outcome. This is referred to as **false success**.

ReliableGuard redefines task success as **environment acceptance**: a task is considered complete only when the observable environment state satisfies predefined postcondition assertions.

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

## Author

Binpeng Liu — PolyU DSAI, MSc Dissertation 2026
Supervisor: Prof. Han Ruijian
