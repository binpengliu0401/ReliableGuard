import json
from dataclasses import replace

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


def run_version(
    version_key: str,
    scenarios: list[dict],
    verbose: bool = True,
    config_override: RuntimeConfig | None = None,
    seeds: list[int] | None = None,
) -> list[dict]:
    base_config = config_override if config_override else VERSIONS[version_key]
    selected_seeds = seeds or [42]
    results = []

    print(f"\n{'#'*60}")
    print(f"# VERSION: {base_config.version_name}")
    print(f"{'#'*60}")

    for seed in selected_seeds:
        config = replace(base_config, llm_temperature=0.7, llm_seed=seed)
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
                    state = run_agent(
                        task["input"],
                        domain=domain,
                        config=config,
                    )
                    state["seed"] = seed

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

    return results


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
        temperature=config.llm_temperature,
        seed=config.llm_seed,
    )
    state["reliability_report"] = report.model_dump()
    state["reliability_verdict_audit"] = report.verdict
    state["reliability_score"] = report.reliability_score
    state["reliability_verdict"] = report.verdict if config.enforce_intervention else "PASS"
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
        results = run_version(version_key, scenarios, seeds=args.seeds)
        metrics = compute_metrics(results)
        all_metrics[version_key] = metrics
        print(f"\n[METRICS] {version_key}: {metrics}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Metrics written to {args.output}")
