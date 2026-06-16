from src.reliableguard.classifier.taxonomy import CLAIM_TAXONOMY


def build_claim_extraction_prompt(domain: str, query: str, agent_answer: str) -> list[dict[str, str]]:
    taxonomy_lines = "\n".join(
        f"- {name}: {meta['definition']}" for name, meta in CLAIM_TAXONOMY.items()
    )
    domain_hint = {
        "retail": (
            "Focus on order ids (format #Wnnnn), order statuses (pending/cancelled/delivered/"
            "return requested/exchange requested), refund amounts, item counts, and payment methods. "
            "Use attribute for status fields, numeric for amounts or counts, existence for order "
            "presence, and relational for modifications or cancellations. "
            "Apply the scope filter: discard 'Before' column values (before_action) and "
            "future promises (future_plan). Output only after_action claims."
        ),
        "airline": (
            "Focus on reservation ids (6-char uppercase alphanumeric, e.g. 4WQ150), cabin class "
            "(basic_economy/economy/business), baggage counts (total_baggages), cancellation status, "
            "flight numbers, insurance, and payment history. "
            "Use attribute for cabin/status fields, numeric for bag counts, existence for reservation "
            "presence. "
            "Apply the scope filter: discard pre-cancellation or pre-modification details "
            "(before_action). Output only after_action claims about the current reservation state."
        ),
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
        "Do not include recommendations or unverifiable opinions unless they are explicit claims.\n\n"
        "IMPORTANT — temporal scope filter (apply before outputting):\n"
        "Before adding a claim to the JSON output, classify it internally as one of:\n"
        "  after_action  — the agent's assertion about the CURRENT state after ALL actions completed.\n"
        "  before_action — how things looked BEFORE the agent acted "
        "(e.g. the 'Before' column in a comparison table, original values being replaced).\n"
        "  future_plan   — something that has NOT happened yet "
        "('you will receive a refund', 'please contact us to return', 'we will process').\n"
        "  during_action — an in-progress step description, not a final outcome.\n\n"
        "OUTPUT RULE: include ONLY after_action claims in the JSON. "
        "Silently discard before_action, future_plan, and during_action claims — do not list them.\n"
        "Set time_range='after_action' on every claim you output.\n\n"
        "Examples:\n"
        "  'Color: Before=Blue | After=Purple' → discard the Blue claim; output only Purple (after_action).\n"
        "  'Your reservation Z7GOZK has been cancelled' → output as after_action "
        "(past-perfect of a completed action is a current-state assertion).\n"
        "  'You will receive a $169 refund in 3-5 days' → discard (future_plan).\n"
        "  'I have updated your address to 123 Main St' → output as after_action."
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
        '"unit":null,"time_range":"after_action","certainty":"certain","confidence":1.0}]}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

