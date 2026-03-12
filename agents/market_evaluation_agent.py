from __future__ import annotations

from .agent_utils import current_candidate, json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState


def market_evaluation_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    payload = json_response(
        load_prompt("market_evaluation.txt"),
        {
            "startup_name": state["startup_name"],
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "domain_context": "Robotics market with focus on labor shortage, automation, AI-robotics convergence, and ROI sensitivity.",
        },
    )
    assessment = {
        "summary": payload.get("summary", ""),
        "target_market": payload.get("target_market", ""),
        "demand_drivers": string_list(payload.get("demand_drivers", [])),
        "market_maturity": payload.get("market_maturity", "insufficient_data"),
        "estimate_range": payload.get("estimate_range", "insufficient_data"),
        "evidence_gaps": string_list(payload.get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("score_1_to_5", 2.5)),
    }
    summary = (
        f"시장 평가: {assessment['summary']} "
        f"타깃 시장: {assessment['target_market'] or 'insufficient_data'}. "
        f"수요 동인: {', '.join(assessment['demand_drivers'][:3]) or 'insufficient_data'}."
    )
    return {"market_assessment": assessment, "market_evaluation": summary}
