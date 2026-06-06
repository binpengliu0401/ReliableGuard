"""
Rebuild mock_data.json from real CSV data using actual paper names.

Includes all papers from tasks/reference_fixture_raw.csv (no per-paper cap).
The five scenario papers keep their established fixture names; the remaining
papers get slugified names. All references from all papers are included so that
the verifier's title/DOI/author lookup tables cover the full 835-row corpus.
Also writes paper_name_mapping.json for use by the scenario update script.
"""
import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "tasks" / "reference_fixture_raw.csv"
OUT_PATH = PROJECT_ROOT / "src" / "domain" / "reference" / "fixtures" / "mock_data.json"
MAPPING_PATH = PROJECT_ROOT / "tasks" / "paper_name_mapping.json"

# Five scenario papers: keep established fixture names used in reference_scenarios.json.
SCENARIO_PAPERS = {
    "ReAct- Synergizing Reasoning and Acting in Language Models": "react.pdf",
    "CRITIC- Large Language Models Can Self-Correct with Tool-Interactive Critiquing": "critic.pdf",
    "Gorilla- Large Language Model Connected with Massive APIs": "gorilla.pdf",
    "Reflexion- Language Agents with Verbal Reinforcement Learning": "reflexion.pdf",
    "Cognitive Architectures for Language Agents": "cognitive_arch.pdf",
}

# Old fictional name → new real PDF name (for scenario update).
NAME_MAPPING = {
    "paper_f0.pdf": "react.pdf",
    "paper_f2.pdf": "critic.pdf",
    "paper_f3.pdf": "gorilla.pdf",
    "paper_nodoi.pdf": "reflexion.pdf",
    "paper_invaliddoi.pdf": "reflexion.pdf",
    "paper_nonexistent_doi.pdf": "critic.pdf",
    "paper_f4.pdf": "paper_f4.pdf",
    "paper_f5.pdf": "cognitive_arch.pdf",
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:40]


def build_refs(rows: list[dict], source_paper: str) -> list[dict]:
    hits = [
        r for r in rows
        if r["source_paper"] == source_paper
        and r.get("api_source") in ("semantic_scholar", "crossref")
        and r.get("ref_title", "").strip()
        and r.get("ref_authors", "").strip()
    ]
    refs = []
    for i, r in enumerate(hits, start=1):
        authors_raw = r.get("ref_authors", "")
        authors = [a.strip() for a in authors_raw.split(";") if a.strip()]
        year_str = r.get("ref_year", "")
        refs.append({
            "ref_id": i,
            "title": r.get("ref_title", "").strip(),
            "authors": authors,
            "doi": r.get("ref_doi", "").strip(),
            "journal": r.get("ref_venue_or_journal", "").strip(),
            "year": int(year_str) if year_str.isdigit() else None,
            "doi_status": "verified" if r.get("ref_doi", "").strip() else "no_doi",
            "provenance": "real_paper",
        })
    return refs


def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Collect all distinct source papers from the CSV.
    all_source_papers = list(dict.fromkeys(r["source_paper"] for r in rows))

    pdfs: dict = {}

    for source_paper in all_source_papers:
        if source_paper in SCENARIO_PAPERS:
            pdf_name = SCENARIO_PAPERS[source_paper]
        else:
            pdf_name = _slugify(source_paper) + ".pdf"

        refs = build_refs(rows, source_paper)
        pdfs[pdf_name] = {
            "paper_id": pdf_name.replace(".pdf", ""),
            "provenance": "real_paper",
            "source": source_paper,
            "references": refs,
        }
        print(f"  {pdf_name}: {len(refs)} references")

    # Synthetic empty-refs fixture for F4 (verifier detects parse returning nothing).
    pdfs["paper_f4.pdf"] = {
        "paper_id": "paper_f4",
        "provenance": "synthetic",
        "source": "synthetic",
        "references": [],
    }

    # Build dois and authors lookup tables from ALL references across all papers.
    dois: dict = {}
    authors_map: dict = {}
    for pdf_data in pdfs.values():
        for ref in pdf_data.get("references", []):
            doi = ref.get("doi", "").strip()
            title = ref.get("title", "").strip()
            auth = ref.get("authors", [])
            year = ref.get("year")
            journal = ref.get("journal", "")
            if doi and doi not in dois:
                dois[doi] = {
                    "exists": True,
                    "matches": True,
                    "metadata": {
                        "title": title,
                        "journal": journal,
                        "authors": auth,
                        "year": year,
                    },
                }
            if title:
                key = title.strip().lower()
                if key not in authors_map:
                    authors_map[key] = {"found": len(auth) > 0, "authors": auth}

    fixture = {"pdfs": pdfs, "dois": dois, "authors": authors_map}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(NAME_MAPPING, f, ensure_ascii=False, indent=2)

    total_refs = sum(len(p.get("references", [])) for p in pdfs.values())
    print(f"\n[OK] mock_data.json: {len(pdfs)} PDFs, {total_refs} refs, "
          f"{len(dois)} DOIs, {len(authors_map)} author entries")
    print(f"[OK] paper_name_mapping.json written to {MAPPING_PATH}")


if __name__ == "__main__":
    main()
