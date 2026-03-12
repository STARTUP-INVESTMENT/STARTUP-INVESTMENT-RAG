from __future__ import annotations

from typing import Any

from .agent_utils import current_candidate, json_response, string_list
from .market_vectorstore import load_or_build_vectorstore, retrieve_market_context
from .prompt_loader import load_prompt
from .state import InvestmentState


def _build_market_query(state: InvestmentState, candidate: dict[str, Any]) -> str:
    """스타트업의 섹터·태그·설명·사용자 쿼리를 조합해 벡터 검색 쿼리를 만든다."""
    sector = candidate.get("sector", "")
    tags = " ".join(str(t) for t in (candidate.get("tags") or []) if t)
    description = str(candidate.get("description", ""))[:200]
    user_query = state.get("user_query", "")
    return " ".join(part for part in [sector, tags, description, user_query] if part)


def market_evaluation_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)

    # RAG: data/ 폴더의 PDF로 빌드된 FAISS 인덱스에서 관련 시장 데이터 검색
    vectorstore = load_or_build_vectorstore()
    market_context = ""
    if vectorstore is not None:
        query = _build_market_query(state, candidate)
        market_context = retrieve_market_context(vectorstore, query)

    payload = json_response(
        load_prompt("market_evaluation.txt"),
        {
            "startup_name": state["startup_name"],
            "user_query": state.get("user_query", ""),
            "startup_basic_info": candidate,
            "domain_context": "Robotics market with focus on labor shortage, automation, AI-robotics convergence, and ROI sensitivity.",
            "market_context": market_context,
        },
    )
    assessment = {
        "summary": payload.get("summary", ""),
        "target_market": payload.get("target_market", ""),
        "demand_drivers": string_list(payload.get("demand_drivers", [])),
        "market_maturity": payload.get("market_maturity", "insufficient_data"),
        "estimate_range": payload.get("estimate_range", "insufficient_data"),
        "evidence_gaps": string_list(payload.get("evidence_gaps", [])),
        "score_1_to_5": float(payload.get("score_1_to_5", 2.5)),
    }
    summary = (
        f"시장 평가: {assessment['summary']} "
        f"타깃 시장: {assessment['target_market'] or 'insufficient_data'}. "
        f"수요 동인: {', '.join(assessment['demand_drivers'][:3]) or 'insufficient_data'}."
    )
    return {
        "market_context": market_context,
        "market_assessment": assessment,
        "market_evaluation": summary,
    }
