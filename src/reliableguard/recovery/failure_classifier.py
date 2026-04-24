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
    REFERENCE_DOI_FAILED = "reference_doi_failed"    # legacy fallback
    REFERENCE_DOI_INVALID = "reference_doi_invalid"   # DOI not found in CrossRef (transient retry eligible)
    REFERENCE_DOI_MISMATCH = "reference_doi_mismatch" # DOI points to a different paper (hard terminate)
    REFERENCE_DOI_UNCERTAIN = "reference_doi_uncertain"  # title score 0.50–0.80, needs human review


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


def _extract_doi_verdict_code(evidence: str) -> str | None:
    """Parse doi_verdict_code=<value> from assertion evidence string."""
    import re
    m = re.search(r"doi_verdict_code=(\w+)", evidence)
    return m.group(1) if m else None


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
        verdict_code = _extract_doi_verdict_code(verifier_result.evidence)
        if verdict_code == "invalid":
            return FailurePacket(
                failure_type=FailureType.REFERENCE_DOI_INVALID,
                source="verifier",
                reason="DOI not found in CrossRef — may be a typo or transient lookup failure.",
                context={"verifier_evidence": verifier_result.evidence},
            )
        if verdict_code == "mismatch":
            return FailurePacket(
                failure_type=FailureType.REFERENCE_DOI_MISMATCH,
                source="verifier",
                reason="DOI exists but points to a different paper — likely a fabricated or misattributed reference.",
                context={"verifier_evidence": verifier_result.evidence},
            )
        if verdict_code == "uncertain":
            return FailurePacket(
                failure_type=FailureType.REFERENCE_DOI_UNCERTAIN,
                source="verifier",
                reason="DOI exists but title similarity is too low to confirm — PDF extraction quality may be insufficient.",
                context={"verifier_evidence": verifier_result.evidence},
            )
        # Fallback for older DB rows without verdict code.
        return FailurePacket(
            failure_type=FailureType.REFERENCE_DOI_FAILED,
            source="verifier",
            reason="DOI verification failed: the DOI does not exist or does not match the reference metadata.",
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
