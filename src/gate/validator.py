from dataclasses import dataclass


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

    config = tool_config[func_name]

    # 1. required fields
    for field in config.get("required", []):
        if field not in func_args:
            return GateResult(
                allowed=False,
                category="SCHEMA_VIOLATION",
                subtype="MISSING_REQUIRED_FIELD",
                reason=f"missing required field: {field}",
            )

    # 2. field rules
    for field, rules in config.get("rules", {}).items():
        if field not in func_args:
            continue

        value = func_args[field]

        if "type" in rules:
            expected_type = rules["type"]
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                return GateResult(
                    allowed=False,
                    category="SCHEMA_VIOLATION",
                    subtype="TYPE_MISMATCH",
                    reason=(
                        f"field '{field}' must be {expected_type.__name__}, "
                        f"got {type(func_args[field]).__name__}"
                    ),
                )

        if "min" in rules and value < rules["min"]:
            return GateResult(
                allowed=False,
                category="SCHEMA_VIOLATION",
                subtype="VALUE_BELOW_MIN",
                reason=f"field '{field}' must be >= {rules['min']}, got {value}",
            )

        if "max" in rules and value > rules["max"]:
            return GateResult(
                allowed=False,
                category="SCHEMA_VIOLATION",
                subtype="VALUE_ABOVE_MAX",
                reason=f"field '{field}' must be <= {rules['max']}, got {value}",
            )

        if "min_length" in rules:
            if not hasattr(value, "__len__") or len(value) < rules["min_length"]:
                return GateResult(
                    allowed=False,
                    category="SCHEMA_VIOLATION",
                    subtype="LENGTH_BELOW_MIN",
                    reason=(
                        f"field '{field}' length must be >= {rules['min_length']}, "
                        f"got {len(value) if hasattr(value, '__len__') else 'N/A'}"
                    ),
                )

        if "max_length" in rules:
            if not hasattr(value, "__len__") or len(value) > rules["max_length"]:
                return GateResult(
                    allowed=False,
                    category="SCHEMA_VIOLATION",
                    subtype="LENGTH_ABOVE_MAX",
                    reason=(
                        f"field '{field}' length must be <= {rules['max_length']}, "
                        f"got {len(value) if hasattr(value, '__len__') else 'N/A'}"
                    ),
                )

    # 3. dependencies
    for dep in config.get("dependencies", []):
        if dep not in executed_tools:
            return GateResult(
                allowed=False,
                category="DEPENDENCY_VIOLATION",
                subtype="MISSING_PREREQUISITE_TOOL",
                reason=f"'{dep}' must be executed before '{func_name}'",
            )

    # 4. policies
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
