from __future__ import annotations

import urllib.parse

from src.domain.reference.sources.common import (
    bibliographic_query,
    claim_doi,
    crossref_item_to_evidence,
    encode_params,
    http_json,
)
from src.reliableguard.schema import Claim
from src.reliableguard.verifier.sources.base import Evidence, SourceConfig


class CrossRefSource:
    def __init__(self, config: SourceConfig):
        self.name = config.name
        self.supports = config.supports
        self.timeout = int(config.options.get("timeout", 15))
        self.rows = int(config.options.get("rows", 5))

    def can_handle(self, claim: Claim) -> bool:
        return bool(claim_doi(claim) or bibliographic_query(claim))

    def query(self, claim: Claim) -> list[Evidence]:
        doi = claim_doi(claim)
        if doi:
            return self._query_doi(doi)
        query = bibliographic_query(claim)
        if not query:
            return []
        return self._query_bibliographic(query)

    def _query_doi(self, doi: str) -> list[Evidence]:
        url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
        try:
            item = http_json(url, timeout=self.timeout).get("message", {})
        except Exception as exc:
            return [Evidence(source=self.name, found=False, doi=doi, raw={"error": str(exc)})]
        return [crossref_item_to_evidence(self.name, item)]

    def _query_bibliographic(self, query: str) -> list[Evidence]:
        params = encode_params({"query.bibliographic": query, "rows": self.rows})
        url = f"https://api.crossref.org/works?{params}"
        try:
            items = http_json(url, timeout=self.timeout).get("message", {}).get("items", [])
        except Exception as exc:
            return [Evidence(source=self.name, found=False, raw={"error": str(exc), "query": query})]
        return [crossref_item_to_evidence(self.name, item) for item in items]
