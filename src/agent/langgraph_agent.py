from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from src.config.runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig
from src.graph.edges import after_execute, after_plan
from src.graph.nodes import execute_node, plan_node, reliability_node
from src.graph.state import AgentState
from src.reliableguard.trace.artifacts import build_run_id, make_run_stamp


load_dotenv()
_graph_cache: dict = {}


def build_graph(config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG, client=None):
    cache_key = (config.use_verifier, config.enforce_intervention, config.llm_model)
    if cache_key in _graph_cache:
        return _graph_cache[cache_key]

    graph = StateGraph(AgentState)

    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("reliability", reliability_node)

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        lambda state: after_plan(state)
        if config.use_verifier
        else ("end" if state.get("tool_call") is None else "execute"),
        {"execute": "execute", "reliability": "reliability", "end": END},
    )
    graph.add_conditional_edges("execute", after_execute, {"plan": "plan"})
    graph.add_edge("reliability", END)

    compiled = graph.compile()
    _graph_cache[cache_key] = compiled
    return compiled


def _build_system_prompt(domain: str) -> str:
    if domain == "ecommerce":
        return (
            "You are an autonomous order management agent. "
            "Use available tools for operational data. "
            "When you give the final answer, be concise and include concrete order ids, "
            "amounts, statuses, and tool results when available."
        )

    if domain == "reference":
        return (
            "You are an autonomous academic reference verification agent. "
            "Use the available tools to parse PDFs, list references, and verify metadata. "
            "When you give the final answer, be concise and include concrete paper ids, "
            "reference ids, DOI statuses, titles, journals, years, and authors when available."
        )

    raise ValueError(f"Unsupported domain: {domain}")


def run_agent(
    msg: str,
    *,
    domain: str = "ecommerce",
    config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
    run_stamp: str | None = None,
) -> dict:
    resolved_run_stamp = run_stamp or make_run_stamp()
    run_id = build_run_id(domain, resolved_run_stamp)
    print(f"\n{'='*50}")
    print(f"[DOMAIN]   {domain}")
    print(f"[RUN_ID]   {run_id}")
    print(f"[INPUT]    {msg}")

    initial_state: AgentState = {
        "messages": [
            {
                "role": "system",
                "content": _build_system_prompt(domain),
            },
            {"role": "user", "content": msg},
        ],
        "tool_call": None,
        "trace": [],
        "final_answer": None,
        "reliability_report": None,
        "reliability_verdict": None,
        "reliability_verdict_audit": None,
        "reliability_score": None,
        "executed_tools": [],
        "config": config,
        "domain": domain,
        "verifier_context": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "run_id": run_id,
        "run_stamp": resolved_run_stamp,
        "run_started_at": resolved_run_stamp,
    }

    from src.graph.nodes import _prepare_execution_context

    _prepare_execution_context(initial_state)

    app = build_graph(config)
    final_state = app.invoke(initial_state)

    if final_state.get("verifier_context") is not None:
        try:
            final_state["verifier_context"].close()
        except Exception:
            pass

    return final_state
