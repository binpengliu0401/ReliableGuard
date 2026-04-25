from src.reliableguard.schema import Claim, RiskResult, VerificationResult


CLAIM_WEIGHTS = {
    "existence": 1.0,
    "attribute": 0.8,
    "numeric": 1.0,
    "temporal": 0.7,
    "relational": 0.9,
    "semantic": 0.5,
}

STATE_PENALTY = {
    "supported": 0.0,
    "contradicted": 1.0,
    "unsupported": 0.6,
    "unverifiable": 0.4,
    "not_found": 1.0,
}


def score_risks(
    claims: list[Claim],
    verification_results: dict[str, VerificationResult],
) -> tuple[dict[str, RiskResult], float]:
    risks: dict[str, RiskResult] = {}
    total_weight = 0.0
    total_penalty = 0.0
    for claim in claims:
        result = verification_results[claim.claim_id]
        weight = CLAIM_WEIGHTS.get(claim.claim_type, 0.5)
        penalty = STATE_PENALTY.get(result.evidence_state, 0.4)
        score = min(1.0, weight * penalty)
        risks[claim.claim_id] = RiskResult(
            claim_id=claim.claim_id,
            risk_level=_risk_level(score),
            score=score,
            reason=f"{claim.claim_type} claim with evidence_state={result.evidence_state}.",
        )
        total_weight += weight
        total_penalty += weight * penalty

    reliability_score = 1.0 if total_weight == 0 else max(0.0, 1.0 - (total_penalty / total_weight))
    return risks, round(reliability_score, 4)


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"

