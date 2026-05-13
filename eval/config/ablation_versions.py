from dataclasses import replace

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
V3_NO_STRUCTURAL = replace(
    V3_INTERVENTION,
    use_structural_audit=False,
    version_name="V3_NoStructural",
)


VERSIONS = {
    "V1_Baseline": V1_BASELINE,
    "V2_AuditOnly": V2_AUDIT_ONLY,
    "V3_Intervention": V3_INTERVENTION,
    "V3_NoStructural": V3_NO_STRUCTURAL,
}


def with_deepseek(config: RuntimeConfig) -> RuntimeConfig:
    return RuntimeConfig(
        use_verifier=config.use_verifier,
        enforce_intervention=config.enforce_intervention,
        use_structural_audit=config.use_structural_audit,
        version_name=config.version_name + "_DeepSeek",
        llm_model=DEEPSEEK_MODEL,
        llm_base_url=OPENROUTER_BASE_URL,
        llm_temperature=config.llm_temperature,
        llm_seed=config.llm_seed,
    )
