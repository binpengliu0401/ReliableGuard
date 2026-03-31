import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.graph.state import AgentState, ToolCallInfo, TraceEntry
from src.gate.shcema_validator import validate as gate_validate, GateResult
from src.recovery.failure_classifier import (
    classify_gate_failure,
    classify_verifier_failure,
)
from src.recovery.recovery_controller import BudgetTracker, recover
from src.tools.order_service import (
    tools,
    create_order,
    get_order_status,
    confirm_order,
    refund_order,
    cursor,
)
from src.config.tool_config import MAX_RETRIES
from src.verifier.verifier import verify
from src.verifier.state_tracker import take_snapshot, compute_diff

load_dotenv()


def _get_client(config):

    api_key = os.getenv("OPENROUTER_API_KEY")

    return OpenAI(api_key=api_key, base_url=config.llm_base_url)


def _trace(state: AgentState, node: str, event: str, detail: str) -> None:
    entry: TraceEntry = {"node": node, "event": event, "detail": detail}
    state["trace"].append(entry)
    print(f"[{node.upper()}] {event} - {detail}")


def plan_node(state: AgentState) -> AgentState:
    config = state["config"]
    client = _get_client(config)

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=state["messages"],
        tools=tools,  # type: ignore
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
    gate_result = gate_validate(tc["func_name"], tc["func_args"], executed_tools)  # type: ignore

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

    state["snapshot_before"] = take_snapshot(cursor)

    if func_name == "create_order":
        result = create_order(**func_args)
    elif func_name == "get_order_status":
        result = get_order_status(**func_args)
    elif func_name == "confirm_order":
        result = confirm_order(**func_args)
    elif func_name == "refund_order":
        result = refund_order(**func_args)
    else:
        result = {"error": f"unknown tool: {func_name}"}

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
    config = state["config"]
    client = _get_client(config)

    tc = state["tool_call"]
    snapshot_after = take_snapshot(cursor)
    diff = compute_diff(state["snapshot_before"], snapshot_after)
    verifier_result = verify(tc["func_name"], tc["func_args"], diff)  # type: ignore

    if verifier_result.passed:
        state["verifier_status"] = "PASSED"
        state["verifier_detail"] = verifier_result.evidence
        _trace(state, "verify_node", "PASSED", verifier_result.evidence)

    else:
        state["verifier_status"] = "FAILED"
        state["verifier_detail"] = verifier_result.evidence
        _trace(state, "verify_node", "FAILED", verifier_result.evidence)
        state["diff"] = diff

    return state


def recovery_node(state: AgentState) -> AgentState:
    config = state["config"]
    client = _get_client(config)

    budget = BudgetTracker(max_retries=MAX_RETRIES)
    budget.retry_count = state["retry_count"]

    if state["gate_status"] == "BLOCKED":
        gate_result = GateResult(allowed=False, reason=state["gate_detail"])  # type: ignore
        failure = classify_gate_failure(gate_result, state["tool_call"]["func_name"])  # type: ignore
    else:
        from src.verifier.verifier import VerifierResult

        verifier_result = VerifierResult(
            passed=False,
            verdict=state["verifier_status"],  # type: ignore
            evidence=state["verifier_detail"],  # type: ignore
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
