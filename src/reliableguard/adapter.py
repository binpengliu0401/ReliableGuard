from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.reliableguard.schema import ChannelConfig, Grounding, VerificationContext


class Trajectory(BaseModel):
    """One agent run captured from a benchmark, decoupling the monitor from any single
    benchmark. Carries only deployment-observable artifacts plus run metadata and the gold
    reward; it NEVER carries the goal annotation (tau-bench `task.actions` / `r_actions`),
    which preserves non-circularity. Emitted by the benchmark adapter (Phase 2).

    `state_before` / `state_after` / `tool_trace` must be snapshotted BEFORE the terminal
    `env.step()` runs `calculate_reward()` (which reloads `env.data` to ground truth and
    appends the gold actions to `env.actions`) -- see docs/architecture.md.
    """

    task_id: str
    domain: str
    model: str
    repeat: int = 0
    seed: int | None = None
    query: str = ""
    # `answer_text` is the answer-local channel input: the concatenation of the agent's
    # natural-language `respond` turns (what it told the user), fed to the extractor. It
    # excludes tool calls (the trace channel) -- channel hygiene for the RQ1-vs-RQ2 contrast.
    # `final_answer` keeps only the last respond turn, for demo / reference.
    final_answer: str = ""
    answer_text: str = ""
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    gold_reward: float | None = None
    native_fault: str | None = None
    # `error` marks an infra failure (retries exhausted), excluded from metrics and re-run by
    # resume -- never recorded as a reward-0 task failure (see the run-harness spec).
    status: Literal["ok", "error"] = "ok"

    def grounding(self) -> Grounding:
        return Grounding(
            state_before=self.state_before,
            state_after=self.state_after,
            tool_trace=self.tool_trace,
        )

    def verification_context(self, channels: ChannelConfig) -> VerificationContext:
        """Build the context for one monitor config; the same grounding is reused across the
        V_answer / V_structural / V_evidence channel presets."""
        return VerificationContext(grounding=self.grounding(), channels=channels)
