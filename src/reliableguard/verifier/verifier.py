from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerifierResult:
    passed: bool
    verdict: str
    evidence: str
    failed_assertions: list[dict[str, Any]] = field(default_factory=list)


def verify(
    func_name: str,
    func_args: dict,
    tool_config: dict,
    *,
    diff=None,
    context=None,
) -> VerifierResult:
    config = tool_config.get(func_name, {})
    assertions = config.get("assertions", [])

    if not assertions:
        return VerifierResult(
            passed=True,
            verdict="NO_ASSERTION_PASS",
            evidence="No assertions defined; treated as pass for this tool.",
            failed_assertions=[],
        )

    failures = []

    for assertion in assertions:
        check_fn = assertion["check"]

        try:
            if context is not None:
                ok, reason = check_fn(func_name, func_args, context)
            else:
                ok, reason = check_fn(func_name, func_args, diff)
        except Exception as e:
            failures.append(
                {
                    "name": assertion["name"],
                    "reason": f"assertion runtime error: {type(e).__name__}: {e}",
                }
            )
            continue

        if not ok:
            failures.append(
                {
                    "name": assertion["name"],
                    "reason": reason or assertion["failure"],
                }
            )

    if failures:
        return VerifierResult(
            passed=False,
            verdict="VERIFY_FAILED",
            evidence="; ".join(
                [f"{item['name']}: {item['reason']}" for item in failures]
            ),
            failed_assertions=failures,
        )

    return VerifierResult(
        passed=True,
        verdict="SUCCESS",
        evidence="All assertions passed",
        failed_assertions=[],
    )
