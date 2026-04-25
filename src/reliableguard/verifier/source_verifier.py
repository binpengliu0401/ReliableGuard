from src.reliableguard.schema import Claim, Verifiability, VerificationResult
from src.reliableguard.verifier.ecommerce_verifier import verify_ecommerce_claim
from src.reliableguard.verifier.reference_verifier import verify_reference_claim


def verify_claims(
    domain: str,
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
) -> dict[str, VerificationResult]:
    results: dict[str, VerificationResult] = {}
    for claim in claims:
        level = verifiability.get(claim.claim_id, "unverifiable")
        if level == "unverifiable":
            results[claim.claim_id] = VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                confidence=1.0,
                reason="No verification path is available for this claim.",
            )
            continue

        if domain == "ecommerce":
            results[claim.claim_id] = verify_ecommerce_claim(claim, level)
        elif domain == "reference":
            results[claim.claim_id] = verify_reference_claim(claim, level)
        else:
            results[claim.claim_id] = VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                confidence=1.0,
                reason=f"Unsupported domain: {domain}",
            )
    return results

