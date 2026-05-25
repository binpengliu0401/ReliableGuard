"""
Update tasks/reference_scenarios.json to replace fictional paper names
with real paper names using tasks/paper_name_mapping.json.
"""
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = PROJECT_ROOT / "tasks" / "reference_scenarios.json"
MAPPING_PATH = PROJECT_ROOT / "tasks" / "paper_name_mapping.json"


def apply_mapping(text: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        text = text.replace(old, new)
        # Also replace without .pdf extension when used as paper_id.
        old_id = old.replace(".pdf", "")
        new_id = new.replace(".pdf", "")
        text = text.replace(f"'{old_id}'", f"'{new_id}'")
        text = text.replace(f'"{old_id}"', f'"{new_id}"')
    return text


def main() -> None:
    if not SCENARIOS_PATH.exists():
        print(f"ERROR: {SCENARIOS_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not MAPPING_PATH.exists():
        print(f"ERROR: {MAPPING_PATH} not found — run build_mock_fixture_from_csv.py first", file=sys.stderr)
        sys.exit(1)

    with open(MAPPING_PATH, encoding="utf-8") as f:
        mapping = json.load(f)

    with open(SCENARIOS_PATH, encoding="utf-8") as f:
        scenarios = json.load(f)

    updated = 0
    for scenario in scenarios:
        original = json.dumps(scenario)
        replaced = apply_mapping(original, mapping)
        if replaced != original:
            scenario.update(json.loads(replaced))
            updated += 1

    with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, ensure_ascii=False, indent=2)

    print(f"[OK] Updated {updated}/{len(scenarios)} scenarios in reference_scenarios.json")


if __name__ == "__main__":
    main()
