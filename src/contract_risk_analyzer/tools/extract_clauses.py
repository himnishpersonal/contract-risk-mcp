from __future__ import annotations

from typing import Iterable

from contract_risk_analyzer.schemas.outputs import ClauseExtraction, ClauseExtractionList
from contract_risk_analyzer.utils.llm_client import call_llm
from contract_risk_analyzer.utils.pdf_parser import extract_text_from_pdf


_SYSTEM_PROMPT = (
    "You are a legal analyst specializing in financial contracts. Extract "
    "all clauses of the requested type and return structured data. Be precise "
    "about page references and always provide plain English explanations."
)


def _keywords_for_clause_type(clause_type: str) -> set[str]:
    base = clause_type.lower().strip()
    words = {w for w in base.replace("-", " ").split() if len(w) > 2}
    synonyms: dict[str, set[str]] = {
        "termination": {"terminate", "termination", "early termination"},
        "default": {"default", "event of default", "events of default", "breach"},
        "collateral": {"collateral", "margin", "security", "pledge"},
        "covenants": {"covenant", "covenants", "undertaking", "undertakings"},
        "indemnification": {"indemnity", "indemnification", "hold harmless"},
        "force": {"force majeure"},
    }
    extra: set[str] = set()
    for k, v in synonyms.items():
        if k in words or k in base:
            extra |= {t.lower() for t in v}
    return words | extra | {base}


def _section_relevance(section_name: str, section_text: str, keywords: set[str]) -> bool:
    hay = f"{section_name}\n{section_text}".lower()
    return any(k in hay for k in keywords if k)


def _iter_relevant_sections(
    sections: dict[str, str], keywords: set[str]
) -> Iterable[tuple[str, str]]:
    for name, text in sections.items():
        if _section_relevance(name, text, keywords):
            yield name, text


async def extract_clauses(file_path: str, clause_type: str) -> list[ClauseExtraction]:
    sections = extract_text_from_pdf(file_path)
    keywords = _keywords_for_clause_type(clause_type)

    results: list[ClauseExtraction] = []
    for section_name, section_text in _iter_relevant_sections(sections, keywords):
        user_prompt = (
            f"Requested clause type: {clause_type}\n\n"
            f"Section name: {section_name}\n"
            f"Section text:\n{section_text}\n\n"
            "Return extractions as a JSON object with key 'items' containing a list."
        )
        parsed = call_llm(_SYSTEM_PROMPT, user_prompt, ClauseExtractionList)
        for item in parsed.items:
            # Ensure clause_type/section_name are populated even if the model omits them.
            item.clause_type = item.clause_type or clause_type
            item.section_name = item.section_name or section_name
            results.append(item)

    return results

