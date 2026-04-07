import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.graph.state import AgentState, ToolCallInfo, TraceEntry
from src.gate.validator import validate as gate_validate, GateResult
from src.recovery.failure_classifier import (
    classify_gate_failure,
    classify_verifier_failure,
)
from src.recovery.recovery_controller import BudgetTracker, recover
from src.verifier.verifier import verify

from src.domain.loader import load_tool_config

# register decorators
import src.domain.ecommerce.policies
import src.domain.ecommerce.assertions
import src.domain.reference.policies
import src.domain.reference.assertions

# ecommerce runtime
from src.tools.order_service import tools as ecommerce_tools
from src.tools.order_service import TOOL_REGISTRY as ECOMMERCE_TOOL_REGISTRY
from src.tools.order_service import cursor as ecommerce_cursor
from src.verifier.ecommerce_state_tracker import (
    take_snapshot as ecommerce_take_snapshot,
    compute_diff as ecommerce_compute_diff,
)


MAX_RETRIES = 3
load_dotenv()

_ECOMMERCE_TOOL_CONFIG = load_tool_config(
    Path(__file__).parent.parent / "domain" / "ecommerce" / "config.yaml"
)

_REFERENCE_TOOL_CONFIG = load_tool_config(
    Path(__file__).parent.parent / "domain" / "reference" / "config.yaml"
)


def _get_client(config):
    api_key = os.getenv("LLM_API_KEY")
    return OpenAI(api_key=api_key, base_url=config.llm_base_url)


def _trace(state: AgentState, node: str, event: str, detail: str) -> None:
    entry: TraceEntry = {"node": node, "event": event, "detail": detail}
    state["trace"].append(entry)
    print(f"[{node.upper()}] {event} - {detail}")


def _get_domain_resources(domain: str):
    if domain == "ecommerce":
        return {
            "tool_config": _ECOMMERCE_TOOL_CONFIG,
            "tools": ecommerce_tools,
            "tool_registry": ECOMMERCE_TOOL_REGISTRY,
        }

    if domain == "reference":
        from src.tools.reference_service import tools, TOOL_REGISTRY

        return {
            "tool_config": _REFERENCE_TOOL_CONFIG,
            "tools": tools,
            "tool_registry": TOOL_REGISTRY,
        }

    raise ValueError(f"Unsupported domain: {domain}")


def _prepare_execution_context(state: AgentState) -> None:
    domain = state["domain"]

    if domain == "ecommerce":
        state["verifier_context"] = None
        state["tool_config"] = _ECOMMERCE_TOOL_CONFIG
        return

    if domain == "reference":
        from src.tools.reference_service import init_reference_db

        conn = init_reference_db()
        state["verifier_context"] = conn
        state["tool_config"] = _REFERENCE_TOOL_CONFIG
        return

    raise ValueError(f"Unsupported domain: {domain}")


def plan_node(state: AgentState) -> AgentState:
    config = state["config"]
    client = _get_client(config)

    domain_resources = _get_domain_resources(state["domain"])
    domain_tools = domain_resources["tools"]

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=state["messages"],
        tools=domain_tools,  # type: ignore
        tool_choice="auto",
    )

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
        func_name=tc.function.name,  # type: ignore
        func_args=json.loads(tc.function.arguments),  # type: ignore
    )

    _trace(
        state,
        "plan_node",
        "TOOL_CALL",
        f"{tc.function.name}({state['tool_call']['func_args']})",  # type: ignore
    )
    return state


def gate_node(state: AgentState) -> AgentState:
    tc = state["tool_call"]
    executed_tools = state.get("executed_tools", [])

    tool_config = state["tool_config"]
    gate_result = gate_validate(
        tc["func_name"], tc["func_args"], executed_tools, tool_config  # type: ignore
    )

    if gate_result.allowed:
        state["gate_status"] = "PASSED"
        state["gate_detail"] = gate_result.reason
        _trace(state, "gate_node", "PASSED", f"args={tc['func_args']}")  # type: ignore
    else:
        state["gate_status"] = "BLOCKED"
        state["gate_detail"] = gate_result.reason
        _trace(state, "gate_node", "BLOCKED", gate_result.reason)

    return state


def execute_node(state: AgentState) -> AgentState:
    tc = state["tool_call"]
    func_name = tc["func_name"]  # type: ignore
    func_args = tc["func_args"]  # type: ignore
    domain = state["domain"]

    domain_resources = _get_domain_resources(domain)
    tool_registry = domain_resources["tool_registry"]

    if domain == "ecommerce":
        state["snapshot_before"] = ecommerce_take_snapshot(ecommerce_cursor)
    else:
        state["snapshot_before"] = None

    result = tool_registry.get(
        func_name,
        lambda **kw: {"error": f"unknown tool: {func_name}"},
    )(**func_args)

    state["executed_tools"] = state.get("executed_tools", []) + [func_name]

    _trace(state, "execute_node", "EXECUTED", f"{func_name} - {result}")

    state["messages"].append(
        {
            "role": "tool",
            "tool_call_id": tc["tool_call_id"],  # type: ignore
            "content": json.dumps(result),
        }
    )

    return state


def verify_node(state: AgentState) -> AgentState:
    tc = state["tool_call"]
    domain = state["domain"]
    tool_config = state["tool_config"]

    if domain == "ecommerce":
        snapshot_after = ecommerce_take_snapshot(ecommerce_cursor)
        diff = ecommerce_compute_diff(state["snapshot_before"], snapshot_after)
        state["diff"] = diff

        verifier_result = verify(
            func_name=tc["func_name"],  # type: ignore
            func_args=tc["func_args"],  # type: ignore
            tool_config=tool_config,
            diff=diff,
        )
    else:
        verifier_result = verify(
            func_name=tc["func_name"],  # type: ignore
            func_args=tc["func_args"],  # type: ignore
            tool_config=tool_config,
            context=state["verifier_context"],
        )

    if verifier_result.passed:
        state["verifier_status"] = "PASSED"
        state["verifier_detail"] = verifier_result.evidence
        _trace(state, "verify_node", "PASSED", verifier_result.evidence)
    else:
        state["verifier_status"] = "FAILED"
        state["verifier_detail"] = verifier_result.evidence
        _trace(state, "verify_node", "FAILED", verifier_result.evidence)

    return state


def recovery_node(state: AgentState) -> AgentState:
    config = state["config"]
    client = _get_client(config)

    budget = BudgetTracker(max_retries=MAX_RETRIES)
    budget.retry_count = state["retry_count"]

    if state["gate_status"] == "BLOCKED":
        gate_result = GateResult(
            allowed=False,
            reason=state["gate_detail"],  # type: ignore
        )
        failure = classify_gate_failure(gate_result, state["tool_call"]["func_name"])  # type: ignore
    else:
        from src.verifier.verifier import VerifierResult

        verifier_result = VerifierResult(
            passed=False,
            verdict=state["verifier_status"],  # type: ignore
            evidence=state["verifier_detail"],  # type: ignore
            failed_assertions=[],
        )
        failure = classify_verifier_failure(verifier_result)

    recovery_result = recover(failure, diff=state.get("diff"), budget=budget)

    state["recovery_action"] = recovery_result.action.value
    state["recovery_detail"] = recovery_result.detail
    _trace(
        state,
        "recovery_node",
        recovery_result.action.value.upper(),
        recovery_result.detail,
    )

    if recovery_result.action.value == "retry":
        state["retry_count"] += 1
        state["messages"].append(
            {
                "role": "user",
                "content": (
                    f"[SYSTEM RECOVERY] Previous attempt failed: {recovery_result.detail}. "
                    f"Please try again with corrected parameters."
                ),
            }
        )

    elif recovery_result.action.value == "rollback":
        clean_messages = [
            m
            for m in state["messages"]
            if not (hasattr(m, "tool_calls") and m.tool_calls)
            and not (isinstance(m, dict) and m.get("role") == "tool")
        ]
        rollback_prompt = clean_messages + [
            {
                "role": "user",
                "content": (
                    f"The system detected an invalid operation and has rolled it back. "
                    f"Reason: {recovery_result.detail}. "
                    f"Please explain this to the user clearly and concisely. "
                    f"Do not suggest any workaround that bypasses this constraint."
                ),
            }
        ]
        final = client.chat.completions.create(
            model=config.llm_model,
            messages=rollback_prompt,  # type: ignore
        )
        state["final_answer"] = final.choices[0].message.content
        _trace(state, "recovery_node", "FINAL_ANSWER", state["final_answer"])  # type: ignore

    elif recovery_result.action.value == "terminate":
        clean_messages = [
            m
            for m in state["messages"]
            if not (hasattr(m, "tool_calls") and m.tool_calls)
            and not (isinstance(m, dict) and m.get("role") == "tool")
        ]
        rejection_prompt = clean_messages + [
            {
                "role": "user",
                "content": (
                    f"The system has rejected this request. Reason: {recovery_result.detail}. "
                    f"Please explain this to the user in a helpful and concise way. "
                    f"Do not suggest any workaround that bypasses this constraint."
                ),
            }
        ]
        final = client.chat.completions.create(
            model=config.llm_model,
            messages=rejection_prompt,  # type: ignore
        )
        state["final_answer"] = final.choices[0].message.content
        _trace(state, "recovery_node", "FINAL_ANSWER", state["final_answer"])  # type: ignore

    return state
