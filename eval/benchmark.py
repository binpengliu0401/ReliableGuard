import argparse
import csv
import json
import os

from eval.ablation_runner import run_version
from eval.metrics import compute_metrics
from src.config.ablation_config import VERSIONS, with_gpt4o_mini
from tasks.scenario_v1 import SCENARIOS as SCENARIOS_V1
from tasks.ecommerce_scenario_generator import SCENARIOS as SCENARIOS_GEN

VERSIONS_TO_RUN = ["V1_Baseline", "V2_Gate", "V3_Verifier", "V4_Full"]
GPT_VERSION_KEY = "V4_Full_GPT4oMini"


def _load_adversarial_scenarios(path: str = "tasks/adversarial_scenarios.json"):
    with open(path, "r") as f:
        return json.load(f)


def _select_scenarios(mode: str):
    main_scenarios = SCENARIOS_V1 + SCENARIOS_GEN
    if mode == "main":
        return main_scenarios
    if mode == "adversarial":
        return _load_adversarial_scenarios()
    return main_scenarios + _load_adversarial_scenarios()


def run_benchmark(
    scenarios,
    output_csv: str = "logs/benchmark_results.csv",
    model: str = "qwen",
):
    all_version_metrics = {}
    all_results = {}
    versions_run = []

    if model in ("qwen", "both"):
        for version_key in VERSIONS_TO_RUN:
            results = run_version(version_key, scenarios, verbose=True)
            metrics = compute_metrics(results)
            all_version_metrics[version_key] = metrics
            all_results[version_key] = results
            versions_run.append(version_key)

    if model in ("gpt", "both"):
        gpt_config = with_gpt4o_mini(VERSIONS["V4_Full"])
        results_gpt = run_version(
            GPT_VERSION_KEY,
            scenarios,
            verbose=True,
            config_override=gpt_config,  # type: ignore
        )
        metrics_gpt = compute_metrics(results_gpt)
        all_version_metrics[GPT_VERSION_KEY] = metrics_gpt
        all_results[GPT_VERSION_KEY] = results_gpt
        versions_run.append(GPT_VERSION_KEY)

    _print_summary(all_version_metrics, versions_run)  # type: ignore
    _export_csv(all_version_metrics, output_csv, versions_run)  # type: ignore
    _export_scenario_results(all_results, "logs/scenario_results.csv")
    with open("logs/benchmark_raw.json", "w") as f:
        raw = {
            v: [{"task": r["task"], "state": r["state"]} for r in all_results[v]]
            for v in all_results
        }
        json.dump(raw, f, default=str)


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


def _export_csv(all_metrics: dict, path: str, versions: list[str]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    metric_keys = [
        "end_to_end_success_rate",
        "false_success_rate",
        "invalid_call_rate",
        "policy_violation_rate",
        "recovery_resolution_rate",
        "avg_outcome_score",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric"] + versions)
        for key in metric_keys:
            row = [key] + [all_metrics.get(v, {}).get(key, "") for v in versions]
            writer.writerow(row)

    print(f"\n[BENCHMARK] Results exported to {path}")


def _export_scenario_results(
    all_results: dict, path: str = "logs/scenario_results.csv"
):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = []
    for version_key, version_results in all_results.items():
        for r in version_results:
            row = r.get("scored_row")
            if row:
                rows.append(row)

    if not rows:
        print("[BENCHMARK] No scenario rows to export.")
        return

    fieldnames = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
        choices=["qwen", "gpt", "both"],
        default="qwen",
    )
    parser.add_argument(
        "--output_csv",
        default="logs/benchmark_results.csv",
    )
    args = parser.parse_args()

    selected_scenarios = _select_scenarios(args.scenarios)
    run_benchmark(
        scenarios=selected_scenarios,
        output_csv=args.output_csv,
        model=args.model,
    )
