from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .company_research_agent import company_research_node
from .competitor_analysis_agent import competitor_analysis_node
from .investment_decision_agent import investment_decision_node
from .market_evaluation_agent import market_evaluation_node
from .report_writer_agent import report_writer_node
from .startup_search_agent import startup_search_node
from .state import InvestmentState
from .tech_evaluation_agent import tech_evaluation_node


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
    graph_builder.add_node("company_research", company_research_node)
    graph_builder.add_node("tech_evaluation", tech_evaluation_node)
    graph_builder.add_node("market_evaluation", market_evaluation_node)
    graph_builder.add_node("competitor_analysis", competitor_analysis_node)
    graph_builder.add_node("investment_decision", investment_decision_node)
    graph_builder.add_node("report_writer", report_writer_node)

    graph_builder.add_edge(START, "startup_search")
    graph_builder.add_edge("startup_search", "company_research")
    graph_builder.add_edge("company_research", "tech_evaluation")
    graph_builder.add_edge("company_research", "market_evaluation")
    graph_builder.add_edge("company_research", "competitor_analysis")
    graph_builder.add_edge("tech_evaluation", "investment_decision")
    graph_builder.add_edge("market_evaluation", "investment_decision")
    graph_builder.add_edge("competitor_analysis", "investment_decision")
    graph_builder.add_edge("investment_decision", "report_writer")
    graph_builder.add_conditional_edges(
        "report_writer",
        route_after_report,
        {"continue": "startup_search", "end": END},
    )

    return graph_builder.compile()


graph = build_investment_graph()
