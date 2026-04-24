from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.langgraph_agent import run_agent
from src.db.reset_env import reset_env


def print_result(title: str, result: dict):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print("final_answer:", result.get("final_answer"))
    print("gate_status:", result.get("gate_status"))
    print("gate_detail:", result.get("gate_detail"))
    print("verifier_status:", result.get("verifier_status"))
    print("verifier_detail:", result.get("verifier_detail"))
    print("recovery_action:", result.get("recovery_action"))
    print("recovery_detail:", result.get("recovery_detail"))
    print("tool_call:", result.get("tool_call"))
    print("executed_tools:", result.get("executed_tools"))
    print("\nTRACE:")
    for t in result.get("trace", []):
        print(f"  - [{t['node']}] {t['event']} :: {t['detail']}")


def smoke_test_ecommerce_success():
    reset_env()

    result = run_agent(
        "Please create an order with amount 100.",
        domain="ecommerce",
    )
    print_result("ECOMMERCE SUCCESS SMOKE TEST", result)


def smoke_test_ecommerce_gate_block():
    reset_env()

    result = run_agent(
        "Please create an order with amount -500.",
        domain="ecommerce",
    )
    print_result("ECOMMERCE GATE BLOCK SMOKE TEST", result)


def smoke_test_reference_parse(pdf_filename: str, paper_id: str, title: str):
    pdf_path = str(Path(f"data/{pdf_filename}").resolve())

    result = run_agent(
        f'Please parse the PDF at "{pdf_path}" with paper_id "{paper_id}".',
        domain="reference",
    )
    print_result(title, result)


def smoke_test_reference_parse_valid():
    smoke_test_reference_parse(
        pdf_filename="paper_valid.pdf",
        paper_id="paper_ref_valid_001",
        title="REFERENCE PARSE VALID SMOKE TEST",
    )


def smoke_test_reference_parse_nonexistent_doi():
    smoke_test_reference_parse(
        pdf_filename="paper_nonexistent_doi.pdf",
        paper_id="paper_ref_nonexistent_doi_001",
        title="REFERENCE PARSE NONEXISTENT DOI SMOKE TEST",
    )


def smoke_test_reference_parse_wrong_doi():
    smoke_test_reference_parse(
        pdf_filename="paper_wrong_doi.pdf",
        paper_id="paper_ref_wrong_doi_001",
        title="REFERENCE PARSE WRONG DOI SMOKE TEST",
    )


def smoke_test_reference_parse_wrong_authors():
    smoke_test_reference_parse(
        pdf_filename="paper_wrong_authors.pdf",
        paper_id="paper_ref_wrong_authors_001",
        title="REFERENCE PARSE WRONG AUTHORS SMOKE TEST",
    )


def smoke_test_reference_parse_wrong_journal():
    smoke_test_reference_parse(
        pdf_filename="paper_wrong_journal.pdf",
        paper_id="paper_ref_wrong_journal_001",
        title="REFERENCE PARSE WRONG JOURNAL SMOKE TEST",
    )


if __name__ == "__main__":
    smoke_test_ecommerce_success()
    smoke_test_ecommerce_gate_block()

    smoke_test_reference_parse_valid()
    smoke_test_reference_parse_nonexistent_doi()
    smoke_test_reference_parse_wrong_doi()
    smoke_test_reference_parse_wrong_authors()
    smoke_test_reference_parse_wrong_journal()
