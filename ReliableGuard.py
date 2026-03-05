from src.agent.react_agent import run_agent
from tasks.obs001_tasks import TASKS


if __name__ == "__main__":
    
    for task in TASKS:
        result = run_agent(task["input"])
        
        # conclusion
        verdict = result.get("verifier_verdict", "N/A")
        gate_blocked = result.get("gate_blocked", False)
        tool_called = result.get("tool_called", False)
        
        if not tool_called:
            status = "NOT_TRIGGERED"
        elif gate_blocked:
            status = "GATE_BLOCKED"
        elif verdict == "FALSE_SUCCESS":
            status = "FALSE_SUCCESS"
        elif verdict == "SUCCESS":
            status = "SUCCESS"
        else:
            status = "UNKNOWN"
        
        print(f"[RESULT]    {task['id']} - {status}\n")
        
    
    
