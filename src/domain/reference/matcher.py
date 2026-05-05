"""
Fuzzy matching utilities for reference verification.

Kept pure (no I/O, no imports from this package) so it can be used by
both tools.py (runtime) and build_real_fixture.py (offline build).
"""

import difflib
import re


def normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def title_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio of two normalized titles. Returns 0.0 if either is empty."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def normalize_author(name: str) -> str:
    """Canonical form for set-based author comparison."""
    return re.sub(r"\s+", " ", name.strip().lower())


def author_overlap(extracted: list[str], canonical: list[str]) -> float:
    """Fraction of claimed authors present in the fixture author list.

    A claimed subset of the complete fixture author list returns 1.0.
    """
    if not canonical or not extracted:
        return 0.0
    claimed = {normalize_author(author) for author in extracted}
    fixture = {normalize_author(author) for author in canonical}
    claimed.discard("")
    fixture.discard("")
    if not claimed or not fixture:
        return 0.0
    return len(claimed & fixture) / len(claimed)
