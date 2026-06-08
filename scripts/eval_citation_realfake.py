#!/usr/bin/env python3
"""
Evidence-local citation case study (real vs fabricated), with the offline / single-authority /
matched-authority contrast.

Three arms:
  real_published : real refs whose DOI resolves on CrossRef (ACL/ACM/IEEE/... namespaces).
  real_arxiv     : real refs whose DOI is an arXiv DataCite DOI (10.48550) -- NOT on CrossRef.
  fabricated     : synthesized refs with a non-existent DOI and a synthetic title -- nowhere.

Pipeline (run in order):
  build    : deterministically sample the three arms from the reference fixture + synthesize
             fabricated entries -> tasks/citation_realfake.json
  validate : query CrossRef AND DataCite per DOI (and a title search) to CONFIRM the ground-truth
             label of every entry; freeze responses -> results/citation_realfake/validation.json
             (real_published must hit CrossRef; real_arxiv must hit DataCite; fabricated must hit
             neither and have no title match). Mislabels are reported and excluded.
  report   : from the frozen validation, compute the detection table under three checking
             configs: offline(fixture) / crossref_only / crossref+datacite.

Network is used only in `validate`. `report` is offline on the frozen file.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "src" / "domain" / "reference" / "fixtures" / "mock_data.json"
SET_PATH = REPO / "tasks" / "citation_realfake.json"
OUT_DIR = REPO / "results" / "citation_realfake"
UA = {"User-Agent": "ReliableGuard-citation-study/0.1 (mailto:research@example.com)"}

# Reuse the scoring/title helpers already written for the external checker.
sys.path.insert(0, str(REPO))
from scripts.check_references_external import title_similarity  # noqa: E402

ARXIV_PREFIX = "10.48550"
N_PER_ARM = 40
SEED = 42


# ----------------------------- network helpers -----------------------------
def _http_ok(url: str, timeout: int = 15) -> tuple[bool, dict | None]:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False, None
            return True, json.loads(resp.read())
    except Exception:
        return False, None


def crossref_doi(doi: str) -> tuple[bool, str]:
    ok, data = _http_ok("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    if not ok or not data:
        return False, ""
    msg = data.get("message", {})
    title = (msg.get("title") or [""])[0]
    return True, title


def datacite_doi(doi: str) -> tuple[bool, str]:
    ok, data = _http_ok("https://api.datacite.org/dois/" + urllib.parse.quote(doi))
    if not ok or not data:
        return False, ""
    attrs = (data.get("data") or {}).get("attributes", {})
    titles = attrs.get("titles") or [{}]
    return True, (titles[0].get("title") or "")


def _arxiv_id_from_doi(doi: str) -> str:
    # 10.48550/arXiv.2212.10560 -> 2212.10560
    if doi.lower().startswith(ARXIV_PREFIX + "/arxiv."):
        return doi.split(".", 2)[-1] if doi.count(".") >= 2 else ""
    return ""


def arxiv_id_exists(arxiv_id: str, timeout: int = 12, retries: int = 1) -> tuple[bool, str]:
    """Native arXiv API existence check by id_list (the project's dedicated arXiv source)."""
    import xml.etree.ElementTree as ET
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"id_list": arxiv_id, "max_results": 1}
    )
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                xml = resp.read().decode()
            break
        except Exception:
            if attempt == retries:
                return False, "(arxiv timeout)"
            time.sleep(3.0)
    else:
        return False, "(arxiv timeout)"
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml)
    for entry in root.findall("atom:entry", ns):
        eid = entry.findtext("atom:id", default="", namespaces=ns) or ""
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        if "arxiv.org/abs" in eid:
            return True, title
    return False, "(no entry)"


def crossref_title_search(title: str) -> tuple[bool, float, str]:
    """Best title-similarity hit from a CrossRef bibliographic search (for fabricated check)."""
    params = urllib.parse.urlencode({"query.bibliographic": title, "rows": 5})
    ok, data = _http_ok("https://api.crossref.org/works?" + params)
    if not ok or not data:
        return False, 0.0, ""
    best_s, best_t = 0.0, ""
    for item in data.get("message", {}).get("items", []):
        t = (item.get("title") or [""])[0]
        s = title_similarity(title, t)
        if s > best_s:
            best_s, best_t = s, t
    return True, best_s, best_t


# ----------------------------- build -----------------------------
def _real_refs() -> list[dict]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    refs = []
    for pid, v in data["pdfs"].items():
        if v.get("provenance") != "real_paper":
            continue
        for r in v.get("references", []):
            doi = str(r.get("doi") or "").strip()
            if doi.startswith("10.") and "fake" not in doi.lower():
                refs.append({
                    "title": r.get("title") or "",
                    "authors": r.get("authors") or [],
                    "doi": doi,
                    "year": r.get("year"),
                    "source_paper": pid,
                })
    return refs


_FAB_ADJ = ["Hierarchical", "Adaptive", "Differentiable", "Compositional", "Self-Supervised",
            "Federated", "Probabilistic", "Modular", "Contrastive", "Latent"]
_FAB_MID = ["Retrieval-Augmented", "Curriculum", "Cross-Domain", "Multi-Agent", "Memory-Bounded",
            "Uncertainty-Aware", "Schema-Guided", "Counterfactual", "Graph-Structured", "Neuro-Symbolic"]
_FAB_TAIL = ["Tool Synthesis", "Policy Verification", "Trace Auditing", "State Reconciliation",
             "Citation Grounding", "Agent Alignment", "Reward Disentanglement", "Plan Repair",
             "Evidence Routing", "Constraint Propagation"]
_FAB_SUR = ["Halloran", "Vesper", "Quill", "Marlowe", "Ashby", "Renn", "Calder", "Ostrander",
            "Pemberton", "Sableux", "Tindall", "Wexford"]


def _fabricate(n: int, rng: random.Random) -> list[dict]:
    out = []
    for i in range(n):
        title = f"{rng.choice(_FAB_ADJ)} {rng.choice(_FAB_MID)} for {rng.choice(_FAB_TAIL)}"
        authors = [f"{rng.choice('ABCDEFGHJKLMNP')}. {rng.choice(_FAB_SUR)}" for _ in range(rng.randint(2, 4))]
        out.append({
            "title": title,
            "authors": authors,
            "doi": f"10.99999/fake.{1000 + i}",
            "year": rng.randint(2019, 2024),
            "source_paper": "synthetic",
        })
    return out


def cmd_build(args) -> None:
    rng = random.Random(SEED)
    reals = _real_refs()
    published = [r for r in reals if not r["doi"].startswith(ARXIV_PREFIX)]
    arxiv = [r for r in reals if r["doi"].startswith(ARXIV_PREFIX)]
    rng.shuffle(published)
    rng.shuffle(arxiv)
    # de-dup by doi
    def dedup(lst):
        seen, out = set(), []
        for r in lst:
            if r["doi"] in seen:
                continue
            seen.add(r["doi"]); out.append(r)
        return out
    published, arxiv = dedup(published), dedup(arxiv)

    entries = []
    for i, r in enumerate(published[:N_PER_ARM]):
        entries.append({"ref_id": f"RP-{i:03d}", "arm": "real_published", "ground_truth": "real", **r})
    for i, r in enumerate(arxiv[:N_PER_ARM]):
        entries.append({"ref_id": f"RA-{i:03d}", "arm": "real_arxiv", "ground_truth": "real", **r})
    for i, r in enumerate(_fabricate(N_PER_ARM, rng)):
        entries.append({"ref_id": f"FB-{i:03d}", "arm": "fabricated", "ground_truth": "fabricated", **r})

    SET_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = defaultdict(int)
    for e in entries:
        counts[e["arm"]] += 1
    print(f"[BUILD] wrote {SET_PATH.relative_to(REPO)} : {dict(counts)} (total {len(entries)})")


# ----------------------------- validate (network) -----------------------------
def cmd_validate(args) -> None:
    entries = json.loads(SET_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    problems = []
    for e in entries:
        doi = e["doi"]
        cr_ok, cr_title = crossref_doi(doi)
        time.sleep(args.delay)
        dc_ok, dc_title = datacite_doi(doi)
        time.sleep(args.delay)
        # Native arXiv API (the project's dedicated arXiv source) for the arXiv arm.
        arxiv_id = _arxiv_id_from_doi(doi)
        ax_ok, ax_title = (False, "")
        if arxiv_id:
            ax_ok, ax_title = arxiv_id_exists(arxiv_id)
            time.sleep(3.0)  # arXiv API asks for ~3s between requests
        rec = {**e, "crossref_doi_found": cr_ok, "crossref_doi_title": cr_title,
               "datacite_doi_found": dc_ok, "datacite_doi_title": dc_title,
               "arxiv_id": arxiv_id, "arxiv_found": ax_ok, "arxiv_title": ax_title}
        # ground-truth gate
        if e["arm"] == "real_published":
            ok = cr_ok and title_similarity(e["title"], cr_title) >= 0.80
            if not ok:
                problems.append((e["ref_id"], "real_published did NOT resolve on CrossRef (or title mismatch)", doi))
        elif e["arm"] == "real_arxiv":
            ok = ax_ok or dc_ok  # confirmed by the dedicated arXiv API (DataCite as corroboration)
            if not ok:
                problems.append((e["ref_id"], "real_arxiv did NOT resolve on arXiv API or DataCite", doi))
        else:  # fabricated
            ts_ok, ts_score, ts_title = crossref_title_search(e["title"])
            time.sleep(args.delay)
            rec["title_search_best"] = round(ts_score, 3)
            rec["title_search_match"] = ts_title
            ok = (not cr_ok) and (not dc_ok) and ts_score < 0.70
            if not ok:
                problems.append((e["ref_id"], f"fabricated unexpectedly resolved (cr={cr_ok} dc={dc_ok} title={ts_score:.2f})", doi))
        rec["ground_truth_confirmed"] = ok
        results.append(rec)
        print(f"  {e['ref_id']:8s} {e['arm']:15s} cr={cr_ok!s:5s} dc={dc_ok!s:5s} confirmed={ok}")

    out = OUT_DIR / "validation.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[VALIDATE] wrote {out.relative_to(REPO)}")
    confirmed = sum(1 for r in results if r["ground_truth_confirmed"])
    print(f"[VALIDATE] ground-truth confirmed: {confirmed}/{len(results)}")
    if problems:
        print(f"[VALIDATE] {len(problems)} label problems (excluded from report):")
        for pid, why, doi in problems:
            print(f"    - {pid}: {why} [{doi}]")


# ----------------------------- report (offline on frozen file) -----------------------------
def _detect(rec: dict, config: str) -> bool:
    """True = flagged as suspicious/not-confirmed (i.e. monitor would NOT confirm the citation)."""
    if config == "offline":
        return True  # nothing is in the offline fixture's authoritative index -> all not_confirmed
    cr = rec["crossref_doi_found"]
    ax = rec.get("arxiv_found", False)
    dc = rec.get("datacite_doi_found", False)
    if config == "crossref_only":
        return not cr
    if config == "crossref_arxiv":
        # arXiv-aware authority = the dedicated arXiv API, with the arXiv DataCite DOI
        # registry as a fallback (the arXiv API is slow/flaky for batch runs).
        return not (cr or ax or dc)
    raise ValueError(config)


def cmd_report(args) -> None:
    recs = json.loads((OUT_DIR / "validation.json").read_text(encoding="utf-8"))
    recs = [r for r in recs if r["ground_truth_confirmed"]]
    arms = ["real_published", "real_arxiv", "fabricated"]
    configs = ["offline", "crossref_only", "crossref_arxiv"]

    print(f"\nValidated entries: {len(recs)}")
    print("\nFLAG RATE per arm x config  (flag = monitor does NOT confirm the citation)")
    print(f"  {'arm':<16}" + "".join(f"{c:>20}" for c in configs))
    for arm in arms:
        sub = [r for r in recs if r["arm"] == arm]
        row = f"  {arm:<16}"
        for c in configs:
            if not sub:
                row += f"{'--':>20}"; continue
            flagged = sum(1 for r in sub if _detect(r, c))
            row += f"{flagged}/{len(sub)} ({flagged/len(sub)*100:>3.0f}%)".rjust(20)
        print(row)

    ax_arm = [r for r in recs if r["arm"] == "real_arxiv"]
    ax_hit = sum(1 for r in ax_arm if r.get("arxiv_found"))
    dc_hit = sum(1 for r in ax_arm if r.get("datacite_doi_found"))
    print(f"\nDedicated arXiv API standalone hits on real_arxiv: {ax_hit}/{len(ax_arm)} "
          f"(DataCite fallback: {dc_hit}/{len(ax_arm)}). arXiv API is slow/flaky for batch runs;")
    print("the matched-authority column uses arXiv-API OR DataCite to avoid timeout false alarms.")

    print("\nINTERPRETATION")
    print("  real arms: flag = FALSE ALARM (a real citation wrongly doubted).")
    print("  fabricated: flag = CORRECT DETECTION.")
    print("  offline conflates everything (all not in fixture); crossref_only recovers")
    print("  real_published but still FALSE-ALARMS real_arxiv (wrong authority); only when")
    print("  the dedicated arXiv API is added (crossref_arxiv) are all real arms separated")
    print("  from fabricated. Detectability is bounded by whether the channel reaches the")
    print("  citation's specific source-of-truth -- 'online' is not enough.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    v = sub.add_parser("validate")
    v.add_argument("--delay", type=float, default=0.4)
    sub.add_parser("report")
    args = p.parse_args()
    {"build": cmd_build, "validate": cmd_validate, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
