"""Build the extractor-annotation workbook for the RQ1 coverage-ceiling study.

Draws a stratified 150-scenario sample (ecommerce 100 by failure_mode F0-F5;
reference 50 by expected verdict), attaches each scenario's real agent answer and
the claims the extractor actually produced (mined from `logs/` run traces), and
writes a human-annotation workbook plus a reproducible sample manifest.

The workbook is the *input* to `scripts/eval_extractor.py` (T3), which compares the
human gold judgement against the extractor output to report precision / recall / F1
and the not-extracted coverage ceiling.

Determinism: the sample is fixed by `--seed` (default 42). For each sampled scenario
the attached trace is the most recent run trace (by `run_started_at`) whose query
matches and that carries a non-empty answer with >= 1 extracted claim. The chosen
trace file is recorded per row in the manifest so the provenance is auditable.

Usage:
    python3 scripts/build_extractor_annotation.py [--seed 42] [--out eval/annotation] [--overwrite]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
ECOM_SCENARIOS = REPO_ROOT / "tasks" / "ecommerce_scenarios.json"
REF_SCENARIOS = REPO_ROOT / "tasks" / "reference_scenarios.json"
LOG_GLOBS = ("logs/ecommerce/*.json", "logs/reference/*.json")

ECOM_N = 100
REF_N = 50


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _largest_remainder(group_sizes: dict[str, int], total: int, n: int) -> dict[str, int]:
    raw = {k: size / total * n for k, size in group_sizes.items()}
    alloc = {k: int(x) for k, x in raw.items()}
    remainder = n - sum(alloc.values())
    order = sorted(raw.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)
    for k, _ in order[:remainder]:
        alloc[k] += 1
    return alloc


def stratified_sample(
    scenarios: list[dict],
    key_fn: Callable[[dict], str],
    n: int,
    rng: random.Random,
) -> tuple[list[dict], dict[str, int]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for scenario in scenarios:
        groups[key_fn(scenario)].append(scenario)
    alloc = _largest_remainder({k: len(v) for k, v in groups.items()}, len(scenarios), n)
    picked: list[dict] = []
    for key, members in groups.items():
        ordered = sorted(members, key=lambda s: s["id"])
        rng.shuffle(ordered)
        picked.extend(ordered[: alloc[key]])
    picked.sort(key=lambda s: s["id"])
    return picked, dict(sorted(alloc.items()))


def index_logs(sample_queries: set[str]) -> dict[str, dict]:
    """Map each sampled query to its best matching run trace.

    "Best" = carries a non-empty answer, prefers >= 1 extracted claim, then the most
    recent `run_started_at`.
    """
    best: dict[str, dict] = {}
    files: list[str] = []
    for pattern in LOG_GLOBS:
        files.extend(glob.glob(str(REPO_ROOT / pattern)))
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        nq = _norm(data.get("query"))
        if nq not in sample_queries:
            continue
        answer = (data.get("answer") or "").strip()
        if not answer:
            continue
        claims = [t.get("claim", {}) for t in data.get("traces", [])]
        rank = (1 if claims else 0, str(data.get("run_started_at") or ""))
        current = best.get(nq)
        if current is None or rank > current["_rank"]:
            best[nq] = {
                "_rank": rank,
                "answer": data.get("answer") or "",
                "claims": claims,
                "trace_file": os.path.relpath(path, REPO_ROOT),
                "run_started_at": data.get("run_started_at"),
            }
    return best


def _claim_struct(claim: dict) -> str:
    parts = [f"type={claim.get('claim_type')}"]
    if claim.get("attribute") is not None:
        parts.append(f"attr={claim.get('attribute')}")
    if claim.get("value") is not None:
        parts.append(f"value={claim.get('value')}")
    if claim.get("entities"):
        parts.append("entities=" + json.dumps(claim["entities"], ensure_ascii=False))
    return "; ".join(parts)


def _numbered_claims(claims: list[dict]) -> str:
    return "\n".join(f"{i}. {c.get('text', '')}" for i, c in enumerate(claims, start=1))


def build_rows(sample: list[tuple[str, str, str, dict]], trace_by_query: dict[str, dict]):
    claim_rows: list[dict] = []
    coverage_rows: list[dict] = []
    manifest_rows: list[dict] = []
    for domain, stratum, sample_id, scenario in sample:
        trace = trace_by_query[_norm(scenario["input"])]
        claims = trace["claims"]
        answer = trace["answer"]
        for idx, claim in enumerate(claims, start=1):
            claim_rows.append(
                {
                    "sample_id": sample_id,
                    "domain": domain,
                    "stratum": stratum,
                    "claim_idx": idx,
                    "claim_text": claim.get("text", ""),
                    "claim_struct": _claim_struct(claim),
                    "query": scenario["input"],
                    "answer": answer,
                    "valid": "",
                    "note": "",
                }
            )
        coverage_rows.append(
            {
                "sample_id": sample_id,
                "domain": domain,
                "stratum": stratum,
                "query": scenario["input"],
                "answer": answer,
                "n_predicted": len(claims),
                "predicted_claims": _numbered_claims(claims),
                "risk_claim_in_answer": "",
                "risk_claim_extracted": "",
                "risk_claim_text": "",
                "other_missed": "",
                "note": "",
            }
        )
        manifest_rows.append(
            {
                "sample_id": sample_id,
                "domain": domain,
                "stratum": stratum,
                "expected_outcome": scenario.get("expected_outcome"),
                "n_predicted": len(claims),
                "trace_file": trace["trace_file"],
                "run_started_at": trace["run_started_at"],
            }
        )
    return claim_rows, coverage_rows, manifest_rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


README = """# Extractor Annotation Workbook (RQ1 coverage-ceiling study)

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
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="eval/annotation")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    claims_path = out_dir / "extractor_annotation_claims.csv"
    coverage_path = out_dir / "extractor_annotation_coverage.csv"
    for path in (claims_path, coverage_path):
        if path.exists() and not args.overwrite:
            raise SystemExit(
                f"{path} already exists. Refusing to overwrite annotation in progress; "
                f"pass --overwrite to regenerate."
            )

    ecom = json.loads(ECOM_SCENARIOS.read_text(encoding="utf-8"))
    ref = json.loads(REF_SCENARIOS.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)
    ecom_sample, ecom_alloc = stratified_sample(ecom, lambda s: s["failure_mode"], ECOM_N, rng)
    ref_sample, ref_alloc = stratified_sample(ref, lambda s: s.get("expected_outcome"), REF_N, rng)

    sample: list[tuple[str, str, str, dict]] = []
    for s in ecom_sample:
        sample.append(("ecommerce", s["failure_mode"], s["id"], s))
    for s in ref_sample:
        sample.append(("reference", s.get("expected_outcome"), s["id"], s))

    sample_queries = {_norm(s["input"]) for _, _, _, s in sample}
    trace_by_query = index_logs(sample_queries)
    missing = [sid for _, _, sid, s in sample if _norm(s["input"]) not in trace_by_query]
    if missing:
        raise SystemExit(
            f"{len(missing)} sampled scenarios have no usable trace: {missing[:10]} ... "
            f"Re-run those scenarios to produce traces, or adjust the sample."
        )

    claim_rows, coverage_rows, manifest_rows = build_rows(sample, trace_by_query)

    _write_csv(
        claims_path,
        claim_rows,
        ["sample_id", "domain", "stratum", "claim_idx", "claim_text",
         "claim_struct", "query", "answer", "valid", "note"],
    )
    _write_csv(
        coverage_path,
        coverage_rows,
        ["sample_id", "domain", "stratum", "query", "answer", "n_predicted",
         "predicted_claims", "risk_claim_in_answer", "risk_claim_extracted",
         "risk_claim_text", "other_missed", "note"],
    )
    _write_csv(
        out_dir / "sample_manifest.csv",
        manifest_rows,
        ["sample_id", "domain", "stratum", "expected_outcome", "n_predicted",
         "trace_file", "run_started_at"],
    )
    (out_dir / "README.md").write_text(README, encoding="utf-8")

    print(f"ecommerce strata (failure_mode): {ecom_alloc} = {sum(ecom_alloc.values())}")
    print(f"reference strata (expected_outcome): {ref_alloc} = {sum(ref_alloc.values())}")
    print(f"samples: {len(sample)} | predicted-claim rows: {len(claim_rows)}")
    print(f"wrote: {claims_path}")
    print(f"       {coverage_path}")
    print(f"       {out_dir / 'sample_manifest.csv'}")
    print(f"       {out_dir / 'README.md'}")


if __name__ == "__main__":
    main()
