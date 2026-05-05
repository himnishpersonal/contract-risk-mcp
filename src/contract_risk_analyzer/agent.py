from __future__ import annotations

import os
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from contract_risk_analyzer.schemas.outputs import (
    ClauseExtraction,
    ObligationSummary,
    RiskBrief,
    RiskTerm,
)
from contract_risk_analyzer.tools.extract_clauses import extract_clauses
from contract_risk_analyzer.tools.flag_risk_terms import flag_risk_terms
from contract_risk_analyzer.tools.summarize_obligations import summarize_obligations
from contract_risk_analyzer.utils.llm_client import call_llm


def _merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])


class RiskState(TypedDict, total=False):
    file_path: str
    contract_name: str
    clauses: Annotated[list[ClauseExtraction], _merge_lists]
    risk_terms: list[RiskTerm]
    obligations: list[ObligationSummary]
    brief: RiskBrief


def _contract_name_from_path(path: str) -> str:
    base = os.path.basename(path)
    return base or "Contract"


async def _termination_node(state: RiskState) -> RiskState:
    clauses = await extract_clauses(state["file_path"], "termination events")
    return {"clauses": clauses}


async def _default_node(state: RiskState) -> RiskState:
    clauses = await extract_clauses(state["file_path"], "event of default")
    return {"clauses": clauses}


async def _collateral_node(state: RiskState) -> RiskState:
    clauses = await extract_clauses(state["file_path"], "collateral")
    return {"clauses": clauses}


def _flag_node(state: RiskState) -> RiskState:
    return {"risk_terms": flag_risk_terms(state["file_path"])}


def _obligations_node(state: RiskState) -> RiskState:
    return {"obligations": summarize_obligations(state["file_path"])}


def _synthesize_node(state: RiskState) -> RiskState:
    system_prompt = (
        "You are a senior legal analyst. Produce a concise, plain-English risk brief "
        "with an overall risk score. Be specific about what drives the score."
    )
    user_prompt = (
        f"Contract name: {state.get('contract_name')}\n\n"
        f"Extracted clauses (selected types):\n{state.get('clauses')}\n\n"
        f"Flagged risk terms:\n{state.get('risk_terms')}\n\n"
        f"Obligations:\n{state.get('obligations')}\n\n"
        "Return a RiskBrief."
    )
    brief = call_llm(system_prompt, user_prompt, RiskBrief)
    return {"brief": brief}


def _build_graph() -> StateGraph:
    g: StateGraph = StateGraph(RiskState)

    # Parallel extraction branches
    g.add_node("termination_node", _termination_node)
    g.add_node("default_node", _default_node)
    g.add_node("collateral_node", _collateral_node)

    # Join after the three extraction nodes
    g.add_node("flag_node", _flag_node)
    g.add_node("obligations_node", _obligations_node)
    g.add_node("synthesize_node", _synthesize_node)

    g.add_edge(START, "termination_node")
    g.add_edge(START, "default_node")
    g.add_edge(START, "collateral_node")

    # Fan-in: all three must complete before flagging
    g.add_edge("termination_node", "flag_node")
    g.add_edge("default_node", "flag_node")
    g.add_edge("collateral_node", "flag_node")

    g.add_edge("flag_node", "obligations_node")
    g.add_edge("obligations_node", "synthesize_node")
    g.add_edge("synthesize_node", END)

    return g


_APP = _build_graph().compile()


async def analyze_contract(file_path: str) -> RiskBrief:
    state: RiskState = {
        "file_path": file_path,
        "contract_name": _contract_name_from_path(file_path),
        "clauses": [],
    }
    out = await _APP.ainvoke(state)
    return out["brief"]

