import json
import os
import sqlite3
from typing import Any

REFERENCE_DB_PATH = "references.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(REFERENCE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_reference_db() -> sqlite3.Connection:
    conn = _get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            pdf_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS "references" (
            ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL,
            title TEXT,
            authors TEXT,
            doi TEXT,
            journal TEXT,
            year INTEGER,
            doi_status TEXT DEFAULT 'pending',
            doi_verdict_code TEXT DEFAULT 'pending',
            authors_status TEXT DEFAULT 'pending',
            journal_status TEXT DEFAULT 'pending',
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
        )
        """
    )

    # Migrate existing DBs that predate the doi_verdict_code column.
    existing_cols = {
        row[1]
        for row in conn.execute('PRAGMA table_info("references")').fetchall()
    }
    if "doi_verdict_code" not in existing_cols:
        conn.execute(
            'ALTER TABLE "references" ADD COLUMN doi_verdict_code TEXT DEFAULT \'pending\''
        )

    conn.commit()
    return conn


def _row_to_reference_dict(row: sqlite3.Row) -> dict[str, Any]:
    authors_raw = row["authors"]
    try:
        authors = json.loads(authors_raw) if authors_raw else []
    except Exception:
        authors = []

    return {
        "ref_id": row["ref_id"],
        "paper_id": row["paper_id"],
        "title": row["title"],
        "authors": authors,
        "doi": row["doi"],
        "journal": row["journal"],
        "year": row["year"],
        "doi_status": row["doi_status"],
        "authors_status": row["authors_status"],
        "journal_status": row["journal_status"],
    }


# Tool 1: parse pdf
def parse_pdf(pdf_path: str, paper_id: str) -> dict[str, Any]:
    from src.domain.reference.api_client import get_references_from_pdf

    refs = get_references_from_pdf(pdf_path)

    conn = init_reference_db()
    try:
        conn.execute(
            """
            INSERT INTO papers (paper_id, pdf_path, status)
            VALUES (?, ?, 'processing')
            ON CONFLICT(paper_id) DO UPDATE SET
                pdf_path=excluded.pdf_path,
                status='processing'
            """,
            (paper_id, pdf_path),
        )

        conn.execute(
            """
            DELETE FROM "references"
            WHERE paper_id = ?
            """,
            (paper_id,),
        )

        if not refs:
            conn.execute(
                """
                UPDATE papers
                SET status = 'failed'
                WHERE paper_id = ?
                """,
                (paper_id,),
            )
            conn.commit()
            return {
                "success": False,
                "paper_id": paper_id,
                "ref_count": 0,
                "error": "No references extracted from PDF.",
            }

        for ref in refs:
            conn.execute(
                """
                INSERT INTO "references" (
                    paper_id, title, authors, doi, journal, year,
                    doi_status, authors_status, journal_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 'pending', 'pending')
                """,
                (
                    paper_id,
                    ref.get("title", ""),
                    json.dumps(ref.get("authors", []), ensure_ascii=False),
                    ref.get("doi"),
                    ref.get("journal", ""),
                    ref.get("year"),
                ),
            )

        conn.execute(
            """
            UPDATE papers
            SET status = 'parsed'
            WHERE paper_id = ?
            """,
            (paper_id,),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "paper_id": paper_id,
        "ref_count": len(refs),
        "status": "parsed",
    }


# Tool 2: list references for a paper
def list_references(paper_id: str) -> dict[str, Any]:
    conn = init_reference_db()
    try:
        rows = conn.execute(
            """
            SELECT ref_id, paper_id, title, authors, doi, journal, year,
                   doi_status, authors_status, journal_status
            FROM "references"
            WHERE paper_id = ?
            ORDER BY ref_id ASC
            """,
            (paper_id,),
        ).fetchall()
    finally:
        conn.close()

    references = [_row_to_reference_dict(row) for row in rows]

    return {
        "success": True,
        "paper_id": paper_id,
        "count": len(references),
        "references": references,
    }


# Tool 3: verify_doi
def verify_doi(ref_id: int, doi: str) -> dict[str, Any]:
    from src.domain.reference.api_client import query_doi, _MODE
    from src.domain.reference.matcher import title_similarity, author_overlap

    result = query_doi(doi)

    exists = result.get("exists", False)
    canonical_metadata = result.get("metadata", {})
    canonical_title = canonical_metadata.get("title", "")

    # Strict mode: verify that this DOI actually points to this reference by comparing
    # titles. Auto-enabled for real/live modes; can be toggled via env var.
    # mock mode keeps old fixture-driven behaviour to preserve ablation reproducibility.
    _env = os.environ.get("REFERENCE_STRICT_DOI_MATCH", "")
    strict = {"1": True, "0": False}.get(_env, _MODE in ("real", "live"))

    title_score = 0.0
    a_overlap = 0.0
    extracted_title = ""
    extracted_authors: list[str] = []

    if strict and exists:
        conn = init_reference_db()
        try:
            row = conn.execute(
                'SELECT title, authors FROM "references" WHERE ref_id = ?',
                (ref_id,),
            ).fetchone()
        finally:
            conn.close()

        if row:
            extracted_title = row["title"] or ""
            title_score = title_similarity(extracted_title, canonical_title)
            try:
                extracted_authors = json.loads(row["authors"]) if row["authors"] else []
            except Exception:
                extracted_authors = []
            a_overlap = author_overlap(extracted_authors, canonical_metadata.get("authors", []))

        matches = title_score >= 0.80
    else:
        matches = result.get("matches", False)

    # Fine-grained verdict code: enables semantic recovery routing.
    # doi_status stays binary (verified/failed) for assertion and ablation compatibility.
    if not exists:
        doi_verdict_code = "invalid"       # DOI not found in CrossRef
    elif matches:
        doi_verdict_code = "verified"      # exists + title confirmed
    elif title_score >= 0.50:
        doi_verdict_code = "uncertain"     # same paper, but parsing quality too low to confirm
    else:
        doi_verdict_code = "mismatch"      # exists but points to a different paper

    doi_status = "verified" if doi_verdict_code == "verified" else "failed"

    conn = init_reference_db()
    try:
        conn.execute(
            'UPDATE "references" SET doi_status = ?, doi_verdict_code = ? WHERE ref_id = ?',
            (doi_status, doi_verdict_code, ref_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "success": True,
        "ref_id": ref_id,
        "doi_status": doi_status,
        "doi_verdict_code": doi_verdict_code,
        "needs_review": doi_verdict_code == "uncertain",
        "exists": exists,
        "matches": matches,
        "canonical_metadata": canonical_metadata,
        "title_score": round(title_score, 3),
        "canonical_title": canonical_title,
        "extracted_title": extracted_title,
        "author_overlap": round(a_overlap, 3),
    }


# Tool 4: verify_authors
def verify_authors(ref_id: int, title: str, authors: list[str]) -> dict[str, Any]:
    from src.domain.reference.api_client import query_authors

    result = query_authors(title)

    expected = result.get("authors", [])
    matches = result.get("found", False) and (expected == authors)
    authors_status = "verified" if matches else "failed"

    conn = init_reference_db()
    try:
        conn.execute(
            'UPDATE "references" SET authors_status = ? WHERE ref_id = ?',
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


# Tool 5: verify_journal
def verify_journal(ref_id: int, doi: str, journal: str) -> dict[str, Any]:
    from src.domain.reference.api_client import query_doi

    result = query_doi(doi)
    expected_journal = result.get("metadata", {}).get("journal", "")

    matches = (
        result.get("exists", False)
        and expected_journal.strip().lower() == journal.strip().lower()
    )
    journal_status = "verified" if matches else "failed"

    conn = init_reference_db()
    try:
        conn.execute(
            'UPDATE "references" SET journal_status = ? WHERE ref_id = ?',
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


tools = [
    {
        "type": "function",
        "function": {
            "name": "parse_pdf",
            "description": "Parse a PDF file and extract references into the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "Path to the PDF file to parse",
                    },
                    "paper_id": {
                        "type": "string",
                        "description": "Unique paper identifier used to store extracted references",
                    },
                },
                "required": ["pdf_path", "paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_references",
            "description": "List all extracted references for a given paper_id, including ref_id and parsed metadata needed for later verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper identifier used when storing extracted references",
                    }
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_doi",
            "description": "Verify whether a DOI exists and matches the extracted reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "integer",
                        "description": "Reference ID in the database",
                    },
                    "doi": {
                        "type": "string",
                        "description": "DOI string to verify",
                    },
                },
                "required": ["ref_id", "doi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_authors",
            "description": "Verify whether the provided author list matches the reference title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "integer",
                        "description": "Reference ID in the database",
                    },
                    "title": {
                        "type": "string",
                        "description": "Reference title",
                    },
                    "authors": {
                        "type": "array",
                        "description": "List of authors extracted from the reference",
                        "items": {"type": "string"},
                    },
                },
                "required": ["ref_id", "title", "authors"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_journal",
            "description": "Verify whether the provided journal name matches the canonical journal metadata of the DOI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "integer",
                        "description": "Reference ID in the database",
                    },
                    "doi": {
                        "type": "string",
                        "description": "DOI string used to retrieve canonical metadata",
                    },
                    "journal": {
                        "type": "string",
                        "description": "Extracted journal name to verify",
                    },
                },
                "required": ["ref_id", "doi", "journal"],
            },
        },
    },
]


TOOL_REGISTRY = {
    "parse_pdf": parse_pdf,
    "list_references": list_references,
    "verify_doi": verify_doi,
    "verify_authors": verify_authors,
    "verify_journal": verify_journal,
}
