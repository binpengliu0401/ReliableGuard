import json
import sqlite3
import os
from typing import Any
from src.utils.db import get_db_path  # type: ignore


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# Tool 1: parse pdf
def parse_pdf(pdf_path: str, paper_id: str) -> dict[str, Any]:
    from src.domain.reference.api_client import get_references_from_pdf

    refs = get_references_from_pdf(pdf_path)

    if not refs:
        return {
            "success": False,
            "paper_id": paper_id,
            "ref_count": 0,
            "error": "No references extracted from PDF.",
        }

    conn = _get_conn()
    try:
        # Upsert paper record
        conn.execute(
            """
            INSERT INTO papers (paper_id, pdf_path, status)
            VALUES (?, ?, 'processing')
            ON CONFLICT(paper_id) DO UPDATE SET status='processing'
            """,
            (paper_id, pdf_path),
        )

        # Insert reference rows (all statuses = pending)
        for ref in refs:
            conn.execute(
                """
                INSERT INTO references (
                    paper_id, title, authors, doi, journal, year,
                    doi_status, authors_status, journal_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 'pending', 'pending')
                """,
                (
                    paper_id,
                    ref.get("title", ""),
                    json.dumps(ref.get("authors", [])),
                    ref.get("doi"),
                    ref.get("journal", ""),
                    ref.get("year"),
                ),
            )

        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "paper_id": paper_id,
        "ref_count": len(refs),
        "status": "pending",
    }


# Tool 2: verify_doi
def verify_doi(ref_id: int, doi: str) -> dict[str, Any]:
    from src.domain.reference.api_client import query_doi

    result = query_doi(doi)

    exists = result.get("exists", False)
    matches = result.get("matches", False)
    doi_status = "verified" if (exists and matches) else "failed"
    canonical_metadata = result.get("metadata", {})

    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE references SET doi_status = ? WHERE ref_id = ?",
            (doi_status, ref_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "ref_id": ref_id,
        "doi_status": doi_status,
        "exists": exists,
        "matches": matches,
        "canonical_metadata": canonical_metadata,
    }


# Tool 3: verify_authors
def verify_authors(ref_id: int, title: str, authors: list[str]) -> dict[str, Any]:
    from src.domain.reference.api_client import query_authors

    result = query_authors(title)

    expected = result.get("authors", [])
    matches = result.get("found", False) and (expected == authors)
    authors_status = "verified" if matches else "failed"

    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE references SET authors_status = ? WHERE ref_id = ?",
            (authors_status, ref_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "ref_id": ref_id,
        "authors_status": authors_status,
        "expected_authors": expected,
        "provided_authors": authors,
    }


# Tool 4: verify_journal
def verify_journal(ref_id: int, doi: str, journal: str) -> dict[str, Any]:
    """
    Verify journal name using canonical metadata from CrossRef.
    Depends on verify_doi having run first (doi_status != pending).
    Updates journal_status in DB.
    Returns: { ref_id, journal_status, expected_journal, provided_journal }
    """
    from src.domain.reference.api_client import query_doi

    # Re-use CrossRef metadata (cached in mock; live makes same call)
    result = query_doi(doi)
    expected_journal = result.get("metadata", {}).get("journal", "")

    matches = (
        result.get("exists", False)
        and expected_journal.strip().lower() == journal.strip().lower()
    )
    journal_status = "verified" if matches else "failed"

    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE references SET journal_status = ? WHERE ref_id = ?",
            (journal_status, ref_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "ref_id": ref_id,
        "journal_status": journal_status,
        "expected_journal": expected_journal,
        "provided_journal": journal,
    }


# Tool registry
TOOL_REGISTRY = {
    "parse_pdf": parse_pdf,
    "verify_doi": verify_doi,
    "verify_authors": verify_authors,
    "verify_journal": verify_journal,
}
