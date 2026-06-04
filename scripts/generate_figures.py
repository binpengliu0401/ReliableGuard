#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_CACHE_ROOT = Path(tempfile.gettempdir()) / "reliable_guard_figure_cache"
_MPL_CONFIG_DIR = _CACHE_ROOT / "matplotlib"
_XDG_CACHE_DIR = _CACHE_ROOT / "xdg"
for _cache_dir in (_MPL_CONFIG_DIR, _XDG_CACHE_DIR):
    _cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(_MPL_CONFIG_DIR)
os.environ["XDG_CACHE_HOME"] = str(_XDG_CACHE_DIR)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


FIGURES_DIR = Path("figures")

VERSION_ORDER = ["V1_Baseline", "V2_AuditOnly", "V3_Intervention"]
VERSION_LABELS = {
    "V1_Baseline": "V1\nBaseline",
    "V2_AuditOnly": "V2\nAuditOnly",
    "V3_Intervention": "V3\nIntervention",
    "V3_NoStructural": "V3\nNoStructural",
}
VERSION_COLORS = {
    "V1_Baseline": "#4878CF",
    "V2_AuditOnly": "#6ACC65",
    "V3_Intervention": "#D65F5F",
    "V3_NoStructural": "#B47CC7",
}
METRIC_COLORS = {
    "risk_detection_rate": "#D65F5F",
    "false_acceptance_rate": "#D65F5F",
    "false_alarm_rate": "#EE854A",
    "safe_pass_rate": "#6ACC65",
}
DOMAIN_ORDER = ["ecommerce", "reference"]
STAGE_LATENCY_ORDER = [
    "extract_claims",
    "classify_verifiability",
    "verify_claims",
    "score_risks",
    "decide_interventions",
    "generate_report",
    "total_pipeline",
]


def main() -> None:
    _configure_style()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    set_a_dir = _latest_set_a_dir()
    set_b_dir = _latest_set_b_dir()
    structural_ablation_dir = _latest_structural_ablation_dir()

    generate_fig1_set_a_main(set_a_dir)
    generate_fig2_set_a_failure_modes(set_a_dir)
    generate_fig3_structural(set_a_dir, structural_ablation_dir)
    generate_fig4_set_b_generalization(set_b_dir)
    generate_table_main_ablation(set_a_dir)
    if set_a_dir is None:
        print("SKIP table_evidence_state.tex: result directory not found")
        print("SKIP table_latency.tex: result directory not found")
    else:
        set_a_metrics_path = set_a_dir / "set_a_metrics.json"
        generate_table_evidence_state(
            str(set_a_metrics_path),
            str(FIGURES_DIR / "table_evidence_state.tex"),
        )
        generate_table_latency(
            str(set_a_metrics_path),
            str(FIGURES_DIR / "table_latency.tex"),
        )


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.grid": False,
        }
    )


def generate_fig1_set_a_main(base_dir: Path | None) -> None:
    output = FIGURES_DIR / "fig1_set_a_main.pdf"
    if base_dir is None:
        print(f"SKIP {output.name}: result directory not found")
        return

    metrics_path = base_dir / "set_a_metrics.json"
    metrics = _load_metrics(metrics_path, output.name)
    if metrics is None:
        return

    metric_order = [
        "risk_detection_rate",
        "false_alarm_rate",
        "safe_pass_rate",
    ]
    metric_labels = {
        "risk_detection_rate": "Risk Detection",
        "false_alarm_rate": "False Alarm",
        "safe_pass_rate": "Safe Pass",
    }

    fig, ax = plt.subplots(figsize=(10, 4))
    centers = _domain_version_centers()
    width = 0.18
    offset_step = 0.28

    for metric_index, metric in enumerate(metric_order):
        xs = []
        ys = []
        for domain in DOMAIN_ORDER:
            for version in VERSION_ORDER:
                xs.append(
                    centers[(domain, version)] + (metric_index - 1) * offset_step
                )
                ys.append(_metric_value(metrics, version, domain, metric))
        bars = ax.bar(
            xs,
            ys,
            width=width,
            color=METRIC_COLORS[metric],
            label=metric_labels[metric],
        )
        _label_bars(ax, bars, y_offset=10 if metric == "false_alarm_rate" else 3)

    _apply_domain_axis(ax, centers)
    ax.axvline(3.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Rate")
    ax.set_title("Set A: Ablation Comparison", pad=16)
    ax.legend(frameon=False, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.40))
    _despine(ax)
    fig.subplots_adjust(bottom=0.34, top=0.86)
    fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"WROTE {output}")


def generate_fig2_set_a_failure_modes(base_dir: Path | None) -> None:
    output = FIGURES_DIR / "fig2_set_a_failure_modes.pdf"
    if base_dir is None:
        print(f"SKIP {output.name}: result directory not found")
        return

    rows_path = base_dir / "set_a_rows.csv"
    if not _path_exists(rows_path, output.name):
        return

    failure_modes = ["F1", "F2", "F3", "F4", "F5"]
    rates = _failure_mode_detection_rates(
        rows_path=rows_path,
        versions=VERSION_ORDER,
        domain="ecommerce",
        failure_modes=failure_modes,
    )
    if rates is None:
        print(f"SKIP {output.name}: no ecommerce failure-mode rows found")
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    x_positions = list(range(len(failure_modes)))
    width = 0.24

    for index, version in enumerate(VERSION_ORDER):
        offsets = [x + (index - 1) * width for x in x_positions]
        bars = ax.bar(
            offsets,
            rates[version].tolist(),
            width=width,
            color=VERSION_COLORS[version],
            label=version,
        )
        _label_bars(ax, bars, y_offset=3 + index * 5)

    ax.set_xticks(x_positions)
    ax.set_xticklabels(failure_modes)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Detection Rate")
    ax.set_title("Set A Ecommerce: Detection Rate by Failure Mode", pad=16)
    ax.legend(frameon=False, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    _despine(ax)
    fig.subplots_adjust(bottom=0.24, top=0.86)
    fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"WROTE {output}")


def generate_fig3_structural(
    set_a_dir: Path | None,
    structural_ablation_dir: Path | None,
) -> None:
    output = FIGURES_DIR / "fig3_structural.pdf"
    if set_a_dir is None:
        print(f"SKIP {output.name}: result directory not found")
        return

    structural_metrics_path = set_a_dir / "set_a_metrics.json"
    structural_rows_path = set_a_dir / "set_a_rows.csv"
    if not _path_exists(structural_metrics_path, output.name):
        return
    if not _path_exists(structural_rows_path, output.name):
        return

    if structural_ablation_dir is None:
        print(f"SKIP {output.name}: structural ablation not yet run")
        return
    ablation_metrics_path = structural_ablation_dir / "set_a_metrics.json"
    ablation_rows_path = structural_ablation_dir / "set_a_rows.csv"
    if not _path_exists(ablation_metrics_path, output.name):
        return
    if not _path_exists(ablation_rows_path, output.name):
        return

    failure_modes = ["F2", "F4"]
    structural_rates = _failure_mode_detection_rates(
        rows_path=structural_rows_path,
        versions=["V3_Intervention"],
        domain="ecommerce",
        failure_modes=failure_modes,
    )
    claim_only_rates = _failure_mode_detection_rates(
        rows_path=ablation_rows_path,
        versions=["V3_NoStructural"],
        domain="ecommerce",
        failure_modes=failure_modes,
    )
    if structural_rates is None or claim_only_rates is None:
        print(f"SKIP {output.name}: missing ecommerce F2/F4 rows")
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    x_positions = list(range(len(failure_modes)))
    width = 0.28
    series = [
        ("V3_Intervention", structural_rates["V3_Intervention"].tolist()),
        ("V3_NoStructural", claim_only_rates["V3_NoStructural"].tolist()),
    ]

    for index, (version, values) in enumerate(series):
        offsets = [x + (index - 0.5) * width for x in x_positions]
        bars = ax.bar(
            offsets,
            values,
            width=width,
            color=VERSION_COLORS[version],
            label=version,
        )
        _label_bars(ax, bars, y_offset=3 + index * 7)

    ax.set_xticks(x_positions)
    ax.set_xticklabels(failure_modes)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Detection Rate")
    ax.set_title("Structural Audit vs. Claim-Only (Ecommerce F2 & F4)", pad=16)
    ax.legend(frameon=False, ncols=2, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    _despine(ax)
    fig.subplots_adjust(bottom=0.24, top=0.86)
    fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"WROTE {output}")


def generate_fig4_set_b_generalization(base_dir: Path | None) -> None:
    output = FIGURES_DIR / "fig4_set_b_generalization.pdf"
    if base_dir is None:
        print(f"SKIP {output.name}: result directory not found")
        return

    metrics_path = base_dir / "set_b_metrics.json"
    metrics = _load_metrics(metrics_path, output.name)
    if metrics is None:
        return

    metric_order = ["false_alarm_rate", "false_acceptance_rate"]
    metric_labels = {
        "false_alarm_rate": "False Alarm",
        "false_acceptance_rate": "False Acceptance",
    }

    fig, ax = plt.subplots(figsize=(10, 4))
    centers = _domain_version_centers()
    width = 0.22
    offset_step = 0.32

    for metric_index, metric in enumerate(metric_order):
        xs = []
        ys = []
        for domain in DOMAIN_ORDER:
            for version in VERSION_ORDER:
                xs.append(
                    centers[(domain, version)] + (metric_index - 0.5) * offset_step
                )
                ys.append(_metric_value(metrics, version, domain, metric))
        bars = ax.bar(
            xs,
            ys,
            width=width,
            color=METRIC_COLORS[metric],
            label=metric_labels[metric],
        )
        _label_bars(
            ax,
            bars,
            y_offset=10 if metric == "false_acceptance_rate" else 3,
        )

    _apply_domain_axis(ax, centers)
    ax.axvline(3.0, color="#777777", linestyle="--", linewidth=1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Rate")
    ax.set_title("Set B: Generalization Test", pad=16)
    ax.legend(frameon=False, ncols=2, loc="upper center", bbox_to_anchor=(0.5, -0.40))
    _despine(ax)
    fig.subplots_adjust(bottom=0.34, top=0.86)
    fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"WROTE {output}")


def generate_table_main_ablation(base_dir: Path | None) -> None:
    output = FIGURES_DIR / "table_main_ablation.tex"
    if base_dir is None:
        print(f"SKIP {output.name}: result directory not found")
        return

    metrics_path = base_dir / "set_a_metrics.json"
    metrics = _load_metrics(metrics_path, output.name)
    if metrics is None:
        return

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Set A Ablation Results}",
        r"\label{tab:set_a_ablation}",
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Version & Domain & RDR & FAR & False Alarm & Safe Pass & Pass Rate \\",
        r"\midrule",
    ]
    for domain in DOMAIN_ORDER:
        for version in VERSION_ORDER:
            domain_metrics = metrics.get(version, {}).get(domain, {})
            values = [
                _latex_escape(version),
                domain,
                _format_rate(domain_metrics.get("risk_detection_rate")),
                _format_rate(domain_metrics.get("false_acceptance_rate")),
                _format_rate(domain_metrics.get("false_alarm_rate")),
                _format_rate(domain_metrics.get("safe_pass_rate")),
                _format_rate(domain_metrics.get("pass_rate")),
            ]
            lines.append(" & ".join(values) + r" \\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {output}")


def generate_table_evidence_state(set_a_metrics_path: str, output_path: str) -> None:
    output = Path(output_path)
    metrics = _load_metrics(Path(set_a_metrics_path), output.name)
    if metrics is None:
        return

    rows = []
    for version in _ordered_versions(metrics):
        for domain in DOMAIN_ORDER:
            domain_metrics = _domain_metrics(metrics, version, domain)
            if "evidence_state_coverage" not in domain_metrics:
                continue
            rows.append(
                [
                    _latex_escape(version),
                    domain,
                    _format_decimal(domain_metrics.get("avg_supported_count"), 3),
                    _format_decimal(domain_metrics.get("avg_contradicted_count"), 3),
                    _format_decimal(domain_metrics.get("avg_unsupported_count"), 3),
                    _format_decimal(domain_metrics.get("avg_unverifiable_count"), 3),
                    _format_decimal(domain_metrics.get("avg_not_found_count"), 3),
                    _format_rate(domain_metrics.get("evidence_state_coverage")),
                ]
            )

    if not rows:
        print(f"SKIP {output.name}: missing evidence state metrics")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Set A Evidence State Distribution}",
        r"\label{tab:evidence_state}",
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r"Version & Domain & Supported & Contradicted & Unsupported & Unverifiable & Not Found & Coverage \\",
        r"\midrule",
    ]
    lines.extend(" & ".join(row) + r" \\" for row in rows)
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {output}")


def generate_table_latency(set_a_metrics_path: str, output_path: str) -> None:
    output = Path(output_path)
    metrics = _load_metrics(Path(set_a_metrics_path), output.name)
    if metrics is None:
        return

    domain_metrics = _domain_metrics(metrics, "V3_Intervention", "ecommerce")
    means = domain_metrics.get("stage_latency_mean_ms")
    p95s = domain_metrics.get("stage_latency_p95_ms")
    if not isinstance(means, dict) or not isinstance(p95s, dict):
        print(f"SKIP {output.name}: missing stage latency metrics")
        return

    rows = []
    for stage in STAGE_LATENCY_ORDER:
        mean_value = means.get(stage)
        p95_value = p95s.get(stage)
        rows.append(
            [
                _latex_escape(stage),
                _format_decimal(mean_value, 1),
                _format_decimal(p95_value, 1),
            ]
        )

    if not any(row[1] != "--" or row[2] != "--" for row in rows):
        print(f"SKIP {output.name}: missing stage latency metrics")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Set A V3 Ecommerce Audit Latency}",
        r"\label{tab:latency}",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Stage & Mean (ms) & P95 (ms) \\",
        r"\midrule",
    ]
    lines.extend(" & ".join(row) + r" \\" for row in rows)
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {output}")


def _load_metrics(path: Path, output_name: str) -> dict[str, Any] | None:
    if not _path_exists(path, output_name):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        print(f"SKIP {output_name}: expected object in {path}")
        return None
    return data


def _path_exists(path: Path, output_name: str) -> bool:
    if path.exists():
        return True
    print(f"SKIP {output_name}: missing {path}")
    return False


def _latest_set_a_dir() -> Path | None:
    base = Path("results/set_a_full")
    candidates = list(base.rglob("set_a_metrics.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path))).parent


def _latest_set_b_dir() -> Path | None:
    base = Path("results/set_b_full")
    candidates = list(base.rglob("set_b_metrics.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path))).parent


def _latest_structural_ablation_dir() -> Path | None:
    # Authoritative directory name kept as results/rq3_ablation (historical, archived).
    base = Path("results/rq3_ablation")
    candidates = list(base.rglob("set_a_metrics.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path))).parent


def _metric_value(
    metrics: dict[str, Any],
    version: str,
    domain: str,
    metric: str,
) -> float:
    value = _domain_metrics(metrics, version, domain).get(metric)
    if value is None:
        return 0.0
    return float(value)


def _domain_metrics(
    metrics: dict[str, Any],
    version: str,
    domain: str,
) -> dict[str, Any]:
    nested_version = metrics.get(version)
    if isinstance(nested_version, dict):
        nested_domain = nested_version.get(domain)
        if isinstance(nested_domain, dict):
            return nested_domain

    flat_domain = metrics.get(f"{version}_{domain}")
    if isinstance(flat_domain, dict):
        return flat_domain

    return {}


def _ordered_versions(metrics: dict[str, Any]) -> list[str]:
    configured = [*VERSION_ORDER, "V3_NoStructural"]
    discovered = []
    for version in configured:
        if version in metrics or any(f"{version}_{domain}" in metrics for domain in DOMAIN_ORDER):
            discovered.append(version)
    extra = sorted(
        key
        for key, value in metrics.items()
        if isinstance(value, dict)
        and key not in discovered
        and not any(key.endswith(f"_{domain}") for domain in DOMAIN_ORDER)
    )
    return discovered + extra


def _failure_mode_detection_rates(
    rows_path: Path,
    versions: list[str],
    domain: str,
    failure_modes: list[str],
) -> pd.DataFrame | None:
    df = pd.read_csv(rows_path)
    required_columns = {"scenario_id", "domain", "version", "actual_outcome"}
    missing = sorted(required_columns.difference(df.columns))
    if missing:
        print(f"SKIP {rows_path}: missing columns {', '.join(missing)}")
        return None

    df = df.copy()
    # Current per-failure-mode figures are ecommerce-only, where scenario IDs
    # start with F0-F5. Reference IDs use REF-F0-G-001 style prefixes; update
    # this to r"(?:REF-)?(F\d+)" before adding reference per-failure-type plots.
    df["failure_mode"] = (
        df["scenario_id"].astype(str).str.extract(r"^(F\d+)", expand=False)
    )
    df = df[
        (df["domain"] == domain)
        & (df["version"].isin(versions))
        & (df["failure_mode"].isin(failure_modes))
    ].copy()
    if df.empty:
        return None

    df["detected"] = df["actual_outcome"].isin(["WARN", "BLOCK"])
    grouped = (
        df.groupby(["version", "failure_mode"], as_index=False)
        .agg(total=("detected", "size"), detected=("detected", "sum"))
    )
    grouped["rate"] = grouped["detected"] / grouped["total"]
    return (
        grouped.pivot(index="failure_mode", columns="version", values="rate")
        .reindex(index=failure_modes, columns=versions)
        .fillna(0.0)
    )


def _domain_version_centers() -> dict[tuple[str, str], float]:
    centers: dict[tuple[str, str], float] = {}
    for domain_index, domain in enumerate(DOMAIN_ORDER):
        base = domain_index * 4
        for version_index, version in enumerate(VERSION_ORDER):
            centers[(domain, version)] = base + version_index
    return centers


def _apply_domain_axis(
    ax: plt.Axes,
    centers: dict[tuple[str, str], float],
) -> None:
    tick_positions = []
    tick_labels = []
    for domain in DOMAIN_ORDER:
        for version in VERSION_ORDER:
            tick_positions.append(centers[(domain, version)])
            tick_labels.append(VERSION_LABELS[version])
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_xlim(-0.7, 6.7)
    ax.text(
        1.0,
        -0.28,
        "ecommerce",
        ha="center",
        va="top",
        transform=ax.get_xaxis_transform(),
        fontsize=10,
    )
    ax.text(
        5.0,
        -0.28,
        "reference",
        ha="center",
        va="top",
        transform=ax.get_xaxis_transform(),
        fontsize=10,
    )


def _label_bars(ax: plt.Axes, bars: Any, y_offset: int = 3) -> None:
    for bar in bars:
        height = float(bar.get_height())
        offset = min(y_offset, 3) if height >= 0.95 else y_offset
        ax.annotate(
            f"{height:.2f}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            clip_on=False,
        )


def _despine(ax: plt.Axes) -> None:
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", width=0.8, length=3)


def _format_rate(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2f}"


def _format_decimal(value: Any, digits: int) -> str:
    if value is None:
        return "--"
    return f"{float(value):.{digits}f}"


def _latex_escape(value: str) -> str:
    return value.replace("_", r"\_")


if __name__ == "__main__":
    main()
