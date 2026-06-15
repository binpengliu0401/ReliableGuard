# Formal Definitions for ReliableGuard

> **Updated 2026-06-15 (τ-bench metric suite).** Ground-truth label = τ-bench reward (1 pass / 0 fail).
> Failure taxonomy = locus of ground truth (answer-local / trace-local / state-local / intent-local).
> Verdict space = {PASS\_VERIFIED, PASS\_UNCHECKED, BLOCK, AUDIT\_FAILED}. Core metric suite includes
> FAR / RDR, ΔRDR (Detection Lift), CDR_κ (Consistent Detection Rate), locus distribution π_ℓ,
> McNemar paired test, and bootstrap 95% CIs. Old safe/risky labels, F0–F5 categories, Type I/II
> split, and ecommerce/reference empirical tables are superseded. Authoritative experiment design:
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

### 2.0 Ground-Truth Label and Verdict Space

**Ground-truth label.** The τ-bench reward is the sole gold standard:

$$
y_t = \text{reward}_t \in \{1, 0\}
$$

where \(y_t = 1\) means the agent completed the task correctly (τ-bench `calculate_reward()` = 1.0) and \(y_t = 0\) means it failed. Define:

$$
T_{\text{fail}} = \{t \in T \mid y_t = 0\}, \quad T_{\text{pass}} = \{t \in T \mid y_t = 1\}
$$

**Verdict space.** Each monitor configuration \(V \in \{V_{\text{answer}},\ V_{\text{structural}}\}\) produces one verdict per trajectory:

$$
v_t^V \in \{\text{PASS\_VERIFIED},\ \text{PASS\_UNCHECKED},\ \text{BLOCK},\ \text{AUDIT\_FAILED}\}
$$

For binary detection metrics, PASS\_VERIFIED and PASS\_UNCHECKED collapse to PASS:

$$
\tilde{v}_t^V = \begin{cases} \text{PASS} & \text{if } v_t^V \in \{\text{PASS\_VERIFIED},\ \text{PASS\_UNCHECKED}\} \\ v_t^V & \text{otherwise} \end{cases}
$$

AUDIT\_FAILED is treated as a non-PASS gate action: when the extractor produces no claims, the monitor conservatively blocks rather than silently accepts.

**Detection and acceptance operators.**

$$
\operatorname{detect}(v) = \mathbb{1}[v \neq \text{PASS}], \quad \operatorname{accept}(v) = \mathbb{1}[v = \text{PASS}]
$$

### 2.1 False Acceptance Rate (FAR)

**Purpose.** Fraction of failed tasks (reward=0) that the monitor incorrectly passes — the primary miss-rate.

**Symbol definition.**

- \(T_{\text{fail}} = \{t \in T \mid y_t = 0\}\)
- \(\tilde{v}_t^V\) is the collapsed aggregate verdict for monitor configuration \(V\)

**Formula.**

$$
\operatorname{FAR}(V)
= \frac{\sum_{t \in T_{\text{fail}}} \mathbb{1}[\tilde{v}_t^V = \text{PASS}]}
{|T_{\text{fail}}|}
$$

**Range.** \(0 \leq \operatorname{FAR}(V) \leq 1\). Lower is better. FAR = 0 means no failed task was silently passed; FAR = 1 means every failed task was missed.

### 2.2 False Alarm Rate

**Purpose.** Fraction of successful tasks (reward=1) that the monitor incorrectly flags — the operational cost of using the monitor on correct agent outputs.

**Symbol definition.**

- \(T_{\text{pass}} = \{t \in T \mid y_t = 1\}\)

**Formula.**

$$
\operatorname{FalseAlarmRate}(V)
= \frac{\sum_{t \in T_{\text{pass}}} \mathbb{1}[\tilde{v}_t^V \neq \text{PASS}]}
{|T_{\text{pass}}|}
$$

**Range.** \(0 \leq \operatorname{FalseAlarmRate}(V) \leq 1\). Lower is better. Written in full to avoid confusion with FAR (False Acceptance Rate). A high FalseAlarmRate indicates the monitor over-fires on correct outputs — limiting practical utility without reducing the missed-failure burden.

### 2.3 Risk Detection Rate (RDR)

**Purpose.** Fraction of failed tasks (reward=0) detected by the monitor — the positive counterpart of FAR.

**Formula.**

$$
\operatorname{RDR}(V)
= \frac{\sum_{t \in T_{\text{fail}}} \mathbb{1}[\tilde{v}_t^V \neq \text{PASS}]}
{|T_{\text{fail}}|}
= 1 - \operatorname{FAR}(V)
$$

**Range.** \(0 \leq \operatorname{RDR}(V) \leq 1\). Higher is better. AUDIT\_FAILED rows count as detected (non-PASS), so \(\operatorname{RDR}(V) + \operatorname{FAR}(V) = 1\) when every row carries a verdict.

### 2.4 Detection Lift (ΔRDR)

**Purpose.** Headline metric for RQ2: the improvement in detection rate when the structural observation channels (state + trace) are added over the answer-only baseline.

**Formula.**

$$
\Delta\operatorname{RDR} = \operatorname{RDR}(V_{\text{structural}}) - \operatorname{RDR}(V_{\text{answer}})
$$

**Interpretation.** Positive \(\Delta\operatorname{RDR}\) across all four audited models (deepseek-v4-pro, mimo-v2.5-pro, glm-4.7-flash, qwen3.6-flash) is the primary RQ2 empirical claim. Significance is assessed per-model via McNemar's test (§2.7). A positive \(\Delta\operatorname{RDR}\) with stable or decreasing FalseAlarmRate constitutes an unambiguous improvement: more failures caught without more correct outputs flagged.

### 2.5 Consistent Detection Rate (CDR$_\kappa$)

**Purpose.** Quantifies detection reliability across K=10 repeat runs per task. A monitor that detects a failure only 1 out of 10 runs is practically unreliable even if its mean RDR looks high. Adapted from τ-bench's pass^k metric; addresses LLM non-determinism (~33% outcome flip rate across runs on DeepSeek/OpenRouter at temp=0+seed).

**Formula.** For failed task \(t\) under model \(m\) and monitor \(V\) across \(K = 10\) runs:

$$
\hat{p}_{\text{detect}}(t, V, m) = \frac{1}{K}\sum_{k=1}^{K} \mathbb{1}[\tilde{v}_{t,k}^V \neq \text{PASS}]
$$

$$
\operatorname{CDR}_\kappa(V, m) = \frac{|\{t \in T_{\text{fail}} \mid \hat{p}_{\text{detect}}(t, V, m) \geq \kappa/K\}|}{|T_{\text{fail}}|}
$$

**Recommended thresholds.** \(\kappa \in \{5, 7, 9\}\) for a K=10 design — majority-consistent (\(\geq 50\%\)), strongly consistent (\(\geq 70\%\)), and near-certain (\(\geq 90\%\)). CDR\(_5\) is the primary threshold; CDR\(_9\) bounds the stable detection floor.

### 2.6 Locus Distribution (π$_\ell$)

**Purpose.** Decomposes failed tasks (reward=0) by the locus of their ground truth. Measures what fraction of failures are in principle detectable by each observation channel, and bounds the maximum achievable RDR for any black-box monitor.

**Formula.**

$$
\pi_\ell = \frac{|\{t \in T_{\text{fail}} \mid \operatorname{locus}(t) = \ell\}|}{|T_{\text{fail}}|}, \quad \ell \in \{\text{answer-local},\ \text{trace-local},\ \text{state-local},\ \text{intent-local}\}
$$

**Constraint.** \(\sum_\ell \pi_\ell = 1\).

**Theoretical detection ceiling.** For \(V_{\text{structural}}\) (which observes answer + state + trace):

$$
\operatorname{RDR}(V_{\text{structural}})^* \leq 1 - \pi_{\text{intent-local}}
$$

The empirical gap \([1 - \pi_{\text{intent-local}}] - \operatorname{RDR}(V_{\text{structural}})\) measures the monitor's implementation shortfall above the theoretical limit. RQ3 reports \(\pi_{\text{intent-local}}\) as the irreducible observability boundary.

### 2.7 Paired Significance Test (McNemar)

**Purpose.** Test whether \(\Delta\operatorname{RDR}\) is statistically significant for each audited model. McNemar's test is appropriate because the unit of observation is the task (paired across monitor configurations).

**Setup.** Restrict to \(T_{\text{fail}}\). For each task \(t\), record \(a_t = \operatorname{detect}(\tilde{v}_t^{V_{\text{answer}}})\) and \(s_t = \operatorname{detect}(\tilde{v}_t^{V_{\text{structural}}})\). The paired \(2 \times 2\) table:

| | \(V_{\text{structural}}\) detects (\(s_t=1\)) | \(V_{\text{structural}}\) misses (\(s_t=0\)) |
| --- | --- | --- |
| \(V_{\text{answer}}\) detects (\(a_t=1\)) | \(n_{11}\) | \(n_{10}\) |
| \(V_{\text{answer}}\) misses (\(a_t=0\)) | \(n_{01}\) | \(n_{00}\) |

Only the discordant cells \(n_{01}\) (structural gains) and \(n_{10}\) (structural loses) carry information.

**Statistic (with continuity correction).**

$$
\chi^2_{\text{McNemar}} = \frac{(|n_{01} - n_{10}| - 1)^2}{n_{01} + n_{10}}, \quad p = P(\chi^2_1 > \chi^2_{\text{McNemar}})
$$

Reject \(H_0\) at \(p < 0.05\). A significant result with \(n_{01} \gg n_{10}\) confirms that \(V_{\text{structural}}\) gains substantially more detections than it loses versus \(V_{\text{answer}}\).

### 2.8 Bootstrap Confidence Intervals

**Purpose.** Report uncertainty on all headline rates. Agent evaluation papers rarely report CIs; this thesis does so to make LLM non-determinism explicit and support reproducibility claims.

**Method.** For a rate metric \(\hat{\mu}\) (e.g., \(\operatorname{RDR}(V)\)) over \(|T|\) tasks with \(K=10\) repeats each:

1. Compute per-task detect-fraction \(\hat{p}_t = \frac{1}{K}\sum_k \operatorname{detect}(\tilde{v}_{t,k}^V)\) for \(t \in T_{\text{fail}}\).
2. Draw \(B = 1000\) bootstrap resamples (with replacement over tasks); compute \(\hat{\mu}^{(b)}\) for each.
3. Report \([\hat{\mu}^{(0.025)},\ \hat{\mu}^{(0.975)}]\) as the 95% CI.

Implementation: `eval/metrics.bootstrap_ci(values, n_resamples=1000, seed=0)`. All headline rates (FAR, FalseAlarmRate, RDR, \(\Delta\operatorname{RDR}\)) are reported with 95% CIs.

### 2.9 Coverage Split: PASS\_VERIFIED vs PASS\_UNCHECKED

**Purpose.** Distinguish substantiated passes (at least one claim corroborated by grounding evidence) from low-evidence passes (no contradictions found but no positive support either). Diagnostic for verifier grounding quality on reward=1 tasks.

For tasks processed by the monitor pipeline with \(y_t = 1\):

$$
\operatorname{VerifiedPassRate}(V) = \frac{|\{t \in T_{\text{pass}} \mid v_t^V = \text{PASS\_VERIFIED}\}|}{|T_{\text{pass}}|}
$$

$$
\operatorname{UncheckedPassRate}(V) = \frac{|\{t \in T_{\text{pass}} \mid v_t^V = \text{PASS\_UNCHECKED}\}|}{|T_{\text{pass}}|}
$$

A high UncheckedPassRate for \(V_{\text{structural}}\) indicates that many correct tasks pass without any claim being positively grounded — the monitor accepts by absence of contradiction rather than by positive corroboration.

### 2.10 Evidence State Distribution

**Purpose.** Reports the average number of claims in each evidence state among tasks where the verifier produced at least one claim-level result. Diagnostic for verifier and extractor quality.

For each task \(t\), ReliableGuard records:

$$
n_t^{\text{sup}},\ n_t^{\text{con}},\ n_t^{\text{uns}},\ n_t^{\text{unv}},\ n_t^{\text{nf}}
$$

corresponding to `supported`, `contradicted`, `unsupported`, `unverifiable`, and `not_found` counts. Let \(T_E = \{t \mid n_t^{\text{sup}}+n_t^{\text{con}}+n_t^{\text{uns}}+n_t^{\text{unv}}+n_t^{\text{nf}} > 0\}\).

$$
\operatorname{AvgSupported} = \frac{\sum_{t \in T_E} n_t^{\text{sup}}}{|T_E|}, \quad
\operatorname{EvidenceStateCoverage} = \frac{|T_E|}{|T|}
$$

The same form applies to each evidence state. Implementation fields: `avg_supported_count`, `avg_contradicted_count`, `avg_unsupported_count`, `avg_unverifiable_count`, `avg_not_found_count`, and `evidence_state_coverage` in `eval/metrics.compute_metrics`.

### 2.11 Stage Latency and Token Cost

ReliableGuard records per-stage audit latency in `ReliabilityReport.stage_latencies`. Aggregated metrics report mean and p95 latency for each pipeline stage: `extract_claims`, `classify_verifiability`, `verify_claims`, `score_risks`, `decide_interventions`, `generate_report`, `total_pipeline`.

For each stage \(s\) with observed latency values \(L_s = \{\ell_1, \ldots, \ell_m\}\):

$$
\operatorname{MeanLatency}_s = \frac{1}{m}\sum_{i=1}^{m}\ell_i
$$

and p95 is the 95th percentile of the sorted latency list. Token usage:

$$
\operatorname{AvgTokens} = \frac{\sum_{t \in T_\tau}\tau_t}{|T_\tau|}
$$

where \(T_\tau\) contains only tasks with positive token counts. Implementation fields: `stage_latency_mean_ms`, `stage_latency_p95_ms`, `avg_tokens`, `total_tokens_sum`.

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

### 4.2 Detection Scope Boundary: Locus Taxonomy

This boundary is an **observability** statement. Each failure is attributed to a _locus_ — the location in the execution artifact space where its ground truth resides. Whether a monitor can detect the failure depends entirely on whether its observation channel reaches that locus.

**The locus taxonomy.** Partitions all tasks by the location of the ground truth needed to determine correctness:

| Locus | Ground truth location | \(V_{\text{answer}}\) | \(V_{\text{structural}}\) |
| --- | --- | --- | --- |
| answer-local | Self-contradiction in the answer text | detectable | detectable |
| trace-local | Tool call sequence violates policy rule | not reachable | detectable (trace channel) |
| state-local | Claimed effect not realized in DB `state_after` | not reachable | detectable (state channel) |
| intent-local | Agent's action is valid but not what the user wanted | not reachable | not reachable |

**Theoretical detection limit.** For any black-box monitor \(M\) operating on (answer text, `state_after`, tool trace):

$$
\operatorname{RDR}(M)^* \leq \pi_{\text{answer-local}} + \pi_{\text{trace-local}} + \pi_{\text{state-local}} = 1 - \pi_{\text{intent-local}}
$$

This bound is not an implementation shortfall; it follows from the definition of intent-local: the agent's final answer, the DB state, and the tool trace are all consistent with a correct execution, yet the user's goal was not achieved. No monitor reading those artifacts can distinguish this case from a correct run.

**Locus annotator.** The assignment is rule-based, operating on verified artifacts independently of the monitor's verdict to avoid circularity. Source: `src/reliableguard/locus.py → annotate_locus()`.

1. Any `TraceViolation` from `verify_trace()` → locus = **trace-local**.
2. Any claim with `evidence_state = contradicted` (state channel) → locus = **state-local**.
3. `gold_reward = 0` with no violation and no contradiction → locus = **intent-local** (unobservable residual).
4. `gold_reward = 1` → locus = **pass**.

**RQ3 operationalization.** The intent-local label in step 3 is the observational residual: tasks where no artifact in any channel carries a detectable contradiction. The thesis does not claim these are intent failures in a philosophical sense — only that they are observationally indistinguishable from correct executions under \(V_{\text{structural}}\). The empirical claim is \(\pi_{\text{intent-local}} > 0\), establishing that the unobservable class is non-empty; its magnitude sets the practical detection ceiling.

**Connection to RQ1 and RQ2.** RQ1 establishes that \(V_{\text{answer}}\) is structurally limited to answer-local detections — the channel limit is not an extractor quality issue. RQ2 shows that \(V_{\text{structural}}\) extends coverage to trace-local and state-local loci (the \(\Delta\operatorname{RDR}\) gain). RQ3 shows that \(\pi_{\text{intent-local}}\) remains after both channels — the irreducible boundary. Together the three RQs traverse the full locus taxonomy from the most observable locus to the least.

**Design implication.** For new domain instantiations, structural audit is necessary when target failures involve policy preconditions, permission constraints, or environment state transitions not reliably exposed in the final answer text. The intent-local class is irreducible regardless of structural channel expansion; only intent-aware evaluation (e.g., human annotation of user goals independent of agent output) could push detection further.

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
