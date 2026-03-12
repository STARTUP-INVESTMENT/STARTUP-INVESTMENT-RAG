from __future__ import annotations

from typing import Any, Literal, TypedDict


Decision = Literal["invest", "hold"]


class InvestmentState(TypedDict, total=False):
    user_query: str
    search_keywords: list[str]
    startup_name: str
    startup_list: list[str]
    evaluated_startups: list[str]
    startup_basic_info: dict[str, Any]
    startup_candidates: list[dict[str, Any]]
    startup_search_summary: str
    startup_search_corpus_path: str
    startup_search_vectorstore_path: str
    tech_summary: str
    market_evaluation: str
    competitor_analysis: str
    scorecard: dict[str, float]
    final_score: float
    investment_decision: Decision
    decision_reason: str
    report_content: str
    report_history: list[dict[str, Any]]
    rag_sources: list[str]
