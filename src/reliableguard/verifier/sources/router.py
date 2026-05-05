from __future__ import annotations

from src.reliableguard.schema import Claim
from src.reliableguard.verifier.sources.base import Evidence
from src.reliableguard.verifier.sources.loader import load_sources


def query_configured_sources(domain: str, claim: Claim) -> list[Evidence]:
    evidence: list[Evidence] = []
    for source in load_sources(domain):
        if not source.can_handle(claim):
            continue
        try:
            evidence.extend(source.query(claim))
        except Exception as exc:
            evidence.append(
                Evidence(
                    source=getattr(source, "name", source.__class__.__name__),
                    found=False,
                    raw={"error": str(exc), "adapter": source.__class__.__name__},
                )
            )
    return evidence
