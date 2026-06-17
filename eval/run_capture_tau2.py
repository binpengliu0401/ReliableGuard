"""tau2-bench capture CLI: run agent × domain × repeat matrix into per-model JSONL shards.

Formal experiment domains: retail (114 tasks) + airline (50 tasks) = 164 tasks/repeat.
User simulator is always minimax/minimax-m3. Resumable: re-running skips status='ok' rows.

Usage:
  .venv/bin/python -m eval.run_capture_tau2 \\
      --domain retail airline \\
      --models deepseek/deepseek-v4-pro xiaomi/mimo-v2.5-pro \\
      --repeats 10 --workers 4

  # Smoke test (5 tasks per domain, cheap):
  .venv/bin/python -m eval.run_capture_tau2 \\
      --domain retail airline --tasks 0 1 2 3 4 \\
      --models qwen/qwen3.6-flash \\
      --repeats 1 --workers 2
"""

from __future__ import annotations

import argparse

from eval.capture_tau2 import run_capture_matrix

# tau2 task IDs per domain. Both retail and airline use plain integer strings ("0", "1", ...).
RETAIL_TASKS = [str(i) for i in range(114)]   # 114 tasks (IDs "0"–"113")
AIRLINE_TASKS = [str(i) for i in range(50)]   # 50 test tasks

USER_MODEL = "openrouter/minimax/minimax-m3"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="tau2-bench capture: run agent × domain × repeat matrix"
    )
    parser.add_argument(
        "--domain", nargs="+",
        choices=["retail", "airline"],
        default=["retail", "airline"],
        metavar="DOMAIN",
        help="domains to capture (default: retail airline)",
    )
    parser.add_argument(
        "--models", nargs="+", required=True,
        metavar="MODEL",
        help="agent model ids (OpenRouter format, e.g. deepseek/deepseek-v4-pro)",
    )
    parser.add_argument(
        "--tasks", nargs="*", default=None,
        metavar="TASK_ID",
        help="specific task IDs to capture (e.g. task_026); default: full domain range",
    )
    parser.add_argument(
        "--repeats", type=int, default=10,
        help="repeats per (model, domain, task) — K in the design doc (default: 10)",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="parallel workers within one model's task batch (default: 1)",
    )
    parser.add_argument(
        "--out-dir", default="results/capture",
        help="output directory for JSONL shards (default: results/capture)",
    )
    args = parser.parse_args()

    domain_defaults = {
        "retail": RETAIL_TASKS,
        "airline": AIRLINE_TASKS,
    }

    if args.tasks:
        # Override task list for all requested domains.
        task_map: dict[str, list[str]] = {d: args.tasks for d in args.domain}
    else:
        task_map = {d: domain_defaults[d] for d in args.domain}

    print(
        f"Capture: {args.models} | domains={list(task_map)} | "
        f"repeats={args.repeats} | workers={args.workers}",
        flush=True,
    )
    run_capture_matrix(
        agent_models=args.models,
        user_model=USER_MODEL,
        tasks=task_map,
        repeats=args.repeats,
        out_dir=args.out_dir,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
