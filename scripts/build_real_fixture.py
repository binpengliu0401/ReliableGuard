import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.reference import api_client
from src.domain.reference.matcher import title_similarity


REAL_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "domain"
    / "reference"
    / "fixtures"
    / "real_data.json"
)

DOI_URL_PATTERN = re.compile(r"https?://doi\.org/([^\s]+)", re.IGNORECASE)
DOI_PATTERN = re.compile(r"\b(10\.\d{4,}/[^\s]+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\((\d{4})\)")
YEAR_BARE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")
HEADER_PATTERN = re.compile(
    r"^(?:\d+(?:\.\d+)*)?\s*(?:references?|bibliography)$", re.IGNORECASE
)
NUMBERED_REF_START_PATTERN = re.compile(
    r"^(?:\[\d+\]|\d+\s*[\.\)]|[A-Z]\d+\.)\s+"
)
AUTHOR_YEAR_START_PATTERN = re.compile(
    r"^[A-Z][^()]{0,140}\(\d{4}[a-z]?\)",
)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def normalize_author(name: str) -> str:
    # "Breiman, L." -> "l breiman"
    # "Leo Breiman" -> "leo breiman"
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
        normalized_given = []
        for token in given_tokens:
            if len(token) == 1:
                normalized_given.append(token)
            else:
                normalized_given.append(token)
        parts = normalized_given + [surname]
        return " ".join(p for p in parts if p)

    parts = re.split(r"[,\s]+", cleaned.lower())
    return " ".join(p for p in parts if p)


def _clean_doi(doi: str) -> str:
    return doi.strip().rstrip(").,;\"'")


def _extract_doi(text: str) -> str | None:
    url_match = DOI_URL_PATTERN.search(text)
    if url_match:
        return _clean_doi(url_match.group(1))

    doi_match = DOI_PATTERN.search(text)
    if doi_match:
        return _clean_doi(doi_match.group(1))
    return None


def _extract_authors(authors_raw: str) -> list[str]:
    # Prefer "Surname, I." style chunks when present.
    canonical_matches = re.findall(
        r"[A-Z][A-Za-z'`-]+,\s*(?:[A-Z]\.\s*){1,4}",
        authors_raw,
    )
    if canonical_matches:
        return [normalize_author(m) for m in canonical_matches if normalize_author(m)]

    parts = re.split(r"\s*(?:&| and |;)\s*", authors_raw, flags=re.IGNORECASE)
    authors: list[str] = []
    for part in parts:
        cleaned = normalize_author(part.strip(" .;:"))
        if cleaned:
            authors.append(cleaned)
    return authors


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
        or DOI_PATTERN.search(entry)
        or DOI_URL_PATTERN.search(entry)
        or YEAR_BARE_PATTERN.search(entry)
    )


def _extract_reference_fields(entry: str) -> dict:
    compact = re.sub(r"\s+", " ", entry).strip()
    if not compact:
        return {}

    doi = _extract_doi(compact)
    doi_url_match = re.search(r"https?://doi\.org/\S+", compact, flags=re.IGNORECASE)
    doi_match = DOI_PATTERN.search(compact) if doi else None
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
        period_idx = after_year.find(".")
        if period_idx != -1:
            title = after_year[:period_idx].strip(" .:-")
            journal_start = period_idx + 1
            journal_source = after_year[journal_start:]
            if doi_url_match:
                # Cut journal before the DOI URL to avoid "https://doi.org/" prefix leaking in.
                url_in_source = re.search(r"https?://", journal_source, re.IGNORECASE)
                journal = journal_source[: url_in_source.start()].strip(" .:-") if url_in_source else journal_source.strip(" .:-")
            elif doi_match:
                raw_doi_in_source = DOI_PATTERN.search(journal_source)
                journal = journal_source[: raw_doi_in_source.start()].strip(" .:-") if raw_doi_in_source else journal_source.strip(" .:-")
            else:
                journal = journal_source.strip(" .:-")
        else:
            title = after_year.strip(" .:-")
    else:
        # Fallback for IEEE/ACM style: "Author. Title. Journal, 2019." (bare year, no parens).
        bare_match = YEAR_BARE_PATTERN.search(compact)
        if bare_match:
            year = int(bare_match.group(1))
            authors_source = _clean_author_source(compact[: bare_match.start()])
            authors = _extract_authors(authors_source)
            after_bare = compact[bare_match.end():].strip(" .:-")
            # Everything before the year-bearing segment is title+journal; best-effort split.
            pre_year = compact[: bare_match.start()].strip(" .:-")
            parts = [p.strip(" .:-") for p in pre_year.split(".") if p.strip()]
            if len(parts) >= 2:
                title = parts[-2] if len(parts) >= 2 else parts[0]
                journal = parts[-1]
            elif parts:
                title = parts[0]
        else:
            sentence_parts = [p.strip(" .:-") for p in compact.split(".") if p.strip()]
            if sentence_parts:
                title = sentence_parts[0]
            if len(sentence_parts) > 1:
                journal = sentence_parts[1]

    reference = {
        "title": title,
        "authors": authors,
        "doi": doi if doi else "",
        "journal": journal,
        "year": year,
    }
    return reference


def _find_references_section_start(lines: list[str]) -> int:
    """Return the index of the first content line after the References heading.
    Returns 0 if no heading is found (treat entire text as a reference list)."""
    for i, line in enumerate(lines):
        if HEADER_PATTERN.match(line.strip()):
            return i + 1
    return 0


def extract_references_from_pdf(pdf_path: Path) -> list[dict]:
    lines: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text.strip():
                continue
            for raw_line in text.splitlines():
                normalized_line = re.sub(r"\s+", " ", raw_line).strip()
                if normalized_line:
                    lines.append(normalized_line)

    if not lines:
        return []

    # Skip paper body; only parse from the References section onwards.
    # For reference-list-only PDFs (no heading found), ref_start=0 so all lines are used.
    ref_start = _find_references_section_start(lines)
    lines = lines[ref_start:]

    # Stateful line-accumulation parser:
    # start a new reference when we see a new reference-like line.
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
        if not entry:
            continue
        if not _is_reference_candidate(entry):
            continue
        ref = _extract_reference_fields(entry)
        if ref and (ref.get("year") or ref.get("doi")):
            references.append(ref)
    return references


def build_fixture(pdf_paths: list[Path]) -> dict:
    api_client._MODE = "live"

    fixture: dict = {
        "pdfs": {},
        "dois": {},
        "authors": {},
    }

    for pdf_path in pdf_paths:
        references = extract_references_from_pdf(pdf_path)
        fixture["pdfs"][pdf_path.name] = {"references": references}

        for ref in references:
            title = ref.get("title", "") or ""
            title_key = normalize_title(title)
            doi = (ref.get("doi", "") or "").strip()

            # Populate dois from CrossRef (for verify_doi / verify_journal).
            # Compute matches via title comparison so the fixture reflects semantic
            # equivalence, not just DOI existence.
            if doi and doi not in fixture["dois"]:
                crossref_data = api_client.query_doi(doi)
                if crossref_data.get("exists"):
                    ref_title = ref.get("title", "") or ""
                    crossref_title = crossref_data.get("metadata", {}).get("title", "") or ""
                    crossref_data["matches"] = title_similarity(ref_title, crossref_title) >= 0.80
                fixture["dois"][doi] = crossref_data

            # Use PDF-parsed authors as ground truth so the DB (populated by
            # parse_pdf) and fixture["authors"] share the same format.
            # CrossRef metadata is only used for DOI verification, not authors.
            if title_key and title_key not in fixture["authors"]:
                extracted_authors = ref.get("authors", []) or []
                fixture["authors"][title_key] = {
                    "found": len(extracted_authors) > 0,
                    "authors": extracted_authors,
                }

    return fixture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build real_data.json from real PDFs with CrossRef enrichment."
    )
    parser.add_argument(
        "--pdf",
        nargs="+",
        required=True,
        help="One or more PDF file paths",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pdf_paths = [Path(p).expanduser().resolve() for p in args.pdf]

    missing = [str(p) for p in pdf_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"PDF not found: {missing}")

    fixture = build_fixture(pdf_paths)
    REAL_FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REAL_FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote real fixture to {REAL_FIXTURE_PATH}")
    print(f"[OK] PDFs processed: {len(pdf_paths)}")
    print(f"[OK] DOIs indexed: {len(fixture['dois'])}")


if __name__ == "__main__":
    main()
