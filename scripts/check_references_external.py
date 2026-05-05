#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import difflib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "src" / "domain" / "reference" / "fixtures" / "real_data.json"
OUT_DIR = REPO_ROOT / "results" / "reference_external_check"


def main() -> int:
    args = _parse_args()
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    results = []
    for pdf_name in args.pdf:
        refs = data["pdfs"][pdf_name]["references"]
        for index, ref in enumerate(refs, 1):
            result = verify_reference(pdf_name, index, ref)
            results.append(result)
            print(
                f"{pdf_name} #{index}: {result['verdict']} "
                f"title={result['title_score']:.3f} authors={result['author_score']:.3f} "
                f"source={result['source']}"
            )
            time.sleep(args.delay)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = OUT_DIR / f"external_reference_check_{run_id}.json"
    md_path = OUT_DIR / f"external_reference_check_{run_id}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(results, run_id), encoding="utf-8")
    print(f"[OK] wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"[OK] wrote {md_path.relative_to(REPO_ROOT)}")
    return 0


def verify_reference(pdf_name: str, index: int, ref: dict[str, Any]) -> dict[str, Any]:
    doi = str(ref.get("doi") or "").strip()
    if doi:
        candidates = [query_crossref_doi(doi)]
        source = "crossref_doi"
    else:
        candidates = query_metadata(ref)
        source = "metadata_fallback"

    candidates = [candidate for candidate in candidates if candidate]
    best = max(candidates, key=lambda candidate: score_candidate(ref, candidate)["overall"], default=None)
    scores = score_candidate(ref, best) if best else empty_scores()
    verdict = decide_verdict(ref, best, scores, doi_present=bool(doi))

    return {
        "pdf": pdf_name,
        "index": index,
        "source": source,
        "verdict": verdict,
        "extracted": ref,
        "matched": best,
        "title_score": round(scores["title"], 3),
        "author_score": round(scores["authors"], 3),
        "year_match": scores["year_match"],
        "venue_score": round(scores["venue"], 3),
        "overall_score": round(scores["overall"], 3),
        "reason": reason_for(verdict, doi_present=bool(doi), matched=best, scores=scores),
    }


def query_crossref_doi(doi: str) -> dict[str, Any] | None:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    try:
        message = http_json(url).get("message", {})
    except Exception as exc:
        return {"source": "crossref", "found": False, "error": str(exc), "doi": doi}
    return crossref_item_to_candidate(message)


def query_metadata(ref: dict[str, Any]) -> list[dict[str, Any]]:
    title = str(ref.get("title") or "")
    year = ref.get("year")
    authors = ref.get("authors") or []
    query = " ".join([title, " ".join(str(a) for a in authors), str(year or "")]).strip()

    candidates: list[dict[str, Any]] = []
    candidates.extend(query_semantic_scholar(title))
    candidates.extend(query_crossref_bibliographic(query))
    return candidates


def query_semantic_scholar(title: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query": title,
            "fields": "title,authors,year,venue,url,externalIds",
            "limit": 5,
        }
    )
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    try:
        papers = http_json(url).get("data", [])
    except Exception:
        return []

    candidates = []
    for paper in papers:
        external = paper.get("externalIds") or {}
        candidates.append(
            {
                "source": "semantic_scholar",
                "found": True,
                "title": paper.get("title") or "",
                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                "year": paper.get("year"),
                "venue": paper.get("venue") or "",
                "doi": external.get("DOI") or "",
                "url": paper.get("url") or "",
            }
        )
    return candidates


def query_crossref_bibliographic(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": 5})
    url = f"https://api.crossref.org/works?{params}"
    try:
        items = http_json(url).get("message", {}).get("items", [])
    except Exception:
        return []
    return [crossref_item_to_candidate(item) for item in items]


def crossref_item_to_candidate(item: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in item.get("author", []) or []:
        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
        if name:
            authors.append(name)
    return {
        "source": "crossref",
        "found": True,
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


def score_candidate(ref: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    if not candidate or not candidate.get("found"):
        return empty_scores()
    title = title_similarity(str(ref.get("title") or ""), str(candidate.get("title") or ""))
    authors = author_overlap(ref.get("authors") or [], candidate.get("authors") or [])
    ref_year = ref.get("year")
    cand_year = candidate.get("year")
    year_match = ref_year is None or cand_year is None or ref_year == cand_year
    venue = title_similarity(str(ref.get("journal") or ""), str(candidate.get("venue") or ""))
    overall = 0.55 * title + 0.25 * authors + 0.12 * (1.0 if year_match else 0.0) + 0.08 * venue
    return {"title": title, "authors": authors, "year_match": year_match, "venue": venue, "overall": overall}


def empty_scores() -> dict[str, Any]:
    return {"title": 0.0, "authors": 0.0, "year_match": False, "venue": 0.0, "overall": 0.0}


def decide_verdict(
    ref: dict[str, Any],
    candidate: dict[str, Any] | None,
    scores: dict[str, Any],
    doi_present: bool,
) -> str:
    if not candidate or not candidate.get("found"):
        return "not_found" if doi_present else "unverified"
    if doi_present and scores["title"] < 0.55:
        return "mismatch"
    if scores["title"] >= 0.82 and scores["authors"] >= 0.35 and scores["year_match"]:
        return "verified"
    if doi_present and scores["title"] >= 0.60 and scores["authors"] >= 0.50 and scores["year_match"]:
        return "needs_correction"
    if scores["title"] >= 0.72 and scores["year_match"]:
        return "needs_correction"
    return "mismatch" if doi_present else "unverified"


def reason_for(
    verdict: str,
    doi_present: bool,
    matched: dict[str, Any] | None,
    scores: dict[str, Any],
) -> str:
    if not matched or not matched.get("found"):
        return "DOI lookup failed." if doi_present else "No external metadata match found by title-author-year fallback."
    return (
        f"Best external match from {matched.get('source')}: title_score={scores['title']:.3f}, "
        f"author_score={scores['authors']:.3f}, year_match={scores['year_match']}, "
        f"venue_score={scores['venue']:.3f}."
    )


def render_markdown(results: list[dict[str, Any]], run_id: str) -> str:
    lines = [
        "# External Reference Check",
        "",
        f"Generated: {run_id}",
        "",
        "DOI references were checked with CrossRef `/works/{doi}`. References without DOI used a title-author-year fallback against Semantic Scholar search and CrossRef bibliographic search.",
        "",
    ]
    for pdf_name in sorted({r["pdf"] for r in results}):
        subset = [r for r in results if r["pdf"] == pdf_name]
        counts: dict[str, int] = {}
        for item in subset:
            counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
        lines.extend(
            [
                f"## {pdf_name}",
                "",
                f"Summary: {json.dumps(counts, ensure_ascii=False)}",
                "",
                "| # | Verdict | Extracted title | Extracted DOI | Matched title | Matched DOI/URL | Scores | Reason |",
                "| ---: | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in subset:
            ref = item["extracted"]
            match = item.get("matched") or {}
            scores = (
                f"t={item['title_score']:.3f}; a={item['author_score']:.3f}; "
                f"y={item['year_match']}; v={item['venue_score']:.3f}"
            )
            lines.append(
                "| {index} | `{verdict}` | {title} | `{doi}` | {mtitle} | {murl} | {scores} | {reason} |".format(
                    index=item["index"],
                    verdict=item["verdict"],
                    title=escape_cell(str(ref.get("title") or "")),
                    doi=str(ref.get("doi") or ""),
                    mtitle=escape_cell(str(match.get("title") or "")),
                    murl=escape_cell(str(match.get("doi") or match.get("url") or "")),
                    scores=scores,
                    reason=escape_cell(item["reason"]),
                )
            )
        lines.append("")
    return "\n".join(lines)


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def author_overlap(a: list[Any], b: list[Any]) -> float:
    left = {normalize_author(str(x)) for x in a if normalize_author(str(x))}
    right = {normalize_author(str(x)) for x in b if normalize_author(str(x))}
    if not left or not right:
        return 0.0
    matches = 0
    for la in left:
        if any(author_match(la, rb) for rb in right):
            matches += 1
    return matches / len(left)


def author_match(a: str, b: str) -> bool:
    if a == b:
        return True
    a_parts = a.split()
    b_parts = b.split()
    if not a_parts or not b_parts:
        return False
    return a_parts[-1] == b_parts[-1] and a_parts[0][0] == b_parts[0][0]


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("–", "-").replace("—", "-").replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_author(value: str) -> str:
    value = normalize_text(value)
    parts = value.split()
    if len(parts) >= 2 and len(parts[0]) <= 4:
        return " ".join(parts)
    return value


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def http_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ReliableGuard reference checker (mailto:local@example.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        nargs="+",
        default=["reference 1.pdf", "reference 2.pdf"],
    )
    parser.add_argument("--delay", type=float, default=0.15)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
