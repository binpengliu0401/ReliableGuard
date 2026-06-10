from src.reliableguard.schema import Claim, Verifiability, VerificationResult

# Benchmark verifier registry. Each entry verifies a claim-set jointly (not claim-by-claim)
# against that benchmark's observable grounding artifacts (state / trace / evidence).
# The legacy self-made ecommerce + reference verifiers were removed in the 2026-06-09 pivot;
# the tau-bench state / trace / evidence verifiers are registered here in Phase 2.
# Signature for a registered verifier:
#   (claims, verifiability) -> dict[claim_id, VerificationResult]
_VERIFIERS: dict[str, object] = {}


def verify_claims(
    domain: str,
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
) -> dict[str, VerificationResult]:
    verifier = _VERIFIERS.get(domain)
    if verifier is not None:
        return verifier(claims, verifiability)  # type: ignore[operator]

    # No verifier registered for this domain yet: every claim is reported as unverifiable
    # (the monitor cannot reach a grounding source). Phase 2 registers the tau-bench verifiers.
    return {
        claim.claim_id: VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unverifiable",
            confidence=1.0,
            reason=f"No verifier registered for domain: {domain}",
        )
        for claim in claims
    }
