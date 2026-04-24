import json
import os
import re
from pathlib import Path
from typing import Any

_MODE = os.environ.get("REFERENCE_API_MODE", "mock").lower()
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_data.json"
_REAL_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "real_data.json"

_mock_cache: dict | None = None
_real_cache: dict | None = None


def _load_mock() -> dict:
    global _mock_cache
    if _mock_cache is None:
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            _mock_cache = json.load(f)
    return _mock_cache  # type: ignore


def _load_real() -> dict:
    global _real_cache
    if _real_cache is None:
        with open(_REAL_FIXTURE_PATH, "r", encoding="utf-8") as f:
            _real_cache = json.load(f)
    return _real_cache


# parse_pdf
def get_references_from_pdf(pdf_path: str) -> list[dict]:
    if _MODE == "mock":
        data = _load_mock()
        key = Path(pdf_path).name
        return data.get("pdfs", {}).get(key, {}).get("references", [])
    elif _MODE == "real":
        data = _load_real()
        key = Path(pdf_path).name
        return data.get("pdfs", {}).get(key, {}).get("references", [])

    # live mode: real PDF parsing not implemented in MVP
    raise NotImplementedError(
        "Live PDF parsing not implemented. Use REFERENCE_API_MODE=mock."
    )


# verify_doi
def query_doi(doi: str) -> dict[str, Any]:
    if _MODE == "mock":
        data = _load_mock()
        entry = data.get("dois", {}).get(doi)
        if entry is None:
            return {"exists": False, "matches": False, "metadata": {}}
        return entry
    elif _MODE == "real":
        data = _load_real()
        entry = data.get("dois", {}).get(doi)
        if entry is None:
            return {"exists": False, "matches": False, "metadata": {}}
        return entry

    # live mode
    import urllib.request
    import urllib.error

    url = f"https://api.crossref.org/works/{doi}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
        item = raw["message"]
        metadata = {
            "title": item.get("title", [""])[0],
            "journal": (item.get("container-title") or [""])[0],
            "authors": [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            ],
            "year": (
                item.get("published-print") or item.get("published-online") or {}
            ).get("date-parts", [[None]])[0][0],
        }
        return {"exists": True, "matches": True, "metadata": metadata}
    except urllib.error.HTTPError:
        return {"exists": False, "matches": False, "metadata": {}}


# verify_authors
def query_authors(title: str) -> dict[str, Any]:
    if _MODE == "mock":
        data = _load_mock()
        key = _normalize_title(title)  # type: ignore
        entry = data.get("authors", {}).get(key)
        if entry is None:
            return {"found": False, "authors": []}
        return entry
    elif _MODE == "real":
        data = _load_real()
        key = _normalize_title(title)  # type: ignore
        entry = data.get("authors", {}).get(key)
        if entry is None:
            return {"found": False, "authors": []}
        return entry

    # live mode
    import urllib.request
    import urllib.parse

    params = urllib.parse.urlencode(
        {
            "query": title,
            "fields": "authors",
            "limit": 1,
        }
    )
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
        papers = raw.get("data", [])
        if not papers:
            return {"found": False, "authors": []}
        authors = [a["name"] for a in papers[0].get("authors", [])]
        return {"found": True, "authors": authors}
    except Exception:
        return {"found": False, "authors": []}


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())
