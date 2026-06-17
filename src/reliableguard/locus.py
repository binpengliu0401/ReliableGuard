"""Locus annotator: assign the primary failure locus for one trajectory.

Based on the rule-based hierarchy in docs/tau_bench_experiment_design.md.
Used in the Phase 3 monitor pass to tag each reward-0 trajectory for per-locus
detection stats (RQ2 / RQ3).

tau-bench does NOT expose a structured native fault type: RewardResult carries only
`reward` (0/1). The annotator is therefore entirely rule-based. The `override`
parameter accepts a manually supplied locus for annotation studies.

Priority (highest wins):
  1. pass        — gold_reward >= 1.0; no failure to explain
  2. trace-local — verify_trace found at least one policy violation OR an agent loop in tool_trace
  3. state-local — state channel found "contradicted" with source in _STATE_SOURCES
  4. answer-local — the answer itself reveals non-completion (agent terminated on an unanswered
                    substantive question; see verifier/answer_completeness.detect_incomplete_answer)
  5. intent-local — reward < 1.0 but no observable channel reached the failure
                    (working label; requires independent spot-check validation)

`answer-local` is assigned when `answer_incomplete` is set (a deterministic answer-channel signal
that V_answer's claim verification does not produce on its own). It is also reachable via `override`.

Scope: retail + airline (two formal domains). Banking_knowledge and evidence-local are
out of scope for the formal experiment and documented in the thesis as Future Work.
"""

from __future__ import annotations

from typing import Literal

from src.reliableguard.schema import TraceViolation, VerificationResult

Locus = Literal[
    "pass",
    "trace-local",
    "state-local",
    "answer-local",
    "intent-local",
]

# Sources set by verifiers that use the state channel.
_STATE_SOURCES = {"tau_bench_state"}


def annotate_locus(
    gold_reward: float,
    violations: list[TraceViolation],
    structural_results: dict[str, VerificationResult],
    *,
    answer_incomplete: bool = False,
    override: Locus | None = None,
) -> Locus:
    """Return the primary failure locus for one trajectory.

    `violations`         — output of `verify_trace` (trace channel, V_structural context).
    `structural_results` — per-claim `VerificationResult` dict from V_structural verify_claims.
    `answer_incomplete`  — True if the answer reveals non-completion (answer channel signal).
    `override`           — bypasses rule logic; used for manual annotation / spot-check studies.
    """
    if override is not None:
        return override
    if gold_reward >= 1.0:
        return "pass"
    if violations:
        return "trace-local"
    if any(
        r.evidence_state == "contradicted" and r.source in _STATE_SOURCES
        for r in structural_results.values()
    ):
        return "state-local"
    if answer_incomplete:
        return "answer-local"
    return "intent-local"


def locus_is_monitor_detectable(locus: Locus) -> bool:
    """True iff a monitor config (V_structural or better) can detect a failure at this locus.

    "pass" is not a failure; "intent-local" is undetectable by any black-box observable channel.
    """
    return locus in {"trace-local", "state-local", "answer-local"}


def locus_needs_structural(locus: Locus) -> bool:
    """True iff detection requires V_structural (not V_answer alone).

    V_answer has no external oracle and runs only claim verification (all results "unverifiable"),
    so trace-local, state-local, and the completeness-based answer-local failures are invisible to
    it -- the V_structural vs V_answer lift (RQ2) comes from these loci. (answer-local is in
    principle answer-channel detectable, but our V_answer baseline does not run the completeness
    check, so in this pipeline it too is recovered only by V_structural.)
    """
    return locus in {"trace-local", "state-local", "answer-local"}
