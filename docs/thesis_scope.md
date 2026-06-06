# Thesis Scope: ReliableGuard

## One-line Positioning

ReliableGuard is a neuro-symbolic post-hoc runtime verification harness for tool-using LLM agents, designed to quantify, standardize, and trace externally verifiable failures through claim-level auditing, domain-specific verification, risk scoring, intervention, and trace reporting.

At a conceptual level, the thesis treats black-box agent auditing as an **observability problem**: the agent's final answer is only a partial, self-reported observation of its true execution, and the central question is which failures are observable through that channel, which are not, and what additional observation channels (tool trace, environment state) are required to restore observability for the failures that the answer alone cannot expose.

## Problem Statement

Tool-using LLM agents increasingly interact with external tools, databases, documents, and information sources. Unlike standalone text generation systems, these agents can fail not only by producing factually incorrect language, but also by creating mismatches among natural-language outputs, tool execution traces, and external environment states.

This thesis focuses on three systematic reliability problems in such agents.

First, agent outputs are often difficult to quantify. When an agent states that an order has been created, a refund has been processed, or a bibliographic reference is valid, there is often no unified metric for determining whether the statement is correct, partially correct, unsupported, or unsafe.

Second, agent failures are difficult to standardize. Errors in different domains may appear in different forms: an ecommerce agent may claim that a database operation succeeded when no state transition occurred, while a reference-generation agent may produce a fabricated DOI or mismatched bibliographic metadata. Without a shared failure taxonomy, verifier interface, and evaluation protocol, such failures remain difficult to benchmark or compare.

Third, agent failures are difficult to trace. Final-answer-level evaluation is insufficient for many tool-using failures because the critical evidence may exist in the execution trace, tool response, database state, or external metadata rather than in the final natural-language response alone.

The scope of this thesis is therefore limited to externally verifiable failures in tool-using LLM agents with observable grounding artifacts, such as database state, bibliographic metadata, PDF reference lists, and tool execution traces.

## Conceptual Framing: Post-hoc Auditing as an Observability Problem

The central scientific question of this thesis is one of **observability**: given only the artifacts a black-box agent exposes, which of its failures can be detected by auditing, and which become detectable only if additional observation channels are introduced?

A tool-using agent's final natural-language answer is a *partial, self-reported observation* of the true execution trajectory. That trajectory includes the tool calls issued, the arguments supplied, the environment state before and after each call, and the policies that governed whether each call should have been permitted. The final answer reflects only what the agent chose to report, filtered through what the agent itself was able to observe. Whether a given failure can be caught by auditing therefore depends on **where its ground truth resides** relative to that observation:

- **Answer-local failures.** The ground truth is recoverable from the answer itself by checking its claims against an evidence source — a fabricated entity, an unsupported attribute. These are observable through the final-answer channel; this is the regime of claim-level auditing.
- **Trace/state-local failures.** The ground truth resides in the execution, not in the answer. Two sub-classes are decisive. *Policy compliance* (was the action permitted?): the resulting state can be fully consistent with the answer, so the answer carries no signal of the violation; the relevant fact is a pre-execution predicate over the tool arguments and the governing policy. *State-effect realization* (did the reported effect actually occur?): the agent honestly relays a tool's reported "success," but the true state did not change; the relevant fact is a pre/post state difference observed outside the tool call.
- **Evidence-local failures.** The ground truth lives in an external source — a DOI record, a PDF reference list — whose availability and heterogeneity are themselves variables.

This reframing turns the thesis into a study of the **observability limits of black-box, post-hoc agent auditing**, analogous to observability in control theory and to monitorability in runtime verification, rather than a system-building exercise. It also yields a precise, falsifiable structure: a failure class is *unobservable* through a given channel exactly when no audit over that channel's artifacts can separate it from a correct execution. Crucially, unobservability must be separated from mere pipeline weakness — a failure that a perfect extractor still could not catch is unobservable in principle, whereas one missed only because extraction was incomplete is a coverage artifact. Establishing that separation empirically is the burden of RQ1. The F0–F5 taxonomy (formalized in `formal_definitions.md`, Section 4.2, Type I/Type II) is organized along exactly this locus-of-ground-truth axis, and the three research questions trace its consequences.

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

The three research questions form a single progression that traces the observability argument above: what the final-answer channel can observe (RQ1), what additional channels are needed for what it cannot (RQ2), and how the observability bottleneck shifts across domains (RQ3). RQ1 and RQ2 are answered within the ecommerce domain: RQ1 establishes how much claim-level final-answer auditing can detect, where its ceiling lies, and — decisively — that the residual blind spot survives near-perfect extraction, so it is an observability limit and not an extraction artifact; RQ2 then shows that this blind spot is broken not by better claim extraction but by adding trace/state observation channels. RQ3 leaves the single domain and asks whether the RQ1/RQ2 findings are properties of the framework or accidents of ecommerce, by testing the framework on a structurally heterogeneous domain. Ordering follows logical dependence, not raw importance: RQ2 (the strongest empirical finding) is placed second because its argument depends on the coverage ceiling that RQ1 must establish first — RQ1's near-perfect-extraction result is precisely what licenses RQ2 to attribute the blind spot to the observation channel rather than to the extractor.

### RQ1: Claim-level Audit Accuracy and Coverage

How accurately does claim-level post-hoc auditing detect known failure modes across different failure categories, and what is its coverage ceiling given current claim extraction?

This question evaluates the effectiveness and limitations of the extract-classify-verify pipeline. It decomposes every miss into one of four attributions — *not-extracted* (the relevant claim was never pulled from the answer), *misjudged* (the claim was extracted but the verifier ruled incorrectly), *no-evidence* (the claim was extracted but no source was available to check it), and *correct* — so that a miss caused by a weak observation channel is never confused with one caused by a weak extractor. The right measurement point for this pure detection ability is the `V2_AuditOnly` audit verdict (auditing without enforcement and without structural signals).

The decisive instrument is a manual claim-extraction annotation study (150 stratified samples), which measures the extractor directly: a near-perfect extraction precision and a very small *not-extracted* coverage ceiling. This result is the empirical crux of the whole thesis, because it converts an intuition into a proof. It is intuitively obvious that an audit cannot catch a policy violation the answer never mentions; what is *not* obvious, and what the annotation establishes, is that this blind spot is **not** an artifact of imperfect extraction — even with near-perfect extraction the failure class remains undetectable, which means it is unobservable through the final-answer channel by construction. RQ1 thus closes by demonstrating that part of its own ceiling is not an extraction problem but a structural property of the observation channel — the precise claim RQ2 takes up.

### RQ2: Final-answer-only versus Trace/State-augmented Auditing

For which categories of agent failure does final-answer-level auditing suffice, and for which are tool-trace and state-transition checks necessary?

This question goes beyond measuring an aggregate detection gain. Read through the observability framing, it asks which *additional observation channels* are required to detect the failures that RQ1 proved unobservable from the final answer. It distinguishes two such channels that final-answer-only auditing does not provide.

The first signal is **pre-execution policy enforcement**: checking business constraints against tool arguments before execution takes place. F2 policy violations are categorically different from factual errors. When an agent creates a high-value order (amount = 8000), the database state after execution may be factually consistent: the record exists, the amount matches, and the status is as reported. The violation is not in the final state but in the decision to permit an operation that exceeded a policy threshold. Authorization is therefore an audit dimension independent of answer correctness, and a post-hoc claim verifier cannot reliably infer it unless the policy condition itself is exposed as an audit signal. This signal also frames the deeper design claim of RQ2: a safety-critical hard constraint should not be delegated to the agent's prompt, because the agent is a stochastic and adversarially-steerable place to enforce it; the constraint belongs in a deterministic monitor outside the agent. Establishing this requires a **controlled policy-aware comparison** that injects the policy into the agent prompt under both benign and adversarial requests. This comparison is not optional decoration: without it, a detected F2 violation only shows that the monitor can enforce a rule the agent was never told, which is the weaker "independent-enforcement" claim. The comparison is what upgrades the result to the strong claim — that *even when the agent is told the policy*, it violates it (especially adversarially), so an external deterministic check is necessary rather than merely available. It is the test that separates a genuine structural blind spot from a mere knowledge gap.

The second signal is **post-execution state-transition validation**: checking whether a tool that reports success actually caused the expected environment mutation. F4 false-success is the architectural bedrock of this RQ: the agent is honest — it relays the tool's "success" return — but the tool's reported effect and the true state diverge. The agent cannot self-verify this from inside its control flow, because what it observes is the tool return value, not the database state. The ground truth lives only in a pre/post snapshot taken in the wrapper outside the tool call. This blind spot is independent of the agent's knowledge or prompt; no prompt change can close it.

A structural ablation on Set A ecommerce illustrates this boundary. With structural audit disabled, `V3_NoStructural` reaches only `0.237` risk detection and `0.762` false acceptance; with it enabled, V3 reaches `0.640` risk detection and `0.231` false acceptance; the targeted F2 detection improves from `0.225` to `0.735` and F4 from `0.353` to `0.827`. **These specific figures are provisional and are scheduled for regeneration under the frozen-corpus methodology (see Evaluation Methodology):** they come from a batch that is now known to be non-reproducible (a second identical run flips roughly a third of per-task outcomes), and the structural A/B in particular was confounded by the agent being re-sampled between the two arms. The *direction* of the effect is robust — it rests on the deterministic structural checks and the architectural argument above, not on the exact rates — but the point estimates must be reported as paired contrasts on a frozen corpus before they carry weight, and the F2 figure must be paired with the policy-aware control to be meaningful at all.

RQ2 therefore asks not only how much structural audit helps, but which hidden runtime properties claim-level final-answer auditing fails to expose: policy preconditions before execution and state-transition correctness after execution.

### RQ3: Cross-domain Framework Generalizability

Do the unified evidence-state taxonomy, claim-type weighting, and risk scoring framework remain applicable and interpretable when the framework is moved to a structurally different agent deployment domain — and when they degrade, does the degradation manifest as graceful, framework-explained decline rather than framework breakdown?

This question is the external-validity test that turns the ecommerce findings of RQ1 and RQ2 into framework-level claims rather than single-domain case studies. The standardization value of the framework is *not* that performance is equal across domains. It is that the same abstraction (claim → evidence-state → score → verdict) continues to produce a *meaningful measurement* in a heterogeneous domain — where "meaningful" explicitly does not mean "high-performing." A framework is meaningful in a new domain when, even as it underperforms, it reports *why* it underperforms in its own terms (coverage, evidence-state distribution, TCCR), instead of collapsing (taxonomy inapplicable, claims unclassifiable, scores meaningless).

In the observability framing, the reference domain is where the observability bottleneck *moves*. Ecommerce is state-grounded: its hard failures are trace/state-local, and RQ2's remedy is to add a state-transition channel. Reference is evidence-grounded: its truth lives in heterogeneous external sources (DOI records, PDF reference lists) that may be unavailable, so its bottleneck is *evidence-local* — and, tellingly, there is no internal state-transition channel to add, so RQ2's specific remedy does not even apply. The academic reference domain is therefore deliberately used as the framework's **diagnostic / boundary case**, not as a second success story. Its low detection (V3 risk detection `0.162`) is reframed as evidence that the framework correctly *locates its own failure boundary*: low extraction coverage (TCCR `0.188`) and missing evidence sources, attributed at the framework's adaptation layer, not at its scoring core. The decisive instrument is the same four-way bottleneck-attribution decomposition used in RQ1 (*not-extracted / misjudged / no-evidence / correct*), now read comparatively across the two domains: it shows the analytic abstraction is domain-invariant — it correctly diagnoses *why* each domain is hard — while the performance difference is confined to the adapter layer and the locus of ground truth. What generalizes is therefore the diagnostic framework, not a performance level; reporting reference's lower detection without this attribution would misread a framework-produced finding as a framework failure.

RQ3 stands in two relations to the earlier questions. It **inherits and cross-validates RQ1**: RQ1 finds that detection ability is capped by extraction coverage in ecommerce; RQ3 confirms the same mechanism in reference, where lower coverage explains the lower performance, upgrading the coverage finding from a single-domain observation to a framework-level regularity. It also **corroborates RQ2 from an external angle**: RQ2 demonstrates the limit of final-answer-only auditing by *internally ablating* structural audit (V3_NoStructural); reference is a domain that *natively lacks* a structural component, and its bounded performance is an external natural experiment pointing at the same conclusion. The internal controlled ablation and the external natural experiment converge on one finding — final-answer-only auditing has a structural ceiling.

## Evaluation Methodology

Because the object of study is the **monitor** and not the agent, the evaluation must hold the agent's behaviour fixed rather than re-sample it on every run. Hosted LLM inference (DeepSeek via OpenRouter) is not reproducible even at temperature 0 with a fixed seed that is passed to the API: two identical runs were observed to disagree on roughly one third of audit outcomes, because provider-side factors (mixture-of-experts routing, floating-point non-associativity, request batching) are outside the experimenter's control. Re-sampling the agent on every run would confound any comparison between monitor configurations (for example V3 versus V3_NoStructural) with uncontrolled variation in the agent's wording — which is precisely the artefact that produced unstable per-stratum detection rates in the earlier batches.

The methodology resolves this with a **frozen-corpus, paired-replay** design:

1. **Freeze the behaviour corpus once.** Each scenario's agent run — final answer, tool-call trace, pre/post state snapshots, and extracted claims — is generated a single time and stored as a fixed benchmark corpus. The agent's role collapses to a one-time corpus generator; its non-determinism is removed from the measurement loop. This mirrors standard practice for evaluating a monitor or classifier on a fixed test set rather than against a live, re-sampled generator.
2. **Replay every monitor configuration on the identical corpus.** All versions (claim-only, structural-augmented, enforced) audit the same frozen behaviours, so any difference between them is attributable solely to the monitor configuration. The structural ablation (RQ2) becomes a *paired*, per-scenario contrast, which removes the dominant between-answer variance and is far more statistically powerful than averaging unpaired runs over multiple seeds. (Because the provider ignores the seed, "multiple seeds" in this stack is merely repeated sampling, not controlled variance; pairing is the correct instrument.)
3. **Treat agent variability as a controlled sensitivity analysis, not as noise in the headline numbers.** On a stratified subset, a second independent agent answer is generated per scenario and the monitor is re-run, reporting how often the verdict changes with the agent's wording. This makes the auditing pipeline's sensitivity to agent stochasticity an explicit, quantified result — itself a finding about post-hoc auditing — rather than leaving it as unacknowledged run-to-run noise.

The claim-extraction stage is itself a neural (LLM) component and is therefore part of what is frozen into the corpus; its quality is validated separately by the RQ1 manual annotation study, so that all downstream symbolic verification, scoring, structural checking, and policy decisions are fully deterministic and reproducible. The net effect is that the monitor evaluation is deterministic on a fixed corpus, the structural contribution is isolated causally, and the inherent non-determinism of hosted LLMs is converted from a threat to internal validity into a measured property of the system.

## Contributions

This thesis makes five main contributions.

1. **An observability characterization of black-box post-hoc agent auditing.**  
   The thesis frames agent auditing as an observability problem and characterizes which failure classes are observable from the agent's final answer and which are not, organizing them by the *locus of their ground truth* (answer-local, trace/state-local, evidence-local). It establishes — rather than assumes — that the final-answer blind spot is a property of the observation channel and not of extraction quality, using a manual annotation study to show the blind spot survives near-perfect extraction.

2. **A failure taxonomy for externally verifiable failures in tool-using LLM agents.**  
   The thesis defines an F0-F5 taxonomy, formalized as Type I (factual inconsistency, answer-local) versus Type II (policy/state, trace-local) failures, for categorizing agent failures that can be checked against external evidence, tool execution, or environment state.

3. **A claim-level neuro-symbolic audit pipeline with a domain verifier adapter pattern.**  
   ReliableGuard implements a structured pipeline that extracts claims (neural), then verifies, scores, intervenes, and traces deterministically (symbolic), with domain-specific evidence sources integrated through a verifier-adapter pattern. The pattern is demonstrated across two distinct grounding mechanisms: state-grounded ecommerce and evidence-grounded academic reference.

4. **A frozen-corpus, paired-replay evaluation methodology for non-deterministic agents.**  
   To evaluate a monitor over a non-reproducible hosted LLM, the thesis freezes the agent behaviour corpus once and replays every monitor configuration on it, turning the structural ablation into a powerful paired contrast and converting agent non-determinism from a validity threat into a measured sensitivity result.

5. **An empirical evaluation across two domains and the ablation settings.**  
   The thesis evaluates ReliableGuard across ecommerce and academic reference domains using baseline, audit-only, enforced, and structural-ablation settings, reporting false acceptance, false alarm, detection rate, coverage, the incremental contribution of trace/state-augmented auditing, and the cross-domain bottleneck attribution.

## Empirical Findings

> **Status caveat (read first).** The numeric findings below are from an earlier experiment batch (commit `3759744`) that is now known to be **non-reproducible**: it was generated with the agent at temperature 0.7, and even after fixing that, two identical runs disagree on roughly a third of per-task outcomes because of provider-level LLM non-determinism. The point estimates are therefore reported here as *provisional directional evidence* and are scheduled for regeneration under the frozen-corpus, paired-replay methodology (see Evaluation Methodology). The qualitative conclusions that rest on deterministic mechanisms and architectural arguments (the F2/F4 observability blind spots, the determinism of the structural checks, the cross-domain bottleneck shift) are expected to survive; the exact rates are not yet citable as final. The F2 numbers in particular require the policy-aware control to be meaningful.

The provisional batch used commit `3759744`. The relevant result directories are `results/set_a_full/20260526/173346/`, `results/set_b_full/20260531/045635/`, and `results/rq3_ablation/20260531/073500/`. A protected copy is archived at `results/_archive/final_experiment_snapshot_20260602_3759744/`.

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

This thesis characterizes the **observability limits of black-box, post-hoc auditing of tool-using LLM agents**: it shows that an agent's final answer is only a partial observation of its execution, that certain failure classes — policy compliance and state-effect realization — are unobservable through that channel by construction rather than by extraction weakness, that adding tool-trace and state-transition observation channels restores observability for exactly those classes, and that which failure class forms the bottleneck is determined by the domain's locus of ground truth.

ReliableGuard operationalizes this characterization as a neuro-symbolic harness that converts unstructured agent outputs into claim-level audit units (neural), verifies them against domain-specific grounding artifacts, scores risk, applies configurable intervention policies, and produces traceable audit reports (symbolic and deterministic). The division of labour is principled: extraction is a natural-language understanding task suited to a neural component, while verification against ground truth is a logical task where determinism is itself a reliability requirement.

Through ecommerce and academic reference evaluations — under the frozen-corpus, paired-replay methodology — the thesis shows that reliability supervision for tool-using agents requires more than final-answer assessment. In state-grounded domains, incorporating tool execution traces and environment state restores detection of failures the final answer cannot expose. In evidence-grounded domains, where no such internal channel exists, the same diagnostic framework correctly attributes the residual bottleneck to claim extraction coverage and evidence availability. Together these results characterize both the promise and the principled limits of post-hoc runtime verification as an agent reliability harness.
