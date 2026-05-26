class LLMResponseTruncatedError(RuntimeError):
    """Raised when an LLM response hits max_tokens and may be incomplete."""
