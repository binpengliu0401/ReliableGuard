from __future__ import annotations

from typing import Any

from src.domain.reference.api_client import query_authors, query_doi
from src.domain.reference.matcher import author_overlap, title_similarity
from src.domain.reference.tools import init_reference_db
from src.reliableguard.schema import Claim, VerificationResult, Verifiability


def verify_reference_claim(claim: Claim, verifiability: Verifiability) -> VerificationResult:
    doi = claim.entities.get("doi") or (claim.value if claim.attribute == "doi" else None)
    if doi:
        return _verify_doi_claim(claim, str(doi))

    ref_id = _as_int(claim.entities.get("ref_id"))
    if ref_id is not None:
        return _verify_reference_db_claim(claim, ref_id)

    if claim.attribute == "authors" and claim.entities.get("paper_title"):
        return _verify_authors_claim(claim, str(claim.entities["paper_title"]))

    if claim.attribute == "title":
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unsupported",
            source="reference_metadata",
            confidence=0.5,
            reason="Title-only claims require DOI or ref_id context for reliable verification.",
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
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="not_found",
            evidence_value=result,
            source="crossref",
            confidence=1.0,
            reason=f"DOI {doi} was not found in the configured reference source.",
        )

    metadata = result.get("metadata", {})
    title = claim.entities.get("paper_title")
    if title:
        score = title_similarity(str(title), metadata.get("title", ""))
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported" if score >= 0.8 else "contradicted",
            evidence_value=metadata,
            source="crossref",
            confidence=score,
            reason=f"DOI exists; title similarity={score:.3f}.",
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=metadata,
        source="crossref",
        confidence=1.0,
        reason=f"DOI {doi} exists in the configured reference source.",
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
        actual = evidence[attr]
        claimed = claim.value
        supported = _normalize(actual) == _normalize(claimed)
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported" if supported else "contradicted",
            evidence_value=evidence,
            source="references_db",
            confidence=1.0,
            reason=f"Claimed {attr}={claimed}; database {attr}={actual}.",
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=evidence,
        source="references_db",
        confidence=1.0,
        reason="Reference entity exists in references_db.",
    )


def _verify_authors_claim(claim: Claim, title: str) -> VerificationResult:
    result = query_authors(title)
    if not result.get("found", False):
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


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

