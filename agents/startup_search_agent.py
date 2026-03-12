from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from openai import OpenAI

from core.prompt_loader import load_prompt
from core.state import InvestmentState


DEFAULT_USER_AGENT = "Mozilla/5.0"
DEFAULT_CACHE_DIR = Path(".cache/robotics-startup-search")
MAX_EVALUATION_CANDIDATES = 3
YC_ALGOLIA_APP_ID = "45BWZJ1SGC"
YC_ALGOLIA_API_KEY = (
    "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4"
    "ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGlj"
    "ZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0Rh"
    "dGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
)
YC_ALGOLIA_URL = f"https://{YC_ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
ROBOTICS_HINTS = [
    "robot",
    "robotics",
    "humanoid",
    "cobot",
    "agv",
    "amr",
    "manipulator",
    "gripper",
    "drone",
    "automation",
    "autonomous",
    "vision",
    "sensor",
    "로봇",
    "로보",
    "휴머노이드",
    "협동로봇",
    "자율",
    "자동화",
    "매니퓰레이터",
    "드론",
    "센서",
    "비전",
]


@dataclass
class StartupCandidate:
    name: str
    source: str
    url: str
    description: str = ""
    location: str = ""
    sector: str = ""
    stage: str = ""
    tags: list[str] | None = None
    core_concept: str = ""
    team_members: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_document_text(self) -> str:
        tags = ", ".join(self.tags or [])
        fields = [
            f"name: {self.name}",
            f"source: {self.source}",
            f"url: {self.url}",
            f"description: {self.description}",
            f"location: {self.location}",
            f"sector: {self.sector}",
            f"stage: {self.stage}",
            f"tags: {tags}",
            f"core_concept: {self.core_concept}",
            f"team_members: {', '.join(self.team_members or [])}",
        ]
        return "\n".join(field for field in fields if field.split(": ", 1)[1])


def _extract_yc_team_members(hit: dict[str, Any]) -> list[str]:
    members: list[str] = []
    founders = hit.get("founders")
    if isinstance(founders, list):
        for founder in founders:
            if isinstance(founder, dict):
                name = str(founder.get("name", "")).strip()
            else:
                name = str(founder).strip()
            if name:
                members.append(name)
    team = hit.get("team")
    if isinstance(team, list):
        for member in team:
            if isinstance(member, dict):
                name = str(member.get("name", "")).strip()
            else:
                name = str(member).strip()
            if name:
                members.append(name)
    deduped: list[str] = []
    seen: set[str] = set()
    for member in members:
        key = _normalize_text(member)
        if key and key not in seen:
            seen.add(key)
            deduped.append(member)
    return deduped[:6]


def _http_text(url: str, *, timeout: int = 20) -> str:
    parsed = urlparse(url)
    encoded_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            quote(parsed.path, safe="/%"),
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    request = Request(encoded_url, headers={"user-agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    timeout: int = 20,
) -> Any:
    payload = None
    request_headers = {"user-agent": DEFAULT_USER_AGENT, **(headers or {})}
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        request_headers.setdefault("content-type", "application/json")
    request = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _keyword_variants(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        normalized.append(keyword)
        parts = [part for part in re.split(r"[\s,/()-]+", keyword) if len(part) >= 2]
        normalized.extend(parts)
    seen: set[str] = set()
    ordered: list[str] = []
    for keyword in normalized:
        lowered = _normalize_text(keyword)
        if lowered and lowered not in seen:
            seen.add(lowered)
            ordered.append(keyword)
    return ordered


def _extract_xml_locs(xml_text: str) -> list[str]:
    return re.findall(r"<loc>(.*?)</loc>", xml_text)


def _extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return {}
    return json.loads(match.group(1))


def _company_name_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return unquote(path.split("/")[-1])


def _robotics_score(text: str) -> int:
    lowered = _normalize_text(text)
    return sum(1 for hint in ROBOTICS_HINTS if hint in lowered)


def _keyword_score(text: str, keywords: list[str]) -> int:
    lowered = _normalize_text(text)
    return sum(2 if " " in keyword else 1 for keyword in (_normalize_text(k) for k in keywords) if keyword and keyword in lowered)


def _safe_join(values: list[Any]) -> str:
    return " ".join(str(value or "") for value in values)


def build_openai_client() -> OpenAI:
    load_env_file(Path.cwd() / ".env")
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPNEAI_API_KEY")
    if not api_key:
        raise RuntimeError(".env에 OPENAI_API_KEY를 넣어야 합니다. 이전 오타 키 OPNEAI_API_KEY도 임시 지원합니다.")
    return OpenAI(api_key=api_key)


def extract_search_keywords(user_query: str, client: OpenAI) -> list[str]:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": load_prompt("startup_search_keywords.txt")},
            {
                "role": "user",
                "content": (
                    "사용자 요청: " + user_query + "\n"
                    "예시 형식: {\"keywords\": [\"휴머노이드\", \"humanoid robot\", \"bipedal robot\"]}"
                ),
            },
        ],
    )
    return json.loads(response.output_text)["keywords"]


def fetch_yc_candidates(keywords: list[str], *, hits_per_keyword: int = 8) -> list[StartupCandidate]:
    candidates: list[StartupCandidate] = []
    for keyword in _keyword_variants(keywords):
        payload = {
            "requests": [
                {
                    "indexName": "YCCompany_production",
                    "params": urlencode({"query": keyword, "hitsPerPage": hits_per_keyword}),
                }
            ]
        }
        response = _http_json(
            YC_ALGOLIA_URL,
            method="POST",
            headers={
                "x-algolia-agent": "Algolia for JavaScript (4.24.0); Browser",
                "x-algolia-api-key": YC_ALGOLIA_API_KEY,
                "x-algolia-application-id": YC_ALGOLIA_APP_ID,
            },
            data=payload,
        )
        for hit in response["results"][0]["hits"]:
            slug = hit.get("slug", "")
            one_liner = hit.get("one_liner", "")
            long_description = hit.get("long_description", "")
            candidates.append(
                StartupCandidate(
                    name=hit["name"],
                    source="ycombinator",
                    url=f"https://www.ycombinator.com/companies/{slug}" if slug else "https://www.ycombinator.com/companies",
                    description=one_liner or long_description,
                    location=hit.get("all_locations", ""),
                    sector=hit.get("subindustry") or hit.get("industry", ""),
                    stage=hit.get("stage", ""),
                    tags=hit.get("tags", []),
                    core_concept=one_liner or long_description,
                    team_members=_extract_yc_team_members(hit),
                )
            )
    return candidates


def fetch_innoforest_company_urls(
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> list[str]:
    cache_path = cache_dir / "innoforest_company_urls.json"
    if not refresh:
        cached = _load_json(cache_path)
        if isinstance(cached, list) and cached:
            return cached

    sitemap_index = _http_text(INNOFOREST_SITEMAP_INDEX_URL)
    sitemap_urls = [
        loc
        for loc in _extract_xml_locs(sitemap_index)
        if re.search(r"/sitemaps/corp-sitemap-main-\d+\.xml$", loc)
    ]

    company_urls: list[str] = []
    for sitemap_url in sitemap_urls:
        sitemap_xml = _http_text(sitemap_url)
        company_urls.extend(
            loc
            for loc in _extract_xml_locs(sitemap_xml)
            if "/company/" in loc and "/invest" not in loc
        )

    deduped = sorted(set(company_urls))
    _save_json(cache_path, deduped)
    return deduped


def fetch_innoforest_company_profile(
    url: str,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> dict[str, Any]:
    company_id_match = re.search(r"/company/([^/]+)/", url)
    company_id = company_id_match.group(1) if company_id_match else "unknown"
    cache_path = cache_dir / "innoforest_profiles" / f"{company_id}.json"
    if not refresh:
        cached = _load_json(cache_path)
        if isinstance(cached, dict) and cached:
            return cached

    html = _http_text(url)
    next_data = _extract_next_data(html)
    page_props = next_data.get("props", {}).get("pageProps", {})
    data = page_props.get("data", {})
    og = page_props.get("ogTagContent", {})
    profile = {
        "corporation_id": data.get("corporationId", company_id),
        "name": data.get("corporationName") or _company_name_from_url(url),
        "found_date": data.get("corporationFoundDate", ""),
        "address": data.get("corporationAddress", ""),
        "intro": data.get("intro", ""),
        "identity_keywords": data.get("identityKeywords", ""),
        "category_name": data.get("categoryName", ""),
        "product_name": data.get("productName", ""),
        "total_invest_value": data.get("totalInvestValue"),
        "people_list": data.get("peopleList", []),
        "meta_description": og.get("metaDescription", ""),
        "meta_title": og.get("metaTitle", ""),
        "url": url,
    }
    _save_json(cache_path, profile)
    return profile


def _build_candidate_from_profile(profile: dict[str, Any]) -> StartupCandidate:
    people = profile.get("people_list") or []
    ceo = next((person.get("peopleName", "") for person in people if person.get("role") == "CEO"), "")
    team_members: list[str] = []
    for person in people:
        name = str(person.get("peopleName", "")).strip()
        role = str(person.get("role", "")).strip()
        if not name:
            continue
        if role in {"CEO", "CTO", "COO", "Founder", "Co-founder", "CPO"}:
            team_members.append(f"{name}({role})")
        elif len(team_members) < 4:
            team_members.append(name)
    intro = profile.get("intro", "")
    if ceo:
        intro = f"{intro} CEO: {ceo}".strip()
    found_year = ""
    if profile.get("found_date"):
        found_year = str(profile["found_date"]).split("-")[0]
    return StartupCandidate(
        name=profile.get("name", ""),
        source="innoforest",
        url=profile.get("url", ""),
        description=intro or profile.get("meta_description", ""),
        location=profile.get("address", "") or "",
        sector=profile.get("category_name", "") or "",
        stage=found_year,
        tags=[profile.get("product_name", ""), profile.get("identity_keywords", "")],
        core_concept=profile.get("product_name") or profile.get("intro", "") or profile.get("meta_description", ""),
        team_members=team_members[:6],
    )


def search_innoforest_candidates(
    keywords: list[str],
    *,
    max_candidates: int = 20,
    max_profile_fetches: int = 120,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> list[StartupCandidate]:
    keyword_variants = _keyword_variants(keywords or ["로봇", "robotics"])
    company_urls = fetch_innoforest_company_urls(cache_dir=cache_dir)

    scored_urls: list[tuple[int, str]] = []
    for url in company_urls:
        name = _company_name_from_url(url)
        searchable_name = f"{name} {url}"
        score = _robotics_score(searchable_name) * 3 + _keyword_score(searchable_name, keyword_variants) * 4
        if score > 0:
            scored_urls.append((score, url))
    scored_urls.sort(key=lambda item: (-item[0], item[1]))

    matched: list[tuple[int, StartupCandidate]] = []
    for _, url in scored_urls[:max_profile_fetches]:
        profile = fetch_innoforest_company_profile(url, cache_dir=cache_dir)
        searchable_text = _safe_join(
            [
                profile.get("name", ""),
                profile.get("intro", ""),
                profile.get("identity_keywords", ""),
                profile.get("category_name", ""),
                profile.get("product_name", ""),
                profile.get("meta_description", ""),
            ]
        )
        score = _robotics_score(searchable_text) * 2 + _keyword_score(searchable_text, keyword_variants) * 5
        if score > 0:
            matched.append((score, _build_candidate_from_profile(profile)))

    deduped: dict[str, tuple[int, StartupCandidate]] = {}
    for score, candidate in matched:
        key = _normalize_text(candidate.name)
        existing = deduped.get(key)
        if existing is None or score > existing[0]:
            deduped[key] = (score, candidate)
    ordered = [candidate for _, candidate in sorted(deduped.values(), key=lambda item: (-item[0], item[1].name))]
    return ordered[:max_candidates]


def deduplicate_candidates(candidates: list[StartupCandidate]) -> list[StartupCandidate]:
    deduped: dict[str, StartupCandidate] = {}
    for candidate in candidates:
        key = _normalize_text(candidate.name)
        if key not in deduped:
            deduped[key] = candidate
            continue

        existing = deduped[key]
        sources = sorted(set(existing.source.split(",")) | set(candidate.source.split(",")))
        tags = sorted(set(existing.tags or []) | set(candidate.tags or []))
        deduped[key] = StartupCandidate(
            name=existing.name,
            source=",".join(sources),
            url=existing.url,
            description=existing.description or candidate.description,
            location=existing.location or candidate.location,
            sector=existing.sector or candidate.sector,
            stage=existing.stage or candidate.stage,
            tags=tags,
            core_concept=existing.core_concept or candidate.core_concept,
            team_members=(existing.team_members or []) or (candidate.team_members or []),
        )
    return list(deduped.values())


def llm_relevance_filter(user_query: str, candidates: list[StartupCandidate], client: OpenAI) -> list[str]:
    candidate_payload = [candidate.to_dict() for candidate in candidates[:30]]
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": load_prompt("startup_relevance_filter.txt")},
            {
                "role": "user",
                "content": json.dumps({"user_query": user_query, "candidates": candidate_payload}, ensure_ascii=False),
            },
        ],
    )
    payload = json.loads(response.output_text)["filtered_candidates"]
    return [item["name"] for item in payload if item["relevance_label"] in {"relevant", "maybe"}]


def save_startup_search_corpus(candidates: list[StartupCandidate], *, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    documents = [
        {
            "source": candidate.source,
            "url": candidate.url,
            "text": candidate.to_document_text(),
            "metadata": candidate.to_dict(),
        }
        for candidate in candidates
    ]
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / "startup_search_corpus.json"
    output_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2))
    return output_path


def _next_startup_name(state: InvestmentState) -> str:
    for startup in state.get("startup_list", []):
        startup_name = startup["name"] if isinstance(startup, dict) else startup
        if startup_name not in state.get("evaluated_startups", []):
            return startup_name
    return ""


def startup_search_node(state: InvestmentState) -> InvestmentState:
    if state.get("startup_list"):
        startup_name = _next_startup_name(state)
        candidate_map = {candidate["name"]: candidate for candidate in state.get("startup_candidates", [])}
        return {
            "startup_name": startup_name,
            "startup_basic_info": candidate_map.get(startup_name, {"name": startup_name}),
        }

    user_query = state.get("user_query", "").strip()
    if not user_query:
        raise ValueError("startup_search_node 실행에는 state['user_query']가 필요합니다.")

    client = build_openai_client()
    keywords = extract_search_keywords(user_query, client)
    yc_candidates = fetch_yc_candidates(keywords)
    raw_candidates = deduplicate_candidates(yc_candidates)
    relevant_names = set(llm_relevance_filter(user_query, raw_candidates, client))
    filtered_candidates = [candidate for candidate in raw_candidates if candidate.name in relevant_names]
    if not filtered_candidates:
        filtered_candidates = raw_candidates[:5]
    filtered_candidates = filtered_candidates[:MAX_EVALUATION_CANDIDATES]
    corpus_path = save_startup_search_corpus(filtered_candidates)
    startup_list = [candidate.name for candidate in filtered_candidates]
    startup_name = startup_list[0] if startup_list else ""
    startup_basic_info = filtered_candidates[0].to_dict() if filtered_candidates else {"name": startup_name}

    return {
        "search_keywords": keywords,
        "startup_name": startup_name,
        "startup_list": startup_list,
        "evaluated_startups": [],
        "startup_basic_info": startup_basic_info,
        "startup_candidates": [candidate.to_dict() for candidate in filtered_candidates],
        "startup_search_summary": (
            f"YC 기반으로 {len(filtered_candidates)}개 후보를 정리했다."
        ),
        "startup_search_corpus_path": str(corpus_path),
        "startup_search_vectorstore_path": "",
        "rag_sources": ["https://www.ycombinator.com/companies"],
    }
