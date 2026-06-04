# Extractor Annotation Workbook (RQ1 coverage-ceiling study)

You are judging **claim-extraction quality only** — whether the extractor turned the
agent answer into the right factual claims. Do **not** judge whether the verifier later
ruled a claim supported/contradicted; that is a separate study and is deliberately not
shown here to avoid anchoring.

Sample: 150 scenarios — ecommerce 100 stratified by failure_mode (F0-F5), reference 50
stratified by expected verdict. The `answer` and predicted claims are real system run
traces (see `sample_manifest.csv` for the source trace of each scenario).

## File 1 — `extractor_annotation_claims.csv` (PRECISION; one row per predicted claim)

Most of the work is here. For each predicted claim fill:

- `valid`: `1` if the claim is a faithful, well-formed factual claim that the answer
  actually asserts AND the structured parse is correct (right entity / attribute /
  value, shown in `claim_struct`). `0` if it is hallucinated (not stated in the answer),
  malformed, a duplicate of another row, or a wrong parse.
- `note`: optional, especially to explain a `0`.

## File 2 — `extractor_annotation_coverage.csv` (RECALL / coverage ceiling; one row per sample)

Read the full `answer` and the numbered `predicted_claims`, then fill:

- `risk_claim_in_answer`: `1` if the answer contains the failure-relevant claim the audit
  must catch (e.g. the claimed order amount, the claimed DOI, a "success" assertion).
  `0` if there is no risk-bearing claim to catch (typical for F0 happy-path).
- `risk_claim_extracted`: `1` if that risk claim is among the predicted claims; `0` if the
  extractor missed it. Leave blank (`NA`) when `risk_claim_in_answer=0`.
- `risk_claim_text`: write the risk claim in your own words — important when
  `risk_claim_extracted=0`, so we know what was missed.
- `other_missed` (optional): other verifiable claims present in the answer but not
  extracted; semicolon-separated; `none` if the extraction was complete.
- `note`: optional.

## How it is scored (T3 `scripts/eval_extractor.py`)

- Precision = valid predicted / all predicted (from File 1).
- Recall = valid predicted / (valid predicted + missed) (File 1 + File 2 `other_missed`).
- Not-extracted coverage ceiling = share of risk-bearing samples with
  `risk_claim_extracted=0` (File 2) — the headline RQ1 number.

## Provenance note

Answers and claims are mined from existing run traces (most recent matching trace with
>= 1 claim). They reflect the current extractor but are not pinned to one authoritative
batch; the source trace per scenario is in `sample_manifest.csv`. If batch-exact numbers
are needed, regenerate from a pinned annotation run instead.
