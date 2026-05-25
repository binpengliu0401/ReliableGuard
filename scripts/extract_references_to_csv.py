"""
Extract references from PDFs in tasks/papers/, query APIs for metadata,
and write results to tasks/reference_fixture_raw.csv.
"""
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests
from dotenv import load_dotenv

load_dotenv()
_S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

PAPERS_DIR = Path(__file__).parent.parent / "tasks" / "papers"
OUTPUT_CSV = Path(__file__).parent.parent / "tasks" / "reference_fixture_raw.csv"

SKIP_FILES = {
    "reference 1.pdf",
    "reference 2.pdf",
    "reference 1.original.pdf",
    "reference 2.original.pdf",
}

ARXIV_PATTERN = re.compile(r'arXiv[:\s](\d{4}\.\d{4,5})|arxiv\.org/abs/(\d{4}\.\d{4,5})', re.IGNORECASE)
DOI_PATTERN = re.compile(r'\b(10\.\d{4,}/[^\s,;\]>]+)')
URL_PATTERN = re.compile(r'https?://[^\s>]+')
DOI_URL_PATTERN = re.compile(r'doi\.org/|arxiv\.org/', re.IGNORECASE)

CSV_FIELDS = [
    "source_paper", "ref_title", "ref_authors", "ref_year",
    "ref_venue_or_journal", "ref_doi", "ref_arxiv_id", "ref_url", "api_source",
]


def strip_trailing(s: str) -> str:
    return s.rstrip('.,;)"')


def find_references_start(pages_text: list[str]) -> int:
    """Return index of first page that contains a References heading."""
    for i, text in enumerate(pages_text):
        if re.search(r'^\s*References\s*$', text, re.MULTILINE | re.IGNORECASE):
            return i
    # Fallback: last 25% of document
    return max(0, len(pages_text) - max(1, len(pages_text) // 4))


def extract_identifiers(pdf_path: Path) -> dict:
    """Extract arXiv IDs, DOIs, and URLs from the references section of a PDF."""
    arxiv_ids: set[str] = set()
    dois: set[str] = set()
    urls: set[str] = set()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                pages_text.append(text)

        ref_start = find_references_start(pages_text)
        ref_text = "\n".join(pages_text[ref_start:])

        for m in ARXIV_PATTERN.finditer(ref_text):
            arxiv_ids.add(m.group(1) or m.group(2))

        for m in DOI_PATTERN.finditer(ref_text):
            dois.add(strip_trailing(m.group(1)))

        for m in URL_PATTERN.finditer(ref_text):
            url = strip_trailing(m.group(0))
            if not DOI_URL_PATTERN.search(url) and not ARXIV_PATTERN.search(url):
                urls.add(url)

    except Exception as e:
        print(f"  WARNING: could not read {pdf_path.name}: {e}", file=sys.stderr)

    return {"arxiv_ids": arxiv_ids, "dois": dois, "urls": urls}


def fetch_semantic_scholar(arxiv_id: str, cache: dict) -> dict:
    key = f"arxiv:{arxiv_id}"
    if key in cache:
        return cache[key]

    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields=title,authors,year,venue,externalIds"
    headers = {"x-api-key": _S2_API_KEY} if _S2_API_KEY else {}
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                authors = "; ".join(a.get("name", "") for a in data.get("authors", []))
                ext_ids = data.get("externalIds", {})
                result = {
                    "ref_title": data.get("title", ""),
                    "ref_authors": authors,
                    "ref_year": str(data.get("year", "")),
                    "ref_venue_or_journal": data.get("venue", ""),
                    "ref_doi": ext_ids.get("DOI", ""),
                    "ref_arxiv_id": arxiv_id,
                    "ref_url": "",
                    "api_source": "semantic_scholar",
                }
                break
            elif resp.status_code == 429:
                print(f"  WARNING: rate limited on arXiv:{arxiv_id}, waiting 15s (attempt {attempt+1}/2)", file=sys.stderr)
                time.sleep(15)
                result = _empty_result(arxiv_id=arxiv_id)
            else:
                result = _empty_result(arxiv_id=arxiv_id)
                break
        except Exception as e:
            print(f"  WARNING: semantic scholar request failed for {arxiv_id}: {e}", file=sys.stderr)
            result = _empty_result(arxiv_id=arxiv_id)
            break

    cache[key] = result
    time.sleep(2)
    return result


def fetch_crossref(doi: str, cache: dict) -> dict:
    key = f"doi:{doi}"
    if key in cache:
        return cache[key]

    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            msg = resp.json().get("message", {})
            title_list = msg.get("title", [])
            title = title_list[0] if title_list else ""
            authors = "; ".join(
                f"{a.get('family', '')} {a.get('given', '')}".strip()
                for a in msg.get("author", [])
            )
            year_parts = msg.get("published", {}).get("date-parts", [[""]])
            year = str(year_parts[0][0]) if year_parts and year_parts[0] else ""
            container = msg.get("container-title", [])
            venue = container[0] if container else ""
            result = {
                "ref_title": title,
                "ref_authors": authors,
                "ref_year": year,
                "ref_venue_or_journal": venue,
                "ref_doi": doi,
                "ref_arxiv_id": "",
                "ref_url": "",
                "api_source": "crossref",
            }
        else:
            if resp.status_code == 429:
                print(f"  WARNING: rate limited on DOI:{doi}", file=sys.stderr)
            result = _empty_result(doi=doi)
    except Exception as e:
        print(f"  WARNING: crossref request failed for {doi}: {e}", file=sys.stderr)
        result = _empty_result(doi=doi)

    cache[key] = result
    time.sleep(0.5)
    return result


def _empty_result(arxiv_id: str = "", doi: str = "", url: str = "") -> dict:
    return {
        "ref_title": "",
        "ref_authors": "",
        "ref_year": "",
        "ref_venue_or_journal": "",
        "ref_doi": doi,
        "ref_arxiv_id": arxiv_id,
        "ref_url": url,
        "api_source": "none",
    }


def build_rows(source_paper: str, identifiers: dict, api_cache: dict, dry_run: bool) -> list[dict]:
    rows = []

    arxiv_fetched_dois: set[str] = set()

    for arxiv_id in sorted(identifiers["arxiv_ids"]):
        if dry_run:
            rows.append({**_empty_result(arxiv_id=arxiv_id), "source_paper": source_paper})
            continue
        result = fetch_semantic_scholar(arxiv_id, api_cache)
        if result.get("ref_doi"):
            arxiv_fetched_dois.add(result["ref_doi"])
        rows.append({"source_paper": source_paper, **result})

    for doi in sorted(identifiers["dois"]):
        if doi in arxiv_fetched_dois:
            continue
        if dry_run:
            rows.append({**_empty_result(doi=doi), "source_paper": source_paper})
            continue
        result = fetch_crossref(doi, api_cache)
        rows.append({"source_paper": source_paper, **result})

    for url in sorted(identifiers["urls"]):
        rows.append({**_empty_result(url=url), "source_paper": source_paper})

    return rows


def retry_failed(output_csv: Path) -> None:
    """Read existing CSV, retry api_source=none rows that have an arXiv ID."""
    if not output_csv.exists():
        print("CSV not found, run without --retry-failed first.", file=sys.stderr)
        sys.exit(1)

    with open(output_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    to_retry = [r for r in rows if r.get("api_source") == "none" and r.get("ref_arxiv_id", "").strip()]
    print(f"Retrying {len(to_retry)} arXiv rows with api_source=none (sleep=2s, 2 attempts on 429)...")

    cache: dict = {}
    updated = 0
    for row in rows:
        if row.get("api_source") == "none" and row.get("ref_arxiv_id", "").strip():
            result = fetch_semantic_scholar(row["ref_arxiv_id"], cache)
            if result.get("api_source") == "semantic_scholar":
                row.update(result)
                updated += 1

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Updated {updated}/{len(to_retry)} rows. CSV rewritten to {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Extract references from PDFs to CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Extract IDs only, no API calls.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry api_source=none arXiv rows in existing CSV.")
    args = parser.parse_args()

    if args.retry_failed:
        retry_failed(OUTPUT_CSV)
        return

    pdf_files = sorted(
        p for p in PAPERS_DIR.glob("*.pdf") if p.name not in SKIP_FILES
    )

    if not pdf_files:
        print("No PDF files found in tasks/papers/", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict] = []
    api_cache: dict = {}

    for pdf_path in pdf_files:
        identifiers = extract_identifiers(pdf_path)
        n_arxiv = len(identifiers["arxiv_ids"])
        n_doi = len(identifiers["dois"])
        print(f"Processing: {pdf_path.name} — found {n_arxiv} arXiv IDs, {n_doi} DOIs")

        source_name = pdf_path.stem
        rows = build_rows(source_name, identifiers, api_cache, dry_run=args.dry_run)
        all_rows.extend(rows)

    if args.dry_run:
        print(f"\nDry-run complete. Total identifiers found: {len(all_rows)}")
        return

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
