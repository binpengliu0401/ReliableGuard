from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.config.ablation_config import AblationConfig, VERSIONS
from src.graph.nodes import (
    plan_node,
    gate_node,
    execute_node,
    verify_node,
    recovery_node,
)

load_dotenv()
_graph_cache: dict = {}


def build_graph(config: AblationConfig = VERSIONS["V4_Full"], client=None):
    cache_key = (
        config.use_gate,
        config.use_verifier,
        config.use_recovery,
        config.llm_model,
    )
    if cache_key in _graph_cache:
        return _graph_cache[cache_key]

    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("plan", plan_node)
    graph.add_node("gate", gate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("recovery", recovery_node)

    graph.set_entry_point("plan")

    # plan → gate or execute or end
    def _after_plan(state: AgentState) -> str:
        if state.get("tool_call") is None:
            return "end"
        return "gate" if config.use_gate else "execute"

    graph.add_conditional_edges(
        "plan",
        _after_plan,
        {"gate": "gate", "execute": "execute", "end": END},
    )

    # gate → execute or recovery or end
    def _after_gate(state: AgentState) -> str:
        if state.get("gate_status") == "BLOCKED":
            return "recovery" if config.use_recovery else "end"
        return "execute"

    graph.add_conditional_edges(
        "gate",
        _after_gate,
        {"execute": "execute", "recovery": "recovery", "end": END},
    )

    # execute → verify or end
    def _after_execute(state: AgentState) -> str:
        return "verify" if config.use_verifier else "end"

    graph.add_conditional_edges(
        "execute",
        _after_execute,
        {"verify": "verify", "end": END},
    )

    # verify → recovery or plan or end
    def _after_verify(state: AgentState) -> str:
        if state.get("verifier_status") == "FAILED":
            return "recovery" if config.use_recovery else "end"
        return "plan"

    graph.add_conditional_edges(
        "verify",
        _after_verify,
        {"recovery": "recovery", "plan": "plan", "end": END},
    )

    compiled = graph.compile()
    _graph_cache[cache_key] = compiled
    return compiled


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
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an autonomous order management agent. "
                    "When the user gives you a multi-step instruction, execute all steps "
                    "sequentially without asking for confirmation between steps. "
                    "Use the available tools to complete the full request."
                ),
            },
            {"role": "user", "content": msg},
        ],
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
