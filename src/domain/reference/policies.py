from src.domain.registry import policy


@policy("batch_size_limit")
def batch_size_limit(func_name: str, func_args: dict) -> tuple[bool, str]:
    ref_id = func_args.get("ref_id")
    if isinstance(ref_id, list) and len(ref_id) > 10:
        return (
            False,
            f"batch_size_limit: ref_id list exceeds max 10, got {len(ref_id)}.",
        )
    return True, ""


@policy("doi_required_for_journal")
def doi_required_for_journal(func_name: str, func_args: dict) -> tuple[bool, str]:
    if func_name != "verify_journal":
        return True, ""
    doi = func_args.get("doi", "")
    if not doi or not doi.strip():
        return (
            False,
            "doi_required_for_journal: verify_journal requires a non-empty doi.",
        )
    return True, ""
