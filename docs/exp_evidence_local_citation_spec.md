# Supplementary Experiment Spec — Evidence-Local Citation Verification (real vs fabricated)

> Purpose: realize the reference domain's **original intent** — use a live authoritative source
> (CrossRef) to decide whether a citation is *real or fabricated* — and turn it into the clean
> RQ3 boundary demonstration. The main Set A benchmark stays offline/deterministic; this is a
> dedicated **online case study**.
>
> Core result wanted: the **offline vs online contrast**. Offline, a fabricated citation is
> indistinguishable from "real but absent from the local fixture" (the irreducible
> evidence-local boundary: `unavailable ≠ not-exist`). Online, the channel reaches the locus,
> so fabricated citations are caught. Detectability is governed by whether the channel reaches
> the locus — exactly RQ3's thesis.

## 1. Data sources (already in the repo)

- **Real citations:** the reference lists of the real papers in `tasks/papers/` are already
  parsed into `src/domain/reference/fixtures/{mock_data.json,real_data.json}` under
  `pdfs[*].references` (19 PDFs tagged `provenance: real_paper`; 565 refs, 406 with DOI).
  These are genuine references → they should resolve on CrossRef.
- **Engine (already built):** `scripts/check_references_external.py` reads `real_data.json`,
  queries CrossRef by DOI (or by title/author metadata fallback), scores title/author
  similarity, and emits a per-reference verdict to `results/reference_external_check/`. This is
  the online checker; the `verifier_sources` CrossRef adapter
  (`src/domain/reference/sources/crossref.py`, `config.yaml` `enabled: false`) is the in-pipeline
  equivalent.

## 2. Build the test set (~50 real + ~50 fabricated)

1. **Real arm (~50):** stratified sample of `provenance: real_paper` references **that carry a
   DOI** (so CrossRef-by-DOI is exercised). Spread across multiple source papers.
2. **Fabricated arm (~50):** synthesize plausible-but-nonexistent references:
   - DOI in the reserved fake namespace `10.99999/fake.NNN` (consistent with existing scenario
     fakes), guaranteed not to resolve.
   - Plausible title (recombine real-sounding terms) + plausible author surnames + a year.
   - Tag `provenance: synthetic`, `ground_truth: fabricated`.
3. Store as a standalone fixture, e.g. `tasks/citation_realfake.json`, each entry:
   `{ "ref_id", "title", "authors", "doi", "year", "ground_truth": "real"|"fabricated", "source_paper" }`.

## 3. MANDATORY ground-truth second check (do this BEFORE running the experiment)

The labels I write are **hypotheses** until confirmed against the live source. Validate once at
construction time and freeze the result:

1. **Every `real`-labeled ref must actually resolve on CrossRef.** Run the DOI through
   `query_crossref_doi` (in `check_references_external.py`); require a hit with title similarity
   ≥ 0.85. **Failure handling:**
   - DOI does not resolve, or it resolves to a *different* title → the fixture DOI is wrong or
     the paper is arXiv-only with no CrossRef DOI. **Do not silently keep it as "real".**
     Either correct the DOI from the PDF, or **relabel/drop** that ref. (This is the exact
     real-vs-fabricated confusion the thesis is about — getting it wrong here would poison the
     ground truth.)
2. **Every `fabricated`-labeled ref must NOT resolve on CrossRef** (no DOI hit; metadata search
   returns nothing above threshold). If a synthesized title accidentally matches a real paper,
   regenerate it.
3. Record the validation output (CrossRef raw response + decision) to
   `results/citation_realfake/ground_truth_validation.json` so the labels are auditable and
   the run is reproducible from a frozen snapshot.
4. **Freeze** the validated set + the CrossRef responses, so the headline numbers do not drift
   with live API changes between runs.

## 4. Run two modes (the contrast is the result)

- **Offline mode:** check each ref against the local fixture only (CrossRef disabled). A
  fabricated DOI → `not_found`; but a real DOI absent from the fixture also → `not_found`.
  Expect: cannot separate fabricated from real-but-absent.
- **Online mode:** enable the CrossRef source (config `enabled: true`, or run the external
  checker). Fabricated → not found; real → found. Expect: clean separation.

Use the existing checker for the engine; if wiring into the pipeline, flip the `crossref`
`enabled` flag for this run only and revert after.

## 5. Metrics

On the validated set, report for **each mode**:

- **Fabrication detection rate** = fraction of `fabricated` refs flagged (`not_found` /
  `contradicted`). Online should be high; offline near-zero *as a discriminator*.
- **False-alarm on real** = fraction of `real` refs wrongly flagged.
- The key sentence: offline conflates `unavailable` with `not-exist` (boundary); online
  resolves it (channel reaches locus).

Tie back to the Set A reference locus decomposition (`no_evidence = 25%`, reference F4 = 82%
`no_evidence`): that 25% is exactly this offline `unavailable ≠ not-exist` boundary, and this
experiment shows it is **crossable iff** an online authoritative channel is added.

## 6. Scope / honesty

- Online breaks determinism → **case study only**; main Set A stays offline. Freeze the
  validated CrossRef responses for reproducibility.
- Network + rate limits: throttle (the checker already has a `--delay`); ~100 refs is small.
- Conclusion to claim: *the framework's evidence-local performance is bounded by source
  availability, not by a verifier defect — give it the channel and it works; withhold the
  channel and the boundary is provable.* Do **not** claim the offline boundary is a framework
  flaw.
