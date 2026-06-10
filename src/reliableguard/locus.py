"""Locus annotator (Phase 2 step 13).

Assigns the primary failure locus for one trajectory based on the rule-based hierarchy described in
docs/tau_bench_experiment_design.md (Locus taxonomy section). Used in the Phase 3 monitor pass to
tag each reward-0 trajectory for per-locus detection stats (RQ2).

tau-bench does NOT expose a structured native fault type: RewardResult carries only `reward` (0/1)
and `r_actions` (action-match fraction). The annotator is therefore entirely rule-based. The
`override` parameter accepts a manually supplied locus for annotation studies (e.g. a human-reviewed
spot-check sample) to validate that the rule-based residual label "intent-local" is not circular --
see the design doc note on independent annotation.

Priority (highest wins):
  1. pass         — gold_reward >= 1.0; no failure to explain
  2. trace-local  — verify_trace found at least one policy violation in tool_trace
  3. state-local  — state channel found at least one "contradicted" result in structural_results
  4. intent-local — reward < 1.0 but no observable channel reached the failure (working label;
                    requires independent spot-check validation before use in RQ3 claims)

`evidence-local` and `answer-local` are defined loci (see locus_is_monitor_detectable) but are not
assigned by the current rule-based logic: the evidence channel is Phase 2+ stretch, and V_answer
produces only "unverifiable" (it has no external oracle). They are reachable via `override`.
"""

from __future__ import annotations

from typing import Literal

from src.reliableguard.schema import TraceViolation, VerificationResult

Locus = Literal[
    "pass",
    "trace-local",
    "state-local",
    "evidence-local",
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
    override: Locus | None = None,
) -> Locus:
    """Return the primary failure locus for one trajectory.

    `violations`         — output of `verify_trace` (trace channel, V_structural context).
    `structural_results` — per-claim `VerificationResult` dict from V_structural verify_claims.
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
    return "intent-local"


def locus_is_monitor_detectable(locus: Locus) -> bool:
    """True iff a monitor config (V_structural or better) can detect a failure at this locus.

    "pass" is not a failure; "intent-local" is undetectable by any black-box observable channel.
    """
    return locus in {"trace-local", "state-local", "evidence-local", "answer-local"}


def locus_needs_structural(locus: Locus) -> bool:
    """True iff detection requires V_structural (not V_answer alone).

    V_answer has no external oracle (all results are "unverifiable"), so trace-local and
    state-local failures are invisible to it -- the V_structural vs V_answer lift (RQ2) comes
    entirely from these two loci.
    """
    return locus in {"trace-local", "state-local"}
