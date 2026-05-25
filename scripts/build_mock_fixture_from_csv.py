"""
Rebuild mock_data.json from real CSV data using actual paper names.

Replaces fictional paper names (paper_f0.pdf etc.) with real papers from
tasks/reference_fixture_raw.csv. Also writes paper_name_mapping.json for use by
the scenario update script.
"""
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "tasks" / "reference_fixture_raw.csv"
OUT_PATH = PROJECT_ROOT / "src" / "domain" / "reference" / "fixtures" / "mock_data.json"
MAPPING_PATH = PROJECT_ROOT / "tasks" / "paper_name_mapping.json"

# Maps CSV source_paper name → new PDF filename and failure mode role.
PAPER_SELECTION = {
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
    "paper_f4.pdf": "paper_f4.pdf",     # keep empty-refs fixture as-is
    "paper_f5.pdf": "cognitive_arch.pdf",
}

MAX_REFS_PER_PAPER = 10


def build_refs(rows: list[dict], source_paper: str) -> list[dict]:
    hits = [
        r for r in rows
        if r["source_paper"] == source_paper
        and r.get("api_source") in ("semantic_scholar", "crossref")
        and r.get("ref_title", "").strip()
        and r.get("ref_authors", "").strip()
    ]
    refs = []
    for i, r in enumerate(hits[:MAX_REFS_PER_PAPER], start=1):
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
        })
    return refs


def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pdfs: dict = {}

    for source_paper, pdf_name in PAPER_SELECTION.items():
        refs = build_refs(rows, source_paper)
        pdfs[pdf_name] = {
            "paper_id": pdf_name.replace(".pdf", ""),
            "source": source_paper,
            "references": refs,
        }
        print(f"  {pdf_name}: {len(refs)} references")

    # Keep the empty-refs fixture for F4 (verifier detects parse returning nothing).
    pdfs["paper_f4.pdf"] = {
        "paper_id": "paper_f4",
        "source": "synthetic",
        "references": [],
    }

    # Build dois and authors from the selected papers' references for mock-mode lookup.
    dois: dict = {}
    authors_map: dict = {}
    for pdf_data in pdfs.values():
        for ref in pdf_data.get("references", []):
            doi = ref.get("doi", "").strip()
            title = ref.get("title", "").strip()
            auth = ref.get("authors", [])
            year = ref.get("year")
            journal = ref.get("journal", "")
            if doi:
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

    print(f"\n[OK] mock_data.json: {len(pdfs)} PDFs, {len(dois)} DOIs, {len(authors_map)} author entries")
    print(f"[OK] paper_name_mapping.json written to {MAPPING_PATH}")


if __name__ == "__main__":
    main()
