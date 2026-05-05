from __future__ import annotations

import json
from typing import Any

from src.domain.reference.api_client import (
    lookup_by_metadata,
    normalize_doi,
    query_authors,
    query_doi,
)
from src.domain.reference.matcher import author_overlap, title_similarity
from src.domain.reference.tools import init_reference_db
from src.reliableguard.schema import Claim, VerificationResult, Verifiability
from src.reliableguard.verifier.sources.router import query_configured_sources
from src.reliableguard.verifier.sources.scorer import verification_from_evidence


def verify_reference_claim(claim: Claim, verifiability: Verifiability) -> VerificationResult:
    doi = claim.entities.get("doi") or (claim.value if claim.attribute == "doi" else None)
    if doi:
        return _verify_doi_claim(claim, normalize_doi(str(doi)))

    ref_id = _as_int(claim.entities.get("ref_id"))
    if ref_id is not None:
        return _verify_reference_db_claim(claim, ref_id)

    if claim.attribute in {"reference_count", "ref_count"} and claim.entities.get("paper_id"):
        return _verify_reference_count_claim(claim, str(claim.entities["paper_id"]))

    if claim.attribute == "authors" and claim.entities.get("paper_title"):
        return _verify_authors_claim(claim, str(claim.entities["paper_title"]))

    fallback = _lookup_claim_metadata(claim)
    if fallback is not None:
        return _verify_record_fields(claim, fallback, "reference_metadata")

    source_result = _verify_with_configured_sources(claim)
    if source_result is not None:
        return source_result

    if _has_metadata_hint(claim):
        return _unverifiable_metadata_result(
            claim,
            "No DOI/ref_id verifier path matched and metadata fallback found no fixture record.",
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="unsupported" if verifiability == "partially_verifiable" else "unverifiable",
        source="reference_metadata",
        confidence=0.0,
        reason="No reference verifier rule matched this claim.",
    )


def _verify_doi_claim(claim: Claim, doi: str) -> VerificationResult:
    result = query_doi(doi)
    if not result.get("exists", False):
        fallback = _lookup_claim_metadata(claim)
        if fallback is not None:
            return _verify_record_fields(claim, fallback, "reference_metadata")
        source_result = _verify_with_configured_sources(claim)
        if source_result is not None:
            return source_result
        if not _has_metadata_hint(claim):
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="not_found",
                evidence_value=result,
                source="crossref",
                confidence=1.0,
                reason=f"DOI {doi} was not found in the configured reference source.",
            )
        return _unverifiable_metadata_result(
            claim,
            f"DOI {doi} was not found in the configured reference source and metadata fallback found no fixture record.",
            result,
        )

    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict) or not metadata:
        return _unverifiable_metadata_result(
            claim,
            f"DOI {doi} exists but no fixture metadata is available for field verification.",
            result,
        )
    metadata = dict(metadata)
    metadata.setdefault("doi", doi)
    return _verify_record_fields(
        claim,
        metadata,
        "crossref",
        default_reason=f"DOI {doi} exists in the configured reference source.",
    )


def _verify_reference_db_claim(claim: Claim, ref_id: int) -> VerificationResult:
    conn = init_reference_db()
    try:
        row = conn.execute(
            'SELECT ref_id, title, authors, doi, journal, year, doi_status FROM "references" WHERE ref_id = ?',
            (ref_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="not_found",
            source="references_db",
            confidence=1.0,
            reason=f"Reference {ref_id} was not found in references_db.",
        )

    evidence = {
        "ref_id": row["ref_id"],
        "title": row["title"],
        "authors": row["authors"],
        "doi": row["doi"],
        "journal": row["journal"],
        "year": row["year"],
        "doi_status": row["doi_status"],
    }
    attr = claim.attribute
    if attr and attr in evidence and claim.value is not None:
        return _verify_record_fields(claim, evidence, "references_db")

    if attr in {"author_count", "authors_count"}:
        try:
            authors = json.loads(evidence["authors"]) if evidence["authors"] else []
        except Exception:
            authors = []
        return _compare_numeric(claim, len(authors), "references_db", evidence)

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=evidence,
        source="references_db",
        confidence=1.0,
        reason="Reference entity exists in references_db.",
    )


def _verify_reference_count_claim(claim: Claim, paper_id: str) -> VerificationResult:
    conn = init_reference_db()
    try:
        row = conn.execute(
            'SELECT COUNT(*) AS count FROM "references" WHERE paper_id = ?',
            (paper_id,),
        ).fetchone()
    finally:
        conn.close()

    actual = row["count"] if row is not None else 0
    return _compare_numeric(claim, actual, "references_db", {"paper_id": paper_id, "count": actual})


def _verify_authors_claim(claim: Claim, title: str) -> VerificationResult:
    result = query_authors(title)
    if not result.get("found", False):
        source_result = _verify_with_configured_sources(claim)
        if source_result is not None:
            return source_result
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unsupported",
            evidence_value=result,
            source="semantic_scholar",
            confidence=0.0,
            reason="No canonical authors were found for the claimed title.",
        )
    claimed = claim.value if isinstance(claim.value, list) else claim.entities.get("authors", [])
    expected = result.get("authors", [])
    overlap = author_overlap([str(x) for x in claimed], expected)
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported" if overlap >= 0.8 else "contradicted",
        evidence_value={"expected_authors": expected, "claimed_authors": claimed},
        source="semantic_scholar",
        confidence=overlap,
        reason=f"Author overlap={overlap:.3f}.",
    )


def _lookup_claim_metadata(claim: Claim) -> dict[str, Any] | None:
    title, authors, year = _metadata_hints(claim)
    if not title or not authors:
        return None
    return lookup_by_metadata(title, authors, year)


def _verify_with_configured_sources(claim: Claim) -> VerificationResult | None:
    evidence = query_configured_sources("reference", claim)
    return verification_from_evidence(claim, evidence, default_source="reference_configured_sources")


def _has_metadata_hint(claim: Claim) -> bool:
    title, authors, year = _metadata_hints(claim)
    return bool(title or authors or year is not None)


def _metadata_hints(claim: Claim) -> tuple[str | None, list[str], int | None]:
    title = claim.entities.get("paper_title") or claim.entities.get("title")
    if claim.attribute == "title" and claim.value is not None:
        title = claim.value

    raw_authors = claim.entities.get("authors")
    if claim.attribute == "authors" and claim.value is not None:
        raw_authors = claim.value
    authors = _as_author_list(raw_authors)

    raw_year = claim.entities.get("year")
    if claim.attribute == "year" and claim.value is not None:
        raw_year = claim.value
    year = _as_int(raw_year)
    return str(title).strip() if title is not None else None, authors, year


def _verify_record_fields(
    claim: Claim,
    record: dict[str, Any],
    source: str,
    *,
    default_reason: str | None = None,
) -> VerificationResult:
    checks: list[tuple[str, bool | None, float, str]] = []

    attr = claim.attribute
    if attr and claim.value is not None:
        checks.append(_compare_field(attr, claim.value, record))

    title = claim.entities.get("paper_title") or claim.entities.get("title")
    if title is not None and attr != "title":
        checks.append(_compare_field("title", title, record))

    authors = claim.entities.get("authors")
    if authors is not None and attr != "authors":
        checks.append(_compare_field("authors", authors, record))

    year = claim.entities.get("year")
    if year is not None and attr != "year":
        checks.append(_compare_field("year", year, record))

    material_checks = [check for check in checks if check[1] is not None]
    missing_checks = [check for check in checks if check[1] is None]

    if any(supported is False for _, supported, _, _ in material_checks):
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="contradicted",
            evidence_value=record,
            source=source,
            confidence=min(score for _, _, score, _ in material_checks),
            reason="; ".join(reason for _, supported, _, reason in material_checks if supported is False),
        )

    if missing_checks:
        return _unverifiable_metadata_result(
            claim,
            "; ".join(reason for _, _, _, reason in missing_checks),
            record,
            source,
        )

    if material_checks:
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported",
            evidence_value=record,
            source=source,
            confidence=min(score for _, _, score, _ in material_checks),
            reason="; ".join(reason for _, _, _, reason in material_checks),
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=record,
        source=source,
        confidence=1.0,
        reason=default_reason or "Reference metadata record exists in the configured source.",
    )


def _compare_field(
    attr: str,
    claimed: Any,
    record: dict[str, Any],
) -> tuple[str, bool | None, float, str]:
    actual = record.get(attr)
    if attr not in record or actual is None or actual == "":
        return attr, None, 0.0, f"Fixture metadata has no {attr} field."

    if attr == "authors":
        claimed_authors = _as_author_list(claimed)
        actual_authors = _as_author_list(actual)
        overlap = author_overlap(claimed_authors, actual_authors)
        return (
            attr,
            overlap >= 0.8,
            overlap,
            f"Author overlap={overlap:.3f}.",
        )

    if attr == "title":
        score = title_similarity(str(claimed), str(actual))
        return (
            attr,
            score >= 0.8,
            score,
            f"Title similarity={score:.3f}.",
        )

    if attr == "doi":
        claimed_doi = normalize_doi(str(claimed))
        actual_doi = normalize_doi(str(actual))
        supported = claimed_doi == actual_doi
        return (
            attr,
            supported,
            1.0 if supported else 0.0,
            f"Claimed doi={claimed_doi}; fixture doi={actual_doi}.",
        )

    if attr == "year":
        claimed_year = _as_int(claimed)
        actual_year = _as_int(actual)
        supported = claimed_year is not None and claimed_year == actual_year
        return (
            attr,
            supported,
            1.0 if supported else 0.0,
            f"Claimed year={claimed_year}; fixture year={actual_year}.",
        )

    supported = _normalize(actual) == _normalize(claimed)
    return (
        attr,
        supported,
        1.0 if supported else 0.0,
        f"Claimed {attr}={claimed}; fixture {attr}={actual}.",
    )


def _as_author_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
        return [value] if value.strip() else []
    return [str(value)] if str(value).strip() else []


def _unverifiable_metadata_result(
    claim: Claim,
    reason: str,
    evidence_value: Any | None = None,
    source: str = "reference_metadata",
) -> VerificationResult:
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="unverifiable",
        evidence_value=evidence_value,
        source=source,
        confidence=0.0,
        reason=reason,
    )


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare_numeric(
    claim: Claim,
    actual: Any,
    source: str,
    evidence_value: Any | None = None,
) -> VerificationResult:
    claimed = _as_float(claim.value)
    actual_number = _as_float(actual)
    if claimed is None or actual_number is None:
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unsupported",
            evidence_value=evidence_value if evidence_value is not None else actual,
            source=source,
            confidence=0.5,
            reason="Numeric claim could not be parsed into a comparable value.",
        )
    supported = abs(claimed - actual_number) < 1e-6
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported" if supported else "contradicted",
        evidence_value=evidence_value if evidence_value is not None else actual,
        source=source,
        confidence=1.0,
        reason=f"Claimed value={claimed}; database value={actual_number}.",
    )
