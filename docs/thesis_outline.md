# ReliableGuard — Thesis Outline

**Title (locked):** *ReliableGuard: A Constraint-Aware, Environment-Grounded Auditing
Framework for Tool-Using LLM Agents*

> Structural note (per advisor feedback): keep the chapter count low and avoid
> fragmentation. Target **7 chapters**, each with **at most 3–4 sections** and no deeper
> sub-subsections. Logically related material is consolidated rather than split.

---

## Central thesis (the one claim everything serves)

> A tool-using LLM agent's final answer is an unreliable, partial *self-report* of what it
> actually did. **ReliableGuard is a black-box, monitor-only runtime auditing framework that
> judges whether that self-reported outcome can be trusted — and doing so reliably requires
> observing the agent's execution (trace/state), not its answer alone.** Failure
> detectability is governed by the **locus of each fault's ground truth** relative to the
> monitor's observation channels (an *observability* problem).

**RQ priority (weighting): RQ2 > RQ1 > RQ3.**

- **RQ1 (setup):** How accurately can answer-only, claim-level auditing detect agent
  failures, and where is its ceiling?
- **RQ2 (center — the contribution):** Does augmenting answer-auditing with symbolic
  trace/state observation reliably detect failures that answer-only auditing misses?
- **RQ3 (generality + boundary):** Does the framework generalize across domains, and where
  does its performance break down?

**Narrative spine (how the chapters build the argument):** Ch.3 defines the framework and the
locus formulation → Ch.5.1 (RQ1) establishes the *problem* (answer-only auditing has a
structural blind spot, not an extraction artifact) → Ch.5.2 (RQ2) delivers the *solution*
(trace/state observation restores detection) → Ch.5.3 (RQ3) maps *where it generalizes and
where the locus makes it irreducible*.

---

## Length budget

> Target **~15,000 words of main text** (excluding references, figures, appendices).
> **Confirm against PolyU's official requirement — that overrides this.** To scale, adjust
> Results / Methodology / Discussion; do **not** pad with extra subsections (advisor feedback).
> Keep §3 (framework) and §5.2 (RQ2) the two heaviest blocks.

| Chapter | Target | Share |
| --- | --- | --- |
| 1 Introduction | ~1,500 | 10% |
| 2 Background & Related Work | ~2,000 | 13% |
| 3 Methodology (framework) | ~3,000 | 20% |
| 4 Experimental Setup | ~1,800 | 12% |
| 5 Results | ~4,500 | 30% |
| &nbsp;&nbsp;— 5.1 RQ1 | ~1,100 | |
| &nbsp;&nbsp;— **5.2 RQ2 (primary)** | **~2,300** | |
| &nbsp;&nbsp;— 5.3 RQ3 | ~1,100 | |
| 6 Discussion & Limitations | ~1,500 | 10% |
| 7 Conclusion | ~700 | 5% |
| **Main text total** | **~15,000** | |

---

## 1. Introduction (~1,500 words)

- **1.1 Motivation.** Tool-using LLM agents act on the world (create orders, cite papers) and
  then *report* what they did. The report can be wrong in ways the report itself hides
  ("order created" when it was not; a policy/schema/dependency violated while the answer reads
  clean). Trusting the self-report is the core reliability gap.
- **1.2 Thesis and framing.** State the central thesis; introduce the observability framing
  and the four loci of ground truth (answer / trace / state / evidence-local). Position as
  *claim-level runtime auditing*, **not** general hallucination detection and **not** model
  fine-tuning.
- **1.3 Research questions and contributions.** State RQ1–RQ3 (with RQ2 as the center).
  Contributions: (i) the observability/locus formulation of agent auditing; (ii) the
  ReliableGuard framework (multi-channel monitor); (iii) the RQ2 result (trace/state restores
  observability); (iv) a deterministic *freeze-replay* evaluation methodology under
  provider-level LLM non-determinism; (v) a two-domain study delimiting generality.

## 2. Background and Related Work (~2,000 words)

> Scope: one consolidated chapter — group, do not enumerate one subsection per paper.

- **2.1 Tool-using LLM agents and benchmarks.** ReAct, Reflexion; agent/tool benchmarks
  (AgentBench, τ-bench, ToolSandbox, ToolLLM, API-Bank). Gap: these evaluate *capability*
  pre-deployment; ReliableGuard audits a *given* agent at runtime.
- **2.2 Reliability, hallucination, and guardrails.** Trustworthiness surveys; CRITIC /
  self-correction (agent improves itself) vs. NeMo Guardrails (programmable rails). Position
  ReliableGuard as black-box, monitor-only, post-hoc — independent of and complementary to the
  agent.
- **2.3 The observability gap.** No prior line treats agent-failure detection as governed by
  the *locus of ground truth* relative to observation channels — the framing this thesis
  contributes.

## 3. Methodology: The ReliableGuard Framework (~3,000 words)

> Scope: heavy chapter — this is the artifact contributed.

- **3.1 Observability formulation.** Locus of ground truth: answer-local (claim-checkable),
  trace-local (tool-use/policy), state-local (pre/post effect), evidence-local (external
  source). The unified operation: **verify each claim against the ground-truth source of its
  locus** — the same operation whether the source is an internal DB (ecommerce) or an external
  authority (reference); only the source *location* differs.
- **3.2 Architecture and pipeline.** Graph (plan → execute → reliability); the six-stage claim
  pipeline (extract → classify → verify → score → intervene → report); the verdict space
  (`PASS_VERIFIED / PASS_UNCHECKED / WARN / BLOCK / AUDIT_FAILED`) as graduated,
  transparency-aware enforcement.
- **3.3 Observation channels and verification design.** (a) Claim channel (answer-local);
  (b) symbolic structural audit (trace/state: pre-execution schema/policy checks,
  post-execution state-effect checks — the latter is *architectural completeness* for the
  state-local locus; in the Set A benchmark the false-success faults are also answer-local, so the
  empirical RQ2 lift comes from the pre-execution policy check, see 5.2); (c) evidence source
  (external/fixture). Joint
  claim-set verification (rather than per-claim): **citation-level sufficiency** (reference)
  and **transition-aware state verification** (ecommerce) — both monotonic "only-lift"
  designs that remove provable false positives without sacrificing detection.
- **3.4 Generality and the neuro-symbolic cost.** Generality lives at the meta level (locus
  taxonomy + channel-matching + shared pipeline + compare-to-source); symbolic rules and
  evidence sources are per-domain *adapters* (the symbolic-determinism vs. domain-adaptation
  trade-off). Spanning two different loci is the generality *demonstration*, not a limitation.

## 4. Experimental Setup (~1,800 words)

> Scope: consolidated — domains, data, methodology, metrics in one chapter.

- **4.1 Domains and failure taxonomy.** Ecommerce = internal-state, high-stakes transactional
  (hero domain); Reference = external-evidence, knowledge-production (boundary domain).
  Failure taxonomy F0–F5 (happy / schema / policy / dependency / state / multi-step).
- **4.2 Datasets.** Set A (controlled known-failure: 1000 ecommerce + 550 reference, F0–F5);
  Set B (120-prompt generalization stress test; PASS/WARN/BLOCK labels — the dataset that
  evaluates the three-way gate, including WARN).
- **4.3 Freeze-replay methodology.** Provider-level LLM non-determinism (~33% per-task verdict
  flips at temp=0) makes naive re-runs irreproducible. *Record once* (freeze agent answer +
  extracted claims + tool trace + state), then *replay* every version deterministically with
  zero LLM calls — yielding a clean paired ablation. Ablation versions
  (V1/V2/V3_NoStructural/V3_Intervention, + V3_PolicyAware control). ×3 seeds for
  agent-variance bootstrap CI.
- **4.4 Metrics.** Risk Detection Rate (RDR) vs. Block/Enforcement Rate (distinguish
  *detected* incl. WARN from *blocked*); False-Alarm Rate (benign); the **locus
  decomposition** (correct / not_extracted / misjudged / not_observable / no_evidence) as the
  bottleneck-attribution instrument; audit latency/overhead.

## 5. Results (~4,500 words)

> Scope: core chapter, organized by RQ. **5.2 (RQ2) is the longest and most detailed.**

> **Figures & tables (placement — keep it lean per advisor):**
> - **Figure 1 → §5.2** = `figures/set_a_3seed/fig_rq2_structural.{pdf,png}` — RQ2 hero figure
>   (ecommerce detection by F-type, `V3_NoStructural` → `V3_Intervention`; F2 0.8→100).
> - **Figure 2 → §5.3** = `figures/set_a_3seed/fig_rq3_locus.{pdf,png}` — two-domain locus
>   decomposition (the boundary figure).
> - **Figure 3 → §5.3 (or §6.2)** = `figures/set_b_3seed/fig_setb_benign_reframe.{pdf,png}` —
>   Set B "43% → 17%" benign false-alarm decomposed (36 correct-catch + 14 true FP).
> - **Table 1 → §5.1** = RQ1 claim-only detection by F-type, both domains (the bimodal table;
>   data in `figures/set_a_3seed/summary.csv` / `scripts/eval_rq1_audit.py`).
> - **Table 2 → §5.2** = RQ2 aggregate RDR + benign false-alarm per version (incl. the "structural
>   adds zero false alarms" row — replaces a separate `fig_benign_far`).
> - **Table 3 → §5.3** = Set B three-way PASS/WARN/BLOCK confusion (V3_Intervention) — shows WARN
>   weakly supported (`results/set_b_3seed/report.txt`).
> - `figures/set_a_3seed/fig_rq1_claim_only` and `fig_benign_far` exist but are **demoted to
>   Tables 1–2** to keep the figure count low (and avoid RQ1/RQ2 figure overlap).

- **5.1 RQ1 — Claim-level auditing and its answer-local ceiling.** *(Setup; ~1,100 words.)*
  *(Numbers: authoritative ×3-seed Set A batch, commit `c74dbb8`.)*
  *(→ Table 1: RQ1 detection-by-F-type, both domains.)*
  - Answer-only audit (`V2_AuditOnly`) detection by failure mode, ecommerce: answer-local
    faults caught (**F3 = 100%, F4 = 100%**), trace-local faults near-blind (**F2 = 0.7%,
    F1 = 15.5%**). Aggregate risky detection = **35.4%**.
  - The ceiling is an *observability* limit, not an extraction artifact: extractor
    precision ≈ **99.15%** (annotation study). Benign false-alarm rate = **1.2%** (ecommerce),
    enabled by transition-aware verification (benign F5 false-block 84% → 2%).
  - **F4 caveat (carry into 5.2):** F4 (state / false-success) is caught at 100% *answer-locally*
    here because the false-success leaves the claimed entity absent from `D_after`, so the claim
    verifier flags it. F4 is therefore not the evidence for the structural channel — F2 is.
  - Takeaway: claim-level auditing covers the answer-local subset and is structurally blind to
    *trace*-local faults (F1/F2) — motivating RQ2.

  **Table 1 — RQ1: claim-only (`V2_AuditOnly`) detection by failure mode, ecommerce (×3-seed).**

  | Failure mode (locus) | Detection |
  | --- | --- |
  | F3 fabricated entity (answer-local) | **100%** |
  | F4 false success (answer-local in Set A) | **100%** |
  | F1 schema violation (trace-local) | 15.5% |
  | F2 policy violation (trace-local) | **0.7%** |
  | Aggregate risky (F1–F4) | 35.4% |
  | Benign false-alarm (F0, F5) | 1.2% |

  > The bimodal split (answer-local ≈100% vs. trace-local ≈0%) under a 99.15%-precision extractor
  > is the observability ceiling. (Reference detection-by-type is reported in §5.3.)

- **5.2 RQ2 — Trace/state-augmented auditing (PRIMARY).** *(Most depth — ~2,300 words; the
  contribution's empirical proof.)*
  *(→ Figure 1: structural ablation by F-type; → Table 2: aggregate RDR + benign FAR per version.)*
  - **Core ablation** (paired, freeze-replay, ×3-seed): `V3_NoStructural` (answer-only) vs.
    `V3_Intervention` (+ trace/state), ecommerce. Detection of policy faults **F2: 0.8% → 100%**;
    schema **F1: 15.6% → 45.3%**; F3/F4 remain 100%. Aggregate fault detection (RDR)
    **35.5% → 76.6%** (±0.1–0.2 across seeds). The structural channel restores detection exactly
    for the *trace*-local classes RQ1 found blind.
  - **F4 in Set A is answer-local — and that is a finding, not a defect.** F4 detection is
    100% with and without the structural channel, because the orders table is fully observable:
    a false-success leaves the claimed entity absent from `D_after`, so the claim channel catches
    it. **When the post-state is fully observable, state-local collapses into answer-local.** The
    RQ2 *aggregate* lift is therefore driven by F2 (+partial F1), not F4.
    *(The state-transition check is consequently necessary only when the post-state is ambiguous
    — e.g. a quantity update that silently no-ops, where the leftover value looks valid on its
    own. A small constructed demonstration of this exists (Appendix; `results/f4_clean/`) but is
    NOT a headline result — keep it in the appendix to avoid spotlighting that the main-benchmark
    F4 instances do not exercise the state-transition check.)*
  - **The result is real, not over-blocking.** Benign false-alarm rate is **identical** at
    **1.3%** with and without the structural channel — the lift is pure detection gain, **zero**
    new false blocks (monotonic "only-lift" verifier designs); locus decomposition shows
    **misjudged = 0%** (no verifier error).
  - **Deployability.** Symbolic audit overhead (verify → score → intervene, no LLM) is
    **~38 ms mean / ~88 ms p95 per task** (replay-measured; the structural channel adds no
    measurable latency over claim-only). The only LLM cost is the one-time claim extraction
    (≈ one extra agent turn); it is frozen in replay, so per-task token overhead is reported
    from the record stage, not replay.
  - **Why an independent monitor, not prompt-enforcement?** *(Consolidate the T8 control here,
    framed as scoping — not a separate RQ.)* A naive agent (policy not in prompt) violates the
    F2 policy **100%** (74/74 adversarial). A policy-aware agent (policy in prompt) violates
    **0/45** adversarial trials across 15 social-engineering attacks ×3 seeds. Reading:
    prompting *enforces* a simple policy, but ReliableGuard provides *verification* under the
    black-box / monitor-only premise — we do not control the agent's prompt, and compliance is
    probabilistic and **unverifiable** from the answer (RQ1). The deterministic check is the
    auditable guarantee; social engineering can sway the LLM but not the check.

  **Table 2 — RQ2: risk detection rate (RDR) and benign false-alarm by version, ecommerce (×3-seed).**

  | Version | Observation channels | RDR | Benign false-alarm |
  | --- | --- | --- | --- |
  | V1_Baseline | none (trust the agent) | 0% | 0% |
  | V2_AuditOnly | claim only (audit verdict) | 35.4% | 1.2% |
  | V3_NoStructural | claim, enforced | 35.5% | 1.3% |
  | V3_Intervention | claim + structural | **76.6%** | **1.3%** |

  > Key row: adding the structural channel lifts RDR 35.5% → 76.6% while the benign false-alarm is
  > **identical** (1.3%) — pure detection gain, zero new false blocks.

- **5.3 RQ3 — Cross-domain generalization and the observability boundary.** *(Lighter —
  ~1,100 words; honest scoping.)*
  *(→ Figure 2: two-domain locus decomposition. → Figure 3 + Table 3: Set B reframe + WARN confusion.)*
  - **Reference RDR = 33.8%, identical across `V2_AuditOnly` / `V3_NoStructural` /
    `V3_Intervention`** — reference has no structural channel, so the RQ2 remedy does not apply.
    This invariance *is* the boundary result, not a null finding.
  - Two-domain **locus decomposition** of the detection bottleneck (×3-seed, `V3_Intervention`).
    Ecommerce: **77% correct, 23% not_observable** (all from F1 schema; recovered in principle by
    the structural channel). Reference: **20% correct, 14% not_extracted, 42% not_observable,
    25% no_evidence, 0% misjudged** — the bottleneck sits *outside* the answer channel, and there
    is no verifier bug (misjudged = 0 in both domains).
  - **Framework generalizes; performance is locus-bounded.** The locus diagnostic applies
    identically to both domains. Reference's not_observable share is trace-local and
    recoverable *in principle* by porting a structural gate (not built — a scoping choice); the
    *irreducible* boundary is the evidence-local core (**no_evidence = 25%**, e.g. reference F4 is
    82% no_evidence: DOI existence with no offline authoritative source). The structural remedy
    (RQ2) cannot cross it.
  - Reference benign false-alarm rate = **8.9%** (vs ecommerce 1.3%) — citation-level sufficiency
    lowered the hard false-block component, but AUDIT_FAILED on confirmation-style benign answers
    keeps it higher than ecommerce. WARN folded conservatively; full three-way (incl. WARN) gate
    evaluated on Set B.
    *(The `no_evidence` boundary is made entirely by the Set A locus decomposition above — no
    extra online experiment is needed in the results. A live "real vs. fabricated citation" pilot
    was run (artifacts in `results/citation_realfake/`) and confirms the boundary is crossable
    only when the channel reaches the citation's specific source; it is deliberately kept to
    future work, not the results, because it breaks the offline-determinism methodology and is not
    load-bearing.)*
  - **Set B (generalization stress test, ×3-seed, 120 naturalistic prompts).** Three findings.
    (i) **RQ2 replicates out-of-distribution:** the structural channel adds **zero** benign false
    alarms (V2 = V3_NoStructural = V3_Intervention on expected-PASS, identical) yet still lifts
    detection (ecommerce expected-BLOCK detection **55% → 76%** with structural; reference flat) —
    the same monotonic pattern as Set A, on un-templated input.
    (ii) **The apparent "43% benign false-alarm" is mostly the monitor being right.** Re-deriving
    benign ground truth from the agent's *actual execution* (requested order count vs. raw
    `db_state_after`, independent of the claim pipeline) shows the agent **under-executes**
    naturalistic multi-step tasks — e.g. asked to create 4 orders it calls `create_order` once
    and narrates the other three. **36/50 of the flagged benign tasks are the monitor correctly
    catching this agent fabrication (100% catch of agent under-execution).** The **true** benign
    false-alarm on tasks the agent *actually executed correctly* is **17%, not 43%** — and the
    "expected-PASS" label is the artifact (it assumed agent success). This reframes Set B from a
    monitor weakness into evidence the monitor catches agent fabrication on hard inputs.
    (iii) **One real limitation:** the **three-way WARN gate is weakly supported** — expected-WARN
    is escalated to BLOCK (ecommerce) or dropped to PASS (reference), WARN recall ~3–13%; the
    symbolic system pushes outcomes to PASS/BLOCK. The 17% residual is mostly a negative-claim
    polarity case (agent correctly reports a non-existent order; verifier flags the not_found) —
    a small monotonic-lift fix, noted as future work. (Results: `results/set_b_3seed/report.txt`;
    `scripts/recheck_setb_benign.py`.)

  **Table 3 — Set B three-way confusion (`V3_Intervention`, both domains, ×3-seed; ERROR excluded).**

  | Expected ＼ Actual | PASS | WARN | BLOCK | AUDIT_FAILED | n |
  | --- | --- | --- | --- | --- | --- |
  | PASS | 169 | 14 | 51 | 0 | 234 |
  | WARN | 27 | **5** | 28 | 0 | 60 |
  | BLOCK | 18 | 3 | 30 | 8 | 59 |

  > WARN recall = 5/60 ≈ 8% — expected-WARN is pushed to PASS or BLOCK, so the three-way gate is in
  > practice near two-way. The 51 PASS→BLOCK in the benign row is reframed by Figure 3 (36 of them are
  > correct detections of agent under-execution; true benign false-alarm = 17%, not the apparent 43%).

## 6. Discussion and Limitations (~1,500 words)

> Scope: consolidated — one chapter, not many small sections.

- **6.1 Synthesis.** Detectability is governed by locus relative to observation channels:
  answer-local is claim-checkable; trace/state-local needs the structural channel (RQ2);
  evidence-local is bounded by external-source availability (RQ3).
- **6.2 Limitations.** Symbolic rules and evidence sources are per-domain adapters
  (adaptation cost); detection rates are benchmark-illustrative, not universal; prompt
  compliance was tested only on a *simple* policy; WARN is one-sided on Set A (validated on
  Set B); closed-loop / final-snapshot evaluation; LLM non-determinism (mitigated by
  freeze-replay + multi-seed CI, not eliminated).
- **6.3 Future work.** A full evidence-local "real vs. fabricated citation" benchmark (a live
  pilot — `results/citation_realfake/` — already shows the `unavailable ≠ not-exist` boundary is
  crossable only with a source-matched online channel; a reproducible at-scale version needs a
  determinism strategy for live sources); porting the structural gate to reference (to recover the
  trace-local `not_observable` share); indirect prompt-injection (data-channel) threat model;
  complex/contextual policies.

## 7. Conclusion (~700 words)

- Restate the central thesis and the locus framing.
- One-line per RQ: RQ1 establishes the answer-only blind spot (observability limit, not
  extraction); RQ2 shows trace/state observation reliably restores detection (the
  contribution); RQ3 shows the framework generalizes while performance stays locus-bounded.
- Closing: trustworthy agent deployment is an observability-engineering problem — instrument
  the channel that matches where the truth lives.

---

### Appendices (optional, keep out of the main chapter count)

- A. Failure taxonomy (F0–F5) definitions and per-domain labeling rules.
- B. Formal definitions and metric formulas (Type I/II = locus of ground truth).
- C. Reproducibility: freeze-replay procedure, seeds, configuration.

### Data-status note (remove before submission)

Set A headline numbers in Ch.5 are now the **authoritative ×3-seed batch** (seeds 42/123/7,
commit `c74dbb8`, archived at `results/_archive/set_a_3seed_20260608_c74dbb8/`), reported as
×3-seed mean ± std. Still pending: **Set B** (recording) → the three-way / WARN results in 5.3;
and per-task **token** overhead from the record stage (latency is already reported from replay).
Optionally add bootstrap CIs (std is currently reported; the metrics JSON also carries `*_ci`).
