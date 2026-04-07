from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TaskSpec:
    """
    Unified task contract across domains.

    This is the minimal task-level object consumed by the runner / harness.
    Domain-specific inputs and assertion targets are stored as dict payloads
    so the core runtime can remain domain-agnostic.
    """

    id: str
    domain: str
    description: str
    input: dict[str, Any]
    expected_outcome: str
    assertion_target: dict[str, Any]
    failure_mode: str
    budget: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSpec:
    """
    Unified tool registration object.

    - schema: used by Gate for schema validation
    - executor: actual callable used to execute the tool
    """

    name: str
    description: str
    schema: dict[str, Any]
    executor: Callable[..., Any]


@dataclass
class VerifyResult:
    """
    Unified verifier output.

    This is intentionally richer than a boolean because:
    - Recovery needs structured evidence
    - Trace logging needs assertion-level details
    - Evaluation may distinguish different verification outcomes
    """

    passed: bool
    status: str
    failed_assertions: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailurePacket:
    """
    Unified failure envelope for cross-domain governance.

    Important design:
    - stage/category are framework-level abstractions
    - subtype/message/evidence preserve domain-specific detail

    Example:
    - ecommerce negative amount:
        stage="gate", category="SCHEMA_VIOLATION", subtype="NEGATIVE_AMOUNT"
    - references author-title mismatch:
        stage="verify", category="VERIFY_FAILED", subtype="AUTHOR_TITLE_MISMATCH"
    """

    stage: str
    category: str
    subtype: str | None
    tool_name: str | None
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False
    repair_hint: str | None = None
