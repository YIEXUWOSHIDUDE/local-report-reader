from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import get_settings


async def ask_ai_json(prompt: str, model: str | None = None) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    clipped = prompt[: settings.max_ai_chars]
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    try:
        if settings.openai_api_style == "chat_completions":
            content = await _ask_chat_completions(settings, headers, clipped, model or settings.openai_model)
        else:
            content = await _ask_responses(settings, headers, clipped, model or settings.openai_model)
        return _parse_json_content(content)
    except Exception:
        return None


async def _ask_responses(settings: Any, headers: dict[str, str], prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/responses",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return _extract_output_text(data)


async def _ask_chat_completions(settings: Any, headers: dict[str, str], prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只输出严格 JSON，不要输出 Markdown 或解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "max_tokens": 8192,
    }
    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    return "{}"


def _parse_json_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.S | re.I)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise
