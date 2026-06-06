from dataclasses import dataclass

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEEPSEEK_MODEL = "deepseek/deepseek-chat-v3-0324"


@dataclass
class RuntimeConfig:
    use_verifier: bool = True
    enforce_intervention: bool = True
    use_structural_audit: bool = True
    version_name: str = "V3_Intervention"
    llm_model: str = DEFAULT_MODEL
    llm_base_url: str = OPENROUTER_BASE_URL
    llm_temperature: float = 0.0
    llm_seed: int | None = None
    # max_tokens is a ceiling, not a target: raising it only prevents truncation
    # (LLMResponseTruncatedError -> task skip) and does not increase cost, which is
    # billed per token actually generated. The previous 2048 truncated long
    # reference answers / multi-claim extraction JSON, causing up to ~36% skipped
    # reference tasks in V2. Ceilings raised generously to drive truncation to ~0.
    # The full-scale Set A record (1550) still hit 21 agent-side truncations on the
    # longest reference verification answers at 4096, so the agent ceiling was raised
    # to 8192 (matches the extractor); cost-free, answer-length only.
    llm_max_tokens: int = 8192
    claim_extraction_max_tokens: int = 8192
    claim_extraction_temperature: float = 0.0
    # Record mode for the frozen-corpus methodology. When True, execute_node runs in
    # observe-only structural mode: it snapshots ecommerce state before/after every tool
    # call and computes structural issues as data, but never blocks execution. This yields
    # a config-independent behaviour trace that replay can audit under any monitor setting.
    capture_trace: bool = False
    # T8 policy-aware experiment: when True, the ecommerce agent system prompt is
    # given the >5000 approval policy. Used to test whether telling the agent the
    # policy is sufficient (it is not, especially adversarially), motivating the
    # deterministic structural check as a necessary backstop (RQ2 F2 hardening).
    policy_aware: bool = False


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()
