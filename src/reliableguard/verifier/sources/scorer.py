from __future__ import annotations

import difflib
import re
from typing import Any

from src.domain.reference.api_client import normalize_doi
from src.reliableguard.schema import Claim, VerificationResult
from src.reliableguard.verifier.sources.base import Evidence


def verification_from_evidence(
    claim: Claim,
    evidence: list[Evidence],
    *,
    default_source: str = "configured_sources",
) -> VerificationResult | None:
    material = [item for item in evidence if item.found]
    if not material:
        if evidence:
            # Configured sources were consulted (online) and positively reported no
            # matching evidence.
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="not_found",
                evidence_value=[item.to_dict() for item in evidence],
                source=default_source,
                source_mode="not_found",
                confidence=0.0,
                reason="Configured verifier sources returned no matching evidence.",
            )
        return None

    scored = [(item, _score_claim_evidence(claim, item)) for item in material]
    best, score = max(scored, key=lambda pair: pair[1]["overall"])
    diagnostic = _diagnostic(score)
    evidence_value = best.to_dict()
    evidence_value["diagnostic"] = diagnostic
    evidence_value["scores"] = score

    if diagnostic == "metadata_mismatch":
        evidence_state = "contradicted"
    elif diagnostic in {"source_supported", "needs_correction"}:
        evidence_state = "supported"
    else:
        evidence_state = "unverifiable"

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state=evidence_state,
        evidence_value=evidence_value,
        source=best.source,
        source_mode="fixture",
        confidence=round(float(score["overall"]), 3),
        reason=(
            f"Configured source diagnostic={diagnostic}; "
            f"title={score['title']:.3f}, authors={score['authors']:.3f}, "
            f"year_match={score['year_match']}, doi_match={score['doi_match']}, "
            f"url_match={score['url_match']}."
        ),
    )


def _score_claim_evidence(claim: Claim, evidence: Evidence) -> dict[str, Any]:
    title = _claim_title(claim)
    authors = _claim_authors(claim)
    year = _claim_year(claim)
    doi = _claim_doi(claim)
    url = _claim_url(claim)

    title_score = _similarity(title, evidence.title)
    author_score = _author_overlap(authors, evidence.authors)
    year_match = year is None or evidence.year is None or year == evidence.year
    doi_match = bool(doi and evidence.doi and normalize_doi(doi) == normalize_doi(evidence.doi))
    url_match = bool(url and evidence.url and _normalize_url(url) == _normalize_url(evidence.url))
    venue_score = _similarity(_claim_venue(claim), evidence.venue)

    overall = (
        0.45 * title_score
        + 0.25 * author_score
        + 0.12 * (1.0 if year_match else 0.0)
        + 0.10 * (1.0 if doi_match else 0.0)
        + 0.04 * (1.0 if url_match else 0.0)
        + 0.04 * venue_score
    )
    return {
        "title": title_score,
        "authors": author_score,
        "year_match": year_match,
        "doi_match": doi_match,
        "url_match": url_match,
        "venue": venue_score,
        "overall": overall,
    }


def _diagnostic(score: dict[str, Any]) -> str:
    if score["doi_match"] and score["title"] < 0.55:
        return "metadata_mismatch"
    if score["title"] >= 0.82 and score["authors"] >= 0.35 and score["year_match"]:
        return "source_supported"
    if score["title"] >= 0.60 and score["authors"] >= 0.50 and score["year_match"]:
        return "needs_correction"
    if score["url_match"] and score["title"] >= 0.45:
        return "source_supported"
    return "insufficient_evidence"


def _claim_title(claim: Claim) -> str | None:
    if claim.attribute == "title" and claim.value is not None:
        return str(claim.value)
    value = claim.entities.get("paper_title") or claim.entities.get("title")
    return str(value) if value is not None else None


def _claim_authors(claim: Claim) -> list[str]:
    raw = claim.value if claim.attribute == "authors" and claim.value is not None else claim.entities.get("authors")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw]
    return []


def _claim_year(claim: Claim) -> int | None:
    raw = claim.value if claim.attribute == "year" and claim.value is not None else claim.entities.get("year")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _claim_doi(claim: Claim) -> str | None:
    raw = claim.entities.get("doi") or (claim.value if claim.attribute == "doi" else None)
    return str(raw).strip() if raw else None


def _claim_url(claim: Claim) -> str | None:
    raw = claim.entities.get("url") or (claim.value if claim.attribute == "url" else None)
    return str(raw).strip() if raw else None


def _claim_venue(claim: Claim) -> str | None:
    raw = claim.entities.get("journal") or claim.entities.get("venue")
    if claim.attribute in {"journal", "venue"} and claim.value is not None:
        raw = claim.value
    return str(raw).strip() if raw else None


def _similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, _normalize_text(left), _normalize_text(right)).ratio()


def _author_overlap(left: list[str], right: list[str]) -> float:
    normalized_right = [_normalize_author(author) for author in right if _normalize_author(author)]
    if not left or not normalized_right:
        return 0.0
    matches = 0
    for author in left:
        normalized = _normalize_author(author)
        if normalized and any(_author_match(normalized, candidate) for candidate in normalized_right):
            matches += 1
    return matches / len(left)


def _author_match(left: str, right: str) -> bool:
    if left == right:
        return True
    left_parts = left.split()
    right_parts = right.split()
    if not left_parts or not right_parts:
        return False
    return left_parts[-1] == right_parts[-1] and left_parts[0][0] == right_parts[0][0]


def _normalize_text(value: str) -> str:
    value = value.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def _normalize_author(value: str) -> str:
    return _normalize_text(value)


def _normalize_url(value: str) -> str:
    return value.strip().lower().rstrip("/")
