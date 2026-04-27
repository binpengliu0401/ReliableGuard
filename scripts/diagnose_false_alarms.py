#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    rows = _load_false_alarm_rows(csv_path)
    if not rows:
        print("No false alarms found.")
        return 0

    output_dir = csv_path.parent
    set_slug = _infer_set_slug(csv_path)
    found = 0
    for row in rows:
        state_path = _state_path(output_dir, set_slug, row)
        print(
            f"\n=== {row['scenario_id']} | {row['version']} | "
            f"seed={row['seed']} | domain={row['domain']} ==="
        )
        print(
            f"expected={row['expected_outcome']} actual={row['actual_outcome']} "
            f"reliability_score={row['reliability_score']} "
            f"fact_accuracy={row['fact_accuracy']}"
        )

        if not state_path.exists():
            print(f"state_json_missing={state_path}")
            continue

        found += 1
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        report = ((payload.get("state") or {}).get("reliability_report") or {})
        _print_report(report)

    if found == 0:
        print(
            "\nNo state JSON files were found. Re-run run_ablation.py with "
            "--save-states false-alarms or --save-states all."
        )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print reliability reports for expected-PASS false alarms."
    )
    parser.add_argument("--csv", required=True, help="Path to set_a_rows.csv or set_b_rows.csv.")
    return parser.parse_args(argv)


def _load_false_alarm_rows(csv_path: Path) -> list[dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        row
        for row in rows
        if row.get("expected_outcome") == "PASS"
        and row.get("actual_outcome") not in {"", "PASS"}
    ]


def _infer_set_slug(csv_path: Path) -> str:
    name = csv_path.name.lower()
    if name.startswith("set_a"):
        return "set_a"
    if name.startswith("set_b"):
        return "set_b"
    return "set_b"


def _state_path(output_dir: Path, set_slug: str, row: dict[str, str]) -> Path:
    scenario_id = _safe_filename(row.get("scenario_id", "unknown"))
    version = _safe_filename(row.get("version", "unknown"))
    domain = _safe_filename(row.get("domain", "unknown"))
    seed = _safe_filename(row.get("seed", "unknown"))
    return output_dir / "states" / set_slug / version / domain / f"{scenario_id}_seed{seed}.json"


def _print_report(report: dict[str, Any]) -> None:
    print(f"report_score={report.get('reliability_score')}")
    print(f"summary={report.get('summary')}")
    for trace in report.get("traces", []) or []:
        claim = trace.get("claim", {})
        verification = trace.get("verification", {})
        risk = trace.get("risk", {})
        intervention = trace.get("intervention", {})
        print(
            "- "
            f"claim_id={claim.get('claim_id')} "
            f"text={claim.get('text')!r} "
            f"evidence_state={verification.get('evidence_state')} "
            f"risk={risk.get('risk_level')}:{risk.get('score')} "
            f"action={intervention.get('action')} "
            f"reason={verification.get('reason')}"
        )


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


if __name__ == "__main__":
    raise SystemExit(main())
