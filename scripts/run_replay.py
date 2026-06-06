#!/usr/bin/env python3
"""
Frozen-corpus, paired-replay driver for reproducible monitor evaluation.

Hosted LLM inference is non-deterministic even at temperature 0 (the seed is
sent but ignored), so re-sampling the agent on every run confounds any
comparison between monitor configurations with uncontrolled agent variation.
This driver separates the two stages:

  record  — run each scenario's agent ONCE (observe-only capture), freezing the
            answer, extracted claims, tool trace, structural issues, and the
            post-execution state into a corpus file. This is the only LLM cost.
  replay  — audit the frozen corpus under every version with ZERO LLM calls.
            All versions see the identical behaviour, so the structural ablation
            (V3 vs V3_NoStructural) is a paired, fully reproducible contrast.

Usage:
    # 1) record once (the expensive step; one agent pass over the scenarios)
    python3 scripts/run_replay.py record --set A --seeds 42 \
        --out results/corpus/set_a_corpus.json

    # 2) replay all versions off the frozen corpus (free, deterministic)
    python3 scripts/run_replay.py replay \
        --corpus results/corpus/set_a_corpus.json \
        --versions V1_Baseline V2_AuditOnly V3_Intervention V3_NoStructural \
        --out results/replay/set_a

The replay output mirrors run_ablation: `<out>/set_a_rows.csv` (+ trace_summary)
and `<out>/set_a_metrics.json`, so eval_rq1_audit.py / decompose_failures.py /
metrics consume it unchanged.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.ablation_runner import record_corpus, replay_corpus
from eval.config.ablation_versions import VERSIONS
from eval.metrics import compute_metrics
from scripts.run_ablation import (
    CSV_FIELDS,
    _load_set_a,
    _load_set_b,
    _result_to_csv_row,
    _select_domain,
)

DEFAULT_VERSIONS = ["V1_Baseline", "V2_AuditOnly", "V3_Intervention", "V3_NoStructural"]


def _flatten(scenarios_by_domain: dict[str, list[dict]]) -> list[dict]:
    flat: list[dict] = []
    for domain_scenarios in scenarios_by_domain.values():
        flat.extend(domain_scenarios)
    return flat


def _read_corpus(path: Path) -> list[dict]:
    """Read a corpus file. Accepts streaming JSONL (one record per line, the
    sharded/checkpointed format) and the legacy {"meta", "records": [...]} JSON
    or a bare JSON list (the original single-file record output)."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    if isinstance(data, list):
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# --- record -----------------------------------------------------------------


def _cmd_record(args: argparse.Namespace) -> int:
    if args.set == "B":
        scenarios_by_domain = _select_domain(_load_set_b(args.tier_b), args.domain)
    else:
        scenarios_by_domain = _select_domain(
            _load_set_a(args.ecommerce, args.reference, args.domain), args.domain
        )
    scenarios = _flatten(scenarios_by_domain)
    if args.num_shards > 1:
        # Stride slicing distributes domains/strata evenly across shards. Each shard
        # must run in its own process with a distinct RG_DB_SUFFIX so the global
        # SQLite files are not shared (see scripts/record_sharded.sh).
        scenarios = scenarios[args.shard :: args.num_shards]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    skip_keys: set = set()
    resuming = bool(args.resume and out.exists())
    if resuming:
        skip_keys = {(r.get("scenario_id"), r.get("seed")) for r in _read_corpus(out)}
        print(f"[RECORD] resume: {len(skip_keys)} records already in {out}; skipping those.")

    shard_label = f" shard {args.shard}/{args.num_shards}" if args.num_shards > 1 else ""
    print(
        f"[RECORD]{shard_label} {len(scenarios)} scenarios x {len(args.seeds)} seed(s); "
        f"observe-only capture, streaming JSONL checkpoint."
    )

    # Stream each record to JSONL immediately so a crash never loses completed work.
    fh = open(out, "a" if resuming else "w", encoding="utf-8")

    def _sink(record: dict) -> None:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()

    try:
        new_records = record_corpus(
            scenarios,
            seeds=args.seeds,
            enable_fault_injection=not args.disable_fault_injection,
            skip_keys=skip_keys,
            on_record=_sink,
            policy_aware=args.policy_aware,
        )
    finally:
        fh.close()

    errors = sum(1 for r in new_records if r.get("error"))
    total = len(skip_keys) + len(new_records)
    print(
        f"[RECORD] wrote {len(new_records)} new records ({errors} error); "
        f"{total} total -> {out}"
    )
    return 0


# --- replay -----------------------------------------------------------------


def _cmd_replay(args: argparse.Namespace) -> int:
    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}", file=sys.stderr)
        return 1
    records = _read_corpus(corpus_path)
    if not records:
        print("ERROR: corpus has no records.", file=sys.stderr)
        return 1

    unknown = [v for v in args.versions if v not in VERSIONS]
    if unknown:
        print(f"ERROR: unknown versions {unknown}; known: {list(VERSIONS)}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    metrics_by_version: dict[str, dict] = {}
    print(f"[REPLAY] {len(records)} records x {len(args.versions)} version(s); no LLM calls.")
    for version in args.versions:
        results = replay_corpus(records, version, verbose=args.verbose)
        all_rows.extend(_result_to_csv_row(r) for r in results)
        metrics_by_version[version] = compute_metrics(results)

    set_slug = f"set_{args.set.lower()}"
    rows_path = out_dir / f"{set_slug}_rows.csv"
    with open(rows_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    metrics_path = out_dir / f"{set_slug}_metrics.json"
    metrics_path.write_text(
        json.dumps(metrics_by_version, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _print_summary(metrics_by_version)
    print(f"\n[REPLAY] rows -> {rows_path}\n[REPLAY] metrics -> {metrics_path}")
    return 0


def _cmd_merge(args: argparse.Namespace) -> int:
    records: list[dict] = []
    for shard in args.shards:
        p = Path(shard)
        if not p.exists():
            print(f"WARNING: shard not found, skipping: {p}", file=sys.stderr)
            continue
        recs = _read_corpus(p)
        records.extend(recs)
        print(f"[MERGE] {p}: {len(recs)} records")

    if not records:
        print("ERROR: no records merged.", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    keys = [(r.get("scenario_id"), r.get("seed")) for r in records]
    duplicates = len(keys) - len(set(keys))
    errors = sum(1 for r in records if r.get("error"))
    note = f" ({duplicates} DUPLICATE keys)" if duplicates else ""
    print(f"[MERGE] {len(records)} records{note}, {errors} error -> {out}")
    return 0


def _print_summary(metrics_by_version: dict[str, dict]) -> None:
    print(f"\n{'version':<18} {'RDR':>7} {'FAR':>7} {'audit_fail':>11} {'pass':>7}")
    print("-" * 54)
    for version, m in metrics_by_version.items():
        rdr = m.get("risk_detection_rate")
        far = m.get("false_acceptance_rate")
        af = m.get("audit_failed_rate")
        pr = m.get("pass_rate")
        print(
            f"{version:<18} {str(rdr):>7} {str(far):>7} {str(af):>11} {str(pr):>7}"
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Run agents once and freeze a behaviour corpus (JSONL).")
    rec.add_argument("--set", choices=["A", "B"], default="A")
    rec.add_argument("--domain", choices=["all", "ecommerce", "reference"], default="all")
    rec.add_argument("--seeds", nargs="+", type=int, default=[42])
    rec.add_argument("--ecommerce", default="tasks/ecommerce_scenarios.json")
    rec.add_argument("--reference", default="tasks/reference_scenarios.json")
    rec.add_argument("--tier-b", default="tasks/tier_b_prompts.json", help="Set B prompts.")
    rec.add_argument("--disable-fault-injection", action="store_true")
    rec.add_argument(
        "--num-shards", type=int, default=1,
        help="Total shards for parallel recording. Each shard must run in its own "
        "process with a distinct RG_DB_SUFFIX (see scripts/record_sharded.sh).",
    )
    rec.add_argument("--shard", type=int, default=0, help="This shard index in [0, num-shards).")
    rec.add_argument(
        "--resume", action="store_true",
        help="Skip (scenario_id, seed) pairs already present in --out (crash recovery).",
    )
    rec.add_argument(
        "--policy-aware", action="store_true",
        help="T8: expose the >5000 approval policy to the ecommerce agent prompt.",
    )
    rec.add_argument("--out", required=True, help="Corpus JSONL output path (streamed).")
    rec.set_defaults(func=_cmd_record)

    mrg = sub.add_parser("merge", help="Concatenate shard corpora into one corpus (JSONL).")
    mrg.add_argument("--shards", nargs="+", required=True, help="Shard corpus files to merge.")
    mrg.add_argument("--out", required=True, help="Merged corpus JSONL output path.")
    mrg.set_defaults(func=_cmd_merge)

    rep = sub.add_parser("replay", help="Audit a frozen corpus under each version (no LLM).")
    rep.add_argument("--corpus", required=True, help="Corpus JSON/JSONL from `record`.")
    rep.add_argument("--versions", nargs="+", default=DEFAULT_VERSIONS)
    rep.add_argument("--set", choices=["A", "B"], default="A", help="Output naming (set_a/set_b).")
    rep.add_argument("--out", required=True, help="Output directory for rows/metrics.")
    rep.add_argument("--verbose", action="store_true")
    rep.set_defaults(func=_cmd_replay)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
