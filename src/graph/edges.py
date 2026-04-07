from src.graph.state import AgentState


def after_plan(state: AgentState) -> str:
    if state.get("tool_call") is None:
        return "end"
    return "gate"


def after_gate(state: AgentState) -> str:
    if state.get("gate_status") == "BLOCKED":
        return "recovery"
    return "execute"


def after_verify(state: AgentState) -> str:
    if state.get("verifier_status") == "FAILED":
        return "recovery"
    return "plan"


def after_recovery(state: AgentState) -> str:
    action = state.get("recovery_action")
    if action == "retry":
        retry_count = state.get("retry_count", 0)
        MAX_RETRIES = 3
        if retry_count >= MAX_RETRIES:
            return "end"
        return "plan"
    return "end"
