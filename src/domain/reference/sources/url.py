from __future__ import annotations

import urllib.request

from src.domain.reference.sources.common import claim_title, claim_url
from src.reliableguard.schema import Claim
from src.reliableguard.verifier.sources.base import Evidence, SourceConfig


class UrlSource:
    def __init__(self, config: SourceConfig):
        self.name = config.name
        self.supports = config.supports
        self.timeout = int(config.options.get("timeout", 10))

    def can_handle(self, claim: Claim) -> bool:
        return bool(claim_url(claim))

    def query(self, claim: Claim) -> list[Evidence]:
        url = claim_url(claim)
        if not url:
            return []
        try:
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ReliableGuard URL verifier"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None)
                final_url = response.geturl()
        except Exception as exc:
            return [Evidence(source=self.name, found=False, url=url, raw={"error": str(exc)})]

        return [
            Evidence(
                source=self.name,
                found=bool(status and 200 <= status < 400),
                title=claim_title(claim),
                url=final_url,
                raw={"status": status, "requested_url": url},
            )
        ]
