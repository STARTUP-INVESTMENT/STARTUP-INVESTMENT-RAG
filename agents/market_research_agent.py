from __future__ import annotations

from pathlib import Path

from .agent_utils import current_candidate
from .company_research_agent import (
    DEFAULT_RESEARCH_CACHE_DIR,
    faiss_market_sources,
    merge_research_state,
    slugify,
)
from .state import InvestmentState


def market_research_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    cache_path = DEFAULT_RESEARCH_CACHE_DIR / slugify(startup_name) / "market_research.json"
    snippets = faiss_market_sources(state, candidate)

    return merge_research_state(
        state,
        prefix="market",
        startup_name=startup_name,
        cache_path=cache_path,
        snippets=snippets,
    )
