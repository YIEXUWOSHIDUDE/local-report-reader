from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx


OFFICIAL_DOMAINS = (
    "gov.cn",
    "mofcom.gov.cn",
    "chengdu.gov.cn",
    "sc.gov.cn",
    "cdht.gov.cn",
)


async def verify_policy_refs_online(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        for ref in refs:
            enriched = dict(ref)
            query = _build_query(ref)
            result = await _search_official_result(client, query)
            if result:
                enriched["联网核验状态"] = "找到官方候选"
                enriched["官方来源链接"] = result["url"]
                enriched["说明"] = f"联网检索命中官方/权威域名：{result['title']}。仍建议人工打开链接核对适用范围和现行有效性。"
            else:
                enriched["联网核验状态"] = "需人工核验"
                enriched["官方来源链接"] = ""
                enriched["说明"] = "后端已联网检索，但未自动命中官方/权威来源；需人工核验政策名称、文号、有效性和适用范围。"
            verified.append(enriched)
    return verified


def _build_query(ref: dict[str, Any]) -> str:
    parts = [str(ref.get("政策名称", "")).strip(), str(ref.get("文号", "")).strip()]
    return " ".join(part for part in parts if part)


async def _search_official_result(client: httpx.AsyncClient, query: str) -> dict[str, str] | None:
    if not query:
        return None
    search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        response = await client.get(search_url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception:
        return None
    return _extract_official_result(response.text)


def _extract_official_result(page: str) -> dict[str, str] | None:
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.S,
    )
    for match in pattern.finditer(page):
        url = html.unescape(match.group("url"))
        title = re.sub(r"<.*?>", "", html.unescape(match.group("title"))).strip()
        if _is_official_url(url):
            return {"url": url, "title": title}
    for url in re.findall(r"https?://[^\"'<> ]+", page):
        clean_url = html.unescape(url)
        if _is_official_url(clean_url):
            return {"url": clean_url, "title": clean_url}
    return None


def _is_official_url(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS)
