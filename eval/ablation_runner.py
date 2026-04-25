from eval.config.ablation_versions import VERSIONS
from src.agent.langgraph_agent import run_agent
from src.config.runtime_config import RuntimeConfig
from src.db.reset_env import reset_env
from eval.metrics import derive_outcome, build_result_row


def run_version(
    version_key: str,
    scenarios: list[dict],
    verbose: bool = True,
    config_override: RuntimeConfig | None = None,
) -> list[dict]:
    config = config_override if config_override else VERSIONS[version_key]
    results = []

    print(f"\n{'#'*60}")
    print(f"# VERSION: {config.version_name}")
    print(f"{'#'*60}")

    for task in scenarios:
        domain = task.get("domain", "ecommerce")
        if domain == "ecommerce":
            reset_env()
        else:
            from src.db.reset_reference_env import reset_reference_env

            reset_reference_env()
        try:
            state = run_agent(
                task["input"],
                domain=domain,
                config=config,
            )
            row = build_result_row(
                task=task, state=state, version=version_key, error=None
            )

            results.append(
                {
                    "task": task,
                    "state": state,
                    "version": version_key,
                    "error": None,
                    "scored_row": row,
                }
            )

            if verbose:
                actual = row["actual_outcome"]
                expected = row["expected_outcome"]
                match = "OK" if actual == expected else "MISMATCH"
                print(f"[{match}] {task['id']} | expected={expected} actual={actual}")

        except Exception as e:
            error_label = type(e).__name__
            print(f"[ERROR] {task['id']} | {error_label}: {e}")

            row = build_result_row(
                task=task, state=None, version=version_key, error=error_label
            )

            results.append(
                {
                    "task": task,
                    "state": None,
                    "version": version_key,
                    "error": error_label,
                    "scored_row": row,
                }
            )

    return results


if __name__ == "__main__":
    import argparse
    import json
    import os
    import random
    from eval.metrics import compute_metrics

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios", type=int, default=10, help="Number of scenarios to run"
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Number of scenarios to skip from the start of input file before sampling",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="tasks/ecommerce_scenarios.json",
        help="Scenarios file",
    )
    parser.add_argument(
        "--versions", nargs="+", default=list(VERSIONS.keys()), help="Versions to run"
    )
    parser.add_argument(
        "--stratified",
        action="store_true",
        help="Sample evenly across failure categories F0-F5 using scenario id prefix",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="logs/ablation_metrics.json",
        help="Output file for metrics",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        all_scenarios = json.load(f)
    source_scenarios = all_scenarios[args.skip :]

    if args.stratified:
        categories = [f"F{i}" for i in range(6)]
        quota = args.scenarios // len(categories)
        grouped = {cat: [] for cat in categories}

        for scenario in source_scenarios:
            scenario_id = str(scenario.get("id", ""))
            for cat in categories:
                if scenario_id.startswith(cat):
                    grouped[cat].append(scenario)
                    break

        rng = random.Random(42)
        scenarios = []
        for cat in categories:
            candidates = grouped[cat]
            if len(candidates) <= quota:
                scenarios.extend(candidates)
            else:
                scenarios.extend(rng.sample(candidates, quota))
    else:
        scenarios = source_scenarios[: args.scenarios]

    print(f"Running {len(scenarios)} scenarios on versions: {args.versions}")

    all_metrics = {}
    for version_key in args.versions:
        results = run_version(version_key, scenarios)
        metrics = compute_metrics(results)
        all_metrics[version_key] = metrics
        print(f"\n[METRICS] {version_key}: {metrics}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Metrics written to {args.output}")
