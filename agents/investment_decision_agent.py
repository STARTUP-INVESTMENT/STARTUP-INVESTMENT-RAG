from __future__ import annotations

from typing import Any

from .agent_utils import current_candidate
from .state import InvestmentState


INVESTMENT_THRESHOLD = 3.5
SCORE_WEIGHTS = {
    "team_founders": 0.20,
    "market_opportunity": 0.20,
    "technology_production": 0.30,
    "competition_moat": 0.10,
    "customer_roi_traction": 0.10,
    "safety_regulation": 0.05,
    "business_model": 0.05,
}


def _clamp_score(value: float) -> float:
    return max(1.0, min(5.0, round(value, 2)))


def _team_score(candidate: dict[str, Any]) -> float:
    tags_text = " ".join(candidate.get("tags") or [])
    description = f"{candidate.get('description', '')} {tags_text}".lower()
    team_signals = sum(
        int(keyword in description)
        for keyword in ["ai", "robot", "manufactur", "industrial", "automation", "vision", "autonomous"]
    )
    return _clamp_score(2.0 + 0.3 * min(team_signals, 6))


def _roi_score(candidate: dict[str, Any]) -> float:
    description = candidate.get("description", "").lower()
    signals = sum(
        int(keyword in description)
        for keyword in ["cost", "productivity", "throughput", "automation", "efficiency", "chores", "manufacturing"]
    )
    return _clamp_score(1.8 + 0.35 * min(signals, 6))


def _safety_score(candidate: dict[str, Any]) -> float:
    description = f"{candidate.get('description', '')} {' '.join(candidate.get('tags') or [])}".lower()
    signals = sum(int(keyword in description) for keyword in ["industrial", "manufacturing", "robot", "autonomous", "service"])
    return _clamp_score(1.8 + 0.3 * min(signals, 5))


def _business_model_score(candidate: dict[str, Any]) -> float:
    description = candidate.get("description", "").lower()
    signals = sum(int(keyword in description) for keyword in ["platform", "software", "service", "data", "ai", "operating system"])
    return _clamp_score(2.0 + 0.3 * min(signals, 5))


def _hard_filters(
    tech_assessment: dict[str, Any],
    competitor_assessment: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, bool]:
    trl_level = int(tech_assessment.get("trl_level", 0) or 0)
    manufacturing_readiness = str(tech_assessment.get("manufacturing_readiness", "")).lower()
    description = candidate.get("description", "").lower()
    roi_missing = _roi_score(candidate) <= 2.0
    return {
        "trl_below_7_signal": trl_level == 0 or trl_level < 7,
        "no_manufacturing_plan_signal": "insufficient_data" in manufacturing_readiness or "none" in manufacturing_readiness,
        "no_roi_evidence_signal": roi_missing,
        "weak_moat_signal": competitor_assessment.get("score_1_to_5", 0.0) < 2.0 and "patent" not in description,
    }


def _build_scorecard(state: InvestmentState) -> tuple[dict[str, float], dict[str, bool], float]:
    candidate = current_candidate(state)
    tech = state.get("tech_assessment", {})
    market = state.get("market_assessment", {})
    competitor = state.get("competitor_assessment", {})
    scorecard = {
        "team_founders": _team_score(candidate),
        "market_opportunity": _clamp_score(float(market.get("score_1_to_5", 2.5))),
        "technology_production": _clamp_score(float(tech.get("score_1_to_5", 2.5))),
        "competition_moat": _clamp_score(float(competitor.get("score_1_to_5", 2.5))),
        "customer_roi_traction": _roi_score(candidate),
        "safety_regulation": _safety_score(candidate),
        "business_model": _business_model_score(candidate),
    }
    hard_filter_results = _hard_filters(tech, competitor, candidate)
    final_score = round(sum(scorecard[key] * SCORE_WEIGHTS[key] for key in SCORE_WEIGHTS), 2)
    return scorecard, hard_filter_results, final_score


def investment_decision_node(state: InvestmentState) -> InvestmentState:
    scorecard, hard_filter_results, final_score = _build_scorecard(state)
    hard_filter_triggered = any(hard_filter_results.values())
    decision = "hold" if hard_filter_triggered or final_score < INVESTMENT_THRESHOLD else "invest"
    candidate = current_candidate(state)
    decision_reason = (
        f"{candidate.get('name', state['startup_name'])}의 최종 점수는 {final_score}점이다. "
        f"기술/양산 점수 {scorecard['technology_production']}, 시장 점수 {scorecard['market_opportunity']}, "
        f"경쟁 해자 점수 {scorecard['competition_moat']}를 반영했다. "
        f"Hard Filter 결과는 {hard_filter_results}이며 최종 판단은 {decision}이다."
    )
    return {
        "scorecard": scorecard,
        "hard_filter_results": hard_filter_results,
        "final_score": final_score,
        "investment_decision": decision,
        "decision_reason": decision_reason,
    }
