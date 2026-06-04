# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

Before every push to GitHub, add an entry under `## [Unreleased]` describing the change,
and include CHANGELOG.md in the same commit as the code changes.

---

## [Unreleased]

### Changed
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
