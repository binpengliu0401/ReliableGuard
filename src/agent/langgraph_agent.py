from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.edges import after_plan, after_gate, after_verify, after_recovery
from src.config.ablation_config import AblationConfig, VERSIONS
from src.graph.nodes import (
    plan_node,
    gate_node,
    execute_node,
    verify_node,
    recovery_node,
)

load_dotenv()


def build_graph(config: AblationConfig = VERSIONS["V4_Full"], client=None):

    graph = StateGraph(AgentState)

    # 始终注册所有节点
    graph.add_node("plan", plan_node)
    graph.add_node("gate", gate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("recovery", recovery_node)

    graph.set_entry_point("plan")

    # plan → gate or execute or end
    def after_plan(state: AgentState) -> str:
        if state.get("tool_call") is None:
            return "end"
        return "gate" if config.use_gate else "execute"

    graph.add_conditional_edges(
        "plan",
        after_plan,
        {"gate": "gate", "execute": "execute", "end": END},
    )

    # gate → execute or recovery or end
    def after_gate(state: AgentState) -> str:
        if state.get("gate_status") == "BLOCKED":
            return "recovery" if config.use_recovery else "end"
        return "execute"

    graph.add_conditional_edges(
        "gate",
        after_gate,
        {"execute": "execute", "recovery": "recovery", "end": END},
    )

    # execute → verify or end
    def after_execute(state: AgentState) -> str:
        return "verify" if config.use_verifier else "end"

    graph.add_conditional_edges(
        "execute",
        after_execute,
        {"verify": "verify", "end": END},
    )

    # verify → recovery or end
    def after_verify(state: AgentState) -> str:
        if state.get("verifier_status") == "FAILED":
            return "recovery" if config.use_recovery else "end"
        return "end"

    graph.add_conditional_edges(
        "verify",
        after_verify,
        {"recovery": "recovery", "end": END},
    )

    # recovery → plan or end
    def after_recovery(state: AgentState) -> str:
        action = state.get("recovery_action")
        if action == "retry":
            if state.get("retry_count", 0) >= MAX_RETRIES:  # type: ignore
                return "end"
            return "plan"
        return "end"

    graph.add_conditional_edges(
        "recovery",
        after_recovery,
        {"plan": "plan", "end": END},
    )

    return graph.compile()


def run_agent(msg: str, config: AblationConfig = VERSIONS["V4_Full"]) -> dict:
    print(f"\n{'='*50}")
    print(f"[INPUT]    {msg}")

    import os
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=config.llm_base_url,
    )

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": msg}],
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
        "executed_tools": [],
        "config": config,
    }  # type: ignore

    app = build_graph(config)
    final_state = app.invoke(initial_state)

    return final_state
