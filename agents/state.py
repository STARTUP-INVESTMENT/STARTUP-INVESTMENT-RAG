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
    research_cache_path: str
    research_summary: str
    research_sources: list[dict[str, Any]]
    research_snippets: list[dict[str, Any]]
    trl_level: int
    tech_summary: str
    tech_assessment: dict[str, Any]
    market_evaluation: str
    market_assessment: dict[str, Any]
    competitor_analysis: str
    competitor_assessment: dict[str, Any]
    scorecard: dict[str, float]
    hard_filter_results: dict[str, bool]
    final_score: float
    investment_decision: Decision
    decision_reason: str
    report_content: str
    report_history: list[dict[str, Any]]
    rag_sources: list[str]
