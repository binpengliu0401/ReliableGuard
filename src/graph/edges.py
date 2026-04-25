from src.graph.state import AgentState


def after_plan(state: AgentState) -> str:
    if state.get("tool_call") is None:
        return "reliability"
    return "execute"


def after_execute(state: AgentState) -> str:
    return "plan"

