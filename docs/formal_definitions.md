# Formal Definitions for ReliableGuard

> **Re-grounded 2026-06-09 (τ-bench pivot).** The metric machinery below (evidence-state
> enumeration, FAR / detection / scoring) **carries over unchanged** to the new τ-bench-based
> design, with two substitutions: (1) the per-task ground-truth label is now the **τ-bench reward**
> (1 pass / 0 fail), replacing the old self-made safe/risky label; (2) the failure taxonomy is the
> **locus of ground truth** (answer / trace / state / evidence / intent-local), replacing the old
> F0–F5 *injection* categories and the Type I/Type II split — any Section referring to F0–F5 /
> Type I–II is **historical**. The verdict space also includes `AUDIT_FAILED` (and PASS may be
> split into PASS_VERIFIED / PASS_UNCHECKED). Authoritative design:
> [tau_bench_experiment_design.md](tau_bench_experiment_design.md).

This document defines the formal concepts used by ReliableGuard to support three thesis-level goals: quantification, standardization, and traceability. The scope is limited to externally verifiable failures in tool-using LLM agents with observable grounding artifacts, such as database state, retrievable knowledge-base documents, and tool execution traces.

## 1. Evidence State Enumeration

ReliableGuard maps each verified claim to an `evidence_state`. This state represents the relationship between an extracted claim and the available domain evidence.

| Evidence State | Meaning | Example Trigger Condition |
| --- | --- | --- |
| `supported` | The claim is consistent with the available grounding evidence. | The agent claims that order `#42` has amount `200`, and the database record for order `#42` also has amount `200`. |
| `contradicted` | The claim conflicts with the available grounding evidence. | The agent claims that a reference was published in `2021`, but DOI metadata shows publication year `2019`. |
| `unsupported` | The claim is checkable in principle, but the available evidence is insufficient to support it. | The agent claims that a paper is "widely cited", but the offline metadata source does not contain citation-count evidence. |
| `not_found` | The entity required to verify the claim cannot be found in the grounding source. | The agent provides a DOI that does not resolve in the local metadata fixture or configured DOI source. |
| `unverifiable` | The claim is not suitable for domain verification because it is subjective, ambiguous, too broad, or outside the verifier contract. | The agent states that a paper is "important and influential", or that "all references are valid" without enumerating reference-level claims. |

The evidence state is assigned at the claim level:

$$
e_i \in E = \{\text{supported}, \text{contradicted}, \text{unsupported}, \text{not\_found}, \text{unverifiable}\}
$$

where \(e_i\) is the evidence state for claim \(c_i\).

## 2. Core Metrics

Let \(T\) be a set of evaluated tasks. Each task \(t \in T\) has an expected safety label:

$$
y_t \in \{\text{safe}, \text{risky}\}
$$

Each evaluated system produces an aggregate intervention verdict:

$$
v_t \in \{\text{PASS}, \text{WARN}, \text{BLOCK}\}
$$

For metric definitions, `PASS` is treated as acceptance, while `WARN` and `BLOCK` are treated as risk detection actions:

$$
\operatorname{accept}(v_t) =
\begin{cases}
1 & \text{if } v_t = \text{PASS} \\
0 & \text{otherwise}
\end{cases}
$$

$$
\operatorname{detect}(v_t) =
\begin{cases}
1 & \text{if } v_t \in \{\text{WARN}, \text{BLOCK}\} \\
0 & \text{otherwise}
\end{cases}
$$

### 2.1 False Acceptance Rate (FAR)

**Purpose.** False Acceptance Rate measures the proportion of risky tasks that are incorrectly allowed to pass.

**Symbol definition.**

- \(T_{\text{risky}} = \{t \in T \mid y_t = \text{risky}\}\)
- \(v_t\) is the aggregate verdict for task \(t\)

**Formula.**

$$
\operatorname{FAR}
= \frac{\sum_{t \in T_{\text{risky}}} \mathbb{1}[v_t = \text{PASS}]}
{|T_{\text{risky}}|}
$$

**Range.**

$$
0 \leq \operatorname{FAR} \leq 1
$$

**Intuition.** Lower is better. A FAR of \(0\) means no risky tasks were accepted. A FAR of \(1\) means all risky tasks were accepted.

### 2.2 False Alarm Rate

**Purpose.** False Alarm Rate measures the proportion of safe tasks that are incorrectly warned or blocked.

**Symbol definition.**

- \(T_{\text{safe}} = \{t \in T \mid y_t = \text{safe}\}\)
- \(v_t\) is the aggregate verdict for task \(t\)

**Formula.**

$$
\operatorname{FalseAlarmRate}
= \frac{\sum_{t \in T_{\text{safe}}} \mathbb{1}[v_t \in \{\text{WARN}, \text{BLOCK}\}]}
{|T_{\text{safe}}|}
$$

**Range.**

$$
0 \leq \operatorname{FalseAlarmRate} \leq 1
$$

**Intuition.** Lower is better. A high false alarm rate indicates that the harness is overly conservative and blocks or warns on many acceptable outputs. This metric is written in full to avoid confusion with FAR, which denotes False Acceptance Rate.

### 2.3 Risk Detection Rate (RDR)

**Purpose.** Risk Detection Rate measures the proportion of risky tasks that are detected by the audit or intervention mechanism.

**Symbol definition.**

- \(T_{\text{risky}} = \{t \in T \mid y_t = \text{risky}\}\)
- Risk detection occurs when \(v_t \in \{\text{WARN}, \text{BLOCK}\}\)

**Formula.**

$$
\operatorname{RDR}
= \frac{\sum_{t \in T_{\text{risky}}} \mathbb{1}[v_t \in \{\text{WARN}, \text{BLOCK}\}]}
{|T_{\text{risky}}|}
$$

Equivalently:

$$
\operatorname{RDR} = 1 - \operatorname{FAR}
$$

when every risky task receives exactly one aggregate verdict in \(\{\text{PASS}, \text{WARN}, \text{BLOCK}\}\). In the implementation, some rows may produce `ERROR` or `NOT_TRIGGERED`. These rows remain in the denominator but are neither false acceptances nor detected risks, so \(\operatorname{RDR} + \operatorname{FAR}\) can be less than 1.

**Range.**

$$
0 \leq \operatorname{RDR} \leq 1
$$

**Intuition.** Higher is better. RDR is the positive counterpart of FAR for risky tasks.

### 2.4 Safe Pass, Pass Rate, and Gate Action Rate

**Safe Pass Rate.** Safe Pass Rate measures the proportion of safe tasks that are correctly accepted:

$$
\operatorname{SafePassRate}
= \frac{\sum_{t \in T_{\text{safe}}} \mathbb{1}[v_t = \text{PASS}]}
{|T_{\text{safe}}|}
$$

Higher is better. In the implementation, \(\operatorname{SafePassRate} + \operatorname{FalseAlarmRate}\) can be less than 1 when safe tasks produce `ERROR` or `NOT_TRIGGERED`.

**Pass Rate.** Pass Rate is exact task-level verdict accuracy:

$$
\operatorname{PassRate}
= \frac{\sum_{t \in T} \mathbb{1}[v_t = \hat{v}_t]}
{|T|}
$$

where \(\hat{v}_t\) is the expected benchmark verdict after normalizing scenario labels. This metric is stricter than RDR: if a risky task expects `BLOCK` but the system returns `WARN`, it counts as detected risk for RDR but not as an exact pass.

**Gate Action Rate.** Gate Action Rate measures how often the system actively warns or blocks:

$$
\operatorname{GateActionRate}
= \frac{\sum_{t \in T} \mathbb{1}[v_t \in \{\text{WARN}, \text{BLOCK}\}]}
{|T|}
$$

It is especially useful for Set B, where the question is not only whether the system is correct but also how often it intervenes under generalization stress.

### 2.5 Task Claim Coverage Rate (TCCR)

**Purpose.** Task Claim Coverage Rate measures the proportion of tasks for which the reliability pipeline produced at least one grounded (non-unverifiable) claim. A grounded claim is one whose evidence state is supported, contradicted, unsupported, or not_found.

**Symbol definition.**

- \(T\) is the set of evaluated tasks where the verifier ran (V2 and V3 only).
- \(\operatorname{has\_grounded\_claim}(t) = 1\) if task \(t\) has at least one claim with \(e_i \neq \texttt{unverifiable}\), i.e., \((\text{supported\_count} + \text{contradicted\_count} + \text{unsupported\_count} + \text{not\_found\_count}) > 0\) in the pipeline report.

**Formula.**

$$
\operatorname{TCCR}
= \frac{\sum_{t \in T} \mathbb{1}[\operatorname{has\_grounded\_claim}(t)]}
{|T|}
$$

**Range.**

$$
0 \leq \operatorname{TCCR} \leq 1
$$

**Intuition.** Higher is better. A low TCCR indicates that the claim extractor is producing mostly unverifiable aggregate claims, preventing the verifier from grounding its audit. For V1 (no verifier), TCCR should be interpreted as no verifier coverage rather than as an extractor-quality signal.

### 2.6 Evidence State Distribution

**Purpose.** Evidence-state distribution reports the average number of claims in each evidence state among tasks where the verifier produced at least one claim-level evidence count.

For each task \(t\), ReliableGuard records:

$$
n_t^{sup}, n_t^{con}, n_t^{uns}, n_t^{unv}, n_t^{nf}
$$

corresponding to `supported_count`, `contradicted_count`, `unsupported_count`, `unverifiable_count`, and `not_found_count`.

Let:

$$
T_E = \{t \in T \mid n_t^{sup}+n_t^{con}+n_t^{uns}+n_t^{unv}+n_t^{nf} > 0\}
$$

The average supported count is:

$$
\operatorname{AvgSupported}
= \frac{\sum_{t \in T_E} n_t^{sup}}{|T_E|}
$$

The same form applies to contradicted, unsupported, unverifiable, and not_found counts. The evidence-state coverage field is:

$$
\operatorname{EvidenceStateCoverage} = \frac{|T_E|}{|T|}
$$

**Implementation fields.** `compute_metrics` reports `avg_supported_count`, `avg_contradicted_count`, `avg_unsupported_count`, `avg_unverifiable_count`, `avg_not_found_count`, and `evidence_state_coverage`.

### 2.7 Stage Latency and Token Cost

ReliableGuard records per-stage audit latency in `ReliabilityReport.stage_latencies`. The aggregated metrics report mean and p95 latency for:

- `extract_claims`
- `classify_verifiability`
- `verify_claims`
- `score_risks`
- `decide_interventions`
- `generate_report`
- `total_pipeline`

For each stage \(s\), with observed latency values \(L_s = \{\ell_1, \ldots, \ell_m\}\):

$$
\operatorname{MeanLatency}_s = \frac{1}{m}\sum_{i=1}^{m}\ell_i
$$

and p95 is computed from the sorted latency list using the experiment code's percentile index rule.

Token usage is aggregated from positive token counts in result rows or `state["total_tokens"]`:

$$
\operatorname{AvgTokens} = \frac{\sum_{t \in T_\tau}\tau_t}{|T_\tau|}
$$

where \(T_\tau\) contains only tasks with \(\tau_t > 0\). The implementation fields are `stage_latency_mean_ms`, `stage_latency_p95_ms`, `avg_tokens`, and `total_tokens_sum`.

## 3. Domain Verifier Adapter Interface Contract

ReliableGuard standardizes domain-specific verification through a verifier adapter contract. Each adapter verifies one claim against one domain context and returns one claim-level verification result.

### 3.1 Input Contract

Each verifier adapter receives:

- `claim`: the natural-language or structured claim to verify.
- `claim_type`: the semantic type of the claim, such as `order_state`, `payment_amount`, `doi_metadata`, `bibliographic_title`, or `reference_existence`.
- `domain_context`: the domain-specific evidence environment, such as database handles, task metadata, tool execution traces, local fixtures, PDF extraction output, or configured metadata sources.

### 3.2 Output Contract

Each verifier adapter returns:

- `evidence_state`: one value from the evidence-state enumeration.
- `confidence`: a numeric confidence score in \([0, 1]\).
- `evidence_source`: a stable identifier for the grounding source used by the verifier.
- `raw_evidence`: the relevant evidence payload used to support the decision.

### 3.3 Typed Interface

```python
from dataclasses import dataclass
from typing import Any, Literal, Protocol

EvidenceState = Literal[
    "supported",
    "contradicted",
    "unsupported",
    "not_found",
    "unverifiable",
]

@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    claim_type: str
    attributes: dict[str, Any]

@dataclass(frozen=True)
class DomainContext:
    domain: str
    query: str
    task_metadata: dict[str, Any]
    tool_trace: list[dict[str, Any]]
    state_snapshot_before: dict[str, Any] | None
    state_snapshot_after: dict[str, Any] | None
    evidence_sources: dict[str, Any]

@dataclass(frozen=True)
class VerificationResult:
    claim_id: str
    evidence_state: EvidenceState
    confidence: float
    evidence_source: str
    raw_evidence: Any

class DomainVerifierAdapter(Protocol):
    def verify_claim(
        self,
        claim: Claim,
        claim_type: str,
        domain_context: DomainContext,
    ) -> VerificationResult:
        ...
```

### 3.4 Adapter Constraints

Verifier adapters must satisfy the following constraints.

1. **Determinism.**  
   Given the same claim, claim type, domain context, and evidence snapshot, the verifier should return the same result:

   $$
   (c_i, \tau_i, D)_{t_1} = (c_i, \tau_i, D)_{t_2}
   \Rightarrow
   V_{t_1}(c_i, \tau_i, D) = V_{t_2}(c_i, \tau_i, D)
   $$

   where \(V\) is the verifier, \(c_i\) is the claim, \(\tau_i\) is the claim type, \(D\) is the domain context, and \(t_1,t_2\) denote two separate invocations over the same evidence snapshot.

2. **Offline by default.**  
   Benchmark verification should use local fixtures, database state, cached metadata, or deterministic test sources by default. Network-backed verification may be enabled for diagnostics or case studies, but should not be required for deterministic benchmark runs.

3. **Single-claim independence.**  
   Each verifier call should verify one claim independently:

   $$
   V(c_i, \tau_i, D) \rightarrow r_i
   $$

   where \(r_i\) is the verification result for claim \(c_i\). Cross-claim aggregation should occur in the risk scoring or policy stage, not inside the verifier adapter.

4. **Evidence transparency.**  
   Every non-`unverifiable` result should expose the evidence source and raw evidence used to produce the decision, unless the evidence is unavailable or intentionally redacted by the domain context.

5. **No hidden policy decisions.**  
   Verifier adapters should report evidence states, not final intervention decisions. PASS, WARN, and BLOCK decisions belong to the intervention policy layer.

## 4. Claim-Level Traceability Chain

ReliableGuard defines a traceability chain from extracted claims to the final aggregate verdict.

Let the agent answer be \(A\), and let the claim extractor produce a set of claims:

$$
C = \{c_1, c_2, \ldots, c_n\} = \operatorname{Extract}(A)
$$

For each claim \(c_i\), the audit chain is:

$$
c_i
\rightarrow l_i
\rightarrow e_i
\rightarrow s_i
\rightarrow a_i
$$

where:

- \(c_i\) is the extracted claim.
- \(l_i\) is the verifiability label.
- \(e_i\) is the evidence state.
- \(s_i\) is the claim-level risk score.
- \(a_i\) is the claim-level intervention action.

The aggregate verdict is then computed from all claim-level outputs and optional structural audit signals:

$$
V_{\text{agg}}
= \operatorname{AggregatePolicy}(\{a_i\}_{i=1}^{n}, \{s_i\}_{i=1}^{n}, S)
$$

where \(S\) denotes structural audit signals, such as tool execution violations or database state-transition anomalies.

### 4.1 Traceability Steps

| Step | Input | Output | Purpose |
| --- | --- | --- | --- |
| `claim` | Agent answer \(A\) | Claim \(c_i\) | Converts unstructured answer text into audit units. |
| `verifiability_label` | Claim \(c_i\) | Label \(l_i\) | Determines whether the claim is suitable for verification. |
| `evidence_state` | Claim \(c_i\), label \(l_i\), domain context \(D\) | Evidence state \(e_i\) | Checks the claim against grounding evidence. |
| `risk_score` | Evidence state \(e_i\), confidence, claim type | Score \(s_i \in [0,1]\) | Quantifies claim-level reliability risk. |
| `intervention_action` | Risk score \(s_i\), policy thresholds | Action \(a_i \in \{\text{PASS}, \text{WARN}, \text{BLOCK}\}\) | Determines claim-level policy response. |
| `aggregate_verdict` | Claim actions, risk scores, structural signals | Verdict \(V_{\text{agg}}\) | Produces task-level PASS, WARN, or BLOCK. |
| `trace_report` | All intermediate artifacts | Trace report \(R\) | Records the audit path for inspection and reproducibility. |

The full trace report can be represented as:

$$
R =
\left(
A,
\{(c_i, l_i, e_i, s_i, a_i)\}_{i=1}^{n},
V_{\text{agg}}
\right)
$$

### 4.2 Detection Scope Boundary: Type I versus Type II Failures

This boundary is an **observability** statement. The final answer \(A\) is a partial, self-reported observation of the true execution trajectory; the claim-level pipeline can only audit what is recoverable from \(A\) together with the domain state \(D_{\text{after}}\) at audit time. A failure class is *unobservable* through this channel exactly when there exists a correct execution that is indistinguishable from the failing one under the observable artifacts. The Type I / Type II split below partitions failures by the **locus of their ground truth** relative to that observation, and thereby determines observability: Type I ground truth is recoverable from \((A, D_{\text{after}})\); Type II ground truth resides in the pre-execution policy predicate or the pre/post state transition, neither of which is exposed by \(A\) or by \(D_{\text{after}}\) alone. This is the formal basis for the claim, established empirically in RQ1, that the final-answer blind spot is a property of the observation channel rather than of extraction quality.

**Type I: Factual inconsistency failures.**

A failure is Type I if the agent's final answer contains claims that contradict or are unsupported by the observable domain state at the time of verification:

$$
\text{Type I}: \exists\, c_i \in C \text{ such that } e_i \in \{\texttt{contradicted}, \texttt{not\_found}\}
\text{ when } V(c_i, D_{\text{after}}) \text{ is evaluated.}
$$

Type I failures are detectable by post-hoc claim verification when the relevant claim is present in \(A\) and extracted into \(C\). The claim pipeline acts as a post-hoc consistency checker between extracted claims and the current domain state, so its empirical coverage still depends on final-answer wording and claim extraction quality.

- **F3 (fabricated claim)**: The agent asserts an entity that does not exist in \(D_{\text{after}}\). Evidence state: \(\texttt{not\_found}\).
- **F4 (false-success)**: The tool reports success but \(D_{\text{after}} = D_{\text{before}}\). If the agent's answer contains an extracted claim of a completed operation, that claim contradicts \(D_{\text{after}}\). Evidence state: \(\texttt{contradicted}\). Structural audit covers this case more directly by checking the state transition itself.

**Type II: Policy violation failures.**

A failure is Type II if the agent initiated an operation that violated a pre-execution policy constraint, yet the resulting domain state \(D_{\text{after}}\) is factually consistent with the agent's final answer:

$$
\text{Type II}: \forall\, c_i \in C,\ e_i = \texttt{supported}
\text{ when } V(c_i, D_{\text{after}}) \text{ is evaluated,}
\text{ yet } P(T_{\text{args}}) = \texttt{violated}
$$

where \(P\) is a pre-condition policy and \(T_{\text{args}}\) are the tool arguments supplied at execution time.

Type II failures are not detectable by post-hoc claim verification. The domain state is correct; the violation occurred in the decision to permit the operation, not in its outcome. Detecting Type II failures requires structural audit: evaluating \(P(T_{\text{args}})\) before the tool executes.

- **F2 (policy violation)**: An agent creates an order with amount = 8000. The database records amount = 8000 correctly. All claims in \(A\) are \(\texttt{supported}\). The violation is that amount \(> 5000\) requires approval, a constraint that exists in the pre-execution policy \(P\), not in \(D_{\text{after}}\).

**Empirical confirmation.**

The current post-fix V3 versus V3\_NoStructural controlled ablation on the ecommerce Set A benchmark confirms that structural audit improves both policy precondition checking and state-transition checking:

| Metric / failure type | V3\_NoStructural (no structural audit) | V3 (structural audit enabled) |
| --- | ---: | ---: |
| Overall ecommerce RDR | 0.237 | 0.640 |
| Overall ecommerce FAR | 0.762 | 0.231 |
| F2 policy violation detection | 0.225 | 0.735 |
| F4 false-success detection | 0.353 | 0.827 |

F2 remains the clearest Type II case: the resulting database state may be factually consistent with the agent answer, while the operation violates a pre-execution policy. F4 is a Type I state inconsistency, but the latest result shows that final-answer claim verification is not sufficient in practice because it depends on the answer wording and the extractor. The post-execution structural check detects the state-transition anomaly directly.

This boundary has a design implication for new domain instantiations: structural audit is necessary when target failures involve policy preconditions, permission constraints, transaction side effects, or environment state transitions that are not reliably exposed as final-answer claims.

## 5. Risk Scoring Framework

ReliableGuard maps each verified claim to a risk score using a two-factor model: claim-type weight and evidence-state penalty. This section formalizes the scoring framework that converts evidence states into a unified reliability score.

### 5.1 Claim-type Weight Function

Each claim type $\tau$ is assigned a weight $w(\tau) \in [0, 1]$ that reflects the precision and verifiability requirements of that claim type.

$$
w(\tau) = \begin{cases}
1.0 & \text{if } \tau \in \{\texttt{existence}, \texttt{numeric}\} \\
0.9 & \text{if } \tau = \texttt{relational} \\
0.8 & \text{if } \tau = \texttt{attribute} \\
0.7 & \text{if } \tau = \texttt{temporal} \\
0.5 & \text{if } \tau = \texttt{semantic}
\end{cases}
$$

Existence and numeric claims carry the highest weight because they are binary and precise: an entity either exists or does not, an amount either matches or it does not. Semantic claims carry the lowest weight because they are inherently imprecise and context-dependent.

### 5.2 Evidence-state Penalty Function

Each evidence state $e$ is assigned a penalty $p(e) \in [0, 1]$ that reflects how strongly that state indicates a reliability risk.

$$
p(e) = \begin{cases}
0.0 & \text{if } e = \texttt{supported} \\
0.6 & \text{if } e = \texttt{unsupported} \\
0.4 & \text{if } e = \texttt{unverifiable} \\
1.0 & \text{if } e \in \{\texttt{contradicted}, \texttt{not\_found}\}
\end{cases}
$$

The penalty for \texttt{unverifiable} is set to $0.4$ rather than $0.0$ to reflect that a high proportion of unverifiable claims reduces audit coverage and should be penalized. If unverifiable claims were penalty-free, an agent producing only aggregate or subjective statements would receive a perfect reliability score without any meaningful verification having occurred.

### 5.3 Claim-level Risk Score

For claim $c_i$ with type $\tau_i$ and verification result $e_i$, the claim-level risk score is:

$$
s_i = \min(1.0,\ w(\tau_i) \times p(e_i))
$$

The risk level is then:

$$
\text{risk\_level}(s_i) = \begin{cases}
\texttt{high}   & \text{if } s_i \geq 0.75 \\
\texttt{medium} & \text{if } 0.35 \leq s_i < 0.75 \\
\texttt{low}    & \text{if } s_i < 0.35
\end{cases}
$$

### 5.4 Aggregate Reliability Score

For a task with $n$ extracted claims, the aggregate reliability score is:

$$
\text{reliability\_score} = \max\!\left(0,\ 1 - \frac{\sum_{i=1}^{n} w(\tau_i) \times p(e_i)}{\sum_{i=1}^{n} w(\tau_i)}\right)
$$

A reliability score of $1.0$ means all claims are fully supported. A score of $0.0$ means all claims are contradicted or not found, weighted by their type importance.

### 5.5 Unified Scoring Across Domains

The claim-type weight function $w$ and evidence-state penalty function $p$ are domain-independent. Domain-specific verifier adapters produce evidence states from domain evidence sources, but the risk scoring formula is identical for both ecommerce and academic reference domains. This allows reliability scores to be compared across domains within the same measurement framework, supporting the cross-domain standardization claim of the thesis.

## 6. Trace Report Schema

The trace report records task-level context and claim-level audit artifacts. The schema below follows the current implementation written by `src/reliableguard/trace/trace_logger.py`. In the implementation, the ordered audit path is represented by the nested `traces` array. The file path to the written trace log may be referenced in the generated reliability report summary, but `trace_path` is not a top-level key inside the trace JSON payload.

```json
{
  "type": "object",
  "required": [
    "run_id",
    "run_started_at",
    "domain",
    "query",
    "answer",
    "summary",
    "traces"
  ],
  "properties": {
    "run_id": {
      "type": "string",
      "description": "Stable identifier for the evaluated run."
    },
    "run_started_at": {
      "type": "string",
      "description": "UTC run stamp used to construct the run identifier."
    },
    "domain": {
      "type": "string",
      "description": "Evaluation domain, such as ecommerce or reference."
    },
    "query": {
      "type": "string",
      "description": "Original user query or benchmark prompt."
    },
    "answer": {
      "type": "string",
      "description": "Final natural-language answer produced by the agent."
    },
    "summary": {
      "type": "object",
      "required": ["total_claims", "counts", "items"],
      "properties": {
        "total_claims": {
          "type": "integer",
          "minimum": 0,
          "description": "Number of extracted claims in the trace log."
        },
        "counts": {
          "type": "object",
          "description": "Evidence-state counts over all claim traces.",
          "properties": {
            "supported": { "type": "integer", "minimum": 0 },
            "contradicted": { "type": "integer", "minimum": 0 },
            "unsupported": { "type": "integer", "minimum": 0 },
            "unverifiable": { "type": "integer", "minimum": 0 },
            "not_found": { "type": "integer", "minimum": 0 }
          }
        },
        "items": {
          "type": "array",
          "description": "Compact claim-level trace summary.",
          "items": {
            "type": "object",
            "required": [
              "claim_id",
              "claim",
              "evidence_state",
              "source",
              "risk_level",
              "intervention",
              "reason"
            ],
            "properties": {
              "claim_id": { "type": "string" },
              "claim": { "type": "string" },
              "evidence_state": {
                "type": "string",
                "enum": [
                  "supported",
                  "contradicted",
                  "unsupported",
                  "not_found",
                  "unverifiable"
                ]
              },
              "source": { "type": ["string", "null"] },
              "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"]
              },
              "intervention": {
                "type": "string",
                "enum": ["PASS", "WARN", "BLOCK"]
              },
              "reason": { "type": "string" }
            }
          }
        }
      }
    },
    "traces": {
      "type": "array",
      "description": "Claim-level audit chain represented as nested claim, verifiability, verification, risk, and intervention objects.",
      "items": {
        "type": "object",
        "required": [
          "claim",
          "verifiability",
          "verification",
          "risk",
          "intervention"
        ],
        "properties": {
          "claim": {
            "type": "object",
            "required": ["claim_id", "text", "claim_type"],
            "properties": {
              "claim_id": { "type": "string" },
              "text": { "type": "string" },
              "claim_type": {
                "type": "string",
                "enum": [
                  "existence",
                  "attribute",
                  "numeric",
                  "temporal",
                  "relational",
                  "semantic"
                ]
              },
              "entities": { "type": "object" },
              "attribute": { "type": ["string", "null"] },
              "value": {},
              "unit": { "type": ["string", "null"] },
              "time_range": { "type": ["string", "null"] },
              "certainty": {
                "type": "string",
                "enum": ["certain", "uncertain", "abstained"]
              },
              "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
              }
            }
          },
          "verifiability": {
            "type": "string",
            "enum": [
              "fully_verifiable",
              "partially_verifiable",
              "unverifiable"
            ],
            "description": "Claim-level verifiability label."
          },
          "verification": {
            "type": "object",
            "required": ["claim_id", "evidence_state", "confidence", "reason"],
            "properties": {
              "claim_id": { "type": "string" },
              "evidence_state": {
                "type": "string",
                "enum": [
                  "supported",
                  "contradicted",
                  "unsupported",
                  "not_found",
                  "unverifiable"
                ]
              },
              "evidence_value": {},
              "source": { "type": ["string", "null"] },
              "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
              },
              "reason": { "type": "string" }
            }
          },
          "risk": {
            "type": "object",
            "required": ["claim_id", "risk_level", "score", "reason"],
            "properties": {
              "claim_id": { "type": "string" },
              "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"]
              },
              "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
              },
              "reason": { "type": "string" }
            }
          },
          "intervention": {
            "type": "object",
            "required": ["claim_id", "action", "reason"],
            "properties": {
              "claim_id": { "type": "string" },
              "action": {
                "type": "string",
                "enum": ["PASS", "WARN", "BLOCK"]
              },
              "reason": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

This schema supports traceability by ensuring that each claim trace links the original claim to its verifiability label, verification result, risk score, and intervention action. The aggregate verdict and reliability score are stored in the `ReliabilityReport` object generated by the pipeline, while the trace JSON stores the detailed claim-level audit artifacts used to explain that report.
