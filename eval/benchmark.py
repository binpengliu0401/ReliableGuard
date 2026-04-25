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
from src.reliableguard.trace.artifacts import build_run_id, make_run_stamp

VERSIONS_TO_RUN = ["V1_Baseline", "V2_NoReliability", "V3_AuditOnly", "V4_Full"]


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
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_scenarios(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_main_scenarios(domain: str):
    if domain == "ecommerce":
        return _load_scenarios("tasks/ecommerce_scenarios.json")
    if domain == "reference":
        return _load_scenarios("tasks/reference_scenarios.json")
    return _load_scenarios("tasks/ecommerce_scenarios.json") + _load_scenarios(
        "tasks/reference_scenarios.json"
    )


def _load_verifier_scenarios(domain: str):
    scenarios = _load_scenarios("tasks/verifier_scenarios.json")
    return _filter_by_domain(scenarios, domain)


def _filter_by_domain(scenarios: list[dict], domain: str) -> list[dict]:
    if domain == "all":
        return scenarios
    return [scenario for scenario in scenarios if scenario.get("domain", "ecommerce") == domain]


def _select_scenarios(mode: str, domain: str):
    main_scenarios = _load_main_scenarios(domain)
    if mode == "main":
        return main_scenarios
    if mode == "verifier":
        return _load_verifier_scenarios(domain)
    if mode == "adversarial":
        return _load_adversarial_scenarios()
    if mode == "all":
        return main_scenarios + _load_verifier_scenarios(domain) + _load_adversarial_scenarios()
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

    domains = {str(scenario.get("domain", "ecommerce")) for scenario in scenarios}
    domain_bucket = domains.pop() if len(domains) == 1 else "all"
    result_dir = os.path.join("results", model, domain_bucket)
    scenario_path = os.path.join(result_dir, "scenario_results.csv")
    ablation_path = os.path.join(result_dir, "ablation.csv")

    _export_scenario_results(all_results, scenario_path)
    _export_ablation_csv(all_results, all_version_metrics, ablation_path, VERSIONS_TO_RUN)


def _print_summary(all_metrics: dict, versions: list[str]):
    version_width = max(16, *(len(version) + 2 for version in versions))
    table_width = 30 + version_width * len(versions)
    print(f"\n{'=' * table_width}")
    print(f"{'BENCHMARK SUMMARY':^{table_width}}")
    print(f"{'=' * table_width}")

    header = f"{'Metric':<30}" + "".join(f"{v:<{version_width}}" for v in versions)
    print(header)
    print("-" * table_width)

    metric_keys = [
        ("pass_rate", "Pass Rate"),
        ("audit_pass_rate", "Audit Pass Rate"),
        ("false_acceptance_rate", "False Acceptance Rate"),
        ("audit_false_acceptance_rate", "Audit FAR"),
        ("block_rate", "Block Rate"),
        ("warn_rate", "Warn Rate"),
        ("avg_reliability_score", "Avg Reliability Score"),
        ("avg_outcome_score", "Avg Outcome Score"),
    ]

    for key, label in metric_keys:
        row = f"{label:<30}"
        for version in versions:
            val = all_metrics.get(version, {}).get(key, "-")
            row += f"{str(val):<{version_width}}"
        print(row)

    print("=" * table_width)


def _compute_block_rate(results: list[dict]) -> float:
    total = len(results)
    if total == 0:
        return 0.0

    blocked = 0
    for result in results:
        state = result.get("state")
        if state is not None and state.get("reliability_verdict") == "BLOCK":
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
                "audit_pass_rate",
                "false_acceptance_rate",
                "audit_false_acceptance_rate",
                "block_rate",
                "warn_rate",
                "avg_reliability_score",
                "avg_outcome_score",
            ]
        )

        for version in versions:
            metrics = all_metrics.get(version, {})
            version_results = all_results.get(version, [])
            writer.writerow(
                [
                    version,
                    metrics.get("total_tasks", len(version_results)),
                    metrics.get("pass_rate", 0.0),
                    metrics.get("audit_pass_rate", 0.0),
                    metrics.get("false_acceptance_rate", 0.0),
                    metrics.get("audit_false_acceptance_rate", 0.0),
                    metrics.get("block_rate", _compute_block_rate(version_results)),
                    metrics.get("warn_rate", 0.0),
                    metrics.get("avg_reliability_score", 0.0),
                    metrics.get("avg_outcome_score", 0.0),
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
                    "domain": row.get("domain"),
                    "version": row.get("version"),
                    "expected_outcome": row.get("expected_outcome"),
                    "actual_outcome": row.get("actual_outcome"),
                    "actual_audit_outcome": row.get("actual_audit_outcome"),
                    "pass_fail": row.get("pass_fail"),
                    "audit_pass_fail": row.get("audit_pass_fail"),
                    "outcome_score": row.get("outcome_score"),
                    "failure_type": row.get("failure_type"),
                    "reliability_score": row.get("reliability_score"),
                    "error": row.get("error"),
                    "tool_calls": row.get("tool_calls", 0),
                    "tokens": row.get("tokens", 0),
                }
            )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario_id",
                "domain",
                "version",
                "expected_outcome",
                "actual_outcome",
                "actual_audit_outcome",
                "pass_fail",
                "audit_pass_fail",
                "outcome_score",
                "failure_type",
                "reliability_score",
                "error",
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
        choices=["main", "verifier", "adversarial", "both", "all"],
        default="main",
    )
    parser.add_argument(
        "--domain",
        choices=["ecommerce", "reference", "all"],
        default="all",
    )
    parser.add_argument(
        "--model",
        choices=["qwen", "deepseek"],
        default="qwen",
    )
    parser.add_argument(
        "--input",
        help="Optional explicit scenario JSON file. Domain filtering still applies.",
    )
    args = parser.parse_args()

    selected_scenarios = (
        _filter_by_domain(_load_scenarios(args.input), args.domain)
        if args.input
        else _select_scenarios(args.scenarios, args.domain)
    )
    run_stamp = make_run_stamp()
    log_path = os.path.join("logs", args.domain, f"{build_run_id(args.domain, run_stamp)}.log")

    with _tee_to_log(log_path):
        print(
            f"[BENCHMARK] model={args.model} domain={args.domain} scenarios={args.scenarios} total={len(selected_scenarios)}"
        )
        run_benchmark(
            scenarios=selected_scenarios,
            model=args.model,
        )
