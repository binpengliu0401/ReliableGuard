"""
Replace DOIs that are no longer in mock_data.json with a valid fixture DOI.
Targets: 10.48550/arXiv.1706.03762 and 10.18653/v1/N19-1423
"""

import json
from pathlib import Path


SCENARIOS_PATH = Path("tasks/reference_scenarios.json")
MOCK_PATH = Path("src/domain/reference/fixtures/mock_data.json")

STALE_DOIS = [
    "10.48550/arXiv.1706.03762",
    "10.18653/v1/N19-1423",
]

with open(MOCK_PATH, encoding="utf-8") as f:
    mock = json.load(f)

valid_doi = next(iter(mock["dois"]))  # pick first valid DOI from fixture
print(f"Replacing stale DOIs with: {valid_doi}")

with open(SCENARIOS_PATH, encoding="utf-8") as f:
    scenarios = json.load(f)

fixed = 0
for s in scenarios:
    inp = s.get("input", "")
    new_inp = inp
    for stale in STALE_DOIS:
        new_inp = new_inp.replace(stale, valid_doi)
    if new_inp != inp:
        s["input"] = new_inp
        fixed += 1

with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
    json.dump(scenarios, f, ensure_ascii=False, indent=2)

print(f"Fixed {fixed} scenarios with stale DOIs")
