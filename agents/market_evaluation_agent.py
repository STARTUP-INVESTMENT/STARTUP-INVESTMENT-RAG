from __future__ import annotations

from typing import Any

from core.agent_utils import current_candidate, json_response, string_list
from core.prompt_loader import load_prompt
from core.state import InvestmentState
from infra.market_vectorstore import load_or_build_vectorstore, retrieve_relevant_context
from infra.research_utils import save_research_cache, snippet, source_rows, summarize_research, tavily_search_results, unique_sources
import time

def _build_market_query(state: InvestmentState, candidate: dict[str, Any]) -> str:
    sector = candidate.get("sector", "")
    tags = " ".join(str(t) for t in (candidate.get("tags") or []) if t)
    description = str(candidate.get("description", ""))[:200]
    user_query = state.get("user_query", "")
    return " ".join(part for part in [sector, tags, description, user_query] if part)


MARKET_SEARCH_PATTERNS = (
    ("market", "{name} robotics market opportunity"),
    ("funding", "{name} funding"),
    ("roi", "{name} ROI case study"),
    ("business_model", "{name} pricing robot as a service"),
)


def _tavily_market_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    name = str(candidate.get("name", "")).strip()
    homepage = str(candidate.get("url", "")).strip() or "https://tavily.com"
    snippets: list[dict[str, Any]] = []
    for category, pattern in MARKET_SEARCH_PATTERNS:
        query = pattern.format(name=name)
        try:
            results = tavily_search_results(query)
        except Exception as exc:
            snippets.append(
                snippet(
                    title=f"{name} {category} Tavily search failed",
                    url=homepage,
                    excerpt=f"query={query}\nTavily search failed: {exc}",
                    source_type=f"tavily_search_error:{category}",
                )
            )
            continue
        for result in results:
            snippets.append(
                snippet(
                    title=result["title"] or f"{name} {category} search result",
                    url=result["url"],
                    excerpt=f"query={query}\n{result['description']}",
                    source_type=f"tavily_search:{category}",
                )
            )
    return unique_sources(snippets)


def market_evaluation_node(state: InvestmentState) -> InvestmentState:
    start = time.time()
    print("Starting market evaluation...")
    candidate = current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    research_snippets = _tavily_market_sources(candidate)
    research_cache_path = save_research_cache(startup_name, "market_research", research_snippets)

    vectorstore = load_or_build_vectorstore()
    market_context = ""
    if vectorstore is not None:
        query = _build_market_query(state, candidate)
        market_context = retrieve_relevant_context(vectorstore, query, k=6)

    payload = json_response(
        load_prompt("market_evaluation.txt"),
        {
            "startup_name": startup_name,
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "research_summary": summarize_research(startup_name, "시장", research_snippets),
            "research_snippets": research_snippets[:8],
            "domain_context": "Robotics market with focus on labor shortage, automation, AI-robotics convergence, and ROI sensitivity.",
            "market_context": market_context,
        },
    )
    market_assessment = {
        "summary": payload.get("market_assessment", {}).get("summary", ""),
        "target_market": payload.get("market_assessment", {}).get("target_market", ""),
        "demand_drivers": string_list(payload.get("market_assessment", {}).get("demand_drivers", [])),
        "market_maturity": payload.get("market_assessment", {}).get("market_maturity", "insufficient_data"),
        "estimate_range": payload.get("market_assessment", {}).get("estimate_range", "insufficient_data"),
        "evidence_gaps": string_list(payload.get("market_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("market_assessment", {}).get("score_1_to_5", 2.5)),
    }
    roi_traction_assessment = {
        "summary": payload.get("roi_traction_assessment", {}).get("summary", ""),
        "roi_signals": string_list(payload.get("roi_traction_assessment", {}).get("roi_signals", [])),
        "traction_signals": string_list(payload.get("roi_traction_assessment", {}).get("traction_signals", [])),
        "evidence_gaps": string_list(payload.get("roi_traction_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("roi_traction_assessment", {}).get("score_1_to_5", 2.5)),
    }
    business_model_assessment = {
        "summary": payload.get("business_model_assessment", {}).get("summary", ""),
        "revenue_model": payload.get("business_model_assessment", {}).get("revenue_model", "insufficient_data"),
        "recurring_revenue_signals": string_list(
            payload.get("business_model_assessment", {}).get("recurring_revenue_signals", [])
        ),
        "risks": string_list(payload.get("business_model_assessment", {}).get("risks", [])),
        "evidence_gaps": string_list(payload.get("business_model_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("business_model_assessment", {}).get("score_1_to_5", 2.5)),
    }
    summary = (
        f"시장 평가: {market_assessment['summary']} "
        f"ROI/트랙션: {roi_traction_assessment['summary']} "
        f"수익모델: {business_model_assessment['summary']}"
    )

    end = time.time()
    print(f"Market evaluation for {startup_name} completed in {end - start:.2f} seconds")

    return {
        "market_research_cache_path": str(research_cache_path),
        "market_research_summary": summarize_research(startup_name, "시장", research_snippets),
        "market_research_sources": source_rows(research_snippets),
        "market_research_snippets": research_snippets,
        "market_context": market_context,
        "market_assessment": market_assessment,
        "roi_traction_assessment": roi_traction_assessment,
        "business_model_assessment": business_model_assessment,
        "market_evaluation": summary,
    }
