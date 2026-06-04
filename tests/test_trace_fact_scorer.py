from eval.fact_scorer import score_trace_facts


class FakeReferenceConnection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
        self._row = None
        self.closed = False

    def execute(self, sql):
        self.queries.append(sql)
        for marker, row in self.rows:
            if marker in sql:
                self._row = row
                break
        else:
            self._row = (None,)
        return self

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True


def test_score_trace_called_tool_matches():
    scores = score_trace_facts(
        {"verify_authors_called": "true"},
        {"executed_tools": ["verify_authors"]},
        "reference",
    )

    assert scores == {"verify_authors_called": True}


def test_score_trace_called_tool_mismatch():
    scores = score_trace_facts(
        {"verify_authors_called": "true"},
        {"executed_tools": []},
        "reference",
    )

    assert scores == {"verify_authors_called": False}


def test_score_trace_parse_status_uses_reference_db(monkeypatch):
    fake_conn = FakeReferenceConnection([("status FROM papers", ("parsed",))])
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts({"parse_status": "parsed"}, {"executed_tools": []}, "reference")

    assert scores == {"parse_status": True}
    assert fake_conn.closed is True


def test_score_trace_parse_status_failed(monkeypatch):
    fake_conn = FakeReferenceConnection([("status FROM papers", ("failed",))])
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts({"parse_status": "failed"}, {"executed_tools": []}, "reference")

    assert scores == {"parse_status": True}


def test_score_trace_verified_doi_count(monkeypatch):
    fake_conn = FakeReferenceConnection([("doi_status='verified'", (3,))])
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts(
        {"verified_doi_count": "3"},
        {"executed_tools": []},
        "reference",
    )

    assert scores == {"verified_doi_count": True}


def test_score_trace_failed_doi_count(monkeypatch):
    fake_conn = FakeReferenceConnection([("doi_status='failed'", (2,))])
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts(
        {"failed_count": "2"},
        {"executed_tools": []},
        "reference",
    )

    assert scores == {"failed_count": True}


def test_score_trace_parse_counts(monkeypatch):
    fake_conn = FakeReferenceConnection(
        [
            ("status='parsed'", (2,)),
            ("status='failed'", (1,)),
        ]
    )
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts(
        {"successful_parses": "2", "failed_parses": "1"},
        {"executed_tools": []},
        "reference",
    )

    assert scores == {"successful_parses": True, "failed_parses": True}


def test_score_trace_matches_uses_verdict_code(monkeypatch):
    fake_conn = FakeReferenceConnection([("COALESCE(doi_verdict_code", ("verified",))])
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    scores = score_trace_facts({"matches": "true"}, {"executed_tools": []}, "reference")

    assert scores == {"matches": True}


def test_score_trace_unknown_keys_are_ignored():
    assert score_trace_facts({"unknown_key": "value"}, {"executed_tools": []}, "reference") == {}
