"""
Fix F2 scenarios that incorrectly reference react instead of critic.
"""

import json
from pathlib import Path


PATH = Path("tasks/reference_scenarios.json")

with open(PATH, encoding="utf-8") as f:
    scenarios = json.load(f)

fixed = 0
for s in scenarios:
    if s.get("failure_mode") != "F2":
        continue
    inp = s.get("input", "")
    new_inp = (
        inp.replace("'react.pdf'", "'critic.pdf'")
        .replace('"react.pdf"', '"critic.pdf"')
        .replace("'react'", "'critic'")
        .replace('"react"', '"critic"')
    )
    if new_inp != inp:
        s["input"] = new_inp
        fixed += 1

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(scenarios, f, ensure_ascii=False, indent=2)

print(f"Fixed {fixed} F2 scenarios: react → critic")
