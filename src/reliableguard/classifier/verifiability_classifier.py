from src.reliableguard.schema import Claim, Verifiability


def classify_verifiability(domain: str, claims: list[Claim]) -> dict[str, Verifiability]:
    return {claim.claim_id: _classify_one(domain, claim) for claim in claims}


def _classify_one(domain: str, claim: Claim) -> Verifiability:
    if claim.claim_type == "semantic":
        return "partially_verifiable" if domain == "reference" else "unverifiable"

    if domain == "ecommerce":
        if claim.entities.get("order_id") is not None or claim.attribute in {
            "order_count",
            "order_total",
            "amount",
            "status",
            "payment_status",
        }:
            return "fully_verifiable"
        return "unverifiable"

    if domain == "reference":
        if (
            claim.entities.get("doi")
            or claim.entities.get("ref_id")
            or claim.entities.get("paper_id")
            or claim.attribute in {"reference_count", "ref_count", "author_count", "authors_count"}
        ):
            return "fully_verifiable"
        if claim.entities.get("paper_title") or claim.attribute in {"title", "authors", "journal", "year"}:
            return "partially_verifiable"
        return "unverifiable"

    return "unverifiable"
