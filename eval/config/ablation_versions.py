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
# T8: same monitor as V3_Intervention, but the agent prompt is given the >5000
# approval policy. Used to test whether prompting the policy suffices (it does not,
# adversarially), motivating the deterministic structural check (RQ2 F2 hardening).
V3_POLICY_AWARE = replace(
    V3_INTERVENTION,
    policy_aware=True,
    version_name="V3_PolicyAware",
)


VERSIONS = {
    "V1_Baseline": V1_BASELINE,
    "V2_AuditOnly": V2_AUDIT_ONLY,
    "V3_Intervention": V3_INTERVENTION,
    "V3_NoStructural": V3_NO_STRUCTURAL,
    "V3_PolicyAware": V3_POLICY_AWARE,
}


def with_deepseek(config: RuntimeConfig) -> RuntimeConfig:
    return replace(
        config,
        llm_model=DEEPSEEK_MODEL,
        llm_base_url=OPENROUTER_BASE_URL,
        version_name=config.version_name + "_DeepSeek",
    )
