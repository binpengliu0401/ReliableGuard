import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.graph.state import AgentState, ToolCallInfo, TraceEntry
from src.reliableguard.pipeline import run_reliability_pipeline

# ecommerce runtime
from src.domain.ecommerce.tools import tools as ecommerce_tools
from src.domain.ecommerce.tools import TOOL_REGISTRY as ECOMMERCE_TOOL_REGISTRY


load_dotenv()


def _get_client(config):
    api_key = os.getenv("OPENROUTER_API_KEY")
    return OpenAI(api_key=api_key, base_url=config.llm_base_url)


def _trace(state: AgentState, node: str, event: str, detail: str) -> None:
    entry: TraceEntry = {"node": node, "event": event, "detail": detail}
    state["trace"].append(entry)
    print(f"[{node.upper()}] {event} - {detail}")


def _get_domain_resources(domain: str):
    if domain == "ecommerce":
        return {
            "tools": ecommerce_tools,
            "tool_registry": ECOMMERCE_TOOL_REGISTRY,
        }

    if domain == "reference":
        from src.domain.reference.tools import tools, TOOL_REGISTRY

        return {
            "tools": tools,
            "tool_registry": TOOL_REGISTRY,
        }

    raise ValueError(f"Unsupported domain: {domain}")


def _prepare_execution_context(state: AgentState) -> None:
    domain = state["domain"]
    if domain == "reference":
        from src.domain.reference.tools import init_reference_db

        state["verifier_context"] = init_reference_db()
    else:
        state["verifier_context"] = None


def _accumulate_usage(state: AgentState, response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    state["prompt_tokens"] = state.get("prompt_tokens", 0) + prompt_tokens
    state["completion_tokens"] = state.get("completion_tokens", 0) + completion_tokens
    state["total_tokens"] = state.get("total_tokens", 0) + total_tokens


def _first_user_query(state: AgentState) -> str:
    for message in state["messages"]:
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def plan_node(state: AgentState) -> AgentState:
    config = state["config"]
    client = _get_client(config)

    domain_resources = _get_domain_resources(state["domain"])
    domain_tools = domain_resources["tools"]

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=state["messages"],
        tools=domain_tools,  # type: ignore[arg-type]
        tool_choice="auto",
    )
    _accumulate_usage(state, response)

    msg = response.choices[0].message
    state["messages"].append(msg)

    tool_calls = msg.tool_calls
    if not tool_calls:
        state["tool_call"] = None
        state["final_answer"] = msg.content
        _trace(state, "plan_node", "COMPLETED", msg.content or "no further tool calls")
        return state

    tc = tool_calls[0]
    state["tool_call"] = ToolCallInfo(
        tool_call_id=tc.id,
        func_name=tc.function.name,  # type: ignore[union-attr]
        func_args=json.loads(tc.function.arguments),  # type: ignore[union-attr]
    )

    _trace(
        state,
        "plan_node",
        "TOOL_CALL",
        f"{tc.function.name}({state['tool_call']['func_args']})",  # type: ignore[union-attr]
    )
    return state


def execute_node(state: AgentState) -> AgentState:
    tc = state["tool_call"]
    func_name = tc["func_name"]  # type: ignore[index]
    func_args = tc["func_args"]  # type: ignore[index]
    domain = state["domain"]

    domain_resources = _get_domain_resources(domain)
    tool_registry = domain_resources["tool_registry"]

    result = tool_registry.get(
        func_name,
        lambda **kw: {"error": f"unknown tool: {func_name}"},
    )(**func_args)

    state["executed_tools"] = state.get("executed_tools", []) + [func_name]

    _trace(state, "execute_node", "EXECUTED", f"{func_name} - {result}")

    state["messages"].append(
        {
            "role": "tool",
            "tool_call_id": tc["tool_call_id"],  # type: ignore[index]
            "content": json.dumps(result, ensure_ascii=False),
        }
    )

    return state


def reliability_node(state: AgentState) -> AgentState:
    config = state["config"]
    answer = state.get("final_answer") or ""
    report = run_reliability_pipeline(
        state["domain"],
        _first_user_query(state),
        answer,
        model=config.llm_model,
        base_url=config.llm_base_url,
        write_logs=True,
        run_stamp=state.get("run_stamp"),
    )
    state["reliability_report"] = report.model_dump()
    state["reliability_verdict_audit"] = report.verdict
    state["reliability_verdict"] = report.verdict if config.enforce_intervention else "PASS"
    state["reliability_score"] = report.reliability_score
    _trace(
        state,
        "reliability_node",
        state["reliability_verdict"] or report.verdict,
        f"score={report.reliability_score:.2f}",
    )
    return state
