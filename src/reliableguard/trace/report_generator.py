from src.reliableguard.schema import ClaimTrace, ReliabilityReport


def generate_report(
    traces: list[ClaimTrace],
    *,
    verdict: str,
    reliability_score: float,
    trace_path: str | None = None,
) -> ReliabilityReport:
    counts = {
        "supported": 0,
        "contradicted": 0,
        "unsupported": 0,
        "unverifiable": 0,
        "not_found": 0,
    }
    for trace in traces:
        counts[trace.verification.evidence_state] += 1

    findings = [
        trace
        for trace in traces
        if trace.verification.evidence_state != "supported"
    ]
    if not traces:
        summary = "No factual claims were extracted from the agent answer."
    elif not findings:
        summary = f"Reliability verdict: {verdict}. All extracted claims are supported."
    else:
        lines = [
            f"Reliability verdict: {verdict}. Score={reliability_score:.2f}.",
            f"Found {len(findings)} claim(s) requiring attention.",
        ]
        for trace in findings[:5]:
            lines.append(
                f"- {trace.claim.text}: {trace.verification.evidence_state}; "
                f"{trace.verification.reason}"
            )
        if trace_path:
            lines.append(f"Trace file: {trace_path}")
        summary = "\n".join(lines)

    return ReliabilityReport(
        verdict=verdict,  # type: ignore[arg-type]
        reliability_score=reliability_score,
        summary=summary,
        traces=traces,
        supported_count=counts["supported"],
        contradicted_count=counts["contradicted"],
        unsupported_count=counts["unsupported"],
        unverifiable_count=counts["unverifiable"],
        not_found_count=counts["not_found"],
    )

