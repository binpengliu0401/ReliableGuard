import time

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
    temperature: float = 0.0,
    seed: int | None = None,
) -> ReliabilityReport:
    t0 = time.perf_counter()
    if claims is None:
        claims = extract_claims(
            domain,
            query,
            agent_answer,
            model=model,
            base_url=base_url,
            temperature=temperature,
            seed=seed,
        )
    t1 = time.perf_counter()

    verifiability = classify_verifiability(domain, claims)
    t2 = time.perf_counter()

    verification_results = verify_claims(domain, claims, verifiability)
    t3 = time.perf_counter()

    risks, reliability_score = score_risks(claims, verification_results)
    t4 = time.perf_counter()

    interventions, verdict = decide_interventions(
        claims,
        verification_results,
        risks,
        reliability_score,
    )
    t5 = time.perf_counter()

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
    report = generate_report(
        traces,
        verdict=verdict,
        reliability_score=reliability_score,
        trace_path=trace_path,
    )
    t6 = time.perf_counter()

    stage_latencies = {
        "extract_claims": round(t1 - t0, 4),
        "classify_verifiability": round(t2 - t1, 4),
        "verify_claims": round(t3 - t2, 4),
        "score_risks": round(t4 - t3, 4),
        "decide_interventions": round(t5 - t4, 4),
        "generate_report": round(t6 - t5, 4),
        "total_pipeline": round(t6 - t0, 4),
    }
    return report.model_copy(update={"stage_latencies": stage_latencies})
