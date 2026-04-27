"""
Generate a readable trace log and structured result artifact.

Run with:
    .venv/bin/python scripts/artifact_smoke_test.py

This is deterministic: it uses a fake LLM client and an isolated in-memory
ecommerce DB, but it still runs through run_agent(), tool execution, the
reliability node, and trace logging.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.config.ablation_versions import VERSIONS
from src.agent.langgraph_agent import run_agent
from src.reliableguard.trace.artifacts import (
    build_run_id,
    make_run_stamp,
)


class _FakeFunction:
    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = json.dumps(arguments)


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: dict):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content: str | None = None, tool_calls: list[_FakeToolCall] | None = None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeCompletions:
    def __init__(self, messages: list[_FakeMessage]):
        self._messages = messages

    def create(self, **_kwargs):
        if not self._messages:
            raise RuntimeError("Fake LLM response queue is empty.")
        message = self._messages.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


class _FakeClient:
    def __init__(self, messages: list[_FakeMessage]):
        self.chat = SimpleNamespace(completions=_FakeCompletions(messages))


def _tool_message(call_id: str, name: str, arguments: dict) -> _FakeMessage:
    return _FakeMessage(tool_calls=[_FakeToolCall(call_id, name, arguments)])


def _final_message(content: str) -> _FakeMessage:
    return _FakeMessage(content=content, tool_calls=None)


def _build_ecommerce_db() -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            refund_reason TEXT DEFAULT NULL
        )
        """
    )
    conn.commit()
    return conn, cursor


def main() -> int:
    os.environ.pop("OPENROUTER_API_KEY", None)

    domain = "ecommerce"
    model = "qwen"
    run_stamp = make_run_stamp()
    run_id = build_run_id(domain, run_stamp)

    fake_client = _FakeClient(
        [
            _tool_message("call_create", "create_order", {"amount": 100}),
            _tool_message("call_confirm", "confirm_order", {"order_id": 1}),
            _final_message("Order 1 status is confirmed and amount is 100."),
        ]
    )
    conn, cursor = _build_ecommerce_db()

    try:
        with (
            patch("src.graph.nodes.OpenAI", lambda **_kwargs: fake_client),
            patch("src.domain.ecommerce.tools.cursor", cursor),
            patch("src.domain.ecommerce.tools.conn", conn),
            patch("src.reliableguard.verifier.ecommerce_verifier.cursor", cursor),
        ):
            result = run_agent(
                "Create an order for amount 100, confirm it, and report the final status.",
                domain=domain,
                config=VERSIONS["V3_Intervention"],
                run_stamp=run_stamp,
            )
    finally:
        conn.close()

    log_path = Path("logs") / domain / f"{run_id}.json"
    print(json.dumps(
        {
            "run_id": run_id,
            "trace_log": str(log_path),
            "results_note": "Single-run artifacts are trace logs only. Run eval.benchmark to generate CSV results.",
            "verdict": result.get("reliability_verdict"),
            "score": result.get("reliability_score"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
