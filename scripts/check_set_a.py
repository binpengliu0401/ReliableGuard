from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.metrics import normalize_expected


DATASETS = {
    "ecommerce": PROJECT_ROOT / "tasks" / "ecommerce_scenarios.json",
    "reference": PROJECT_ROOT / "tasks" / "reference_scenarios.json",
}
OUTPUT_PATH = PROJECT_ROOT / "results" / "set_a_quality_report.json"
REQUIRED_FIELDS = ("id", "input", "expected_outcome", "failure_mode")
VALID_EXPECTED = ("PASS", "WARN", "BLOCK")
KNOWN_FAILURE_MODES = ("F0", "F1", "F2", "F3", "F4", "F5")


def _load_scenarios(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list.")
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{path} item at index {index} must be an object.")
    return data


def _is_missing(item: dict[str, Any], field: str) -> bool:
    return field not in item or item[field] is None


def _scenario_id(item: dict[str, Any], index: int) -> str:
    value = item.get("id")
    if value is None:
        return f"<missing:{index}>"
    return str(value)


def _raw_expected_value(item: dict[str, Any]) -> str:
    value = item.get("expected_verdict") or item.get("expected_outcome") or "PASS"
    return str(value)


def analyze_dataset(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    missing_fields = {field: 0 for field in REQUIRED_FIELDS}
    ids: list[str] = []
    empty_input: list[str] = []
    expected_counts: Counter[str] = Counter()
    other_expected_counts: Counter[str] = Counter()
    failure_mode_counts = {mode: 0 for mode in KNOWN_FAILURE_MODES}
    failure_mode_counts["unknown"] = 0
    unknown_expected_samples: list[dict[str, str]] = []

    for index, item in enumerate(scenarios):
        scenario_id = _scenario_id(item, index)

        for field in REQUIRED_FIELDS:
            if _is_missing(item, field):
                missing_fields[field] += 1

        if not _is_missing(item, "id"):
            ids.append(str(item["id"]))

        raw_input = item.get("input")
        if not isinstance(raw_input, str) or not raw_input.strip():
            empty_input.append(scenario_id)

        normalized_expected = normalize_expected(item)
        if normalized_expected in VALID_EXPECTED:
            expected_counts[normalized_expected] += 1
        else:
            raw_value = _raw_expected_value(item)
            other_expected_counts[raw_value] += 1
            unknown_expected_samples.append(
                {"id": scenario_id, "raw_value": raw_value}
            )

        failure_mode = item.get("failure_mode")
        if failure_mode in KNOWN_FAILURE_MODES:
            failure_mode_counts[str(failure_mode)] += 1
        else:
            failure_mode_counts["unknown"] += 1

    id_counts = Counter(ids)
    duplicate_ids = sorted(
        scenario_id for scenario_id, count in id_counts.items() if count > 1
    )

    return {
        "total": len(scenarios),
        "missing_fields": missing_fields,
        "duplicate_ids": duplicate_ids,
        "empty_input": empty_input,
        "expected_outcome_distribution": {
            "PASS": expected_counts["PASS"],
            "WARN": expected_counts["WARN"],
            "BLOCK": expected_counts["BLOCK"],
            "OTHER": dict(sorted(other_expected_counts.items())),
        },
        "failure_mode_distribution": failure_mode_counts,
        "unknown_expected_outcome_samples": unknown_expected_samples,
    }


def _has_blocking_issue(section: dict[str, Any]) -> bool:
    required_missing = {
        field: count
        for field, count in section["missing_fields"].items()
        if field != "failure_mode"
    }
    return any(
        [
            bool(section["duplicate_ids"]),
            bool(section["empty_input"]),
            bool(section["expected_outcome_distribution"]["OTHER"]),
            any(count > 0 for count in required_missing.values()),
        ]
    )


def _valid_expected_total(section: dict[str, Any]) -> int:
    distribution = section["expected_outcome_distribution"]
    return sum(int(distribution[label]) for label in VALID_EXPECTED)


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {}
    for name, path in DATASETS.items():
        report[name] = analyze_dataset(_load_scenarios(path))

    total = report["ecommerce"]["total"] + report["reference"]["total"]
    valid_expected = _valid_expected_total(report["ecommerce"]) + _valid_expected_total(
        report["reference"]
    )
    report["combined"] = {
        "total": total,
        "label_coverage": round(valid_expected / total, 3) if total else 0.0,
        "has_blocking_issue": _has_blocking_issue(report["ecommerce"])
        or _has_blocking_issue(report["reference"]),
    }
    return report


def _warn_line(has_issue: bool, label: str, value: Any) -> str:
    prefix = "\u26a0 " if has_issue else "  "
    return f"{prefix}{label}: {value}"


def print_summary(report: dict[str, Any]) -> None:
    print("Set A quality summary")
    for domain in ("ecommerce", "reference"):
        section = report[domain]
        missing_required = {
            field: count
            for field, count in section["missing_fields"].items()
            if field != "failure_mode"
        }
        unknown_failure = section["failure_mode_distribution"]["unknown"]
        other_expected = section["expected_outcome_distribution"]["OTHER"]
        print(f"\n[{domain}] total={section['total']}")
        print(_warn_line(any(missing_required.values()), "missing_required_fields", missing_required))
        print(_warn_line(section["missing_fields"]["failure_mode"] > 0, "missing_failure_mode", section["missing_fields"]["failure_mode"]))
        print(_warn_line(bool(section["duplicate_ids"]), "duplicate_ids", len(section["duplicate_ids"])))
        print(_warn_line(bool(section["empty_input"]), "empty_input", len(section["empty_input"])))
        print(_warn_line(bool(other_expected), "unknown_expected_outcome", other_expected))
        print(_warn_line(unknown_failure > 0, "unknown_failure_mode", unknown_failure))

    combined = report["combined"]
    print("\n[combined]")
    print(_warn_line(combined["has_blocking_issue"], "has_blocking_issue", combined["has_blocking_issue"]))
    print(f"  label_coverage: {combined['label_coverage']}")
    print(f"  report_path: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


def main() -> int:
    report = build_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
