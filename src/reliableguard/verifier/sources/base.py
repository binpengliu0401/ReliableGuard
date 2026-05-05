from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.reliableguard.schema import Claim


@dataclass(frozen=True)
class Evidence:
    source: str
    found: bool
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "found": self.found,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "url": self.url,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class SourceConfig:
    name: str
    adapter: str
    supports: set[str]
    priority: int = 100
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


class VerifierSource(Protocol):
    name: str
    supports: set[str]

    def can_handle(self, claim: Claim) -> bool:
        ...

    def query(self, claim: Claim) -> list[Evidence]:
        ...
