from eval.fact_scorer import score_facts, snapshot_facts


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.params = []
        self._row = None

    def execute(self, sql, params=()):
        self.queries.append(sql)
        self.params.append(params)
        if "status='refunded'" in sql:
            self._row = (1,)
        elif "AVG(amount)" in sql:
            self._row = (42.5,)
        elif "status='confirmed'" in sql and "SUM(amount)" in sql:
            self._row = (80.0,)
        elif "status='pending'" in sql and "SUM(amount)" in sql:
            self._row = (20.0,)
        elif "WHERE id = 2" in sql:
            self._row = (2, 200.0, "confirmed")
        else:
            self._row = (None,)
        return self

    def fetchone(self):
        return self._row


class FakeReferenceConnection:
    def __init__(self):
        self.queries = []
        self._row = None
        self.closed = False

    def execute(self, sql):
        self.queries.append(sql)
        if "COUNT(*) > 0" in sql:
            self._row = (1,)
        elif "COUNT(*)" in sql:
            self._row = (3,)
        elif "SELECT authors" in sql:
            self._row = ('["Ada Lovelace", "Grace Hopper"]',)
        else:
            self._row = (None,)
        return self

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True


def test_snapshot_ecommerce_extended_aggregate_keys(monkeypatch):
    fake_cursor = FakeCursor()
    monkeypatch.setattr("src.domain.ecommerce.tools.cursor", fake_cursor)

    snapshot = snapshot_facts(
        "ecommerce",
        {"refund_success", "average_amount", "confirmed_total", "pending_total"},
    )

    assert snapshot == {
        "refund_success": 1,
        "average_amount": 42.5,
        "confirmed_total": 80.0,
        "pending_total": 20.0,
    }


def test_snapshot_ecommerce_order_n_key(monkeypatch):
    fake_cursor = FakeCursor()
    monkeypatch.setattr("src.domain.ecommerce.tools.cursor", fake_cursor)

    snapshot = snapshot_facts("ecommerce", {"order_2"})

    assert snapshot["order_2"] == "2,200.0,confirmed"
    assert "WHERE id = 2" in fake_cursor.queries[-1]


def test_snapshot_reference_extended_keys(monkeypatch):
    fake_conn = FakeReferenceConnection()
    monkeypatch.setattr("src.domain.reference.tools.init_reference_db", lambda: fake_conn)

    snapshot = snapshot_facts("reference", {"doi_exists", "author", "total_refs"})

    assert snapshot == {
        "doi_exists": 1,
        "author": "Ada Lovelace",
        "total_refs": 3,
    }
    assert fake_conn.closed is True


def test_snapshot_facts_unknown_keys_return_empty_dict():
    assert snapshot_facts("reference", {"not_supported"}) == {}


def test_score_facts_still_matches_new_values():
    assert score_facts({"order_2": "2,200.0,confirmed"}, {"order_2": "2,200.0,confirmed"}) == 1.0
