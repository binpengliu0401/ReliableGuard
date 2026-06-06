from src.reliableguard.schema import (
    Claim,
    InterventionAction,
    InterventionResult,
    OverallVerdict,
    RiskResult,
    VerificationResult,
)

# Evidence states where the verifier actually grounded the claim against a source.
# A PASS whose grounded fraction (TCCR) falls below the threshold is reported as
# PASS_UNCHECKED: the answer passed but the monitor could not really check it.
# 🟡 Threshold is a judgment call (currently 0.3); adjust here.
_GROUNDED_STATES = {"supported", "contradicted", "unsupported", "not_found"}
PASS_COVERAGE_THRESHOLD = 0.3


def decide_interventions(
    claims: list[Claim],
    verification_results: dict[str, VerificationResult],
    risks: dict[str, RiskResult],
    reliability_score: float,
) -> tuple[dict[str, InterventionResult], OverallVerdict]:
    interventions: dict[str, InterventionResult] = {}
    for claim in claims:
        verification = verification_results[claim.claim_id]
        risk = risks[claim.claim_id]
        action = _decide_action(verification, risk)
        interventions[claim.claim_id] = InterventionResult(
            claim_id=claim.claim_id,
            action=action,
            reason=f"{verification.evidence_state} evidence with {risk.risk_level} risk.",
        )

    overall = _aggregate(interventions, risks, reliability_score, verification_results)
    return interventions, overall


def _coverage(verification_results: dict[str, VerificationResult]) -> float:
    if not verification_results:
        return 0.0
    grounded = sum(
        1 for v in verification_results.values() if v.evidence_state in _GROUNDED_STATES
    )
    return grounded / len(verification_results)


def _decide_action(verification: VerificationResult, risk: RiskResult) -> InterventionAction:
    if verification.evidence_state in {"contradicted", "not_found"} and risk.risk_level == "high":
        return "BLOCK"
    if verification.evidence_state in {"contradicted", "not_found"}:
        return "WARN"
    if verification.evidence_state == "unsupported":
        return "WARN"
    if verification.evidence_state == "unverifiable":
        return "PASS"
    return "PASS"


def _aggregate(
    interventions: dict[str, InterventionResult],
    risks: dict[str, RiskResult],
    reliability_score: float,
    verification_results: dict[str, VerificationResult] | None = None,
) -> OverallVerdict:
    # Zero claims means the extractor produced nothing to audit. Fail closed:
    # emit AUDIT_FAILED instead of letting an empty pipeline fall through to
    # reliability_score=1.0 -> PASS (which silently looks like a clean answer).
    if not interventions:
        return "AUDIT_FAILED"
    for claim_id, intervention in interventions.items():
        if intervention.action == "BLOCK" and risks[claim_id].risk_level == "high":
            return "BLOCK"
    if reliability_score < 0.6:
        return "WARN"
    if any(item.action in {"WARN", "BLOCK"} for item in interventions.values()):
        return "WARN"
    # Coverage-aware PASS: flag passes the monitor could not actually substantiate.
    coverage = _coverage(verification_results or {})
    return "PASS_VERIFIED" if coverage >= PASS_COVERAGE_THRESHOLD else "PASS_UNCHECKED"
