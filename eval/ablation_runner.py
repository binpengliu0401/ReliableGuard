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
