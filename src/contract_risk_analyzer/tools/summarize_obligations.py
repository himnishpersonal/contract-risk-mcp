from __future__ import annotations

from collections import defaultdict

from contract_risk_analyzer.schemas.outputs import ObligationSummary, ObligationSummaryList
from contract_risk_analyzer.utils.chunker import chunk_section
from contract_risk_analyzer.utils.llm_client import call_llm
from contract_risk_analyzer.utils.pdf_parser import extract_text_from_pdf
from contract_risk_analyzer.utils.pdf_source import pdf_path_from_source


_SYSTEM_PROMPT = (
    "You are a legal analyst. Identify each named party in this contract "
    "and list their specific obligations, deadlines, and conditions precisely."
)


def _dedupe_extend(target: list[str], items: list[str]) -> None:
    seen = set(target)
    for it in items:
        s = (it or "").strip()
        if not s or s in seen:
            continue
        target.append(s)
        seen.add(s)


def summarize_obligations(
    file_path: str | None = None,
    pdf_url: str | None = None,
) -> list[ObligationSummary]:
    with pdf_path_from_source(file_path=file_path, pdf_url=pdf_url) as resolved_path:
        sections = extract_text_from_pdf(resolved_path)
    full_text = "\n\n".join(sections.values())
    chunks = chunk_section(full_text, max_tokens=1500)

    by_party: dict[str, ObligationSummary] = {}

    for chunk in chunks:
        user_prompt = (
            "Contract text chunk:\n"
            f"{chunk}\n\n"
            "Return a JSON object with key 'items' containing a list of obligations grouped by party."
        )
        parsed = call_llm(_SYSTEM_PROMPT, user_prompt, ObligationSummaryList)
        for item in parsed.items:
            party = (item.party or "").strip() or "Unknown"
            if party not in by_party:
                by_party[party] = ObligationSummary(
                    party=party, obligations=[], key_deadlines=[], conditions=[]
                )
            agg = by_party[party]
            _dedupe_extend(agg.obligations, item.obligations)
            _dedupe_extend(agg.key_deadlines, item.key_deadlines)
            _dedupe_extend(agg.conditions, item.conditions)

    # Stable-ish ordering: parties with more obligations first.
    return sorted(by_party.values(), key=lambda x: len(x.obligations), reverse=True)
