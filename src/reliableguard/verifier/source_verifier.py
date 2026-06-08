from src.reliableguard.schema import Claim, Verifiability, VerificationResult
from src.reliableguard.verifier.ecommerce_verifier import verify_ecommerce_claims
from src.reliableguard.verifier.reference_verifier import verify_reference_claims


def verify_claims(
    domain: str,
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
) -> dict[str, VerificationResult]:
    # Both domains verify claim-sets jointly rather than claim-by-claim: reference joins
    # claims about the same paper (citation-level sufficiency), ecommerce joins the status
    # claims of the same order (transition-aware state verification). Each is handed the
    # whole batch through a single entry point.
    if domain == "reference":
        return verify_reference_claims(claims, verifiability)
    if domain == "ecommerce":
        return verify_ecommerce_claims(claims, verifiability)

    return {
        claim.claim_id: VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unverifiable",
            confidence=1.0,
            reason=f"Unsupported domain: {domain}",
        )
        for claim in claims
    }

