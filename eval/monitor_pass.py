"""Phase 3: monitor pass — apply V_answer + V_structural to captured trajectories.

Reads per-model JSONL shards from --capture-dir (written by Phase 2 capture), runs the
claim extractor once per trajectory (minimax/minimax-m3, reasoning disabled), applies both
monitor configurations via the same claims + grounding, annotates locus, and writes a result
row to --out-dir.

Resumable: rows already written with status='done' are skipped on re-run.

Usage:
  .venv/bin/python -m eval.monitor_pass \\
      --capture-dir results/capture \\
      --out-dir results/monitor \\
      [--model z-ai_glm-4.7-flash]   # process one shard; omit for all shards
      [--workers 4]                   # parallel extractions per shard (default 1)
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.reliableguard.adapter import Trajectory
from src.reliableguard.extractor.claim_extractor import extract_claims
from src.reliableguard.locus import annotate_locus
from src.reliableguard.schema import (
    CHANNELS_ANSWER,
    CHANNELS_STRUCTURAL,
    TraceViolation,
    VerificationResult,
)
from src.reliableguard.verifier.answer_completeness import detect_incomplete_answer
from src.reliableguard.verifier.source_verifier import verify_claims
from src.reliableguard.verifier.tau_bench_verifiers import (
    register_tau_bench_verifiers,
    verify_trace,
)

EXTRACTOR_MODEL = "minimax/minimax-m3"
EXTRACTOR_MAX_TOKENS = 16384
# Airline agents occasionally produce very long answer texts that cause the extractor to
# generate 16k+ tokens of claims JSON and hit the cap. Truncate to the tail of the answer
# (where the final verdict/summary lives) to keep extraction output well within limits.
_MAX_ANSWER_CHARS = 8000


def _compute_verdict(
    results: dict[str, VerificationResult],
    violations: list[TraceViolation],
    *,
    answer_incomplete: bool = False,
) -> str:
    """Collapse per-claim results + trace violations (+ optional answer-incompleteness) into one
    OverallVerdict string. `answer_incomplete` is an answer-channel signal, so BOTH V_answer and
    V_structural consult it; the V_structural lift over V_answer therefore comes purely from the
    state + trace channels (violations / contradictions)."""
    if not results and not violations and not answer_incomplete:
        return "AUDIT_FAILED"
    if (
        violations
        or answer_incomplete
        or any(r.evidence_state == "contradicted" for r in results.values())
    ):
        return "BLOCK"
    if any(r.evidence_state == "supported" for r in results.values()):
        return "PASS_VERIFIED"
    return "PASS_UNCHECKED"


def _result_key(model: str, domain: str, repeat: int, task_id: Any) -> str:
    return f"{model}|{domain}|r{repeat}|t{task_id}"


def _load_done_keys(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "done":
                done.add(
                    _result_key(row["model"], row["domain"], row.get("repeat", 0), row["task_id"])
                )
    return done


def _process_trajectory(traj: Trajectory) -> dict[str, Any]:
    """Full monitor pipeline for one trajectory: extract → V_answer → V_structural → locus."""
    answer_text = traj.answer_text
    if len(answer_text) > _MAX_ANSWER_CHARS:
        answer_text = answer_text[-_MAX_ANSWER_CHARS:]
    claims = extract_claims(
        traj.domain,
        traj.query,
        answer_text,
        model=EXTRACTOR_MODEL,
        disable_reasoning=True,
        max_tokens=EXTRACTOR_MAX_TOKENS,
    )

    # Answer-channel completeness signal: non-completion visible in the agent's own answer
    # (terminated on an unanswered substantive question). Read the FULL answer text, not the
    # length-truncated tail, so a terminal question is not lost to truncation.
    incomplete_reason = detect_incomplete_answer(traj.answer_text)
    answer_incomplete = incomplete_reason is not None

    # Completeness is a pure answer-channel signal (read only from answer_text), so it belongs to
    # the answer-only baseline: V_answer detects it too. Keeping it in BOTH configs means the
    # V_structural vs V_answer lift (RQ2) is attributable purely to the state + trace channels.
    ctx_answer = traj.verification_context(CHANNELS_ANSWER)
    answer_results = verify_claims(traj.domain, claims, {}, ctx_answer)
    v_answer_verdict = _compute_verdict(answer_results, [], answer_incomplete=answer_incomplete)

    ctx_structural = traj.verification_context(CHANNELS_STRUCTURAL)
    structural_results = verify_claims(traj.domain, claims, {}, ctx_structural)
    violations = verify_trace(ctx_structural, domain=traj.domain)
    v_structural_verdict = _compute_verdict(
        structural_results, violations, answer_incomplete=answer_incomplete
    )

    locus = annotate_locus(
        traj.gold_reward or 0.0, violations, structural_results,
        answer_incomplete=answer_incomplete,
    )

    n_contradicted = sum(
        1 for r in structural_results.values() if r.evidence_state == "contradicted"
    )

    # For every BLOCKed trajectory, record which claims were contradicted and why.
    # Enables post-hoc false-alarm analysis without re-running the extractor.
    block_detail: dict[str, Any] | None = None
    if v_structural_verdict == "BLOCK":
        claim_by_id = {c.claim_id: c for c in claims}
        contradicted = []
        for cid, result in structural_results.items():
            if result.evidence_state != "contradicted":
                continue
            c = claim_by_id.get(cid)
            contradicted.append({
                "claim_id": cid,
                "text": c.text if c else None,
                "time_range": c.time_range if c else None,
                "attribute": c.attribute if c else None,
                "value": str(c.value) if c else None,
                "reason": result.reason,
            })
        block_detail = {
            "contradicted_claims": contradicted,
            "trace_violations": [str(v) for v in violations],
            "answer_incomplete": incomplete_reason,
        }

    return {
        "task_id": traj.task_id,
        "domain": traj.domain,
        "model": traj.model,
        "repeat": traj.repeat,
        "gold_reward": traj.gold_reward,
        "locus": locus,
        "v_answer_verdict": v_answer_verdict,
        "v_structural_verdict": v_structural_verdict,
        "n_claims": len(claims),
        "n_violations": len(violations),
        "n_contradicted": n_contradicted,
        "answer_incomplete": answer_incomplete,
        "trace_verdict": "BLOCK" if violations else "PASS",
        "block_detail": block_detail,
        "status": "done",
    }


def run_monitor_shard(
    capture_path: Path,
    out_path: Path,
    *,
    max_workers: int = 1,
) -> None:
    """Process all status='ok' trajectories in one shard that haven't been processed yet."""
    done = _load_done_keys(out_path)

    trajectories: list[Trajectory] = []
    with capture_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("status") != "ok":
                continue
            key = _result_key(
                data["model"], data["domain"], data.get("repeat", 0), data["task_id"]
            )
            if key in done:
                continue
            trajectories.append(Trajectory(**data))

    print(f"  {len(done)} done, {len(trajectories)} pending -> {out_path}", flush=True)
    if not trajectories:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def _do(traj: Trajectory) -> None:
        try:
            row = _process_trajectory(traj)
            print(
                f"  ok  [{traj.domain} t{traj.task_id} r{traj.repeat}] "
                f"locus={row['locus']} v_struct={row['v_structural_verdict']} "
                f"claims={row['n_claims']} viol={row['n_violations']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"  ERR [{traj.model} {traj.domain} t{traj.task_id} r{traj.repeat}]: "
                f"{type(exc).__name__}: {str(exc)[:120]}",
                flush=True,
            )
            row = {
                "task_id": traj.task_id,
                "domain": traj.domain,
                "model": traj.model,
                "repeat": traj.repeat,
                "gold_reward": traj.gold_reward,
                "locus": "unknown",
                "v_answer_verdict": "AUDIT_FAILED",
                "v_structural_verdict": "AUDIT_FAILED",
                "n_claims": 0,
                "n_violations": 0,
                "n_contradicted": 0,
                "trace_verdict": "PASS",
                "status": "done",
            }
        with lock:
            with out_path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
                fh.flush()

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_do, trajectories))
    else:
        for traj in trajectories:
            _do(traj)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3 monitor pass: apply V_answer + V_structural to captured trajectories"
    )
    parser.add_argument(
        "--capture-dir", default="results/capture",
        help="directory of Phase 2 JSONL capture shards (default: results/capture)",
    )
    parser.add_argument(
        "--out-dir", default="results/monitor",
        help="output directory for monitor result shards (default: results/monitor)",
    )
    parser.add_argument(
        "--model", default=None,
        help="process only this shard by model slug (e.g. z-ai_glm-4.7-flash); default: all shards",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="parallel extractor workers per shard (default: 1)",
    )
    args = parser.parse_args()

    register_tau_bench_verifiers()

    capture_dir = Path(args.capture_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.model:
        slug = args.model.replace("/", "_")
        shards = [capture_dir / f"{slug}.jsonl"]
    else:
        shards = sorted(capture_dir.glob("*.jsonl"))

    for shard in shards:
        if not shard.exists():
            print(f"[SKIP] {shard} not found", flush=True)
            continue
        out_path = out_dir / shard.name
        print(f"[{shard.stem}]", flush=True)
        run_monitor_shard(shard, out_path, max_workers=args.workers)


if __name__ == "__main__":
    main()
