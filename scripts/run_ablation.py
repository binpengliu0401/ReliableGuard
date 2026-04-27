#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.ablation_runner import run_version
from eval.config.ablation_versions import VERSIONS
from eval.metrics import build_result_row, compute_metrics, normalize_expected


DEFAULT_VERSIONS = ["V1_Baseline", "V2_AuditOnly", "V3_Intervention"]
DEFAULT_SEEDS = [42, 123, 7]
VERSION_ALIASES = {
    "V1": "V1_Baseline",
    "V2": "V2_AuditOnly",
    "V3": "V3_Intervention",
    "V4": "V3_Intervention",
}
CSV_FIELDS = [
    "scenario_id",
    "domain",
    "version",
    "seed",
    "expected_outcome",
    "actual_outcome",
    "actual_audit_outcome",
    "pass_fail",
    "outcome_score",
    "reliability_score",
    "fact_accuracy",
    "tokens",
    "error",
]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        return 1

    output_dir = _resolve_output_dir(Path(args.output_dir), args.timestamped_output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OUTPUT_DIR] {output_dir}")

    all_summaries: list[str] = []
    if args.set in {"A", "both"}:
        set_a = _run_set(
            label="Set A",
            set_slug="set_a",
            scenarios_by_domain=_load_set_a(args.ecommerce, args.reference),
            versions=args.versions,
            seeds=args.seeds,
            output_dir=output_dir,
            save_states=args.save_states,
            debug_false_alarms=args.debug_false_alarms,
        )
        _write_outputs(
            output_dir=output_dir,
            metrics_path="set_a_metrics.json",
            rows_path="set_a_rows.csv",
            metrics=set_a["metrics"],
            rows=set_a["rows"],
        )
        all_summaries.append(
            _format_summary_section(
                title="SET A: Known Failure Modes (F0-F5)",
                aggregate_results=set_a["aggregate_results"],
                versions=args.versions,
                include_fact_accuracy=False,
            )
        )

    if args.set in {"B", "both"}:
        set_b = _run_set(
            label="Set B",
            set_slug="set_b",
            scenarios_by_domain=_load_set_b(args.tier_b),
            versions=args.versions,
            seeds=args.seeds,
            output_dir=output_dir,
            save_states=args.save_states,
            debug_false_alarms=args.debug_false_alarms,
        )
        _write_outputs(
            output_dir=output_dir,
            metrics_path="set_b_metrics.json",
            rows_path="set_b_rows.csv",
            metrics=set_b["metrics"],
            rows=set_b["rows"],
        )
        all_summaries.append(
            _format_summary_section(
                title="SET B: Generalization Stress Test (Tier B)",
                aggregate_results=set_b["aggregate_results"],
                versions=args.versions,
                include_fact_accuracy=True,
            )
        )

    summary = "\n\n".join(all_summaries)
    print(summary)
    (output_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Reliable Guard ablation sets.")
    parser.add_argument("--set", choices=["A", "B", "both"], default="both")
    parser.add_argument("--versions", nargs="+", default=DEFAULT_VERSIONS)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--ecommerce", default="tasks/ecommerce_scenarios.json")
    parser.add_argument("--reference", default="tasks/reference_scenarios.json")
    parser.add_argument("--tier-b", default="tasks/tier_b_prompts.json")
    parser.add_argument("--output-dir", default="results/")
    parser.add_argument(
        "--timestamped-output",
        action="store_true",
        help="Write outputs under output-dir/YYYYMMDD/HHMMSS to avoid overwrites.",
    )
    parser.add_argument(
        "--save-states",
        choices=["none", "false-alarms", "all"],
        default="none",
        help="Persist JSON-safe agent states for later diagnosis.",
    )
    parser.add_argument(
        "--debug-false-alarms",
        action="store_true",
        help="Print reliability reports for expected PASS rows that do not PASS.",
    )
    args = parser.parse_args(argv)

    args.versions = [VERSION_ALIASES.get(version, version) for version in args.versions]
    unknown_versions = [version for version in args.versions if version not in VERSIONS]
    if unknown_versions:
        parser.error(f"Unknown version(s): {', '.join(unknown_versions)}")
    return args


def _resolve_output_dir(base_dir: Path, timestamped: bool) -> Path:
    if not timestamped:
        return base_dir
    now = datetime.now()
    return base_dir / now.strftime("%Y%m%d") / now.strftime("%H%M%S")


def _load_json(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Scenario file must contain a list: {path}")
    return data


def _load_set_a(ecommerce_path: str, reference_path: str) -> dict[str, list[dict[str, Any]]]:
    ecommerce = []
    for scenario in _load_json(ecommerce_path):
        tagged = dict(scenario)
        tagged.setdefault("domain", "ecommerce")
        ecommerce.append(tagged)

    reference = []
    for scenario in _load_json(reference_path):
        tagged = dict(scenario)
        tagged.setdefault("domain", "reference")
        reference.append(tagged)

    return {"ecommerce": ecommerce, "reference": reference}


def _load_set_b(tier_b_path: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for scenario in _load_json(tier_b_path):
        domain = str(scenario.get("domain", "unknown"))
        grouped.setdefault(domain, []).append(dict(scenario))
    return grouped


def _run_set(
    label: str,
    set_slug: str,
    scenarios_by_domain: dict[str, list[dict[str, Any]]],
    versions: list[str],
    seeds: list[int],
    output_dir: Path,
    save_states: str,
    debug_false_alarms: bool,
) -> dict[str, Any]:
    metrics: dict[str, dict[str, dict[str, Any]]] = {
        version: {} for version in versions
    }
    aggregate_results: dict[str, list[dict[str, Any]]] = {
        version: [] for version in versions
    }
    rows: list[dict[str, Any]] = []

    for version in versions:
        for domain, scenarios in scenarios_by_domain.items():
            print(
                f"[{_timestamp()}] START {label} version={version} "
                f"domain={domain} scenarios={len(scenarios)} seeds={seeds}"
            )
            status = "ok"
            try:
                results = run_version(version, scenarios, seeds=seeds)
            except Exception as exc:
                error_label = f"{type(exc).__name__}: {exc}"
                status = "error"
                print(
                    f"[{_timestamp()}] ERROR {label} version={version} "
                    f"domain={domain} {error_label}",
                    file=sys.stderr,
                )
                metrics[version][domain] = {"error": error_label}
                print(
                    f"[{_timestamp()}] END {label} version={version} "
                    f"domain={domain} status={status}"
                )
                continue

            metrics[version][domain] = compute_metrics(results)
            aggregate_results[version].extend(results)
            for result in results:
                rows.append(_result_to_csv_row(result))
                if _should_save_state(result, save_states):
                    _write_state(output_dir, set_slug, result)
                if debug_false_alarms and _is_false_alarm(result):
                    _print_false_alarm_report(result)
            print(
                f"[{_timestamp()}] END {label} version={version} "
                f"domain={domain} status={status} rows={len(results)}"
            )

    return {
        "metrics": metrics,
        "aggregate_results": aggregate_results,
        "rows": rows,
    }


def _write_outputs(
    output_dir: Path,
    metrics_path: str,
    rows_path: str,
    metrics: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    (output_dir / metrics_path).write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with open(output_dir / rows_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _result_to_csv_row(result: dict[str, Any]) -> dict[str, Any]:
    row = result.get("scored_row")
    if not row:
        row = build_result_row(
            task=result.get("task", {}),
            state=result.get("state"),
            version=str(result.get("version", "")),
            error=result.get("error"),
            seed=result.get("seed"),
            fact_accuracy=result.get("fact_accuracy"),
        )

    fact_accuracy = result.get("fact_accuracy")
    if fact_accuracy is None:
        fact_accuracy = row.get("fact_accuracy")

    return {
        "scenario_id": row.get("scenario_id", ""),
        "domain": row.get("domain", ""),
        "version": row.get("version", result.get("version", "")),
        "seed": row.get("seed", result.get("seed", "")),
        "expected_outcome": row.get("expected_outcome", ""),
        "actual_outcome": row.get("actual_outcome", ""),
        "actual_audit_outcome": row.get("actual_audit_outcome", ""),
        "pass_fail": row.get("pass_fail", ""),
        "outcome_score": row.get("outcome_score", ""),
        "reliability_score": _blank_if_none(row.get("reliability_score")),
        "fact_accuracy": _blank_if_none(fact_accuracy),
        "tokens": row.get("tokens", ""),
        "error": row.get("error", result.get("error", "")) or "",
    }


def _format_summary_section(
    title: str,
    aggregate_results: dict[str, list[dict[str, Any]]],
    versions: list[str],
    include_fact_accuracy: bool,
) -> str:
    metrics_by_version = {
        version: compute_metrics(results) if results else {}
        for version, results in aggregate_results.items()
    }

    metric_label = "avg_fact_accuracy" if include_fact_accuracy else "block_rate"
    lines = [
        f"=== {title} ===",
        f"{'Version':<18} {'pass_rate (95% CI)':<22} {'FAR':<8} "
        f"{'avg_reliability':<17} {metric_label}",
    ]

    for version in versions:
        metrics = metrics_by_version.get(version, {})
        lines.append(
            f"{version:<18} "
            f"{_format_pass_rate(metrics):<22} "
            f"{_format_far(metrics, aggregate_results.get(version, [])):<8} "
            f"{_format_optional_float(metrics.get('avg_reliability_score')):<17} "
            f"{_format_optional_float(metrics.get(metric_label))}"
        )
    return "\n".join(lines)


def _format_pass_rate(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "N/A"
    pass_rate = metrics.get("pass_rate")
    ci = metrics.get("pass_rate_ci")
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        return f"{pass_rate} [{ci[0]}, {ci[1]}]"
    return str(pass_rate) if pass_rate is not None else "N/A"


def _format_far(metrics: dict[str, Any], results: list[dict[str, Any]]) -> str:
    if not metrics or not _has_far_denominator(results):
        return "N/A"
    return _format_optional_float(metrics.get("false_acceptance_rate"))


def _has_far_denominator(results: list[dict[str, Any]]) -> bool:
    for result in results:
        expected = normalize_expected(result.get("task", {}))
        if expected in {"WARN", "BLOCK"}:
            return True
    return False


def _should_save_state(result: dict[str, Any], save_states: str) -> bool:
    if save_states == "all":
        return True
    if save_states == "false-alarms":
        return _is_false_alarm(result)
    return False


def _is_false_alarm(result: dict[str, Any]) -> bool:
    row = result.get("scored_row") or {}
    if row:
        expected = row.get("expected_outcome")
        actual = row.get("actual_outcome")
        return expected == "PASS" and actual != "PASS"

    expected = normalize_expected(result.get("task", {}))
    state = result.get("state")
    if state is None:
        actual = "ERROR"
    else:
        actual = state.get("reliability_verdict") or "PASS"
    return expected == "PASS" and actual != "PASS"


def _write_state(output_dir: Path, set_slug: str, result: dict[str, Any]) -> Path:
    row = result.get("scored_row") or {}
    scenario_id = _safe_filename(str(row.get("scenario_id") or result.get("task", {}).get("id", "unknown")))
    version = _safe_filename(str(row.get("version") or result.get("version", "unknown")))
    domain = _safe_filename(str(row.get("domain") or result.get("task", {}).get("domain", "unknown")))
    seed = _safe_filename(str(row.get("seed") or result.get("seed", "unknown")))
    path = output_dir / "states" / set_slug / version / domain / f"{scenario_id}_seed{seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": result.get("task"),
        "version": result.get("version"),
        "seed": result.get("seed"),
        "error": result.get("error"),
        "scored_row": result.get("scored_row"),
        "fact_snapshot": result.get("fact_snapshot"),
        "fact_accuracy": result.get("fact_accuracy"),
        "trace_fact_scores": result.get("trace_fact_scores"),
        "state": result.get("state"),
    }
    path.write_text(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _print_false_alarm_report(result: dict[str, Any]) -> None:
    row = result.get("scored_row") or {}
    report = (result.get("state") or {}).get("reliability_report") or {}
    print(
        f"[FALSE_ALARM] scenario={row.get('scenario_id')} "
        f"version={row.get('version')} seed={row.get('seed')} "
        f"score={row.get('reliability_score')}"
    )
    _print_report_details(report)


def _print_report_details(report: dict[str, Any]) -> None:
    print(f"  summary: {report.get('summary')}")
    for trace in report.get("traces", []) or []:
        claim = trace.get("claim", {}) if isinstance(trace, dict) else {}
        verification = trace.get("verification", {}) if isinstance(trace, dict) else {}
        print(
            "  claim="
            f"{claim.get('claim_id')}: {claim.get('text')} | "
            f"evidence_state={verification.get('evidence_state')} | "
            f"reason={verification.get('reason')}"
        )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return str(value)


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _format_optional_float(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _blank_if_none(value: Any) -> Any:
    return "" if value is None else value


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
