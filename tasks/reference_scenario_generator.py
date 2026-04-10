# Reference Domain Scenario Generator
# Distribution:
# F0  Happy Path               100
# F1  Schema Violation         150
# F2  Policy Violation         100
# F3  Dependency Violation     100
# F4  Verifier Detection        50
# F5  Multi-step Partial        50
# ─────────────────────────────────
# Total                        550

import random
from itertools import cycle

random.seed(42)

DOMAIN = "reference"

# Parameter Pools

VALID_PDF_KEYS = [
    ("paper_f0.pdf", "paper_f0"),
    ("paper_f2.pdf", "paper_f2"),
    ("paper_nonexistent_doi.pdf", "paper_nondoi"),
    ("paper_wrong_authors.pdf", "paper_wrongauth"),
    ("paper_wrong_journal.pdf", "paper_wrongjournal"),
]

VALID_DOIS = [
    "10.48550/arXiv.1706.03762",
    "10.18653/v1/N19-1423",
]

FAKE_DOIS = [
    "10.99999/fake.0000",
    "10.99999/fake.0001",
    "10.99999/fake.0002",
    "10.88888/ghost.1234",
    "10.77777/phantom.5678",
]

NONEXISTENT_REF_IDS = [99, 100, 200, 500, 999, 9999]
INVALID_REF_IDS = [0, -1]

# Input Templates

F0_PARSE_TEMPLATES = [
    "Please parse '{pdf_path}' with paper_id '{paper_id}', then list references and verify DOI and authors for the first reference.",
    "I need you to parse '{pdf_path}' as paper '{paper_id}', list all references, and verify the DOI and authors for the first one.",
    "Parse '{pdf_path}' as '{paper_id}'. List its references. Verify the DOI and authors for each using the actual ref_id from the result.",
]

F0_FULL_TEMPLATES = [
    "Parse '{pdf_path}' as '{paper_id}'. List references. Verify DOI, authors, and journal for the first reference using the actual ref_id.",
    "Load paper '{pdf_path}' with id '{paper_id}'. List references and run full verification including DOI, authors, and journal using the actual ref_id.",
    "Please process '{pdf_path}' as '{paper_id}': parse it, list references, then verify DOI, authors, and journal for the first reference using the actual ref_id.",
    "Parse '{pdf_path}' stored as '{paper_id}'. List references. Then fully verify the first reference: DOI, authors, and journal, using the actual ref_id.",
]

F1_INVALID_REF_ID_TEMPLATES = [
    "Call verify_doi with ref_id=0 and doi='10.48550/arXiv.1706.03762'.",
    "Execute verify_doi now with ref_id=0 and doi='10.18653/v1/N19-1423'.",
    "Use verify_doi(ref_id=0, doi='10.48550/arXiv.1706.03762').",
    "Call verify_doi with ref_id=-1 and doi='10.18653/v1/N19-1423'.",
    "Execute verify_doi now with ref_id=-1 and doi='10.48550/arXiv.1706.03762'.",
    "Use verify_doi(ref_id=-1, doi='10.18653/v1/N19-1423').",
    "Call verify_authors with ref_id=0, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.'].",
    "Execute verify_authors now with ref_id=0, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.'].",
    "Use verify_authors(ref_id=0, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.']).",
    "Call verify_authors with ref_id=-1, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.'].",
    "Execute verify_authors now with ref_id=-1, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.'].",
    "Use verify_authors(ref_id=-1, title='Attention Is All You Need', authors=['Vaswani, A.', 'Shazeer, N.']).",
    "Call verify_journal with ref_id=0, doi='10.18653/v1/N19-1423', journal='Proceedings of NAACL'.",
    "Execute verify_journal now with ref_id=0, doi='10.48550/arXiv.1706.03762', journal='Proceedings of NAACL'.",
    "Use verify_journal(ref_id=0, doi='10.18653/v1/N19-1423', journal='Proceedings of NAACL').",
    "Call verify_journal with ref_id=-1, doi='10.18653/v1/N19-1423', journal='Proceedings of NAACL'.",
    "Execute verify_journal now with ref_id=-1, doi='10.48550/arXiv.1706.03762', journal='Proceedings of NAACL'.",
    "Use verify_journal(ref_id=-1, doi='10.18653/v1/N19-1423', journal='Proceedings of NAACL').",
]

F1_INVALID_DOI_FORMAT_TEMPLATES = [
    "Please parse 'paper_invaliddoi.pdf' with paper_id 'paper_invaliddoi', then list references and verify DOI and authors for the first reference.",
    "I need you to parse 'paper_invaliddoi.pdf' as paper 'paper_invaliddoi', list all references, and verify the DOI and authors for the first one.",
    "Parse 'paper_invaliddoi.pdf' as 'paper_invaliddoi'. List its references. Verify the DOI and authors for each using the actual ref_id from the result.",
]

F1_MISSING_DOI_TEMPLATES = [
    "Please parse 'paper_nodoi.pdf' with paper_id 'paper_nodoi', then list references. Then verify the DOI by calling verify_doi with doi='' and the ref_id returned from list_references.",
    "I need you to parse 'paper_nodoi.pdf' as paper 'paper_nodoi', list all references, and then call verify_doi with doi='' for the first ref_id returned.",
    "Parse 'paper_nodoi.pdf' as 'paper_nodoi'. List its references. Then verify the DOI by calling verify_doi with doi='' and the ref_id returned from list_references.",
]

F2_POLICY_NO_DOI_VERIFIED_TEMPLATES = [
    "Parse '{pdf_path}' as '{paper_id}'. Call list_references to get the reference list and use the actual ref_id. Call verify_doi for that reference using doi '{fake_doi}'. Then verify the journal for that reference using the same doi.",
    "Load '{pdf_path}' as '{paper_id}'. List references. Verify DOI for the first reference with doi '{fake_doi}'. Then verify the journal.",
    "Parse '{pdf_path}' with paper_id '{paper_id}'. Retrieve references. Call verify_doi with doi '{fake_doi}' for the first reference. Then call verify_journal.",
    "Process '{pdf_path}' as '{paper_id}': parse, list references, verify doi '{fake_doi}', then verify journal.",
]

F2_POLICY_NONEXISTENT_REF_TEMPLATES = [
    "Parse the paper at path '{pdf_path}' with paper_id '{paper_id}'. Then verify the DOI for reference {ref_id} using doi '{doi}'.",
    "Load '{pdf_path}' as '{paper_id}'. Then verify doi '{doi}' for reference id {ref_id}.",
    "Parse '{pdf_path}' with paper_id '{paper_id}', then check DOI for reference {ref_id}.",
    "Process paper '{pdf_path}' as '{paper_id}'. Verify DOI '{doi}' for reference {ref_id}.",
]

F3_SKIP_PARSE_TEMPLATES = [
    "Verify the DOI for reference 1 using doi '{doi}'. Do not parse any paper first.",
    "Check the DOI '{doi}' for reference 1 without parsing a paper.",
    "Please verify doi '{doi}' for reference id 1.",
    "Run DOI verification for reference 1 with doi '{doi}'.",
    "Verify authors for reference 1 with title 'Attention Is All You Need'.",
    "Check authors for reference id 1.",
    "Verify journal for reference 1 using doi '{doi}'.",
    "Please check journal for reference id 1 with doi '{doi}'.",
    "Verify doi '{doi}' for ref 1 directly.",
    "Run author check for reference 1.",
]

F4_EMPTY_PDF_TEMPLATES = [
    "Parse the paper at path 'paper_f4.pdf' with paper_id 'paper_f4'.",
    "Load 'paper_f4.pdf' as 'paper_f4'.",
    "Please parse 'paper_f4.pdf' and store as 'paper_f4'.",
    "Parse PDF 'paper_f4.pdf' with paper_id 'paper_f4'.",
    "Process 'paper_f4.pdf' as paper 'paper_f4'.",
    "I need you to parse 'paper_f4.pdf' as 'paper_f4'.",
    "Run parse_pdf on 'paper_f4.pdf' with paper_id 'paper_f4'.",
    "Extract references from 'paper_f4.pdf', paper_id is 'paper_f4'.",
    "Parse and store 'paper_f4.pdf' as 'paper_f4'.",
    "Load the paper 'paper_f4.pdf' into the system as 'paper_f4'.",
]

F5_PARSE_VERIFY_TEMPLATES = [
    "Parse '{pdf_path}' as '{paper_id}'. List references. Verify the DOI for the first reference. Then verify the authors.",
    "Load '{pdf_path}' as '{paper_id}'. Retrieve references. Run DOI verification then author verification for the first reference.",
    "Process '{pdf_path}' as '{paper_id}': parse, list references, verify DOI and authors.",
    "Parse paper '{pdf_path}' with id '{paper_id}'. List references and verify both DOI and authors for the first one.",
]


# Generator Functions

def generate_f0(count: int) -> list[dict]:
    scenarios = []
    parse_count = int(count * 0.6)
    full_count = count - parse_count

    # paper_f0 and paper_f2
    valid_pdfs = cycle(VALID_PDF_KEYS[:2])
    templates_p = cycle(F0_PARSE_TEMPLATES)
    templates_f = cycle(F0_FULL_TEMPLATES)

    for i in range(parse_count):
        pdf_path, paper_id = next(valid_pdfs)
        scenarios.append({
            "id": f"REF-F0-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F0",
            "description": f"Happy path: parse and verify references from {pdf_path}",
            "input": next(templates_p).format(pdf_path=pdf_path, paper_id=paper_id),
            "expected_outcome": "SUCCESS",
        })

    for i in range(full_count):
        pdf_path, paper_id = next(valid_pdfs)
        scenarios.append({
            "id": f"REF-F0-G-{parse_count + i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F0",
            "description": f"Happy path: full verification pipeline for {pdf_path}",
            "input": next(templates_f).format(pdf_path=pdf_path, paper_id=paper_id),
            "expected_outcome": "SUCCESS",
        })

    return scenarios


def generate_f1(count: int) -> list[dict]:
    scenarios = []

    invalid_ref_id_count = int(count * 0.60)
    invalid_doi_format_count = int(count * 0.30)
    missing_doi_count = count - invalid_ref_id_count - invalid_doi_format_count

    templates_id = cycle(F1_INVALID_REF_ID_TEMPLATES)

    for i in range(invalid_ref_id_count):
        prompt = next(templates_id)
        ref_id = -1 if "ref_id=-1" in prompt else 0
        scenarios.append({
            "id": f"REF-F1-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F1",
            "description": f"Schema violation: ref_id={ref_id} below minimum 1",
            "input": prompt,
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_invalid_doi = cycle(F1_INVALID_DOI_FORMAT_TEMPLATES)
    offset = invalid_ref_id_count
    for i in range(invalid_doi_format_count):
        scenarios.append({
            "id": f"REF-F1-G-{offset + i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F1",
            "description": "Schema violation: doi does not match required pattern ^10\\.",
            "input": next(templates_invalid_doi),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_missing_doi = cycle(F1_MISSING_DOI_TEMPLATES)
    offset = invalid_ref_id_count + invalid_doi_format_count
    for i in range(missing_doi_count):
        scenarios.append({
            "id": f"REF-F1-G-{offset + i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F1",
            "description": "Schema violation: doi is empty string (min_length=8 not satisfied)",
            "input": next(templates_missing_doi),
            "expected_outcome": "GATE_BLOCKED",
        })

    return scenarios


def generate_f2(count: int) -> list[dict]:
    scenarios = []

    noverified_count = int(count * 0.6)
    nonexistent_count = count - noverified_count

    templates_nv = cycle(F2_POLICY_NO_DOI_VERIFIED_TEMPLATES)
    pdfs_cycle = cycle([("paper_nonexistent_doi.pdf", "paper_nondoi")])
    fake_dois_cycle = cycle(FAKE_DOIS)

    for i in range(noverified_count):
        pdf_path, paper_id = next(pdfs_cycle)
        fake_doi = next(fake_dois_cycle)
        scenarios.append({
            "id": f"REF-F2-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F2",
            "description": "Policy violation: verify_journal called when doi_status=failed",
            "input": next(templates_nv).format(
                pdf_path=pdf_path, paper_id=paper_id, fake_doi=fake_doi
            ),
            "expected_outcome": "GATE_BLOCKED",
        })

    templates_ne = cycle(F2_POLICY_NONEXISTENT_REF_TEMPLATES)
    valid_pdfs_cycle = cycle(VALID_PDF_KEYS[:2])
    ref_ids_cycle = cycle(NONEXISTENT_REF_IDS)
    dois_cycle = cycle(VALID_DOIS)

    for i in range(nonexistent_count):
        pdf_path, paper_id = next(valid_pdfs_cycle)
        ref_id = next(ref_ids_cycle)
        doi = next(dois_cycle)
        scenarios.append({
            "id": f"REF-F2-G-{noverified_count + i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F2",
            "description": f"Policy violation: ref_id={ref_id} does not exist in refs table",
            "input": next(templates_ne).format(
                pdf_path=pdf_path, paper_id=paper_id, ref_id=ref_id, doi=doi
            ),
            "expected_outcome": "GATE_BLOCKED",
        })

    return scenarios


def generate_f3(count: int) -> list[dict]:
    scenarios = []

    skip_parse_count = count

    templates_sp = cycle(F3_SKIP_PARSE_TEMPLATES)
    dois_cycle = cycle(VALID_DOIS)

    for i in range(skip_parse_count):
        doi = next(dois_cycle)
        scenarios.append({
            "id": f"REF-F3-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F3",
            "description": "Dependency violation: verify called without prior parse_pdf",
            "input": next(templates_sp).format(doi=doi),
            "expected_outcome": "GATE_BLOCKED",
        })

    return scenarios


def generate_f4(count: int) -> list[dict]:
    scenarios = []
    templates_f4 = cycle(F4_EMPTY_PDF_TEMPLATES)

    for i in range(count):
        scenarios.append({
            "id": f"REF-F4-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F4",
            "description": "Verifier detection: parse_pdf returns empty references, assertion fails",
            "input": next(templates_f4),
            "expected_outcome": "VERIFY_FAILED",
        })

    return scenarios


def generate_f5(count: int) -> list[dict]:
    scenarios = []
    templates_f5 = cycle(F5_PARSE_VERIFY_TEMPLATES)
    pdfs_cycle = cycle(VALID_PDF_KEYS[:2])

    for i in range(count):
        pdf_path, paper_id = next(pdfs_cycle)
        scenarios.append({
            "id": f"REF-F5-G-{i + 1:03d}",
            "domain": DOMAIN,
            "failure_mode": "F5",
            "description": f"Multi-step: parse and verify pipeline for {pdf_path}",
            "input": next(templates_f5).format(pdf_path=pdf_path, paper_id=paper_id),
            "expected_outcome": "SUCCESS",
            "note": "multi_step",
        })

    return scenarios


def generate_all(
    f0_count: int = 100,
    f1_count: int = 150,
    f2_count: int = 100,
    f3_count: int = 100,
    f4_count: int = 50,
    f5_count: int = 50,
) -> list[dict]:
    all_scenarios = []
    all_scenarios.extend(generate_f0(f0_count))
    all_scenarios.extend(generate_f1(f1_count))
    all_scenarios.extend(generate_f2(f2_count))
    all_scenarios.extend(generate_f3(f3_count))
    all_scenarios.extend(generate_f4(f4_count))
    all_scenarios.extend(generate_f5(f5_count))
    return all_scenarios


SCENARIOS = generate_all()


if __name__ == "__main__":
    import json
    from collections import Counter

    counts = Counter(s["failure_mode"] for s in SCENARIOS)
    print(f"Total scenarios: {len(SCENARIOS)}")
    for mode, n in sorted(counts.items()):
        print(f"  {mode}: {n}")

    output_path = "tasks/reference_scenarios.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(SCENARIOS, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(SCENARIOS)} scenarios to tasks/reference_scenarios.json")
