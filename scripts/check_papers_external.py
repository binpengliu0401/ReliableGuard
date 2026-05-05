#!/usr/bin/env python3
import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pdfplumber


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "results" / "paper_external_check"


def main() -> int:
    args = parse_args()
    pdfs = [
        path
        for path in sorted(Path(args.paper_dir).resolve().glob("*.pdf"))
        if not path.name.lower().startswith("reference ")
    ]
    if args.limit:
        pdfs = pdfs[: args.limit]
    source_queries = {
        "semantic_scholar": query_semantic_scholar,
        "crossref": query_crossref,
        "openalex": query_openalex,
        "arxiv": query_arxiv,
    }
    selected_sources = [source_queries[name] for name in args.sources]

    results = []
    for pdf_path in pdfs:
        candidates = title_candidates(pdf_path)
        matches = []
        for query in candidates[:4]:
            for source_query in selected_sources:
                matches.extend(source_query(query))
                if score_match(candidates, best_match(candidates, matches)) >= 0.94:
                    break
            if score_match(candidates, best_match(candidates, matches)) >= 0.94:
                break
            time.sleep(args.delay)

        best = best_match(candidates, matches)
        score = score_match(candidates, best) if best else 0.0
        verdict = decide_verdict(score, best)
        result = {
            "pdf": str(pdf_path.relative_to(REPO_ROOT)),
            "title_candidates": candidates,
            "verdict": verdict,
            "score": round(score, 3),
            "matched": best,
        }
        results.append(result)
        print(f"{pdf_path.name}: {verdict} score={score:.3f} source={(best or {}).get('source', '')}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = OUT_DIR / f"paper_external_check_{run_id}.json"
    md_path = OUT_DIR / f"paper_external_check_{run_id}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(results, run_id), encoding="utf-8")
    print(f"[OK] wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"[OK] wrote {md_path.relative_to(REPO_ROOT)}")
    return 0


def title_candidates(pdf_path: Path) -> list[str]:
    values: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            meta_title = (pdf.metadata or {}).get("Title")
            if meta_title:
                values.append(clean_title(meta_title))
            values.append(filename_title(pdf_path))
            text = pdf.pages[0].extract_text() or ""
            values.extend(first_page_title_candidates(text))
    except Exception:
        pass
    values.append(filename_title(pdf_path))

    seen = set()
    result = []
    for value in values:
        value = clean_title(value)
        for candidate in [value, strip_author_suffix(value)]:
            key = normalize_text(candidate)
            if len(key) < 8 or key in seen:
                continue
            seen.add(key)
            result.append(candidate)
    return result


def first_page_title_candidates(text: str) -> list[str]:
    lines = [clean_title(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    before_abstract = []
    for line in lines[:25]:
        if normalize_text(line) == "abstract":
            break
        if should_skip_header(line):
            continue
        before_abstract.append(line)

    single_line: list[str] = []
    joined_lines: list[str] = []
    for line in before_abstract[:8]:
        if 10 <= len(normalize_text(line)) <= 150 and not looks_like_author_line(line):
            single_line.append(line)

    for width in (2, 3):
        for i in range(min(8, len(before_abstract) - width + 1)):
            joined = " ".join(before_abstract[i : i + width])
            if 18 <= len(normalize_text(joined)) <= 180 and not looks_like_author_line(joined):
                joined_lines.append(joined)
    return joined_lines + single_line


def should_skip_header(line: str) -> bool:
    lowered = normalize_text(line)
    compact = re.sub(r"[^a-z0-9]+", "", line.lower())
    return (
        lowered.startswith("published as")
        or compact.startswith("publishedasaconferencepaper")
        or lowered.startswith("published in")
        or lowered.startswith("provided proper attribution")
        or compact.startswith("providedproperattribution")
        or compact.startswith("reproducethetables")
        or "permission to reproduce" in lowered
        or "permissiontoreproduce" in compact
        or compact in {"scholarlyworks"}
        or lowered.startswith("transactions on machine learning research")
    )


def looks_like_author_line(line: str) -> bool:
    lowered = line.lower()
    return "@" in lowered or lowered.count(",") >= 2 or bool(re.search(r"\d[∗*,†‡]", line))


def strip_author_suffix(value: str) -> str:
    tokens = value.split()
    kept = []
    for token in tokens:
        if any(marker in token for marker in ("∗", "*", "†", "‡")):
            break
        kept.append(token)
    if len(kept) < 3:
        return value
    return " ".join(kept)


def filename_title(pdf_path: Path) -> str:
    stem = pdf_path.stem
    stem = stem.replace("τ", "tau")
    if "-" in stem:
        left, right = stem.split("-", 1)
        stem = f"{left}: {right}"
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def query_semantic_scholar(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "fields": "title,authors,year,venue,url,externalIds",
            "limit": 5,
        }
    )
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    try:
        papers = http_json(url).get("data", [])
    except Exception:
        return []
    results = []
    for paper in papers:
        external = paper.get("externalIds") or {}
        results.append(
            {
                "source": "semantic_scholar",
                "title": paper.get("title") or "",
                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                "year": paper.get("year"),
                "venue": paper.get("venue") or "",
                "doi": external.get("DOI") or "",
                "url": paper.get("url") or "",
            }
        )
    return results


def query_crossref(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": 5})
    url = f"https://api.crossref.org/works?{params}"
    try:
        items = http_json(url).get("message", {}).get("items", [])
    except Exception:
        return []
    return [crossref_item_to_candidate(item) for item in items]


def query_openalex(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per-page": 5,
            "mailto": "local@example.com",
        }
    )
    url = f"https://api.openalex.org/works?{params}"
    try:
        items = http_json(url).get("results", [])
    except Exception:
        return []
    results = []
    for item in items:
        authors = []
        for authorship in item.get("authorships", []) or []:
            author = authorship.get("author") or {}
            if author.get("display_name"):
                authors.append(author["display_name"])
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        doi = item.get("doi") or ""
        if doi.startswith("https://doi.org/"):
            doi = doi.removeprefix("https://doi.org/")
        results.append(
            {
                "source": "openalex",
                "title": item.get("title") or item.get("display_name") or "",
                "authors": authors,
                "year": item.get("publication_year"),
                "venue": source.get("display_name") or "",
                "doi": doi,
                "url": item.get("id") or "",
            }
        )
    return results


def query_arxiv(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": 5,
        }
    )
    url = f"https://export.arxiv.org/api/query?{params}"
    try:
        xml = http_text(url)
    except Exception:
        return []
    root = ET.fromstring(xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("atom:entry", ns):
        title = clean_title((entry.findtext("atom:title", default="", namespaces=ns) or ""))
        authors = [
            clean_title(author.findtext("atom:name", default="", namespaces=ns) or "")
            for author in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", default="", namespaces=ns) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        arxiv_id = entry.findtext("atom:id", default="", namespaces=ns) or ""
        results.append(
            {
                "source": "arxiv",
                "title": title,
                "authors": authors,
                "year": year,
                "venue": "arXiv",
                "doi": "",
                "url": arxiv_id,
            }
        )
    return results


def crossref_item_to_candidate(item: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in item.get("author", []) or []:
        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
        if name:
            authors.append(name)
    return {
        "source": "crossref",
        "title": (item.get("title") or [""])[0],
        "authors": authors,
        "year": extract_year(item),
        "venue": (item.get("container-title") or [""])[0],
        "doi": item.get("DOI") or "",
        "url": item.get("URL") or "",
    }


def extract_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = (item.get(key) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def score_match(candidates: list[str], match: dict[str, Any] | None) -> float:
    if not match:
        return 0.0
    title = str(match.get("title") or "")
    return max((title_similarity(candidate, title) for candidate in candidates), default=0.0)


def best_match(candidates: list[str], matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(matches, key=lambda item: score_match(candidates, item), default=None)


def decide_verdict(score: float, match: dict[str, Any] | None) -> str:
    if not match:
        return "not_found"
    if score >= 0.94:
        return "verified"
    if score >= 0.80:
        return "needs_review"
    return "unverified"


def render_markdown(results: list[dict[str, Any]], run_id: str) -> str:
    counts = Counter(item["verdict"] for item in results)
    lines = [
        "# External Paper Check",
        "",
        f"Generated: {run_id}",
        "",
        f"Summary: {json.dumps(dict(counts), ensure_ascii=False)}",
        "",
        "Each PDF was checked as a paper-level item. The checker extracted title candidates from the first page and filename, then queried Semantic Scholar and CrossRef.",
        "",
        "| # | PDF | Verdict | Score | Query title | Matched title | Matched DOI/URL | Source |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(results, 1):
        match = item.get("matched") or {}
        lines.append(
            "| {index} | {pdf} | `{verdict}` | {score:.3f} | {query} | {matched} | {url} | {source} |".format(
                index=index,
                pdf=escape_cell(item["pdf"]),
                verdict=item["verdict"],
                score=item["score"],
                query=escape_cell((item.get("title_candidates") or [""])[0]),
                matched=escape_cell(str(match.get("title") or "")),
                url=escape_cell(str(match.get("doi") or match.get("url") or "")),
                source=escape_cell(str(match.get("source") or "")),
            )
        )
    return "\n".join(lines)


def title_similarity(a: str, b: str) -> float:
    left = normalize_text(a)
    right = normalize_text(b)
    char_score = difflib.SequenceMatcher(None, left, right).ratio()
    word_score = difflib.SequenceMatcher(None, left.split(), right.split()).ratio()
    length_penalty = min(len(left), len(right)) / max(len(left), len(right), 1)
    return 0.45 * char_score + 0.45 * word_score + 0.10 * length_penalty


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("–", "-").replace("—", "-").replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_title(value: str) -> str:
    value = value.replace("|", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value.strip(" .:-")


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def http_json(url: str) -> dict[str, Any]:
    return json.loads(http_text(url))


def http_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ReliableGuard paper checker (mailto:local@example.com)"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-dir", default="tasks/papers")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["semantic_scholar", "crossref", "openalex", "arxiv"],
        default=["semantic_scholar", "crossref", "openalex"],
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
