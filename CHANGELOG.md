# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

Before every push to GitHub, add an entry under `## [Unreleased]` describing the change,
and include CHANGELOG.md in the same commit as the code changes.

---

## [Unreleased]

### Changed (2026-06-25 — drop evidence-local from concept figures + thesis v11)

- `eval/make_concept_figures.py`: removed the **evidence-local** locus from Figure 1 (now 4 loci:
  answer/trace/state/intent) and Figure 2 (3 nested ellipses; legend "unreachable: intent-local", no
  dashed evidence ring). `OUT_DIR` -> `docs/thesis/figures_v11`. The thesis has no evidence-local
  experiment, so the concept figures now match the four loci actually measured. Figures regenerated.
- Thesis v11 text (gitignored, local): removed the "evidence-local not instantiated / no KB" sentence
  in §3.2 and the future-work "KB gaps" phrase, so v11 is **4-locus everywhere** (concept and results).
  The per-claim `evidence_state` outcome is unrelated and unchanged.

### Added (2026-06-25 — thesis v11: reward-fn-corrected results integrated)

- `docs/thesis/ReliableGuard_Thesis_v11.md` + `.pdf` + `build_thesis_v11.sh`: the thesis now reports
  the **reward-fn-corrected** numbers as the single result set (no before/after; the V10 raw numbers
  are not referenced). A new **"Reward-oracle correction"** methodology paragraph in §5.1 defines the
  corrected failure set `T_fail` (re-score reward=0 -> success when write-effects == gold actions AND
  every non-DB reward component is provably 1 AND the locus is intent-local). "Provably 1" covers
  empty/substring-matched COMMUNICATE, empty NL-assertions, AND NL-assertions whose required numeric
  facts (prices/quantities) appear verbatim in the answer; purely-qualitative NL-assertions are
  conservatively kept as failures. **628 trajectories re-scored.** Tables A–D, the RQ1/RQ2/RQ3 prose,
  the contributions, Table 9 (incl. a reward-oracle residual row), and the conclusion are updated.
- `eval/build_monitor_v11.py`: writes `results/monitor_v11/*.jsonl` (monitor_v2 with the 628
  intent-local provable reward-fn re-scored to PASS). `python -m eval.analyze --monitor-dir
  results/monitor_v11 --out-dir results/metrics_v11 --figures-dir docs/thesis/figures_v11` regenerates
  the corrected metrics and Figures 6–9; concept Figures 1–5 are copied unchanged. The numeric-fact
  check was validated against the 40-row manual review: it flips zero reviewer-judged failures
  (R35/R36 kept) and re-scores only reviewer-judged successes.
- **Corrected headline numbers (now the thesis values):** aggregate π_intent 61.7% over 2,242
  failures; mean V_structural RDR 37.0%, FalseAlarmRate 3.8%–10.1%, precision 66.2%–79.4%; mean ΔRDR
  +22.0pp (range +11.4 to +34.4), all McNemar p<0.001 with n_10=0; monitor-vs-oracle gap still 0.000.
  Per-model V_structural RDR: deepseek 0.363, mimo 0.480, glm 0.461, qwen 0.176.

### Added (2026-06-25 — deterministic reward-false-negative overlay, full population)

- `eval/overlay_reward_fn.py`: scales the 40-row manual intent-local spot-check to the **whole**
  `reward<1` population (2992 trajectories; intent-local subset 2134) with **no LLM and no
  re-capture**. For each trajectory it deterministically classifies: **A1** provable reward
  false-negative (agent writes == gold actions with full args, AND every non-DB `reward_basis`
  component is provably 1 — empty NL_ASSERTION/COMMUNICATE, or COMMUNICATE substrings all present —
  so `reward=0` can only be the premature-termination guard `evaluator.py:113`); **A2** undetermined
  (DB-match but a non-empty `nl_assertions` is LLM-judged, not replicable); **B_loop / B_comm**
  observable failure (stall-loop in the answer / required COMMUNICATE string absent); **RESIDUAL**
  DB mismatch (genuine DB-level `reward=0`). Handles tau2's component-specific scoring (retail
  DB×NL_ASSERTION, airline DB×COMMUNICATE) and malformed/no-op tool calls. Emits
  `eval/locus_spotcheck/reward_fn_overlay.{md,json}`.
- **Findings:** intent-local is **19.3% provable reward-fn (A1, floor)** + 17.3% undetermined (A2) +
  1.5% observable defect + 61.9% genuine DB-mismatch residual. **18.0% of ALL `reward<1`** are
  provable reward false-negatives — the termination artifact contaminates RQ1/RQ2 failure sets, not
  just RQ3. **Corrected agent success rate** (re-scoring A1): deepseek 71.3%->75.2%, mimo
  43.5%->**56.3%**, glm 52.9%->58.1%, qwen 49.9%->60.9% (floor; ceiling adds A2). Validation: the
  deterministic classes (A1/B_loop/B_comm/RESIDUAL) are **100% consistent (29/29)** with the manual
  verdicts; only A2 is intentionally ambiguous, and the overlay independently corrects the one
  inconsistent manual label (R5->A2). Caveat: the 40-row sample's 47.5% reward-fn overstates the
  population (stratified sampling over-weighted no-write refuse/info tasks); the population floor is
  19.3%. Counts are for the `monitor_v2`/`capture` draw (LLM non-determinism -> representative, not
  re-runnable to identical values).

### Added (2026-06-25 — reward-fn-corrected thesis metrics, before/after)

- `eval/correct_metrics_rewardfn.py`: an uncorrected-vs-corrected comparison tool (the thesis reports
  the corrected column only). Reuses `eval.analyze.compute_model_metrics` verbatim (so the "before"
  column reproduces `results/metrics_v2` exactly — sanity-checked OK for all 4 models) and re-scores
  the **same 628 intent-local provable reward-fn** as the V11 pipeline (A1 + A2-numeric, imported from
  `eval/build_monitor_v11.py`). Provenance written to `eval/locus_spotcheck/reward_fn_corrected_metrics.md`.
  Brackets the alternatives (all-A1, all-A1+A2) to show that re-scoring non-intent-local A1 would
  convert legitimate detections into false alarms (verification != enforcement) — it drags mimo's RDR
  down (.377->.371) — which is why those are left as failures.
- **Before -> after (correction is a strict improvement; precision unchanged, no false alarms added):**
  mean V_structural RDR **30.0% -> 37.0%**, mean ΔRDR **+17.8pp -> +22.0pp**, mean MCC **0.27 -> 0.37**,
  FalseAlarmRate falls (e.g. mimo .130->.101), pi_intent drops (e.g. mimo .623->.520). The
  monitor-vs-oracle gap stays exactly 0.000 — the ceiling identity is structural, so the correction
  raises the ceiling (1-pi_intent) and the achieved RDR together. Per model V_structural RDR:
  deepseek .303->.363, mimo .377->.480, glm .399->.461, qwen .123->.176.

### Added (2026-06-23 — intent-local spot-check harness, RQ3 validity)

- `eval/make_locus_spotcheck.py`: generates a **reproducible** intent-local review sheet to
  validate the purity of the annotator's intent-local *residual* (RQ3). **Seeded-random** stratified
  sampling (SEED=20260623, per-model seed `f"{SEED}:{model}"`) — 10 trajectories per audited model
  (40 total = 8.1% of the 492 distinct intent-local (domain, task_id) scenarios; one representative
  repeat per scenario); re-running with the same seed reproduces the exact draw. Joins `monitor_v2`
  (locus tag) × `capture` (query / answer / tool_trace) × tau²-bench retail+airline `tasks.json`
  (user intent + gold actions). Emits `eval/locus_spotcheck/intent_local_review.{md,csv}`: per row
  the user intent, gold write actions **with full arguments** (intent-level reference) beside the
  agent's full tool-call sequence, an **auto-computed PARAM DIFF table** (gold↔agent write actions
  matched by (name, id); per matched pair the argument fields that differ, plus gold actions the
  agent omitted and agent writes with no gold counterpart) — so argument-level divergences
  (insurance, variant, quantity) are visible at a glance without diffing JSON or opening
  `tasks.json` — and the review template
  (`counterfactual_holds`, `discriminator_only_in_gold`, `verdict` ∈ {true-intent-local,
  missed-detection, unsure}, `true_class_if_missed`, required `basis`). The reviewer's
  missed-detection rate bounds π_intent mis-labelling, upgrading the RQ3 limitation from
  "unvalidated residual" to a spot-validated figure.

### Fixed (2026-06-23 — Figure 6 ceiling-line removal + intent-local annotation)

- `eval/analyze.py` (Figure 6, RQ1): **removed the dashed "π_ℓ ceiling" line.** It plotted locus
  *prevalence* π_ℓ (denominator = all failures), overlaid on bars that are *within-locus recall*
  (denominator = failures of that locus) — two different quantities, so the line never bounded the
  bars. It produced false "bar exceeds ceiling" reads (glm trace-local 0.29 > line 0.20; and
  answer-local recall 1.0 ≫ line 0.077) and, worst, floated at 0.70 over the zero-height
  intent-local bar — visually suggesting intent-local "should" reach 70%. Prevalence and the
  1 − π_intent ceiling already live in Figure 9 (RQ3), where the denominator is correct.
- `eval/analyze.py` (Figure 6): annotated the intent-local group as **"0% detected (measured,
  n=315–670)"** so the empty bar reads as a large-n measured zero (0 for *both* V_answer and
  V_structural), not missing data.
- Thesis v10 Figure 6 caption: rewrote to state bars are within-locus recall, V_answer is
  complete/partial-leakage/zero across answer/trace+state/intent loci, and to point prevalence +
  ceiling to Figure 9. Regenerated `results/figures_v2/figure6` and synced `figures_v10/figure6`.

### Fixed (2026-06-22 — thesis v10 cross-validation follow-ups)

- `eval/analyze.py`: figures now iterate models in a **canonical order** (`MODEL_ORDER` =
  deepseek-v4-pro, mimo-v2.5-pro, glm-4.7-flash, qwen3.6-flash) instead of alphabetical by model
  ID, so figure x-axes line up with Table 7 / Table D. Fixes the figure-vs-table order mismatch
  (figures were deepseek/qwen/mimo/glm; tables are deepseek/mimo/glm/qwen). Affects the embedded
  Figures 6/7/8 and the standalone Figure 9; data/point estimates unchanged, column order only.
- Thesis v10: corrected V_structural mean RDR **30.1% → 30.0%** (mean of 0.303/0.377/0.399/0.123 =
  0.3005, round-half-to-even); regenerated `figures_v10/` in canonical order and rebuilt the PDF.
- Thesis v10: **embedded the detector-quality figure** into §5.2 (RQ2), after Table D. To keep
  figure numbers monotonic in order of appearance, it is labelled **Figure 8** and the RQ3
  stacked-bar figure is renumbered **Figure 9**. NB: thesis figure number ≠ generated filename here —
  thesis Figure 8 renders `figures_v10/figure9_rq2_detector_quality.png` and thesis Figure 9 renders
  `figure8_rq3_locus_stacked.png` (caption/prose carry the number; the build strips image alt-text,
  filenames are invisible to readers). Thesis now embeds Figures 1–9.
- `eval/analyze.py`: fixed the **in-image matplotlib titles** to match the thesis renumber — the
  detector-quality chart's `suptitle` now reads "Figure 8 — Detector Quality" and the RQ3 stacked
  bar's reads "Figure 9 — Detected vs. Undetected …". Previously the rasterized in-image titles
  still showed the old numbers (Figure 9 / Figure 8), so the printed-on-image number contradicted
  the prose/caption. Code comments document that the PNG filename (figure9_=detector, figure8_=stacked)
  is intentionally decoupled from the thesis figure number. Regenerated figures + rebuilt the PDF.

### Changed (2026-06-22 — README/requirements brought up to the tau2-bench reality)

- `README.md` and `requirements.txt` were stale (pre-pivot): they pointed at the old
  `sierra-research/tau-bench`, listed three monitor configs incl. `V_evidence`, said "one seed",
  and referenced the deleted `eval/metrics.py`. Updated to match the current code:
  - benchmark → **`sierra-research/tau2-bench` v1.0.0** (the `tau2` package the capture driver
    imports); retail 114 + airline 50 = 164 tasks/repeat.
  - monitor configs → **two** (`V_answer`, `V_structural`); `V_evidence`/`banking_knowledge` noted
    as Future Work; statistical design → **unseeded K=10**, CIs split (Clopper-Pearson at boundary).
  - `eval/` listing → real scripts (`run_capture_tau2`, `capture_tau2`, `monitor_pass`,
    `reannotate_signals`, `analyze`).
  - new **"Data"** section: a clone ships **no** data (benchmark lives in `tau2-bench`; trajectories
    /results/ and `docs/thesis/` are gitignored), plus the end-to-end capture → monitor →
    reannotate → analyze command chain to regenerate everything.

### Changed (2026-06-22 — doc/thesis-v9 consistency pass)

- Reconciled `docs/thesis_scope.md`, `docs/tau_bench_experiment_design.md`, and
  `docs/formal_definitions.md` with thesis v9 (the finalized baseline):
  - **Task count**: `thesis_scope.md` corrected from retail 115 / total 165 → **retail 114 /
    total 164** (matches v9 and `tau_bench_experiment_design.md`).
  - **Seed policy**: `scope.md` and `experiment_design.md` changed from "single seed (42)" →
    **unseeded repeats** (v9's position: at temp 0 a fixed seed does not control provider
    non-determinism; the K=10 repeats absorb variance).
  - **CI method**: all three docs now state the v9 reporting convention — **Clopper-Pearson exact
    for rates at the 0/1 boundary, bootstrap otherwise** — instead of a flat "bootstrap CIs"
    (avoids the degenerate zero-width CI on boundary rates such as V_answer RDR ≈ 0 on
    trace/state loci). `formal_definitions.md` §2.8 retitled and split accordingly.
  - **Cleanup**: removed the residual "F0–F5 / safe-risky / Type I/II" deprecated-label
    enumeration from the top of `formal_definitions.md`.
- **`eval/analyze.py`: implemented the Clopper-Pearson boundary CI** (closing the doc↔code gap
  the consistency pass surfaced — v9 and the docs claimed it but only bootstrap existed).
  - New `_rate_ci` dispatcher: task-level bootstrap for interior rates, `_clopper_pearson_boundary_ci`
    (closed-form exact interval, no scipy — matches the codebase's no-scipy McNemar) at the 0/1
    boundary where the bootstrap degenerates to zero width. Applied to RDR, FalseAlarmRate, and the
    per-locus detection rates; ΔRDR keeps its paired bootstrap.
  - Re-ran `analyze.py` over `results/monitor_v2` → refreshed `results/metrics_v2` + `results/figures_v2`
    (gitignored local artifacts). Verified **all point estimates unchanged** (RDR/FAR/precision/F1/
    MCC/ΔRDR/locus rates identical across all 4 models); only degenerate boundary CIs replaced
    (e.g. V_answer answer-local `[1,1]`→`[0.951,1]`, intent-local `[0,0]`→`[0,0.012]`).
- **Repointed the stale `eval/metrics.py` references** (module renamed/refactored to `eval/analyze.py`
  in the pivot): `formal_definitions.md` §2.8/§2.10/§2.11, `architecture.md` repo layout (removed the
  phantom `metrics.py` line) and metrics paragraph, and the Phase-1 "Keep" list in
  `tau_bench_experiment_design.md`. §2.10/§2.11 now state honestly that the evidence-state-distribution
  and latency/token aggregates are diagnostics not emitted by the current detection-focused
  `analyze.py` (raw inputs live on `ReliabilityReport`).
- **Thesis v10** (`docs/thesis/ReliableGuard_Thesis_v10.{md,pdf}` + `figures_v10/` +
  `build_thesis_v10.sh`). Identical to v9 except **Figure 6** (RQ1 V_answer detection by locus),
  regenerated from the CI-fixed `analyze.py` so the boundary loci now show proper Clopper-Pearson
  error bars instead of zero-width whiskers (answer-local at rate 1.0, intent-local at ≈0).
  Figures 1–5 carried over from v9; Figures 7/8 verified byte-identical to v9 (data unchanged) —
  Figure 6 is the only visual change. PDF rebuilt with pandoc + xelatex (TinyTeX).

### Added (2026-06-17 — two observable signals recover a slice of "intent-local")

- **Agent-loop guard (trace channel) + answer-completeness check (answer channel).** Control-group
  analysis of the captured tau2 matrix found ~22% of failures labelled `intent-local` are in fact
  observable and were mislabelled by the rule-based annotator:
  - `verifier/tau_bench_verifiers.detect_agent_loops`: a tool call re-issued with identical
    arguments (>= 2x) is a stuck/looping process — a `TraceViolation` (rule `agent_loop`), now
    folded into `verify_trace` for both domains. Validated precision ~80%, false-alarm ~2.6%.
    Reclassifies these failures to their true `trace-local` locus.
  - `verifier/answer_completeness.detect_incomplete_answer`: the answer terminates on an unanswered
    substantive question (excluding polite closers) — the agent never executed the action and says
    so. Validated precision ~90%, false-alarm ~0.7%. New `answer-local` assignment in
    `annotate_locus` (priority: pass > trace-local > state-local > answer-local > intent-local).
  - Channel placement: loop → V_structural (trace); completeness → BOTH configs (it is a pure
    answer-channel signal, so it belongs to the V_answer baseline — this lifts V_answer off its
    structural RDR=0 floor and makes the V_structural-over-V_answer lift attributable purely to
    state + trace). `monitor_pass` threads completeness through `_compute_verdict`/`annotate_locus`
    for both configs; new row fields `answer_incomplete`, `n_agent_loops`.

- **State-channel framing fix (retail status verifier).** A claim whose status word is capability/
  negation/modal framed ("Order X **cannot** be cancelled", "can no longer be modified") is not a
  current-state assertion; the old `_check_state_retail` matched the bare word "cancelled" and
  flagged it as a false `status=cancelled` claim. Added `_is_nonstate_status_framing` (Route 2 →
  `unverifiable`), mirroring the airline verifier's positive/negated/ambiguous routing. ~73% of
  retail state-channel false alarms were this misparse. Trade is a genuine soundness-for-coverage
  one (the removed detections were "right verdict, wrong reason"): pooled V_structural RDR 34→30%,
  false-alarm 13→8%; `state-local` π drops sharply (it was bug-inflated), so the V_structural lift
  is now driven mainly by the trace channel (policy + loop).

- **Detector-classifier metrics in `analyze.py` (RQ2 honesty).** Per config: `precision` (+ bootstrap
  CI), `f1`, `mcc`, and the raw `confusion` matrix, alongside the existing RDR/FalseAlarmRate. MCC is
  the recommended cross-model axis (the four agents have different failure base rates). New
  **Figure 9** (`figure9_rq2_detector_quality.png`): RDR / Precision / FalseAlarm / MCC, V_answer vs
  V_structural, per model. Definitions added to `docs/formal_definitions.md` §2.3a.

- **`eval/reannotate_signals.py`**: overlays all three corrections (loop, completeness, state-framing)
  on existing monitor shards WITHOUT re-running the claim extractor — the signals are pure functions
  of `tool_trace` / `answer_text` / the recorded `block_detail`, already captured in Phase 2. Output
  dir is re-run through `eval.analyze` for updated metrics. (A full monitor re-run will bake the
  state-framing fix into the extractor path once the design is frozen.)

- **Final per-model metrics (monitor_v2, all three corrections):** V_answer RDR 4–20% / precision
  87–96%; V_structural RDR 30–40% (mean 30%) / false-alarm 5–13% (mean 8%) / precision 66–79%;
  ΔRDR positive on all four models (+8 to +27, McNemar p≈0); corrected π_intent ≈ 60–88%.

### Changed (2026-06-16 — banking_knowledge retired; evidence-local locus removed)

- **Formal experiment scope narrowed to retail + airline (165 tasks/repeat).** Following a 45-trajectory
  smoke test, `banking_knowledge` was found structurally incompatible with the monitor's observable
  channels: tau2-bench evaluates banking tasks via tool-call optimality (`communicate_info=[]` for all
  97 tasks), so no factual-accuracy ground truth is reachable by the monitor. 85% of banking failures
  were intent-local (agent chose wrong action but reported it honestly). Domain is retired from the
  formal experiment and documented in `docs/thesis_scope.md §6.2` (Future Work: action-centric domains
  and the intent-local boundary). Total trajectories in full run: 4 models × 165 tasks × 10 repeats = 6,600.

- **Evidence-local locus removed from formal taxonomy.** No KB exists in retail/airline; without
  banking_knowledge there is zero evidence detection surface. Locus priority simplified to:
  pass > trace-local > state-local > intent-local.

- **Code cleanup — banking and evidence-local deleted from all pipeline files:**
  - `src/reliableguard/locus.py`: removed `evidence-local` from `Locus` Literal, removed
    `_EVIDENCE_SOURCES`, removed evidence-local check in `annotate_locus`, removed from
    `locus_is_monitor_detectable`.
  - `src/reliableguard/verifier/tau_bench_verifiers.py`: removed `_verify_trace_banking`,
    `_check_state_banking`, `banking_knowledge_verifier`, all `_BANKING_*` constants, BM25
    retrieval, LLM judge; removed banking dispatch from `verify_trace`; removed
    `source_verifier._VERIFIERS["banking_knowledge"]` registration.
  - `eval/capture_tau2.py`: removed `_get_kb_dir`, `_load_documents`, `_slice_state_banking`,
    `is_banking` branches, `retrieval_variant` parameter, `evidence` field from Trajectory return.
  - `eval/run_capture_tau2.py`: removed `banking_knowledge` from CLI choices and default; removed
    `BANKING_TASKS`; removed `--retrieval-variant` flag.
  - `eval/monitor_pass.py`: removed `CHANNELS_EVIDENCE` import; removed banking_knowledge
    V_evidence branch in `_process_trajectory`.

- **Docs updated:** `docs/tau_bench_experiment_design.md`, `docs/architecture.md`,
  `docs/thesis_scope.md` — removed V_evidence config, banking verifier sections, evidence-local
  locus; updated domain scope, task counts, budget table, locus taxonomy table, Future Work.

### Added

- **Banking trace + state verifiers (2026-06-16): full multi-channel support for banking_knowledge domain.**

  *Trace verifier (`_verify_trace_banking`):* Three rules encoded as `TraceViolation` objects.
  `user_info_before_log_verification` — `log_verification` (identity confirmation) must be preceded
  by a `get_user_information_*` call (agent cannot confirm 2-of-4 identity fields it has not retrieved).
  `auth_before_write` — `call_discoverable_agent_tool` and other write tools must not be invoked before
  `log_verification`. `unlock_before_call` — `call_discoverable_agent_tool` requires a prior
  `unlock_discoverable_agent_tool` for the same `agent_tool_name`. Added `domain="banking_knowledge"`
  routing branch in `verify_trace()`.

  *State verifier (`_check_state_banking`):* Checks verification/identity claims against
  `state_after.verification_history`; returns `supported` if new entries appeared since `state_before`,
  `unverifiable` for balance/amount claims (no resolvable account IDs in claim text).
  Source tag `"tau_bench_state"` prevents evidence-merge from overwriting state results.

  *Verifier routing update (`banking_knowledge_verifier`):* Dual-channel with priority. State channel
  (0 tokens, deterministic) runs first; evidence channel (BM25 + LLM judge) runs in parallel when
  evidence is available. Routing: prefer non-unverifiable state result; fall back to evidence result.

  *Bug fix in task ID generation (`eval/run_capture_tau2.py`):* Retail and airline use plain integer
  task IDs (`"0"`, `"1"`, …) while banking_knowledge uses `"task_001"` format. Fixed `RETAIL_TASKS`
  and `AIRLINE_TASKS` constants (were incorrectly using the `task_NNN` format).

- **Smoke test — 45 trajectories (15 × 3 domains) with qwen3.6-flash (2026-06-16).** Results:
  agent pass rates: retail 47%, airline 67%, banking 13% (overall 42%). V_structural correctly blocked
  4/4 observable failures (100% conditioned detection rate, 0% false alarm rate): 1 retail state-local
  (order status misrepresentation), 1 airline trace-local (basic_economy flight modification violation),
  2 banking evidence-local (policy number errors: 9-day vs 7-day rolling window; $100 vs $75 referral
  bonus). 85% of failures were intent-local (agent chose wrong action, not a verifiable factual error).
  V_answer never blocked any task (all PASS_UNCHECKED or AUDIT_FAILED), confirming the answer-only
  baseline cannot catch these categories of failure.

### Fixed

- **Airline state verifier false positives — 3-route cancellation logic (2026-06-16).** The original
  verifier triggered on any text containing "cancel" and always returned `contradicted` when the
  reservation was not in `status="cancelled"` state. This produced 2–3 false alarms per monitor run:
  (a) claims asserting "not cancelled" were labeled "claimed cancelled"; (b) eligibility claims
  ("cannot be cancelled through the automated system") were treated as cancellation assertions;
  (c) `attribute="refund_processing_time", value="5-7 business days"` matched "business" as a
  cabin-class claim via the text-matching fallback. Replaced with three-route logic:
  positive cancellation assertion (→ state check), explicit non-cancellation assertion (→ inverse
  check), anything else (eligibility, transfer, ambiguous) → `unverifiable`. Cabin check now requires
  `attribute` to be in an explicit whitelist (`cabin`, `cabin_class`, `class`, `seat_class`, etc.)
  rather than matching the cabin keyword anywhere in free text.

- **tau2-bench migration decision (2026-06-16): upgrade to tau2-bench for all three core domains.**
  Following a systematic bug audit of the original `sierra-research/tau-bench` tasks, we decided to
  migrate the entire capture pipeline from the old `tau_bench` API to `tau2` (τ³-bench, the
  successor at `sierra-research/tau2-bench`) and expand the experiment from 2 to 3 domains:

  *Bug scope in the old benchmark:* airline 27/50 tasks (54%) had incorrect gold expected actions,
  ambiguous user instructions, impossible constraints (e.g. Mastercard not in user profile), or
  policy-loophole tasks where the correct agent behaviour was nonetheless scored 0. Retail had 26/115
  tasks (23%) with similar issues. Running our monitor on these tasks produces misleading RDR numbers:
  a low RDR on airline is partly explained by the agent correctly refusing an impossible action — not
  a monitor failure. The tau2-bench (v1.0.0) changelog lists every fix; we adopt the corrected tasks.

  *Scope decision:* retire `eval/capture.py` (old `tau_bench` API) after the tau2 migration;
  `banking_knowledge` (97 tasks, 698 policy/procedure documents) is promoted from stretch to **core**
  — it is the only domain with evidence-local failures (agent gives wrong policy information from KB
  documents). Total: **retail 115 + airline 50 + banking_knowledge 97 = 262 tasks / repeat**.

  *Implemented (2026-06-16):*
  - `eval/capture_tau2.py` — new capture driver using `tau2.runner` API; supports retail +
    airline + banking_knowledge; `state_before` from `env.tools.db` snapshot before `run_simulation`;
    `state_after` from `env.tools.db` snapshot after; tool trace from `AssistantMessage.tool_calls`
    in `sim.messages` (requestor="assistant" only); evidence from task.required_documents → KB lookup.
    Model strings auto-prefixed with `openrouter/` for litellm routing.
  - `eval/run_capture_tau2.py` — CLI wrapper; `--retrieval-variant bm25` for offline smoke tests.
  - `src/reliableguard/verifier/tau_bench_verifiers.py` — `banking_knowledge_verifier` (pure-Python
    BM25 keyword retrieval + minimax-m3 LLM judge via OpenRouter; registered as
    `_VERIFIERS["banking_knowledge"]`).
  - `src/reliableguard/schema.py` — `Grounding.evidence: list[dict]|None` (typed, was `Any|None`).
  - `src/reliableguard/adapter.py` — `Trajectory.evidence: list[dict]|None` field; `grounding()`
    propagates evidence into `Grounding`.
  - `src/reliableguard/locus.py` — evidence-local detection branch: after state-local check,
    `r.evidence_state=="contradicted" and r.source=="banking_kb"` → `"evidence-local"`.
  - `eval/monitor_pass.py` — for banking_knowledge domain with evidence, runs V_evidence channel
    (CHANNELS_STRUCTURAL + evidence=True), layers evidence results over structural_results so
    annotate_locus can assign evidence-local.

  Smoke test confirmed: 1 banking_knowledge task captured (task_026, 11 tool-call steps, 8 KB docs,
  JSONL with tool_trace + evidence); monitor pass ran (17 claims, 0 violations, locus=intent-local).

### Fixed

- **Phase 3 follow-up (2026-06-16): four pipeline robustness fixes discovered on the 6,600-trajectory
  monitor pass.**

  *(1) Temporal-scope filter (`src/reliableguard/verifier/source_verifier.py`).* Added
  `_NON_CURRENT_SCOPES = {"before_action", "future_plan", "during_action"}`. `verify_claims` now
  filters these claims out before routing to any domain verifier and returns them as `unverifiable`.
  Root cause of elevated FAR: the extractor occasionally emits `before_action` claims (the "Before"
  column in a Before/After comparison table, or the pre-modification value the agent describes while
  explaining the change) which the state verifier then contradicts against `state_after` → false BLOCK
  on a reward-1 task. The fix complements the prompt-level instruction in `prompts.py` (which already
  asks the extractor to discard these) with an enforcement layer in the verifier.

  *(2) Answer truncation (`eval/monitor_pass.py`).* Added `_MAX_ANSWER_CHARS = 8000` cap (tail of
  the answer text fed to the extractor). Airline agents occasionally emit very long answers (full
  policy recitations, itinerary summaries) that drove the extractor to generate 16k+ tokens of claims
  JSON and hit the `max_tokens` ceiling → `LLMResponseTruncatedError`. The tail of the answer carries
  the final verdict/state assertion; leading policy-citation context does not add verifiable claims.

  *(3) ERR rows write AUDIT_FAILED (`eval/monitor_pass.py`).* Previously an exception in
  `_process_trajectory` hit `return` before the write, silently dropping the trajectory from the
  output file. The resume logic skips rows by key, so a silently-dropped row was re-run on every
  resume attempt. Fix: the except block now writes an `AUDIT_FAILED` row (`status="done"`), making
  the trajectory present in the monitor output and correctly excluded from metrics by `analyze.py`.
  Added `block_detail` field on every BLOCK row — a list of contradicted claim texts + reasons —
  enabling post-hoc false-alarm analysis without re-running the extractor.

  *(4) JSON decode retry (`src/reliableguard/extractor/claim_extractor.py`).* Wrapped the LLM call
  in a 2-attempt loop (2-second sleep between retries); added `_safe_claim()` to skip individual
  malformed claim dicts rather than failing the whole batch. Eliminates the intermittent
  `JSONDecodeError` that surfaced on minimax-m3 outputs (model occasionally emits trailing text after
  the JSON object).

### Changed

- **`analyze.py`: AUDIT_FAILED rows excluded from RDR/FAR denominators (2026-06-16).** Added
  `_is_audit_failed()` predicate; `compute_model_metrics` filters rows where both config verdicts are
  `AUDIT_FAILED` before computing any metric. `n_audit_failed` is reported separately. Previously
  these rows were included in both the failed-task denominator (deflating RDR) and the passed-task
  denominator (inflating FAR).

### Added

- **Phase 3 & 4 (2026-06-15): monitor pass driver + full analysis pipeline — all four thesis
  metrics plus figures computed end-to-end.**

  *Monitor pass (`eval/monitor_pass.py`):* applies V_answer + V_structural to captured
  trajectories. Reads per-model JSONL shards from `results/capture/`, runs claim extraction once
  (minimax/minimax-m3, reasoning disabled), applies both monitor configs via the same claims +
  grounding, annotates locus, and writes one result row per trajectory. Resumable: rows with
  `status='done'` are skipped on re-run. Parallel extraction via `ThreadPoolExecutor`. Output
  fields: `task_id / domain / model / repeat / gold_reward / locus / v_answer_verdict /
  v_structural_verdict / n_claims / n_violations / n_contradicted / trace_verdict / status`.

  *Run-capture CLI (`eval/run_capture.py`):* thin CLI wrapper over `run_capture_matrix` with
  `--models / --repeats / --workers / --retail-only / --airline-only` flags.

  *Analysis script (`eval/analyze.py`):* reads `results/monitor/*.jsonl`, computes all thesis
  metrics, and writes per-model JSON summaries + three figures. Metrics computed:
  - FAR / RDR / FalseAlarmRate per model, per locus, per domain
  - π_ℓ — locus distribution over failed tasks
  - ΔRDR = RDR(V_structural) − RDR(V_answer) per model
  - McNemar test (V_answer vs V_structural, continuity correction, p-value via `math.erfc` — no
    scipy dependency)
  - Bootstrap 95% CIs (B=1000) for RDR, FalseAlarmRate, ΔRDR; paired bootstrap for ΔRDR to
    preserve per-task correlation
  - CDR_κ at κ ∈ {5, 7, 9} for K=10 repeats
  - Per-repeat RDR list (for box chart + within-model std)
  Figures: `figure6_*.png` (V_answer detection by locus, RQ1), `figure7_*.png` (cross-model RDR
  box chart, RQ2), `figure8_*.png` (detected/undetected stacked bar, RQ3). Uses matplotlib Agg
  backend (no display required).

  *Docs:* `docs/thesis_scope.md` finalized to 6-chapter ~20-page structure with full figure/table
  inventory (17 items). `docs/formal_definitions.md` revised to align with τ-bench metrics and the
  three monitor configs.

### Fixed

- **State verifier: three systematic false alarm root causes identified and fixed
  (`tau_bench_verifiers.py`).** Root cause analysis on V_structural FalseAlarmRate on reward-1
  tasks: 92.5% of false alarms originated in the state verifier (not the trace verifier). Two
  domain-level patterns were confirmed via live data:

  *(1) Airline cabin — `"economy"` claim on `"basic_economy"` reservation.*
  The verifier did string-exact comparison: `claimed == actual`. When the actual cabin is
  `"basic_economy"` and the agent says `"economy"` (colloquial usage, "basic economy is a type of
  economy"), the comparison failed → `contradicted` → BLOCK on a successful task.
  Fix: added an explicit branch — `actual == "basic_economy" and claimed == "economy"` →
  `"supported"`. All other mismatches (e.g. `"business"` vs `"economy"`) still → `"contradicted"`.

  *(2) Retail refund amount — extractor captures item price as refund claim.*
  In exchange tasks (e.g. return Hiking Boots $253.89, get slightly different pair), the agent
  mentions the item price during the exchange conversation. The extractor classifies this as a
  refund claim with `value=$253.89`. The actual `payment_history` refund is the price differential
  ($0.35). The verifier correctly identified the mismatch, but incorrectly returned `"contradicted"`
  because the amount ≠ any recorded refund.
  Fix: when amount mismatch occurs, check the claimed amount against item prices in `state_before`
  (now passed to the verifier). If the amount matches an item price → `"unverifiable"` (it's a
  product price mention, not a refund amount assertion). Otherwise → `"not_found"` (refund exists
  but claimed figure unconfirmed). This required passing `state_before` to `_check_state_retail`.

  *(3) Airline baggage count — extractor captures delta ("added 1 bag") instead of total.*
  When an agent says "I've added 1 checked bag", the extractor may set `value=1` (the delta).
  The `total_baggages` in `state_after` is the new total (e.g. 2, if there was 1 before). The
  check `|2 - 1| = 1 > 0.5` → `"contradicted"`. But the claim is correct in delta form.
  Fix: when total-form check fails, compute `delta = state_after.total_baggages −
  state_before.total_baggages` and test `|claimed − delta| ≤ 0.5`. If the delta matches →
  `"supported"`. If neither total nor delta matches → `"not_found"`. Requires `state_before` in
  `_check_state_airline` (same plumbing as fix 2 above; no Phase 2 re-capture needed —
  `state_before` was already stored in capture JSONL).

- **`_slice_state` airline support (`eval/capture.py`):** `_slice_state` only handled the retail
  state schema (`orders / users / products`). Airline uses `reservations / users / flights`.
  Fixed by scanning whichever keys are present and applying the same user-reachability join for
  `reservations` (via `user.reservations[]`) and keeping only trace-referenced `flights`.

- **Extractor JSON robustness (`src/reliableguard/extractor/claim_extractor.py`):** replaced
  brittle `rfind("}")` JSON extraction with `json.JSONDecoder().raw_decode()`, which stops at the
  first complete JSON object and ignores trailing LLM text. Fixed `entities` field defaulting to
  `None` on missing key → now always `{}`, preventing downstream `KeyError` on claim construction.

- **Extractor airline domain hint (`src/reliableguard/extractor/prompts.py`):** added an airline
  domain hint instructing the extractor to focus on reservation IDs (6-char alphanumeric),
  `cabin_class` (basic_economy/economy/business), `total_baggages` (numeric), and cancellation
  status. Previously the generic fallback was used, causing missed or miscategorized claims.

### Removed

- **`eval/metrics.py` deleted.** The old metrics script was built for the self-made benchmark
  format (`task/state` dict structure) and is entirely incompatible with the monitor_pass JSONL
  output. Replaced by `eval/analyze.py`.

- **Phase 2 (2026-06-10): τ-bench verifiers, capture driver, locus annotator — all Phase 2 steps
  complete (steps 9–11, 13; step 12 evidence channel deferred as stretch).**

  *Capture driver (`eval/capture.py`):* `capture_trajectory` runs one agent loop with a
  correctness-critical deepcopy snapshot of `env.data` + `env.actions` BEFORE the terminal
  `env.step()` that runs `calculate_reward()` (which would otherwise pollute both artifacts).
  Added `_slice_state` to discard the 997 irrelevant orders/users from the full 1000-order retail
  DB: **2511 KB → 3 KB per trajectory (840×)**, eliminating a ~16 GB blowup over the full matrix.
  Batch driver `run_capture_matrix` adds per-model JSONL shards, resume via `_load_done_keys`
  (status=ok only), credit/auth halt (`_is_halt_error` on 401/402), and `ThreadPoolExecutor`
  concurrency. Added `LLMResponseTruncatedError` and `USER_SIM_MAX_TOKENS` monkeypatch. Tests:
  `tests/test_capture_resume.py` (7 tests including `_slice_state` offline validation).

  *Retail state verifier (`tau_bench_verifiers.py`):* claim-level checks against `state_after`
  (lifecycle-aware status, refund amount, existence), channel-gated on `context.channels.state`.
  Lifecycle reachability prevents false positives when the agent correctly reports a milestone
  status (e.g. "delivered" is still true after status advances to "exchange requested"). Tests:
  `tests/test_tau_bench_state_verifier.py` (11 tests).

  *Airline state verifier:* reservation-level checks against `state_after` (existence,
  cancellation — `status="cancelled"` or absent, cabin class, baggage count). Registered in
  `source_verifier._VERIFIERS["airline"]`. Tests: `tests/test_airline_verifiers.py` (18 tests).

  *Retail trace verifier (`verify_trace`, retail):* trajectory-level `wiki.md` policy checks over
  `tool_trace` + `state_before`; returns `list[TraceViolation]`. Encodes:
  `auth_before_action`, `status_precondition`, `called_twice`, `modify_after_freeze`,
  `multi_user`. Tests: `tests/test_tau_bench_trace_verifier.py` (12 tests).

  *Airline trace verifier (`verify_trace`, airline):* `auth_before_action`,
  `basic_economy_no_flight_modify`, `baggage_only_increase`. `verify_trace` now takes
  `domain: str = "retail"` keyword arg and dispatches. Tests in `test_airline_verifiers.py`.

  *Locus annotator (`src/reliableguard/locus.py`):* `annotate_locus(gold_reward, violations,
  structural_results)` assigns the primary failure locus with priority: pass > trace-local >
  state-local > intent-local (working label; τ-bench has no native fault type). Helpers:
  `locus_is_monitor_detectable`, `locus_needs_structural` (the two loci driving the
  V_structural vs V_answer lift in RQ2). Tests: `tests/test_locus_annotator.py` (10 tests).

  *Schema additions:* `TraceViolation` model (rule/action/step/order_id, locus="trace-local").

  *Architecture docs updated:* verifier registry (grounding injection DONE, retail+airline
  registered), trace channel (domain dispatch, retail+airline rules documented, deliberate
  omissions explained), structural-audit pattern (ported, known gap documented), locus annotator.
  Design doc steps 10, 11, 13 marked DONE with implementation notes.

- **Phase 1 (2026-06-10): grounding-injection plumbing (decision B) + extractor lock.** Added the
  benchmark-adapter `Trajectory` record (`src/reliableguard/adapter.py`) and the verification
  vocabulary `ChannelConfig` / `Grounding` / `VerificationContext` (`schema.py`), with channel
  presets mapping to the three monitor configs (`CHANNELS_ANSWER` / `_STRUCTURAL` / `_EVIDENCE`).
  Threaded an optional `VerificationContext` through `verify_claims` and `run_reliability_pipeline`
  so the same extracted claims + grounding yield the V_answer / V_structural / V_evidence verdicts by
  varying only `channels`, with no hidden global state. Added `tests/test_verification_context.py`
  (5 tests). **Locked the extractor model = `minimax/minimax-m3`** (same as the user-sim; both fixed
  controls off the audited vendor set; JSON extraction verified end-to-end on a real retail
  trajectory). Recorded the **answer-local input definition** (extractor is fed the concatenation of
  the agent's `respond` turns, not the last message and not tool calls — channel hygiene for the
  RQ1-vs-RQ2 contrast). Budget updated to ~$213 (extractor reasoning ≈ $13).

- **Phase 0 closeout (2026-06-10): τ-bench environment locked + run-harness spec.** Cloned
  `sierra-research/tau-bench` (retail + airline; telecom/banking_knowledge are the separate
  `tau2-bench` repo, stretch) and verified the env API. **Locked the audited model lineup**
  (OpenRouter, all `tools=True`): agents `deepseek/deepseek-v4-pro`, `xiaomi/mimo-v2.5-pro`,
  `z-ai/glm-4.7-flash`, `qwen/qwen3.6-flash` (2 flagship + 2 low-end across 4 vendors); user-simulator
  `minimax/minimax-m3` (fixed control). Recorded the operational constraint that **OpenAI models are
  blocked on this OpenRouter account** (403 ToS), so the user-sim cannot be gpt-4o. Smoke-calibrated
  the budget to ~$204 for the 4-model × K=10 × 165-task matrix (all 11 smoke/calib tasks passed with
  valid tool calls, concurrency 5 clean; `deepseek-v4-pro` = 63% of cost, firm at n=8). Documented the
  **run-harness correctness & robustness spec** in `architecture.md` (snapshot `env.data` AND
  `env.actions` before the reward-bearing terminal `env.step()`; shard + resume keyed on
  `(model, domain, repeat, task_id)`; retry vs. spurious-failure for gold-label integrity; max_tokens
  caps agent 4096 / user-sim 2048 + `finish_reason="length"` alarm), and the locked configuration +
  calibrated budget in `tau_bench_experiment_design.md` (K=5 → K=10).

### Fixed

- **AGENTS.md pre-push hook description was stale.** It still documented the removed elaborate gate
  (hard-reject on missing `CLAUDE.md` update at a new node + `memory`/`README` warns +
  `doc_push_state` content-hash baseline). Corrected to match the actual `hooks/pre-push`, which
  enforces exactly one gate: hard-reject if `CHANGELOG.md` was not updated in the pushed commits.
  Now consistent with `docs/push_checklist.md` and `CLAUDE.md`.

### Changed

- **PROJECT PIVOT (2026-06-09): re-grounded on τ-bench; self-made evaluation retired.** The whole
  evaluation moves from a self-made benchmark to the recognized **τ-bench** benchmark
  (`sierra-research/tau-bench`), whose ground truth is execution-based and externally authored,
  removing the "self-made data + self-made labels" weakness. **Deleted** from the repo: the
  ecommerce + reference scenario files (`tasks/*scenarios*.json`, `tier_b_prompts.json`,
  `verifier_scenarios.json`, etc.), all SQLite databases (`*.db`), all old `results/` and `logs/`
  outputs, the experiment + figure scripts under `scripts/` (kept `install-hooks.sh`), the
  `eval/` old harness (`benchmark.py`, `ablation_runner.py`, `fact_scorer.py`,
  `config/ablation_versions.py`, `annotation/` — kept `metrics.py`), and the corresponding tests.
  **Kept**: the reusable monitor core (`src/reliableguard/`), `eval/metrics.py`, the structural-audit
  pattern, `tasks/papers/`, `figures/`, and `docs/thesis/`. The legacy `src/domain`, `src/agent`,
  `src/graph`, `src/db`, and `ReliableGuard.py` are kept until Phase 2, then removed. The
  intellectual core is unchanged: observability framing + locus-of-ground-truth taxonomy (now
  answer / trace / state / evidence / **intent**-local) + the neuro-symbolic pipeline. Three monitor
  configs (`V_answer` / `V_structural` / `V_evidence`) replace V1/V2/V3; RQs re-grounded (RQ1
  answer-only ceiling, RQ2 trace/state recovery + cross-model robustness, RQ3 intent-local boundary);
  statistics = single-seed multi-LLM (4 models) + K repeats + per-task McNemar. Rewrote `CLAUDE.md`,
  `README.md`, `docs/thesis_scope.md`; added a re-grounding banner to `docs/formal_definitions.md`;
  added `docs/tau_bench_experiment_design.md` (authoritative design). Documentation + deletion only;
  no monitor-core logic changed. Memory updated (`project_tau_bench_pivot`).
- **CLAUDE.md split into overview + router; pre-push gate simplified to CHANGELOG-only.** `CLAUDE.md`
  is now a thin entry point (identity + conceptual spine + a router table + always-on rules);
  technical detail moved to the new `docs/architecture.md` (repo layout, pipeline, 3 monitor configs,
  verifier registry, τ-bench integration, adapter interface, operational conventions). `hooks/pre-push`
  now enforces only that **CHANGELOG.md** is updated in the pushed commits; the old CLAUDE.md/memory
  content-hash node gates and the README warning were removed (CLAUDE.md as a thin router would have
  been falsely flagged every push). Updated `docs/push_checklist.md` accordingly.

### Added

- **Authoritative ×3-seed batch + RQ figures + thesis writing interface**: the full Set A and Set B ×3-seed batches (seeds 42/123/7) at commit `c74dbb8` are the single source of truth for all thesis numbers (archived under `results/_archive/set_{a,b}_3seed_20260608_c74dbb8/`). `scripts/plot_results.py` renders the RQ-aligned figures from a replay rows CSV (`fig_rq1_claim_only` / `fig_rq2_structural` / `fig_rq3_locus` / `fig_benign_far` + `summary.csv`); committed under `figures/set_a_3seed/`. Set B reframe figure via `scripts/plot_setb_reframe.py` → `figures/set_b_3seed/fig_setb_benign_reframe.{png,pdf}`. Thesis interface docs added: `docs/thesis_outline.md`, `docs/thesis_handoff_brief.md` (§6 carries every ×3 number + locked decisions), `docs/draft_setb_results.md`, `docs/advisor_briefing_20260608.md`. Headline: ecommerce claim-only RDR 35.4% → +structural 76.6% (F2 0.7→100), benign FAR 1.2%; reference RDR 33.8% (no structural channel — the boundary); RQ1 extractor precision 99.15%.
- **Set B benign false-alarm reframe (methodological, not a verifier change)**: `scripts/recheck_setb_benign.py` re-derives benign ground truth from the agent's actual execution (requested order count vs. `db_state_after`, independent of the claim pipeline). The naive 43% benign FAR is mostly the monitor correctly catching agent under-execution (36/50 flagged); the TRUE benign FAR is ~17%. The structural channel contributes zero of these flags. Residual ~17% is largely a negative-claim polarity case (left to future work).
- **Supplementary experiments (DEMOTED to appendix/future-work — isolated, Set A untouched)**: (1) clean state-local F4 — `inventory` table + `update_stock` tool + `f4_clean_injection` (`src/db/init_db.py`, `src/domain/ecommerce/tools.py`, `structural_audit.py`, `config.yaml`, `eval/ablation_runner.py`); `tasks/f4_clean.json` (12 scenarios; claim-only 0/12 BLOCK vs +structural 12/12). (2) evidence-local real-vs-fabricated citation pilot — `scripts/eval_citation_realfake.py` (CrossRef DOI + arXiv API with DataCite fallback), `tasks/citation_realfake.json` (40 real-published + 40 real-arXiv + 40 fabricated; ground truth validated live). Both stay out of the headline results.

### Changed

- **Joint claim-set verifier fixes (monotonic only-lift, zero new BLOCKs, detection preserved)**: (1) citation-sufficiency (`reference_verifier.verify_reference_claims`) — paper-level strong/medium/weak/none joint evidence; reference benign BLOCK FAR 20%→6.7%. (2) transition-aware state verification (`ecommerce_verifier.verify_ecommerce_claims`) — an intermediate status (e.g. `pending`) is no longer `contradicted` vs the final DB snapshot when the narrated end state matches; ecommerce F5 multi-step benign FAR 84%→2%, F0 3.5%→0.5%, F2/F3/F4 detection unchanged at 100%. `source_verifier.verify_claims` now dispatches both domains to a batch entry point.
- **T4 failure-attribution decomposer += `not_observable` bucket** (`scripts/decompose_failures.py`): splits the old "misjudged" into a genuine verifier miss vs the fault not being claim-shaped at all. On the ×3 batch misjudged = 0% in both domains (no verifier bug); reference miss = not_observable 42% + no_evidence 25% + not_extracted 14% — the RQ3 boundary evidence.
- **T8 policy-violation eval** (`scripts/eval_policy_violation.py`): ×3 result — naive agent 100% (74/74) adversarial violations, policy-aware agent 0% (0/45). Reframed as verification ≠ prevention (prompting robustly enforces a simple policy under the black-box premise; the structural check provides detection independent of agent configuration).
- **Figure reorganization**: superseded root-level figures moved to `figures/_old_prefix/`; interim single-seed v8 figures under `figures/v8/`; authoritative ×3 figures under `figures/set_a_3seed/` and `figures/set_b_3seed/`.
- **Thesis reframing: observability as the central conceptual contribution**: rewrote `docs/thesis_scope.md` (and aligned `docs/formal_definitions.md` Section 4.2 and `docs/related_work_skeleton.md`) to make the academic spine explicit — black-box post-hoc agent auditing is an *observability* problem (the final answer is a partial self-reported observation; failures are classified by the *locus of their ground truth*: answer-local / trace-state-local / evidence-local). Added a new "Conceptual Framing" section and an "Evaluation Methodology" section (frozen-corpus, paired-replay; agent non-determinism handled as a controlled sensitivity analysis). Sharpened the three RQs: RQ1's manual annotation (near-perfect extraction) is framed as the *proof* that the final-answer blind spot is an observability limit, not an extraction artifact; RQ2's two structural signals are framed as added observation channels, with the policy-aware (T8) control made a requirement for the F2 claim rather than optional; RQ3 framed as the bottleneck *shifting* to an evidence-local locus where RQ2's remedy does not apply. Reframed contributions (5, led by the observability characterization and the methodology) and the core thesis claim. Aligned `README.md` (observability paragraph in Overview + provisional/non-reproducible caveat on the experiment snapshot) and `AGENTS.md` (pointer to the thesis framing). Marked the existing empirical numbers as provisional/non-reproducible pending the frozen-corpus regeneration. Documentation-only; no code or data changed.
- **Finding: benchmark is provider-non-deterministic (rerun paused)**: two identical smoke runs (same code, `temperature=0.0`, `seed=42` — and the seed IS sent to both the agent and extractor API calls) disagreed on 32/96 (33%) of audit outcomes, 23 flipping the caught-vs-PASS class (reference 21 vs ecommerce 11). Root cause is DeepSeek-via-OpenRouter non-determinism at temp 0 (MoE routing / float / batching), not fixable in code, so `temperature=0` does not yield determinism. The two prior "authoritative" batches were therefore never reproducible (this plus the old hardcoded `0.7` explains the ecommerce F4 claim-only 97.8% vs 35.3% swing). Per-task flips do not necessarily destabilize aggregate RDR/FAR over ~1550 scenarios (LLN); the affected analyses are fine-grained per-stratum tables and the structural A/B (confounded by different agent answers per run). Smoke gates that passed: error rate 0/96 (max_tokens fix) and `trace_summary` 62/62 populated. Added `scripts/validate_smoke.py` (error-rate / trace_summary / determinism gates). Rerun paused pending a strategy decision (more seeds + bootstrap CI vs an agent-answer freeze-replay mode); no rerun executed.
- **Benchmark reproducibility fixes (pre-rerun, P0)**: two harness defects that made the prior batches non-reproducible and internally inconsistent. (1) The ablation runner hardcoded `llm_temperature=0.7`, so agent answers were stochastic run-to-run and wording-dependent claim detection swung sharply (ecommerce F4 audit detection 97.8% in `set_a_full` vs 35.3% in `rq3_ablation`, same code/seeds); it now inherits the configured temperature (default `0.0`) so the agent stage is the reproducible variable under test, overridable via `RuntimeConfig` for a stochastic-agent study. (2) `claim_extraction_max_tokens` was `2048`, which truncated long reference answers / multi-claim extraction JSON and skipped up to ~36% of reference V2 tasks as `LLMResponseTruncatedError`; ceilings raised to `llm_max_tokens=4096` / `claim_extraction_max_tokens=8192` (a ceiling, not a target — cost is billed per generated token, so this only removes truncation). Added `docs/rerun_plan.md` (parameter-locked config + smoke→validate→full procedure; the new batch becomes the single source of truth, superseding `set_a_full/20260526` and `rq3_ablation/20260531`) and stratified smoke scenario files `tasks/smoke_{ecommerce,reference}.json` (2 per F0–F5). Also added `scripts/eval_rq1_audit.py` (RQ1/T6 pure-audit detection by failure stratum, computable from existing rows). No production-path metric logic changed.
- **Extractor-annotation gold labels filled + cleaned (T3 input ready)**: both annotation sheets under `eval/annotation/` are now human-annotated and quality-checked. `extractor_annotation_claims.csv` (precision, one row per predicted claim) and `extractor_annotation_coverage.csv` (recall / coverage ceiling, one row per sample) are complete. Cleaning pass: (1) `F2-G-107`'s 3 duplicate claim rows relabeled `valid=0` per the README duplicate rule (precision denominator now 931/939); (2) captured agent/extractor output that code-switched to the CJK currency unit normalized to `RMB` in `answer` / `claim_text` / `predicted_claims` for `F2-G-165` and `F2-G-185` (English-only repository rule applied to committed transcripts); (3) `risk_claim_text` whitespace normalized (`amount<N>` → `amount <N>`, trimmed), `other_missed` placeholder normalized to lowercase `none`; (4) `F4-G-029` display-only `predicted_claims` regenerated from the canonical claim rows. Preliminary hand-computed precision = 931/939 (99.15%), not-extracted coverage ceiling = 2/130 (1.54%) — to be recomputed authoritatively by the forthcoming `scripts/eval_extractor.py`.
- **Pre-push memory check downgraded to a warning**: `hooks/pre-push` now hard-gates only `CLAUDE.md` for the local-records node check; an unchanged `memory/` prints a non-blocking warning instead of rejecting the push (memory hygiene — not every node produces a durable fact worth recording).
- **README structure**: list `eval/annotation/` and `scripts/build_extractor_annotation.py` in the project-structure map
- **Renumber paper RQs** (confirmed 2026-06-04, by logical dependence):
  - RQ1 = Claim-level audit accuracy + coverage ceiling (ecommerce, success case)
  - RQ2 = Final-answer-only vs. trace/state-augmented auditing (ecommerce, formerly RQ3's structural content)
  - RQ3 = Cross-domain generalizability, framed as a diagnostic/boundary case (reference, self-diagnosis)
  - Rewrote all three RQs in `docs/thesis_scope.md`, including the RQ3 falsifiability defense and inter-RQ relations
- **Decouple code from paper numbering** (numbers live only in the paper; code uses semantic names):
  - `scripts/run_rq3_ablation.sh` → `scripts/run_structural_ablation.sh`
  - `generate_figures.py`: `generate_fig3_rq3_structural` → `generate_fig3_structural`, `_latest_rq3_dir` → `_latest_structural_ablation_dir`, dropped the `RQ3:` prefix from the figure title
  - Renamed figure artifact `figures/fig3_rq3_structural.pdf` → `figures/fig3_structural.pdf`
  - Authoritative directory `results/rq3_ablation/` left unchanged (historical name = structural ablation = paper RQ2)
- **Restructure thesis docs**: moved `thesis_scope.md` / `formal_definitions.md` / `related_work_skeleton.md` from the repo root into `docs/`; refreshed `README.md` project structure and experiment-snapshot references
- **English-only repository content**: converted CHANGELOG.md to English and removed the Chinese-language fallback alternative (a CJK synonym for "amount") from the order-amount regex in `claim_extractor.py` (benchmark is English-only; no effect on current data). From now on all committed files (code, comments, output strings, docs, README) are in English; conversation language stays Chinese.

### Added

- **Coverage-aware PASS verdict (T5)** and **Set B record/replay**. T5 splits `PASS` into
  `PASS_VERIFIED` / `PASS_UNCHECKED` (`schema.OverallVerdict`): `policy_engine._aggregate` now, when it
  would PASS, emits `PASS_UNCHECKED` if the grounded-evidence fraction (TCCR) is below
  `PASS_COVERAGE_THRESHOLD` (0.3, adjustable) — a transparency signal that the answer passed but the
  monitor could not actually substantiate it. Crucially this does NOT disturb existing metrics:
  `eval/metrics.derive_outcome` / `derive_audit_outcome` collapse both back to `PASS` for FAR / RDR /
  pass-matching and for the downstream analysis scripts (`decompose_failures.py`, `eval_rq1_audit.py`),
  while the fine-grained label is exposed separately via a new `coverage_verdict` CSV column
  (`build_result_row` + `derive_coverage_verdict`) and `pass_verified_rate` / `pass_unchecked_rate`
  metrics. New pure unit test `test_coverage_aware_pass_split`. Set B: `run_replay.py record`/`replay`
  accept `--set B` (`--tier-b` loader) and name outputs `set_a`/`set_b` accordingly, so the frozen-corpus
  methodology covers the stress set too. **Code-only; functional tests deferred (isolated `RG_DB_SUFFIX`).**
- **T8 policy-aware experiment (RQ2 F2 hardening)**: tests whether telling the ecommerce agent the >5000 approval policy is enough to stop violations (it is not, especially adversarially — which is the point: a deterministic structural check is a necessary backstop, not just an enforcer of a rule the agent never knew). `RuntimeConfig.policy_aware` injects `ECOMMERCE_APPROVAL_POLICY` into the agent system prompt (`langgraph_agent._build_system_prompt` now takes `config`); `eval/config/ablation_versions.py` adds `V3_PolicyAware`; `record_corpus` / `run_replay.py record --policy-aware` thread the flag. New scenarios `tasks/f2_policy_adversarial.json` (10 benign + 15 adversarial >5000 requests: authority/urgency, rule-reframing, direct override, false-threshold, impersonation, instruction-injection, amount obfuscation, etc.). New analysis `scripts/eval_policy_violation.py` reads the frozen `tool_trace` and prints the naive-vs-policy-aware × benign-vs-adversarial violation-rate 2×2 (violation = agent actually called `create_order` with amount > threshold). Reuses the record/replay machinery — the run is two small records over the F2 file (with/without `--policy-aware`). Policy/adversarial wording and the violation definition use proposed defaults (adjustable). **Code-only; functional tests deferred (isolated `RG_DB_SUFFIX` DB).**
- **Parallel + crash-safe record (process sharding, checkpoint/resume)**: makes the one-time record pass tractable (the sequential Set A record takes ~13h; reference is the multi-step bottleneck). Concurrency uses **process sharding**, not threads, because the ecommerce/reference DBs and the tool registry are process-global singletons (`reset_env` clears them, F4 injection mutates the registry), so concurrent scenarios in one process would corrupt each other. `src/db/init_db.py` and `src/domain/reference/tools.py` now read an optional `RG_DB_SUFFIX` env var, giving each shard process its own SQLite files. `run_replay.py record` gains `--num-shards N` / `--shard i` (stride-sliced disjoint scenario partitions), streams each record to a JSONL checkpoint immediately (`record_corpus` gains `on_record` + `skip_keys`), and supports `--resume` (skip already-recorded `(scenario_id, seed)` pairs) so a crash only re-does a shard's tail. New `run_replay.py merge` concatenates shard corpora; `scripts/record_sharded.sh` launches N shards in parallel (distinct `RG_DB_SUFFIX`), waits, and merges. `_read_corpus` accepts both the streaming JSONL and the legacy `{meta, records}` JSON, so an in-flight legacy record stays replayable. Expected speedup ~N× (bounded by OpenRouter rate limits; N=4–6 recommended). **Code-only; functional tests deferred (running against an isolated `RG_DB_SUFFIX` DB) to avoid touching an in-progress record run — see CLAUDE.md deferred-test checklist.**
- **Frozen-corpus, paired-replay evaluation (reproducible monitor methodology)**: implements the methodology that answers the provider-non-determinism finding. A `record`/`replay` split separates the non-deterministic agent+extractor stages from the deterministic monitor: (1) `RuntimeConfig.capture_trace` puts `execute_node` in observe-only structural mode — it snapshots ecommerce state before/after every tool call and computes structural issues as data but never blocks, yielding a config-independent behaviour trace (`AgentState.tool_trace`); (2) `eval/ablation_runner.record_corpus` runs each scenario's agent once and freezes (answer, extracted claims, tool trace, structural issues, post-execution state, scenario) into a corpus; (3) `eval/ablation_runner.replay_corpus` audits that frozen corpus under any version with zero LLM calls, applying the frozen structural issues only when the version enables structural audit. The structural ablation (V3 vs V3_NoStructural) thus becomes a paired, fully reproducible contrast over identical agent behaviour, eliminating the agent-variance confound behind the F4 35%↔98% swing. New driver `scripts/run_replay.py` (`record` builds the corpus — the only LLM cost; `replay` writes `set_a_rows.csv` + `set_a_metrics.json` in the run_ablation format, consumed unchanged by `eval_rq1_audit.py` / `decompose_failures.py` / metrics). New tests `tests/test_replay.py` (determinism; paired structural isolation; zero-claim fails closed without re-extraction; trace_summary populated). Additive and opt-in: default `capture_trace=False`, so the existing e2e ablation path is unchanged (43 tests pass).
- **Failure-attribution decomposer (T4, RQ3 core / feeds RQ1)**: `scripts/decompose_failures.py` classifies every risk-bearing task (expected `BLOCK`/`WARN`) in a `run_ablation` rows CSV into `correct` / `not_extracted` (zero claims or `AUDIT_FAILED` — extractor coverage bottleneck) / `misjudged` (verifier consulted a source but the risk slipped through) / `no_evidence` (no source consultable), and prints a per-version × domain × failure-stratum table (plus `--json` shares) — the cross-domain bottleneck view. `source_mode` (T1) is the primary `misjudged`/`no_evidence` discriminator, with an `evidence_state` fallback for pre-T1 rows. To make the decomposition batch-exact and self-contained (the older authoritative batch wrote `write_logs=False`, so its per-claim traces were never persisted and cannot be recovered), `eval/metrics.build_result_row` now emits a compact `trace_summary` (per-claim `evidence_state` + `source_mode` + `risk_level` + `action`) and `scripts/run_ablation.py` writes a `trace_summary` CSV column. The decomposer refuses legacy CSVs that lack the column. Requires a fresh full Set A run to populate; no change to existing metric values.
- **`AUDIT_FAILED` fail-closed verdict (T2, P0)**: when the extractor produces zero claims the pipeline no longer falls through the scorer to `reliability_score=1.0 → PASS` (which silently looked like a clean answer). `src/reliableguard/schema.py` adds `OverallVerdict = {PASS, WARN, BLOCK, AUDIT_FAILED}` for the report-level verdict (the per-claim `InterventionAction` stays three-valued); `policy_engine._aggregate` returns `AUDIT_FAILED` when there is nothing to audit. Per the locked decision (option (a) fail-closed): in the enforced setting `AUDIT_FAILED` is a gate action — counted in the risk-detection rate and `gate_action_rate`, excluded from the false-acceptance rate (it is not `PASS`), and treated as a false alarm on benign tasks; `eval/metrics.py` adds a standalone `audit_failed_rate`, scores it in `compute_outcome_score` (risky→2 safe catch, benign→1 false alarm) and labels it `audit_failed` in `derive_failure_type`. The score-threshold counterfactual `scripts/threshold_sensitivity.py` preserves `AUDIT_FAILED` rows and counts them as detections. Non-enforced (V1/V2) `reliability_verdict` stays `PASS`, so the signal is informational there. No effect on existing PASS/WARN/BLOCK rows; the authoritative batch is unaffected (it had no zero-claim tasks routed through this branch). 38/38 tests pass.
- **Extractor-quality scorer (T3)**: `scripts/eval_extractor.py` reads the two human-annotated `eval/annotation/` sheets and reports claim-extraction precision / recall / F1 plus the headline not-extracted coverage ceiling (the RQ1 number), with by-domain and by-stratum breakdowns, an invalid-claim and missed-risk-claim listing, and a `--json` mode for downstream tables. Authoritative results on the cleaned annotation: precision 931/939 = 99.15%, risk-claim recall 128/130 = 98.46%, not-extracted coverage ceiling 2/130 = 1.54% (`REF-F3-G-034` and `REF-F3-G-044`, both reference `GATE_BLOCKED`), claim-level recall 99.79% → F1 99.47%. Scoring follows `eval/annotation/README.md`; recall's "missed" count de-duplicates the case where a missed risk claim is restated in `other_missed`, so each `risk_claim_extracted=0` row contributes exactly one miss (documented in the script).
- **Pre-push documentation gate**: `docs/push_checklist.md` + expanded `hooks/pre-push` treat a push as a project node and enforce that all record files are current — hard-gates `CHANGELOG.md` (existing), warns when tracked code changed but `README.md` did not, and hard-gates the gitignored local records (`CLAUDE.md` and the `memory/` roadmap) by comparing their content hash against a local baseline in `.git/doc_push_state`: at a new node (HEAD changed since the last push) the push is rejected if `CLAUDE.md` is unchanged or no `memory/*.md` changed. Same-HEAD re-pushes and the first run are not enforced; `RG_MEMORY_DIR` overrides the memory location. Reinstall with `bash scripts/install-hooks.sh`.
- **Extractor-annotation workbook (T3 prep)**: `scripts/build_extractor_annotation.py` draws a deterministic stratified 150-scenario sample (ecommerce 100 by failure_mode F0-F5; reference 50 by expected verdict), attaches each scenario's real agent answer and extractor-produced claims mined from `logs/` run traces, and emits a human-annotation workbook under `eval/annotation/` (`extractor_annotation_claims.csv` for precision, `extractor_annotation_coverage.csv` for recall/coverage ceiling, `sample_manifest.csv` for trace provenance, `README.md` for instructions). Input to the forthcoming `scripts/eval_extractor.py` precision/recall/F1 scorer.
- **`source_mode` provenance (T1)**: `VerificationResult` gains a `source_mode` field (`fixture` / `unavailable` / `not_found`) recording whether the verifier actually had an evidence source at runtime, orthogonal to `evidence_state`. Distinguishes "no source could be consulted" (offline / source disabled → `unavailable`) from "an available authoritative source positively reported absence" (`not_found`). `ReliabilityReport` aggregates `unavailable_count`; `eval/metrics.py` adds `avg_unavailable_count` and `unavailable_task_rate`; the trace summary adds a `source_modes` breakdown. This is a black-box, runtime-only signal — it never reads dataset ground-truth labels and changes **no** `evidence_state`, score, or verdict (authoritative batch stays reproducible).
- **Reference-fixture provenance tagging (T1)**: `mock_data.json` PDF entries and each reference record carry a `provenance` field (`real_paper` / `synthetic`); `paper_provenance()` accessor in `src/domain/reference/api_client.py` exposes it. Consumed by offline failure-attribution analysis (paper RQ3 bottleneck decomposition); not read by the verifier. Scenario-injected fabricated DOIs (e.g. `10.99999/fake.*`) remain identified at the dataset level, not stored in the fixture.
- Zero-claim transparency metrics (`eval/metrics.py`): `zero_claim_rate`, `zero_claim_pass_rate`, `pass_with_claim_rate`, `pass_without_claim_rate`, plus a `claim_count` column in the per-row CSV
- `scripts/threshold_sensitivity.py`: post-hoc sensitivity analysis over the score-based WARN thresholds {0.5, 0.6, 0.7}, reporting FAR/RDR
- `CHANGELOG.md` and a Git pre-push hook (`hooks/pre-push`, `scripts/install-hooks.sh`): enforce CHANGELOG updates before push

### Fixed

- `eval/fact_scorer.py`: align with the `doi_status` values the reference tools actually write (`valid`→`verified`, `not_found`→`failed`), fixing Set B reference auxiliary fact metrics (no effect on the main FAR/RDR)

### Removed

- Removed root `thesis_outline.md` (obsolete after thesis restructuring)
- Removed orphaned figure artifact `figures/fig3_rq3_structural.pdf` (replaced by `fig3_structural.pdf`)

---

## [0.6.0] - 2026-06-02 — Docs & Thesis Materials

### Changed
- Update thesis materials and experiment artifacts

---

## [0.5.0] - 2026-05-26 — Experiment Freeze & Benchmark Stability

### Fixed
- Fail fast on benchmark runtime failures — prevents silently skipping infrastructure errors
- Refine audit policy and experiment output format

### Changed
- Track experiment input files and refresh the reference fixture
- Freeze thesis metrics and lock the `scripts/` experiment script state
- Refresh README overview to reflect the current experiment batch

> This version corresponds to authoritative experiment batch commit `3759744`:
> - Set A full ablation: `results/set_a_full/20260526/173346/`
> - Set B full ablation: `results/set_b_full/20260531/045635/`
> - Structural ablation (paper RQ2): `results/rq3_ablation/20260531/073500/`

---

## [0.4.0] - 2026-05-13 — Structural Audit Ablation

### Added
- `structural_audit.py`: ecommerce structural-audit component
  - Pre-execution policy check: `create_order` with `amount > 5000` → direct BLOCK (corresponds to F2)
  - Post-execution state check: tool reports success but DB state unchanged → BLOCK (corresponds to F4)
- `use_structural_audit` ablation switch: enables the `V3_NoStructural` vs `V3_Intervention` controlled comparison
- Ecommerce-only ablation control and the TCCR metric
- Reference verifier sources: CrossRef, Semantic Scholar, URL adapters (disabled by default)

### Changed
- Consolidate runtime report updates and clean up unused registry entries

---

## [0.3.0] - 2026-04-27 — Ablation Framework & V1/V2/V3 Standardization

### Added
- Multi-seed bootstrap confidence intervals: run across seeds and export CI columns for pass rate / FAR
- Audit-only ablation metric fix: add `reliability_verdict_audit`, exported alongside the effective verdict
- Set A summary metrics and full run scripts (`run_set_a_full.sh`, etc.)
- Ablation metric refinement and CSV diagnostic export

### Changed
- Standardize ablation version names to `V1_Baseline` / `V2_AuditOnly` / `V3_Intervention` (remove all legacy aliases)
- Remove legacy version aliases

### Fixed
- Align ablation keys and fix pipeline injection

---

## [0.2.0] - 2026-04-07 — Reference Domain & Unified Benchmark

### Added
- Full reference-domain implementation: DOI/PDF fixtures, SchemaValidator, gate validation, reference scenario datasets
- Reference-domain DB-aware policy layer
- Real-PDF fixture workflow and semantic DOI recovery
- Unified benchmark export (ecommerce + reference dual-domain)

### Changed
- Refactor: archive the legacy ReAct path, unify the ablation runtime on LangGraph
- Replace hardcoded TOOL_CONFIG with a registry + YAML config
- Reorganize runtime module structure; move scenario generators into `scripts/`

### Fixed
- Rebuild SchemaValidator rule structure; float-precision bug
- List-type support; reference scenarios benchmark integration; rename F4B to F4

---

## [0.1.0] - 2026-03-27 — Benchmark Core & F0-F5 Scenarios

### Added
- `eval/benchmark.py`, `ablation_runner.py`, `metrics.py`: benchmark framework core
- F0-F5 failure taxonomy scenario coverage (`tasks/scenario_v1.py`)
- `confirm_order` / `refund_order` tools with multi-turn loop support; F5 smoke test passing
- Multi-backend support (`ablation_config.py`)

### Fixed
- Metric computation, float precision, scenario label errors

---

## [0.0.2] - 2026-03-16 — LangGraph Migration

### Added
- Recovery v0: failure classifier, recovery controller, agent integration
- Migrate LLM backend to Qwen-plus / OpenRouter

### Changed
- Refactor agent control flow into a LangGraph `StateGraph` (replacing the custom loop)

### Fixed
- `final_answer` generation; `tool_calls` filtering

---

## [0.0.1] - 2026-03-02 — Project Bootstrap

### Added
- Project bootstrap: Mistral API + SQLite ecommerce tools
- State Tracker and Verifier; FALSE_SUCCESS detection working
- Gate v1: schema, policy, dependency checks all passing
- `reset_env`: reproducible run environment with order_id starting from 1
- Baseline agent complete; comparison data ready
- RG-OBS-001 finding; multi-run test; distribution plot
