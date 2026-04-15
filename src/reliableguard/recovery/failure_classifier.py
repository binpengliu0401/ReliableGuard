from enum import Enum
from dataclasses import dataclass
from src.reliableguard.gate.validator import GateResult
from src.reliableguard.verifier.verifier import VerifierResult


# Standardized failure types for recovery strategy mapping
class FailureType(Enum):
    GATE_SCHEMA_BLOCKED = "gate_schema_blocked"
    GATE_POLICY_BLOCKED = "gate_policy_blocked"
    GATE_DEPENDENCY_BLOCKED = "gate_dependency_blocked"
    FALSE_SUCCESS = "false_success"
    VERIFY_FAIL = "verify_fail"
    REFERENCE_DOI_FAILED = "reference_doi_failed"


# Structured failure information passed to recovery controller
@dataclass
class FailurePacket:
    failure_type: FailureType
    source: str
    reason: str
    context: dict | None = None


def classify_gate_failure(gate_result: GateResult, func_name: str) -> FailurePacket:
    reason = gate_result.reason

    if "Dependency violation" in reason:
        return FailurePacket(
            failure_type=FailureType.GATE_DEPENDENCY_BLOCKED,
            source="gate",
            reason=reason,
            context={"func_name": func_name},
        )

    if "Policy violation" in reason:
        return FailurePacket(
            failure_type=FailureType.GATE_POLICY_BLOCKED,
            source="gate",
            reason=reason,
            context={"func_name": func_name},
        )

    return FailurePacket(
        failure_type=FailureType.GATE_SCHEMA_BLOCKED,
        source="gate",
        reason=reason,
        context={"func_name": func_name},
    )


# Classify a Verifier failure into a specific failure type
def classify_verifier_failure(verifier_result: VerifierResult) -> FailurePacket:
    if verifier_result.verdict == "FALSE_SUCCESS":
        return FailurePacket(
            failure_type=FailureType.FALSE_SUCCESS,
            source="verifier",
            reason=verifier_result.evidence,
        )

    verdict_message = (
        f"{verifier_result.verdict} {verifier_result.evidence}".lower()
    )
    if (
        "doi_status_verified" in verdict_message
        or "doi_status=failed" in verdict_message
    ):
        return FailurePacket(
            failure_type=FailureType.REFERENCE_DOI_FAILED,
            source="verifier",
            reason=(
                "DOI verification failed: the DOI does not exist or does not match "
                "the reference metadata."
            ),
            context={
                "verifier_verdict": verifier_result.verdict,
                "verifier_evidence": verifier_result.evidence,
            },
        )

    return FailurePacket(
        failure_type=FailureType.VERIFY_FAIL,
        source="verifier",
        reason=verifier_result.evidence,
    )
