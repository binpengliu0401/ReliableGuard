from src.reliableguard.schema import (
    Claim,
    Verifiability,
    VerificationContext,
    VerificationResult,
)

# Benchmark verifier registry. Each entry verifies a claim-set jointly (not claim-by-claim)
# against that benchmark's observable grounding artifacts (state / trace / evidence).
# The legacy self-made ecommerce + reference verifiers were removed in the 2026-06-09 pivot;
# the tau-bench state / trace / evidence verifiers are registered here in Phase 2.
# Signature for a registered verifier:
#   (claims, verifiability, context) -> dict[claim_id, VerificationResult]
# `context` (grounding injection, decision B) carries the trajectory Grounding plus the
# ChannelConfig; the verifier reads only the channels enabled in `context.channels`, so the
# same claims + grounding yield the V_answer / V_structural verdicts.
_VERIFIERS: dict[str, object] = {}

# Claims with these time_range values describe pre-action history or future intentions,
# not the current post-action database state. Verifying them against state_after produces
# spurious contradictions (false alarms). Skip them before routing to domain verifiers.
_NON_CURRENT_SCOPES = {"before_action", "future_plan", "during_action"}


def verify_claims(
    domain: str,
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
    context: VerificationContext | None = None,
) -> dict[str, VerificationResult]:
    context = context or VerificationContext()  # default = answer-only, no grounding

    scoped, skipped_claims = [], []
    for c in claims:
        if c.time_range in _NON_CURRENT_SCOPES:
            skipped_claims.append(c)
        else:
            scoped.append(c)

    skipped_results: dict[str, VerificationResult] = {
        c.claim_id: VerificationResult(
            claim_id=c.claim_id,
            evidence_state="unverifiable",
            confidence=1.0,
            reason=f"Temporal scope excluded: {c.time_range}",
        )
        for c in skipped_claims
    }

    verifier = _VERIFIERS.get(domain)
    if verifier is not None:
        return {**skipped_results, **verifier(scoped, verifiability, context)}  # type: ignore[operator]

    # No verifier registered for this domain yet: every claim is reported as unverifiable
    # (the monitor cannot reach a grounding source). Phase 2 registers the tau-bench verifiers.
    return {
        **skipped_results,
        **{
            claim.claim_id: VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                confidence=1.0,
                reason=f"No verifier registered for domain: {domain}",
            )
            for claim in scoped
        },
    }
