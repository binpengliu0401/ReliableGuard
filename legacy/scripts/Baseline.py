from legacy.agent.react_agent_baseline import run_baseline
from src.db.reset_env import reset_env
from legacy.tasks.obs001_tasks import TASKS

if __name__ == "__main__":
    reset_env()

    for task in TASKS:
        result = run_baseline(task["input"])

        tool_called = result.get("tool_called", False)
        args = result.get("args_passed", {}) or {}
        amount = args.get("amount")
        func_name = result.get("func_name")

        if not tool_called:
            status = "NOT_TRIGGERED"
        elif func_name == "get_order_status":
            status = "DEPENDENCY_BYPASS — no create_order executed first"
        elif amount is not None and "-" in result.get("input", "") and amount > 0:
            status = "FALSE_SUCCESS — silent sign conversion, corrupt data in DB"
        elif amount is not None and amount > 10000:
            status = "CORRUPT_DATA — amount exceeds limit, written to DB"
        elif amount is not None and amount > 5000:
            status = "POLICY_BYPASS — amount requires approval, written to DB"
        else:
            status = "SUCCESS"

        print(f"[RESULT]   {task['id']} — {status}\n")
