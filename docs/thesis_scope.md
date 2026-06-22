# Thesis Scope: ReliableGuard

> **Updated 2026-06-15.** Re-grounded on τ-bench (2026-06-09); thesis structure finalized
> (2026-06-15) targeting ~20 pages with 6 chapters. Authoritative experiment design:
> [tau_bench_experiment_design.md](tau_bench_experiment_design.md). Metric definitions:
> [formal_definitions.md](formal_definitions.md). Code architecture:
> [architecture.md](architecture.md).

---

## One-line Positioning

ReliableGuard is a neuro-symbolic, **black-box, monitor-only** post-hoc runtime auditing harness
for tool-using LLM agents. It detects externally verifiable agent failures through claim-level
auditing plus tool-trace and environment-state checks, scores risk, and produces traceable verdicts
— without modifying, fine-tuning, or re-prompting the agent.

The thesis treats black-box agent auditing as an **observability problem**: the agent's final
answer is a partial, self-reported observation of its execution; the central question is which
failures are observable through which channels, and what additional channels restore observability
for the failures the answer alone cannot expose.

---

## Core Thesis Claim

ReliableGuard characterizes the **observability limits of black-box, post-hoc auditing of
tool-using LLM agents**: an agent's final answer is only a partial observation of its execution;
certain failure classes (policy/trace and state-effect) are unobservable through the answer
channel by construction rather than by extraction weakness; adding tool-trace and state-transition
channels restores observability for exactly those classes, robustly across base models; and the
residual boundary is the intent-local class, where the truth lives in the user's goal and no
observable artifact reaches it. Demonstrated entirely on the recognized τ-bench benchmark with
its own execution-based ground truth.

---

## Problem Statement

Tool-using LLM agents interact with tools, databases, documents, and external sources. They fail
not only by producing incorrect language but by creating mismatches among natural-language outputs,
tool execution traces, and environment states. Such failures are hard to quantify (no unified
verdict), hard to standardize (different surface forms across domains), and hard to trace (the
decisive evidence lives in the trace/state/external source, not the final answer). Scope is
limited to **externally verifiable failures with observable grounding artifacts** (database state,
tool traces, retrievable knowledge-base documents).

---

## Conceptual Framing: Auditing as an Observability Problem

A tool-using agent's final answer is a *partial, self-reported observation* of its true trajectory.
Whether a failure can be caught depends on **where its ground truth resides** relative to the
monitor's channels. The **locus of ground truth** organizes this:

| Locus | Ground-truth location | V_answer | V_structural |
| --- | --- | --- | --- |
| answer-local | Self-contradiction in the answer | detectable | detectable |
| trace-local | Tool-call sequence violates policy | not reachable | detectable |
| state-local | Claimed effect not realized in state_after | not reachable | detectable |
| intent-local | Valid action, wrong user goal | not reachable | **not reachable** |

Evidence-local (claim unsupported by KB documents) is excluded from the formal taxonomy: no KB
exists in the two formal domains (retail + airline), giving zero evidence detection surface.
Banking_knowledge — the only tau2-bench domain with a KB — is moved to Future Work (see §6.2)
because tau2-bench evaluates it via tool-call optimality, not factual accuracy.

The theoretical detection ceiling for any black-box monitor:

$$\text{RDR}(M)^* \leq 1 - \pi_{\text{intent-local}}$$

Crucially, unobservability must be separated from pipeline weakness: a failure a perfect extractor
still could not catch is unobservable in principle; one missed only because extraction was
incomplete is a coverage artifact. Establishing that separation is the burden of RQ1.

---

## Research Questions

| RQ | Question | Monitor config | Primary measurement | Expected direction |
| --- | --- | --- | --- | --- |
| RQ1 | How much can answer-only auditing detect, and where is its ceiling? | V_answer | Detection by locus + extraction spot-check | High answer-local, ~0 trace/state |
| RQ2 | Do trace/state channels recover what answer-only misses, robustly across models? | V_structural vs V_answer | ΔRDR by locus, McNemar, cross-model box chart | Positive ΔRDR; FAR stable |
| RQ3 | Where does black-box auditing saturate? | V_structural residual | π_intent-local; monitor-vs-oracle gap | Residual = intent-local share |

---

## Proposed Solution

ReliableGuard combines neural and symbolic components. Neural: extract and classify factual
claims from unstructured agent output. Symbolic: verify those claims against observable grounding
artifacts (environment state, tool trace, policy, retrievable evidence), score risk, and decide a
verdict. Six-stage pipeline: **Extract → Classify → Verify → Score → Intervene → Trace**.

Two monitor configurations differing only in which observation channel the verifier consults
(one claim extraction shared across both):

| Config | Channels | RQ served |
| --- | --- | --- |
| V_answer | Answer / conversation only | RQ1 baseline |
| V_structural | V_answer + state (env.data) + trace (env.actions vs wiki.md) | RQ2 primary |

---

## Evaluation Substrate: τ-bench

The evaluation is grounded entirely on **τ²-bench** (`sierra-research/tau2-bench` v1.0.0),
a recognized tool-agent benchmark whose ground truth is execution-based and not authored by us.
Formal domains: **retail (114 tasks) + airline (50 tasks) = 164 tasks/repeat**. The benchmark
exposes tool trace, DB state, and a reward function (`calculate_reward()` using the goal
annotation `r_actions`).

τ-bench is the **environment and oracle**, not a competing method. The monitor reads only
deployment-observable artifacts (final answer, `env.actions`, `env.data` before/after) and never
`r_actions` — gold label and monitor signal come from disjoint inputs, making the comparison
**non-circular**. Failures occur naturally; each reward-0 task receives a locus tag from a
rule-based annotator (`src/reliableguard/locus.py`).

Statistical design (advisor-agreed): **unseeded repeats** (no fixed seed — at temperature 0 the
provider is still non-deterministic, so a fixed seed does not control variance; the K repeats are
the primary noise-absorbing mechanism), 4 audited base models, fixed extractor model + fixed
user-simulator as controls, K = 10 repeats per (domain, model). Significance via per-task McNemar;
generality via cross-model distribution; noise via within-model std across K repeats.

---

## Contributions

1. **An observability characterization** of black-box post-hoc agent auditing, organizing failures
   by the locus of their ground truth and establishing (not assuming) that the answer-channel
   blind spot is a property of the channel, not of extraction quality.
2. **A locus-of-ground-truth taxonomy** (answer / trace / state / intent) as a
   domain-independent analysis lens over real benchmark failures, with a principled account of
   which loci fall outside any black-box observable channel.
3. **A claim-level neuro-symbolic audit pipeline** with a benchmark-adapter pattern (neural
   extraction; symbolic verification, scoring, intervention, and tracing).
4. **A statistically principled evaluation** on τ-bench across four base models with per-task
   McNemar paired tests, 95% confidence intervals (Clopper-Pearson exact for rates at the 0/1
   boundary, bootstrap otherwise), and CDR_κ reliability scores.
5. **A boundary result**: the irreducible intent-local class that no black-box channel can reach,
   identified on real benchmark data via the monitor-vs-oracle gap.

---

## Out of Scope

1. No model optimization (no fine-tuning / RLHF / reward models).
2. No universal hallucination-detection claim — only externally verifiable failures.
3. No claim of universal domain generality — each domain needs grounding artifacts and verifier
   logic.
4. No evaluation of subjective / unverifiable answers.
5. Verifiers are domain-specific audit signals, not infallible truth.

---

## Thesis Structure (finalized 2026-06-15)

Target: **~20 pages** of body text (excluding references and appendices). Style: heavy use of
figures, tables, and formal notation over prose, following the convention of top venues (τ-bench,
AgentSpec). Six chapters; advisor feedback applied (no fragmented subsections; arguments expressed
as figures/tables/equations wherever possible).

### Chapter 1 — Introduction (~1.5 pages, no subsections)

Flat prose. Covers: opening failure scenario from a real τ-bench trajectory → core insight
(answer is a partial observation) → ReliableGuard overview → numbered contributions list.
Contains **Figure 1** (conceptual diagram: agent execution → observable channels → locus → verdict).

### Chapter 2 — Related Work (~2.5 pages)

**2.1 Runtime Verification and Agent Safety**
Classical RV (Havelund & Rosu 2004; Barringer et al. 2004; Bartocci et al. 2018) →
AgentSpec (Wang et al. 2025) → AGrail (Luo et al. 2025). Focus: these enforce
action-level constraints; they do not do claim-level semantic auditing.

**2.2 Factuality Detection and Agent Evaluation**
FActScore (Min et al. 2023), SelfCheckGPT (Manakul et al. 2023): claim decomposition on static
text, no trace/state channels. AgentBench (Liu et al. 2024), τ-bench (Yao et al. 2024),
ToolSandbox (Lu et al. 2025): benchmark success metrics, no monitor with intervention verdicts.
LangSmith / Langfuse / DeepEval: general observability platforms, no domain-grounded verifier
pipeline.

Closes with **Table 1** (comparison matrix: Work × Evaluation object × Verification method ×
Intervention × Domain-specific × Runtime mode) + one positioning paragraph.

### Chapter 3 — Problem Formulation (~3 pages)

**3.1 Agent Model, Observable Channels, and Non-Circularity**
Formal agent as POMDP ⟨S, A, O, T, R, U⟩ (following τ-bench notation). Trajectory record
definition. Three observable channels: answer text, tool_trace, state_before/after. Non-circularity
constraint: monitor never reads `r_actions`. One equation block.

**3.2 Locus Taxonomy, Detection Ceiling, and Research Questions**
**Table 2** (locus × ground-truth location × V_answer reachability × V_structural reachability ×
τ-bench example). **Figure 2** (observability boundary diagram). Theoretical detection ceiling
equation: RDR* ≤ 1 − π_intent-local. **Table 3** (RQ × operationalization × monitor config ×
primary test × expected direction).

### Chapter 4 — ReliableGuard (~5.5 pages)

**4.1 Architecture and Monitor Configurations**
**Figure 3** (end-to-end pipeline: trajectory input → 6 stages → verdict + trace report).
**Table 4** (3 monitor configs × channels × gate flags × RQ served). One paragraph on design
principles (black-box, monitor-only, domain-portable, deterministic after stage 1).

**4.2 Claim Verification Pipeline**
Six stages unified in one section. **Table 5** (stage × input/output × neural/symbolic ×
purpose). Equation blocks for: claim extraction output C = {c_1,…,c_n}, evidence state
enumeration E, risk score formula (w(τ) × p(e)), aggregate reliability score, verdict space.
Verifier adapter contract (input/output typed interface in a code block). Adapter constraints
(determinism, offline, single-claim independence, no hidden policy).

**4.3 τ-bench Integration**
**Figure 4** (split diagram: what the monitor reads vs. what the τ-bench oracle reads —
non-circularity visual proof). Trajectory record schema (compact table). Snapshot order rule
(deepcopy before terminal env.step()). **Table 6** (trace rule set: retail rules +
airline rules, each with trigger condition and locus). **Algorithm 1** (locus annotator
priority logic: pass > trace-local > state-local > intent-local).

### Chapter 5 — Evaluation (~5.5 pages)

**5.1 Setup**
**Table 7** (4 audited models × vendor × tier × cost × ctx + 2 fixed controls). **Table 8**
(domains × task count × DB structure × policy source). **Figure 5** (statistical design
diagram: 3 claim types — significance via McNemar / generality via cross-model / noise via
K-repeat std — each at the right unit of analysis).

**5.2 Results: RQ1 and RQ2**
RQ1: bar chart (V_answer detection by locus) + extraction spot-check precision table.
RQ2: box/violin chart (cross-model V_answer vs V_structural RDR — the money chart) +
McNemar p-values table + per-locus lift table + FAR-unchanged panel.

**5.3 Results: RQ3 and Limitations**
Stacked bar (detected vs. undetected reward-0 tasks by locus, with intent-local as the
irreducible residual). Monitor-vs-oracle gap equation: gap = π_intent-local. **Table 9**
(limitations × root cause × mitigation/future direction).

### Chapter 6 — Conclusion and Future Work (~1.5 pages)

**6.1 Conclusion** (flat prose, ~0.8 pages)
Restates core claim grounded in empirical results. Three sentences per RQ: what we found,
why it matters, what it establishes.

**6.2 Future Work** (~0.7 pages)
Three directions:
(1) **Intent-local annotation**: independent human labeling to harden the RQ3 boundary claim
(spot-check that the residual coincides with a separately-derived intent-local class).
(2) **Action-centric domain extension**: banking_knowledge (tau2-bench) as a case study where
the monitor hits a structural observability limit — the benchmark evaluates tool-call optimality
(reward_basis="DB"/"ACTION") rather than factual accuracy, so `communicate_info=[]` for all 97
tasks and the monitor's detectable locus coverage approaches zero. This exposes a new failure
mode: the intent-local boundary is not just about user goals but also about action-selection
optimality in domains with no factual grounding surface. Future approaches include an action-local
verifier (checking agent's self-reported actions against tool_trace for phantom-action /
parameter-mismatch detection) or an LLM-as-judge for action optimality.
(3) **Online / in-loop monitoring**: integrating the verdict into the agent loop with a latency
budget, exploring whether early intervention on trace violations reduces downstream state errors.

---

## Planned Figures and Tables

| ID | Type | Chapter | Content |
| --- | --- | --- | --- |
| Figure 1 | Concept diagram | 1 | Agent → channels → locus → verdict |
| Figure 2 | Observability boundary | 3 | Venn of loci vs. channel reach |
| Figure 3 | Pipeline diagram | 4 | 6-stage audit pipeline end-to-end |
| Figure 4 | Split diagram | 4 | Monitor reads vs. oracle reads (non-circularity) |
| Figure 5 | Statistical design | 5 | 3 claim types at 3 levels |
| Figure 6 | Bar chart | 5 | V_answer detection by locus (RQ1) |
| Figure 7 | Box/violin | 5 | Cross-model RDR comparison (RQ2 money chart) |
| Figure 8 | Stacked bar | 5 | Detected vs. undetected by locus (RQ3) |
| Table 1 | Comparison matrix | 2 | Related work × 6 dimensions |
| Table 2 | Locus taxonomy | 3 | 4 loci × detectability (evidence-local excluded) |
| Table 3 | RQ table | 3 | RQ × operationalization × test |
| Table 4 | Monitor configs | 4 | 3 configs × channels × flags |
| Table 5 | Pipeline stages | 4 | Stage × I/O × neural/symbolic |
| Table 6 | Trace rules | 4 | Retail + airline policy rules (2 domains) |
| Table 7 | Model lineup | 5 | 4 audited + 2 controls |
| Table 8 | Domain stats | 5 | Domains × task count × structure |
| Table 9 | Limitations | 5 | Limitation × cause × mitigation |
| Algorithm 1 | Pseudocode | 4 | Locus annotator priority logic |
