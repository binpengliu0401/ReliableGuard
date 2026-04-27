"""
Smoke and business-flow tests for ReliableGuard.

Run with:
    .venv/bin/python -m pytest scripts/smoke_test.py -q
    .venv/bin/python scripts/smoke_test.py

These tests avoid real LLM/API calls. They cover verifier rules, reliability
pipeline wiring, and full agent-tool-reliability business flows with deterministic
fakes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.config.ablation_versions import VERSIONS
from src.agent.langgraph_agent import run_agent
from src.reliableguard.schema import Claim
from src.reliableguard.verifier.ecommerce_verifier import verify_ecommerce_claim
from src.reliableguard.verifier.reference_verifier import verify_reference_claim


_SEED_REF = (
    1,
    "p1",
    "Attention is All You Need",
    '["Vaswani et al."]',
    "10.1234/test",
    "NeurIPS",
    2017,
    "verified",
    "verified",
    "verified",
    "verified",
)

_DOI_FOUND = {
    "exists": True,
    "metadata": {
        "title": "Attention is All You Need",
        "journal": "NeurIPS",
        "year": 2017,
        "authors": ["Vaswani et al."],
    },
}

_DOI_NOT_FOUND = {"exists": False}


class _FakeFunction:
    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = json.dumps(arguments)


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: dict):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[_FakeToolCall] | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls


class _FakeCompletions:
    def __init__(self, messages: list[_FakeMessage]):
        self._messages = messages

    def create(self, **_kwargs):
        if not self._messages:
            raise AssertionError("Fake LLM response queue is empty.")
        message = self._messages.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


class _FakeClient:
    def __init__(self, messages: list[_FakeMessage]):
        self.chat = SimpleNamespace(completions=_FakeCompletions(messages))


def _tool_message(call_id: str, name: str, arguments: dict) -> _FakeMessage:
    return _FakeMessage(tool_calls=[_FakeToolCall(call_id, name, arguments)])


def _final_message(content: str) -> _FakeMessage:
    return _FakeMessage(content=content, tool_calls=None)


def _order_claim(
    claim_id: str,
    attribute: str,
    value: object,
    order_id: int,
    claim_type: str = "attribute",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=f"Order {order_id} {attribute} is {value}",
        claim_type=claim_type,  # type: ignore[arg-type]
        entities={"order_id": order_id},
        attribute=attribute,
        value=value,
    )


def _make_ref_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE "references" (
            ref_id INTEGER PRIMARY KEY,
            paper_id TEXT,
            title TEXT,
            authors TEXT,
            doi TEXT,
            journal TEXT,
            year INTEGER,
            doi_status TEXT,
            doi_verdict_code TEXT,
            authors_status TEXT,
            journal_status TEXT
        )
        """
    )
    conn.execute('INSERT INTO "references" VALUES (?,?,?,?,?,?,?,?,?,?,?)', _SEED_REF)
    conn.commit()
    return conn


@pytest.fixture
def no_openrouter_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def fake_openai(monkeypatch):
    def install(messages: list[_FakeMessage]) -> _FakeClient:
        client = _FakeClient(messages)
        monkeypatch.setattr("src.graph.nodes.OpenAI", lambda **_kwargs: client)
        return client

    return install


@pytest.fixture
def ec_cursor():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            amount REAL,
            status TEXT,
            refund_reason TEXT
        )
        """
    )
    conn.execute("INSERT INTO orders VALUES (1, 99.90, 'confirmed', NULL)")
    conn.execute("INSERT INTO orders VALUES (2, 150.00, 'pending', NULL)")
    conn.commit()
    cursor = conn.cursor()
    with patch("src.reliableguard.verifier.ecommerce_verifier.cursor", cursor):
        yield cursor
    conn.close()


@pytest.fixture
def ref_db():
    with patch(
        "src.reliableguard.verifier.reference_verifier.init_reference_db",
        side_effect=_make_ref_conn,
    ):
        yield


@pytest.fixture
def isolated_ecommerce_db(monkeypatch):
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

    monkeypatch.setattr("src.domain.ecommerce.tools.cursor", cursor)
    monkeypatch.setattr("src.domain.ecommerce.tools.conn", conn)
    monkeypatch.setattr("src.reliableguard.verifier.ecommerce_verifier.cursor", cursor)

    yield cursor

    conn.close()


@pytest.fixture
def isolated_reference_db(monkeypatch, tmp_path):
    db_path = tmp_path / "references.db"
    monkeypatch.setattr("src.domain.reference.tools.REFERENCE_DB_PATH", str(db_path))
    return db_path


def test_ecommerce_status_supported(ec_cursor):
    result = verify_ecommerce_claim(
        _order_claim("c1", "status", "confirmed", order_id=1),
        "fully_verifiable",
    )
    assert result.evidence_state == "supported"
    assert result.source == "orders_db"
    assert result.confidence == 1.0


def test_ecommerce_status_contradicted(ec_cursor):
    result = verify_ecommerce_claim(
        _order_claim("c1", "status", "refunded", order_id=1),
        "fully_verifiable",
    )
    assert result.evidence_state == "contradicted"


def test_ecommerce_order_not_found(ec_cursor):
    result = verify_ecommerce_claim(
        _order_claim("c1", "status", "confirmed", order_id=999),
        "fully_verifiable",
    )
    assert result.evidence_state == "not_found"


def test_ecommerce_amount_supported(ec_cursor):
    result = verify_ecommerce_claim(
        _order_claim("c1", "amount", 99.90, order_id=1, claim_type="numeric"),
        "fully_verifiable",
    )
    assert result.evidence_state == "supported"


def test_ecommerce_amount_contradicted(ec_cursor):
    result = verify_ecommerce_claim(
        _order_claim("c1", "amount", 50.00, order_id=1, claim_type="numeric"),
        "fully_verifiable",
    )
    assert result.evidence_state == "contradicted"


def test_ecommerce_order_count_supported(ec_cursor):
    claim = Claim(
        claim_id="c1",
        text="There are 2 orders in total",
        claim_type="numeric",
        entities={},
        attribute="order_count",
        value=2,
    )
    result = verify_ecommerce_claim(claim, "fully_verifiable")
    assert result.evidence_state == "supported"


def test_ecommerce_order_count_contradicted(ec_cursor):
    claim = Claim(
        claim_id="c1",
        text="There are 10 orders in total",
        claim_type="numeric",
        entities={},
        attribute="order_count",
        value=10,
    )
    result = verify_ecommerce_claim(claim, "fully_verifiable")
    assert result.evidence_state == "contradicted"


def test_ecommerce_customer_filter_unsupported_schema(ec_cursor):
    claim = Claim(
        claim_id="c1",
        text="Customer alice has 1 order",
        claim_type="numeric",
        entities={"customer": "alice"},
        attribute="order_count",
        value=1,
    )
    result = verify_ecommerce_claim(claim, "fully_verifiable")
    assert result.evidence_state == "unverifiable"


def test_ecommerce_pipeline_heuristic_path(ec_cursor):
    from src.reliableguard.pipeline import run_reliability_pipeline

    report = run_reliability_pipeline(
        domain="ecommerce",
        query="What is the status of order 1?",
        agent_answer="Order 1 status is confirmed",
        model="dummy-model",
        base_url="http://localhost",
        write_logs=False,
    )

    assert 0.0 <= report.reliability_score <= 1.0
    assert report.verdict in {"PASS", "WARN", "BLOCK", "ESCALATE"}
    assert len(report.traces) > 0
    for trace in report.traces:
        assert trace.claim.claim_id == trace.verification.claim_id
        assert trace.verification.claim_id == trace.risk.claim_id
        assert trace.risk.claim_id == trace.intervention.claim_id


def test_reference_doi_existence_supported():
    with patch(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        return_value=_DOI_FOUND,
    ):
        claim = Claim(
            claim_id="c1",
            text="DOI 10.1234/test exists",
            claim_type="existence",
            entities={"doi": "10.1234/test"},
            attribute="doi",
            value="10.1234/test",
        )
        result = verify_reference_claim(claim, "fully_verifiable")
        assert result.evidence_state == "supported"
        assert result.source == "crossref"


def test_reference_doi_existence_not_found():
    with patch(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        return_value=_DOI_NOT_FOUND,
    ):
        claim = Claim(
            claim_id="c1",
            text="DOI 10.9999/fake exists",
            claim_type="existence",
            entities={"doi": "10.9999/fake"},
            attribute="doi",
            value="10.9999/fake",
        )
        result = verify_reference_claim(claim, "fully_verifiable")
        assert result.evidence_state == "not_found"
        assert result.source == "crossref"


def test_reference_doi_with_title_supported():
    with patch(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        return_value=_DOI_FOUND,
    ):
        claim = Claim(
            claim_id="c1",
            text="DOI 10.1234/test is Attention is All You Need",
            claim_type="existence",
            entities={
                "doi": "10.1234/test",
                "paper_title": "Attention is All You Need",
            },
            attribute="doi",
            value="10.1234/test",
        )
        result = verify_reference_claim(claim, "fully_verifiable")
        assert result.evidence_state == "supported"
        assert result.confidence >= 0.8


def test_reference_doi_with_wrong_title_contradicted():
    with patch(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        return_value=_DOI_FOUND,
    ):
        claim = Claim(
            claim_id="c1",
            text="DOI 10.1234/test is Completely Different Paper",
            claim_type="existence",
            entities={
                "doi": "10.1234/test",
                "paper_title": "Completely Different Paper Xyz",
            },
            attribute="doi",
            value="10.1234/test",
        )
        result = verify_reference_claim(claim, "fully_verifiable")
        assert result.evidence_state == "contradicted"


def test_reference_db_attribute_supported(ref_db):
    claim = Claim(
        claim_id="c1",
        text="Reference 1 doi_status is verified",
        claim_type="attribute",
        entities={"ref_id": 1},
        attribute="doi_status",
        value="verified",
    )
    result = verify_reference_claim(claim, "fully_verifiable")
    assert result.evidence_state == "supported"
    assert result.source == "references_db"


def test_reference_db_attribute_contradicted(ref_db):
    claim = Claim(
        claim_id="c1",
        text="Reference 1 doi_status is pending",
        claim_type="attribute",
        entities={"ref_id": 1},
        attribute="doi_status",
        value="pending",
    )
    result = verify_reference_claim(claim, "fully_verifiable")
    assert result.evidence_state == "contradicted"


def test_reference_not_found(ref_db):
    claim = Claim(
        claim_id="c1",
        text="Reference 999 exists",
        claim_type="existence",
        entities={"ref_id": 999},
    )
    result = verify_reference_claim(claim, "fully_verifiable")
    assert result.evidence_state == "not_found"


def test_reference_entity_existence_supported(ref_db):
    claim = Claim(
        claim_id="c1",
        text="Reference 1 exists",
        claim_type="existence",
        entities={"ref_id": 1},
    )
    result = verify_reference_claim(claim, "fully_verifiable")
    assert result.evidence_state == "supported"
    assert result.evidence_value is not None


def test_reference_pipeline_heuristic_path(ref_db):
    with patch(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        return_value=_DOI_FOUND,
    ):
        from src.reliableguard.pipeline import run_reliability_pipeline

        report = run_reliability_pipeline(
            domain="reference",
            query="Does DOI 10.1234/test exist?",
            agent_answer="The reference with DOI 10.1234/TEST has been verified.",
            model="dummy-model",
            base_url="http://localhost",
            write_logs=False,
        )

    assert 0.0 <= report.reliability_score <= 1.0
    assert report.verdict in {"PASS", "WARN", "BLOCK", "ESCALATE"}
    assert len(report.traces) > 0
    for trace in report.traces:
        assert trace.claim.claim_id == trace.verification.claim_id
        assert trace.verification.claim_id == trace.risk.claim_id
        assert trace.risk.claim_id == trace.intervention.claim_id


def test_ecommerce_order_create_confirm_full_business_flow(
    no_openrouter_key,
    fake_openai,
    isolated_ecommerce_db,
):
    fake_openai(
        [
            _tool_message("call_create", "create_order", {"amount": 100}),
            _tool_message("call_confirm", "confirm_order", {"order_id": 1}),
            _final_message("Order 1 status is confirmed and amount is 100."),
        ]
    )

    result = run_agent(
        "Create an order for amount 100, confirm it, and report the final status.",
        domain="ecommerce",
        config=VERSIONS["V3_Intervention"],
    )

    row = isolated_ecommerce_db.execute(
        "SELECT id, amount, status FROM orders WHERE id = 1"
    ).fetchone()

    assert row == (1, 100.0, "confirmed")
    assert result["executed_tools"] == ["create_order", "confirm_order"]
    assert result["final_answer"] == "Order 1 status is confirmed and amount is 100."
    assert result["reliability_verdict"] == "PASS"
    assert result["reliability_score"] == 1.0
    assert result["reliability_report"]["supported_count"] >= 2
    assert result["reliability_report"]["contradicted_count"] == 0
    assert result["reliability_report"]["not_found_count"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_reference_parse_verify_doi_full_business_flow(
    no_openrouter_key,
    fake_openai,
    isolated_reference_db,
    monkeypatch,
):
    extracted_refs = [
        {
            "title": "Attention is All You Need",
            "authors": ["Vaswani et al."],
            "doi": "10.1234/test",
            "journal": "NeurIPS",
            "year": 2017,
        }
    ]
    doi_response = {
        "exists": True,
        "matches": True,
        "metadata": {
            "title": "Attention is All You Need",
            "journal": "NeurIPS",
            "year": 2017,
            "authors": ["Vaswani et al."],
        },
    }

    monkeypatch.setattr(
        "src.domain.reference.api_client.get_references_from_pdf",
        lambda _pdf_path: extracted_refs,
    )
    monkeypatch.setattr("src.domain.reference.api_client.query_doi", lambda _doi: doi_response)
    monkeypatch.setattr(
        "src.reliableguard.verifier.reference_verifier.query_doi",
        lambda _doi: doi_response,
    )

    fake_openai(
        [
            _tool_message(
                "call_parse",
                "parse_pdf",
                {"pdf_path": "business-fixture.pdf", "paper_id": "paper_business_001"},
            ),
            _tool_message("call_verify", "verify_doi", {"ref_id": 1, "doi": "10.1234/test"}),
            _final_message("Reference 1 doi_status is verified. DOI 10.1234/test exists."),
        ]
    )

    result = run_agent(
        'Parse "business-fixture.pdf" as paper_business_001 and verify its DOI.',
        domain="reference",
        config=VERSIONS["V3_Intervention"],
    )

    conn = sqlite3.connect(isolated_reference_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            'SELECT ref_id, paper_id, title, doi, journal, year, doi_status '
            'FROM "references" WHERE ref_id = 1'
        ).fetchone()
    finally:
        conn.close()

    assert dict(row) == {
        "ref_id": 1,
        "paper_id": "paper_business_001",
        "title": "Attention is All You Need",
        "doi": "10.1234/test",
        "journal": "NeurIPS",
        "year": 2017,
        "doi_status": "verified",
    }
    assert result["executed_tools"] == ["parse_pdf", "verify_doi"]
    assert result["final_answer"] == "Reference 1 doi_status is verified. DOI 10.1234/test exists."
    assert result["reliability_verdict"] == "PASS"
    assert result["reliability_score"] == 1.0
    assert result["reliability_report"]["supported_count"] >= 2
    assert result["reliability_report"]["contradicted_count"] == 0
    assert result["reliability_report"]["not_found_count"] == 0
