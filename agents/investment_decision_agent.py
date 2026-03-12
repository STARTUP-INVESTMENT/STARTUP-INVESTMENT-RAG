from __future__ import annotations

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
HARD_FILTER_LABELS = {
    "trl_below_7_signal": "TRL 7 미만 또는 기술 검증 근거 부족",
    "no_manufacturing_plan_signal": "양산 계획 또는 제조 파트너 근거 부족",
    "no_roi_evidence_signal": "고객 ROI 정량 근거 부족",
    "weak_moat_signal": "기술 해자 약함",
    "no_safety_plan_signal": "안전 인증 또는 규제 대응 계획 부족",
}


def _clamp_score(value: float) -> float:
    return max(1.0, min(5.0, round(value, 2)))


def _score(value: object, default: float = 2.5) -> float:
    try:
        return _clamp_score(float(value))
    except (TypeError, ValueError):
        return default


def _hard_filters(state: InvestmentState) -> dict[str, bool]:
    tech = state.get("tech_assessment", {})
    roi = state.get("roi_traction_assessment", {})
    safety = state.get("safety_assessment", {})
    trl_level = int(tech.get("trl_level", 0) or 0)
    manufacturing_readiness = str(tech.get("manufacturing_readiness", "insufficient_data")).lower()
    roi_score = _score(roi.get("score_1_to_5", 0), 0.0)
    safety_status = str(safety.get("regulation_status", "insufficient_data")).lower()
    return {
        "trl_below_7_signal": trl_level == 0 or trl_level < 7,
        "no_manufacturing_plan_signal": "insufficient" in manufacturing_readiness or "none" in manufacturing_readiness,
        "no_roi_evidence_signal": roi_score <= 2.0,
        "weak_moat_signal": _score(state.get("competitor_assessment", {}).get("score_1_to_5", 0), 0.0) <= 2.0,
        "no_safety_plan_signal": "insufficient" in safety_status or "none" in safety_status or "unknown" in safety_status,
    }


def _hard_filter_summary(hard_filter_results: dict[str, bool]) -> str:
    triggered = [label for key, label in HARD_FILTER_LABELS.items() if hard_filter_results.get(key, False)]
    clear = [label for key, label in HARD_FILTER_LABELS.items() if not hard_filter_results.get(key, False)]
    if triggered:
        return (
            "Hard Filter에서 "
            + ", ".join(triggered)
            + " 항목이 경고로 확인되었다. "
            + "반면 "
            + (", ".join(clear) if clear else "나머지 항목")
            + " 항목은 특이사항이 없었다."
        )
    return "Hard Filter에서는 유의미한 경고 항목이 확인되지 않았다."


def investment_decision_node(state: InvestmentState) -> InvestmentState:
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
    hard_filter_results = _hard_filters(state)
    decision = "hold" if any(hard_filter_results.values()) or final_score < INVESTMENT_THRESHOLD else "invest"
    decision_reason = (
        f"{state.get('startup_name', '')}의 최종 점수는 {final_score}점이다. "
        f"팀 {scorecard['team_founders']}, 시장 {scorecard['market_opportunity']}, 기술/양산 {scorecard['technology_production']}, "
        f"경쟁 {scorecard['competition_moat']}, ROI/트랙션 {scorecard['customer_roi_traction']}, "
        f"안전/규제 {scorecard['safety_regulation']}, 수익모델 {scorecard['business_model']}를 반영했다. "
        f"{_hard_filter_summary(hard_filter_results)} "
        f"최종 판단은 {'투자 추천' if decision == 'invest' else '관심 보류'}다."
    )
    return {
        "scorecard": scorecard,
        "hard_filter_results": hard_filter_results,
        "final_score": final_score,
        "investment_decision": decision,
        "decision_reason": decision_reason,
    }
