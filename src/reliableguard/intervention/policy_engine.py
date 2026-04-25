from src.reliableguard.schema import Claim, InterventionResult, RiskResult, VerificationResult


def decide_interventions(
    claims: list[Claim],
    verification_results: dict[str, VerificationResult],
    risks: dict[str, RiskResult],
    reliability_score: float,
) -> tuple[dict[str, InterventionResult], str]:
    interventions: dict[str, InterventionResult] = {}
    for claim in claims:
        verification = verification_results[claim.claim_id]
        risk = risks[claim.claim_id]
        action = _decide_action(verification, risk)
        interventions[claim.claim_id] = InterventionResult(
            claim_id=claim.claim_id,
            action=action,  # type: ignore[arg-type]
            reason=f"{verification.evidence_state} evidence with {risk.risk_level} risk.",
        )

    overall = _aggregate(interventions, risks, reliability_score)
    return interventions, overall


def _decide_action(verification: VerificationResult, risk: RiskResult) -> str:
    if verification.evidence_state in {"contradicted", "not_found"} and risk.risk_level == "high":
        return "BLOCK"
    if verification.evidence_state in {"contradicted", "not_found"}:
        return "WARN"
    if verification.evidence_state == "unsupported":
        return "WARN"
    if verification.evidence_state == "unverifiable":
        return "ESCALATE"
    return "PASS"


def _aggregate(
    interventions: dict[str, InterventionResult],
    risks: dict[str, RiskResult],
    reliability_score: float,
) -> str:
    for claim_id, intervention in interventions.items():
        if intervention.action == "BLOCK" and risks[claim_id].risk_level == "high":
            return "BLOCK"
    if reliability_score < 0.6:
        return "WARN"
    if any(item.action in {"WARN", "ESCALATE", "BLOCK"} for item in interventions.values()):
        return "WARN"
    return "PASS"

