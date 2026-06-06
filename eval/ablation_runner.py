import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.config.ablation_versions import VERSIONS
from eval.fact_scorer import (
    parse_expected_facts,
    score_facts,
    score_trace_facts,
    snapshot_facts,
)
from src.agent.langgraph_agent import run_agent
from src.config.runtime_config import RuntimeConfig
from src.db.reset_env import reset_env
from eval.metrics import build_result_row
from src.reliableguard.pipeline import run_reliability_pipeline
from src.reliableguard.schema import Claim


LLM_INFRASTRUCTURE_ERRORS = {
    "APIStatusError",
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "InternalServerError",
    "PermissionDeniedError",
    "RateLimitError",
}

# Truncation is task-level (answer too long for this specific input), not an
# infrastructure failure. Log and skip; do not count toward consecutive abort threshold.
TRUNCATION_ERRORS = {"LLMResponseTruncatedError"}


class ExperimentAbort(RuntimeError):
    """Raised when a benchmark run should stop instead of producing more ERROR rows."""


def run_version(
    version_key: str,
    scenarios: list[dict],
    verbose: bool = True,
    config_override: RuntimeConfig | None = None,
    seeds: list[int] | None = None,
    enable_fault_injection: bool = True,
    fail_fast: bool = True,
    max_consecutive_errors: int = 3,
) -> list[dict]:
    base_config = config_override if config_override else VERSIONS[version_key]
    selected_seeds = seeds or [42]
    results = []
    consecutive_errors = 0

    print(f"\n{'#'*60}")
    print(f"# VERSION: {base_config.version_name}")
    print(f"{'#'*60}")

    for seed in selected_seeds:
        # Inherit the configured agent temperature (default 0.0) instead of
        # hardcoding 0.7: the benchmark must be reproducible, and a stochastic
        # agent answer was the dominant cause of run-to-run swings in
        # wording-dependent claim detection (e.g. F4). Override via RuntimeConfig
        # if a stochastic-agent study is wanted.
        config = replace(base_config, llm_seed=seed)
        if verbose:
            print(f"\n[SEED] {seed}")

        for task in scenarios:
            domain = task.get("domain", "ecommerce")
            if domain == "ecommerce":
                reset_env()
            else:
                from src.db.reset_reference_env import reset_reference_env

                reset_reference_env()
            try:
                if task.get("mode", "e2e") == "verifier_only":
                    state = _run_verifier_only(task, config, seed)
                else:
                    with _maybe_inject_ecommerce_f4_false_success(
                        task,
                        domain,
                        enabled=enable_fault_injection,
                    ):
                        state = run_agent(
                            task["input"],
                            domain=domain,
                            config=config,
                        )
                    state["seed"] = seed
                    if domain == "ecommerce":
                        state["db_state_after"] = _snapshot_ecommerce_db_state()

                verifiable_facts = task.get("verifiable_facts", [])
                expected_facts = parse_expected_facts(verifiable_facts)
                fact_snap = (
                    snapshot_facts(domain, set(expected_facts.keys()))
                    if expected_facts
                    else {}
                )
                fact_accuracy = (
                    score_facts(expected_facts, fact_snap) if expected_facts else None
                )
                trace_fact_scores = (
                    score_trace_facts(expected_facts, state, domain)
                    if expected_facts
                    else {}
                )
                row = build_result_row(
                    task=task,
                    state=state,
                    version=version_key,
                    error=None,
                    seed=seed,
                    fact_accuracy=fact_accuracy,
                    fact_snapshot=fact_snap,
                    trace_fact_scores=trace_fact_scores,
                )

                results.append(
                    {
                        "task": task,
                        "state": state,
                        "version": version_key,
                        "seed": seed,
                        "error": None,
                        "scored_row": row,
                        "fact_snapshot": fact_snap,
                        "fact_accuracy": fact_accuracy,
                        "trace_fact_scores": trace_fact_scores,
                    }
                )
                consecutive_errors = 0

                if verbose:
                    actual = row["actual_outcome"]
                    expected = row["expected_outcome"]
                    match = "OK" if actual == expected else "MISMATCH"
                    print(
                        f"[{match}] seed={seed} {task['id']} | "
                        f"expected={expected} actual={actual}"
                    )

            except Exception as e:
                error_label = type(e).__name__
                print(f"[ERROR] seed={seed} {task['id']} | {error_label}: {e}")
                if error_label not in TRUNCATION_ERRORS:
                    consecutive_errors += 1

                row = build_result_row(
                    task=task,
                    state=None,
                    version=version_key,
                    error=error_label,
                    seed=seed,
                    fact_accuracy=None,
                    fact_snapshot={},
                    trace_fact_scores={},
                )

                results.append(
                    {
                        "task": task,
                        "state": None,
                        "version": version_key,
                        "seed": seed,
                        "error": error_label,
                        "scored_row": row,
                        "fact_snapshot": {},
                        "fact_accuracy": None,
                        "trace_fact_scores": {},
                    }
                )
                if fail_fast and _should_abort_run(
                    error_label,
                    consecutive_errors,
                    max_consecutive_errors,
                ):
                    raise ExperimentAbort(
                        "aborting benchmark after "
                        f"{consecutive_errors} consecutive error(s); "
                        f"latest seed={seed} scenario={task['id']} "
                        f"error={error_label}: {e}"
                    ) from e

    return results


def _should_abort_run(
    error_label: str,
    consecutive_errors: int,
    max_consecutive_errors: int,
) -> bool:
    if error_label in LLM_INFRASTRUCTURE_ERRORS:
        return True
    return consecutive_errors >= max_consecutive_errors


@contextmanager
def _maybe_inject_ecommerce_f4_false_success(
    task: dict[str, Any],
    domain: str,
    enabled: bool = True,
) -> Iterator[None]:
    if not enabled or domain != "ecommerce" or task.get("note") not in {
        "f4_injection",
        "f4b_injection",
    }:
        yield
        return

    from src.graph import nodes

    registry = nodes.ECOMMERCE_TOOL_REGISTRY
    original_create_order = registry.get("create_order")

    def false_success_create_order(amount: float) -> dict[str, Any]:
        return {
            "success": True,
            "order_id": 1,
            "amount": amount,
            "status": "pending",
            "injected_fault": "f4_false_success_no_db_write",
        }

    registry["create_order"] = false_success_create_order
    try:
        yield
    finally:
        if original_create_order is None:
            registry.pop("create_order", None)
        else:
            registry["create_order"] = original_create_order


def _snapshot_ecommerce_db_state() -> list[dict[str, Any]]:
    from src.domain.ecommerce.tools import cursor

    rows = cursor.execute(  # type: ignore[union-attr]
        "SELECT id, amount, status, refund_reason FROM orders ORDER BY id"
    ).fetchall()
    return [
        {
            "id": row[0],
            "amount": row[1],
            "status": row[2],
            "refund_reason": row[3],
        }
        for row in rows
    ]


def _run_verifier_only(task: dict, config: RuntimeConfig, seed: int) -> dict:
    domain = task.get("domain", "ecommerce")
    _seed_database(domain, task.get("db_seed", {}))
    answer = task.get("injected_final_answer", "")

    state = {
        "messages": [{"role": "user", "content": task.get("input", "")}],
        "tool_call": None,
        "trace": [],
        "final_answer": answer,
        "reliability_report": None,
        "reliability_verdict": None,
        "reliability_verdict_audit": None,
        "reliability_score": None,
        "executed_tools": [],
        "config": config,
        "domain": domain,
        "verifier_context": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "run_id": task.get("id"),
        "run_stamp": None,
        "run_started_at": None,
        "seed": seed,
    }

    if not config.use_verifier:
        return state

    injected_claims = [
        Claim(**claim_payload)
        for claim_payload in task.get("injected_claims", [])
        if isinstance(claim_payload, dict)
    ]
    report = run_reliability_pipeline(
        domain=domain,
        query=task.get("input", ""),
        agent_answer=answer,
        model=config.llm_model,
        base_url=config.llm_base_url,
        write_logs=False,
        claims=injected_claims or None,
        temperature=config.claim_extraction_temperature,
        seed=config.llm_seed,
        max_tokens=config.claim_extraction_max_tokens,
    )
    state["reliability_report"] = report.model_dump()
    state["reliability_verdict_audit"] = report.verdict
    state["reliability_score"] = report.reliability_score
    state["reliability_verdict"] = report.verdict if config.enforce_intervention else "PASS"
    token_usage = report.token_usage or {}
    state["prompt_tokens"] = int(token_usage.get("prompt_tokens", 0) or 0)
    state["completion_tokens"] = int(token_usage.get("completion_tokens", 0) or 0)
    state["total_tokens"] = int(token_usage.get("total_tokens", 0) or 0)
    return state


def _seed_database(domain: str, seed: dict) -> None:
    if not seed:
        return

    if domain == "ecommerce":
        from src.domain.ecommerce.tools import conn, cursor

        for order in seed.get("orders", []):
            cursor.execute(  # type: ignore[union-attr]
                """
                INSERT INTO orders (id, amount, status, refund_reason)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order.get("id"),
                    order.get("amount"),
                    order.get("status", "pending"),
                    order.get("refund_reason"),
                ),
            )
        conn.commit()
        return

    if domain == "reference":
        from src.domain.reference.tools import init_reference_db

        db = init_reference_db()
        try:
            for paper in seed.get("papers", []):
                db.execute(
                    """
                    INSERT INTO papers (paper_id, pdf_path, status)
                    VALUES (?, ?, ?)
                    """,
                    (
                        paper.get("paper_id"),
                        paper.get("pdf_path", "fixture.pdf"),
                        paper.get("status", "parsed"),
                    ),
                )
            for ref in seed.get("references", []):
                authors = ref.get("authors", [])
                db.execute(
                    """
                    INSERT INTO "references" (
                        ref_id, paper_id, title, authors, doi, journal, year,
                        doi_status, doi_verdict_code, authors_status, journal_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ref.get("ref_id"),
                        ref.get("paper_id"),
                        ref.get("title", ""),
                        json.dumps(authors, ensure_ascii=False),
                        ref.get("doi", ""),
                        ref.get("journal", ""),
                        ref.get("year"),
                        ref.get("doi_status", "pending"),
                        ref.get("doi_verdict_code", "pending"),
                        ref.get("authors_status", "pending"),
                        ref.get("journal_status", "pending"),
                    ),
                )
            db.commit()
        finally:
            db.close()
        return

    raise ValueError(f"Unsupported domain: {domain}")


# ---------------------------------------------------------------------------
# Frozen-corpus record / replay (reproducible monitor evaluation).
#
# The agent (and the claim extractor) are non-deterministic hosted LLMs, so a
# fair comparison between monitor configurations must hold the agent behaviour
# fixed. `record_corpus` runs each scenario once in observe-only capture mode and
# freezes (answer, extracted claims, tool trace, structural issues, post-state).
# `replay_corpus` then audits that frozen behaviour under any version with zero
# LLM calls, so version differences (e.g. V3 vs V3_NoStructural) are paired and
# fully reproducible. Ecommerce structural is faithful; reference replay re-seeds
# the scenario db_seed and relies on the static evidence fixture.
# ---------------------------------------------------------------------------

CORPUS_RECORD_VERSION = 1


def _reset_domain(domain: str) -> None:
    if domain == "ecommerce":
        reset_env()
    else:
        from src.db.reset_reference_env import reset_reference_env

        reset_reference_env()


def _state_to_record(task: dict, state: dict, seed: int, domain: str) -> dict:
    report = state.get("reliability_report") or {}
    claims = [
        trace["claim"]
        for trace in (report.get("traces") or [])
        if isinstance(trace, dict) and trace.get("claim")
    ]
    db_state_after = (
        _snapshot_ecommerce_db_state() if domain == "ecommerce" else None
    )
    return {
        "record_version": CORPUS_RECORD_VERSION,
        "scenario_id": task.get("id"),
        "domain": domain,
        "seed": seed,
        "input": task.get("input", ""),
        # The full scenario, so replay scores pass_fail/expected exactly as e2e
        # (normalize_expected reads expected_outcome / failure_mode / verifiable_facts).
        "task": task,
        "final_answer": state.get("final_answer") or "",
        "claims": claims,
        "tool_trace": state.get("tool_trace", []) or [],
        "structural_issues": state.get("structural_audit", []) or [],
        "executed_tools": state.get("executed_tools", []) or [],
        "db_state_after": db_state_after,
        "db_seed": task.get("db_seed", {}),
        "error": None,
    }


def record_corpus(
    scenarios: list[dict],
    seeds: list[int] | None = None,
    enable_fault_injection: bool = True,
    verbose: bool = True,
    skip_keys: set | None = None,
    on_record=None,
    policy_aware: bool = False,
) -> list[dict]:
    """Run each (scenario, seed) once in observe-only capture mode; return corpus records.

    `skip_keys` is a set of (scenario_id, seed) already recorded (for --resume); those
    are skipped. `on_record(record)` is called immediately after each record is built,
    enabling incremental checkpointing so a crash never loses completed work.
    `policy_aware` (T8) exposes the >5000 approval policy to the ecommerce agent prompt.
    """
    selected_seeds = seeds or [42]
    skip_keys = skip_keys or set()
    base = replace(VERSIONS["V2_AuditOnly"], capture_trace=True, policy_aware=policy_aware)
    corpus: list[dict] = []
    for seed in selected_seeds:
        config = replace(base, llm_seed=seed)
        for task in scenarios:
            if (task.get("id"), seed) in skip_keys:
                continue
            domain = task.get("domain", "ecommerce")
            _reset_domain(domain)
            try:
                if task.get("mode", "e2e") == "verifier_only":
                    # Already a frozen unit: pass the injected answer/claims through.
                    record = {
                        "record_version": CORPUS_RECORD_VERSION,
                        "scenario_id": task.get("id"),
                        "domain": domain,
                        "seed": seed,
                        "input": task.get("input", ""),
                        "task": task,
                        "final_answer": task.get("injected_final_answer", ""),
                        "claims": task.get("injected_claims", []),
                        "tool_trace": [],
                        "structural_issues": [],
                        "executed_tools": [],
                        "db_state_after": None,
                        "db_seed": task.get("db_seed", {}),
                        "error": None,
                    }
                else:
                    with _maybe_inject_ecommerce_f4_false_success(
                        task, domain, enabled=enable_fault_injection
                    ):
                        state = run_agent(
                            task["input"], domain=domain, config=config
                        )
                    record = _state_to_record(task, state, seed, domain)
            except Exception as e:  # noqa: BLE001 - record the failure, keep going
                record = {
                    "record_version": CORPUS_RECORD_VERSION,
                    "scenario_id": task.get("id"),
                    "domain": domain,
                    "seed": seed,
                    "input": task.get("input", ""),
                    "task": task,
                    "final_answer": "",
                    "claims": [],
                    "tool_trace": [],
                    "structural_issues": [],
                    "executed_tools": [],
                    "db_state_after": None,
                    "db_seed": task.get("db_seed", {}),
                    "error": type(e).__name__,
                }
                if verbose:
                    print(f"[RECORD-ERROR] seed={seed} {task.get('id')} | {record['error']}: {e}")
            if on_record is not None:
                on_record(record)
            corpus.append(record)
            if verbose and not record["error"]:
                print(
                    f"[RECORD] seed={seed} {task.get('id')} | "
                    f"claims={len(record['claims'])} "
                    f"structural={len(record['structural_issues'])}"
                )
    return corpus


def _record_to_task(record: dict) -> dict:
    """The frozen scenario, so build_result_row scores expected/pass_fail as in e2e."""
    task = record.get("task")
    if isinstance(task, dict) and task:
        return task
    return {
        "id": record.get("scenario_id"),
        "domain": record.get("domain", "ecommerce"),
        "input": record.get("input", ""),
    }


def replay_corpus(
    corpus: list[dict],
    version_key: str,
    config_override: RuntimeConfig | None = None,
    verbose: bool = True,
) -> list[dict]:
    """Audit a frozen corpus under one version with no LLM calls. Fully deterministic."""
    config = config_override or VERSIONS[version_key]
    results: list[dict] = []
    for record in corpus:
        task = _record_to_task(record)
        seed = record.get("seed")
        if record.get("error"):
            row = build_result_row(
                task=task, state=None, version=version_key,
                error=record["error"], seed=seed,
            )
            results.append({
                "task": task, "state": None, "version": version_key,
                "seed": seed, "error": record["error"], "scored_row": row,
            })
            continue

        domain = record.get("domain", "ecommerce")
        # Reconstruct the evidence the verifier checks against.
        _reset_domain(domain)
        if domain == "ecommerce":
            _seed_database("ecommerce", {"orders": record.get("db_state_after") or []})
        else:
            _seed_database("reference", record.get("db_seed", {}))

        state = _replay_state(record, config, domain, seed)
        row = build_result_row(task=task, state=state, version=version_key, seed=seed)
        results.append({
            "task": task, "state": state, "version": version_key,
            "seed": seed, "error": None, "scored_row": row,
        })
        if verbose:
            print(
                f"[REPLAY:{version_key}] seed={seed} {record.get('scenario_id')} | "
                f"audit={state.get('reliability_verdict_audit')}"
            )
    return results


def _replay_state(record: dict, config: RuntimeConfig, domain: str, seed: int | None) -> dict:
    answer = record.get("final_answer", "")
    executed_tools = record.get("executed_tools", []) or []
    structural_issues = record.get("structural_issues", []) or []

    state: dict = {
        "messages": [{"role": "user", "content": record.get("input", "")}],
        "tool_call": None, "trace": [], "final_answer": answer,
        "reliability_report": None, "reliability_verdict": None,
        "reliability_verdict_audit": None, "reliability_score": None,
        "structural_audit": structural_issues, "tool_trace": record.get("tool_trace", []) or [],
        "executed_tools": executed_tools, "config": config, "domain": domain,
        "verifier_context": None, "prompt_tokens": 0, "completion_tokens": 0,
        "total_tokens": 0, "run_id": record.get("scenario_id"), "run_stamp": None,
        "run_started_at": None, "seed": seed,
    }

    if not config.use_verifier:
        # Baseline: no monitor runs. Enforcement off -> PASS, matching the e2e baseline.
        return state

    # Inject the frozen claims (never re-extract: pass the list even when empty so
    # the pipeline does not fall back to an LLM extraction call).
    claims = [Claim(**c) for c in record.get("claims", []) if isinstance(c, dict)]
    report = run_reliability_pipeline(
        domain=domain, query=record.get("input", ""), agent_answer=answer,
        model=config.llm_model, base_url=config.llm_base_url, write_logs=False,
        claims=claims, temperature=config.claim_extraction_temperature,
        seed=config.llm_seed, max_tokens=config.claim_extraction_max_tokens,
    )
    state["reliability_report"] = report.model_dump()
    state["reliability_score"] = report.reliability_score

    # Apply the frozen structural issues only when this version enables structural audit.
    apply_structural = config.enforce_intervention and config.use_structural_audit
    structural_blocks = [
        item for item in structural_issues
        if apply_structural and item.get("action") == "BLOCK"
    ]
    audit_verdict = "BLOCK" if structural_blocks else report.verdict
    state["reliability_verdict_audit"] = audit_verdict
    state["reliability_verdict"] = audit_verdict if config.enforce_intervention else "PASS"
    return state


if __name__ == "__main__":
    import argparse
    import json
    import os
    import random
    from eval.metrics import compute_metrics

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios", type=int, default=10, help="Number of scenarios to run"
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Number of scenarios to skip from the start of input file before sampling",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="tasks/ecommerce_scenarios.json",
        help="Scenarios file",
    )
    parser.add_argument(
        "--versions", nargs="+", default=list(VERSIONS.keys()), help="Versions to run"
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=[42],
        help="Random seeds to run for each version",
    )
    parser.add_argument(
        "--stratified",
        action="store_true",
        help="Sample evenly across failure categories F0-F5 using scenario id prefix",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="logs/ablation_metrics.json",
        help="Output file for metrics",
    )
    parser.add_argument(
        "--disable-fault-injection",
        action="store_true",
        help="Disable ecommerce F4 false-success fault injection.",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        all_scenarios = json.load(f)
    source_scenarios = all_scenarios[args.skip :]

    if args.stratified:
        categories = [f"F{i}" for i in range(6)]
        quota = args.scenarios // len(categories)
        grouped = {cat: [] for cat in categories}

        for scenario in source_scenarios:
            scenario_id = str(scenario.get("id", ""))
            for cat in categories:
                if scenario_id.startswith(cat):
                    grouped[cat].append(scenario)
                    break

        rng = random.Random(42)
        scenarios = []
        for cat in categories:
            candidates = grouped[cat]
            if len(candidates) <= quota:
                scenarios.extend(candidates)
            else:
                scenarios.extend(rng.sample(candidates, quota))
    else:
        scenarios = source_scenarios[: args.scenarios]

    print(f"Running {len(scenarios)} scenarios on versions: {args.versions}")

    all_metrics = {}
    for version_key in args.versions:
        results = run_version(
            version_key,
            scenarios,
            seeds=args.seeds,
            enable_fault_injection=not args.disable_fault_injection,
        )
        metrics = compute_metrics(results)
        all_metrics[version_key] = metrics
        print(f"\n[METRICS] {version_key}: {metrics}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Metrics written to {args.output}")
