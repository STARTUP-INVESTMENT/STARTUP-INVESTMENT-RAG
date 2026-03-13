from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse

from core.agent_utils import string_list
from core.prompt_loader import load_prompt
from core.state import InvestmentState
from agents.startup_search_agent import build_openai_client


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


def _as_text(value: object, default: str = "미기재") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


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


def _reference_line(source: dict[str, object]) -> str:
    title = _as_text(source.get("title"), "제목 미상")
    url = _as_text(source.get("url"), "")
    source_type = _source_kind(url, title)
    year = _extract_year(f"{title} {url}")
    org = _org_name(url, title)
    if source_type == "report":
        return f"- {org}({year}). *{title}*. {url}"
    if source_type == "paper":
        return f"- {org}({year}). {title}. *학술지명 미상*, 권(호) 미상, 페이지 미상."
    return f"- {org}({year if year != '연도 미상' else REPORT_DATE.isoformat()}). *{title}*. {_site_name(url)}, {url}"


def _reference_payload(sources: list[dict[str, object]]) -> dict[str, list[str]]:
    buckets = {"기관 보고서": [], "학술 논문": [], "웹페이지": []}
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (str(source.get("title", "")), str(source.get("url", "")))
        if key in seen:
            continue
        seen.add(key)
        kind = _source_kind(str(source.get("url", "")), str(source.get("title", "")))
        if kind == "report":
            buckets["기관 보고서"].append(_reference_line(source))
        elif kind == "paper":
            buckets["학술 논문"].append(_reference_line(source))
        else:
            buckets["웹페이지"].append(_reference_line(source))
    return buckets


def _final_reference_payload(report_history: list[dict[str, object]]) -> dict[str, list[str]]:
    all_sources: list[dict[str, object]] = []
    for item in report_history:
        all_sources.extend(item.get("references", []))
    return _reference_payload(all_sources)


def _scorecard_rows(scorecard: dict[str, float], final_score: float) -> list[dict[str, object]]:
    rows = []
    for key, label in SCORECARD_LABELS.items():
        score = float(scorecard.get(key, 0.0))
        weight = {"team_founders": 20, "market_opportunity": 20, "technology_production": 30, "competition_moat": 10, "customer_roi_traction": 10, "safety_regulation": 5, "business_model": 5}[key]
        rows.append({"label": label, "score": round(score, 2), "weight_percent": weight, "weighted_score": round(score * weight / 100, 2)})
    rows.append({"label": "총점", "score": "", "weight_percent": 100, "weighted_score": round(final_score, 2)})
    return rows


def _company_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "startup_name": item.get("startup_name", ""),
        "decision": DECISION_LABELS.get(str(item.get("decision", "hold")), "보류"),
        "final_score": item.get("final_score", 0.0),
        "startup_basic_info": item.get("startup_basic_info", {}),
        "team_assessment": item.get("team_assessment", {}),
        "tech_assessment": item.get("tech_assessment", {}),
        "market_assessment": item.get("market_assessment", {}),
        "roi_traction_assessment": item.get("roi_traction_assessment", {}),
        "business_model_assessment": item.get("business_model_assessment", {}),
        "safety_assessment": item.get("safety_assessment", {}),
        "competitor_assessment": item.get("competitor_assessment", {}),
        "decision_reason": item.get("decision_reason", ""),
        "scorecard_rows": _scorecard_rows(item.get("scorecard", {}), float(item.get("final_score", 0.0) or 0.0)),
    }


def _collect_company_result(state: InvestmentState) -> InvestmentState:
    report_history = [*state.get("report_history", [])]
    report_history.append(
        {
            "startup_name": state.get("startup_name", ""),
            "decision": state.get("investment_decision", "hold"),
            "final_score": state.get("final_score", 0.0),
            "decision_reason": state.get("decision_reason", ""),
            "startup_basic_info": state.get("startup_basic_info", {}),
            "team_assessment": state.get("team_assessment", {}),
            "tech_assessment": state.get("tech_assessment", {}),
            "market_assessment": state.get("market_assessment", {}),
            "roi_traction_assessment": state.get("roi_traction_assessment", {}),
            "business_model_assessment": state.get("business_model_assessment", {}),
            "safety_assessment": state.get("safety_assessment", {}),
            "competitor_assessment": state.get("competitor_assessment", {}),
            "scorecard": state.get("scorecard", {}),
            "references": [
                *state.get("tech_research_sources", []),
                *state.get("market_research_sources", []),
                *state.get("competitor_research_sources", []),
            ],
        }
    )
    return {
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), state.get("startup_name", "")],
    }


def _generate_final_markdown(report_history: list[dict[str, object]]) -> str:
    client = build_openai_client()
    payload = {
        "companies": [_company_payload(item) for item in report_history],
        "final_references": _final_reference_payload(report_history),
        "report_date": REPORT_DATE.isoformat(),
    }
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": load_prompt("report_writer_ko.txt")},
            {"role": "user", "content": str(payload)},
        ],
    )
    return response.output_text.strip()


def report_writer_node(state: InvestmentState) -> InvestmentState:
    report_history = [*state.get("report_history", [])]
    final_markdown = _generate_final_markdown(report_history)
    return {"report_content": final_markdown}


def collect_company_result_node(state: InvestmentState) -> InvestmentState:
    return _collect_company_result(state)
