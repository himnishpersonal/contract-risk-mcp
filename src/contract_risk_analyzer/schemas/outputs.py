from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClauseExtraction(BaseModel):
    section_name: str
    clause_type: str
    raw_text: str
    plain_english: str
    page_references: list[int] = Field(default_factory=list)


class RiskTerm(BaseModel):
    term: str
    context: str
    risk_explanation: str
    severity: Literal["low", "medium", "high"]
    page_reference: int


class ObligationSummary(BaseModel):
    party: str
    obligations: list[str] = Field(default_factory=list)
    key_deadlines: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


class ContractDiff(BaseModel):
    added_clauses: list[str] = Field(default_factory=list)
    removed_clauses: list[str] = Field(default_factory=list)
    materially_changed_clauses: list[dict] = Field(default_factory=list)
    risk_delta: str


class RiskBrief(BaseModel):
    contract_name: str
    high_risk_terms: list[RiskTerm] = Field(default_factory=list)
    obligations: list[ObligationSummary] = Field(default_factory=list)
    overall_risk_score: Literal["low", "medium", "high"]
    summary: str


# ---- Wrapper schemas for structured list outputs ----


class ClauseExtractionList(BaseModel):
    items: list[ClauseExtraction] = Field(default_factory=list)


class RiskTermList(BaseModel):
    items: list[RiskTerm] = Field(default_factory=list)


class ObligationSummaryList(BaseModel):
    items: list[ObligationSummary] = Field(default_factory=list)

