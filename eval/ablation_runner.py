from src.config.ablation_config import AblationConfig, VERSIONS
from src.agent.langgraph_agent import run_agent
from src.db.reset_env import reset_env


def run_version(
    version_key: str,
    scenarios: list[dict],
    verbose: bool = True,
    config_override: AblationConfig = None,  # type: ignore
) -> list[dict]:
    config = config_override if config_override else VERSIONS[version_key]
    results = []

    print(f"\n{'#'*60}")
    print(f"# VERSION: {config.version_name}")
    print(f"{'#'*60}")

    reset_env()

    for task in scenarios:
        try:
            state = run_agent(task["input"], config=config)
        except Exception as e:
            error_label = type(e).__name__
            print(f"[ERROR] {task['id']} | {error_label}: {e}")
            results.append(
                {
                    "task": task,
                    "state": None,
                    "version": version_key,
                    "error": error_label,
                }
            )
            continue

        results.append({"task": task, "state": state, "version": version_key})

        if verbose:
            from eval.metrics import derive_outcome

            actual = derive_outcome(state)
            expected = task["expected_outcome"]
            match = "OK" if actual == expected else "MISMATCH"
            print(f"[{match}] {task['id']} | expected={expected} actual={actual}")

    return results


if __name__ == "__main__":
    import argparse
    import json
    from eval.metrics import compute_metrics

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios", type=int, default=10, help="Number of scenarios to run"
    )
    parser.add_argument(
        "--input", type=str, default="tasks/scenarios.json", help="Scenarios file"
    )
    parser.add_argument(
        "--versions", nargs="+", default=list(VERSIONS.keys()), help="Versions to run"
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        all_scenarios = json.load(f)
    scenarios = all_scenarios[: args.scenarios]

    print(f"Running {len(scenarios)} scenarios on versions: {args.versions}")

    for version_key in args.versions:
        results = run_version(version_key, scenarios)
        metrics = compute_metrics(results)
        print(f"\n[METRICS] {version_key}: {metrics}")
