from __future__ import annotations

import json
from typing import Any

from src.domain.reference.api_client import (
    lookup_by_metadata,
    lookup_by_title_only,
    normalize_doi,
    query_authors,
    query_doi,
)
from src.domain.reference.matcher import author_overlap, title_similarity
from src.domain.reference.tools import init_reference_db
from src.reliableguard.schema import Claim, SourceMode, VerificationResult, Verifiability
from src.reliableguard.verifier.sources.loader import load_sources
from src.reliableguard.verifier.sources.router import query_configured_sources
from src.reliableguard.verifier.sources.scorer import verification_from_evidence


def _external_sources_enabled() -> bool:
    """Whether any external reference source is configured and enabled.

    Offline (the default benchmark mode) all sources are disabled, so a claim the
    fixture cannot confirm maps to `unavailable` ("no source to consult") rather than
    `not_found` ("an available authoritative source positively reported absence").
    """
    return len(load_sources("reference")) > 0


# --- Citation-level sufficiency check ----------------------------------------
#
# The per-claim verifier (`verify_reference_claim`) judges each extracted claim in
# isolation: a DOI route, a title route, an authors route, etc. That isolation is the
# source of the reference-domain false-BLOCK problem: a single genuine citation is
# decomposed into several claims, and any one field the fixture cannot confirm on its
# own (e.g. a real DOI absent from the fixture `dois` map) yields `not_found` -> high
# risk -> BLOCK, even when the title and authors clearly identify a real paper.
#
# `verify_reference_claims` adds a paper-level layer on top of the per-claim baseline.
# It groups claims that describe the same citation (by ref_id, else title, else DOI),
# joins the evidence, and applies a sufficiency hierarchy:
#
#   strong : a claimed DOI exists in the fixture AND (no competing title, or the
#            claimed title agrees with the DOI's fixture record >= 0.85)  -> supported
#   medium : no/failed DOI, but the title matches a fixture record (>= 0.85) AND every
#            claimed author surname is in that record's author list        -> supported
#   weak   : exactly one of {title-match, author-match} holds              -> unverifiable
#   none   : neither holds                                                 -> unchanged
#
# The layer only ever *lifts* a baseline result (it never downgrades a claim the
# per-claim verifier already supported), so it can reduce false BLOCKs without raising
# new ones. `none` groups keep the per-claim baseline verbatim, preserving F1/F3
# (fabricated DOI / title) detection.

_CITATION_TITLE_THRESHOLD = 0.95


def verify_reference_claims(
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
) -> dict[str, VerificationResult]:
    """Reference-domain batch verifier with citation-level sufficiency.

    Computes the per-claim baseline first (identical to the legacy path), then merges
    claims belonging to the same citation and upgrades baselines that the joint
    evidence renders a false alarm. Returns a result for every claim.
    """
    results: dict[str, VerificationResult] = {}
    for claim in claims:
        level = verifiability.get(claim.claim_id, "unverifiable")
        if level == "unverifiable":
            results[claim.claim_id] = VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                confidence=1.0,
                reason="No verification path is available for this claim.",
            )
        else:
            results[claim.claim_id] = verify_reference_claim(claim, level)

    for group_claims in _group_citation_claims(claims).values():
        titles, dois, authors = _collect_citation_fields(group_claims)
        tier, record, source = _judge_citation(titles, dois, authors)
        if tier == "none":
            continue
        for claim in group_claims:
            results[claim.claim_id] = _apply_citation_tier(
                claim, results[claim.claim_id], tier, record, source
            )
    return results


def _group_citation_claims(claims: list[Claim]) -> dict[tuple[str, str], list[Claim]]:
    """Group claims that describe the same citation.

    Grouping key preference: ref_id (scoped by paper_id when present) > claimed title >
    claimed DOI. Claims with no citation handle (e.g. a paper-level reference_count)
    fall into singleton groups and are therefore never cross-contaminated.
    """
    groups: dict[tuple[str, str], list[Claim]] = {}
    for claim in claims:
        groups.setdefault(_citation_key(claim), []).append(claim)
    return groups


def _citation_key(claim: Claim) -> tuple[str, str]:
    ref_id = claim.entities.get("ref_id")
    if ref_id is not None:
        paper_id = claim.entities.get("paper_id")
        scope = str(paper_id) if paper_id is not None else ""
        return ("ref", f"{scope}:{ref_id}")

    title = _claim_title(claim)
    if title:
        return ("title", _normalize(title))

    doi = _claim_doi(claim)
    if doi:
        return ("doi", normalize_doi(doi))

    return ("solo", claim.claim_id)


def _claim_title(claim: Claim) -> str | None:
    if (claim.attribute or "").lower() in {"title", "paper_title"} and claim.value:
        return str(claim.value).strip()
    title = claim.entities.get("paper_title") or claim.entities.get("title")
    return str(title).strip() if title else None


def _claim_doi(claim: Claim) -> str | None:
    if (claim.attribute or "").lower() == "doi" and claim.value:
        candidate = str(claim.value).strip()
        if candidate and candidate.lower() not in {"none", "n/a", "null", "na", "-"}:
            return candidate
    raw = claim.entities.get("doi") or claim.entities.get("DOI")
    if raw:
        candidate = str(raw).strip()
        if candidate and candidate.lower() not in {"none", "n/a", "null", "na", "-"}:
            return candidate
    return None


def _collect_citation_fields(
    group_claims: list[Claim],
) -> tuple[list[str], list[str], list[str]]:
    """Collect the distinct titles, DOIs, and author names asserted across a group."""
    titles: list[str] = []
    dois: list[str] = []
    authors: list[str] = []
    for claim in group_claims:
        title = _claim_title(claim)
        if title and title not in titles:
            titles.append(title)
        doi = _claim_doi(claim)
        if doi and doi not in dois:
            dois.append(doi)
        if (claim.attribute or "").lower() == "authors" and claim.value is not None:
            for author in _as_author_list(claim.value):
                if author not in authors:
                    authors.append(author)
        for author in _as_author_list(claim.entities.get("authors")):
            if author not in authors:
                authors.append(author)
    return titles, dois, authors


def _judge_citation(
    titles: list[str],
    dois: list[str],
    authors: list[str],
) -> tuple[str, dict[str, Any] | None, str]:
    """Return (tier, fixture_record, source) for one citation group."""
    doi_record: dict[str, Any] | None = None
    for doi in dois:
        result = query_doi(normalize_doi(doi))
        if result.get("exists", False):
            metadata = result.get("metadata")
            doi_record = dict(metadata) if isinstance(metadata, dict) else {}
            break

    title_record: dict[str, Any] | None = None
    for title in titles:
        record = lookup_by_title_only(title, _CITATION_TITLE_THRESHOLD)
        if record is not None:
            title_record = record
            break

    # Strong: a verified DOI, consistent with the claimed title (when one is asserted).
    if doi_record is not None:
        if not titles:
            return "strong", doi_record, "crossref"
        fixture_title = str(doi_record.get("title") or "")
        best = max(
            (title_similarity(title, fixture_title) for title in titles), default=0.0
        )
        if best >= _CITATION_TITLE_THRESHOLD:
            return "strong", doi_record, "crossref"
        # A valid DOI paired with a disagreeing title is not auto-trusted; fall through.

    title_match = title_record is not None
    reference_record = doi_record or title_record or {}
    fixture_authors = reference_record.get("authors") or []
    author_match = bool(authors) and _author_surnames_subset(authors, fixture_authors)

    # Medium: title matches a fixture record and every claimed author surname is present.
    if title_match and author_match:
        return "medium", title_record, "reference_metadata"

    # Weak: a single corroborating signal — enough to suppress a BLOCK, not to support.
    if title_match or author_match:
        return "weak", title_record or doi_record, "reference_metadata"

    return "none", None, "reference_metadata"


def _author_surnames_subset(claimed: list[str], fixture: list[str]) -> bool:
    """True when every claimed author surname appears in the fixture author list.

    Order-independent, surname-only (last name). The author lists here are
    comma/`and`-separated "Given Family" names, so the surname is the trailing token;
    a "Family, Given" entry is handled by taking the text before the comma.
    """
    claimed_surnames = {_surname(name) for name in claimed}
    fixture_surnames = {_surname(name) for name in fixture}
    claimed_surnames.discard("")
    fixture_surnames.discard("")
    if not claimed_surnames or not fixture_surnames:
        return False
    return claimed_surnames <= fixture_surnames


def _surname(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    if "," in text:
        return text.split(",", 1)[0].strip().lower()
    tokens = text.split()
    return tokens[-1].strip().lower() if tokens else ""


def _apply_citation_tier(
    claim: Claim,
    baseline: VerificationResult,
    tier: str,
    record: dict[str, Any] | None,
    source: str,
) -> VerificationResult:
    if tier in {"strong", "medium"}:
        confidence = 1.0 if tier == "strong" else 0.9
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported",
            evidence_value=record if record else baseline.evidence_value,
            source=source,
            source_mode="fixture",
            confidence=confidence,
            reason=(
                f"Citation-level {tier} evidence: the reference is grounded in the "
                "fixture, so its claims are treated as supported."
            ),
        )

    if tier == "weak" and baseline.evidence_state in {"not_found", "contradicted"}:
        # One signal corroborates the citation but the joint evidence is insufficient
        # to assert the field. Downgrade the false alarm to unverifiable (low risk,
        # not BLOCK) rather than letting a single unconfirmed field gate the answer.
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unverifiable",
            evidence_value=baseline.evidence_value,
            source=source,
            source_mode="unavailable",
            confidence=0.0,
            reason=(
                "Citation-level weak evidence (only one of title/authors matched the "
                "fixture); insufficient to confirm or to flag this field."
            ),
        )

    return baseline


def verify_reference_claim(claim: Claim, verifiability: Verifiability) -> VerificationResult:
    doi = claim.entities.get("doi") or (claim.value if claim.attribute == "doi" else None)
    if doi:
        return _verify_doi_claim(claim, normalize_doi(str(doi)))

    ref_id = _as_int(claim.entities.get("ref_id"))
    if ref_id is not None:
        # For ref_id-tagged claims: first try per-attribute fixture verification
        # (title / DOI can be looked up directly in the fixture). All other
        # attribute types fall through to _verify_reference_db_claim, which
        # returns `unverifiable` when the ref_id is absent from the DB (the DB
        # only holds F4 fault-injected records; its absence is NOT authoritative
        # evidence that the reference does not exist).
        fixture_result = _verify_ref_id_claim_via_fixture(claim)
        if fixture_result is not None:
            return fixture_result
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
        source_mode="unavailable",
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
                source_mode="not_found" if _external_sources_enabled() else "unavailable",
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
            source_mode="fixture",
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
        # The references_db only contains F4 fault-injected records (high ref_ids).
        # Absence here does NOT mean the reference does not exist — the DB is not
        # an authoritative source for normal fixture ref_ids (1–N per paper).
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unverifiable",
            source="references_db",
            source_mode="unavailable",
            confidence=0.0,
            reason=f"Reference {ref_id} was not found in references_db (not authoritative for this ref_id).",
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
        source_mode="fixture",
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
    if actual == 0:
        # Paper has no references in the DB (only F4 records are stored there).
        # A zero count here means the DB is not authoritative for this paper's refs,
        # not that the paper actually has zero references.
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="unverifiable",
            source="references_db",
            source_mode="unavailable",
            confidence=0.0,
            reason=f"Paper '{paper_id}' has no references in references_db (not authoritative).",
        )
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
            source_mode="not_found" if _external_sources_enabled() else "unavailable",
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
        source_mode="fixture",
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
            source_mode="fixture",
            confidence=min(score for _, _, score, _ in material_checks),
            reason="; ".join(reason for _, supported, _, reason in material_checks if supported is False),
        )

    if missing_checks:
        # A record was found; only the specific field is absent, so this is still
        # fixture-sourced evidence (not "source offline").
        return _unverifiable_metadata_result(
            claim,
            "; ".join(reason for _, _, _, reason in missing_checks),
            record,
            source,
            source_mode="fixture",
        )

    if material_checks:
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="supported",
            evidence_value=record,
            source=source,
            source_mode="fixture",
            confidence=min(score for _, _, score, _ in material_checks),
            reason="; ".join(reason for _, _, _, reason in material_checks),
        )

    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported",
        evidence_value=record,
        source=source,
        source_mode="fixture",
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
    *,
    source_mode: SourceMode = "unavailable",
) -> VerificationResult:
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="unverifiable",
        evidence_value=evidence_value,
        source=source,
        source_mode=source_mode,
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
            source_mode="fixture",
            confidence=0.5,
            reason="Numeric claim could not be parsed into a comparable value.",
        )
    supported = abs(claimed - actual_number) < 1e-6
    return VerificationResult(
        claim_id=claim.claim_id,
        evidence_state="supported" if supported else "contradicted",
        evidence_value=evidence_value if evidence_value is not None else actual,
        source=source,
        source_mode="fixture",
        confidence=1.0,
        reason=f"Claimed value={claimed}; database value={actual_number}.",
    )


def _verify_ref_id_claim_via_fixture(claim: Claim) -> VerificationResult | None:
    """Fixture-based verification for claims that carry a ref_id entity.

    For title and DOI attributes, the claim value provides a direct fixture lookup
    path — find the paper by title or DOI and verify the attribute.  A real title
    returns `supported`; a fabricated title returns `not_found` (preserving F1/F3
    detection).  For all other attribute types (authors, ref_id existence, meta-
    claims such as verification_status), there is no unambiguous fixture path (ref_ids
    are per-paper and not globally unique), so None is returned to fall through to
    _verify_reference_db_claim, which now returns `unverifiable` for absent ref_ids.
    """
    attr = (claim.attribute or "").lower()

    # Title claims: look up the title value in the fixture.
    # Correct title → supported; hallucinated/wrong title → not_found (detection preserved).
    if attr in {"title", "paper_title"} and claim.value:
        record = lookup_by_title_only(str(claim.value))
        if record is not None:
            sim = title_similarity(str(claim.value), str(record.get("title", "")))
            state = "supported" if sim >= 0.8 else "contradicted"
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state=state,
                evidence_value=record,
                source="reference_fixture",
                source_mode="fixture",
                confidence=sim,
                reason=(
                    f"Title {'matches' if state == 'supported' else 'contradicts'}"
                    f" fixture record (similarity={sim:.3f})."
                ),
            )
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="not_found",
            source="reference_fixture",
            source_mode="not_found",
            confidence=1.0,
            reason="Title not found in reference fixture.",
        )

    # DOI claims: look up the DOI value in the fixture.
    # Correct DOI → supported; fabricated DOI → not_found (detection preserved).
    # Null-like values ("none", empty) mean "this reference has no DOI" —
    # that is unverifiable without paper context, not a fixture miss.
    if attr == "doi" and claim.value:
        doi_str = str(claim.value).strip()
        if not doi_str or doi_str.lower() in {"none", "n/a", "null", "na", "-"}:
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="unverifiable",
                source="reference_fixture",
                source_mode="unavailable",
                confidence=0.0,
                reason="DOI claim has a null/absent value; cannot verify without paper context.",
            )
        doi_result = query_doi(normalize_doi(doi_str))
        if doi_result.get("exists", False):
            return VerificationResult(
                claim_id=claim.claim_id,
                evidence_state="supported",
                evidence_value=doi_result.get("metadata"),
                source="crossref",
                source_mode="fixture",
                confidence=1.0,
                reason="DOI found in reference fixture.",
            )
        return VerificationResult(
            claim_id=claim.claim_id,
            evidence_state="not_found",
            source="crossref",
            source_mode="not_found" if _external_sources_enabled() else "unavailable",
            confidence=1.0,
            reason="DOI not found in reference fixture.",
        )

    # All other attribute types: no unambiguous fixture path — fall through.
    return None
