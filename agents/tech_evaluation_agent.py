from __future__ import annotations

from .agent_utils import current_candidate, json_response, string_list
from .prompt_loader import load_prompt
from .state import InvestmentState
import requests

# -----------------------------
# 기술 점수 계산 함수
# -----------------------------
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

# -----------------------------
# FAISS 서버 검색 함수
# -----------------------------
def search_faiss(query: str, top_k: int = 1) -> list[dict]:
    """
    FAISS 서버에 질의하고 top_k 유사 문서 반환
    각 문서는 {"filename": ..., "content": ...} 형태
    """
    try:
        resp = requests.post("http://localhost:8000/search", json={"text": query, "top_k": top_k})
        if resp.status_code == 200:
            print(resp)
            return resp.json().get("results", [])
        else:
            print(f"FAISS search failed: {resp.status_code}")
            return []
    except Exception as e:
        print(f"Error connecting to FAISS server: {e}")
        return []

# -----------------------------
# 기술 평가 노드
# -----------------------------
def tech_evaluation_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)

    # 1. FAISS에서 관련 문서 검색
    user_query = state.get("user_query", "")
    related_docs = search_faiss(user_query, top_k=5)

    # 문서 내용을 research_snippets에 넣고
    # 파일명만 related_documents에 넣음
    research_snippets = [doc["content"] for doc in related_docs]
    related_documents = [doc["filename"] for doc in related_docs]

    # 2. LLM payload 생성
    payload = json_response(
        load_prompt("tech_evaluation.txt"),
        {
            "startup_name": state["startup_name"],
            "user_query": user_query,
            "startup_basic_info": candidate,
            "research_summary": state.get("research_summary", ""),
            "research_snippets": research_snippets[:5],  # 상위 5개 문서만 사용
            "related_documents": related_documents[:5],
        },
    )

    # 3. 평가 생성
    assessment = {
        "summary": payload.get("summary", ""),
        "trl_level": int(payload.get("trl_level", 3)),
        "trl_basis": payload.get("trl_basis", ""),
        "trl_exit_criteria_met": payload.get("trl_exit_criteria_met", {}),
        "trl_estimate": f"TRL {int(payload.get('trl_level', 3))}",
        "manufacturing_readiness": payload.get("manufacturing_readiness", "insufficient_data"),
        "key_strengths": string_list(payload.get("key_strengths", [])),
        "key_risks": string_list(payload.get("key_risks", [])),
        "evidence_gaps": string_list(payload.get("evidence_gaps", [])),
        "score_1_to_5": _technology_score(
            int(payload.get("trl_level", 3)),
            str(payload.get("manufacturing_readiness", "insufficient_data")),
        ),
    }

    # 4. 요약 생성
    summary = (
        f"기술 요약: {assessment['summary']} "
        f"TRL 추정: {assessment['trl_estimate']} ({assessment['trl_basis']}). "
        f"양산 준비도: {assessment['manufacturing_readiness']}. "
        f"핵심 리스크: {', '.join(assessment['key_risks'][:3]) or 'insufficient_data'}."
    )

    return {"trl_level": assessment["trl_level"], "tech_assessment": assessment, "tech_summary": summary}