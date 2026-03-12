from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from langchain_community.retrievers import TavilySearchAPIRetriever

from agents.startup_search_agent import load_env_file


DEFAULT_RESEARCH_CACHE_DIR = Path(".cache/company_research")
MAX_EXCERPT_CHARS = 2000
MAX_TAVILY_RESULTS_PER_QUERY = 3
MAX_MCP_RESULTS_PER_QUERY = 3


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


def _http_response_text(
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


def unique_sources(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in snippets:
        url = str(item.get("url", "")).strip()
        source_type = str(item.get("source_type", "")).strip()
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


def _brightdata_mcp_rpc(base_url: str, payload: dict[str, Any], *, session_id: str = "") -> tuple[dict[str, Any], dict[str, str]]:
    headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    if session_id:
        headers["mcp-session-id"] = session_id
    body, response_headers = _http_response_text(base_url, method="POST", headers=headers, data=payload)
    return _parse_mcp_event(body), response_headers


def _brightdata_mcp_session(base_url: str) -> str:
    response, headers = _brightdata_mcp_rpc(
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
    _brightdata_mcp_rpc(
        base_url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id=session_id,
    )
    return session_id


def mcp_search_results(query: str, *, max_results: int = MAX_MCP_RESULTS_PER_QUERY) -> list[dict[str, str]]:
    base_url = brightdata_mcp_base_url()
    if not base_url:
        return []
    session_id = _brightdata_mcp_session(base_url)
    response, _ = _brightdata_mcp_rpc(
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
    for item in organic[:max_results]:
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


def save_research_cache(startup_name: str, kind: str, snippets: list[dict[str, Any]]) -> Path:
    cache_path = DEFAULT_RESEARCH_CACHE_DIR / slugify(startup_name) / f"{kind}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(snippets, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache_path


def summarize_research(startup_name: str, label: str, snippets: list[dict[str, Any]]) -> str:
    types = ", ".join(item["source_type"] for item in snippets[:3]) or "없음"
    return f"{startup_name}에 대해 {len(snippets)}개의 {label} 근거를 수집했다. 주요 출처 유형은 {types}."


def source_rows(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"title": item["title"], "url": item["url"], "source_type": item["source_type"]}
        for item in snippets
    ]
