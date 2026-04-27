from src.config.runtime_config import (
    DEEPSEEK_MODEL,
    OPENROUTER_BASE_URL,
    RuntimeConfig,
)


V1_BASELINE = RuntimeConfig(
    use_verifier=False,
    enforce_intervention=False,
    version_name="V1_Baseline",
)
V2_NO_RELIABILITY = RuntimeConfig(
    use_verifier=False,
    enforce_intervention=False,
    version_name="V2_NoReliability",
)
V2_AUDIT_ONLY = RuntimeConfig(
    use_verifier=True,
    enforce_intervention=False,
    version_name="V2_AuditOnly",
)
V3_INTERVENTION = RuntimeConfig(
    use_verifier=True,
    enforce_intervention=True,
    version_name="V3_Intervention",
)


VERSIONS = {
    "V1_Baseline": V1_BASELINE,
    # V2_NoReliability: Same flags as V1; intended for DeepSeek cross-model comparison.
    # Use with with_deepseek(VERSIONS["V2_NoReliability"]) when running --model deepseek.
    "V2_NoReliability": V2_NO_RELIABILITY,
    "V2_AuditOnly": V2_AUDIT_ONLY,
    "V3_Intervention": V3_INTERVENTION,
    # Legacy aliases kept for old commands and previous result artifacts.
    "V3_AuditOnly": V2_AUDIT_ONLY,
    "V4_Full": V3_INTERVENTION,
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
