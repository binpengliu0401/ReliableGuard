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

The three research questions form a single progression. RQ1 and RQ2 are answered within the ecommerce domain: RQ1 establishes how much claim-level final-answer auditing can detect and where its ceiling lies; RQ2 then shows that part of that ceiling is not an extraction problem but a structural blind spot of the final-answer channel itself, which trace/state signals can break. RQ3 leaves the single domain and asks whether the RQ1/RQ2 findings are properties of the framework or accidents of ecommerce, by testing the framework on a structurally heterogeneous domain. Ordering follows logical dependence, not raw importance: RQ2 (the strongest empirical finding) is placed second because its argument depends on the coverage ceiling that RQ1 must establish first.

### RQ1: Claim-level Audit Accuracy and Coverage

How accurately does claim-level post-hoc auditing detect known failure modes across different failure categories, and what is its coverage ceiling given current claim extraction?

This question evaluates the effectiveness and limitations of the extract-classify-verify pipeline. It separates failures that are missed because the verifier is incorrect from failures that are missed because the relevant claim was never extracted. The latter defines a coverage ceiling for claim-level auditing. The right measurement point for this pure detection ability is the `V2_AuditOnly` audit verdict (auditing without enforcement and without structural signals), supported by manual claim-extraction annotation that decomposes misses into *not-extracted* versus *misjudged*. RQ1 closes by asking whether the residual ceiling is entirely an extraction problem, or whether part of it is structural — a question RQ2 takes up directly.

### RQ2: Final-answer-only versus Trace/State-augmented Auditing

For which categories of agent failure does final-answer-level auditing suffice, and for which are tool-trace and state-transition checks necessary?

This question goes beyond measuring an aggregate detection gain. It distinguishes two structural signals that final-answer-only auditing does not reliably provide.

The first signal is **pre-execution policy enforcement**: checking business constraints against tool arguments before execution takes place. F2 policy violations are categorically different from factual errors. When an agent creates a high-value order (amount = 8000), the database state after execution may be factually consistent: the record exists, the amount matches, and the status is as reported. The violation is not in the final state but in the decision to permit an operation that exceeded a policy threshold. Authorization is therefore an audit dimension independent of answer correctness, and a post-hoc claim verifier cannot reliably infer it unless the policy condition itself is exposed as an audit signal. A controlled policy-aware comparison (injecting the policy into the agent prompt, under both benign and adversarial requests) is the test that separates a genuine structural blind spot from a mere knowledge gap.

The second signal is **post-execution state-transition validation**: checking whether a tool that reports success actually caused the expected environment mutation. F4 false-success is the architectural bedrock of this RQ: the agent is honest — it relays the tool's "success" return — but the tool's reported effect and the true state diverge. The agent cannot self-verify this from inside its control flow, because what it observes is the tool return value, not the database state. The ground truth lives only in a pre/post snapshot taken in the wrapper outside the tool call. This blind spot is independent of the agent's knowledge or prompt; no prompt change can close it.

The current post-fix structural ablation confirms this boundary on Set A ecommerce. With structural audit disabled, `V3_NoStructural` reaches only `0.237` risk detection and `0.762` false acceptance. With structural audit enabled, V3 reaches `0.640` risk detection and `0.231` false acceptance. The targeted F2 detection rate improves from `0.225` to `0.735`, and F4 improves from `0.353` to `0.827`.

RQ2 therefore asks not only how much structural audit helps, but which hidden runtime properties claim-level final-answer auditing fails to expose: policy preconditions before execution and state-transition correctness after execution.

### RQ3: Cross-domain Framework Generalizability

Do the unified evidence-state taxonomy, claim-type weighting, and risk scoring framework remain applicable and interpretable when the framework is moved to a structurally different agent deployment domain — and when they degrade, does the degradation manifest as graceful, framework-explained decline rather than framework breakdown?

This question is the external-validity test that turns the ecommerce findings of RQ1 and RQ2 into framework-level claims rather than single-domain case studies. The standardization value of the framework is *not* that performance is equal across domains. It is that the same abstraction (claim → evidence-state → score → verdict) continues to produce a *meaningful measurement* in a heterogeneous domain — where "meaningful" explicitly does not mean "high-performing." A framework is meaningful in a new domain when, even as it underperforms, it reports *why* it underperforms in its own terms (coverage, evidence-state distribution, TCCR), instead of collapsing (taxonomy inapplicable, claims unclassifiable, scores meaningless).

The academic reference domain is deliberately used as the framework's **diagnostic / boundary case**, not as a second success story. Its low detection (V3 risk detection `0.162`) is reframed as evidence that the framework correctly *locates its own failure boundary*: low extraction coverage (TCCR `0.188`) and missing evidence sources, attributed at the framework's adaptation layer, not at its scoring core. The decisive instrument is the bottleneck-attribution decomposition (*not-extracted / misjudged / no-evidence*), which shows the abstraction is domain-invariant while the performance difference is confined to the adapter layer.

RQ3 stands in two relations to the earlier questions. It **inherits and cross-validates RQ1**: RQ1 finds that detection ability is capped by extraction coverage in ecommerce; RQ3 confirms the same mechanism in reference, where lower coverage explains the lower performance, upgrading the coverage finding from a single-domain observation to a framework-level regularity. It also **corroborates RQ2 from an external angle**: RQ2 demonstrates the limit of final-answer-only auditing by *internally ablating* structural audit (V3_NoStructural); reference is a domain that *natively lacks* a structural component, and its bounded performance is an external natural experiment pointing at the same conclusion. The internal controlled ablation and the external natural experiment converge on one finding — final-answer-only auditing has a structural ceiling.

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

The current post-fix experiment batch was run on commit `3759744`. The relevant result directories are `results/set_a_full/20260526/173346/`, `results/set_b_full/20260531/045635/`, and `results/rq3_ablation/20260531/073500/`. A protected copy is archived at `results/_archive/final_experiment_snapshot_20260602_3759744/`.

**Finding A: Trace/state-augmented auditing substantially improves ecommerce risk interception.**
On Set A ecommerce, V3 reaches `0.640` risk detection and `0.231` false acceptance. The claim-only structural-ablation variant (`V3_NoStructural`) reaches only `0.237` risk detection and `0.762` false acceptance. The structural audit gain is especially visible on the two runtime-sensitive failure modes: F2 policy violation improves from `0.225` to `0.735`, and F4 false-success detection improves from `0.353` to `0.827`.

**Finding B: Reference auditing is limited by claim grounding and verifier coverage rather than by the same trace/state mechanism.**
On Set A reference, V3 reaches only `0.162` risk detection and still has `0.666` false acceptance. Its evidence-state coverage is `0.321`, TCCR is `0.188`, and the average unverifiable count among covered tasks is `2.512`. These values support a bounded conclusion: the unified evidence-state framework exposes the reference bottleneck, but the current extractor/verifier combination does not deliver strong intervention performance for heterogeneous citation evidence.

**Finding C: Set B shows limited generalization under open-ended stress prompts.**
On Set B, overall V3 false acceptance remains `0.783`, with `0.178` gate action rate and `0.569` pass rate. These results should be reported as a stress-test limitation rather than as the main success claim.

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
