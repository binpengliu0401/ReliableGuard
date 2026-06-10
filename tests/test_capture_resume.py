"""Phase 2: capture batch driver resume logic (offline, no API).

Pins the shard/resume contract: which (model, domain, repeat, task_id) keys count as done, that
resume skips them, and that only credit/auth errors trigger a halt.
"""

import json

from eval.capture import (
    _is_halt_error,
    _load_done_keys,
    _pending_jobs,
    _shard_path,
    _slice_state,
    _traj_key,
)


def test_slice_state_keeps_only_relevant_entities() -> None:
    before = {
        "orders": {"#W1": {"status": "pending"}, "#W2": {"status": "pending"}, "#W3": {"status": "delivered"}},
        "users": {"u1": {"orders": ["#W3"]}, "u2": {"orders": []}},
        "products": {"p1": {}, "p2": {}},
    }
    after = {
        "orders": {"#W1": {"status": "cancelled"}, "#W2": {"status": "pending"}, "#W3": {"status": "delivered"}},
        "users": {"u1": {"orders": ["#W3"]}, "u2": {"orders": []}},
        "products": {"p1": {}, "p2": {}},
    }
    trace = [
        {"name": "get_user_details", "kwargs": {"user_id": "u1"}},
        {"name": "cancel_pending_order", "kwargs": {"order_id": "#W1"}},
    ]
    sliced_before, sliced_after = _slice_state(before, after, trace)
    # #W1 referenced+changed; #W3 belongs to kept user u1; #W2 neither -> dropped
    assert set(sliced_after["orders"]) == {"#W1", "#W3"}
    assert set(sliced_after["users"]) == {"u1"}  # u2 untouched -> dropped
    assert sliced_after["products"] == {}  # no product referenced
    assert sliced_before["orders"]["#W1"]["status"] == "pending"  # before preserved for kept entity


def test_traj_key_includes_all_dims() -> None:
    k = _traj_key("z-ai/glm-4.7-flash", "retail", 2, 7)
    assert k == "z-ai/glm-4.7-flash|retail|r2|t7"


def test_shard_path_slugs_model() -> None:
    assert _shard_path("results/capture", "z-ai/glm-4.7-flash").name == "z-ai_glm-4.7-flash.jsonl"


def test_load_done_keys_counts_ok_only(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "shard.jsonl"
    rows = [
        {"model": "m", "domain": "retail", "repeat": 0, "task_id": "1", "status": "ok"},
        {"model": "m", "domain": "retail", "repeat": 0, "task_id": "2", "status": "error"},
        {"model": "m", "domain": "airline", "repeat": 1, "task_id": "5", "status": "ok"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    done = _load_done_keys(path)
    assert done == {_traj_key("m", "retail", 0, "1"), _traj_key("m", "airline", 1, "5")}
    assert _traj_key("m", "retail", 0, "2") not in done  # error record is NOT done -> resume reruns


def test_load_done_keys_missing_file_is_empty(tmp_path) -> None:  # noqa: ANN001
    assert _load_done_keys(tmp_path / "nope.jsonl") == set()


def test_pending_jobs_expands_matrix_and_skips_done() -> None:
    tasks = {"retail": [1, 2], "airline": [5]}
    done = {_traj_key("m", "retail", 0, 1)}  # already captured
    jobs = _pending_jobs("m", tasks, repeats=2, done=done)
    # 2 domains-tasks(3) x 2 repeats = 6 total, minus the 1 done = 5
    assert len(jobs) == 5
    assert ("retail", 0, 1) not in jobs
    assert ("retail", 1, 1) in jobs and ("airline", 1, 5) in jobs


def test_is_halt_error_only_on_credit_auth() -> None:
    assert _is_halt_error(Exception("OpenRouterException 402: insufficient credits"))
    assert _is_halt_error(Exception("401 Unauthorized"))
    assert not _is_halt_error(Exception("429 rate limit exceeded"))
    assert not _is_halt_error(Exception("timeout while reading"))
