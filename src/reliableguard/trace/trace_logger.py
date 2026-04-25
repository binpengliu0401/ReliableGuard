import json
from pathlib import Path

from src.reliableguard.schema import Claim, ClaimTrace, InterventionResult, RiskResult, VerificationResult, Verifiability
from src.reliableguard.trace.artifacts import build_run_id, make_run_stamp


def build_traces(
    claims: list[Claim],
    verifiability: dict[str, Verifiability],
    verification_results: dict[str, VerificationResult],
    risks: dict[str, RiskResult],
    interventions: dict[str, InterventionResult],
) -> list[ClaimTrace]:
    traces: list[ClaimTrace] = []
    for claim in claims:
        traces.append(
            ClaimTrace(
                claim=claim,
                verifiability=verifiability.get(claim.claim_id, "unverifiable"),
                verification=verification_results[claim.claim_id],
                risk=risks[claim.claim_id],
                intervention=interventions[claim.claim_id],
            )
        )
    return traces


def write_trace(
    domain: str,
    query: str,
    answer: str,
    traces: list[ClaimTrace],
    *,
    run_stamp: str | None = None,
) -> str:
    log_dir = Path("logs") / domain
    log_dir.mkdir(parents=True, exist_ok=True)
    resolved_run_stamp = run_stamp or make_run_stamp()
    run_id = build_run_id(domain, resolved_run_stamp)
    path = log_dir / f"{run_id}.json"
    summary = _build_trace_summary(traces)
    payload = {
        "run_id": run_id,
        "run_started_at": resolved_run_stamp,
        "domain": domain,
        "query": query,
        "answer": answer,
        "summary": summary,
        "traces": [trace.model_dump() for trace in traces],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _build_trace_summary(traces: list[ClaimTrace]) -> dict:
    counts = {
        "supported": 0,
        "contradicted": 0,
        "unsupported": 0,
        "unverifiable": 0,
        "not_found": 0,
    }
    items = []
    for trace in traces:
        state = trace.verification.evidence_state
        counts[state] += 1
        items.append(
            {
                "claim_id": trace.claim.claim_id,
                "claim": trace.claim.text,
                "evidence_state": state,
                "source": trace.verification.source,
                "risk_level": trace.risk.risk_level,
                "intervention": trace.intervention.action,
                "reason": trace.verification.reason,
            }
        )
    return {
        "total_claims": len(traces),
        "counts": counts,
        "items": items,
    }
