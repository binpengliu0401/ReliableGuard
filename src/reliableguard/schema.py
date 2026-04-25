from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ClaimType = Literal[
    "existence",
    "attribute",
    "numeric",
    "temporal",
    "relational",
    "semantic",
]
Verifiability = Literal[
    "fully_verifiable",
    "partially_verifiable",
    "unverifiable",
]
EvidenceState = Literal[
    "supported",
    "contradicted",
    "unsupported",
    "unverifiable",
    "not_found",
]
RiskLevel = Literal["low", "medium", "high"]
InterventionAction = Literal["PASS", "WARN", "BLOCK", "ESCALATE"]
Certainty = Literal["certain", "uncertain", "abstained"]


class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: ClaimType
    entities: dict[str, Any] = Field(default_factory=dict)
    attribute: str | None = None
    value: Any | None = None
    unit: str | None = None
    time_range: str | None = None
    certainty: Certainty = "certain"
    confidence: float = 1.0


class VerificationResult(BaseModel):
    claim_id: str
    evidence_state: EvidenceState
    evidence_value: Any | None = None
    source: str | None = None
    confidence: float = 1.0
    reason: str = ""


class RiskResult(BaseModel):
    claim_id: str
    risk_level: RiskLevel
    score: float
    reason: str = ""


class InterventionResult(BaseModel):
    claim_id: str
    action: InterventionAction
    reason: str = ""


class ClaimTrace(BaseModel):
    claim: Claim
    verifiability: Verifiability
    verification: VerificationResult
    risk: RiskResult
    intervention: InterventionResult


class ReliabilityReport(BaseModel):
    verdict: InterventionAction
    reliability_score: float
    summary: str
    traces: list[ClaimTrace]
    supported_count: int = 0
    contradicted_count: int = 0
    unsupported_count: int = 0
    unverifiable_count: int = 0
    not_found_count: int = 0

