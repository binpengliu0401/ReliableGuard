import yaml
from pathlib import Path
from src.domain.registry import get_policy, get_assertion

_TYPE_MAP = {
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
    "list": list,
}


def load_tool_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tools = {}
    for tool_name, cfg in raw["tools"].items():
        rules = {}
        for field, rule in cfg.get("rules", {}).items():
            converted_rule = dict(rule)
            if "type" in converted_rule:
                type_str = converted_rule["type"]
                if type_str not in _TYPE_MAP:
                    raise ValueError(
                        f"Unknown type '{type_str}' in config for field '{field}'"
                    )
                converted_rule["type"] = _TYPE_MAP[type_str]
            rules[field] = converted_rule

        policies = []
        for p in cfg.get("policies", []):
            policies.append(
                {
                    "name": p["name"],
                    "check": get_policy(p["name"]),
                    "reason": p["reason"],
                }
            )

        assertions = []
        for a in cfg.get("assertions", []):
            assertions.append(
                {
                    "name": a["name"],
                    "check": get_assertion(a["name"]),
                    "failure": a["failure"],
                }
            )

        tools[tool_name] = {
            "required": cfg.get("required", []),
            "rules": rules,
            "policies": policies,
            "dependencies": cfg.get("dependencies", []),
            "assertions": assertions,
        }

    return tools
