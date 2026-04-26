import json
import os
import re
from pathlib import Path
from typing import Any

_MODE = os.environ.get("REFERENCE_API_MODE", "mock").lower()
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_data.json"
_REAL_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "real_data.json"

_mock_cache: dict[str, Any] | None = None
_real_cache: dict[str, Any] | None = None

DOI_URL_PATTERN = re.compile(r"https?://doi\.org/([^\s]+)", re.IGNORECASE)
DOI_PATTERN = re.compile(r"\b(10\.\d{4,}/[^\s]+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\((\d{4})\)")
YEAR_BARE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")
HEADER_PATTERN = re.compile(
    r"^(?:\d+(?:\.\d+)*)?\s*(?:references?|bibliography)$",
    re.IGNORECASE,
)
NUMBERED_REF_START_PATTERN = re.compile(
    r"^(?:\[\d+\]|\d+\s*[\.\)]|[A-Z]\d+\.)\s+"
)
AUTHOR_YEAR_START_PATTERN = re.compile(r"^[A-Z][^()]{0,140}\(\d{4}[a-z]?\)")


def _load_mock() -> dict[str, Any]:
    global _mock_cache
    if _mock_cache is None:
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Mock reference fixture must be a JSON object: {_FIXTURE_PATH}"
            )
        _mock_cache = loaded
    return _mock_cache


def _load_real() -> dict[str, Any]:
    global _real_cache
    if _real_cache is None:
        with open(_REAL_FIXTURE_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Real reference fixture must be a JSON object: {_REAL_FIXTURE_PATH}"
            )
        _real_cache = loaded
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

    # live mode is intended for demos: parse the local PDF directly.
    return _extract_references_from_pdf(_resolve_pdf_path(pdf_path))


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


def _resolve_pdf_path(pdf_path: str) -> Path:
    path = Path(pdf_path)
    if path.exists():
        return path

    candidates = [
        Path.cwd() / pdf_path,
        Path.cwd() / "tasks" / "papers" / Path(pdf_path).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"PDF not found: {pdf_path}")


def _extract_references_from_pdf(pdf_path: Path) -> list[dict]:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = re.sub(r"\s+", " ", raw_line).strip()
                if line:
                    lines.append(line)

    if not lines:
        return []

    ref_start = _find_references_section_start(lines)
    lines = lines[ref_start:]

    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if _is_header_line(line):
            continue
        if not current:
            current = [line]
            continue
        if _looks_like_reference_start(line) and _is_reference_candidate(" ".join(current)):
            blocks.append(" ".join(current))
            current = [line]
            continue
        current.append(line)

    if current:
        blocks.append(" ".join(current))

    references: list[dict] = []
    for block in blocks:
        entry = re.sub(r"\s+", " ", block).strip()
        if not entry or not _is_reference_candidate(entry):
            continue
        ref = _extract_reference_fields(entry)
        if ref and (ref.get("year") or ref.get("doi")):
            references.append(ref)
    return references


def _find_references_section_start(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if HEADER_PATTERN.match(line.strip()):
            return i + 1
    return 0


def _is_header_line(line: str) -> bool:
    return bool(HEADER_PATTERN.match(line.strip()))


def _looks_like_reference_start(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    return bool(
        NUMBERED_REF_START_PATTERN.match(line)
        or AUTHOR_YEAR_START_PATTERN.match(line)
    )


def _is_reference_candidate(entry: str) -> bool:
    return bool(
        YEAR_PATTERN.search(entry)
        or YEAR_BARE_PATTERN.search(entry)
        or DOI_PATTERN.search(entry)
        or DOI_URL_PATTERN.search(entry)
    )


def _extract_reference_fields(entry: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", " ", entry).strip()
    doi = _extract_doi(compact)
    year_match = YEAR_PATTERN.search(compact)

    year = None
    title = ""
    journal = ""
    authors: list[str] = []

    if year_match and 1900 <= int(year_match.group(1)) <= 2099:
        year = int(year_match.group(1))
        authors_source = _clean_author_source(compact[: year_match.start()])
        authors = _extract_authors(authors_source)
        after_year = compact[year_match.end() :].strip(" .:-")
        title, journal = _split_title_journal(after_year)
    else:
        bare_match = YEAR_BARE_PATTERN.search(compact)
        if bare_match:
            year = int(bare_match.group(1))
            authors_source = _clean_author_source(compact[: bare_match.start()])
            authors = _extract_authors(authors_source)
            pre_year = compact[: bare_match.start()].strip(" .:-")
            parts = [p.strip(" .:-") for p in pre_year.split(".") if p.strip()]
            if len(parts) >= 2:
                title = parts[-2]
                journal = parts[-1]
            elif parts:
                title = parts[0]
        else:
            title, journal = _split_title_journal(compact)

    if doi:
        journal = _trim_doi_from_text(journal)

    return {
        "title": title,
        "authors": authors,
        "doi": doi or "",
        "journal": journal,
        "year": year,
    }


def _split_title_journal(text: str) -> tuple[str, str]:
    parts = [p.strip(" .:-") for p in text.split(".") if p.strip(" .:-")]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:]).strip(" .:-")


def _extract_doi(text: str) -> str | None:
    url_match = DOI_URL_PATTERN.search(text)
    if url_match:
        return _clean_doi(url_match.group(1))
    doi_match = DOI_PATTERN.search(text)
    if doi_match:
        return _clean_doi(doi_match.group(1))
    return None


def _clean_doi(doi: str) -> str:
    return doi.strip().rstrip(").,;\"'")


def _trim_doi_from_text(text: str) -> str:
    url_match = re.search(r"https?://doi\.org/\S+", text, flags=re.IGNORECASE)
    if url_match:
        return text[: url_match.start()].strip(" .:-")
    doi_match = DOI_PATTERN.search(text)
    if doi_match:
        return text[: doi_match.start()].strip(" .:-")
    return text.strip(" .:-")


def _clean_author_source(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^(?:\d+(?:\.\d+)*)?\s*references?\b[:\s-]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:\[\d+\]|\d+\s*[\.\)])\s*", "", cleaned)
    return cleaned.strip()


def _extract_authors(authors_raw: str) -> list[str]:
    canonical_matches = re.findall(
        r"[A-Z][A-Za-z'`-]+,\s*(?:[A-Z]\.\s*){1,4}",
        authors_raw,
    )
    if canonical_matches:
        return [
            _normalize_author(match)
            for match in canonical_matches
            if _normalize_author(match)
        ]

    parts = re.split(r"\s*(?:&| and |;)\s*", authors_raw, flags=re.IGNORECASE)
    authors: list[str] = []
    for part in parts:
        cleaned = _normalize_author(part.strip(" .;:"))
        if cleaned:
            authors.append(cleaned)
    return authors


def _normalize_author(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip())
    if not cleaned:
        return ""
    if "," in cleaned:
        left, right = cleaned.split(",", 1)
        surname = left.strip().lower()
        given_tokens = [
            token.strip(". ").lower()
            for token in re.split(r"\s+", right.strip())
            if token.strip(". ")
        ]
        return " ".join(given_tokens + [surname]).strip()
    parts = re.split(r"[,\s]+", cleaned.lower())
    return " ".join(part for part in parts if part)
