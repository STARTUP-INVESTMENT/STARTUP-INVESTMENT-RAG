from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.competitor_analysis_agent import competitor_analysis_node
from agents.investment_decision_agent import investment_decision_node
from agents.market_evaluation_agent import market_evaluation_node
from agents.report_writer_agent import collect_company_result_node, report_writer_node
from agents.startup_search_agent import startup_search_node
from core.state import InvestmentState
from agents.tech_evaluation_agent import tech_evaluation_node


def route_after_collect(state: InvestmentState) -> str:
    remaining = [
        startup
        for startup in state.get("startup_list", [])
        if startup not in state.get("evaluated_startups", [])
    ]
    return "continue" if remaining else "finalize"


def build_investment_graph():
    graph_builder = StateGraph(InvestmentState)

    graph_builder.add_node("startup_search", startup_search_node)
    graph_builder.add_node("tech_evaluation", tech_evaluation_node)
    graph_builder.add_node("market_evaluation", market_evaluation_node)
    graph_builder.add_node("competitor_analysis", competitor_analysis_node)
    graph_builder.add_node("investment_decision", investment_decision_node)
    graph_builder.add_node("collect_company_result", collect_company_result_node)
    graph_builder.add_node("report_writer", report_writer_node)

    graph_builder.add_edge(START, "startup_search")
    graph_builder.add_edge("startup_search", "tech_evaluation")
    graph_builder.add_edge("startup_search", "market_evaluation")
    graph_builder.add_edge("startup_search", "competitor_analysis")
    graph_builder.add_edge("tech_evaluation", "investment_decision")
    graph_builder.add_edge("market_evaluation", "investment_decision")
    graph_builder.add_edge("competitor_analysis", "investment_decision")
    graph_builder.add_edge("investment_decision", "collect_company_result")
    graph_builder.add_conditional_edges(
        "collect_company_result",
        route_after_collect,
        {"continue": "startup_search", "finalize": "report_writer"},
    )
    graph_builder.add_edge("report_writer", END)

    return graph_builder.compile()


graph = build_investment_graph()
