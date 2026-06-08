# ReliableGuard — Thesis Writing Handoff Brief

> Self-contained context for a fresh assistant (e.g. web Claude) that has **no access to
> the codebase, CLAUDE.md, or prior chat memory**. Everything needed to co-write the thesis
> following the agreed direction is in this file + `thesis_outline.md` + the figures.
>
> **What to upload to web Claude:** this file, `docs/thesis_outline.md`, the Set A figures in
> `figures/set_a_3seed/` (use `fig_rq2_structural.png` = Figure 1 and `fig_rq3_locus.png` =
> Figure 2; `fig_rq1_claim_only.png` / `fig_benign_far.png` are demoted to tables) +
> `summary.csv`, and the Set B figure `figures/set_b_3seed/fig_setb_benign_reframe.png` (= Figure 3).

---

## 0. Suggested opening prompt (paste this to web Claude)

> I'm writing my master's thesis on **ReliableGuard**, a runtime auditing framework for
> tool-using LLM agents. I'm attaching a **handoff brief** (locked decisions + results), a
> **chapter outline**, and **result figures**. Please act as my thesis co-author: help me
> draft chapter by chapter following the outline. Respect the locked decisions in the brief
> (do not re-open them), keep the structure consolidated (my advisor wants few sections / not
> fragmented), weight RQ2 > RQ1 > RQ3, and challenge any weak claim within the agreed framing.
> Start by confirming you've understood the central thesis and the RQ priority, then we'll
> begin with [Chapter X]. Use the numbers from the brief; flag anything that still says
> "pending ×3 seed".

---

## 1. Your role (web Claude)

Thesis co-author. Draft prose chapter by chapter from `thesis_outline.md`. Use the locked
decisions and numbers below. **Do not re-derive or re-open settled framing decisions** (Section
3) — they were reached after extensive analysis. Challenge weak claims, but within this
framing. Match a top-tier AI paper's tone (concise, evidence-led). English only.

## 2. Identity and central thesis

**Thesis title (locked):** *ReliableGuard: A Constraint-Aware, Environment-Grounded Auditing
Framework for Tool-Using LLM Agents.* (Note: "auditing", not "governance/control" — the system
is monitor-only and does not enforce on or modify the agent.)

ReliableGuard is a **black-box, monitor-only, post-hoc runtime verification harness** for
tool-using LLM agents. It does **not** modify or fine-tune the agent. It is **claim-level
runtime auditing, NOT general hallucination detection.**

**Central thesis:** a tool-using agent's final answer is an unreliable, partial *self-report*
of what it did. ReliableGuard judges whether that self-reported outcome can be trusted — and
**doing so reliably requires observing the agent's execution (trace/state), not its answer
alone.** Failure detectability is governed by the **locus of each fault's ground truth**
relative to the monitor's observation channels — an *observability* problem.

## 3. Locked decisions (MUST respect — the heart of the handoff)

1. **Observability / locus framing.** Faults are classified by the locus of their ground
   truth: **answer-local** (claim-checkable), **trace-local** (tool-use / policy / dependency),
   **state-local** (pre/post effect), **evidence-local** (external source). This is the spine;
   lead with it, not with detection rates.

2. **RQ priority: RQ2 > RQ1 > RQ3.** RQ2 (trace/state augmentation) is the contribution and
   gets the most space. RQ1 is the setup. RQ3 is generality + boundary (lighter, honest).

3. **RQ2 = verification, NOT enforcement.** A control experiment (T8) showed a *policy-aware*
   agent (policy in its prompt) resists **0/45** adversarial social-engineering attempts, while
   a *naive* agent violates **100%**. So the argument is **NOT** "prompting is insufficient"
   (false). It is: under the black-box / monitor-only premise we **don't control the agent's
   prompt**, and compliance is **probabilistic and unverifiable** from the answer (RQ1); the
   deterministic structural check is the **auditable guarantee**. Keep "the agent violates"
   (T8) separate from "the monitor detects" (RQ2's core, untouched by T8).

4. **Generality lives at the meta level.** Generality = locus taxonomy + channel-matching +
   shared pipeline + the unified **compare-each-claim-to-its-locus-source** operation
   (ecommerce DB-verify and reference source-verify are the *same* operation; only the source
   location differs). Symbolic rules + evidence sources are per-domain **adapters** (the
   neuro-symbolic domain-adaptation cost). Position the contribution as a **diagnostic
   framework**, NOT a universal detector. Do **not** headline "general" — say "reliable,
   demonstrated in ecommerce; generality probed."

5. **Reference is the evidence-local / boundary domain — with an honest caveat.** The
   *intended* role of reference is evidence-local (is this citation real?). But the current
   Set A reference scenarios (F1 schema / F2 policy / F3 dependency) are actually **trace-local**
   (re-used from ecommerce). So RQ3's honest version: the framework + locus diagnostic
   generalize; reference's trace-local misses are recoverable *in principle* by porting a
   structural gate (not built — scoping); the **irreducible boundary** is the evidence-local
   core (no offline authoritative source). Do NOT overclaim "reference = fundamental boundary"
   for the whole bottleneck.

6. **Two verifier design contributions (monotonic "only-lift").** Both judge a *claim-set*
   jointly, not per-claim, and only ever remove provable false positives (never add new
   blocks): **citation-level sufficiency** (reference; joint DOI/title/author evidence) and
   **transition-aware state verification** (ecommerce; an intermediate state like `pending` is
   not "contradicted" vs the final DB snapshot — a snapshot cannot confirm a past state).

7. **Freeze-replay methodology.** Provider-level LLM non-determinism (~33% per-task verdict
   flips at temp=0) makes naive re-runs irreproducible. Solution: **record once** (freeze agent
   answer + claims + tool trace + state), then **replay** every version deterministically with
   zero LLM calls. This makes the V3 vs V3_NoStructural ablation a clean paired comparison
   (stable even at single seed). Multi-seed only for agent-variance CI on absolute rates.

8. **WARN handling.** Set A ground truth is binary (PASS/BLOCK); WARN is a conservative
   graduated downgrade, folded into binary there (and folded *conservatively* — it counts
   against benign FAR). The full three-way gate (incl. WARN as a correct answer) is evaluated
   on **Set B** (20 expected-WARN scenarios). Report the full verdict space
   (`PASS_VERIFIED/PASS_UNCHECKED/WARN/BLOCK/AUDIT_FAILED`); do not over-sell WARN — it is thin
   by design (symbolic determinism pushes outcomes to PASS/BLOCK).

## 4. Framework (for Chapter 3)

- **Verdict space:** `PASS_VERIFIED / PASS_UNCHECKED / WARN / BLOCK / AUDIT_FAILED` (graduated,
  transparency-aware; `AUDIT_FAILED` = zero claims extracted, fail-closed; `PASS_UNCHECKED` =
  passed but evidence coverage below threshold).
- **Pipeline (6 stages):** extract claims → classify verifiability → verify (compare to
  locus-source) → score risk → decide intervention → report.
- **Channels:** (a) claim pipeline (answer-local); (b) symbolic structural audit (trace/state:
  pre-execution schema/policy checks, post-execution state-effect snapshot checks); (c) evidence
  source (external/fixture, offline by default for determinism).
- **Graph:** plan → execute → reliability nodes (LangGraph).

## 5. Experimental setup (for Chapter 4)

- **Domains:** ecommerce (internal-state, high-stakes transactional — the **hero** domain);
  reference (external-evidence, knowledge-production — the **boundary** domain).
- **Failure taxonomy F0–F5:** F0 happy / F1 schema / F2 policy / F3 dependency / F4 state /
  F5 multi-step. (Ecommerce: F1–F4 are faults expecting a gate; F0/F5 benign. Reference: same
  labels but they manifest as trace-local tool-use violations.)
- **Set A** (controlled, F0–F5): 1000 ecommerce + 550 reference, ×3 seeds.
  **Set B** (generalization stress test): 120 prompts, with PASS/WARN/BLOCK labels.
- **Ablation versions:** `V1_Baseline` (no audit) / `V2_AuditOnly` (audit, no enforce) /
  `V3_NoStructural` (audit + enforce, structural OFF = answer-only) / `V3_Intervention`
  (audit + enforce, structural ON) / `V3_PolicyAware` (T8 control: policy in agent prompt).
- **Metrics:** Risk Detection Rate (RDR) and a separate Block/Enforcement rate (distinguish
  *detected*, incl. WARN, from *blocked*); benign False-Alarm Rate (FAR); the **locus
  decomposition** (correct / not_extracted / misjudged / not_observable / no_evidence) as the
  bottleneck-attribution instrument; audit latency/overhead.

## 6. Results — current numbers (for Chapter 5)

> **DATA-STATUS:** numbers below are the **authoritative ×3-seed Set A batch** (seeds 42/123/7,
> 4650 records, commit `c74dbb8`, archived at
> `results/_archive/set_a_3seed_20260608_c74dbb8/`). Rates are ×3-seed mean ± std. **Set B is
> still recording** (three-way WARN results pending). Treat all rates as benchmark-illustrative,
> not universal.

**RQ1 (claim-only ability + ceiling), ecommerce, `V2_AuditOnly` (pure audit verdict):**
- Detection by failure mode: answer-local **F3 = 100%, F4 = 100%**; trace-local blind
  **F2 = 0.7%, F1 = 15.5%**. Aggregate fault detection = **35.4%**.
- The ceiling is observability, not extraction: extractor precision ≈ **99.15%** (annotation
  study). Benign false-alarm = **1.2%**.

**RQ2 (answer-only vs +trace/state), ecommerce, `V3_NoStructural` → `V3_Intervention`:**
- Aggregate fault detection (RDR) **35.5% → 76.6%** (±0.1–0.2). By F-type:
  **F2 policy 0.8% → 100%** (the clean structural win), **F1 schema 15.6% → 45.3%**.
- ⚠️ **F4 reconciliation (MUST address in Ch3/Ch4):** F4 (state / false-success) is **already
  100% under claim-only** (V2/V3_NoStructural), so the structural state-transition check adds
  **zero** measured F4 detection. In this benchmark the false-success leaves the claimed entity
  **absent from `D_after`**, so the claim verifier catches it answer-locally. The structural
  channel's measured gain is **entirely F2 (+partial F1)**. Do NOT write "F4 detectable only by
  pre/post snapshots" — that contradicts the data. Frame F4's snapshot check as *architectural
  completeness* (the general mechanism), not the empirical driver of the RQ2 lift.
- Not over-blocking: benign false-alarm unchanged at **1.3%** (claim-only and +structural
  identical) — structural lift is pure detection gain, **0** new false blocks. Locus
  decomposition: **misjudged = 0%**; the residual ecommerce miss is **23% not_observable** (all
  from F1 schema, 55% of F1 unobservable).
- Prompt-enforcement control (T8, ×3 seeds): naive agent violates **74/74 (100%)** adversarial;
  policy-aware agent violates **0/45 (0%)**. → frame as verification-not-enforcement (Decision 3).
- Deployability: symbolic audit overhead (verify→score→intervene, no LLM) = **~38 ms mean /
  ~88 ms p95** per task; structural channel adds no measurable latency over claim-only. Only LLM
  cost is the one-time claim extraction (≈ one agent turn; token cost measured at record, not replay).
- **F4 collapse argument (use in prose, NOT a separate result):** in Set A, F4 is answer-local
  because order state is fully observable, so state-local collapses into answer-local — this is why
  the structural channel's measured lift is F2 (+partial F1), not F4. The state-transition check is
  necessary only when the post-state is *ambiguous*. A small constructed demo confirming it fires
  (`results/f4_clean/`, claim-only 0/12 BLOCK vs +structural 12/12) is **appendix-only** — do NOT
  headline it (it would spotlight that main-benchmark F4 doesn't exercise the state check, and it
  looks constructed).

**RQ3 (cross-domain + boundary), locus decomposition, `V3_Intervention`:**
- Reference RDR = **33.8%** and is **identical across V2/V3_NoStructural/V3_Intervention** —
  reference has **no structural channel**, so the RQ2 remedy does not apply (this *is* the
  boundary result).
- Ecommerce locus: **77% correct, 23% not_observable, 0% misjudged/not_extracted/no_evidence.**
- Reference locus: **20% correct, 14% not_extracted, 42% not_observable, 25% no_evidence, 0%
  misjudged.** → bottleneck is outside the answer channel; **no verifier bug** (misjudged 0 in
  both domains). F4 reference = **82% no_evidence** (DOI existence, no offline authoritative
  source = the irreducible evidence-local core).
- Reference benign false-alarm = **8.9%** (vs ecommerce 1.3%) — partly AUDIT_FAILED on
  confirmation-style benign answers.
- **Evidence-local citation pilot — FUTURE WORK, NOT a result.** The `no_evidence` boundary is
  made entirely by the Set A locus decomposition above. A live real-vs-fabricated citation pilot
  was run (`results/citation_realfake/`: offline can't separate real/fake; CrossRef-only false-
  alarms every arXiv paper; CrossRef + the dedicated arXiv API separates all real from fabricated)
  and confirms the boundary is crossable only with a source-matched online channel. Keep it in
  future work, **not the results** — it breaks the offline-determinism methodology, is near-
  tautological as a finding, and would spotlight that the Set A reference scenarios test a
  trace-local (not evidence-local) locus. Artifacts exist if an examiner asks live.
- Message: framework + locus diagnostic generalize; performance is locus-bounded; the
  trace-local part (not_observable) is recoverable in principle (port a structural gate), the
  evidence-local part (no_evidence) is irreducible.

**Set B (generalization stress test, ×3-seed, 120 naturalistic prompts; archived
`set_b_3seed_20260608_c74dbb8`):**
- **RQ2 replicates out-of-distribution (good):** structural channel adds **zero** benign false
  alarms (V2 = V3_NoStructural = V3_Intervention on expected-PASS, identical) yet still lifts
  detection (ecommerce expected-BLOCK **55% → 76%**; reference flat).
- **The "43% benign false-alarm" is mostly the monitor being RIGHT (key reframe).** Re-deriving
  benign ground truth from the agent's actual execution (requested order count vs. raw
  `db_state_after`, independent of the claim pipeline; `scripts/recheck_setb_benign.py`): the
  agent under-executes naturalistic multi-step tasks (asked for 4 orders, makes 1, narrates 4).
  **36/50 flagged benign = monitor correctly catching agent fabrication (100% catch of
  under-execution); TRUE benign false-alarm = 17%, not 43%.** "expected-PASS" is the artifact (it
  assumed agent success). Frame Set B as evidence the monitor catches fabrication on hard inputs.
- **One real limitation:** the **three-way WARN gate is weakly supported** — expected-WARN
  escalated to BLOCK (ecommerce) or dropped to PASS (reference); WARN recall ~3–13%. The 17%
  residual is mostly a negative-claim polarity case (agent correctly reports a non-existent order;
  verifier flags the not_found) — small monotonic-lift fix, future work. Results:
  `results/set_b_3seed/report.txt`.

## 7. Writing constraints and style

- **Advisor feedback (must follow):** too many subsections / fragmented; consolidate small
  sections into larger ones; keep the **overall chapter count low**. Target **7 chapters**,
  ≤ 3–4 sections each, no deep nesting (see `thesis_outline.md`).
- **Lead with the framework + RQ2.** RQ1 motivates; RQ3 scopes. Don't give the three RQs equal
  billing.
- **Be honest:** report rates as benchmark-specific; state limitations plainly (symbolic
  adaptation cost; simple-policy prompt-compliance; closed-loop eval; WARN one-sided on Set A;
  LLM non-determinism mitigated not eliminated). Do not overclaim "general" or "hallucination
  detector."
- Reference exemplar papers (structure/tone): ReAct, Reflexion, CRITIC, τ-bench, AgentBench,
  ToolSandbox, NeMo Guardrails.

## 8. Pending (will change the numbers, not the structure)

- ✅ DONE: ×3-seed Set A recorded + replayed + analyzed + archived (`set_a_3seed_20260608_c74dbb8`);
  Section 6 now carries ×3 mean ± std. ✅ DONE: audit latency (replay-measured, §6 deployability line).
- ✅ DONE: **clean state-local F4** supplementary experiment (§6 RQ2; `results/f4_clean/`).
- ✅ DONE: **evidence-local citation** case study (§6 RQ3; `results/citation_realfake/`).
- ✅ DONE: Set B recorded + replayed + analyzed + archived (`set_b_3seed_20260608_c74dbb8`);
  3-way WARN confusion + benign-false-alarm findings in §6.
- PENDING: per-task token overhead from the record stage (latency already done); optional bootstrap CI.
- Future work (not in this thesis): porting the structural gate to reference (recover the
  trace-local `not_observable` share); indirect (data-channel) prompt-injection threat model;
  complex/contextual policies.
