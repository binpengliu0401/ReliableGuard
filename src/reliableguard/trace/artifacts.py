from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
SUPPORTED_MODELS = {"qwen", "deepseek"}
SUPPORTED_DOMAINS = {"ecommerce", "reference"}


def make_run_stamp(started_at: datetime | None = None) -> str:
    dt = started_at or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(RUN_STAMP_FORMAT)


def build_run_id(domain: str, run_stamp: str) -> str:
    return f"{domain}_{run_stamp}"


def cleanup_incompatible_results(results_dir: str | Path = "results") -> list[str]:
    root = Path(results_dir)
    if not root.exists():
        return []

    removed: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_compatible_result_file(path, root):
            continue
        path.unlink()
        removed.append(str(path))

    for directory in sorted(
        [p for p in root.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    return removed


def save_run_result(
    *,
    model: str,
    domain: str,
    run_stamp: str,
    payload: dict[str, Any],
    results_dir: str | Path = "results",
) -> str:
    model_dir = Path(results_dir) / model / domain
    model_dir.mkdir(parents=True, exist_ok=True)

    path = model_dir / f"{build_run_id(domain, run_stamp)}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def _is_compatible_result_file(path: Path, root: Path) -> bool:
    if path.suffix != ".json":
        return False

    relative = path.relative_to(root)
    if len(relative.parts) != 3:
        return False

    model = relative.parts[0]
    domain = relative.parts[1]
    if model not in SUPPORTED_MODELS:
        return False
    if domain not in SUPPORTED_DOMAINS:
        return False

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    required = {"run_id", "run_started_at", "domain", "model", "version", "result"}
    if not required.issubset(payload):
        return False

    expected_prefix = f"{payload.get('domain')}_"
    return (
        payload.get("domain") == domain
        and
        payload.get("model") == model
        and isinstance(payload.get("run_id"), str)
        and payload["run_id"].startswith(expected_prefix)
        and path.stem == payload["run_id"]
    )
