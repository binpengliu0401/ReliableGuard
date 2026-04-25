from src.reliableguard.classifier.verifiability_classifier import classify_verifiability
from src.reliableguard.extractor.claim_extractor import extract_claims
from src.reliableguard.intervention.policy_engine import decide_interventions
from src.reliableguard.schema import Claim, ReliabilityReport
from src.reliableguard.scorer.risk_scorer import score_risks
from src.reliableguard.trace.report_generator import generate_report
from src.reliableguard.trace.trace_logger import build_traces, write_trace
from src.reliableguard.verifier.source_verifier import verify_claims


def run_reliability_pipeline(
    domain: str,
    query: str,
    agent_answer: str,
    *,
    model: str,
    base_url: str,
    write_logs: bool = True,
    run_stamp: str | None = None,
    claims: list[Claim] | None = None,
) -> ReliabilityReport:
    if claims is None:
        claims = extract_claims(domain, query, agent_answer, model=model, base_url=base_url)
    verifiability = classify_verifiability(domain, claims)
    verification_results = verify_claims(domain, claims, verifiability)
    risks, reliability_score = score_risks(claims, verification_results)
    interventions, verdict = decide_interventions(
        claims,
        verification_results,
        risks,
        reliability_score,
    )
    traces = build_traces(
        claims,
        verifiability,
        verification_results,
        risks,
        interventions,
    )
    trace_path = (
        write_trace(domain, query, agent_answer, traces, run_stamp=run_stamp)
        if write_logs
        else None
    )
    return generate_report(
        traces,
        verdict=verdict,
        reliability_score=reliability_score,
        trace_path=trace_path,
    )
