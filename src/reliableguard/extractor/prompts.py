from src.reliableguard.classifier.taxonomy import CLAIM_TAXONOMY


def build_claim_extraction_prompt(domain: str, query: str, agent_answer: str) -> list[dict[str, str]]:
    taxonomy_lines = "\n".join(
        f"- {name}: {meta['definition']}" for name, meta in CLAIM_TAXONOMY.items()
    )
    domain_hint = {
        "ecommerce": (
            "Focus on order ids, amounts, counts, statuses, refunds, and tool-reported results. "
            "Use attribute for status fields and numeric for amounts or counts."
        ),
        "reference": (
            "Focus on paper ids, reference ids, titles, DOIs, authors, journals, years, "
            "reference counts, DOI verification results, and bibliographic metadata."
        ),
    }.get(domain, "Extract only verifiable factual claims.")

    system = (
        "You extract atomic factual claims from an AI agent answer. "
        "Return strict JSON only with a top-level key 'claims'. "
        "Each claim must contain claim_id, text, claim_type, entities, attribute, value, "
        "unit, time_range, certainty, and confidence. "
        "claim_type must be one of: existence, attribute, numeric, temporal, relational, semantic. "
        "certainty must be one of: certain, uncertain, abstained. "
        "Do not include recommendations or unverifiable opinions unless they are explicit claims."
    )
    user = (
        f"Domain: {domain}\n"
        f"Domain hint: {domain_hint}\n\n"
        f"Claim taxonomy:\n{taxonomy_lines}\n\n"
        f"User query:\n{query}\n\n"
        f"Agent answer:\n{agent_answer}\n\n"
        "Return JSON in this shape:\n"
        '{"claims":[{"claim_id":"c1","text":"...","claim_type":"numeric",'
        '"entities":{"order_id":1},"attribute":"amount","value":100,'
        '"unit":null,"time_range":null,"certainty":"certain","confidence":1.0}]}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

