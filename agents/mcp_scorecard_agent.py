from __future__ import annotations

from .agent_utils import current_candidate, json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState


def mcp_scorecard_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    payload = json_response(
        load_prompt("mcp_scorecard_evaluation.txt"),
        {
            "startup_name": state["startup_name"],
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "research_summary": state.get("market_research_summary", ""),
            "research_snippets": state.get("market_research_snippets", [])[:8],
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

    return {
        "market_assessment": market_assessment,
        "market_evaluation": market_assessment["summary"],
        "roi_traction_assessment": roi_traction_assessment,
        "business_model_assessment": business_model_assessment,
    }
