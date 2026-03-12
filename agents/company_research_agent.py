from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain_teddynote.tools.tavily import TavilySearch

from .agent_utils import current_candidate
from .startup_search_agent import _http_text, fetch_innoforest_company_profile, load_env_file
from .state import InvestmentState


DEFAULT_RESEARCH_CACHE_DIR = Path(".cache/company_research")
MAX_EXCERPT_CHARS = 2000
TAVILY_MAX_RESULTS = 3
SEARCH_QUERIES = (
    "{name} robotics startup",
    "{name} founder technology investment",
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "startup"


def _clean_html_text(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;|&#160;", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _snippet(title: str, url: str, excerpt: str, source_type: str) -> dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "source_type": source_type,
        "excerpt": excerpt[:MAX_EXCERPT_CHARS],
    }


def _unique_by_url(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for snippet in snippets:
        url = str(snippet.get("url", ""))
        source_type = str(snippet.get("source_type", ""))
        key = (url, source_type)
        if not url or key in seen:
            continue
        seen.add(key)
        deduped.append(snippet)
    return deduped


def _tavily_search_snippets(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    load_env_file(Path.cwd() / ".env")
    tavily_tool = TavilySearch()
    name = str(candidate.get("name", "")).strip()
    snippets: list[dict[str, Any]] = []
    for query_pattern in SEARCH_QUERIES:
        query = query_pattern.format(name=name)
        try:
            results = tavily_tool.search(
                query=query,
                topic="general",
                max_results=TAVILY_MAX_RESULTS,
                format_output=False,
            )
            if isinstance(results, list):
                for item in results:
                    url = str(item.get("url", ""))
                    title = str(item.get("title", query))
                    content = str(item.get("content", ""))
                    if content:
                        snippets.append(
                            _snippet(
                                title=title,
                                url=url,
                                excerpt=f"query={query}\n{content}",
                                source_type=f"tavily_search:{urlparse(url).netloc}",
                            )
                        )
            elif isinstance(results, str) and results:
                snippets.append(
                    _snippet(
                        title=f"{name} web search: {query}",
                        url="",
                        excerpt=f"query={query}\n{results}",
                        source_type="tavily_search",
                    )
                )
        except Exception:
            continue
    return snippets


def _candidate_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    description = candidate.get("description", "")
    if description:
        sources.append(
            _snippet(
                title=f"{candidate.get('name', '')} candidate profile",
                url=str(candidate.get("url", "")),
                excerpt=str(description),
                source_type="candidate_profile",
            )
        )

    url = str(candidate.get("url", "")).strip()
    if not url:
        return sources

    try:
        if "innoforest.co.kr" in url:
            profile = fetch_innoforest_company_profile(url)
            excerpt = " ".join(
                str(profile.get(key, "") or "")
                for key in ["intro", "identity_keywords", "product_name", "category_name", "meta_description"]
            ).strip()
            if excerpt:
                sources.append(
                    _snippet(
                        title=f"{profile.get('name', candidate.get('name', ''))} innoforest profile",
                        url=url,
                        excerpt=excerpt,
                        source_type="innoforest_profile",
                    )
                )
        html = _http_text(url, timeout=15)
        clean_text = _clean_html_text(html)
        if clean_text:
            host = urlparse(url).netloc
            sources.append(
                _snippet(
                    title=f"{candidate.get('name', '')} website",
                    url=url,
                    excerpt=clean_text,
                    source_type=f"webpage:{host}",
                )
            )
    except Exception as exc:
        sources.append(
            _snippet(
                title=f"{candidate.get('name', '')} fetch error",
                url=url,
                excerpt=f"source fetch failed: {exc}",
                source_type="fetch_error",
            )
        )

    sources.extend(_tavily_search_snippets(candidate))

    return _unique_by_url(sources)


def company_research_node(state: InvestmentState) -> InvestmentState:
    candidate = current_candidate(state)
    startup_name = str(candidate.get("name", state.get("startup_name", "")))
    startup_slug = _slugify(startup_name)
    cache_dir = DEFAULT_RESEARCH_CACHE_DIR / startup_slug
    cache_path = cache_dir / "research.json"

    snippets = _candidate_sources(candidate)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(snippets, ensure_ascii=False, indent=2))

    research_summary = (
        f"{startup_name}에 대해 {len(snippets)}개의 근거 스니펫을 수집했다. "
        f"주요 출처는 {', '.join(snippet['source_type'] for snippet in snippets[:3]) or '없음'}."
    )
    return {
        "research_cache_path": str(cache_path),
        "research_summary": research_summary,
        "research_sources": [
            {"title": snippet["title"], "url": snippet["url"], "source_type": snippet["source_type"]}
            for snippet in snippets
        ],
        "research_snippets": snippets,
        "rag_sources": [*state.get("rag_sources", []), *[snippet["url"] for snippet in snippets if snippet.get("url")]],
    }
