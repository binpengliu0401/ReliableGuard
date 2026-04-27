from src.config.runtime_config import (
    DEEPSEEK_MODEL,
    OPENROUTER_BASE_URL,
    RuntimeConfig,
)

VERSIONS = {
    "V1_Baseline": RuntimeConfig(
        use_verifier=False,
        enforce_intervention=False,
        version_name="V1_Baseline",
    ),
    # V2_NoReliability: Same flags as V1; intended for DeepSeek cross-model comparison.
    # Use with with_deepseek(VERSIONS["V2_NoReliability"]) when running --model deepseek.
    "V2_NoReliability": RuntimeConfig(
        use_verifier=False,
        enforce_intervention=False,
        version_name="V2_NoReliability",
    ),
    "V3_AuditOnly": RuntimeConfig(
        use_verifier=True,
        enforce_intervention=False,
        version_name="V3_AuditOnly",
    ),
    "V4_Full": RuntimeConfig(
        use_verifier=True,
        enforce_intervention=True,
        version_name="V4_Intervention",
    ),
}


def with_deepseek(config: RuntimeConfig) -> RuntimeConfig:
    return RuntimeConfig(
        use_verifier=config.use_verifier,
        enforce_intervention=config.enforce_intervention,
        version_name=config.version_name + "_DeepSeek",
        llm_model=DEEPSEEK_MODEL,
        llm_base_url=OPENROUTER_BASE_URL,
        llm_temperature=config.llm_temperature,
        llm_seed=config.llm_seed,
    )
