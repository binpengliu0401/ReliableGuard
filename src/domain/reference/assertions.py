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


def _get_reference_status(
    conn,
    ref_id: int,
    column: str,
    assertion_name: str,
) -> tuple[bool, str, str | None]:
    if not _table_exists(conn, "references"):
        return False, f'{assertion_name}: table "references" does not exist.', None

    row = conn.execute(
        f'SELECT {column} FROM "references" WHERE ref_id = ?',
        (ref_id,),
    ).fetchone()

    if row is None:
        return False, f"{assertion_name}: ref_id={ref_id} not found in DB.", None

    return True, "", row[column]


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


@assertion("doi_status_updated")
def doi_status_updated(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_doi":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "doi_status",
        "doi_status_updated",
    )
    if not ok:
        return False, reason

    if actual_status == "pending":
        return (
            False,
            (
                f"doi_status_updated: doi_status is still pending for ref_id={ref_id}, "
                "verify_doi was not executed or did not update the record."
            ),
        )

    return True, ""


@assertion("doi_status_verified")
def doi_status_verified(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_doi":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "doi_status",
        "doi_status_verified",
    )
    if not ok:
        return False, reason

    if actual_status != "verified":
        # Include doi_verdict_code so failure_classifier can route semantically.
        _, _, verdict_code = _get_reference_status(
            conn, ref_id, "doi_verdict_code", "doi_status_verified"
        )
        code = verdict_code or "failed"
        return (
            False,
            (
                f"doi_status_verified: doi_status={actual_status} "
                f"doi_verdict_code={code} for ref_id={ref_id}, "
                "DOI verification failed — the DOI may be invalid, mismatched, or uncertain."
            ),
        )

    return True, ""


@assertion("authors_status_updated")
def authors_status_updated(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_authors":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "authors_status",
        "authors_status_updated",
    )
    if not ok:
        return False, reason

    if actual_status == "pending":
        return (
            False,
            (
                f"authors_status_updated: authors_status is still pending for ref_id={ref_id}, "
                "verify_authors was not executed or did not update the record."
            ),
        )

    return True, ""


@assertion("authors_status_verified")
def authors_status_verified(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_authors":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "authors_status",
        "authors_status_verified",
    )
    if not ok:
        return False, reason

    if actual_status != "verified":
        return (
            False,
            (
                f"authors_status_verified: authors_status={actual_status} for ref_id={ref_id}, "
                "author verification failed - the provided authors may not match canonical metadata."
            ),
        )

    return True, ""


@assertion("journal_status_updated")
def journal_status_updated(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "journal_status",
        "journal_status_updated",
    )
    if not ok:
        return False, reason

    if actual_status == "pending":
        return (
            False,
            (
                f"journal_status_updated: journal_status is still pending for ref_id={ref_id}, "
                "verify_journal was not executed or did not update the record."
            ),
        )

    return True, ""


@assertion("journal_status_verified")
def journal_status_verified(tool_name: str, tool_args: dict, conn) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "journal_status",
        "journal_status_verified",
    )
    if not ok:
        return False, reason

    if actual_status != "verified":
        return (
            False,
            (
                f"journal_status_verified: journal_status={actual_status} for ref_id={ref_id}, "
                "journal verification failed - the journal may not match canonical metadata."
            ),
        )

    return True, ""


@assertion("verify_journal_doi_status_verified")
def verify_journal_doi_status_verified(
    tool_name: str, tool_args: dict, conn
) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    ref_id = tool_args.get("ref_id")
    ok, reason, actual_status = _get_reference_status(
        conn,
        ref_id,
        "doi_status",
        "verify_journal_doi_status_verified",
    )
    if not ok:
        return False, reason

    if actual_status != "verified":
        return (
            False,
            (
                "verify_journal_doi_status_verified: doi_status must be 'verified' "
                f"before verify_journal, got '{actual_status}' for ref_id={ref_id}."
            ),
        )

    return True, ""
