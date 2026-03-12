from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from startup_search_agent import startup_search_node
from state import InvestmentState


def tech_evaluation_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    return {
        "tech_summary": (
            f"{startup_name}의 기술력, TRL, 특허, 제조 가능성 평가 노드 자리. "
            "현재는 stub이며 이후 실제 RAG/웹 리서치 로직을 연결한다."
        )
    }


def market_evaluation_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    return {
        "market_evaluation": (
            f"{startup_name}의 TAM/SAM/SOM, CAGR, 수요 구조 평가 노드 자리. "
            "현재는 stub이며 이후 시장 리포트 기반 분석을 연결한다."
        )
    }


def competitor_analysis_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    return {
        "competitor_analysis": (
            f"{startup_name}의 경쟁사 비교, 차별성, 진입장벽 분석 노드 자리. "
            "현재는 stub이며 이후 웹 검색 및 비교 로직을 연결한다."
        )
    }


def investment_decision_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    return {
        "scorecard": {},
        "final_score": 0.0,
        "investment_decision": "hold",
        "decision_reason": (
            f"{startup_name}의 기술/시장/경쟁 분석 결과가 모두 연결되면 "
            "이 노드에서 스코어카드와 투자 판단을 계산한다."
        ),
    }


def report_writer_node(state: InvestmentState) -> InvestmentState:
    startup_name = state["startup_name"]
    report_history = state.get("report_history", [])
    report_history.append(
        {
            "startup_name": startup_name,
            "decision": state.get("investment_decision", "hold"),
            "summary": state.get("decision_reason", ""),
        }
    )
    return {
        "report_content": (
            f"[{startup_name}] "
            f"{state.get('tech_summary', '')} "
            f"{state.get('market_evaluation', '')} "
            f"{state.get('competitor_analysis', '')} "
            f"{state.get('decision_reason', '')}"
        ),
        "report_history": report_history,
        "evaluated_startups": [*state.get("evaluated_startups", []), startup_name],
    }


def route_after_report(state: InvestmentState) -> str:
    remaining = [
        startup
        for startup in state.get("startup_list", [])
        if startup not in state.get("evaluated_startups", [])
    ]
    return "continue" if remaining else "end"


def build_investment_graph():
    graph_builder = StateGraph(InvestmentState)

    graph_builder.add_node("startup_search", startup_search_node)
    graph_builder.add_node("tech_evaluation", tech_evaluation_node)
    graph_builder.add_node("market_evaluation", market_evaluation_node)
    graph_builder.add_node("competitor_analysis", competitor_analysis_node)
    graph_builder.add_node("investment_decision", investment_decision_node)
    graph_builder.add_node("report_writer", report_writer_node)

    graph_builder.add_edge(START, "startup_search")
    graph_builder.add_edge("startup_search", "tech_evaluation")
    graph_builder.add_edge("startup_search", "market_evaluation")
    graph_builder.add_edge("startup_search", "competitor_analysis")
    graph_builder.add_edge("tech_evaluation", "investment_decision")
    graph_builder.add_edge("market_evaluation", "investment_decision")
    graph_builder.add_edge("competitor_analysis", "investment_decision")
    graph_builder.add_edge("investment_decision", "report_writer")
    graph_builder.add_conditional_edges(
        "report_writer",
        route_after_report,
        {
            "continue": "startup_search",
            "end": END,
        },
    )

    return graph_builder.compile()


graph = build_investment_graph()
