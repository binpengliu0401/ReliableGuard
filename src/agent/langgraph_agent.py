from dotenv import load_dotenv
from mistralai.models import UserMessage
from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.nodes import (
    plan_node,
    gate_node,
    execute_node,
    verify_node,
    recovery_node,
)
from src.graph.edges import after_plan, after_gate, after_verify, after_recovery

load_dotenv()


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan", plan_node)
    graph.add_node("gate", gate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("recovery", recovery_node)

    graph.set_entry_point("plan")

    graph.add_conditional_edges("plan", after_plan, {"gate": "gate", "end": END})
    graph.add_conditional_edges(
        "gate", after_gate, {"execute": "execute", "recovery": "recovery"}
    )
    graph.add_edge("execute", "verify")
    graph.add_conditional_edges(
        "verify", after_verify, {"recovery": "recovery", "end": END}
    )
    graph.add_conditional_edges(
        "recovery", after_recovery, {"plan": "plan", "end": END}
    )

    return graph.compile()


def run_agent(msg: str) -> dict:
    print(f"\n{'='*50}")
    print(f"[INPUT]    {msg}")

    initial_state: AgentState = {
        "messages": [UserMessage(content=msg)],
        "tool_call": None,
        "gate_status": None,
        "gate_detail": None,
        "verifier_status": None,
        "verifier_detail": None,
        "recovery_action": None,
        "recovery_detail": None,
        "retry_count": 0,
        "trace": [],
        "final_answer": None,
        "snapshot_before": None,
        "diff": None,
    } # type: ignore

    app = build_graph()
    final_state = app.invoke(initial_state)

    return final_state
