from __future__ import annotations

from .agent_utils import current_candidate, json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState


def tavily_scorecard_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    payload = json_response(
        load_prompt("tavily_scorecard_evaluation.txt"),
        {
            "startup_name": state["startup_name"],
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "research_summary": state.get("tech_research_summary", ""),
            "research_snippets": state.get("tech_research_snippets", [])[:8],
        },
    )

    team_assessment = {
        "summary": payload.get("team_assessment", {}).get("summary", ""),
        "evidence": string_list(payload.get("team_assessment", {}).get("evidence", [])),
        "risks": string_list(payload.get("team_assessment", {}).get("risks", [])),
        "evidence_gaps": string_list(payload.get("team_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("team_assessment", {}).get("score_1_to_5", 2.5)),
    }
    tech_assessment = {
        "summary": payload.get("tech_assessment", {}).get("summary", ""),
        "trl_level": int(payload.get("tech_assessment", {}).get("trl_level", 3)),
        "trl_basis": payload.get("tech_assessment", {}).get("trl_basis", ""),
        "trl_exit_criteria_met": payload.get("tech_assessment", {}).get("trl_exit_criteria_met", {}),
        "trl_estimate": f"TRL {int(payload.get('tech_assessment', {}).get('trl_level', 3))}",
        "manufacturing_readiness": payload.get("tech_assessment", {}).get("manufacturing_readiness", "insufficient_data"),
        "key_strengths": string_list(payload.get("tech_assessment", {}).get("evidence", [])),
        "key_risks": string_list(payload.get("tech_assessment", {}).get("risks", [])),
        "evidence_gaps": string_list(payload.get("tech_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("tech_assessment", {}).get("score_1_to_5", 2.5)),
    }
    competitor_assessment = {
        "summary": payload.get("competitor_assessment", {}).get("summary", ""),
        "closest_competitors": string_list(payload.get("competitor_assessment", {}).get("closest_competitors", [])),
        "differentiation": string_list(payload.get("competitor_assessment", {}).get("differentiation", [])),
        "moat_signals": string_list(payload.get("competitor_assessment", {}).get("moat_signals", [])),
        "competitive_risks": string_list(payload.get("competitor_assessment", {}).get("competitive_risks", [])),
        "evidence_gaps": string_list(payload.get("competitor_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("competitor_assessment", {}).get("score_1_to_5", 2.5)),
    }
    safety_assessment = {
        "summary": payload.get("safety_assessment", {}).get("summary", ""),
        "certifications": string_list(payload.get("safety_assessment", {}).get("certifications", [])),
        "regulation_status": payload.get("safety_assessment", {}).get("regulation_status", "insufficient_data"),
        "compliance_risks": string_list(payload.get("safety_assessment", {}).get("compliance_risks", [])),
        "evidence_gaps": string_list(payload.get("safety_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("safety_assessment", {}).get("score_1_to_5", 2.5)),
    }

    return {
        "team_assessment": team_assessment,
        "trl_level": tech_assessment["trl_level"],
        "tech_assessment": tech_assessment,
        "tech_summary": tech_assessment["summary"],
        "competitor_assessment": competitor_assessment,
        "competitor_analysis": competitor_assessment["summary"],
        "safety_assessment": safety_assessment,
    }
