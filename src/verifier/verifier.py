from dataclasses import dataclass
from src.verifier.state_tracker import StateDiff


@dataclass
class VerifierResult:
    passed: bool
    verdict: str  # "SUCCESS" / "FAIL_SUCCESS" / "UNVERIFIED"
    evidence: str


def verify_create_order(user_input: str, diff: StateDiff) -> VerifierResult:
    # No order
    if not diff.order_created:
        return VerifierResult(passed=False, verdict="UNVERIFIED", evidence="No Order")

    if diff.new_order is None:
        return VerifierResult(
            passed=False, verdict="UNVERIFIED", evidence="New order is missing"
        )

    # print(f"DEBUG new_order: {diff.new_order}")
    actual_amount = diff.new_order["amount"]

    # User inputs negative signals
    negative_signals = ["-", "negative", "minus", "负"]
    usder_intended_nagetive = any(s in user_input.lower() for s in negative_signals)

    # User inputs negative values and LLM transforms to positive
    if usder_intended_nagetive and actual_amount > 0:
        return VerifierResult(
            passed=False,
            verdict="FALSE_SUCCESS",
            evidence=(
                f"User input suggests negative amount, "
                f"but DB recorded amount={actual_amount}."
                f"Silent sign conversion detected."
            ),
        )
    return VerifierResult(
        passed=True,
        verdict="SUCCESS",
        evidence=f"DB state consistent with user intent. Amount={actual_amount}",
    )
