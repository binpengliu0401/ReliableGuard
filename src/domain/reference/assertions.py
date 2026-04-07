import json
from src.domain.registry import assertion


@assertion("parse_pdf_wrote_references")
def parse_pdf_wrote_references(
    func_name: str, func_args: dict, conn
) -> tuple[bool, str]:
    """
    After parse_pdf: references table must have >= 1 row for this paper_id.
    """
    if func_name != "parse_pdf":
        return True, ""
    paper_id = func_args.get("paper_id")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM references WHERE paper_id = ?", (paper_id,)
    ).fetchone()
    count = row["cnt"] if row else 0
    if count == 0:
        return (
            False,
            f"parse_pdf_wrote_references: no references found for paper_id={paper_id}.",
        )
    return True, ""


@assertion("doi_status_not_pending")
def doi_status_not_pending(func_name: str, func_args: dict, conn) -> tuple[bool, str]:
    """
    After verify_doi: doi_status must be 'verified' or 'failed', not 'pending'.
    """
    if func_name != "verify_doi":
        return True, ""
    ref_id = func_args.get("ref_id")
    row = conn.execute(
        "SELECT doi_status FROM references WHERE ref_id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        return False, f"doi_status_not_pending: ref_id={ref_id} not found in DB."
    if row["doi_status"] == "pending":
        return (
            False,
            f"doi_status_not_pending: doi_status still pending for ref_id={ref_id}.",
        )
    return True, ""


@assertion("authors_status_not_pending")
def authors_status_not_pending(
    func_name: str, func_args: dict, conn
) -> tuple[bool, str]:
    """
    After verify_authors: authors_status must be 'verified' or 'failed', not 'pending'.
    """
    if func_name != "verify_authors":
        return True, ""
    ref_id = func_args.get("ref_id")
    row = conn.execute(
        "SELECT authors_status FROM references WHERE ref_id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        return False, f"authors_status_not_pending: ref_id={ref_id} not found in DB."
    if row["authors_status"] == "pending":
        return (
            False,
            f"authors_status_not_pending: authors_status still pending for ref_id={ref_id}.",
        )
    return True, ""


@assertion("journal_status_not_pending")
def journal_status_not_pending(
    func_name: str, func_args: dict, conn
) -> tuple[bool, str]:
    """
    After verify_journal: journal_status must be 'verified' or 'failed', not 'pending'.
    """
    if func_name != "verify_journal":
        return True, ""
    ref_id = func_args.get("ref_id")
    row = conn.execute(
        "SELECT journal_status FROM references WHERE ref_id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        return False, f"journal_status_not_pending: ref_id={ref_id} not found in DB."
    if row["journal_status"] == "pending":
        return (
            False,
            f"journal_status_not_pending: journal_status still pending for ref_id={ref_id}.",
        )
    return True, ""


@assertion("verify_journal_doi_status_verified")
def verify_journal_doi_status_verified(
    func_name: str, func_args: dict, conn
) -> tuple[bool, str]:
    """
    Before verify_journal runs its write, doi_status must already be verified.
    Catches dependency violation: verify_journal called before verify_doi passed.
    """
    if func_name != "verify_journal":
        return True, ""
    ref_id = func_args.get("ref_id")
    row = conn.execute(
        "SELECT doi_status FROM references WHERE ref_id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        return False, f"verify_journal_doi_status_verified: ref_id={ref_id} not found."
    if row["doi_status"] != "verified":
        return (
            False,
            f"verify_journal_doi_status_verified: doi_status must be 'verified' before "
            f"verify_journal, got '{row['doi_status']}' for ref_id={ref_id}.",
        )
    return True, ""
