"""tau2-bench capture driver: run one agent on one task and emit a Trajectory.

Formal experiment domains: retail + airline (165 tasks/repeat).
Output schema is identical to capture.py (Trajectory JSONL).

State snapshot timing:
  - state_before: deepcopy of env.tools.db AFTER orchestrator is built
    (task-specific initialization_data already applied) but BEFORE run_simulation.
  - state_after: deepcopy of env.tools.db AFTER run_simulation completes.
  The tau2 runner applies agent actions directly to env.tools.db, so the
  post-sim snapshot is the agent-final state (not gold-polluted).

Batch / resume / halt logic mirrors capture.py exactly.
"""

from __future__ import annotations

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

load_dotenv()

from src.reliableguard.adapter import Trajectory


def _get_env_state(environment: Any) -> dict[str, Any]:
    """Extract current DB state from a tau2 Environment.

    env.tools is the live ToolKitBase; env.tools.db is the active DB model.
    Returns an empty dict if the structure differs (e.g., future domain changes).
    """
    try:
        return copy.deepcopy(environment.tools.db.model_dump())
    except AttributeError:
        return {}


def _slice_state_retail_airline(
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    tool_trace: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-uses the same entity-level slicing logic as capture.py.

    Keeps only entities referenced in the trace, changed between snapshots,
    or reachable from a kept user (orders for retail, reservations for airline).
    """
    blob = json.dumps(tool_trace)
    before, after = state_before or {}, state_after or {}

    def _keep_keys(category: str) -> set[str]:
        b, a = before.get(category, {}), after.get(category, {})
        return {k for k in set(b) | set(a) if k in blob or b.get(k) != a.get(k)}

    user_keys = _keep_keys("users")
    order_keys = _keep_keys("orders")
    for users in (before.get("users", {}), after.get("users", {})):
        for key in user_keys:
            user = users.get(key)
            if user:
                order_keys.update(user.get("orders", []))
    reservation_keys = _keep_keys("reservations")
    for users in (before.get("users", {}), after.get("users", {})):
        for key in user_keys:
            user = users.get(key)
            if user:
                reservation_keys.update(user.get("reservations", []))
    product_keys = {k for k in set(before.get("products", {})) | set(after.get("products", {})) if k in blob}
    flight_keys = {k for k in set(before.get("flights", {})) | set(after.get("flights", {})) if k in blob}

    keep = {
        "orders": order_keys,
        "users": user_keys,
        "products": product_keys,
        "reservations": reservation_keys,
        "flights": flight_keys,
    }

    def _slice(state: dict[str, Any]) -> dict[str, Any]:
        return {
            category: {k: state[category][k] for k in keys if k in state.get(category, {})}
            for category, keys in keep.items()
            if category in state
        }

    return _slice(before), _slice(after)


def capture_tau2_trajectory(
    *,
    agent_model: str,
    user_model: str,
    domain: str,
    task_id: str,
    repeat: int = 0,
    max_steps: int = 30,
) -> Trajectory:
    """Run one (agent, domain, task, repeat) with tau2 and return a Trajectory.

    Formal domains: retail + airline. The monitor reads only the returned observable
    artifacts; the gold annotation (task.evaluation_criteria) is never read into the
    Trajectory.
    """
    import sys
    tau2_src = "/Users/beike/Desktop/PolyU/semester_2/5902/code/tau2-bench/src"
    if tau2_src not in sys.path:
        sys.path.insert(0, tau2_src)

    from tau2.runner import build_text_orchestrator, get_tasks, run_simulation
    from tau2.data_model.simulation import TextRunConfig

    # tau2 hard-codes "gpt-4.1-2025-04-14" (OpenAI) for NL-assertion evaluation; tasks
    # with NL_ASSERTION in their reward_basis would fail with AuthenticationError because
    # OPENAI_API_KEY is not set. Patch to use the user-simulator model via OpenRouter instead.
    import tau2.evaluator.evaluator_nl_assertions as _nl_eval_mod
    def _or_static(m: str) -> str:
        return m if m.startswith("openrouter/") else f"openrouter/{m}"
    # Use deepseek-v4-pro for NL assertions: reliable JSON output, available via OpenRouter.
    _nl_eval_mod.DEFAULT_LLM_NL_ASSERTIONS = "openrouter/deepseek/deepseek-v4-pro"

    tasks = get_tasks(domain, task_ids=[task_id])
    if not tasks:
        raise ValueError(f"No task found for domain={domain} task_id={task_id}")
    task = tasks[0]

    # tau2 uses litellm; OpenRouter models need the "openrouter/" prefix so litellm
    # routes through OpenRouter using OPENROUTER_API_KEY instead of direct providers.
    def _or(model: str) -> str:
        return model if model.startswith("openrouter/") else f"openrouter/{model}"

    config = TextRunConfig(
        domain=domain,
        llm_agent=_or(agent_model),
        llm_user=_or(user_model),
        agent="llm_agent",
        user="user_simulator",
        max_steps=max_steps,
    )

    orch = build_text_orchestrator(config, task, seed=None)

    # Snapshot state_before: task initialization already applied; no agent actions yet.
    state_before = _get_env_state(orch.environment)

    # Run the full simulation.
    sim = run_simulation(orch)

    # Snapshot state_after: agent-final state.
    state_after = _get_env_state(orch.environment)

    # Extract tool_trace: only agent-initiated tool calls (not user tool calls).
    tool_trace: list[dict[str, Any]] = []
    for msg in (sim.messages or []):
        if getattr(msg, "role", None) != "assistant":
            continue
        for tc in (msg.tool_calls or []):
            if getattr(tc, "requestor", "assistant") == "assistant":
                tool_trace.append({"name": tc.name, "kwargs": tc.arguments})

    # Extract answer_text: assistant natural-language turns (no tool calls).
    respond_turns: list[str] = [
        msg.content
        for msg in (sim.messages or [])
        if getattr(msg, "role", None) == "assistant"
        and msg.content
        and not msg.tool_calls
    ]
    answer_text = "\n\n".join(respond_turns)
    final_answer = respond_turns[-1] if respond_turns else ""

    # Initial query: first user message content.
    query = next(
        (msg.content for msg in (sim.messages or [])
         if getattr(msg, "role", None) == "user" and msg.content),
        "",
    )

    gold_reward = sim.reward_info.reward if sim.reward_info else None

    sliced_before, sliced_after = _slice_state_retail_airline(state_before, state_after, tool_trace)

    return Trajectory(
        task_id=str(task_id),
        domain=domain,
        model=agent_model,
        repeat=repeat,
        seed=None,
        query=query,
        final_answer=final_answer,
        answer_text=answer_text,
        tool_trace=tool_trace,
        state_before=sliced_before,
        state_after=sliced_after,
        gold_reward=gold_reward,
        status="ok",
    )


# --- Batch capture: shard + resume + credit-aware halt --------------------------------

_HALT_MARKERS = ("402", "insufficient", "credit", "payment required", "401", "unauthorized")


def _is_halt_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _HALT_MARKERS)


def _traj_key(model: str, domain: str, repeat: int, task_id: Any) -> str:
    return f"{model}|{domain}|r{repeat}|t{task_id}"


def _shard_path(out_dir: str | Path, model: str) -> Path:
    return Path(out_dir) / (model.replace("/", "_") + ".jsonl")


def _load_done_keys(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("status") == "ok":
                done.add(_traj_key(
                    record.get("model"), record.get("domain"),
                    record.get("repeat", 0), record.get("task_id"),
                ))
    return done


def _pending_jobs(
    model: str, tasks: dict[str, Iterable[str]], repeats: int, done: set[str]
) -> list[tuple[str, int, str]]:
    return [
        (domain, repeat, task_id)
        for domain, ids in tasks.items()
        for repeat in range(repeats)
        for task_id in ids
        if _traj_key(model, domain, repeat, task_id) not in done
    ]


def run_capture_matrix(
    *,
    agent_models: list[str],
    user_model: str,
    tasks: dict[str, Iterable[str]],
    repeats: int = 1,
    out_dir: str | Path = "results/capture",
    max_workers: int = 1,
) -> None:
    """Capture the (model × domain × repeat × task) matrix into per-model JSONL shards.

    Resumable: re-running skips trajectories already captured with status='ok'.
    On a credit/auth error the model's run halts so you can recharge and resume.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for model in agent_models:
        path = _shard_path(out_dir, model)
        done = _load_done_keys(path)
        jobs = _pending_jobs(model, tasks, repeats, done)
        print(f"[{model}] {len(done)} done, {len(jobs)} pending -> {path}", flush=True)
        lock = threading.Lock()
        halted = threading.Event()

        def _do(job: tuple[str, int, str]) -> None:
            if halted.is_set():
                return
            domain, repeat, task_id = job
            try:
                traj = capture_tau2_trajectory(
                    agent_model=model,
                    user_model=user_model,
                    domain=domain,
                    task_id=task_id,
                    repeat=repeat,
                )
            except Exception as exc:  # noqa: BLE001
                if _is_halt_error(exc):
                    halted.set()
                    print(
                        f"  HALT [{model} {domain} {task_id}]: credit/auth ({exc}); "
                        "recharge + rerun", flush=True,
                    )
                else:
                    print(
                        f"  ERR  [{model} {domain} {task_id}]: "
                        f"{type(exc).__name__}: {str(exc)[:120]}; resume will retry",
                        flush=True,
                    )
                return
            with lock:
                with path.open("a") as handle:
                    handle.write(json.dumps(traj.model_dump()) + "\n")
                    handle.flush()
            print(
                f"  ok   [{model} {domain} {task_id} r{repeat}] "
                f"reward={traj.gold_reward}",
                flush=True,
            )

        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(_do, jobs))
        else:
            for job in jobs:
                if halted.is_set():
                    break
                _do(job)

        if halted.is_set():
            print(
                f"[{model}] HALTED (credit/auth). Recharge, then re-run to resume.",
                flush=True,
            )
            return
