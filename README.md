# ReliableGuard

ReliableGuard is a third-party reliability auditing layer for AI agent outputs.

It does not try to make the agent verify itself. After an agent produces a final
answer, ReliableGuard extracts factual claims, checks them against authoritative
sources, scores the risk, and returns a user-readable reliability report with a
claim-level evidence trace.

## Current Direction

This project has been refactored from a tool-execution governance prototype into
a claim-level reliability auditing framework.

The previous Gate / Recovery / assertion-decorator design has been removed. The
current research focus is:

- hallucination taxonomy for AI agent outputs
- verifiability boundary analysis
- evidence-grounded source verification
- claim-level reliability trace
- risk-aware intervention decisions
- detection-rate and human-agreement evaluation

## Architecture

Runtime agent flow:

```text
plan -> execute -> plan
plan -> reliability -> END
```

Reliability pipeline:

```text
Agent final answer
  -> Claim Extractor
  -> Verifiability Classifier
  -> Source Verifier
  -> Risk Scorer
  -> Intervention Policy
  -> Reliability Trace
  -> Report Generator
```

The framework's shared abstraction is not a universal verifier. Each domain has
its own evidence sources and verification logic, but both domains are mapped into
the same claim-level trace:

```text
claim -> verifiability -> evidence -> verdict -> risk -> intervention
```

## Project Structure

```text
ReliableGuard/
|-- src/
|   |-- agent/                 # LangGraph agent runtime
|   |-- graph/                 # StateGraph nodes and control flow
|   |-- reliableguard/
|   |   |-- schema.py          # Pydantic v2 data contracts
|   |   |-- pipeline.py        # Reliability pipeline orchestrator
|   |   |-- extractor/         # Claim extraction
|   |   |-- classifier/        # Taxonomy and verifiability classification
|   |   |-- verifier/          # Domain source verifiers
|   |   |-- scorer/            # Risk scoring
|   |   |-- intervention/      # PASS/WARN/BLOCK/ESCALATE policy
|   |   |-- trace/             # Trace logging and report generation
|   |-- domain/
|   |   |-- ecommerce/         # Ecommerce tools and DB-backed evidence
|   |   |-- reference/         # Reference tools, CrossRef fixtures, matcher
|   |-- db/                    # DB initialization and reset helpers
|   |-- config/                # Runtime config
|-- tasks/                     # Scenario datasets and paper test data
|-- eval/                      # Evaluation runners and metrics
|-- scripts/                   # Utility and smoke-test scripts
|-- logs/                      # Domain-scoped traces: logs/<domain>/
|-- results/                   # Model/domain-scoped outputs: results/<model>/<domain>/
|-- ReliableGuard.py           # CLI entry point
|-- requirements.txt
```

Runtime databases are local generated artifacts and are ignored by git:

- `ecommerce.db`: ecommerce orders table
- `references.db`: reference-domain papers and references tables

Removed legacy modules:

```text
src/reliableguard/gate/
src/reliableguard/recovery/
src/reliableguard/verifier/verifier.py
src/reliableguard/verifier/ecommerce_state_tracker.py
src/domain/ecommerce/assertions.py
src/domain/ecommerce/policies.py
src/domain/reference/assertions.py
src/domain/reference/policies.py
src/domain/loader.py
```

## Core Concepts

### Claim Types

ReliableGuard currently uses six claim types:

| Type | Meaning |
|---|---|
| `existence` | Entity exists in an authoritative source |
| `attribute` | Direct non-numeric property of an entity |
| `numeric` | Amount, count, score, year, or calculated value |
| `temporal` | Date, order, duration, or state transition timing |
| `relational` | Relationship between two or more entities |
| `semantic` | Textual grounding or interpretation |

Uncertainty is not a claim type. It is represented as a claim field:

```text
certainty = certain | uncertain | abstained
```

### Evidence States

| State | Meaning |
|---|---|
| `supported` | Evidence confirms the claim |
| `contradicted` | Entity exists, but the claimed value or relation conflicts with evidence |
| `unsupported` | Relevant evidence exists, but is insufficient to support the claim |
| `unverifiable` | No suitable verification path exists |
| `not_found` | The claimed primary entity cannot be resolved in the source |

`not_found` corresponds to a potential entity fabrication, but the code uses the
more conservative name because missing evidence does not always prove malicious
or intentional fabrication.

### Interventions

ReliableGuard does not perform automatic recovery by default. It decides how the
answer should be treated:

```text
PASS      claim is acceptable
WARN      user should inspect the issue
BLOCK     high-risk contradiction or missing entity
ESCALATE  no reliable verification path is available
```

This is intentionally different from recovery. Verification answers whether the
agent output is trustworthy; recovery would require knowing the correct
replacement answer, which can introduce secondary hallucinations.

## Quickstart

### 1. Install

```bash
git clone https://github.com/binpengliu0401/ReliableGuard.git
cd ReliableGuard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure LLM access

Create a `.env` file in the project root:

```text
OPENROUTER_API_KEY=your_key_here
```

If the key is absent, the claim extractor falls back to simple heuristic
extraction. That is useful for smoke tests, but LLM extraction is expected for
real experiments.

### 3. Run ecommerce domain

```bash
python ReliableGuard.py \
  --domain ecommerce \
  --input "Please create an order with amount 100 and tell me the status." \
  --model qwen \
  --version V4_Full \
  --reset
```

### 4. Run reference domain

Mock fixture mode is the default:

```bash
python ReliableGuard.py \
  --domain reference \
  --input "Please parse the PDF at \"paper_f0.pdf\" with paper_id \"paper_ref_valid_001\" and verify DOI." \
  --model qwen \
  --version V4_Full \
  --reset
```

Real fixture mode:

```bash
REFERENCE_API_MODE=real python ReliableGuard.py \
  --domain reference \
  --input "Please parse the PDF at \"reference 2.pdf\" with paper_id \"paper_ref2\" and verify DOI for all references." \
  --model qwen \
  --version V4_Full \
  --reset
```

Useful flags:

- `--verbose`: show internal runtime logs
- `--full-result`: print full raw agent state, including `reliability_report`

The concise CLI output includes:

```text
final_answer
reliability_verdict
reliability_score
reliability_summary
executed_tools
total_tokens
```

Current version presets:

| CLI key | Runtime behavior |
|---|---|
| `V1_Baseline` | Agent only, no reliability node |
| `V2_Gate` | Legacy-compatible key; currently same as no reliability |
| `V3_Verifier` | Audit-only reliability: report is generated, but intervention is not enforced |
| `V4_Full` | Full reliability: report is generated and PASS/WARN/BLOCK/ESCALATE is enforced |

## Reference Domain Modes

`src/domain/reference/api_client.py` supports:

- `REFERENCE_API_MODE=mock` default, uses `src/domain/reference/fixtures/mock_data.json`
- `REFERENCE_API_MODE=real`, uses `src/domain/reference/fixtures/real_data.json`
- `REFERENCE_API_MODE=live`, parses a local PDF directly and calls external APIs for DOI/authors lookup

Recommended usage:

- Use `mock` for full benchmark runs and ablation experiments. It is deterministic and reproducible.
- Use `live` for demos where the system should parse a real local PDF.
- Use `real` when you want reproducible experiments backed by a prebuilt fixture from real PDFs.

Live mode is intended for demonstration, not full-scale benchmark reporting,
because PDF parsing quality and external API availability can vary.

Build the real fixture:

```bash
python scripts/build_real_fixture.py --pdf "reference 1.pdf" "reference 2.pdf"
```

Demo with direct PDF parsing:

```bash
REFERENCE_API_MODE=live python ReliableGuard.py \
  --domain reference \
  --input "Please parse the PDF at \"tasks/papers/All Atention you need.pdf\" with paper_id \"attention_demo\" and list the references." \
  --model qwen \
  --version V4_Full \
  --reset
```

The generated fixture includes:

- `pdfs`: parsed references by PDF filename
- `dois`: DOI metadata and existence/match information
- `authors`: title-keyed author lists

## Reliability Traces

Each reliability run can write a JSON trace into `logs/<domain>/`:

```json
{
  "run_id": "ecommerce_20260425T072209Z",
  "run_started_at": "20260425T072209Z",
  "domain": "ecommerce",
  "query": "...",
  "answer": "...",
  "summary": {
    "total_claims": 2,
    "counts": {
      "supported": 2,
      "contradicted": 0,
      "unsupported": 0,
      "unverifiable": 0,
      "not_found": 0
    },
    "items": [
      {
        "claim": "Order 1 status is confirmed",
        "evidence_state": "supported",
        "source": "orders_db",
        "risk_level": "low",
        "intervention": "PASS"
      }
    ]
  },
  "traces": []
}
```

CLI runs also write structured outputs into `results/<model>/<domain>/`.

Result files contain the final answer, executed tools, verdict, reliability
score, summary counts, and a compact claim list. For example:

```text
logs/ecommerce/ecommerce_20260425T072209Z.json
results/qwen/ecommerce/ecommerce_20260425T072209Z.json
```

To generate a deterministic local artifact sample without real LLM/API access:

```bash
python scripts/artifact_smoke_test.py
```

To inspect the newest ecommerce artifacts:

```bash
cat "$(ls -t logs/ecommerce/*.json | head -1)"
cat "$(ls -t results/qwen/ecommerce/*.json | head -1)"
```

These traces are the basis for:

- debugging agent hallucinations
- detection-rate analysis by claim type
- human agreement annotation
- calibration of reliability scores

## Smoke Tests

All smoke and local business-flow tests are consolidated in:

```text
scripts/smoke_test.py
```

Run them with either command:

```bash
python -m pytest scripts/smoke_test.py -q
python scripts/smoke_test.py
```

The smoke suite is deterministic. It avoids real OpenRouter, CrossRef, and PDF
parsing calls, but it covers:

- ecommerce and reference verifier rules
- heuristic claim extraction through the full reliability pipeline
- `run_agent()` business flows through LangGraph plan/execute/reliability nodes
- real tool side effects against isolated in-memory databases

Real paper PDFs used for reference-domain experiments live under:

```text
tasks/papers/
```

## Evaluation

Run ablation scenarios:

```bash
python -m eval.ablation_runner \
  --input tasks/reference_scenarios.json \
  --scenarios 20 \
  --versions V4_Full \
  --output results/reference_sample.json
```

Run benchmark:

```bash
python -m eval.benchmark --scenarios main --domain all --model qwen
python -m eval.benchmark --scenarios main --domain reference --model deepseek
```

Current metrics are reliability-oriented:

| Metric | Description |
|---|---|
| Pass Rate | Fraction of scenarios where expected and actual verdict match |
| False Acceptance Rate | Risky outputs incorrectly accepted as `PASS` |
| Block Rate | Fraction of runs producing `BLOCK` |
| Warn Rate | Fraction of runs producing `WARN` |
| Avg Reliability Score | Mean reliability score across runs |
| Detection Rate by Type | Detection rate grouped by injected claim/hallucination type |

## Research Framing

ReliableGuard studies a narrower and more deployable problem than training a
better agent:

> Given an AI agent's final answer, which generated claims are verifiable, what
> evidence supports or contradicts them, and what risk-aware intervention should
> be shown to the user?

The intended thesis contributions are:

1. A taxonomy of hallucination types in enterprise-style agent outputs.
2. A verifiability boundary for deciding which claims can be checked.
3. A domain-adaptable evidence verification pipeline.
4. Claim-level reliability traces for auditability and human agreement study.
5. Detection-rate and false-acceptance evaluation across ecommerce and reference domains.

## LLM Backend

| Backend | Status | Notes |
|---|---|---|
| `qwen/qwen-plus` | Active | OpenRouter backend via OpenAI-compatible API |
| `deepseek/deepseek-chat-v3-0324` | Active | OpenRouter backend via OpenAI-compatible API |

## Author

Binpeng Liu - PolyU DSAI, MSc Dissertation (2026)  
Supervisor: Prof. Han Ruijian
