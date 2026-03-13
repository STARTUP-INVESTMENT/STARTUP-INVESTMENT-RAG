from __future__ import annotations

from typing import Any

from core.agent_utils import current_candidate, json_response, string_list
from core.prompt_loader import load_prompt
from core.state import InvestmentState
import time
from infra.market_vectorstore import load_or_build_vectorstore, retrieve_relevant_context
from infra.research_utils import (
    save_research_cache,
    snippet,
    source_rows,
    summarize_research,
    tavily_search_results,
    unique_sources,
)


TECH_SEARCH_PATTERNS = (
    ("team", "{name} founders robotics"),
    ("tech", "{name} robotics technology"),
    ("safety", "{name} safety certification robotics"),
)


def _build_tech_query(state: InvestmentState, candidate: dict[str, Any]) -> str:
    sector = str(candidate.get("sector", "")).strip()
    tags = " ".join(str(tag) for tag in (candidate.get("tags") or []) if str(tag).strip())
    description = str(candidate.get("description", "")).strip()[:300]
    user_query = str(state.get("user_query", "")).strip()
    return " ".join(
        part
        for part in [
            str(candidate.get("name", "")).strip(),
            sector,
            tags,
            description,
            "founder team TRL manufacturing safety certification regulation robotics",
            user_query,
        ]
        if part
    )


def _tavily_tech_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    name = str(candidate.get("name", "")).strip()
    homepage = str(candidate.get("url", "")).strip() or "https://tavily.com"
    snippets: list[dict[str, Any]] = []
    for category, pattern in TECH_SEARCH_PATTERNS:
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


def _technology_score(trl_level: int, manufacturing_readiness: str) -> float:
    if trl_level <= 2:
        base = 1.0
    elif trl_level <= 4:
        base = 2.0
    elif trl_level == 5:
        base = 3.0
    elif trl_level == 6:
        base = 3.5
    elif trl_level == 7:
        base = 4.0
    elif trl_level == 8:
        base = 4.5
    else:
        base = 5.0

    readiness = manufacturing_readiness.lower()
    if any(term in readiness for term in ["high", "qualified", "production", "mass"]):
        base += 0.3
    elif any(term in readiness for term in ["low", "insufficient", "prototype", "none"]):
        base -= 0.2
    return max(1.0, min(5.0, round(base, 2)))


def tech_evaluation_node(state: InvestmentState) -> InvestmentState:
    start = time.time()
    print("Starting tech evaluation...")
    candidate =current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    research_snippets = _tavily_tech_sources(candidate)
    research_cache_path = save_research_cache(startup_name, "tech_research", research_snippets)
    vectorstore = load_or_build_vectorstore()
    vector_context = ""
    if vectorstore is not None:
        vector_context = retrieve_relevant_context(vectorstore, _build_tech_query(state, candidate), k=6)

    payload = json_response(
        load_prompt("tech_evaluation.txt"),
        {
            "startup_name": startup_name,
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "research_summary": summarize_research(startup_name, "기술", research_snippets),
            "research_snippets": research_snippets[:8],
            "vector_context": vector_context,
        },
    )
    team_assessment = {
        "summary": payload.get("team_assessment", {}).get("summary", ""),
        "evidence": string_list(payload.get("team_assessment", {}).get("evidence", [])),
        "risks": string_list(payload.get("team_assessment", {}).get("risks", [])),
        "evidence_gaps": string_list(payload.get("team_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("team_assessment", {}).get("score_1_to_5", 2.5)),
    }
    tech_assessment = {
        "summary": payload.get("tech_assessment", {}).get("summary", ""),
        "trl_level": int(payload.get("tech_assessment", {}).get("trl_level", 3)),
        "trl_basis": payload.get("tech_assessment", {}).get("trl_basis", ""),
        "trl_exit_criteria_met": payload.get("tech_assessment", {}).get("trl_exit_criteria_met", {}),
        "trl_estimate": f"TRL {int(payload.get('tech_assessment', {}).get('trl_level', 3))}",
        "manufacturing_readiness": payload.get("tech_assessment", {}).get("manufacturing_readiness", "insufficient_data"),
        "key_strengths": string_list(payload.get("tech_assessment", {}).get("evidence", [])),
        "key_risks": string_list(payload.get("tech_assessment", {}).get("risks", [])),
        "evidence_gaps": string_list(payload.get("tech_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": _technology_score(
            int(payload.get("tech_assessment", {}).get("trl_level", 3)),
            str(payload.get("tech_assessment", {}).get("manufacturing_readiness", "insufficient_data")),
        ),
    }
    safety_assessment = {
        "summary": payload.get("safety_assessment", {}).get("summary", ""),
        "certifications": string_list(payload.get("safety_assessment", {}).get("certifications", [])),
        "regulation_status": payload.get("safety_assessment", {}).get("regulation_status", "insufficient_data"),
        "compliance_risks": string_list(payload.get("safety_assessment", {}).get("compliance_risks", [])),
        "evidence_gaps": string_list(payload.get("safety_assessment", {}).get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("safety_assessment", {}).get("score_1_to_5", 2.5)),
    }
    summary = (
        f"팀 평가: {team_assessment['summary']} "
        f"기술 평가: {tech_assessment['summary']} "
        f"안전/규제: {safety_assessment['summary']}"
    )

    end = time.time()
    print(f"Tech evaluation for {startup_name} completed in {end - start:.2f} seconds")

    return {
        "tech_research_cache_path": str(research_cache_path),
        "tech_research_summary": summarize_research(startup_name, "기술", research_snippets),
        "tech_research_sources": source_rows(research_snippets),
        "tech_research_snippets": research_snippets,
        "team_assessment": team_assessment,
        "trl_level": tech_assessment["trl_level"],
        "tech_assessment": tech_assessment,
        "tech_summary": summary,
        "safety_assessment": safety_assessment,
    }
