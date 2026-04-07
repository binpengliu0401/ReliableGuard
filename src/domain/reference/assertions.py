from src.domain.registry import assertion


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


@assertion("parse_pdf_wrote_references")
def parse_pdf_wrote_references(
    tool_name: str, tool_args: dict, conn
) -> tuple[bool, str]:
    if tool_name != "parse_pdf":
        return True, ""

    if not _table_exists(conn, "references"):
        return False, 'parse_pdf_wrote_references: table "references" does not exist.'

    paper_id = tool_args.get("paper_id")
    row = conn.execute(
        'SELECT COUNT(*) as cnt FROM "references" WHERE paper_id = ?',
        (paper_id,),
    ).fetchone()
    count = row["cnt"] if row else 0

    if count == 0:
        return (
            False,
            f"parse_pdf_wrote_references: no references found for paper_id={paper_id}.",
        )
    return True, ""


@assertion("doi_status_not_pending")
def doi_status_not_pending(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_doi":
        return True, ""

    if not _table_exists(conn, "references"):
        return False, 'doi_status_not_pending: table "references" does not exist.'

    ref_id = tool_args.get("ref_id")
    row = conn.execute(
        'SELECT doi_status FROM "references" WHERE ref_id = ?',
        (ref_id,),
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
    tool_name: str, tool_args: dict, conn
) -> tuple[bool, str]:
    if tool_name != "verify_authors":
        return True, ""

    if not _table_exists(conn, "references"):
        return False, 'authors_status_not_pending: table "references" does not exist.'

    ref_id = tool_args.get("ref_id")
    row = conn.execute(
        'SELECT authors_status FROM "references" WHERE ref_id = ?',
        (ref_id,),
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
    tool_name: str, tool_args: dict, conn
) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    if not _table_exists(conn, "references"):
        return False, 'journal_status_not_pending: table "references" does not exist.'

    ref_id = tool_args.get("ref_id")
    row = conn.execute(
        'SELECT journal_status FROM "references" WHERE ref_id = ?',
        (ref_id,),
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
    tool_name: str, tool_args: dict, conn
) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    if not _table_exists(conn, "references"):
        return (
            False,
            'verify_journal_doi_status_verified: table "references" does not exist.',
        )

    ref_id = tool_args.get("ref_id")
    row = conn.execute(
        'SELECT doi_status FROM "references" WHERE ref_id = ?',
        (ref_id,),
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
