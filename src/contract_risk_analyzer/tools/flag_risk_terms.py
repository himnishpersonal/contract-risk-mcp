from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from contract_risk_analyzer.schemas.outputs import RiskTerm, RiskTermList
from contract_risk_analyzer.utils.llm_client import call_llm
from contract_risk_analyzer.utils.pdf_parser import extract_text_from_pdf
from contract_risk_analyzer.utils.pdf_source import pdf_path_from_source


_SEED_TERMS = [
    "cross-default",
    "material adverse change",
    "acceleration clause",
    "ipso facto",
    "walkaway clause",
    "negative pledge",
    "pari passu",
    "event of default",
    "force majeure",
    "indemnification",
]

_SYSTEM_PROMPT = (
    "You are a financial legal risk analyst. Explain why this clause term is "
    "significant, what risk it poses to each party, and rate its severity."
)


def _words_around(text: str, start_idx: int, end_idx: int, max_words: int = 200) -> str:
    prefix = text[:start_idx]
    hit = text[start_idx:end_idx]
    suffix = text[end_idx:]
    pre_words = prefix.split()
    post_words = suffix.split()
    left = " ".join(pre_words[-max_words // 2:])
    right = " ".join(post_words[:max_words // 2])
    return f"{left} {hit} {right}".strip()


def _severity_rank(sev: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(sev, 0)


def _call_for_term(term: str, m: re.Match, full_text: str) -> RiskTerm | None:
    ctx = _words_around(full_text, m.start(), m.end(), max_words=200)
    user_prompt = (
        f"Term: {term}\n\n"
        f"Context (approx 200 words):\n{ctx}\n\n"
        "Return a JSON object with key 'items' containing a single RiskTerm in a list."
    )
    parsed = call_llm(_SYSTEM_PROMPT, user_prompt, RiskTermList)
    if parsed.items:
        item = parsed.items[0]
        item.term = item.term or term
        return item
    return None


def flag_risk_terms(
    file_path: str | None = None,
    pdf_url: str | None = None,
) -> list[RiskTerm]:
    with pdf_path_from_source(file_path=file_path, pdf_url=pdf_url) as resolved_path:
        sections = extract_text_from_pdf(resolved_path)
    full_text = "\n\n".join(sections.values())
    lower = full_text.lower()

    found_terms: list[tuple[str, re.Match]] = []
    for term in _SEED_TERMS:
        for m in re.finditer(re.escape(term.lower()), lower):
            found_terms.append((term, m))
            break  # one match per term is enough

    # Run all OpenAI calls in parallel via thread pool
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_call_for_term, term, m, full_text)
            for term, m in found_terms
        ]
        results = [f.result() for f in futures]

    found = [r for r in results if r is not None]
    found.sort(key=lambda x: _severity_rank(x.severity), reverse=True)
    return found
