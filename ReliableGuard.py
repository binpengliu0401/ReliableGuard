import argparse
import io
import json
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Any

VERSION_CHOICES = ["V1_Baseline", "V2_Gate", "V3_Verifier", "V4_Full"]


def _to_json_safe(value: Any):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReliableGuard runtime CLI entry point")
    parser.add_argument(
        "--domain",
        choices=["ecommerce", "reference"],
        default="ecommerce",
    )
    parser.add_argument("--input", required=True, help="User instruction for the agent")
    parser.add_argument(
        "--model",
        choices=["qwen", "deepseek"],
        default="qwen",
    )
    parser.add_argument(
        "--version",
        choices=VERSION_CHOICES,
        default="V4_Full",
        help="Ablation version preset",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset domain environment before running",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show internal runtime logs",
    )
    parser.add_argument(
        "--full-result",
        action="store_true",
        help="Print full raw agent state",
    )
    return parser


@contextmanager
def _silence_stdio(enabled: bool):
    if not enabled:
        yield
        return

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def main():
    parser = _build_parser()
    args = parser.parse_args()

    with _silence_stdio(enabled=not args.verbose):
        from eval.config.ablation_versions import VERSIONS, with_deepseek
        from src.agent.langgraph_agent import run_agent
        from src.db.reset_env import reset_env
        from src.db.reset_reference_env import reset_reference_env

        if args.reset:
            if args.domain == "ecommerce":
                reset_env()
            else:
                reset_reference_env()

        config = VERSIONS[args.version]
        if args.model == "deepseek":
            config = with_deepseek(config)

        result = run_agent(
            args.input,
            domain=args.domain,
            config=config,
        )

    output = {
        "domain": args.domain,
        "model": args.model,
        "version": config.version_name,
    }
    if args.full_result:
        output["result"] = _to_json_safe(result)
    else:
        output["result"] = {
            "final_answer": result.get("final_answer"),
            "gate_status": result.get("gate_status"),
            "verifier_status": result.get("verifier_status"),
            "recovery_action": result.get("recovery_action"),
            "executed_tools": _to_json_safe(result.get("executed_tools", [])),
            "total_tokens": result.get("total_tokens", 0),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
