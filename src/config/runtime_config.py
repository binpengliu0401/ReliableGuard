from dataclasses import dataclass

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
QWEN_PLUS_MODEL = "qwen/qwen-plus"

DEEPSEEK_MODEL = "deepseek/deepseek-chat-v3-0324"


@dataclass
class RuntimeConfig:
    use_verifier: bool = True
    enforce_intervention: bool = True
    version_name: str = "V4_Full"
    llm_model: str = QWEN_PLUS_MODEL
    llm_base_url: str = OPENROUTER_BASE_URL


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()
