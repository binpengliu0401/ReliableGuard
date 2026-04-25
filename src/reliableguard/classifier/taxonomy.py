from src.reliableguard.schema import ClaimType, EvidenceState, Verifiability


CLAIM_TAXONOMY: dict[ClaimType, dict[str, str]] = {
    "existence": {
        "definition": "A claim that an entity exists in an authoritative source.",
        "evidence": "Entity lookup by primary identifier, DOI, order id, paper id, or reference id.",
        "example": "Order 42 exists. DOI 10.1145/example exists.",
    },
    "attribute": {
        "definition": "A claim about a direct non-numeric property of one entity.",
        "evidence": "Exact or normalized comparison against a source field.",
        "example": "Order 42 is paid. The paper was published at NeurIPS.",
    },
    "numeric": {
        "definition": "A claim about a count, amount, score, year, or other numeric value.",
        "evidence": "Numeric field lookup, aggregation, or deterministic calculation.",
        "example": "The order amount is 300. The paper has 12 references.",
    },
    "temporal": {
        "definition": "A claim about dates, order, duration, or state transition timing.",
        "evidence": "Timestamp fields, event logs, or ordered status history.",
        "example": "The order was created yesterday.",
    },
    "relational": {
        "definition": "A claim about a relationship between two or more entities.",
        "evidence": "Foreign keys, ownership records, reference links, or set membership.",
        "example": "Order 42 belongs to customer A. Paper A cites paper B.",
    },
    "semantic": {
        "definition": "A claim requiring textual grounding or interpretation.",
        "evidence": "Retrieved text spans or metadata that semantically support the claim.",
        "example": "The paper proposes a new agent evaluation method.",
    },
}


EVIDENCE_STATE_RULES: dict[EvidenceState, str] = {
    "supported": "Authoritative evidence confirms the claim.",
    "contradicted": "The primary entity exists, but evidence conflicts with the claimed value or relation.",
    "unsupported": "Relevant evidence exists, but it is insufficient to support the claim.",
    "unverifiable": "No suitable authoritative source or verification path exists.",
    "not_found": "The claimed primary entity cannot be resolved in the authoritative source.",
}


VERIFIABILITY_RULES: dict[Verifiability, str] = {
    "fully_verifiable": "The claim can be checked against a deterministic or authoritative source.",
    "partially_verifiable": "The claim can be checked only with fuzzy matching, incomplete metadata, or semantic evidence.",
    "unverifiable": "The claim has no available verification path in the current domain.",
}

