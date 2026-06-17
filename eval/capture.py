"""tau-bench capture driver (Phase 2): run one agent on one task and emit a Trajectory.

Honors the run-harness spec (docs/architecture.md -> "Run-harness correctness & robustness"):
  - snapshot `state_after` / `tool_trace` BEFORE the reward-bearing terminal `env.step()` (which
    reloads `env.data` to ground truth and appends the gold actions to `env.actions`);
  - per-call max_tokens caps (agent 4096, user-sim 2048) + truncation alarm on finish_reason=length;
  - transient retry via litellm globals (429/timeout/5xx; NOT 400 bad-request);
  - answer-local input = the concatenation of the agent's `respond` turns (not tool calls).

Sharding + resume live in the batch driver (next increment). Requires PYTHONPATH including the
tau-bench checkout. `capture_trajectory` raises on an infra failure (retries exhausted / truncation);
the batch driver turns that into a `status="error"` Trajectory that resume re-runs.
"""

from __future__ import annotations

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

import litellm
from dotenv import load_dotenv
from litellm import completion

load_dotenv()  # make OPENROUTER_API_KEY available from .env before any litellm/openai calls

from src.reliableguard.adapter import Trajectory
from src.reliableguard.errors import LLMResponseTruncatedError

litellm.suppress_debug_info = True
litellm.num_retries = 4  # retry transient errors with backoff; 400 bad-request is not retried

AGENT_MAX_TOKENS = 4096
USER_SIM_MAX_TOKENS = 2048
MAX_NUM_STEPS = 30
RESPOND = "respond"


def _patch_user_sim_max_tokens() -> None:
    """tau-bench's user simulator calls `completion` with no max_tokens; inject a runaway-guard
    cap and fix openrouter routing: when custom_llm_provider="openrouter", litellm prefixes the
    model string internally but OpenRouter rejects the resulting path for minimax models. Fix by
    prefixing the model with "openrouter/" and dropping custom_llm_provider so litellm routes
    via the native openrouter/* path instead.
    Idempotent (patches the module-level symbol once)."""
    import tau_bench.envs.user as user_mod

    if getattr(user_mod, "_rg_capped", False):
        return
    original = user_mod.completion

    def capped(*args: Any, **kwargs: Any):  # noqa: ANN202
        kwargs.setdefault("max_tokens", USER_SIM_MAX_TOKENS)
        if kwargs.get("custom_llm_provider") == "openrouter":
            model = kwargs.get("model", "")
            if not model.startswith("openrouter/"):
                kwargs["model"] = f"openrouter/{model}"
            kwargs.pop("custom_llm_provider")
        return original(*args, **kwargs)

    user_mod.completion = capped
    user_mod._rg_capped = True


def _slice_state(
    state_before: dict[str, Any], state_after: dict[str, Any], tool_trace: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only the entities the monitor can need, not the whole DB (~2.5 MB/trajectory for retail
    ≈ 16 GB over the full matrix). An entity is kept if its id appears in the tool trace (read or
    written), if it changed between before/after, or if it is reachable from a kept user (orders for
    retail, reservations for airline). Handles both retail (orders/users/products) and airline
    (reservations/users/flights) state schemas by scanning whichever keys are present. Returns
    sliced (before, after)."""
    blob = json.dumps(tool_trace)
    before, after = state_before or {}, state_after or {}

    def _keep_keys(category: str) -> set[str]:
        b, a = before.get(category, {}), after.get(category, {})
        return {k for k in set(b) | set(a) if k in blob or b.get(k) != a.get(k)}

    user_keys = _keep_keys("users")

    # Retail: orders owned by kept users are pulled in even if not directly in trace.
    order_keys = _keep_keys("orders")
    for users in (before.get("users", {}), after.get("users", {})):
        for key in user_keys:
            user = users.get(key)
            if user:
                order_keys.update(user.get("orders", []))

    # Airline: reservations owned by kept users are pulled in (same join pattern as retail orders).
    reservation_keys = _keep_keys("reservations")
    for users in (before.get("users", {}), after.get("users", {})):
        for key in user_keys:
            user = users.get(key)
            if user:
                reservation_keys.update(user.get("reservations", []))

    # Products (retail) and flights (airline): keep only those referenced in the trace blob.
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
        # Only include a category key if the source state actually has it (keeps airline states
        # clean of empty "orders"/{} and retail states clean of empty "reservations"/{}).
        return {
            category: {k: state[category][k] for k in keys if k in state.get(category, {})}
            for category, keys in keep.items()
            if category in state
        }

    return _slice(before), _slice(after)


def capture_trajectory(
    *,
    agent_model: str,
    user_model: str,
    domain: str,
    task_index: int,
    repeat: int = 0,
    seed: int | None = None,
    agent_max_tokens: int = AGENT_MAX_TOKENS,
) -> Trajectory:
    """Run one (agent, domain, task, repeat) and return a captured Trajectory. The monitor reads
    only the returned observable artifacts; the gold annotation (`task.actions`) is never read."""
    from tau_bench.envs import get_env
    from tau_bench.types import Action

    _patch_user_sim_max_tokens()
    env = get_env(
        domain,
        user_strategy="llm",
        user_model=user_model,
        user_provider="openrouter",
        task_split="test",
        task_index=task_index,
    )
    obs = env.reset(task_index=task_index).observation
    state_before = copy.deepcopy(env.data)
    state_after = copy.deepcopy(env.data)
    tool_trace: list[dict[str, Any]] = []
    respond_turns: list[str] = []
    reward = 0.0
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": env.wiki},
        {"role": "user", "content": obs},
    ]
    for _ in range(MAX_NUM_STEPS):
        res = completion(
            messages=messages,
            model=agent_model,
            custom_llm_provider="openrouter",
            tools=env.tools_info,
            temperature=0.0,
            seed=seed,
            max_tokens=agent_max_tokens,
        )
        choice = res.choices[0]
        if choice.finish_reason == "length":
            raise LLMResponseTruncatedError(
                f"agent completion hit max_tokens={agent_max_tokens} on {domain} task "
                f"{task_index}; raise the cap (see run-harness spec)"
            )
        message = choice.message.model_dump()
        if message.get("tool_calls"):
            call = message["tool_calls"][0]
            action = Action(
                name=call["function"]["name"],
                kwargs=json.loads(call["function"]["arguments"]),
            )
        else:
            content = message.get("content") or ""
            action = Action(name=RESPOND, kwargs={"content": content})
            respond_turns.append(content)

        response = env.step(action)
        reward = response.reward
        # Last pre-terminal snapshot = the agent-final state: the terminal RESPOND that triggers
        # calculate_reward does not mutate env.data, so the most recent non-done snapshot holds it.
        if not response.done:
            state_after = copy.deepcopy(env.data)
            tool_trace = [{"name": a.name, "kwargs": a.kwargs} for a in env.actions]

        if action.name != RESPOND:
            message["tool_calls"] = message["tool_calls"][:1]
            messages.extend(
                [
                    message,
                    {
                        "role": "tool",
                        "tool_call_id": message["tool_calls"][0]["id"],
                        "name": message["tool_calls"][0]["function"]["name"],
                        "content": response.observation,
                    },
                ]
            )
        else:
            messages.extend([message, {"role": "user", "content": response.observation}])
        if response.done:
            break

    sliced_before, sliced_after = _slice_state(state_before, state_after, tool_trace)
    return Trajectory(
        task_id=str(task_index),
        domain=domain,
        model=agent_model,
        repeat=repeat,
        seed=seed,
        query=obs,
        final_answer=respond_turns[-1] if respond_turns else "",
        answer_text="\n\n".join(respond_turns),
        tool_trace=tool_trace,
        state_before=sliced_before,
        state_after=sliced_after,
        gold_reward=reward,
        status="ok",
    )


# --- Batch capture: shard + resume + credit-aware halt (run-harness spec item 2/3) ----------

# Markers of a credit/auth failure (OpenRouter 402 / 401): halt the run so you can recharge and
# resume, rather than churning retries on every remaining task.
_HALT_MARKERS = ("402", "insufficient", "credit", "payment required", "401", "unauthorized")


def _is_halt_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _HALT_MARKERS)


def _traj_key(model: str, domain: str, repeat: int, task_id: Any) -> str:
    return f"{model}|{domain}|r{repeat}|t{task_id}"


def _shard_path(out_dir: str | Path, model: str) -> Path:
    return Path(out_dir) / (model.replace("/", "_") + ".jsonl")


def _load_done_keys(path: Path) -> set[str]:
    """Keys of the status='ok' trajectories already captured in a shard (for resume)."""
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
                done.add(
                    _traj_key(
                        record.get("model"), record.get("domain"),
                        record.get("repeat", 0), record.get("task_id"),
                    )
                )
    return done


def _pending_jobs(
    model: str, tasks: dict[str, Iterable[int]], repeats: int, done: set[str]
) -> list[tuple[str, int, int]]:
    """(domain, repeat, task_id) jobs not yet captured (status=ok) for this model."""
    return [
        (domain, repeat, task_id)
        for domain, indices in tasks.items()
        for repeat in range(repeats)
        for task_id in indices
        if _traj_key(model, domain, repeat, task_id) not in done
    ]


def run_capture_matrix(
    *,
    agent_models: list[str],
    user_model: str,
    tasks: dict[str, Iterable[int]],
    repeats: int = 1,
    seed: int | None = None,
    out_dir: str | Path = "results/capture",
    max_workers: int = 1,
) -> None:
    """Capture the (model x domain x repeat x task) matrix into per-model JSONL shards.

    Resumable: re-running skips trajectories already captured with status='ok'. Crash-safe: each
    trajectory is appended + flushed on completion (a crash loses at most the in-flight task). On a
    credit/auth error (OpenRouter 402/401) the model's run HALTS so you can recharge and re-run to
    resume from the gap; other (already-retried) transient failures are logged and left for resume.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for model in agent_models:
        path = _shard_path(out_dir, model)
        done = _load_done_keys(path)
        jobs = _pending_jobs(model, tasks, repeats, done)
        print(f"[{model}] {len(done)} done, {len(jobs)} pending -> {path}", flush=True)
        lock = threading.Lock()
        halted = threading.Event()

        def _do(job: tuple[str, int, int]) -> None:
            if halted.is_set():
                return
            domain, repeat, task_id = job
            try:
                traj = capture_trajectory(
                    agent_model=model, user_model=user_model, domain=domain,
                    task_index=task_id, repeat=repeat, seed=seed,
                )
            except Exception as exc:  # noqa: BLE001 - classify into halt vs. retry-on-resume
                if _is_halt_error(exc):
                    halted.set()
                    print(f"  HALT [{model} {domain} t{task_id}]: credit/auth ({exc}); recharge + rerun", flush=True)
                else:
                    print(f"  ERR  [{model} {domain} t{task_id}]: {type(exc).__name__}: {str(exc)[:120]}; resume will retry", flush=True)
                return
            with lock:
                with path.open("a") as handle:
                    handle.write(json.dumps(traj.model_dump()) + "\n")
                    handle.flush()
            print(f"  ok   [{model} {domain} t{task_id} r{repeat}] reward={traj.gold_reward}", flush=True)

        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(_do, jobs))
        else:
            for job in jobs:
                if halted.is_set():
                    break
                _do(job)

        if halted.is_set():
            print(f"[{model}] HALTED (credit/auth). Recharge, then re-run to resume from the gap.", flush=True)
            return
