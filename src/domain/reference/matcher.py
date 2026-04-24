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
    """Canonical form: space-separated lowercase tokens, surname last.

    Handles two common input formats:
      "Breiman, L."  -> "l breiman"
      "Leo Breiman"  -> "leo breiman"
    """
    cleaned = re.sub(r"\s+", " ", name.strip().lower())
    if not cleaned:
        return ""
    if "," in cleaned:
        left, right = cleaned.split(",", 1)
        surname = left.strip()
        given_parts = [p.strip(".") for p in right.split() if p.strip(".")]
        return " ".join(given_parts + [surname]).strip()
    return cleaned


def author_overlap(extracted: list[str], canonical: list[str]) -> float:
    """Fraction of canonical authors that fuzzy-match at least one extracted author.

    Uses 0.75 as the per-pair similarity floor. Returns 0.0 when either list is empty.
    This is a soft signal — the caller decides whether to fail or only warn.
    """
    if not canonical or not extracted:
        return 0.0
    norm_ext = [normalize_author(a) for a in extracted]
    matched = 0
    for canon in canonical:
        nc = normalize_author(canon)
        best = max(
            difflib.SequenceMatcher(None, nc, ne).ratio() for ne in norm_ext
        )
        if best >= 0.75:
            matched += 1
    return matched / len(canonical)
