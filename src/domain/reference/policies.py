from src.domain.registry import policy


@policy("batch_size_limit")
def batch_size_limit(
    tool_name: str, tool_args: dict, context=None
) -> tuple[bool, str]:
    ref_id = tool_args.get("ref_id")
    if isinstance(ref_id, list) and len(ref_id) > 10:
        return (
            False,
            f"batch_size_limit: ref_id list exceeds max 10, got {len(ref_id)}.",
        )
    return True, ""


@policy("doi_required_for_journal")
def doi_required_for_journal(
    tool_name: str, tool_args: dict, context=None
) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    doi = tool_args.get("doi", "")
    if not doi or not str(doi).strip():
        return (
            False,
            "doi_required_for_journal: verify_journal requires a non-empty doi.",
        )
    return True, ""


@policy("doi_must_be_verified_before_journal")
def doi_must_be_verified_before_journal(
    tool_name: str, tool_args: dict, context=None
) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""
    if context is None or context.get("db_conn") is None:
        return True, ""

    ref_id = tool_args.get("ref_id")
    if ref_id is None:
        return True, ""

    conn = context["db_conn"]
    row = conn.execute(
        'SELECT doi_status FROM "references" WHERE ref_id = ?', (ref_id,)
    ).fetchone()
    if row is None or row[0] != "verified":
        status = row[0] if row else "not found"
        return (
            False,
            f"doi_must_be_verified_before_journal: ref_id={ref_id} doi_status={status}, must be verified first.",
        )
    return True, ""


@policy("reference_must_exist_before_verify")
def reference_must_exist_before_verify(
    tool_name: str, tool_args: dict, context=None
) -> tuple[bool, str]:
    if tool_name not in ("verify_doi", "verify_authors", "verify_journal"):
        return True, ""
    if context is None or context.get("db_conn") is None:
        return True, ""

    ref_id = tool_args.get("ref_id")
    if ref_id is None:
        return True, ""

    conn = context["db_conn"]
    row = conn.execute(
        'SELECT ref_id FROM "references" WHERE ref_id = ?', (ref_id,)
    ).fetchone()
    if row is None:
        return (
            False,
            f"reference_must_exist_before_verify: ref_id={ref_id} does not exist in references table.",
        )
    return True, ""
