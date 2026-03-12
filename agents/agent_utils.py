from __future__ import annotations

import json
import re
from typing import Any

from .startup_search_agent import build_openai_client
from .state import InvestmentState


MODEL_NAME = "gpt-4.1-mini"


def json_response(system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
    client = build_openai_client()
    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    )
    try:
        return parse_json_object(response.output_text)
    except json.JSONDecodeError:
        repair = client.responses.create(
            model=MODEL_NAME,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Convert the user's malformed JSON-like text into valid strict JSON. "
                        "Do not add new facts. Return only valid JSON."
                    ),
                },
                {"role": "user", "content": response.output_text},
            ],
        )
        return parse_json_object(repair.output_text)


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def candidate_map(state: InvestmentState) -> dict[str, dict[str, Any]]:
    return {candidate["name"]: candidate for candidate in state.get("startup_candidates", [])}


def current_candidate(state: InvestmentState) -> dict[str, Any]:
    startup_name = state["startup_name"]
    return candidate_map(state).get(startup_name, state.get("startup_basic_info", {"name": startup_name}))


def string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized.append(value)
        elif isinstance(value, dict):
            if "name" in value:
                normalized.append(str(value["name"]))
            else:
                normalized.append(json.dumps(value, ensure_ascii=False))
        else:
            normalized.append(str(value))
    return normalized
