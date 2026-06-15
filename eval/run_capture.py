"""Phase 2 capture CLI: run the agent × domain × repeat matrix into per-model JSONL shards.

Wraps run_capture_matrix with a CLI interface. Retail = 115 tasks (0-114), airline = 50 tasks
(0-49). User simulator is always minimax/minimax-m3. Resumable: re-running skips status='ok'
rows already in the output shard.

Usage:
  .venv/bin/python -m eval.run_capture \\
      --models z-ai/glm-4.7-flash qwen/qwen3.6-flash \\
      --repeats 10 --workers 10

  # flagship models after flash models are verified:
  .venv/bin/python -m eval.run_capture \\
      --models deepseek/deepseek-v4-pro xiaomi/mimo-v2.5-pro \\
      --repeats 10 --workers 10
"""

from __future__ import annotations

import argparse

from eval.capture import run_capture_matrix

RETAIL_TASKS = list(range(115))   # tau-bench retail: 115 test tasks (index 0-114)
AIRLINE_TASKS = list(range(50))   # tau-bench airline: 50 test tasks (index 0-49)
USER_MODEL = "minimax/minimax-m3"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2: capture agent trajectories from tau-bench"
    )
    parser.add_argument(
        "--models", nargs="+", required=True,
        metavar="MODEL",
        help="agent model ids (OpenRouter format, e.g. z-ai/glm-4.7-flash)",
    )
    parser.add_argument(
        "--repeats", type=int, default=10,
        help="number of repeats per (model, domain, task) — K in the design doc (default: 10)",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="parallel workers within one model's task batch (default: 1)",
    )
    parser.add_argument(
        "--out-dir", default="results/capture",
        help="output directory for JSONL shards (default: results/capture)",
    )
    parser.add_argument(
        "--retail-only", action="store_true",
        help="capture retail domain only (skip airline)",
    )
    parser.add_argument(
        "--airline-only", action="store_true",
        help="capture airline domain only (skip retail)",
    )
    args = parser.parse_args()

    tasks: dict[str, list[int]] = {}
    if not args.airline_only:
        tasks["retail"] = RETAIL_TASKS
    if not args.retail_only:
        tasks["airline"] = AIRLINE_TASKS

    print(
        f"Capture: {args.models} | "
        f"domains={list(tasks)} | repeats={args.repeats} | workers={args.workers}",
        flush=True,
    )
    run_capture_matrix(
        agent_models=args.models,
        user_model=USER_MODEL,
        tasks=tasks,
        repeats=args.repeats,
        out_dir=args.out_dir,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
