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
    messages: list[Any]
    tool_call: Optional[ToolCallInfo]

    gate_status: Optional[str]
    gate_detail: Optional[str]
    gate_category: Optional[str]

    verifier_status: Optional[str]
    verifier_verdict: Optional[str]
    verifier_detail: Optional[str]

    recovery_action: Optional[str]
    recovery_detail: Optional[str]

    retry_count: int
    trace: list[TraceEntry]
    final_answer: Optional[str]

    snapshot_before: Any
    snapshot_after: Any
    diff: Any
    executed_tools: list[str]

    config: Any

    # new fields
    domain: str
    tool_config: dict
    verifier_context: Any
    inject_false_success: bool
