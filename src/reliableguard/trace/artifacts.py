from __future__ import annotations

from datetime import datetime, timezone


RUN_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def make_run_stamp(started_at: datetime | None = None) -> str:
    dt = started_at or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(RUN_STAMP_FORMAT)


def build_run_id(domain: str, run_stamp: str) -> str:
    return f"{domain}_{run_stamp}"
