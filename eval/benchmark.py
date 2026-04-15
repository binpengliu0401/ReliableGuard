import argparse
import csv
import json
import os
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime

from eval.ablation_runner import run_version
from eval.config.ablation_versions import VERSIONS, with_deepseek
from eval.metrics import compute_metrics

VERSIONS_TO_RUN = ["V1_Baseline", "V2_Gate", "V3_Verifier", "V4_Full"]


class _TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data: str):
        for stream in self.streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()


@contextmanager
def _tee_to_log(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "a", encoding="utf-8") as log_file:
        tee_stdout = _TeeStream(sys.stdout, log_file)
        tee_stderr = _TeeStream(sys.stderr, log_file)

        with redirect_stdout(tee_stdout), redirect_stderr(tee_stderr):
            print(f"\n[{datetime.now().isoformat(timespec='seconds')}] BENCHMARK START")
            yield
            print(f"[{datetime.now().isoformat(timespec='seconds')}] BENCHMARK END")


def _load_adversarial_scenarios(path: str = "tasks/adversarial_scenarios.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_scenarios(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _select_scenarios(mode: str):
    main_scenarios = _load_scenarios("tasks/ecommerce_scenarios.json") + _load_scenarios(
        "tasks/reference_scenarios.json"
    )
    if mode == "main":
        return main_scenarios
    if mode == "adversarial":
        return _load_adversarial_scenarios()
    return main_scenarios + _load_adversarial_scenarios()


def run_benchmark(scenarios, model: str = "qwen"):
    all_version_metrics = {}
    all_results = {}

    for version_key in VERSIONS_TO_RUN:
        config_override = with_deepseek(VERSIONS[version_key]) if model == "deepseek" else None

        results = run_version(
            version_key,
            scenarios,
            verbose=True,
            config_override=config_override,  # type: ignore[arg-type]
        )
        metrics = compute_metrics(results)

        all_version_metrics[version_key] = metrics
        all_results[version_key] = results

    _print_summary(all_version_metrics, VERSIONS_TO_RUN)

    result_dir = os.path.join("results", model)
    scenario_path = os.path.join(result_dir, "scenario_results.csv")
    ablation_path = os.path.join(result_dir, "ablation.csv")

    _export_scenario_results(all_results, scenario_path)
    _export_ablation_csv(all_results, all_version_metrics, ablation_path, VERSIONS_TO_RUN)


def _print_summary(all_metrics: dict, versions: list[str]):
    print(f"\n{'='*86}")
    print(f"{'BENCHMARK SUMMARY':^86}")
    print(f"{'='*86}")

    header = f"{'Metric':<30}" + "".join(f"{v:<16}" for v in versions)
    print(header)
    print("-" * 86)

    metric_keys = [
        ("end_to_end_success_rate", "Success Rate"),
        ("false_success_rate", "False Success Rate"),
        ("invalid_call_rate", "Invalid Call Rate"),
        ("policy_violation_rate", "Policy Violation Rate"),
        ("recovery_resolution_rate", "Recovery Resolution Rate"),
        ("avg_outcome_score", "Avg Outcome Score"),
    ]

    for key, label in metric_keys:
        row = f"{label:<30}"
        for version in versions:
            val = all_metrics.get(version, {}).get(key, "-")
            row += f"{str(val):<16}"
        print(row)

    print("=" * 86)


def _compute_gate_block_rate(results: list[dict]) -> float:
    total = len(results)
    if total == 0:
        return 0.0

    blocked = 0
    for result in results:
        state = result.get("state")
        if state is not None and state.get("gate_status") == "BLOCKED":
            blocked += 1

    return round(blocked / total, 3)


def _export_ablation_csv(
    all_results: dict,
    all_metrics: dict,
    path: str,
    versions: list[str],
):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "version",
                "total",
                "success_rate",
                "false_success_rate",
                "gate_block_rate",
                "recovery_resolution_rate",
            ]
        )

        for version in versions:
            metrics = all_metrics.get(version, {})
            version_results = all_results.get(version, [])
            writer.writerow(
                [
                    version,
                    metrics.get("total_tasks", len(version_results)),
                    metrics.get("end_to_end_success_rate", 0.0),
                    metrics.get("false_success_rate", 0.0),
                    _compute_gate_block_rate(version_results),
                    metrics.get("recovery_resolution_rate", 0.0),
                ]
            )

    print(f"[BENCHMARK] Ablation summary exported to {path}")


def _export_scenario_results(all_results: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = []
    for _, version_results in all_results.items():
        for result in version_results:
            row = result.get("scored_row") or {}
            rows.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "version": row.get("version"),
                    "outcome": row.get("actual_outcome"),
                    "failure_type": row.get("failure_type"),
                    "tool_calls": row.get("tool_calls", 0),
                    "tokens": row.get("tokens", 0),
                }
            )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario_id",
                "version",
                "outcome",
                "failure_type",
                "tool_calls",
                "tokens",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[BENCHMARK] Scenario-level results exported to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        choices=["main", "adversarial", "both"],
        default="main",
    )
    parser.add_argument(
        "--model",
        choices=["qwen", "deepseek"],
        default="qwen",
    )
    args = parser.parse_args()

    selected_scenarios = _select_scenarios(args.scenarios)
    log_path = os.path.join("logs", f"{args.model}_run.log")

    with _tee_to_log(log_path):
        print(f"[BENCHMARK] model={args.model} scenarios={args.scenarios} total={len(selected_scenarios)}")
        run_benchmark(
            scenarios=selected_scenarios,
            model=args.model,
        )
