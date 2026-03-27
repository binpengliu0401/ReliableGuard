from typing import Any, Optional
from typing_extensions import TypedDict


class ToolCallInfo(TypedDict):
    tool_call_id: str
    func_name: str
    func_args: dict


class TraceEntry(TypedDict):
    node: str
    event: str
    detail: str


class AgentState(TypedDict):
    # conversation history passed to LLM each turn
    messages: list[Any]

    # parsed tool call from plan_node
    tool_call: Optional[ToolCallInfo]

    # gate decision: "PASSED" | "BLOCKED" | None
    gate_status: Optional[str]
    gate_detail: Optional[str]

    # Verifier decision: "PASSED" | "FAILED" | None
    verifier_status: Optional[str]
    verifier_detail: Optional[str]

    # Recovery decision: "retry" | "rollback" | "terminate" | None
    recovery_action: Optional[str]
    recovery_detail: Optional[str]

    retry_count: int

    # structured trace log
    trace: list[TraceEntry]

    # final answer to surface
    final_answer: Optional[str]

    snapshot_before: Any
    snapshot_after: Any
    diff: Any
    executed_tools: list[str]
    config: Any
