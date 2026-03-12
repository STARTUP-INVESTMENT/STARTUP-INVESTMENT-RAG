from __future__ import annotations

from .agent_utils import json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState


SCORECARD_LABELS = {
    "team_founders": "팀 & 창업자",
    "market_opportunity": "시장 기회",
    "technology_production": "기술력 & 양산 가능성",
    "competition_moat": "경쟁 환경 & 기술 해자",
    "customer_roi_traction": "고객 ROI & 트랙션",
    "safety_regulation": "안전 인증 & 규제",
    "business_model": "수익 모델 지속성",
}

HARD_FILTER_LABELS = {
    "trl_below_7_signal": "TRL 7 미만 또는 근거 부족",
    "no_manufacturing_plan_signal": "양산 계획 또는 제조 파트너 근거 부족",
    "no_roi_evidence_signal": "고객 ROI 정량 근거 부족",
    "weak_moat_signal": "기술 해자 약함",
}


def _bullet_lines(items: list[str]) -> list[str]:
    if not items:
        return ["- 없음"]
    return [f"- {item}" for item in items]


def _as_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if value is None:
        return ""
    return str(value)


def _company_overview_lines(startup_basic_info: dict[str, object]) -> list[str]:
    tags = startup_basic_info.get("tags") or []
    if isinstance(tags, list):
        tags_text = ", ".join(str(tag) for tag in tags if tag)
    else:
        tags_text = str(tags)
    return [
        f"- 회사명: {startup_basic_info.get('name', '')}",
        f"- 출처: {startup_basic_info.get('source', '')}",
        f"- URL: {startup_basic_info.get('url', '')}",
        f"- 설명: {startup_basic_info.get('description', '')}",
        f"- 위치: {startup_basic_info.get('location', '')}",
        f"- 섹터: {startup_basic_info.get('sector', '')}",
        f"- 단계: {startup_basic_info.get('stage', '')}",
        f"- 태그: {tags_text}",
    ]


def _scorecard_lines(scorecard: dict[str, object]) -> list[str]:
    lines = [
        "| 항목 | 점수 | 가중치 |",
        "| --- | --- | --- |",
    ]
    weights = {
        "team_founders": "20%",
        "market_opportunity": "20%",
        "technology_production": "30%",
        "competition_moat": "10%",
        "customer_roi_traction": "10%",
        "safety_regulation": "5%",
        "business_model": "5%",
    }
    for key, label in SCORECARD_LABELS.items():
        lines.append(f"| {label} | {scorecard.get(key, '')} | {weights[key]} |")
    return lines


def _hard_filter_lines(hard_filter_results: dict[str, bool]) -> list[str]:
    lines = []
    for key, label in HARD_FILTER_LABELS.items():
        triggered = bool(hard_filter_results.get(key, False))
        lines.append(f"- {label}: {'예' if triggered else '아니오'}")
    return lines


def _analysis_section(title: str, summary: str, assessment: dict[str, object]) -> list[str]:
    lines = [f"## {title}", summary]
    strengths = assessment.get("key_strengths") or assessment.get("demand_drivers") or assessment.get("differentiation") or []
    risks = assessment.get("key_risks") or assessment.get("competitive_risks") or []
    gaps = assessment.get("evidence_gaps") or []

    if title == "기술 분석":
        lines.extend(
            [
                f"- TRL 추정: {assessment.get('trl_estimate', '')}",
                f"- TRL 판단 근거: {assessment.get('trl_basis', '')}",
                f"- 양산 준비도: {assessment.get('manufacturing_readiness', '')}",
            ]
        )
        criteria = assessment.get("trl_exit_criteria_met") or {}
        if isinstance(criteria, dict) and criteria:
            lines.append("- TRL 기준 충족:")
            for key, value in criteria.items():
                lines.append(f"  - {key}: {'예' if value else '아니오'}")
    if title == "시장 분석":
        lines.extend(
            [
                f"- 타깃 시장: {assessment.get('target_market', '')}",
                f"- 시장 성숙도: {assessment.get('market_maturity', '')}",
                f"- 시장 추정 범위: {assessment.get('estimate_range', '')}",
            ]
        )
    if title == "경쟁 분석":
        closest = assessment.get("closest_competitors") or []
        if isinstance(closest, list):
            lines.append(f"- 근접 경쟁사: {', '.join(str(item) for item in closest[:5])}")

    lines.append("")
    lines.append("핵심 포인트")
    lines.extend(_bullet_lines([str(item) for item in strengths]))
    lines.append("")
    lines.append("주요 리스크")
    lines.extend(_bullet_lines([str(item) for item in risks]))
    lines.append("")
    lines.append("추가 확인 필요")
    lines.extend(_bullet_lines([str(item) for item in gaps]))
    return lines


def _research_source_lines(research_sources: list[dict[str, object]]) -> list[str]:
    if not research_sources:
        return ["- 추가 수집 근거 없음"]
    lines: list[str] = []
    for source in research_sources[:8]:
        lines.append(
            f"- [{source.get('source_type', '')}] {source.get('title', '')} ({source.get('url', '')})"
        )
    return lines


def _localized_report_fields(state: InvestmentState) -> dict[str, object]:
    startup_basic_info = state.get("startup_basic_info", {})
    tech_assessment = state.get("tech_assessment", {})
    market_assessment = state.get("market_assessment", {})
    competitor_assessment = state.get("competitor_assessment", {})
    payload = json_response(
        load_prompt("report_writer_ko.txt"),
        {
            "startup_name": state.get("startup_name", ""),
            "investment_decision": state.get("investment_decision", "hold"),
            "final_score": state.get("final_score", 0.0),
            "decision_reason": state.get("decision_reason", ""),
            "startup_basic_info": startup_basic_info,
            "tech_summary": state.get("tech_summary", ""),
            "tech_assessment": tech_assessment,
            "market_evaluation": state.get("market_evaluation", ""),
            "market_assessment": market_assessment,
            "competitor_analysis": state.get("competitor_analysis", ""),
            "competitor_assessment": competitor_assessment,
        },
    )
    return {
        "decision_label_ko": _as_text(payload.get("decision_label_ko", state.get("investment_decision", "hold"))),
        "decision_reason_ko": _as_text(payload.get("decision_reason_ko", state.get("decision_reason", ""))),
        "company_overview_lines": string_list(payload.get("company_overview_lines", [])),
        "tech_summary_ko": _as_text(payload.get("tech_summary_ko", state.get("tech_summary", ""))),
        "tech_trl_ko": _as_text(payload.get("tech_trl_ko", tech_assessment.get("trl_estimate", ""))),
        "tech_manufacturing_readiness_ko": _as_text(
            payload.get("tech_manufacturing_readiness_ko", tech_assessment.get("manufacturing_readiness", ""))
        ),
        "tech_key_points_ko": string_list(payload.get("tech_key_points_ko", [])),
        "tech_risks_ko": string_list(payload.get("tech_risks_ko", [])),
        "tech_gaps_ko": string_list(payload.get("tech_gaps_ko", [])),
        "market_summary_ko": _as_text(payload.get("market_summary_ko", state.get("market_evaluation", ""))),
        "market_target_ko": _as_text(payload.get("market_target_ko", market_assessment.get("target_market", ""))),
        "market_maturity_ko": _as_text(payload.get("market_maturity_ko", market_assessment.get("market_maturity", ""))),
        "market_estimate_range_ko": _as_text(
            payload.get("market_estimate_range_ko", market_assessment.get("estimate_range", ""))
        ),
        "market_key_points_ko": string_list(payload.get("market_key_points_ko", [])),
        "market_risks_ko": string_list(payload.get("market_risks_ko", [])),
        "market_gaps_ko": string_list(payload.get("market_gaps_ko", [])),
        "competitor_summary_ko": _as_text(payload.get("competitor_summary_ko", state.get("competitor_analysis", ""))),
        "competitor_closest_ko": string_list(payload.get("competitor_closest_ko", competitor_assessment.get("closest_competitors", []))),
        "competitor_key_points_ko": string_list(payload.get("competitor_key_points_ko", [])),
        "competitor_risks_ko": string_list(payload.get("competitor_risks_ko", [])),
        "competitor_gaps_ko": string_list(payload.get("competitor_gaps_ko", [])),
        "summary_reason_short_ko": _as_text(payload.get("summary_reason_short_ko", state.get("decision_reason", ""))),
    }


def report_writer_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    startup_basic_info = state.get("startup_basic_info", {})
    scorecard = state.get("scorecard", {})
    hard_filter_results = state.get("hard_filter_results", {})
    localized = _localized_report_fields(state)
    research_sources = state.get("research_sources", [])
    company_report = "\n".join(
        [
            f"# Robotics Investment Memo: {startup_name}",
            "",
            "## Summary",
            f"- 투자 판단: {localized['decision_label_ko']}",
            f"- 최종 점수: {state.get('final_score', 0.0)} / 5.0",
            f"- 판단 근거: {localized['decision_reason_ko']}",
            "",
            "## 기업 개요",
            *(
                _bullet_lines(localized["company_overview_lines"])
                if localized["company_overview_lines"]
                else _company_overview_lines(startup_basic_info)
            ),
            "",
            *_analysis_section("기술 분석", localized["tech_summary_ko"], {
                **state.get("tech_assessment", {}),
                "trl_estimate": localized["tech_trl_ko"],
                "manufacturing_readiness": localized["tech_manufacturing_readiness_ko"],
                "key_strengths": localized["tech_key_points_ko"],
                "key_risks": localized["tech_risks_ko"],
                "evidence_gaps": localized["tech_gaps_ko"],
            }),
            "",
            *_analysis_section("시장 분석", localized["market_summary_ko"], {
                **state.get("market_assessment", {}),
                "target_market": localized["market_target_ko"],
                "market_maturity": localized["market_maturity_ko"],
                "estimate_range": localized["market_estimate_range_ko"],
                "demand_drivers": localized["market_key_points_ko"],
                "competitive_risks": localized["market_risks_ko"],
                "evidence_gaps": localized["market_gaps_ko"],
            }),
            "",
            *_analysis_section("경쟁 분석", localized["competitor_summary_ko"], {
                **state.get("competitor_assessment", {}),
                "closest_competitors": localized["competitor_closest_ko"],
                "differentiation": localized["competitor_key_points_ko"],
                "competitive_risks": localized["competitor_risks_ko"],
                "evidence_gaps": localized["competitor_gaps_ko"],
            }),
            "",
            "## 스코어카드",
            *_scorecard_lines(scorecard),
            "",
            "## Hard Filter",
            *_hard_filter_lines(hard_filter_results),
            "",
            "## 수집 근거",
            *_research_source_lines(research_sources),
            "",
            "## 참고 출처",
            "\n".join(f"- {source}" for source in state.get("rag_sources", [])),
        ]
    )
    report_history = [*state.get("report_history", [])]
    report_history.append(
        {
            "startup_name": startup_name,
            "decision": state.get("investment_decision", "hold"),
            "final_score": state.get("final_score", 0.0),
            "summary": localized["summary_reason_short_ko"],
            "scorecard": scorecard,
            "hard_filter_results": hard_filter_results,
            "startup_basic_info": startup_basic_info,
            "report_content": company_report,
        }
    )
    report_content = "\n".join(
        [
            "# Robotics Evaluation Summary",
            "",
            "| Startup | Decision | Final Score | Key Reason |",
            "| --- | --- | --- | --- |",
            *[
                f"| {item['startup_name']} | {item['decision']} | {item['final_score']} | {item['summary']} |"
                for item in report_history
            ],
        ]
    )
    return {
        "report_content": report_content,
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), startup_name],
    }
