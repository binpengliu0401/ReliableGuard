# Thesis Scope: ReliableGuard

## One-line Positioning

ReliableGuard is a neuro-symbolic post-hoc runtime verification harness for tool-using LLM agents, designed to quantify, standardize, and trace externally verifiable failures through claim-level auditing, domain-specific verification, risk scoring, intervention, and trace reporting.

## Problem Statement

Tool-using LLM agents increasingly interact with external tools, databases, documents, and information sources. Unlike standalone text generation systems, these agents can fail not only by producing factually incorrect language, but also by creating mismatches among natural-language outputs, tool execution traces, and external environment states.

This thesis focuses on three systematic reliability problems in such agents.

First, agent outputs are often difficult to quantify. When an agent states that an order has been created, a refund has been processed, or a bibliographic reference is valid, there is often no unified metric for determining whether the statement is correct, partially correct, unsupported, or unsafe.

Second, agent failures are difficult to standardize. Errors in different domains may appear in different forms: an ecommerce agent may claim that a database operation succeeded when no state transition occurred, while a reference-generation agent may produce a fabricated DOI or mismatched bibliographic metadata. Without a shared failure taxonomy, verifier interface, and evaluation protocol, such failures remain difficult to benchmark or compare.

Third, agent failures are difficult to trace. Final-answer-level evaluation is insufficient for many tool-using failures because the critical evidence may exist in the execution trace, tool response, database state, or external metadata rather than in the final natural-language response alone.

The scope of this thesis is therefore limited to externally verifiable failures in tool-using LLM agents with observable grounding artifacts, such as database state, bibliographic metadata, PDF reference lists, and tool execution traces.

## Proposed Solution

This thesis proposes ReliableGuard, a neuro-symbolic post-hoc runtime verification harness for monitoring tool-using LLM agents after or during task execution.

The framework combines neural and symbolic components. Neural components are used to interpret unstructured agent outputs by extracting and classifying factual claims. Symbolic components are used to verify those claims against domain-specific evidence sources, execution traces, environment states, and policy rules.

ReliableGuard follows a claim-level audit pipeline:

1. **Extract** factual claims from the agent's final answer.
2. **Classify** each claim by verifiability and relevance.
3. **Verify** claims using domain-specific verifier adapters.
4. **Score** claim-level and aggregate reliability risks.
5. **Intervene** through PASS, WARN, or BLOCK decisions when enforcement is enabled.
6. **Trace** the full audit path from claim to evidence, verifier result, risk score, and final verdict.

The framework is designed as a reliability harness rather than a model optimization method. It does not fine-tune or otherwise improve the underlying LLM. Instead, it supervises the behavior of tool-using agents by making their failures measurable, comparable, and traceable.

## Two Evaluation Domains

The empirical evaluation uses two domains that represent different grounding mechanisms.

### Ecommerce Domain: State-grounded Agent Tasks

The ecommerce domain evaluates an agent that uses tools to query and modify an SQLite-backed order database. The grounding artifacts are database records, tool calls, tool responses, and pre-/post-execution state transitions.

This domain captures state-grounded failures, such as incorrect order information, unsafe high-value order creation, and false-success cases where a tool reports success but the database state remains unchanged.

The ecommerce setting is used to test whether trace- and state-augmented auditing can detect failures that final-answer-level auditing alone cannot observe.

### Academic Reference Domain: Evidence-grounded Citation Tasks

The academic reference domain evaluates an agent that generates or verifies bibliographic references using DOI values, authors, titles, publication years, PDF reference lists, and bibliographic metadata.

This domain captures evidence-grounded failures, such as fabricated references, invalid DOI metadata, author-title mismatches, and unsupported bibliographic claims.

The reference setting is used to test how the reliability harness behaves when evidence is less state-like, more heterogeneous, and dependent on claim extraction quality.

## Research Questions

### RQ1: Claim-level Audit Accuracy and Coverage

How accurately does claim-level post-hoc auditing detect known failure modes across different failure categories, and what is its coverage ceiling given current claim extraction?

This question evaluates the effectiveness and limitations of the extract-classify-verify pipeline. It separates failures that are missed because the verifier is incorrect from failures that are missed because the relevant claim was never extracted. The latter defines a coverage ceiling for claim-level auditing.

### RQ2: Cross-domain Framework Generalizability

Does the unified evidence-state taxonomy, claim-type weighting, and risk scoring framework produce consistent and interpretable reliability measurements across structurally different agent deployment domains?

This question evaluates whether the same scoring framework—evidence-state classification, claim-weight matrix, and reliability score formula—can characterize the distinct failure patterns of state-grounded ecommerce tasks and evidence-grounded academic reference tasks in a comparable way. It specifically examines whether domain-dependent differences in TCCR, evidence-state distribution, and false alarm behavior are explained by the framework itself rather than by framework breakdown, thereby establishing the standardization claim of the thesis.

### RQ3: Final-answer-only versus Trace/State-augmented Auditing

For which categories of agent failure does final-answer-level auditing suffice, and for which is pre-execution structural checking irreplaceable?

This question goes beyond measuring an aggregate detection gain. It distinguishes two structurally different failure detection modes that the label "final-answer versus trace/state" conflates.

The first mode is **post-hoc factual verification**: the claim-level pipeline extracts claims from the final answer and verifies them against the current domain state. This mode naturally covers failures where the agent's output contradicts observable evidence. F4 false-success is an example: if a tool reports success but the database does not change, the agent will claim "order confirmed" while the database still shows status = pending. The claim pipeline detects this contradiction post-hoc without any trace or pre-execution visibility, because the inconsistency is present in the current state at audit time.

The second mode is **pre-execution policy enforcement**: checking business constraints against tool arguments before execution takes place. F2 policy violations are categorically different from factual errors. When an agent creates a high-value order (amount = 8000), the database state after execution is factually correct: the record exists, the amount matches, the status is as reported. The claim-level pipeline finds all claims supported and returns PASS. The violation is not in the state but in the decision to permit an operation that exceeded a policy threshold. No comparison of the final answer against domain state can expose this, because the state provides no evidence of wrongdoing.

The archived 2026-05-14 RQ3 run preliminarily supports this boundary: F4 detection rate remained 1.0 without structural audit, while F2 detection dropped to 0.0. That run predates the current TCCR, evidence-state, latency, and token aggregation fields. A later local full-run snapshot is preserved at `results/_archive/full_experiment_snapshot_20260522.tar.gz`, but it also precedes the latest policy, latency-unit, reference-output, and token-limit fixes. The codebase is now stable (token limits, fail-fast, claim extraction temperature all corrected). The final thesis numbers must come from a fresh re-run of `V3_Intervention` and `V3_NoStructural` under the current code version and seeds, using `./scripts/run_full_experiment_sequence.sh --timestamped-output`.

RQ3 therefore asks: not just how much does structural audit help, but where exactly does the claim-level pipeline reach its fundamental detection boundary, and what architectural component is necessary to cross it?

## Contributions

This thesis makes four main contributions.

1. **A failure taxonomy for externally verifiable failures in tool-using LLM agents.**  
   The thesis defines an F0-F5 taxonomy for categorizing agent failures that can be checked against external evidence, tool execution, or environment state.

2. **A claim-level neuro-symbolic audit pipeline.**  
   ReliableGuard implements a structured pipeline that extracts claims, classifies their verifiability, verifies them against domain evidence, scores reliability risk, applies intervention policies, and records traceable audit reports.

3. **A domain verifier adapter design pattern with interface contracts.**  
   The thesis specifies a verifier adapter pattern that allows domain-specific evidence sources and checking logic to be integrated into a common audit framework. This pattern is demonstrated across two distinct grounding mechanisms: state-grounded ecommerce tasks and evidence-grounded academic reference tasks.

4. **An empirical evaluation across two domains and three ablation settings.**  
   The thesis evaluates ReliableGuard across ecommerce and academic reference domains using baseline, audit-only, and enforced-intervention settings. The evaluation reports false acceptance, false alarm, detection rate, coverage, and the incremental contribution of trace/state-augmented auditing.

## Empirical Findings

The thesis is expected to support two central empirical findings.

**Finding A: Trace/state-augmented auditing substantially improves detection in the ecommerce domain, primarily through pre-execution policy enforcement.**  
Earlier runs indicate that ecommerce detection improves strongly from the baseline to V3 and that the controlled `V3_NoStructural` ablation isolates F2 policy violations as the key structural-audit contribution. These numbers must be refreshed after the code freeze so Set A, Set B, and RQ3 share the same commit, seeds, metrics schema, and output format. The final thesis should report the refreshed RDR and F2/F4 detection values rather than mixing old batches.

**Finding B: Claim extraction coverage is the dominant bottleneck in the reference domain, and domain-dependent differences are explainable within the unified framework.**  
In the academic reference setting, earlier runs show high false alarm behavior under enforced intervention. The hypothesized bottleneck is that claim extraction produces many unverifiable aggregate claims, which the verifier cannot reliably ground. The refreshed metrics now directly expose this mechanism through `avg_unverifiable_count`, `evidence_state_coverage`, and TCCR, allowing the final thesis to explain false alarms using evidence-state distribution rather than narrative interpretation alone.

Prior full-run outputs are treated as archived reproducibility snapshots, not as the source of final reported numbers. The post-fix rerun should use `--timestamped-output` and record the exact result directory paths alongside the git commit hash (`git rev-parse --short HEAD`).

## Out of Scope

This thesis explicitly does not address the following problems.

1. **No model optimization.**  
   ReliableGuard does not fine-tune models, perform RLHF, train reward models, or otherwise optimize the underlying LLM.

2. **No universal hallucination detection claim.**  
   The thesis does not claim to solve all forms of hallucination. It focuses only on failures that can be externally verified through observable grounding artifacts.

3. **No claim of universal domain generality.**  
   ReliableGuard is not claimed to work out-of-the-box for every agent domain. The framework is domain-adaptable through verifier adapters, but each new domain requires appropriate grounding artifacts, verifier logic, and evaluation scenarios.

4. **No evaluation of unverifiable subjective answers.**  
   The framework does not aim to judge subjective opinions, stylistic quality, open-ended preferences, or claims that lack external evidence.

5. **No assumption that verifiers are always correct.**  
   Verifier outputs are treated as domain-specific audit signals, not infallible truth. The reliability of each verifier depends on the quality of its evidence sources, interface design, and checking logic.

## Core Thesis Claim

This thesis argues that externally verifiable failures in tool-using LLM agents can be systematically quantified, standardized, and traced through a neuro-symbolic post-hoc runtime verification harness.

ReliableGuard operationalizes this claim by converting unstructured agent outputs into claim-level audit units, verifying those claims against domain-specific grounding artifacts, scoring reliability risks, applying configurable intervention policies, and producing traceable audit reports.

Through ecommerce and academic reference evaluations, the thesis shows that reliability supervision for tool-using agents requires more than final-answer assessment. In state-grounded domains, incorporating tool execution traces and environment state can substantially improve failure detection. In evidence-grounded domains, the effectiveness of intervention is strongly limited by claim extraction coverage and verifier calibration. These findings characterize both the promise and the limitations of post-hoc runtime verification as an agent reliability harness.
