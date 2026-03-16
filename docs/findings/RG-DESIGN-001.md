# RG-DESIGN-001: Recovery-to-LLM Feedback Requires Business Context Injection

## Date

2026-03-16

## Category

Architecture Design Insight (not empirical finding)

## Observation

After Recovery module rolled back a FALSE_SUCCESS order (T04: silent sign conversion of -500 to 500), the LLM's final response told the user "if you need to create an order with a negative amount, please contact support." This suggestion is nonsensical — negative amount orders are never valid in the e-commerce domain.

## Root Cause

Recovery passed the rollback result to LLM via ToolMessage, but the message only described what happened (rollback executed, record deleted), not the business rule (negative amounts are invalid). LLM lacks business domain knowledge and attempted to infer a recovery path on its own, producing a misleading suggestion.

## Architectural Implication

Recovery-to-LLM feedback must include three layers of information:

1. What happened (action taken: rollback, terminate, retry)
2. What the current state is (record deleted, no order exists)
3. What the business rule says (negative amounts are not valid, guide user to provide a positive amount)

Without layer 3, LLM will fill the gap with hallucinated business logic.

## Design Decision

v0: hardcoded business context in system_note field of recovery result passed to LLM.
v1: business-level recovery messages should be configurable per failure type, stored in tool_config.py or a dedicated recovery_config.py, consistent with the config/logic separation principle used in Gate.

## Relevance to Thesis

- Recovery module design section: justifies why recovery feedback must be structured and business-aware, not just action-level
- Discussion section: example of "system-layer holds business rules, LLM handles natural language expression only" architectural principle
- Connects to RG-OBS-001: OBS-001 showed Gate cannot intercept model-level semantic decisions; DESIGN-001 shows Recovery output must also be constrained at system level to prevent LLM from generating incorrect business guidance
