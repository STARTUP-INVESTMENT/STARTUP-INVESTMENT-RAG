from __future__ import annotations

from pathlib import Path

from .agent_utils import current_candidate
from .company_research_agent import (
    DEFAULT_RESEARCH_CACHE_DIR,
    faiss_tech_sources,
    merge_research_state,
    slugify,
)
from .state import InvestmentState


def tech_research_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    cache_path = DEFAULT_RESEARCH_CACHE_DIR / slugify(startup_name) / "tech_research.json"
    snippets = faiss_tech_sources(state, candidate)

    return merge_research_state(
        state,
        prefix="tech",
        startup_name=startup_name,
        cache_path=cache_path,
        snippets=snippets,
    )
