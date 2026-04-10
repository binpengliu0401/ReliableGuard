# smoke_test_f5.py
# Validates the create → confirm chain (F5) end-to-end.
# Run from project root: python smoke_test_f5.py

from src.db.reset_env import reset_env
from src.agent.langgraph_agent import run_agent
from src.config.ablation_config import VERSIONS

# Use full pipeline (V4: Gate + Verifier + Recovery)
config = VERSIONS["V4_Full"]

# Single F5 scenario: create then confirm
scenario_input = "please confirm order 9999"

print("=" * 60)
print("SMOKE TEST: F3 dependency violation - confirm without create")
print(f"INPUT: {scenario_input}")
print("=" * 60)

reset_env()
state = run_agent(scenario_input, config=config)

print("\n" + "=" * 60)
print("FINAL STATE SUMMARY")
print("=" * 60)
print(f"tool_call      : {state.get('tool_call')}")
print(f"gate_status    : {state.get('gate_status')}")
print(f"verifier_status: {state.get('verifier_status')}")
print(f"recovery_action: {state.get('recovery_action')}")
print(f"executed_tools : {state.get('executed_tools')}")
print(f"final_answer   : {state.get('final_answer')}")

print("\nTRACE:")
for entry in state.get("trace", []):
    print(f"  [{entry['node']}] {entry['event']} — {entry['detail']}")
