from dataclasses import dataclass


@dataclass
class GateResult:
    allowed: bool
    reason: str = ""


def validate(
    func_name: str,
    func_args: dict,
    executed_tools: list[str],
    tool_config: dict,
) -> GateResult:
    if func_name not in tool_config:
        return GateResult(allowed=True, reason="tool not in schema, passthrough")

    schema = tool_config[func_name]

    for field in schema["required"]:
        if field not in func_args:
            return GateResult(allowed=False, reason=f"missing required field: {field}")

    for field, rules in schema["rules"].items():
        if field not in func_args:
            continue
        value = func_args[field]
        try:
            value = rules["type"](value)
        except (ValueError, TypeError):
            return GateResult(
                allowed=False,
                reason=f"field '{field}' must be {rules['type'].__name__}, got {type(value).__name__}",
            )
        if "min" in rules and value < rules["min"]:
            return GateResult(
                allowed=False,
                reason=f"field '{field}' must be >= {rules['min']}, got {value}",
            )
        if "max" in rules and value > rules["max"]:
            return GateResult(
                allowed=False,
                reason=f"field '{field}' must be <= {rules['max']}, got {value}",
            )

    for policy in schema.get("policies", []):
        if policy["condition"](func_args):
            return GateResult(
                allowed=False,
                reason=f"Policy violation: {policy['reason']}",
            )

    for dep in schema.get("dependencies", []):
        if dep not in executed_tools:
            return GateResult(
                allowed=False,
                reason=f"Dependency violation: '{dep}' must be executed before '{func_name}'",
            )

    return GateResult(allowed=True)
