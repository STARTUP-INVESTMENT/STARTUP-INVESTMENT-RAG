from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .investment_decision_agent import investment_decision_node
from .market_research_agent import market_research_node
from .mcp_scorecard_agent import mcp_scorecard_node
from .report_writer_agent import report_writer_node
from .startup_search_agent import startup_search_node
from .state import InvestmentState
from .tech_research_agent import tech_research_node
from .tavily_scorecard_agent import tavily_scorecard_node


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
    graph_builder.add_node("tech_research", tech_research_node)
    graph_builder.add_node("market_research", market_research_node)
    graph_builder.add_node("tavily_scorecard", tavily_scorecard_node)
    graph_builder.add_node("mcp_scorecard", mcp_scorecard_node)
    graph_builder.add_node("investment_decision", investment_decision_node)
    graph_builder.add_node("report_writer", report_writer_node)

    graph_builder.add_edge(START, "startup_search")
    graph_builder.add_edge("startup_search", "tech_research")
    graph_builder.add_edge("tech_research", "market_research")
    graph_builder.add_edge("market_research", "tavily_scorecard")
    graph_builder.add_edge("tavily_scorecard", "mcp_scorecard")
    graph_builder.add_edge("mcp_scorecard", "investment_decision")
    graph_builder.add_edge("investment_decision", "report_writer")
    graph_builder.add_conditional_edges(
        "report_writer",
        route_after_report,
        {"continue": "startup_search", "end": END},
    )

    return graph_builder.compile()


graph = build_investment_graph()
