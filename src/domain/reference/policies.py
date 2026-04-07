from src.domain.registry import policy


@policy("batch_size_limit")
def batch_size_limit(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    ref_id = tool_args.get("ref_id")
    if isinstance(ref_id, list) and len(ref_id) > 10:
        return (
            False,
            f"batch_size_limit: ref_id list exceeds max 10, got {len(ref_id)}.",
        )
    return True, ""


@policy("doi_required_for_journal")
def doi_required_for_journal(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    if tool_name != "verify_journal":
        return True, ""

    doi = tool_args.get("doi", "")
    if not doi or not str(doi).strip():
        return (
            False,
            "doi_required_for_journal: verify_journal requires a non-empty doi.",
        )
    return True, ""
