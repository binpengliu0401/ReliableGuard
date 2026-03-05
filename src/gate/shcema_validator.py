from dataclasses import dataclass


@dataclass
class GateResult:
    allowed: bool
    reason: str = ""


# Define the defination of every tool's schema rule
TOOL_SCHEMAS = {
    "create_order": {
        "required": ["amount"],
        "rules": {
            "amount": {
                "type": float,
                "min": 0.01,
                "max": 10000,
            }
        },
        "policies": [
            {
                "condition": lambda args: args.get("amount", 0) > 5000, 
                "reason": "amount exceeds 5000, requires approval before order creation"
            }
        ]
    },
    "get_order_status": {
        "required": ["order_id"],
        "rules": {
            "order_id": {
                "type": int,
                "min": 1,
            }
        },
        "dependencies": ["create_order"]
    },
}


def validate(func_name: str, func_args: dict, executed_tools: list[str] = []) -> GateResult:
    # If tool does not in schema defination, pass
    if func_name not in TOOL_SCHEMAS:
        return GateResult(allowed=True, reason="tools not in schema, passthrough")

    schema = TOOL_SCHEMAS[func_name]

    # check necessary parameters
    for field in schema["required"]:
        if field not in func_args:
            return GateResult(allowed=False, reason=f"missing required field: {field}")

    # check every necessary parameter's rule, skip unnecessary paramaters
    for field, rules in schema["rules"].items():
        if field not in func_args:
            continue

        value = func_args[field]

        # check data type
        try:
            value = rules["type"](value)
        except (ValueError, TypeError):
            return GateResult(
                allowed=False,
                reason=f"field'{field}' must be {rules['type'].__name__}, got {type(value).__name__}",
            )
            
        # check minimum value range
        if "min" in rules and value < rules["min"]:
            return GateResult(
                allowed=False,
                reason=f"field '{field}' must be >= {rules["min"]}, got {value}",
            )

        # check maximum value range
        if "max" in rules and value > rules["max"]:
            return GateResult(
                allowed=False,
                reason=f"field  '{field}' must be <= {rules["max"]}, got {value}",
            )

    # policies verify
    for policy in schema.get("policies", []):
        if policy["condition"](func_args):
            return GateResult(
                allowed=False,
                reason=f"Policy violation: {policy['reason']}"
            )
    # dependices verify
    for dep in schema.get("dependencies", []):
        if dep not in executed_tools:
            return GateResult(
                allowed=False,
                reason=f"Dependency violation: '{dep}' must be executed before '{func_name}'"
            )

    return GateResult(allowed=True)
