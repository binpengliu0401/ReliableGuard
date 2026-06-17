"""Re-annotate existing Phase 3 monitor rows with the two new V_structural signals, WITHOUT
re-running the (expensive, non-deterministic) claim extractor.

The agent-loop guard (trace channel) and the answer-completeness check (answer channel) are pure
functions of `tool_trace` and `answer_text` -- both already captured in Phase 2. So instead of a
full Phase 3 re-run (which would re-extract claims for ~6.5k trajectories at real cost for no
benefit, since the claims do not change), this script overlays the two signals on the existing
monitor shards and writes updated shards. Re-run `eval.analyze` on the output dir to get the
updated metrics.

For each row:
  - loop = detect_agent_loops(capture.tool_trace)         -> trace-channel violation
  - incomplete = detect_incomplete_answer(capture.answer_text)  -> answer-channel signal
  - v_structural := BLOCK if (old==BLOCK or loop or incomplete) else old verdict
  - locus recomputed with the documented priority, preserving prior trace/state decisions:
        pass > trace-local (policy OR loop) > state-local > answer-local (incomplete) > intent-local

Usage:
  .venv/bin/python -m eval.reannotate_signals \\
      --monitor-dir results/monitor \\
      --capture-dir results/capture \\
      --out-dir results/monitor_v2
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.reliableguard.verifier.answer_completeness import detect_incomplete_answer
from src.reliableguard.verifier.tau_bench_verifiers import (
    _is_nonstate_status_framing,
    detect_agent_loops,
)

_PASS_LIKE = {"PASS_VERIFIED", "PASS_UNCHECKED"}


def _key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("model")),
        str(row.get("domain")),
        str(row.get("repeat", 0)),
        str(row.get("task_id")),
    )


def _load_capture_index(capture_dir: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in sorted(capture_dir.glob("*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") == "ok":
                    index[_key(rec)] = rec
    return index


def _recompute_locus(
    gold_reward: float,
    trace_policy: bool,
    has_loop: bool,
    state_block: bool,
    incomplete: bool,
) -> str:
    """Recompute locus from components per the documented hierarchy:
    pass > trace-local (policy OR loop) > state-local > answer-local > intent-local.
    `state_block` is the state contribution AFTER the capability/negation framing fix."""
    if (gold_reward or 0.0) >= 1.0:
        return "pass"
    if trace_policy or has_loop:
        return "trace-local"
    if state_block:
        return "state-local"
    if incomplete:
        return "answer-local"
    return "intent-local"


def reannotate_shard(
    monitor_path: Path,
    out_path: Path,
    capture_index: dict[tuple[str, str, str, str], dict[str, Any]],
) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with monitor_path.open() as fin, out_path.open("w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            stats["rows"] += 1

            cap = capture_index.get(_key(row))
            loop_violations = detect_agent_loops(cap.get("tool_trace", [])) if cap else []
            incomplete_reason = detect_incomplete_answer(cap.get("answer_text")) if cap else None
            has_loop = bool(loop_violations)
            incomplete = incomplete_reason is not None

            # State-channel framing fix: a contradicted status claim whose text is capability/negation
            # framed ("cannot be cancelled") is not a current-state assertion -> it no longer
            # contributes a contradiction. Recompute the state contribution over the kept claims.
            block_detail = row.get("block_detail") or {}
            contradicted = block_detail.get("contradicted_claims", [])
            kept = [c for c in contradicted if not _is_nonstate_status_framing(c.get("text", "") or "")]
            dropped = len(contradicted) - len(kept)
            # A contradiction can only drive a BLOCK row, which always carries block_detail; if a row
            # reports contradictions but exposes none (shouldn't happen), keep it conservatively.
            if (row.get("n_contradicted", 0) or 0) > 0 and not contradicted:
                state_block = True
            else:
                state_block = len(kept) > 0

            # Baseline n_violations = wiki-policy violations only (loops added below). Completeness is
            # an answer-channel signal -> lifts BOTH configs; loop + state lift only V_structural.
            trace_policy = (row.get("n_violations", 0) or 0) > 0
            struct_block = state_block or trace_policy or has_loop or incomplete

            old_struct = row.get("v_structural_verdict")
            if struct_block:
                new_struct = "BLOCK"
            elif old_struct == "BLOCK":
                new_struct = "PASS_UNCHECKED"  # was blocked only by a now-removed state contradiction
            else:
                new_struct = old_struct  # PASS_* or AUDIT_FAILED unchanged

            old_answer = row.get("v_answer_verdict")
            new_answer = "BLOCK" if incomplete else (old_answer if old_answer != "BLOCK" else "PASS_UNCHECKED")

            old_locus = row.get("locus")
            new_locus = _recompute_locus(
                row.get("gold_reward", 0.0), trace_policy, has_loop, state_block, incomplete
            )

            if new_struct != old_struct:
                stats["struct_verdict_changed"] += 1
            if new_answer != old_answer:
                stats["answer_verdict_changed"] += 1
            if new_locus != old_locus:
                stats["locus_changed"] += 1
            if has_loop:
                stats["with_loop"] += 1
            if incomplete:
                stats["with_incomplete"] += 1
            if dropped:
                stats["state_claims_dropped"] += dropped

            row["v_structural_verdict"] = new_struct
            row["v_answer_verdict"] = new_answer
            row["locus"] = new_locus
            row["answer_incomplete"] = incomplete
            row["n_agent_loops"] = len(loop_violations)
            row["n_violations"] = int(row.get("n_violations", 0)) + len(loop_violations)
            row["n_contradicted"] = len(kept) if contradicted else row.get("n_contradicted", 0)
            fout.write(json.dumps(row) + "\n")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Overlay loop + completeness signals on existing monitor rows (no re-extraction)"
    )
    parser.add_argument("--monitor-dir", default="results/monitor")
    parser.add_argument("--capture-dir", default="results/capture")
    parser.add_argument("--out-dir", default="results/monitor_v2")
    args = parser.parse_args()

    monitor_dir = Path(args.monitor_dir)
    capture_dir = Path(args.capture_dir)
    out_dir = Path(args.out_dir)

    capture_index = _load_capture_index(capture_dir)
    print(f"Loaded {len(capture_index):,} captured trajectories from {capture_dir}")

    total: dict[str, int] = defaultdict(int)
    for shard in sorted(monitor_dir.glob("*.jsonl")):
        out_path = out_dir / shard.name
        stats = reannotate_shard(shard, out_path, capture_index)
        print(
            f"[{shard.stem}] rows={stats['rows']} "
            f"struct_changed={stats['struct_verdict_changed']} "
            f"answer_changed={stats['answer_verdict_changed']} "
            f"locus_changed={stats['locus_changed']} "
            f"loop={stats['with_loop']} incomplete={stats['with_incomplete']} "
            f"state_dropped={stats['state_claims_dropped']} -> {out_path}"
        )
        for k, v in stats.items():
            total[k] += v
    print(
        f"TOTAL rows={total['rows']} struct_changed={total['struct_verdict_changed']} "
        f"answer_changed={total['answer_verdict_changed']} locus_changed={total['locus_changed']} "
        f"loop={total['with_loop']} incomplete={total['with_incomplete']} "
        f"state_dropped={total['state_claims_dropped']}"
    )


if __name__ == "__main__":
    main()
