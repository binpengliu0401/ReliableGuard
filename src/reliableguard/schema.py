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
# Provenance of the evidence the verifier actually had at runtime. Orthogonal to
# `evidence_state` (the verification outcome): a `not_found` outcome can be produced
# either by an available authoritative source ("not_found" mode) or by a missing
# source offline ("unavailable" mode). `None` means no source was consulted (e.g. the
# claim was classified unverifiable by type). This is a black-box, runtime-only signal;
# it never reads dataset ground-truth labels.
SourceMode = Literal["fixture", "unavailable", "not_found"]
RiskLevel = Literal["low", "medium", "high"]
InterventionAction = Literal["PASS", "WARN", "BLOCK"]
# Overall reliability verdict. Extends the per-claim actions with:
#   - AUDIT_FAILED: the extractor produced zero claims, so the pipeline had nothing
#     to audit (fail-closed, NOT a PASS; a gate action when enforced).
#   - PASS_VERIFIED / PASS_UNCHECKED: a coverage-aware split of PASS. PASS_UNCHECKED
#     means the answer passed but evidence coverage was below threshold, i.e. the
#     monitor could not actually check most claims -- a transparency signal, still
#     PASS-like for enforcement. Metrics collapse both back to "PASS" for FAR/RDR.
# A per-claim `InterventionResult` never takes any of these extended values.
OverallVerdict = Literal[
    "PASS",
    "PASS_VERIFIED",
    "PASS_UNCHECKED",
    "WARN",
    "BLOCK",
    "AUDIT_FAILED",
]
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
    source_mode: SourceMode | None = None
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
    verdict: OverallVerdict
    reliability_score: float
    summary: str
    traces: list[ClaimTrace]
    supported_count: int = 0
    contradicted_count: int = 0
    unsupported_count: int = 0
    unverifiable_count: int = 0
    not_found_count: int = 0
    unavailable_count: int = 0
    stage_latencies: dict[str, float] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
