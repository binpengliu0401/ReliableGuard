"""
Build src/domain/reference/fixtures/real_data.json from tasks/reference_fixture_raw.csv.

Reads S2 and CrossRef hits from the CSV and produces an independent verifier
ground-truth fixture. The agent continues to use mock_data.json; the verifier
reads real_data.json when REFERENCE_API_MODE=real.
"""
import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "tasks" / "reference_fixture_raw.csv"
OUT_PATH = PROJECT_ROOT / "src" / "domain" / "reference" / "fixtures" / "real_data.json"


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def normalize_doi(doi: str) -> str:
    doi = doi.strip().rstrip(".,;\"')")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.lower()


def parse_authors(authors_str: str) -> list[str]:
    if not authors_str.strip():
        return []
    return [a.strip() for a in authors_str.split(";") if a.strip()]


def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    dois: dict = {}
    authors: dict = {}

    for row in rows:
        api_source = row.get("api_source", "")
        if api_source not in ("semantic_scholar", "crossref"):
            continue

        title = row.get("ref_title", "").strip()
        authors_str = row.get("ref_authors", "").strip()
        year_str = row.get("ref_year", "").strip()
        venue = row.get("ref_venue_or_journal", "").strip()
        doi = row.get("ref_doi", "").strip()
        arxiv_id = row.get("ref_arxiv_id", "").strip()

        year = int(year_str) if year_str.isdigit() else None
        author_list = parse_authors(authors_str)

        # Build authors entry keyed by normalized title.
        if title:
            title_key = normalize_title(title)
            if title_key not in authors:
                authors[title_key] = {
                    "found": len(author_list) > 0,
                    "authors": author_list,
                    "year": year,
                    "venue": venue,
                    "doi": doi,
                    "arxiv_id": arxiv_id,
                }

        # Build dois entry.
        if doi:
            doi_key = normalize_doi(doi)
            if doi_key not in dois:
                dois[doi_key] = {
                    "exists": True,
                    "matches": True,
                    "metadata": {
                        "title": title,
                        "journal": venue,
                        "authors": author_list,
                        "year": year,
                    },
                }

        # Also index by arXiv DOI alias so verify_doi works for arXiv papers.
        if arxiv_id and not doi:
            arxiv_doi = f"10.48550/arxiv.{arxiv_id}"
            if arxiv_doi not in dois:
                dois[arxiv_doi] = {
                    "exists": True,
                    "matches": True,
                    "metadata": {
                        "title": title,
                        "journal": venue or "arXiv",
                        "authors": author_list,
                        "year": year,
                    },
                }

    fixture = {"pdfs": {}, "dois": dois, "authors": authors}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote real_data.json")
    print(f"     DOI entries  : {len(dois)}")
    print(f"     Author entries: {len(authors)}")


if __name__ == "__main__":
    main()
