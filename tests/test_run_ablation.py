import csv
import json
from pathlib import Path

import scripts.run_ablation as run_ablation


def test_default_versions_excludes_v2():
    from scripts.run_ablation import DEFAULT_VERSIONS

    assert "V2_NoReliability" not in DEFAULT_VERSIONS
    assert DEFAULT_VERSIONS == ["V1_Baseline", "V3_AuditOnly", "V4_Full"]


def _write_scenarios(tmp_path: Path) -> tuple[Path, Path, Path]:
    ecommerce = tmp_path / "ecommerce.json"
    reference = tmp_path / "reference.json"
    tier_b = tmp_path / "tier_b.json"

    ecommerce.write_text(
        json.dumps(
            [
                {
                    "id": "EC-1",
                    "input": "create order",
                    "expected_outcome": "PASS",
                }
            ]
        ),
        encoding="utf-8",
    )
    reference.write_text(
        json.dumps(
            [
                {
                    "id": "REF-1",
                    "domain": "reference",
                    "input": "parse refs",
                    "expected_outcome": "PASS",
                }
            ]
        ),
        encoding="utf-8",
    )
    tier_b.write_text(
        json.dumps(
            [
                {
                    "id": "TB-EC-1",
                    "domain": "ecommerce",
                    "input": "stress ecommerce",
                    "expected_outcome": "PASS",
                    "verifiable_facts": ["order_count=1"],
                },
                {
                    "id": "TB-REF-1",
                    "domain": "reference",
                    "input": "stress reference",
                    "expected_verdict": "WARN",
                    "verifiable_facts": ["parse_status=ok"],
                },
            ]
        ),
        encoding="utf-8",
    )
    return ecommerce, reference, tier_b


def _fake_results(version: str, scenarios: list[dict], seeds: list[int]) -> list[dict]:
    results = []
    for i in range(5):
        task = dict(scenarios[i % len(scenarios)])
        seed = seeds[i % len(seeds)]
        state = {
            "reliability_verdict": "PASS",
            "reliability_verdict_audit": "PASS",
            "reliability_score": 0.5,
            "final_answer": "ok",
            "executed_tools": [],
            "total_tokens": 10,
        }
        row = {
            "scenario_id": task.get("id"),
            "domain": task.get("domain", "ecommerce"),
            "version": version,
            "seed": seed,
            "expected_outcome": task.get("expected_verdict")
            or task.get("expected_outcome", "PASS"),
            "actual_outcome": "PASS",
            "actual_audit_outcome": "PASS",
            "pass_fail": True,
            "outcome_score": 3,
            "reliability_score": 0.5,
            "fact_accuracy": 1.0,
            "tokens": 10,
            "error": None,
        }
        results.append(
            {
                "task": task,
                "state": state,
                "version": version,
                "seed": seed,
                "error": None,
                "scored_row": row,
                "fact_accuracy": 1.0,
            }
        )
    return results


def _run_main(tmp_path, monkeypatch, fake_run_version):
    ecommerce, reference, tier_b = _write_scenarios(tmp_path)
    output_dir = tmp_path / "results"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(run_ablation, "run_version", fake_run_version)

    code = run_ablation.main(
        [
            "--ecommerce",
            str(ecommerce),
            "--reference",
            str(reference),
            "--tier-b",
            str(tier_b),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert code == 0
    return output_dir


def test_set_a_metrics_has_all_versions_and_domains(tmp_path, monkeypatch):
    output_dir = _run_main(tmp_path, monkeypatch, _fake_results)

    metrics = json.loads((output_dir / "set_a_metrics.json").read_text(encoding="utf-8"))

    assert set(metrics) == set(run_ablation.DEFAULT_VERSIONS)
    for version_metrics in metrics.values():
        assert set(version_metrics) == {"ecommerce", "reference"}


def test_set_b_metrics_is_written_separately(tmp_path, monkeypatch):
    output_dir = _run_main(tmp_path, monkeypatch, _fake_results)

    set_a = json.loads((output_dir / "set_a_metrics.json").read_text(encoding="utf-8"))
    set_b = json.loads((output_dir / "set_b_metrics.json").read_text(encoding="utf-8"))

    assert set_b
    assert set_a is not set_b
    for version_metrics in set_b.values():
        assert set(version_metrics) == {"ecommerce", "reference"}


def test_csv_files_have_expected_headers(tmp_path, monkeypatch):
    output_dir = _run_main(tmp_path, monkeypatch, _fake_results)

    for filename in ["set_a_rows.csv", "set_b_rows.csv"]:
        with open(output_dir / filename, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            assert next(reader) == run_ablation.CSV_FIELDS


def test_summary_contains_both_sections(tmp_path, monkeypatch):
    output_dir = _run_main(tmp_path, monkeypatch, _fake_results)

    summary = (output_dir / "summary.txt").read_text(encoding="utf-8")

    assert "SET A" in summary
    assert "SET B" in summary


def test_missing_openrouter_api_key_exits_with_error(tmp_path, monkeypatch, capsys):
    ecommerce, reference, tier_b = _write_scenarios(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    code = run_ablation.main(
        [
            "--ecommerce",
            str(ecommerce),
            "--reference",
            str(reference),
            "--tier-b",
            str(tier_b),
            "--output-dir",
            str(tmp_path / "results"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "OPENROUTER_API_KEY is not set" in captured.err


def test_group_exception_does_not_abort_remaining_groups(tmp_path, monkeypatch):
    calls = []

    def flaky_run_version(version: str, scenarios: list[dict], seeds: list[int]):
        domain = scenarios[0].get("domain", "ecommerce")
        calls.append((version, domain))
        if version == "V1_Baseline" and domain == "ecommerce":
            raise RuntimeError("boom")
        return _fake_results(version, scenarios, seeds)

    output_dir = _run_main(tmp_path, monkeypatch, flaky_run_version)
    metrics = json.loads((output_dir / "set_a_metrics.json").read_text(encoding="utf-8"))

    assert metrics["V1_Baseline"]["ecommerce"]["error"] == "RuntimeError: boom"
    assert metrics["V1_Baseline"]["reference"]["total_tasks"] == 5
    assert ("V4_Full", "reference") in calls
