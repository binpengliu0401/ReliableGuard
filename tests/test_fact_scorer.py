from eval.fact_scorer import parse_expected_facts, score_facts, snapshot_facts


def test_parse_expected_facts_returns_key_value_mapping():
    assert parse_expected_facts(["order_id=1", "amount=100.0", "status=pending"]) == {
        "order_id": "1",
        "amount": "100.0",
        "status": "pending",
    }


def test_score_facts_returns_full_match():
    assert score_facts({"status": "pending"}, {"status": "pending"}) == 1.0


def test_score_facts_returns_zero_for_mismatch():
    assert score_facts({"status": "pending"}, {"status": "confirmed"}) == 0.0


def test_score_facts_numeric_fallback_matches_int_and_float_strings():
    assert score_facts({"amount": "50"}, {"amount": 50.0}) == 1.0


def test_score_facts_returns_none_when_no_overlap():
    assert score_facts({"order_id": "1"}, {}) is None


def test_parse_expected_facts_empty_list_returns_empty_dict():
    assert parse_expected_facts([]) == {}


def test_snapshot_facts_omits_unknown_keys():
    assert snapshot_facts("ecommerce", {"unsupported_name"}) == {}
