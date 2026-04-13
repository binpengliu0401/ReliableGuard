from dataclasses import dataclass


class SchemaValidator:
    def __init__(self, tool_config: dict):
        self.tool_config = tool_config or {}

    def validate(self, tool_name: str, args: dict) -> dict:
        if tool_name not in self.tool_config:
            return {
                "allowed": False,
                "reason": f"unknown tool: {tool_name}",
            }

        config = self.tool_config[tool_name]
        rules = config.get("rules", {})
        required_fields = config.get("required", [])

        for field_name in required_fields:
            if field_name not in args:
                return {
                    "allowed": False,
                    "reason": f"missing required parameter: {field_name}",
                }

        for field_name, value in args.items():
            if field_name not in rules:
                continue

            rule = rules[field_name]
            declared_type = rule.get("type")

            if declared_type is float:
                if not isinstance(value, (int, float)):
                    return {
                        "allowed": False,
                        "reason": f"parameter '{field_name}' must be float-compatible",
                    }
            elif declared_type is int:
                if not (isinstance(value, int) and not isinstance(value, bool)):
                    return {
                        "allowed": False,
                        "reason": f"parameter '{field_name}' must be int",
                    }
            elif declared_type is str:
                if not isinstance(value, str):
                    return {
                        "allowed": False,
                        "reason": f"parameter '{field_name}' must be str",
                    }
            else:
                return {
                    "allowed": False,
                    "reason": (
                        f"unsupported type '{declared_type}' for parameter "
                        f"'{field_name}'"
                    ),
                }

            if ("min" in rule or "max" in rule) and not isinstance(
                value, (int, float)
            ):
                return {
                    "allowed": False,
                    "reason": (
                        f"parameter '{field_name}' must be numeric for range checks"
                    ),
                }

            if "min" in rule and value < rule["min"]:
                return {
                    "allowed": False,
                    "reason": (
                        f"parameter '{field_name}' must be >= "
                        f"{rule['min']}, got {value}"
                    ),
                }

            if "max" in rule and value > rule["max"]:
                return {
                    "allowed": False,
                    "reason": (
                        f"parameter '{field_name}' must be <= "
                        f"{rule['max']}, got {value}"
                    ),
                }

            if "enum" in rule and value not in rule["enum"]:
                return {
                    "allowed": False,
                    "reason": (
                        f"parameter '{field_name}' must be one of "
                        f"{rule['enum']}, got {value}"
                    ),
                }

        return {"allowed": True}


@dataclass
class GateResult:
    allowed: bool
    category: str | None = None
    subtype: str | None = None
    reason: str = ""


def validate(
    func_name: str,
    func_args: dict,
    executed_tools: list[str],
    tool_config: dict,
    context: dict | None = None,
) -> GateResult:
    if func_name not in tool_config:
        return GateResult(
            allowed=True,
            reason="tool not in config, passthrough",
        )

    schema_result = SchemaValidator(tool_config).validate(func_name, func_args)
    if not schema_result.get("allowed"):
        return GateResult(
            allowed=False,
            category="SCHEMA_VIOLATION",
            subtype="VALIDATION_FAILED",
            reason=schema_result.get("reason", "schema validation failed"),
        )

    config = tool_config[func_name]

    for dep in config.get("dependencies", []):
        if dep not in executed_tools:
            return GateResult(
                allowed=False,
                category="DEPENDENCY_VIOLATION",
                subtype="MISSING_PREREQUISITE_TOOL",
                reason=f"'{dep}' must be executed before '{func_name}'",
            )

    for policy in config.get("policies", []):
        check_fn = policy["check"]
        if check_fn.__code__.co_argcount >= 3:
            ok, policy_reason = check_fn(func_name, func_args, context)
        else:
            ok, policy_reason = check_fn(func_name, func_args)
        if not ok:
            return GateResult(
                allowed=False,
                category="POLICY_VIOLATION",
                subtype=policy["name"],
                reason=policy_reason or f"policy violation: {policy['reason']}",
            )

    return GateResult(
        allowed=True,
        reason="gate passed",
    )
