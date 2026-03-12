from __future__ import annotations

from .state import InvestmentState


SCORECARD_LABELS = {
    "team_founders": "팀 & 창업자",
    "market_opportunity": "시장 기회",
    "technology_production": "기술력 & 양산 가능성",
    "competition_moat": "경쟁 환경",
    "customer_roi_traction": "고객 ROI & 트랙션",
    "safety_regulation": "안전 인증 & 규제",
    "business_model": "수익 모델 지속성",
}


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- 없음"]


def _scorecard_lines(scorecard: dict[str, float]) -> list[str]:
    weights = {
        "team_founders": "20%",
        "market_opportunity": "20%",
        "technology_production": "30%",
        "competition_moat": "10%",
        "customer_roi_traction": "10%",
        "safety_regulation": "5%",
        "business_model": "5%",
    }
    lines = ["| 항목 | 점수 | 가중치 |", "| --- | --- | --- |"]
    for key, label in SCORECARD_LABELS.items():
        lines.append(f"| {label} | {scorecard.get(key, '')} | {weights[key]} |")
    return lines


def _hard_filter_lines(hard_filter_results: dict[str, bool]) -> list[str]:
    return [f"- {key}: {'예' if value else '아니오'}" for key, value in hard_filter_results.items()]


def _assessment_section(title: str, assessment: dict[str, object], extra: list[str] | None = None) -> list[str]:
    lines = [f"## {title}", str(assessment.get("summary", ""))]
    if extra:
        lines.extend(extra)
    evidence = assessment.get("evidence") or assessment.get("key_strengths") or assessment.get("demand_drivers") or assessment.get("roi_signals") or assessment.get("recurring_revenue_signals") or assessment.get("differentiation") or assessment.get("certifications") or []
    risks = assessment.get("risks") or assessment.get("key_risks") or assessment.get("competitive_risks") or assessment.get("compliance_risks") or []
    gaps = assessment.get("evidence_gaps") or []
    lines.append("")
    lines.append("핵심 근거")
    lines.extend(_bullet_lines([str(item) for item in evidence]))
    lines.append("")
    lines.append("주요 리스크")
    lines.extend(_bullet_lines([str(item) for item in risks]))
    lines.append("")
    lines.append("추가 확인 필요")
    lines.extend(_bullet_lines([str(item) for item in gaps]))
    return lines


def _research_source_lines(title: str, research_sources: list[dict[str, object]]) -> list[str]:
    lines = [title]
    if not research_sources:
        lines.append("- 없음")
        return lines
    for source in research_sources[:8]:
        lines.append(f"- [{source.get('source_type', '')}] {source.get('title', '')} ({source.get('url', '')})")
    return lines


def report_writer_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    team = state.get("team_assessment", {})
    market = state.get("market_assessment", {})
    tech = state.get("tech_assessment", {})
    competition = state.get("competitor_assessment", {})
    roi = state.get("roi_traction_assessment", {})
    safety = state.get("safety_assessment", {})
    business = state.get("business_model_assessment", {})
    scorecard = state.get("scorecard", {})
    hard_filter_results = state.get("hard_filter_results", {})

    company_report = "\n".join(
        [
            f"# Robotics Investment Memo: {startup_name}",
            "",
            "## Summary",
            f"- 투자 판단: {state.get('investment_decision', 'hold')}",
            f"- 최종 점수: {state.get('final_score', 0.0)} / 5.0",
            f"- 판단 근거: {state.get('decision_reason', '')}",
            "",
            *_assessment_section("팀 & 창업자", team),
            "",
            *_assessment_section(
                "기술력 & 양산 가능성",
                tech,
                [
                    f"- TRL 추정: {tech.get('trl_estimate', '')}",
                    f"- TRL 판단 근거: {tech.get('trl_basis', '')}",
                    f"- 양산 준비도: {tech.get('manufacturing_readiness', '')}",
                ],
            ),
            "",
            *_assessment_section(
                "시장 기회",
                market,
                [
                    f"- 타깃 시장: {market.get('target_market', '')}",
                    f"- 시장 성숙도: {market.get('market_maturity', '')}",
                    f"- 시장 추정 범위: {market.get('estimate_range', '')}",
                ],
            ),
            "",
            *_assessment_section(
                "경쟁 환경",
                competition,
                [f"- 근접 경쟁사: {', '.join(competition.get('closest_competitors', [])[:5])}"],
            ),
            "",
            *_assessment_section(
                "고객 ROI & 트랙션",
                {
                    "summary": roi.get("summary", ""),
                    "evidence": [*roi.get("roi_signals", []), *roi.get("traction_signals", [])],
                    "risks": [],
                    "evidence_gaps": roi.get("evidence_gaps", []),
                },
            ),
            "",
            *_assessment_section(
                "안전 인증 & 규제",
                {
                    "summary": safety.get("summary", ""),
                    "evidence": safety.get("certifications", []),
                    "risks": safety.get("compliance_risks", []),
                    "evidence_gaps": safety.get("evidence_gaps", []),
                },
                [f"- 규제 상태: {safety.get('regulation_status', '')}"],
            ),
            "",
            *_assessment_section(
                "수익 모델 지속성",
                {
                    "summary": business.get("summary", ""),
                    "evidence": business.get("recurring_revenue_signals", []),
                    "risks": business.get("risks", []),
                    "evidence_gaps": business.get("evidence_gaps", []),
                },
                [f"- 수익 모델: {business.get('revenue_model', '')}"],
            ),
            "",
            "## 스코어카드",
            *_scorecard_lines(scorecard),
            "",
            "## Hard Filter",
            *_hard_filter_lines(hard_filter_results),
            "",
            "## 수집 근거",
            *_research_source_lines("기술 근거", state.get("tech_research_sources", [])),
            "",
            *_research_source_lines("시장 근거", state.get("market_research_sources", [])),
        ]
    )

    report_history = [*state.get("report_history", [])]
    report_history.append(
        {
            "startup_name": startup_name,
            "decision": state.get("investment_decision", "hold"),
            "final_score": state.get("final_score", 0.0),
            "summary": state.get("decision_reason", ""),
            "scorecard": scorecard,
            "hard_filter_results": hard_filter_results,
            "report_content": company_report,
        }
    )
    summary_lines = [
        "# Robotics Evaluation Summary",
        "",
        "| Startup | Decision | Final Score | Key Reason |",
        "| --- | --- | --- | --- |",
    ]
    for item in report_history:
        summary_lines.append(
            f"| {item['startup_name']} | {item['decision']} | {item['final_score']} | {item['summary']} |"
        )
    return {
        "report_content": "\n".join(summary_lines),
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), startup_name],
    }
