from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_USER_AGENT = "ReliableGuard verifier source (local research prototype)"


def http_json(url: str, *, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def encode_params(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})


def claim_title(claim) -> str | None:
    if claim.attribute == "title" and claim.value is not None:
        return str(claim.value)
    value = claim.entities.get("paper_title") or claim.entities.get("title")
    return str(value).strip() if value is not None and str(value).strip() else None


def claim_authors(claim) -> list[str]:
    raw = claim.value if claim.attribute == "authors" and claim.value is not None else claim.entities.get("authors")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw]
    return []


def claim_year(claim) -> int | None:
    raw = claim.value if claim.attribute == "year" and claim.value is not None else claim.entities.get("year")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def claim_doi(claim) -> str | None:
    raw = claim.entities.get("doi") or (claim.value if claim.attribute == "doi" else None)
    return str(raw).strip() if raw else None


def claim_url(claim) -> str | None:
    raw = claim.entities.get("url") or (claim.value if claim.attribute == "url" else None)
    return str(raw).strip() if raw else None


def bibliographic_query(claim) -> str:
    parts = [claim_title(claim) or "", " ".join(claim_authors(claim)), str(claim_year(claim) or "")]
    return " ".join(part for part in parts if part).strip()


def extract_crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = (item.get(key) or {}).get("date-parts")
        if date_parts and date_parts[0] and date_parts[0][0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError):
                return None
    return None


def crossref_item_to_evidence(source: str, item: dict[str, Any]):
    from src.reliableguard.verifier.sources.base import Evidence

    authors = []
    for author in item.get("author", []) or []:
        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
        if name:
            authors.append(name)

    return Evidence(
        source=source,
        found=True,
        title=(item.get("title") or [""])[0],
        authors=authors,
        year=extract_crossref_year(item),
        venue=(item.get("container-title") or [""])[0],
        doi=item.get("DOI") or "",
        url=item.get("URL") or "",
        raw=item,
    )
