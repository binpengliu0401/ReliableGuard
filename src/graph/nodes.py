import ast
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


def _completion_options(config) -> dict:
    options = {"temperature": config.llm_temperature}
    if config.llm_seed is not None:
        options["seed"] = config.llm_seed
    return options


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


def _parse_tool_arguments(raw_arguments: str | None) -> dict:
    if not raw_arguments:
        return {}

    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        repaired_arguments = _repair_json_closing_delimiters(raw_arguments)
        if repaired_arguments != raw_arguments:
            try:
                parsed = json.loads(repaired_arguments)
                return parsed if isinstance(parsed, dict) else {
                    "_argument_parse_error": raw_arguments
                }
            except json.JSONDecodeError:
                pass
        try:
            parsed = ast.literal_eval(raw_arguments)
        except (SyntaxError, ValueError):
            return {"_argument_parse_error": raw_arguments}

    return parsed if isinstance(parsed, dict) else {"_argument_parse_error": raw_arguments}


def _repair_json_closing_delimiters(raw_arguments: str) -> str:
    stripped = raw_arguments.strip()
    if not stripped:
        return raw_arguments

    repaired = stripped
    bracket_delta = stripped.count("[") - stripped.count("]")
    brace_delta = stripped.count("{") - stripped.count("}")
    if bracket_delta > 0:
        repaired += "]" * bracket_delta
    if brace_delta > 0:
        repaired += "}" * brace_delta
    return repaired


def _assistant_message_from_response(msg, parsed_args: dict | None = None) -> dict:
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return {"role": "assistant", "content": msg.content}

    sanitized_tool_calls = []
    for index, tool_call in enumerate(tool_calls):
        arguments = tool_call.function.arguments
        if index == 0 and parsed_args is not None:
            arguments = json.dumps(parsed_args, ensure_ascii=False)
        else:
            arguments = json.dumps(_parse_tool_arguments(arguments), ensure_ascii=False)
        sanitized_tool_calls.append(
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": arguments,
                },
            }
        )

    return {
        "role": "assistant",
        "content": msg.content,
        "tool_calls": sanitized_tool_calls,
    }


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
        **_completion_options(config),
    )
    _accumulate_usage(state, response)

    msg = response.choices[0].message
    tool_calls = msg.tool_calls
    if not tool_calls:
        state["messages"].append(_assistant_message_from_response(msg))
        state["tool_call"] = None
        state["final_answer"] = msg.content
        _trace(state, "plan_node", "COMPLETED", msg.content or "no further tool calls")
        return state

    tc = tool_calls[0]
    func_args = _parse_tool_arguments(tc.function.arguments)  # type: ignore[union-attr]
    state["messages"].append(_assistant_message_from_response(msg, func_args))
    state["tool_call"] = ToolCallInfo(
        tool_call_id=tc.id,
        func_name=tc.function.name,  # type: ignore[union-attr]
        func_args=func_args,
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

    if "_argument_parse_error" in func_args:
        result = {
            "error": "tool argument parse error",
            "raw_arguments": func_args["_argument_parse_error"],
        }
    else:
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
        temperature=config.llm_temperature,
        seed=config.llm_seed,
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
