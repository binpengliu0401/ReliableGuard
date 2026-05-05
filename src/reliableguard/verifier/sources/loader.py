from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.reliableguard.verifier.sources.base import SourceConfig, VerifierSource


REPO_ROOT = Path(__file__).resolve().parents[4]


def load_source_configs(domain: str) -> list[SourceConfig]:
    config_path = REPO_ROOT / "src" / "domain" / domain / "config.yaml"
    if not config_path.exists():
        return []

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw_sources = loaded.get("verifier_sources", [])
    if not isinstance(raw_sources, list):
        return []

    configs: list[SourceConfig] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        adapter = item.get("adapter")
        name = item.get("name")
        if not adapter or not name:
            continue
        configs.append(
            SourceConfig(
                name=str(name),
                adapter=str(adapter),
                supports={str(value) for value in item.get("supports", []) or []},
                priority=int(item.get("priority", 100)),
                enabled=bool(item.get("enabled", True)),
                options=dict(item.get("options", {}) or {}),
            )
        )
    return sorted(configs, key=lambda config: config.priority)


@lru_cache(maxsize=16)
def load_sources(domain: str) -> tuple[VerifierSource, ...]:
    sources: list[VerifierSource] = []
    for config in load_source_configs(domain):
        if not config.enabled:
            continue
        source_cls = _import_object(config.adapter)
        source = source_cls(config)
        sources.append(source)
    return tuple(sources)


def _import_object(path: str) -> Any:
    module_name, _, attr = path.partition(":")
    if not module_name or not attr:
        raise ValueError(f"Adapter path must be 'module:ClassName', got {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)
