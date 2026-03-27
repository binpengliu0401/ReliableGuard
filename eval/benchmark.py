import csv
import os
from tasks.scenario_v1 import SCENARIOS
from eval.ablation_runner import run_version
from eval.metrics import compute_metrics
from src.config.ablation_config import VERSIONS, with_gpt4o_mini

VERSIONS_TO_RUN = ["V1_Baseline", "V2_Gate", "V3_Verifier", "V4_Full"]
GPT_VERSION_KEY = "V4_Full_GPT4oMini"


def run_benchmark(output_csv: str = "logs/benchmark_results.csv"):
    all_version_metrics = {}

    SKIP_IDS = {"F3-02", "F5-01", "F5-02"}
    safe_scenarios = [s for s in SCENARIOS if s["id"] not in SKIP_IDS]

    # Qwen
    for version_key in VERSIONS_TO_RUN:
        results = run_version(version_key, safe_scenarios, verbose=True)
        metrics = compute_metrics(results)
        all_version_metrics[version_key] = metrics

    # GPT-4o-mini V4_Full
    gpt_config = with_gpt4o_mini(VERSIONS["V4_Full"])
    results_gpt = run_version(
        GPT_VERSION_KEY,
        safe_scenarios,
        verbose=True,
        config_override=gpt_config,  # type: ignore
    )
    metrics_gpt = compute_metrics(results_gpt)
    all_version_metrics[GPT_VERSION_KEY] = metrics_gpt

    _print_summary(all_version_metrics)
    _export_csv(all_version_metrics, output_csv)


def _print_summary(all_metrics: dict):
    all_versions = VERSIONS_TO_RUN + [GPT_VERSION_KEY]

    print(f"\n{'='*86}")
    print(f"{'BENCHMARK SUMMARY':^86}")
    print(f"{'='*86}")

    header = f"{'Metric':<30}" + "".join(f"{v:<16}" for v in all_versions)
    print(header)
    print("-" * 86)

    metric_keys = [
        ("end_to_end_success_rate", "Success Rate"),
        ("false_success_rate", "False Success Rate"),
        ("invalid_call_rate", "Invalid Call Rate"),
        ("policy_violation_rate", "Policy Violation Rate"),
        ("avg_outcome_score", "Avg Outcome Score"),
    ]

    for key, label in metric_keys:
        row = f"{label:<30}"
        for version in all_versions:
            val = all_metrics.get(version, {}).get(key, "-")
            row += f"{str(val):<16}"
        print(row)

    print("=" * 86)


def _export_csv(all_metrics: dict, path: str):
    all_versions = VERSIONS_TO_RUN + [GPT_VERSION_KEY]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    metric_keys = [
        "end_to_end_success_rate",
        "false_success_rate",
        "invalid_call_rate",
        "policy_violation_rate",
        "avg_outcome_score",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric"] + all_versions)
        for key in metric_keys:
            row = [key] + [all_metrics.get(v, {}).get(key, "") for v in all_versions]
            writer.writerow(row)

    print(f"\n[BENCHMARK] Results exported to {path}")


if __name__ == "__main__":
    run_benchmark()
