from typing import Any
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
    tool_call: ToolCallInfo | None

    trace: list[TraceEntry]
    final_answer: str | None
    reliability_report: dict[str, Any] | None
    reliability_verdict: str | None
    reliability_verdict_audit: str | None
    reliability_score: float | None

    executed_tools: list[str]
    config: Any
    domain: str
    verifier_context: Any
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    run_id: str
    run_stamp: str
    run_started_at: str
