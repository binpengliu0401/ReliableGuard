from dataclasses import dataclass

QWEN_PLUS_MODEL = "qwen-plus"
QWEN_PLUS_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

GPT4O_MINI_MODEL = "openai/gpt-5.4-mini"
GPT4O_MINI_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class AblationConfig:
    use_gate: bool = True
    use_verifier: bool = True
    use_recovery: bool = True
    version_name: str = "V4_Full"
    llm_model: str = QWEN_PLUS_MODEL
    llm_base_url: str = QWEN_PLUS_BASE_URL


VERSIONS = {
    "V1_Baseline": AblationConfig(
        use_gate=False,
        use_verifier=False,
        use_recovery=False,
        version_name="V1_Baseline",
    ),
    "V2_Gate": AblationConfig(
        use_gate=True,
        use_verifier=False,
        use_recovery=False,
        version_name="V2_Gate",
    ),
    "V3_Verifier": AblationConfig(
        use_gate=True,
        use_verifier=True,
        use_recovery=False,
        version_name="V3_Verifier",
    ),
    "V4_Full": AblationConfig(
        use_gate=True,
        use_verifier=True,
        use_recovery=True,
        version_name="V4_Full",
    ),
}


def with_gpt4o_mini(config: AblationConfig) -> AblationConfig:
    return AblationConfig(
        use_gate=config.use_gate,
        use_verifier=config.use_verifier,
        use_recovery=config.use_recovery,
        version_name=config.version_name + "_GPT4oMini",
        llm_model=GPT4O_MINI_MODEL,
        llm_base_url=GPT4O_MINI_BASE_URL,
    )
