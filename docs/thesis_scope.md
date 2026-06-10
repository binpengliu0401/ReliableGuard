# Thesis Scope: ReliableGuard

> **Re-grounded 2026-06-09.** This document was updated when the project pivoted from a self-made
> benchmark (Set A/B, F0–F5, ecommerce + reference domains) to the recognized **τ-bench** benchmark.
> The conceptual spine (observability + locus of ground truth) is unchanged; the evaluation
> substrate and the research-question instruments are new. Authoritative experiment design:
> [tau_bench_experiment_design.md](tau_bench_experiment_design.md).

## One-line Positioning

ReliableGuard is a neuro-symbolic, **black-box, monitor-only** post-hoc runtime auditing harness for
tool-using LLM agents. It detects externally verifiable agent failures through claim-level auditing
plus tool-trace and environment-state checks, scores risk, and produces traceable verdicts — without
modifying, fine-tuning, or re-prompting the agent.

At a conceptual level the thesis treats black-box agent auditing as an **observability problem**:
the agent's final answer is only a partial, self-reported observation of its execution, and the
central question is which failures are observable through which channels, and what additional
observation channels (tool trace, environment state, external evidence) restore observability for
the failures the answer alone cannot expose.

## Problem Statement

Tool-using LLM agents interact with tools, databases, documents, and external sources. They fail not
only by producing incorrect language but by creating mismatches among natural-language outputs, tool
execution traces, and environment states. Such failures are hard to quantify (no unified verdict),
hard to standardize (different surface forms across domains), and hard to trace (the decisive
evidence lives in the trace/state/external source, not the final answer). The scope is limited to
**externally verifiable failures with observable grounding artifacts** (database state, tool traces,
retrievable knowledge-base documents).

## Conceptual Framing: Post-hoc Auditing as an Observability Problem

A tool-using agent's final answer is a *partial, self-reported observation* of its true trajectory
(tool calls, arguments, pre/post environment state, governing policy). Whether a failure can be
caught by auditing depends on **where its ground truth resides** relative to the monitor's channels.
A failure class is *unobservable* through a channel exactly when no audit over that channel's
artifacts can separate it from a correct execution. The **locus of ground truth** organizes this:

- **answer-local** — recoverable from the answer itself (self-contradiction, impossible value,
  a claim checkable from the answer). Observable through the answer channel.
- **trace-local** — in the tool-call trace: a policy / precondition / ordering violation. The
  resulting state can be consistent with the answer, so the answer carries no signal; the fact is a
  predicate over the actions and the governing policy.
- **state-local** — in the post-execution environment state: the agent honestly relays a tool's
  reported "success," but the true state did not change; the fact is a pre/post state difference.
- **evidence-local** — in an external source. *Source-available* (a retrievable knowledge base) is
  recoverable by re-retrieval; *source-unavailable* (no black-box access) is a boundary.
- **intent-local** — in the user's goal: a valid action that is not what the user wanted. The answer
  is self-consistent and the state matches the claim, yet the goal is unmet. **No black-box channel
  reaches it** — this is the principled boundary.

This turns the thesis into a study of the **observability limits of black-box, post-hoc agent
auditing**, analogous to observability in control theory and monitorability in runtime verification.
Crucially, unobservability must be separated from mere pipeline weakness — a failure a perfect
extractor still could not catch is unobservable in principle, whereas one missed only because
extraction was incomplete is a coverage artifact. Establishing that separation is the burden of RQ1.

## Proposed Solution

ReliableGuard combines neural and symbolic components. Neural: extract and classify factual claims
from unstructured agent output. Symbolic: verify those claims against observable grounding artifacts
(environment state, tool trace, policy, retrievable evidence), score risk, and decide a verdict.
The six-stage pipeline: **Extract → Classify → Verify → Score → Intervene (PASS/WARN/BLOCK/
AUDIT_FAILED) → Trace**. It is a reliability harness, not a model-optimization method.

The monitor is evaluated in three configurations that differ only in the verifier's observation
channel (sharing one claim extraction per trajectory):

- **V_answer** — answer/conversation only (the RQ1 baseline; answer-local).
- **V_structural** — V_answer + environment-state channel + tool-trace/policy channel + a
  post-execution state-change assertion (RQ2).
- **V_evidence** — V_answer + re-retrieval against a knowledge base (RQ2 extension; source-available
  evidence-local).

## Evaluation Substrate: τ-bench

The evaluation is grounded entirely on **τ-bench** (Yao et al. 2024; `sierra-research/tau-bench`,
with tau2/tau3 domains), a recognized tool-agent benchmark whose ground truth is **execution-based**
and **not authored by us**. Domains: retail / airline / telecom (DB-backed, with explicit `wiki.md`
policy and preconditions) and banking_knowledge (RAG, supplying source-available evidence-local).

τ-bench is the **environment and the gold-truth oracle**, not a competing method. Its
`calculate_reward()` compares the final database state to an annotated goal (`r_actions`) — an
oracle that needs the answer key. ReliableGuard is the **monitor under study**: it reads only
deployment-observable artifacts (final answer, `env.actions`, `env.data` before/after) and never the
goal annotation, so the gold label and the monitor signal come from disjoint inputs — the comparison
is **non-circular**. The baseline ReliableGuard improves on is its own `V_answer` configuration, not
τ-bench.

Failures are not injected; they occur naturally. Each real failure is given a **locus tag** for
analysis (preferring τ-bench's native fault types, else a documented rule-based classifier); the
correctness label is always τ-bench's reward, never the locus tag.

## Research Questions

The three RQs form one progression: what the answer channel can observe (RQ1), what channels recover
what it cannot (RQ2), and where the irreducible boundary lies (RQ3).

### RQ1 — Answer-only audit accuracy and ceiling

How much can black-box answer-only auditing detect across failure loci, and where is its ceiling?
Measured by `V_answer` detection / precision / false-alarm on τ-bench, broken out by locus
(expected: catches answer-local, near-blind on trace/state/intent). A small extraction-quality
spot-check shows the residual blind spot is a property of the **observation channel**, not of weak
extraction — converting the intuition into a proof.

### RQ2 — Trace/state-augmented auditing, robust across base models (the primary contribution)

For which failure loci are tool-trace and state-transition channels necessary, and does the recovery
hold across base agent models? Measured by `V_structural` vs `V_answer` detection lift by locus with
false-alarm held constant; **significance** via per-task paired McNemar; **generality** via the
cross-model distribution over four audited base models (the headline box chart). `V_evidence` extends
the recovery to source-available evidence-local in banking_knowledge. The trace channel checks the
agent's actions against τ-bench's own published `wiki.md` policy, so even the rules are not self-made.

### RQ3 — The boundary

Where does black-box auditing saturate? The residual reward-0 failures that `V_structural` still
misses correspond to **intent-local** faults (the answer is self-consistent and the state matches the
claim, yet the goal is unmet) and to source-unavailable evidence-local faults. The truth lives in the
user's goal, which no observable artifact carries; only the τ-bench oracle (holding the goal
annotation) can catch them. The monitor-vs-oracle gap *is* the intent-local share — the framework
correctly locates its own boundary rather than breaking.

## Evaluation Methodology (statistical design)

The object of study is the **monitor**. Hosted LLM inference is non-reproducible even at temperature
0 with a fixed seed (provider-side MoE routing, float non-associativity, batching); two identical
runs disagree on roughly a third of per-task outcomes. The seed therefore barely controls variance.
The design (advisor-agreed) handles this with **single-seed multi-LLM + repeats**, with the
statistics placed at the right level:

- Single seed (42); **four audited base agent models** (DeepSeek / GLM / MiMo / one open-source mid),
  with the **monitor extractor model fixed** and the **user-simulator model fixed** as controls;
  **K = 5 repeats** per (domain, model).
- **Significance** → per-task paired **McNemar** test (V_answer vs V_structural) within each model,
  plus bootstrap CIs over tasks — hundreds of paired tasks give high power on a single model.
- **Generality** → cross-model distribution (mean±std, p25/p75) as the box/violin chart. Four model
  points carry generality, *not* significance.
- **Noise** → within-model std across the K repeats, shown to be smaller than the cross-model
  separation.

The claim-extraction stage is the only neural monitor component; its quality is validated by a small
direct spot-check so all downstream symbolic verification, scoring, and verdicts are deterministic.

## Contributions

1. **An observability characterization of black-box post-hoc agent auditing**, organizing failures
   by the locus of their ground truth and establishing (not assuming) that the answer-channel blind
   spot is a property of the channel, not of extraction.
2. **A locus-of-ground-truth taxonomy** (answer / trace / state / evidence / intent) used as a
   domain-independent analysis lens over real benchmark failures.
3. **A claim-level neuro-symbolic audit pipeline** with a benchmark-adapter pattern (claims neural;
   verification, scoring, intervention, trace symbolic and deterministic).
4. **An evaluation entirely on a recognized, execution-grounded benchmark** (τ-bench), across four
   base models, with a statistically principled single-seed multi-LLM + per-task-paired design.
5. **A boundary result**: the irreducible intent-local class that no black-box channel can reach,
   identified on real benchmark data via the monitor-vs-oracle gap.

## Out of Scope

1. No model optimization (no fine-tuning / RLHF / reward models).
2. No universal hallucination-detection claim — only externally verifiable failures.
3. No claim of universal domain generality — each domain needs grounding artifacts and verifier logic.
4. No evaluation of subjective / unverifiable answers.
5. Verifiers are domain-specific audit signals, not infallible truth.

## Core Thesis Claim

ReliableGuard characterizes the **observability limits of black-box, post-hoc auditing of tool-using
LLM agents**: an agent's final answer is only a partial observation of its execution; certain failure
classes (policy/trace and state-effect) are unobservable through the answer channel by construction
rather than by extraction weakness; adding tool-trace and state-transition channels restores
observability for exactly those classes, robustly across base models; and the residual boundary is
the intent-local class, where the truth lives in the user's goal and no observable artifact reaches
it. Demonstrated entirely on the recognized τ-bench benchmark with its own execution-based ground
truth.
