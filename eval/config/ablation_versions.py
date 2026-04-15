from src.config.runtime_config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    RuntimeConfig,
)

VERSIONS = {
    "V1_Baseline": RuntimeConfig(
        use_gate=False,
        use_verifier=False,
        use_recovery=False,
        version_name="V1_Baseline",
    ),
    "V2_Gate": RuntimeConfig(
        use_gate=True,
        use_verifier=False,
        use_recovery=False,
        version_name="V2_Gate",
    ),
    "V3_Verifier": RuntimeConfig(
        use_gate=True,
        use_verifier=True,
        use_recovery=False,
        version_name="V3_Verifier",
    ),
    "V4_Full": RuntimeConfig(
        use_gate=True,
        use_verifier=True,
        use_recovery=True,
        version_name="V4_Full",
    ),
}


def with_deepseek(config: RuntimeConfig) -> RuntimeConfig:
    return RuntimeConfig(
        use_gate=config.use_gate,
        use_verifier=config.use_verifier,
        use_recovery=config.use_recovery,
        version_name=config.version_name + "_DeepSeek",
        llm_model=DEEPSEEK_MODEL,
        llm_base_url=DEEPSEEK_BASE_URL,
    )
