from __future__ import annotations

from datetime import date

from .state import InvestmentState


TEAM_MEMBERS = ["배민", "이성민", "임세하", "정찬혁"]
REPORT_DATE = date(2026, 3, 12)
SCORECARD_WEIGHTS: dict[str, float] = {
    "팀 & 창업자": 0.20,
    "시장 기회": 0.20,
    "기술력·양산": 0.30,
    "경쟁 환경·해자": 0.10,
    "고객 ROI·트랙션": 0.10,
    "안전 인증·규제": 0.05,
    "수익모델 지속성": 0.05,
}
SCORECARD_KEY_MAP = {
    "팀 & 창업자": "team_founders",
    "시장 기회": "market_opportunity",
    "기술력·양산": "technology_production",
    "경쟁 환경·해자": "competition_moat",
    "고객 ROI·트랙션": "customer_roi_traction",
    "안전 인증·규제": "safety_regulation",
    "수익모델 지속성": "business_model",
}
DECISION_LABELS = {
    "invest": "투자 추천",
    "hold": "관심 보류",
}
HARD_FILTER_LABELS = {
    "trl_below_7_signal": "TRL 7 미만 또는 기술 검증 근거 부족",
    "no_manufacturing_plan_signal": "양산 계획 또는 제조 파트너 근거 부족",
    "no_roi_evidence_signal": "고객 ROI 정량 근거 부족",
    "weak_moat_signal": "기술 해자 약함",
    "no_safety_plan_signal": "안전 인증 또는 규제 대응 계획 부족",
}


def _extract_domain_label(user_query: str) -> str:
    cleaned = (user_query or "").strip()
    if not cleaned:
        return "Robotics"
    suffixes = [
        " 찾아서 투자 평가해줘",
        " 투자 평가해줘",
        " 스타트업 찾아줘",
        " 찾아줘",
        " 평가해줘",
        " 투자 검토",
        " 투자 검토 요청",
    ]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned or "Robotics"


def _decision_grade(final_score: float) -> str:
    if final_score >= 3.5:
        return "투자 추천"
    if final_score >= 2.5:
        return "관심 보류"
    return "투자 제외"


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _as_text(value: object, default: str = "미기재") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _format_basic_info(basic_info: dict[str, object]) -> str:
    founded_year = basic_info.get("founded_year") or basic_info.get("founding_year") or basic_info.get("found_date") or "미기재"
    country = basic_info.get("country") or basic_info.get("location") or basic_info.get("region") or "미기재"
    funding_round = basic_info.get("funding_round") or basic_info.get("investment_stage") or basic_info.get("stage") or "미기재"
    product = (
        basic_info.get("core_product")
        or basic_info.get("product_name")
        or basic_info.get("product")
        or basic_info.get("description")
        or "미기재"
    )
    return (
        f"- 설립연도: {founded_year}\n"
        f"- 국가: {country}\n"
        f"- 투자 라운드: {funding_round}\n"
        f"- 핵심 제품: {product}"
    )


def _render_bullet_block(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}\n- 미기재"
    return "\n".join([title, *[f"- {item}" for item in items]])


def _render_reference_block(title: str, sources: list[dict[str, object]]) -> str:
    if not sources:
        return f"{title}\n- 관련 문서 근거 없음"
    lines = [title]
    for source in sources[:5]:
        source_type = source.get("source_type", "source")
        label = source.get("title") or source.get("url") or "미기재"
        lines.append(f"- [{source_type}] {label}")
    return "\n".join(lines)


def _render_hard_filter_section(hard_filter_results: dict[str, bool]) -> str:
    triggered: list[str] = []
    clear: list[str] = []
    for key, label in HARD_FILTER_LABELS.items():
        if bool(hard_filter_results.get(key, False)):
            triggered.append(label)
        else:
            clear.append(label)
    lines = ["Hard Filter 판정"]
    lines.append("- 종합 판정: " + ("주의 필요" if triggered else "특이 경고 없음"))
    lines.append("- 경고 항목: " + (", ".join(triggered) if triggered else "없음"))
    lines.append("- 통과 항목: " + (", ".join(clear) if clear else "없음"))
    return "\n".join(lines)


def _score_from_state(scorecard: dict[str, float], label: str) -> float:
    return float(scorecard.get(SCORECARD_KEY_MAP[label], 0.0))


def _render_scorecard_table(scorecard: dict[str, float], final_score: float) -> str:
    rows = [
        "| 항목 | 가중치 | 점수 | 가중점수 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item, weight in SCORECARD_WEIGHTS.items():
        score = _score_from_state(scorecard, item)
        weighted = score * weight
        rows.append(f"| {item} | {int(weight * 100)}% | {score:.1f} | {weighted:.2f} |")
    rows.append(f"| 총점 | 100% |  | {final_score:.2f} |")
    return "\n".join(rows)


def _render_ranking_table(evaluations: list[dict[str, object]]) -> str:
    lines = [
        "| 순위 | 기업명 | 총점 | 투자 결론 |",
        "| --- | --- | ---: | --- |",
    ]
    for rank, evaluation in enumerate(evaluations, start=1):
        lines.append(
            f"| {rank} | {evaluation['startup_name']} | {float(evaluation['final_score']):.2f} | {evaluation['decision_label']} |"
        )
    return "\n".join(lines)


def _render_weight_table() -> str:
    lines = [
        "| 평가 항목 | 가중치 |",
        "| --- | ---: |",
    ]
    for item, weight in SCORECARD_WEIGHTS.items():
        lines.append(f"| {item} | {int(weight * 100)}% |")
    return "\n".join(lines)


def _render_company_list(evaluations: list[dict[str, object]]) -> str:
    return "\n".join(
        f"- {item['startup_name']} ({_decision_grade(float(item['final_score']))}, 총점 {float(item['final_score']):.2f})"
        for item in evaluations
    )


def _render_decision_breakdown(evaluations: list[dict[str, object]]) -> str:
    invest_count = sum(1 for item in evaluations if item.get("investment_decision") == "invest")
    hold_count = sum(1 for item in evaluations if item.get("investment_decision") == "hold")
    excluded_count = sum(1 for item in evaluations if float(item.get("final_score", 0.0)) < 2.5)
    return (
        f"- 전체 평가 기업 수: {len(evaluations)}\n"
        f"- 투자 추천 수: {invest_count}\n"
        f"- 투자 보류 수: {hold_count}\n"
        f"- 저점(2.5점 미만) 기업 수: {excluded_count}"
    )


def _render_hold_list(evaluations: list[dict[str, object]]) -> str:
    hold_items = [item for item in evaluations if item.get("investment_decision") == "hold"]
    if not hold_items:
        return "- 해당 없음"
    return "\n".join(
        f"- {item['startup_name']} ({float(item['final_score']):.2f}점): {item.get('decision_reason', '사유 미기재')}"
        for item in hold_items
    )


def _render_comparison_table(evaluations: list[dict[str, object]]) -> str:
    header = "| 기업명 | " + " | ".join(SCORECARD_WEIGHTS.keys()) + " | 총점 | 등급 |"
    separator = "| --- |" + " ---: |" * (len(SCORECARD_WEIGHTS) + 2)
    lines = [header, separator]
    for evaluation in evaluations:
        scores = " | ".join(
            f"{_score_from_state(evaluation.get('scorecard', {}), item):.2f}" for item in SCORECARD_WEIGHTS
        )
        lines.append(
            f"| {evaluation['startup_name']} | {scores} | {float(evaluation['final_score']):.2f} | {_decision_grade(float(evaluation['final_score']))} |"
        )
    return "\n".join(lines)


def _render_strengths(evaluations: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for item in SCORECARD_WEIGHTS:
        best = max(evaluations, key=lambda evaluation: _score_from_state(evaluation.get("scorecard", {}), item))
        lines.append(f"- {item}: {best['startup_name']} ({_score_from_state(best.get('scorecard', {}), item):.2f}점)")
    return "\n".join(lines)


def _render_references(evaluations: list[dict[str, object]]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for evaluation in evaluations:
        for source in evaluation.get("rag_sources", []):
            source_text = str(source).strip()
            if source_text and source_text not in seen:
                seen.add(source_text)
                ordered.append(source_text)
        for source in evaluation.get("tech_research_sources", []):
            label = str(source.get("title") or source.get("url") or "").strip()
            if label and label not in seen:
                seen.add(label)
                ordered.append(label)
        for source in evaluation.get("market_research_sources", []):
            label = str(source.get("title") or source.get("url") or "").strip()
            if label and label not in seen:
                seen.add(label)
                ordered.append(label)
    if not ordered:
        return "- 기관 보고서\n- 학술 논문\n- 웹페이지"
    return "\n".join(f"- {source}" for source in ordered)


def _build_summary(evaluations: list[dict[str, object]], domain_label: str) -> str:
    top = evaluations[0]
    return (
        "[SUMMARY]\n"
        f"- 평가 개요: {domain_label} 스타트업 {len(evaluations)}개사를 7개 항목 Scorecard와 정성 분석으로 평가했다.\n"
        "- 평가 기준: 팀, 시장, 기술력·양산, 경쟁 환경, 고객 ROI, 규제, 수익모델을 종합 반영했다.\n\n"
        f"{_render_ranking_table(evaluations)}\n\n"
        f"- 핵심 인사이트 1: {domain_label} 투자에서는 기술 성숙도와 양산 실행력이 최종 순위에 큰 영향을 준다.\n"
        f"- 핵심 인사이트 2: 최고 점수 기업은 {top['startup_name']}이며 총점은 {float(top['final_score']):.2f}점이다.\n"
        "- 핵심 인사이트 3: 총점이 유사한 기업은 경쟁 해자와 고객 ROI 검증 수준에서 우선순위가 갈린다."
    )


def _build_company_section(evaluation: dict[str, object], index: int) -> str:
    prefix = f"2.{index}"
    basic_info = evaluation.get("startup_basic_info", {})
    if not isinstance(basic_info, dict):
        basic_info = {}
    traction = evaluation.get("traction_summary", "파일럿, ROI, 재계약률 관련 정보 미기재")
    tech_sources = evaluation.get("tech_research_sources", [])
    market_sources = evaluation.get("market_research_sources", [])
    competitor_closest = evaluation.get("competitor_closest", [])
    return (
        f"{prefix} [{evaluation['startup_name']}]\n"
        f"{prefix}.1 기업 개요\n{_format_basic_info(basic_info)}\n\n"
        f"{prefix}.2 기술력 분석\n{evaluation.get('tech_summary', '미기재')}\n"
        f"- TRL 추정: {evaluation.get('tech_trl', '미기재')}\n"
        f"- 양산 준비도: {evaluation.get('tech_manufacturing_readiness', '미기재')}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('tech_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('tech_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('tech_gaps', []))}\n\n"
        f"{_render_reference_block('기술 문서 근거', tech_sources)}\n\n"
        f"{prefix}.3 시장성 분석\n{evaluation.get('market_evaluation', '미기재')}\n"
        f"- 타깃 시장: {evaluation.get('market_target', '미기재')}\n"
        f"- 시장 성숙도: {evaluation.get('market_maturity', '미기재')}\n"
        f"- 시장 추정 범위: {evaluation.get('market_estimate_range', '미기재')}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('market_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('market_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('market_gaps', []))}\n\n"
        f"{_render_reference_block('시장 문서 근거', market_sources)}\n\n"
        f"{prefix}.4 경쟁 환경\n{evaluation.get('competitor_analysis', '미기재')}\n"
        f"- 근접 경쟁사: {', '.join(str(item) for item in competitor_closest) or '미기재'}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('competitor_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('competitor_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('competitor_gaps', []))}\n\n"
        f"{prefix}.5 고객 트랙션\n{traction}\n\n"
        f"{prefix}.6 Scorecard 점수표\n{_render_scorecard_table(evaluation.get('scorecard', {}), float(evaluation.get('final_score', 0.0)))}\n\n"
        f"{prefix}.7 Hard Filter 점검\n{_render_hard_filter_section(evaluation.get('hard_filter_results', {}))}\n\n"
        f"{prefix}.8 투자 판단 및 근거\n"
        f"- 투자 결론: {evaluation.get('investment_decision', 'hold')}\n"
        f"- 투자 판단(한글): {evaluation.get('decision_label', _decision_grade(float(evaluation.get('final_score', 0.0))))}\n"
        f"- 등급: {_decision_grade(float(evaluation.get('final_score', 0.0)))}\n"
        f"- 판단 근거: {evaluation.get('decision_reason', '미기재')}"
    )


def _build_company_sections(evaluations: list[dict[str, object]]) -> str:
    sections: list[str] = ["2. 기업별 상세 분석"]
    for index, evaluation in enumerate(evaluations, start=1):
        sections.append(_build_company_section(evaluation, index))
    return "\n\n".join(sections)


def build_report_content(all_evaluations: list[dict[str, object]], *, domain_label: str) -> str:
    evaluations = sorted(all_evaluations, key=lambda item: float(item["final_score"]), reverse=True)
    if not evaluations:
        return "평가 결과가 없어 통합 투자 보고서를 생성할 수 없습니다."

    top = evaluations[0]
    company_risks = "\n".join(
        f"- {evaluation['startup_name']}: {evaluation.get('decision_reason', '리스크 정보 미기재')}"
        for evaluation in evaluations
    )
    sections = [
        "[표지]\n"
        f"- 보고서명: {domain_label} 스타트업 투자 평가 보고서\n"
        "- 팀원: " + ", ".join(TEAM_MEMBERS) + "\n"
        f"- 평가 도메인: {domain_label}\n"
        f"- 작성일: {REPORT_DATE.isoformat()}\n"
        f"- 평가 기업 수: {len(evaluations)}",
        _build_summary(evaluations, domain_label),
        "────────────────────────────────────",
        "1. 평가 개요\n"
        "1.1 평가 목적 및 범위\n"
        f"- {domain_label} 스타트업의 투자 적합도를 기술, 시장, 경쟁, 사업성 관점에서 종합 평가한다.\n"
        "- 평가 결과는 다중 후보 간 상대 비교와 투자 우선순위 도출에 사용한다.\n"
        "- 보고서에는 투자 추천, 투자 보류, 저점 기업을 포함한 전체 평가 결과를 모두 포함한다.\n\n"
        "1.2 평가 방법론\n"
        "- Scorecard 7개 항목과 Hard Filter를 결합해 점수와 보류 여부를 판단한다.\n\n"
        f"{_render_weight_table()}\n\n"
        "1.3 평가 대상 기업 목록\n"
        f"{_render_company_list(evaluations)}\n\n"
        "1.4 전체 평가 현황\n"
        f"{_render_decision_breakdown(evaluations)}",
        "────────────────────────────────────",
        _build_company_sections(evaluations),
        "────────────────────────────────────",
        "3. 종합 비교 분석\n"
        "3.1 항목별 비교표\n"
        f"{_render_comparison_table(evaluations)}\n\n"
        "3.2 최종 순위 및 투자 추천 등급\n"
        "- 투자 추천: 총점 3.5 이상\n"
        "- 관심 보류: 총점 2.5~3.4\n"
        "- 투자 제외: 총점 2.5 미만\n\n"
        "3.3 투자 보류 및 저점 기업 목록\n"
        f"{_render_hold_list(evaluations)}\n\n"
        "3.4 항목별 강자 분석\n"
        f"{_render_strengths(evaluations)}",
        "────────────────────────────────────",
        "4. 리스크 분석\n"
        "4.1 공통 리스크\n"
        "- 로보틱스 도메인은 인증 지연, 제조 원가, 공급망 불확실성, 현장 통합 난이도가 높다.\n"
        "- 고객 ROI 입증이 늦어지면 파일럿 장기화와 후속 투자 지연이 동시에 발생할 수 있다.\n\n"
        "4.2 기업별 핵심 리스크 요약\n"
        f"{company_risks}",
        "────────────────────────────────────",
        "5. 투자 제언\n"
        "5.1 1순위 투자 추천 기업 및 조건\n"
        f"- 1순위 투자 추천 기업: {top['startup_name']}\n"
        f"- 추천 조건: {top.get('decision_reason', '추가 검토 필요')}\n\n"
        "5.2 모니터링 지표 (KPI)\n"
        "- 파일럿 수와 유상 전환율\n"
        "- 양산 일정 준수율과 BOM 원가 개선 추이\n"
        "- 인증 획득 진행률과 고객 ROI 수치\n\n"
        "5.3 추가 검토 사항 및 한계점\n"
        "- 공개 자료 중심 평가라 비공개 재무, 계약, 제조 수율 정보는 제한적으로 반영되었을 수 있다.\n"
        "- 실제 투자 집행 전 고객 인터뷰, 제조 파트너 실사, 인증 문서 검증이 필요하다.",
        "────────────────────────────────────",
        "[REFERENCE]\n" + _render_references(evaluations),
    ]
    return "\n\n".join(sections)


def _as_report_item(state: InvestmentState) -> dict[str, object]:
    startup_basic_info = state.get("startup_basic_info", {})
    tech_assessment = state.get("tech_assessment", {})
    market_assessment = state.get("market_assessment", {})
    competitor_assessment = state.get("competitor_assessment", {})
    roi_assessment = state.get("roi_traction_assessment", {})
    final_score = float(state.get("final_score", 0.0))
    decision = state.get("investment_decision", "hold")
    return {
        "startup_name": state["startup_name"],
        "investment_decision": decision,
        "decision_label": DECISION_LABELS.get(decision, "관심 보류"),
        "final_score": final_score,
        "decision_reason": _as_text(state.get("decision_reason", "미기재")),
        "scorecard": state.get("scorecard", {}),
        "hard_filter_results": state.get("hard_filter_results", {}),
        "startup_basic_info": startup_basic_info,
        "tech_summary": _as_text(
            state.get("tech_summary") or tech_assessment.get("summary"),
        ),
        "tech_trl": _as_text(tech_assessment.get("trl_estimate") or tech_assessment.get("trl_level")),
        "tech_manufacturing_readiness": _as_text(tech_assessment.get("manufacturing_readiness")),
        "tech_key_points": _as_list(tech_assessment.get("key_strengths") or tech_assessment.get("evidence")),
        "tech_risks": _as_list(tech_assessment.get("key_risks") or tech_assessment.get("risks")),
        "tech_gaps": _as_list(tech_assessment.get("evidence_gaps")),
        "market_evaluation": _as_text(
            state.get("market_evaluation") or market_assessment.get("summary"),
        ),
        "market_target": _as_text(market_assessment.get("target_market")),
        "market_maturity": _as_text(market_assessment.get("market_maturity")),
        "market_estimate_range": _as_text(market_assessment.get("estimate_range")),
        "market_key_points": _as_list(market_assessment.get("demand_drivers") or market_assessment.get("evidence")),
        "market_risks": _as_list(market_assessment.get("competitive_risks") or market_assessment.get("risks")),
        "market_gaps": _as_list(market_assessment.get("evidence_gaps")),
        "competitor_analysis": _as_text(
            state.get("competitor_analysis") or competitor_assessment.get("summary"),
        ),
        "competitor_closest": _as_list(competitor_assessment.get("closest_competitors")),
        "competitor_key_points": _as_list(competitor_assessment.get("differentiation") or competitor_assessment.get("evidence")),
        "competitor_risks": _as_list(competitor_assessment.get("competitive_risks") or competitor_assessment.get("risks")),
        "competitor_gaps": _as_list(competitor_assessment.get("evidence_gaps")),
        "traction_summary": _as_text(
            startup_basic_info.get("traction")
            or roi_assessment.get("summary")
            or "파일럿, ROI, 재계약률 관련 정보 미기재"
        ),
        "tech_research_sources": state.get("tech_research_sources", []),
        "market_research_sources": state.get("market_research_sources", []),
        "rag_sources": state.get("rag_sources", []),
        "summary": _as_text(state.get("decision_reason", "미기재")),
        "report_content": "",
    }


def report_writer_node(state: InvestmentState) -> InvestmentState:
    domain_label = _extract_domain_label(state.get("user_query", ""))
    report_history = [*state.get("report_history", [])]
    current = _as_report_item(state)
    current["report_content"] = _build_company_section(current, len(report_history) + 1)
    report_history.append(current)
    report_content = build_report_content(report_history, domain_label=domain_label)
    return {
        "report_content": report_content,
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), state["startup_name"]],
    }


report_writer_node = report_writer_node
