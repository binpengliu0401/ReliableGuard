"""Answer-local completeness check: detect non-completion that is visible in the answer text.

A slice of trajectories the rule-based locus annotator labels `intent-local` are in fact
*answer-local*: the agent never executed the requested action and its own final answer reveals this
by terminating on a substantive, unanswered question ("Do you confirm you'd like to proceed with
this exchange?", "Would you like me to book the new flight?"). The failure ground truth is in the
answer (the agent is still asking permission, hence it has not acted), so it is recoverable from the
answer channel alone -- no oracle needed.

This is a black-box, deterministic check on the concatenated `respond` turns. It does NOT read the
gold annotation. Validated on the captured tau2 matrix (2026-06-17): 89.9% precision separating
intent-local failures from passing trajectories, 0.7% false-alarm rate -- the discriminating step is
excluding polite closers ("Is there anything else I can help with?"), which also end on "?" but on a
completed task.
"""

from __future__ import annotations

import re

# Trailing-question phrases that are mere conversational closers on a *completed* task, not a
# request for the user to authorize an unfinished action. Without this exclusion the terminal-"?"
# signal fires on ~37% of passing trajectories (precision collapses to ~52%); excluding them lifts
# precision to ~90% at <1% false alarm.
_POLITE_CLOSERS = (
    "anything else",
    "is there anything",
    "else i can help",
    "else i can assist",
    "help you with today",
    "can i help you with",
    "further assistance",
    "let me know if",
)

_SENTENCE_SPLIT = re.compile(r"[.!\n]")


def detect_incomplete_answer(answer_text: str | None) -> str | None:
    """Return a reason string if the answer reveals non-completion, else None.

    Fires iff the answer's final sentence is a question (ends with "?") that is NOT a polite closer
    -- i.e. the agent terminated while still asking the user to authorize/clarify an action it had
    not yet performed.
    """
    text = (answer_text or "").strip()
    if not text.endswith("?"):
        return None
    # Isolate the final question sentence (the part the agent left the user on).
    question = None
    for part in reversed(_SENTENCE_SPLIT.split(text)):
        part = part.strip()
        if part.endswith("?"):
            question = part.lower()
            break
    if question is None:
        question = text.lower()
    if any(closer in question for closer in _POLITE_CLOSERS):
        return None
    return f"answer terminates on an unanswered substantive question: {question[:120]!r}"
