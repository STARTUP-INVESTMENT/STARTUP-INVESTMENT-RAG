from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse

from core.agent_utils import json_response, string_list
from core.prompt_loader import load_prompt
from core.state import InvestmentState


REPORT_DATE = date(2026, 3, 12)
DECISION_LABELS = {"invest": "투자 추천", "hold": "보류"}
SCORECARD_LABELS = {
    "team_founders": "팀 & 창업자",
    "market_opportunity": "시장 기회",
    "technology_production": "기술력 & 양산 가능성",
    "competition_moat": "경쟁 환경",
    "customer_roi_traction": "고객 ROI & 트랙션",
    "safety_regulation": "안전 인증 & 규제",
    "business_model": "수익 모델 지속성",
}
SCORECARD_WEIGHTS = {
    "team_founders": 0.20,
    "market_opportunity": 0.20,
    "technology_production": 0.30,
    "competition_moat": 0.10,
    "customer_roi_traction": 0.10,
    "safety_regulation": 0.05,
    "business_model": 0.05,
}


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _as_text(value: object, default: str = "미기재") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _bullets(items: list[str], empty: str = "미기재") -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def _company_overview_lines(basic_info: dict[str, object]) -> list[str]:
    return [
        f"- 회사명: {_as_text(basic_info.get('name'))}",
        f"- 국가/지역: {_as_text(basic_info.get('country') or basic_info.get('location') or basic_info.get('region'))}",
        f"- 단계: {_as_text(basic_info.get('funding_round') or basic_info.get('investment_stage') or basic_info.get('stage'))}",
        f"- 핵심 제품: {_as_text(basic_info.get('core_product') or basic_info.get('product_name') or basic_info.get('product') or basic_info.get('description'))}",
    ]


def _scorecard_table(scorecard: dict[str, float], final_score: float) -> list[str]:
    lines = [
        "| 평가 항목 | 점수 | 가중치 | 가중 점수 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, label in SCORECARD_LABELS.items():
        score = float(scorecard.get(key, 0.0))
        weight = SCORECARD_WEIGHTS[key]
        lines.append(f"| {label} | {score:.2f} | {int(weight * 100)}% | {(score * weight):.2f} |")
    lines.append(f"| 총점 |  | 100% | {final_score:.2f} |")
    return lines


def _source_kind(url: str, title: str) -> str:
    host = urlparse(url).netloc.lower()
    title_text = title.lower()
    if any(domain in host for domain in ["arxiv.org", "nature.com", "science.org", "ieeexplore.ieee.org", "springer.com"]):
        return "paper"
    if any(token in host for token in ["mckinsey", "ifr", "researchandmarkets", "iea", "kdi", "bok.or.kr", "oecd", "worldbank"]):
        return "report"
    if any(token in title_text for token in ["report", "outlook", "white paper", "world robotics", "금융안정보고서", "시장 보고서"]):
        return "report"
    return "web"


def _extract_year(text: str) -> str:
    match = re.search(r"(20\d{2})", text or "")
    return match.group(1) if match else "연도 미상"


def _site_name(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host or "출처 미상"


def _org_name(url: str, title: str) -> str:
    host = _site_name(url)
    if host != "출처 미상":
        return host.split(".")[0].upper()
    token = re.split(r"[\s\-\|:/]+", title.strip())[0]
    return token or "출처 미상"


def _reference_line(source: dict[str, object]) -> tuple[str, str]:
    title = _as_text(source.get("title"), "제목 미상")
    url = _as_text(source.get("url"), "")
    source_type = _source_kind(url, title)
    year = _extract_year(f"{title} {url}")
    org = _org_name(url, title)
    if source_type == "report":
        line = f"- {org}({year}). *{title}*. {url}"
        return "기관 보고서", line
    if source_type == "paper":
        line = f"- {org}({year}). {title}. *학술지명 미상*, 권(호) 미상, 페이지 미상."
        return "학술 논문", line
    line = f"- {org}({year if year != '연도 미상' else REPORT_DATE.isoformat()}). *{title}*. {_site_name(url)}, {url}"
    return "웹페이지", line


def _reference_sections(sources: list[dict[str, object]]) -> list[str]:
    unique: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (str(source.get("title", "")), str(source.get("url", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)

    buckets = {"기관 보고서": [], "학술 논문": [], "웹페이지": []}
    for source in unique:
        bucket, line = _reference_line(source)
        buckets[bucket].append(line)

    lines = ["## REFERENCE", ""]
    for bucket in ["기관 보고서", "학술 논문", "웹페이지"]:
        lines.append(bucket)
        if buckets[bucket]:
            lines.extend(buckets[bucket])
        else:
            lines.append("- 해당 없음")
        lines.append("")
    return lines[:-1]


def _company_references(state: InvestmentState) -> list[dict[str, object]]:
    return [
        *state.get("tech_research_sources", []),
        *state.get("market_research_sources", []),
        *state.get("competitor_research_sources", []),
    ]


def _llm_company_sections(state: InvestmentState) -> dict[str, object]:
    basic_info = state.get("startup_basic_info", {})
    payload = json_response(
        load_prompt("report_writer_ko.txt"),
        {
            "startup_name": state.get("startup_name", ""),
            "startup_basic_info": basic_info,
            "team_assessment": state.get("team_assessment", {}),
            "tech_assessment": state.get("tech_assessment", {}),
            "market_assessment": state.get("market_assessment", {}),
            "roi_traction_assessment": state.get("roi_traction_assessment", {}),
            "business_model_assessment": state.get("business_model_assessment", {}),
            "safety_assessment": state.get("safety_assessment", {}),
            "competitor_assessment": state.get("competitor_assessment", {}),
            "decision": state.get("investment_decision", "hold"),
            "decision_reason": state.get("decision_reason", ""),
            "final_score": state.get("final_score", 0.0),
        },
    )
    return {
        "summary_short_ko": _as_text(payload.get("summary_short_ko"), "핵심 요약 미기재"),
        "decision_label_ko": _as_text(payload.get("decision_label_ko"), DECISION_LABELS.get(str(state.get("investment_decision", "hold")), "보류")),
        "decision_reason_ko": _as_text(payload.get("decision_reason_ko"), _as_text(state.get("decision_reason"))),
        "business_idea_ko": string_list(payload.get("business_idea_ko", [])),
        "business_risks_ko": string_list(payload.get("business_risks_ko", [])),
        "market_size_ko": string_list(payload.get("market_size_ko", [])),
        "team_composition_ko": string_list(payload.get("team_composition_ko", [])),
        "limitations_ko": string_list(payload.get("limitations_ko", [])),
    }


def _company_report(state: InvestmentState, llm_sections: dict[str, object]) -> str:
    basic_info = state.get("startup_basic_info", {})
    tech = state.get("tech_assessment", {})
    scorecard = state.get("scorecard", {})
    references = _company_references(state)

    lines = [
        f"# {state.get('startup_name', '')}",
        "",
        "## 기업 분석",
        *_company_overview_lines(basic_info),
        "",
        "### 사업 아이디어",
        *_bullets(_as_list(llm_sections.get("business_idea_ko"))),
        "",
        "### 사업 리스크",
        *_bullets(_as_list(llm_sections.get("business_risks_ko"))),
        "",
        "### 시장 규모",
        *_bullets(_as_list(llm_sections.get("market_size_ko"))),
        "",
        "### 팀의 구성",
        *_bullets(_as_list(llm_sections.get("team_composition_ko"))),
        "",
        "### 한계점",
        *_bullets(_as_list(llm_sections.get("limitations_ko"))),
        "",
        "### 투자 판단",
        f"- 결론: {_as_text(llm_sections.get('decision_label_ko'), DECISION_LABELS.get(str(state.get('investment_decision', 'hold')), '보류'))}",
        f"- 최종 점수: {float(state.get('final_score', 0.0)):.2f} / 5.00",
        f"- TRL: {_as_text(tech.get('trl_estimate'))}",
        f"- 판단 근거: {_as_text(llm_sections.get('decision_reason_ko'), _as_text(state.get('decision_reason')))}",
        "",
        "### 스코어카드",
        *_scorecard_table(scorecard, float(state.get("final_score", 0.0))),
        "",
        *_reference_sections(references),
    ]
    return "\n".join(lines)


def _summary_markdown(report_history: list[dict[str, object]]) -> str:
    sorted_items = sorted(report_history, key=lambda item: float(item.get("final_score", 0.0)), reverse=True)
    top_lines = [
        f"- {item['startup_name']}: {DECISION_LABELS.get(str(item.get('decision', 'hold')), '보류')} ({float(item.get('final_score', 0.0)):.2f}) - {_as_text(item.get('summary'), '핵심 근거 미기재')}"
        for item in sorted_items[:3]
    ]
    risk_summary = [
        "- 공통적으로 ROI 정량 근거와 시장 규모 근거가 약한 기업이 많았음",
        "- 기술 성숙도는 일부 기업에서 높았으나 규제·안전 인증 정보는 전반적으로 부족했음",
        "- 투자 추천은 기술 검증과 사업화 근거가 동시에 확보된 기업에 한정됨",
    ]
    lines = [
        "# SUMMARY",
        "",
        f"- 전체 평가 기업 수: {len(report_history)}",
        f"- 투자 추천 수: {sum(1 for item in report_history if item.get('decision') == 'invest')}",
        f"- 보류 수: {sum(1 for item in report_history if item.get('decision') != 'invest')}",
        "",
        "## 핵심 요약",
        *top_lines,
        "",
        "## 공통 시사점",
        *risk_summary,
    ]
    return "\n".join(lines)


def report_writer_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    llm_sections = _llm_company_sections(state)
    company_report = _company_report(state, llm_sections)
    report_history = [*state.get("report_history", [])]
    report_history.append(
        {
            "startup_name": startup_name,
            "decision": state.get("investment_decision", "hold"),
            "decision_label": DECISION_LABELS.get(str(state.get("investment_decision", "hold")), "보류"),
            "final_score": state.get("final_score", 0.0),
            "summary": llm_sections.get("summary_short_ko", _as_text(state.get("decision_reason"))),
            "report_content": company_report,
        }
    )
    return {
        "report_content": _summary_markdown(report_history),
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), startup_name],
    }
