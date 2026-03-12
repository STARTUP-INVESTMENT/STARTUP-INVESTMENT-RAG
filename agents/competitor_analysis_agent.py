from __future__ import annotations

from .agent_utils import current_candidate, json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState


def competitor_analysis_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    peer_candidates = [item for item in state.get("startup_candidates", []) if item["name"] != state["startup_name"]][:8]
    payload = json_response(
        load_prompt("competitor_analysis.txt"),
        {
            "startup_name": state["startup_name"],
            "startup_basic_info": candidate,
            "peer_candidates": peer_candidates,
        },
    )
    assessment = {
        "summary": payload.get("summary", ""),
        "closest_competitors": string_list(payload.get("closest_competitors", [])),
        "differentiation": string_list(payload.get("differentiation", [])),
        "moat_signals": string_list(payload.get("moat_signals", [])),
        "competitive_risks": string_list(payload.get("competitive_risks", [])),
        "evidence_gaps": string_list(payload.get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("score_1_to_5", 2.5)),
    }
    summary = (
        f"경쟁 분석: {assessment['summary']} "
        f"근접 경쟁사: {', '.join(assessment['closest_competitors'][:3]) or 'insufficient_data'}. "
        f"차별화: {', '.join(assessment['differentiation'][:3]) or 'insufficient_data'}."
    )
    return {"competitor_assessment": assessment, "competitor_analysis": summary}
