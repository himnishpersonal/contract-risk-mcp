from __future__ import annotations

import re
from collections import OrderedDict

import fitz  # PyMuPDF


_RE_SECTION_NUMBERED = re.compile(
    r"^(?:Section|SECTION)\s+\d+(?:\.\d+)*\s*[\.:]\s+.+$"
)
_RE_ARTICLE = re.compile(r"^(?:Article|ARTICLE)\s+(?:[IVXLCDM]+|\d+)\b.*$")
_RE_NUMERIC_HEADING = re.compile(r"^\d+(?:\.\d+){0,4}\s+.+$")


def _is_all_caps_heading(line: str) -> bool:
    s = re.sub(r"\s+", " ", line.strip())
    if len(s) < 8:
        return False
    if len(s) > 140:
        return False
    # allow basic punctuation/digits but require letters that are all uppercase
    letters = re.findall(r"[A-Za-z]", s)
    if len(letters) < 6:
        return False
    return all(ch.isupper() for ch in letters)


def _normalize_heading(line: str) -> str:
    s = re.sub(r"\s+", " ", line.strip())
    s = s.strip(" -:\t")
    return s


def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _RE_SECTION_NUMBERED.match(s):
        return True
    if _RE_ARTICLE.match(s):
        return True
    if _RE_NUMERIC_HEADING.match(s) and len(s) <= 120:
        return True
    if _is_all_caps_heading(s):
        return True
    return False


def extract_text_from_pdf(file_path: str) -> dict[str, str]:
    """
    Extract text page-by-page, detect section headers, and return a dict:
    section_name -> section_text.
    """
    doc = fitz.open(file_path)

    sections: "OrderedDict[str, list[str]]" = OrderedDict()
    section_order: list[str] = []

    def ensure_section(name: str) -> str:
        base = name or "Preamble"
        candidate = base
        i = 2
        while candidate in sections:
            candidate = f"{base} ({i})"
            i += 1
        if candidate not in sections:
            sections[candidate] = []
            section_order.append(candidate)
        return candidate

    current_section = ensure_section("Preamble")

    for page_index, page in enumerate(doc, start=1):
        raw = page.get_text("text") or ""
        lines = raw.splitlines()

        # Add lightweight page boundary marker to help downstream prompts.
        sections[current_section].append(f"\n[Page {page_index}]\n")

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _looks_like_heading(stripped):
                heading = _normalize_heading(stripped)
                current_section = ensure_section(heading)
                sections[current_section].append(f"\n[Page {page_index}]\n")
                continue
            sections[current_section].append(stripped)

    doc.close()

    out: dict[str, str] = {}
    for name in section_order:
        text = "\n".join(sections[name]).strip()
        if text:
            out[name] = text
    return out


if __name__ == "__main__":
    sample_pdf_path = "/path/to/sample.pdf"
    try:
        section_map = extract_text_from_pdf(sample_pdf_path)
        print("Sections found:")
        for section_name in section_map.keys():
            print("-", section_name)
    except Exception as e:
        print(f"Failed to parse sample PDF at {sample_pdf_path}: {e}")

