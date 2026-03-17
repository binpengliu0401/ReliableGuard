from src.agent.langgraph_agent import run_agent
from tasks.obs001_tasks import TASKS
from src.db.reset_env import reset_env


if __name__ == "__main__":

    reset_env()

    for task in TASKS:
        result = run_agent(task["input"])

        gate_status = result.get("gate_status")
        verifier_status = result.get("verifier_status")
        recovery_action = result.get("recovery_action")
        tool_call = result.get("tool_call")

        if tool_call is None:
            status = "NOT_TRIGGERED"
        elif gate_status == "BLOCKED":
            status = f"GATE_BLOCKED — {result.get('gate_detail', '')}"
        elif recovery_action == "rollback":
            status = f"FALSE_SUCCESS — {result.get('verifier_detail', '')}"
        elif verifier_status == "PASSED":
            status = "SUCCESS"
        else:
            status = "UNKNOWN"

        print(f"[RESULT]    {task['id']} — {status}\n")