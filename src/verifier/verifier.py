from dataclasses import dataclass
from src.verifier.state_tracker import StateDiff


@dataclass
class VerifierResult:
    passed: bool
    verdict: str
    evidence: str


def verify(
    func_name: str,
    func_args: dict,
    diff: StateDiff,
    tool_config: dict,
) -> VerifierResult:
    config = tool_config.get(func_name, {})
    assertions = config.get("assertions", [])

    if not assertions:
        return VerifierResult(
            passed=False, verdict="UNVERIFIED", evidence="No assertions defined"
        )

    for assertion in assertions:
        if not assertion["check"](diff, func_args):
            return VerifierResult(
                passed=False,
                verdict="FALSE_SUCCESS",
                evidence=f"Assertion '{assertion['name']}' failed: {assertion['failure']}",
            )

    return VerifierResult(
        passed=True, verdict="SUCCESS", evidence="All assertions passed"
    )
