from __future__ import annotations

from core.state import InvestmentState
import time

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


def _score(value: object, default: float = 2.5) -> float:
    try:
        return _clamp_score(float(value))
    except (TypeError, ValueError):
        return default


def investment_decision_node(state: InvestmentState) -> InvestmentState:
    start = time.time()
    print(f"Starting investment decision for {state.get('startup_name', '')}...")
    team = state.get("team_assessment", {})
    market = state.get("market_assessment", {})
    tech = state.get("tech_assessment", {})
    competition = state.get("competitor_assessment", {})
    roi = state.get("roi_traction_assessment", {})
    safety = state.get("safety_assessment", {})
    business = state.get("business_model_assessment", {})

    scorecard = {
        "team_founders": _score(team.get("score_1_to_5")),
        "market_opportunity": _score(market.get("score_1_to_5")),
        "technology_production": _score(tech.get("score_1_to_5")),
        "competition_moat": _score(competition.get("score_1_to_5")),
        "customer_roi_traction": _score(roi.get("score_1_to_5")),
        "safety_regulation": _score(safety.get("score_1_to_5")),
        "business_model": _score(business.get("score_1_to_5")),
    }
    final_score = round(sum(scorecard[key] * SCORE_WEIGHTS[key] for key in SCORE_WEIGHTS), 2)
    decision = "hold" if final_score < INVESTMENT_THRESHOLD else "invest"
    decision_reason = (
        f"{state.get('startup_name', '')}의 최종 점수는 {final_score}점이다. "
        f"팀 {scorecard['team_founders']}, 시장 {scorecard['market_opportunity']}, 기술/양산 {scorecard['technology_production']}, "
        f"경쟁 {scorecard['competition_moat']}, ROI/트랙션 {scorecard['customer_roi_traction']}, "
        f"안전/규제 {scorecard['safety_regulation']}, 수익모델 {scorecard['business_model']}를 반영했다. "
        f"기존 scorecard 가중치 기준으로 최종 판단은 {'투자 추천' if decision == 'invest' else '관심 보류'}다."
    )

    end = time.time()
    print(f"Investment decision for {state.get('startup_name', '')} completed in {end - start:.2f} seconds")
    
    return {
        "scorecard": scorecard,
        "final_score": final_score,
        "investment_decision": decision,
        "decision_reason": decision_reason,
    }
