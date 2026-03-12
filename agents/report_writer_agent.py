from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse

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


def _clean_source_title(title: str) -> str:
    cleaned = re.sub(r"\s+p\.\d+\s*$", "", title or "").strip()
    return cleaned or "자료명 미기재"


def _extract_year(text: str) -> str:
    match = re.search(r"(20\d{2})", text or "")
    return match.group(1) if match else str(REPORT_DATE.year)


def _extract_date(text: str) -> str:
    match = re.search(r"(20\d{2})[-_/]?(\d{2})[-_/]?(\d{2})", text or "")
    if not match:
        return REPORT_DATE.isoformat()
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _site_name(url: str) -> str:
    host = urlparse(url or "").netloc.lower().replace("www.", "").strip()
    return host or "source"


def _source_org(title: str, url: str) -> str:
    site = _site_name(url)
    if site and site != "source":
        return site.split(".")[0].upper()
    token = re.split(r"[\s\-\|_/]+", _clean_source_title(title))[0].strip()
    return token or "출처기관"


def _classify_reference(source: dict[str, str]) -> str:
    text = " ".join(
        [
            source.get("title", ""),
            source.get("url", ""),
            source.get("source_type", ""),
        ]
    ).lower()
    if any(keyword in text for keyword in ["arxiv", "doi.org", "journal", "proceedings", "ieee", "acm", "springer"]):
        return "academic"
    if any(keyword in text for keyword in ["report", "outlook", "whitepaper", "보고서", "백서"]):
        return "institution"
    return "web"


def _collect_used_sources(evaluations: list[dict[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for evaluation in evaluations:
        basic_info = evaluation.get("startup_basic_info", {})
        if isinstance(basic_info, dict):
            profile_url = str(basic_info.get("url", "")).strip()
            if profile_url:
                rows.append(
                    {
                        "title": f"{evaluation.get('startup_name', '')} company profile",
                        "url": profile_url,
                        "source_type": "startup_profile",
                    }
                )
        for source in evaluation.get("tech_research_sources", []):
            rows.append(
                {
                    "title": str(source.get("title", "")).strip(),
                    "url": str(source.get("url", "")).strip(),
                    "source_type": str(source.get("source_type", "")).strip(),
                }
            )
        for source in evaluation.get("market_research_sources", []):
            rows.append(
                {
                    "title": str(source.get("title", "")).strip(),
                    "url": str(source.get("url", "")).strip(),
                    "source_type": str(source.get("source_type", "")).strip(),
                }
            )
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.get("url", ""), row.get("title", ""))
        if not row.get("url") or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _format_reference_line(category: str, source: dict[str, str]) -> str:
    title = _clean_source_title(source.get("title", ""))
    url = source.get("url", "")
    org = _source_org(title, url)
    year = _extract_year(f"{title} {url}")
    if category == "institution":
        return f"- {org}({year}). *{title}*. {url}"
    if category == "academic":
        return f"- {org}({year}). {title}. *학술지 미상*, 권(호) 미상, 페이지 미상."
    date_text = _extract_date(f"{title} {url}")
    return f"- {org}({date_text}). *{title}*. {_site_name(url)}, {url}"


def _render_references(evaluations: list[dict[str, object]]) -> str:
    used_sources = _collect_used_sources(evaluations)
    grouped = {"institution": [], "academic": [], "web": []}
    for source in used_sources:
        category = _classify_reference(source)
        grouped[category].append(_format_reference_line(category, source))
    institution_lines = "\n".join(grouped["institution"]) if grouped["institution"] else "- 해당 없음"
    academic_lines = "\n".join(grouped["academic"]) if grouped["academic"] else "- 해당 없음"
    web_lines = "\n".join(grouped["web"]) if grouped["web"] else "- 해당 없음"
    return (
        "기관 보고서\n"
        f"{institution_lines}\n\n"
        "학술 논문\n"
        f"{academic_lines}\n\n"
        "웹페이지\n"
        f"{web_lines}"
    )


def _build_summary(evaluations: list[dict[str, object]], domain_label: str) -> str:
    top = evaluations[0]
    top_risks = ", ".join(_as_list(top.get("business_risks", []))[:3]) or "제조/인증/ROI 검증 리스크"
    return (
        "[SUMMARY]\n"
        f"- 평가 대상: {domain_label} 스타트업 {len(evaluations)}개사\n"
        "- 평가 방법: 7개 항목 Scorecard + Hard Filter + 근거자료 기반 정성 분석\n"
        f"- 최우선 후보: {top['startup_name']} (총점 {float(top['final_score']):.2f}, {top['decision_label']})\n"
        f"- 핵심 투자포인트: {top.get('business_idea', '핵심 컨셉 정보 미기재')}\n"
        f"- 핵심 리스크: {top_risks}\n"
        "- 공통 한계: 공개자료 중심 분석으로 비공개 재무/실사 정보는 제한적으로 반영"
    )


def _build_company_section(evaluation: dict[str, object], index: int) -> str:
    prefix = f"1.{index}"
    basic_info = evaluation.get("startup_basic_info", {})
    if not isinstance(basic_info, dict):
        basic_info = {}
    traction = evaluation.get("traction_summary", "파일럿, ROI, 재계약률 관련 정보 미기재")
    tech_sources = evaluation.get("tech_research_sources", [])
    market_sources = evaluation.get("market_research_sources", [])
    competitor_closest = evaluation.get("competitor_closest", [])
    business_risks = _as_list(evaluation.get("business_risks", []))
    limitations = _as_list(evaluation.get("limitations", []))
    return (
        f"{prefix} [{evaluation['startup_name']}]\n"
        f"{prefix}.1 기업 개요\n{_format_basic_info(basic_info)}\n\n"
        f"{prefix}.2 사업 아이디어(핵심 컨셉)\n{evaluation.get('business_idea', '미기재')}\n\n"
        f"{prefix}.3 팀 구성(핵심 창업자/기술 역량)\n"
        f"{_render_bullet_block('핵심 팀', _as_list(evaluation.get('team_composition', [])))}\n\n"
        f"{prefix}.4 기술력 분석\n{evaluation.get('tech_summary', '미기재')}\n"
        f"- TRL 추정: {evaluation.get('tech_trl', '미기재')}\n"
        f"- 양산 준비도: {evaluation.get('tech_manufacturing_readiness', '미기재')}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('tech_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('tech_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('tech_gaps', []))}\n\n"
        f"{_render_reference_block('기술 문서 근거', tech_sources)}\n\n"
        f"{prefix}.5 시장성 분석\n{evaluation.get('market_evaluation', '미기재')}\n"
        f"- 타깃 시장: {evaluation.get('market_target', '미기재')}\n"
        f"- 시장 성숙도: {evaluation.get('market_maturity', '미기재')}\n"
        f"- 시장 규모: {evaluation.get('market_estimate_range', '미기재')}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('market_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('market_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('market_gaps', []))}\n\n"
        f"{_render_reference_block('시장 문서 근거', market_sources)}\n\n"
        f"{prefix}.6 경쟁 환경\n{evaluation.get('competitor_analysis', '미기재')}\n"
        f"- 근접 경쟁사: {', '.join(str(item) for item in competitor_closest) or '미기재'}\n\n"
        f"{_render_bullet_block('핵심 포인트', evaluation.get('competitor_key_points', []))}\n\n"
        f"{_render_bullet_block('주요 리스크', evaluation.get('competitor_risks', []))}\n\n"
        f"{_render_bullet_block('추가 확인 필요', evaluation.get('competitor_gaps', []))}\n\n"
        f"{prefix}.7 사업 리스크(시장·기술·규제·경쟁)\n"
        f"{_render_bullet_block('핵심 리스크', business_risks)}\n\n"
        f"{prefix}.8 고객 트랙션\n{traction}\n\n"
        f"{prefix}.9 한계점\n{_render_bullet_block('분석 한계', limitations)}\n\n"
        f"{prefix}.10 Scorecard 점수표\n{_render_scorecard_table(evaluation.get('scorecard', {}), float(evaluation.get('final_score', 0.0)))}\n\n"
        f"{prefix}.11 Hard Filter 점검\n{_render_hard_filter_section(evaluation.get('hard_filter_results', {}))}\n\n"
        f"{prefix}.12 투자 판단 및 근거\n"
        f"- 투자 결론: {evaluation.get('investment_decision', 'hold')}\n"
        f"- 투자 판단(한글): {evaluation.get('decision_label', _decision_grade(float(evaluation.get('final_score', 0.0))))}\n"
        f"- 등급: {_decision_grade(float(evaluation.get('final_score', 0.0)))}\n"
        f"- 판단 근거: {evaluation.get('decision_reason', '미기재')}"
    )


def _build_company_sections(evaluations: list[dict[str, object]]) -> str:
    sections: list[str] = ["1. 기업별 상세 분석"]
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
        _build_summary(evaluations, domain_label),
        "────────────────────────────────────",
        "0. 보고서 개요\n"
        f"- 보고서명: {domain_label} 스타트업 투자 평가 보고서\n"
        "- 작성자: " + ", ".join(TEAM_MEMBERS) + "\n"
        f"- 작성일: {REPORT_DATE.isoformat()}\n"
        f"- 평가 도메인: {domain_label}\n"
        f"- 평가 기업 수: {len(evaluations)}\n\n"
        "0.1 평가 목적 및 범위\n"
        f"- {domain_label} 스타트업의 투자 적합도를 기술, 시장, 경쟁, 사업성 관점에서 종합 평가한다.\n"
        "- 평가 결과는 다중 후보 간 상대 비교와 투자 우선순위 도출에 사용한다.\n"
        "- 보고서에는 투자 추천, 투자 보류, 저점 기업을 포함한 전체 평가 결과를 모두 포함한다.\n\n"
        "0.2 평가 방법론\n"
        "- Scorecard 7개 항목과 Hard Filter를 결합해 점수와 보류 여부를 판단한다.\n\n"
        f"{_render_weight_table()}\n\n"
        "0.3 평가 대상 기업 목록\n"
        f"{_render_company_list(evaluations)}\n\n"
        "0.4 전체 평가 현황\n"
        f"{_render_decision_breakdown(evaluations)}",
        "────────────────────────────────────",
        _build_company_sections(evaluations),
        "────────────────────────────────────",
        "2. 종합 비교 분석\n"
        "2.1 항목별 비교표\n"
        f"{_render_comparison_table(evaluations)}\n\n"
        "2.2 최종 순위 및 투자 추천 등급\n"
        "- 투자 추천: 총점 3.5 이상\n"
        "- 관심 보류: 총점 2.5~3.4\n"
        "- 투자 제외: 총점 2.5 미만\n\n"
        "2.3 투자 보류 및 저점 기업 목록\n"
        f"{_render_hold_list(evaluations)}\n\n"
        "2.4 항목별 강자 분석\n"
        f"{_render_strengths(evaluations)}",
        "────────────────────────────────────",
        "3. 리스크 분석\n"
        "3.1 공통 리스크\n"
        "- 로보틱스 도메인은 인증 지연, 제조 원가, 공급망 불확실성, 현장 통합 난이도가 높다.\n"
        "- 고객 ROI 입증이 늦어지면 파일럿 장기화와 후속 투자 지연이 동시에 발생할 수 있다.\n\n"
        "3.2 기업별 핵심 리스크 요약\n"
        f"{company_risks}",
        "────────────────────────────────────",
        "4. 투자 제언\n"
        "4.1 1순위 투자 추천 기업 및 조건\n"
        f"- 1순위 투자 추천 기업: {top['startup_name']}\n"
        f"- 추천 조건: {top.get('decision_reason', '추가 검토 필요')}\n\n"
        "4.2 모니터링 지표 (KPI)\n"
        "- 파일럿 수와 유상 전환율\n"
        "- 양산 일정 준수율과 BOM 원가 개선 추이\n"
        "- 인증 획득 진행률과 고객 ROI 수치\n\n"
        "4.3 추가 검토 사항 및 한계점\n"
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
        "business_idea": _as_text(
            startup_basic_info.get("core_concept")
            or startup_basic_info.get("product_name")
            or startup_basic_info.get("description")
        ),
        "team_composition": _as_list(startup_basic_info.get("team_members") or startup_basic_info.get("founders")),
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
        "business_risks": _as_list(
            [
                *_as_list(market_assessment.get("evidence_gaps")),
                *_as_list(tech_assessment.get("risks")),
                *_as_list(competitor_assessment.get("competitive_risks")),
                *_as_list(state.get("safety_assessment", {}).get("compliance_risks")),
            ]
        ),
        "limitations": _as_list(
            [
                *_as_list(tech_assessment.get("evidence_gaps")),
                *_as_list(market_assessment.get("evidence_gaps")),
                *_as_list(competitor_assessment.get("evidence_gaps")),
                *_as_list(state.get("safety_assessment", {}).get("evidence_gaps")),
            ]
        ),
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
