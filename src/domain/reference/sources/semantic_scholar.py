from __future__ import annotations

from src.domain.reference.sources.common import claim_title, encode_params, http_json
from src.reliableguard.schema import Claim
from src.reliableguard.verifier.sources.base import Evidence, SourceConfig


class SemanticScholarSource:
    def __init__(self, config: SourceConfig):
        self.name = config.name
        self.supports = config.supports
        self.timeout = int(config.options.get("timeout", 15))
        self.limit = int(config.options.get("limit", 5))

    def can_handle(self, claim: Claim) -> bool:
        return bool(claim_title(claim))

    def query(self, claim: Claim) -> list[Evidence]:
        title = claim_title(claim)
        if not title:
            return []
        params = encode_params(
            {
                "query": title,
                "fields": "title,authors,year,venue,url,externalIds",
                "limit": self.limit,
            }
        )
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
        try:
            papers = http_json(url, timeout=self.timeout).get("data", [])
        except Exception as exc:
            return [Evidence(source=self.name, found=False, raw={"error": str(exc), "query": title})]

        evidence = []
        for paper in papers:
            external = paper.get("externalIds") or {}
            evidence.append(
                Evidence(
                    source=self.name,
                    found=True,
                    title=paper.get("title") or "",
                    authors=[author.get("name", "") for author in paper.get("authors", [])],
                    year=paper.get("year"),
                    venue=paper.get("venue") or "",
                    doi=external.get("DOI") or "",
                    url=paper.get("url") or "",
                    raw=paper,
                )
            )
        return evidence
