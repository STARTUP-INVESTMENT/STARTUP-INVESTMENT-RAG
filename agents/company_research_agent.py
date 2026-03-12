from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain_community.retrievers import TavilySearchAPIRetriever

from .startup_search_agent import load_env_file


DEFAULT_RESEARCH_CACHE_DIR = Path(".cache/company_research")
MAX_EXCERPT_CHARS = 2000
MAX_TAVILY_RESULTS_PER_QUERY = 3
MAX_MCP_RESULTS_PER_QUERY = 2
TECH_SEARCH_PATTERNS = (
    ("tech", "{name} robotics technology"),
    ("tech", "{name} humanoid robot"),
    ("tech", "{name} founder technology"),
    ("tech", "{name} github"),
    ("tech", "{name} demo"),
)
MARKET_SEARCH_PATTERNS = (
    ("funding", "{name} funding"),
    ("funding", "{name} raised seed funding"),
    ("roi", "{name} ROI case study"),
    ("roi", "{name} robotics payback"),
    ("roi", "{name} cost reduction automation"),
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "startup"


def snippet(title: str, url: str, excerpt: str, source_type: str) -> dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "source_type": source_type,
        "excerpt": excerpt[:MAX_EXCERPT_CHARS],
    }


def http_response_text(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[str, dict[str, str]]:
    payload = None
    request_headers = {"user-agent": "Mozilla/5.0", **(headers or {})}
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        request_headers.setdefault("content-type", "application/json")
    request = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="ignore")
        return body, dict(response.headers.items())


def unique_by_url(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in snippets:
        url = str(item.get("url", ""))
        source_type = str(item.get("source_type", ""))
        key = (url, source_type)
        if not url or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def tavily_api_key() -> str:
    load_env_file(Path.cwd() / ".env")
    return os.getenv("TAVILY_API_KEY", "").strip()


def tavily_search_results(query: str, *, max_results: int = MAX_TAVILY_RESULTS_PER_QUERY) -> list[dict[str, str]]:
    api_key = tavily_api_key()
    if not api_key:
        return []
    retriever = TavilySearchAPIRetriever(
        k=max_results,
        api_key=api_key,
        search_depth="advanced",
        include_generated_answer=False,
        include_raw_content=False,
    )
    documents = retriever.invoke(query)
    normalized: list[dict[str, str]] = []
    for doc in documents[:max_results]:
        metadata = getattr(doc, "metadata", {}) or {}
        content = getattr(doc, "page_content", "") or ""
        url = str(metadata.get("source") or metadata.get("url") or "").strip()
        if not url:
            continue
        normalized.append(
            {
                "title": str(metadata.get("title") or query).strip(),
                "url": url,
                "description": str(content).strip(),
            }
        )
    return normalized


def tavily_tech_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if not tavily_api_key():
        return []
    name = str(candidate.get("name", "")).strip()
    homepage = str(candidate.get("url", "")).strip() or "https://api.tavily.com/search"
    sources: list[dict[str, Any]] = []
    for category, pattern in TECH_SEARCH_PATTERNS:
        query = pattern.format(name=name)
        try:
            results = tavily_search_results(query)
        except Exception as exc:
            sources.append(
                snippet(
                    title=f"{name} {category} Tavily search failed",
                    url=homepage,
                    excerpt=f"query={query}\nTavily search failed: {exc}",
                    source_type=f"tavily_search_error:{category}",
                )
            )
            continue
        for result in results:
            sources.append(
                snippet(
                    title=result["title"] or f"{name} {category} search result",
                    url=result["url"],
                    excerpt=f"query={query}\n{result['description']}",
                    source_type=f"tavily_search:{category}",
                )
            )
    return unique_by_url(sources)


def brightdata_mcp_base_url() -> str:
    load_env_file(Path.cwd() / ".env")
    direct_url = os.getenv("BRIGHTDATA_MCP_URL", "").strip()
    if direct_url:
        return direct_url
    token = os.getenv("BRIGHTDATA_MCP_TOKEN", "").strip()
    if token:
        return f"https://mcp.brightdata.com/mcp?token={token}"
    return ""


def _parse_mcp_event(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                continue
    return {}


def brightdata_mcp_rpc(base_url: str, payload: dict[str, Any], *, session_id: str = "") -> tuple[dict[str, Any], dict[str, str]]:
    headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    if session_id:
        headers["mcp-session-id"] = session_id
    body, response_headers = http_response_text(base_url, method="POST", headers=headers, data=payload)
    return _parse_mcp_event(body), response_headers


def brightdata_mcp_session(base_url: str) -> str:
    response, headers = brightdata_mcp_rpc(
        base_url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "robotics-investment-agent", "version": "0.1"},
            },
        },
    )
    session_id = headers.get("mcp-session-id", "")
    if not session_id or response.get("error"):
        raise RuntimeError(response.get("error", {}).get("message", "Bright Data MCP initialize failed"))
    brightdata_mcp_rpc(
        base_url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id=session_id,
    )
    return session_id


def brightdata_search_results(base_url: str, session_id: str, query: str) -> list[dict[str, str]]:
    response, _ = brightdata_mcp_rpc(
        base_url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_engine", "arguments": {"query": query, "engine": "google"}},
        },
        session_id=session_id,
    )
    result = response.get("result", {})
    if result.get("isError"):
        return []
    content = result.get("content", [])
    if not isinstance(content, list) or not content:
        return []
    payload = json.loads(str(content[0].get("text", "")))
    organic = payload.get("organic", [])
    if not isinstance(organic, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in organic[:MAX_MCP_RESULTS_PER_QUERY]:
        url = str(item.get("link", "")).strip()
        if not url:
            continue
        normalized.append(
            {
                "title": str(item.get("title", "")).strip(),
                "url": url,
                "description": str(item.get("description", "")).strip(),
            }
        )
    return normalized


def mcp_market_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = brightdata_mcp_base_url()
    if not base_url:
        return []
    name = str(candidate.get("name", "")).strip()
    homepage = str(candidate.get("url", "")).strip() or base_url
    try:
        session_id = brightdata_mcp_session(base_url)
    except Exception as exc:
        return [
            snippet(
                title=f"{name} Bright Data MCP unavailable",
                url=homepage,
                excerpt=f"Bright Data MCP request failed: {exc}",
                source_type="mcp_error",
            )
        ]

    sources: list[dict[str, Any]] = []
    for category, pattern in MARKET_SEARCH_PATTERNS:
        query = pattern.format(name=name)
        try:
            results = brightdata_search_results(base_url, session_id, query)
        except Exception as exc:
            sources.append(
                snippet(
                    title=f"{name} {category} MCP search failed",
                    url=homepage,
                    excerpt=f"query={query}\nBright Data MCP search failed: {exc}",
                    source_type=f"mcp_search_error:{category}",
                )
            )
            continue
        for result in results:
            sources.append(
                snippet(
                    title=result["title"] or f"{name} {category} search result",
                    url=result["url"],
                    excerpt=f"query={query}\n{result['description']}",
                    source_type=f"mcp_search:{category}",
                )
            )
    return unique_by_url(sources)


def merge_research_state(
    state: dict[str, Any],
    *,
    prefix: str,
    startup_name: str,
    cache_path: Path,
    snippets: list[dict[str, Any]],
) -> dict[str, Any]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(snippets, ensure_ascii=False, indent=2))

    summary = (
        f"{startup_name}에 대해 {len(snippets)}개의 {prefix} 근거 스니펫을 수집했다. "
        f"주요 출처는 {', '.join(item['source_type'] for item in snippets[:3]) or '없음'}."
    )
    source_rows = [
        {"title": item["title"], "url": item["url"], "source_type": item["source_type"]}
        for item in snippets
    ]
    return {
        f"{prefix}_research_cache_path": str(cache_path),
        f"{prefix}_research_summary": summary,
        f"{prefix}_research_sources": source_rows,
        f"{prefix}_research_snippets": snippets,
        "research_sources": unique_by_url([*state.get("research_sources", []), *source_rows]),
        "research_snippets": unique_by_url([*state.get("research_snippets", []), *snippets]),
        "rag_sources": [*state.get("rag_sources", []), *[item["url"] for item in snippets if item.get("url")]],
    }
