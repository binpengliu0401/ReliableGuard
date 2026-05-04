#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "src" / "domain" / "reference" / "fixtures" / "real_data.json"
PAPER_DIR = REPO_ROOT / "tasks" / "papers"

PAGE_W = 612
PAGE_H = 792
MARGIN_X = 54
TOP_Y = 738
LINE_H = 14
FONT_SIZE = 10
TITLE_FONT_SIZE = 14
MAX_CHARS = 92


def main() -> int:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for filename in ("reference 1.pdf", "reference 2.pdf"):
        refs = data["pdfs"][filename]["references"]
        out_path = PAPER_DIR / filename
        backup_path = PAPER_DIR / f"{out_path.stem}.original.pdf"
        if out_path.exists() and not backup_path.exists():
            backup_path.write_bytes(out_path.read_bytes())
        _make_pdf(out_path, refs)
        print(f"wrote {out_path.relative_to(REPO_ROOT)} refs={len(refs)}")
    return 0


def _make_pdf(path: Path, refs: list[dict[str, Any]]) -> None:
    objects: list[str] = []

    def add(obj: str) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add("")
    pages_id = add("")
    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []

    for page_lines in _build_pages(refs):
        stream_lines = ["BT"]
        y = TOP_Y
        for text, size in page_lines:
            stream_lines.append(f"/F1 {size} Tf")
            stream_lines.append(f"1 0 0 1 {MARGIN_X} {y} Tm")
            stream_lines.append(f"({_pdf_escape(text)}) Tj")
            y -= 24 if size == TITLE_FONT_SIZE else LINE_H
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_id = add(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
    )
    path.write_bytes(out)


def _build_pages(refs: list[dict[str, Any]]) -> list[list[tuple[str, int]]]:
    pages: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = [("References", TITLE_FONT_SIZE)]
    y = TOP_Y - 24
    for idx, ref in enumerate(refs, 1):
        wrapped = _wrap_text(_reference_line(idx, ref))
        needed = len(wrapped) * LINE_H + 8
        if y - needed < 54:
            pages.append(current)
            current = [("References continued", TITLE_FONT_SIZE)]
            y = TOP_Y - 24
        for line_idx, line in enumerate(wrapped):
            current.append((line if line_idx == 0 else f"    {line}", FONT_SIZE))
            y -= LINE_H
        y -= 6
    pages.append(current)
    return pages


def _reference_line(index: int, ref: dict[str, Any]) -> str:
    authors = " and ".join(_title_case_author(author) for author in ref.get("authors", [])) or "Unknown"
    year = ref.get("year") or "n.d."
    title = ref.get("title") or "Untitled"
    journal = ref.get("journal") or ""
    doi = ref.get("doi") or ""
    journal_part = f" {journal}." if journal else ""
    doi_part = f" https://doi.org/{doi}" if doi else ""
    return _ascii_text(f"[{index}] {authors} ({year}). {title}.{journal_part}{doi_part}")


def _wrap_text(text: str) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= MAX_CHARS:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _title_case_author(author: str) -> str:
    return " ".join(part.upper() if len(part) == 1 else part.capitalize() for part in author.split())


def _ascii_text(text: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
        "\u00ad": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


if __name__ == "__main__":
    raise SystemExit(main())
