from __future__ import annotations

from core.agent_utils import current_candidate, json_response, string_list
from core.prompt_loader import load_prompt
from core.state import InvestmentState
from infra.research_utils import save_research_cache, snippet, source_rows, summarize_research, tavily_search_results, unique_sources


COMPETITOR_SEARCH_PATTERNS = (
    ("competition", "{name} robotics competitors"),
)


def _competitor_sources(candidate: dict[str, object]) -> list[dict[str, object]]:
    name = str(candidate.get("name", "")).strip()
    homepage = str(candidate.get("url", "")).strip() or "https://tavily.com"
    snippets: list[dict[str, object]] = []
    for category, pattern in COMPETITOR_SEARCH_PATTERNS:
        query = pattern.format(name=name)
        try:
            results = tavily_search_results(query)
        except Exception as exc:
            snippets.append(
                snippet(
                    title=f"{name} {category} Tavily search failed",
                    url=homepage,
                    excerpt=f"query={query}\nTavily search failed: {exc}",
                    source_type=f"tavily_search_error:{category}",
                )
            )
            continue
        for result in results:
            snippets.append(
                snippet(
                    title=result["title"] or f"{name} {category} search result",
                    url=result["url"],
                    excerpt=f"query={query}\n{result['description']}",
                    source_type=f"tavily_search:{category}",
                )
            )
    return unique_sources(snippets)


def competitor_analysis_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    research_snippets = _competitor_sources(candidate)
    research_cache_path = save_research_cache(startup_name, "competitor_research", research_snippets)
    peer_candidates = [item for item in state.get("startup_candidates", []) if item["name"] != state["startup_name"]][:8]
    payload = json_response(
        load_prompt("competitor_analysis.txt"),
        {
            "startup_name": startup_name,
            "startup_basic_info": candidate,
            "peer_candidates": peer_candidates,
            "research_summary": summarize_research(startup_name, "경쟁", research_snippets),
            "research_snippets": research_snippets[:8],
        },
    )
    assessment = {
        "summary": payload.get("summary", ""),
        "closest_competitors": string_list(payload.get("closest_competitors", [])),
        "differentiation": string_list(payload.get("differentiation", [])),
        "moat_signals": string_list(payload.get("moat_signals", [])),
        "competitive_risks": string_list(payload.get("competitive_risks", [])),
        "evidence_gaps": string_list(payload.get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("score_1_to_5", 2.5)),
    }
    summary = (
        f"경쟁 분석: {assessment['summary']} "
        f"근접 경쟁사: {', '.join(assessment['closest_competitors'][:3]) or 'insufficient_data'}. "
        f"차별화: {', '.join(assessment['differentiation'][:3]) or 'insufficient_data'}."
    )
    return {
        "competitor_research_cache_path": str(research_cache_path),
        "competitor_research_summary": summarize_research(startup_name, "경쟁", research_snippets),
        "competitor_research_sources": source_rows(research_snippets),
        "competitor_research_snippets": research_snippets,
        "competitor_assessment": assessment,
        "competitor_analysis": summary,
    }
