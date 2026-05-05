from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from contract_risk_analyzer.schemas.outputs import ContractDiff
from contract_risk_analyzer.utils.llm_client import call_llm
from contract_risk_analyzer.utils.pdf_parser import extract_text_from_pdf


class _SectionDiff(BaseModel):
    section_name: str
    added_clauses: list[str] = Field(default_factory=list)
    removed_clauses: list[str] = Field(default_factory=list)
    materially_changed_clauses: list[dict[str, Any]] = Field(default_factory=list)
    risk_note: str = ""


class _SectionDiffList(BaseModel):
    items: list[_SectionDiff] = Field(default_factory=list)


_SYSTEM_PROMPT = (
    "You are a legal analyst comparing two versions of a financial contract. "
    "Identify added clauses, removed clauses, and materially changed clauses. "
    "Flag any changes that increase risk."
)


def compare_contracts(file_path_a: str, file_path_b: str) -> ContractDiff:
    a_sections = extract_text_from_pdf(file_path_a)
    b_sections = extract_text_from_pdf(file_path_b)

    common_names = [name for name in a_sections.keys() if name in b_sections]
    diffs: list[_SectionDiff] = []

    for name in common_names:
        user_prompt = (
            f"Section name: {name}\n\n"
            f"Version A:\n{a_sections[name]}\n\n"
            f"Version B:\n{b_sections[name]}\n\n"
            "Return a JSON object with key 'items' containing a single section diff in a list."
        )
        parsed = call_llm(_SYSTEM_PROMPT, user_prompt, _SectionDiffList)
        if parsed.items:
            diffs.append(parsed.items[0])

    added: list[str] = []
    removed: list[str] = []
    changed: list[dict] = []
    risk_notes: list[str] = []

    for d in diffs:
        added.extend([c for c in d.added_clauses if c])
        removed.extend([c for c in d.removed_clauses if c])
        for ch in d.materially_changed_clauses:
            if isinstance(ch, dict):
                ch.setdefault("section_name", d.section_name)
                changed.append(ch)
        if d.risk_note.strip():
            risk_notes.append(d.risk_note.strip())

    # A lightweight overall risk delta summary, unless the model already supplied one.
    risk_delta = (
        " ".join(risk_notes).strip()
        or "Compared versions across matching sections; review added/removed/changed clauses for risk impact."
    )

    return ContractDiff(
        added_clauses=added,
        removed_clauses=removed,
        materially_changed_clauses=changed,
        risk_delta=risk_delta,
    )

