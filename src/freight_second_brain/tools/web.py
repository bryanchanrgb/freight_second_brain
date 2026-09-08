"""Live web research backends used by the dry-bulk research skill: Exa, RSS, Jina."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any

import feedparser
import httpx

from freight_second_brain.config import USER_AGENT, Settings, get_settings

WEB_TOOL_NAMES = ("web_search", "rss_feed", "fetch_url")

HELLENIC_DRY_BULK_RSS = (
    "https://www.hellenicshippingnews.com/category/shipping-news/dry-bulk-market/feed/"
)
EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_MCP_URL = "https://mcp.exa.ai/mcp"
JINA_READER_PREFIX = "https://r.jina.ai/"

COOKIE_WALL_MARKERS = (
    "this website uses cookies",
    "we use cookies",
    "enable javascript and cookies",
    "cookie consent",
    "to continue you need to enable",
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_MCP_FIELD_RE = re.compile(r"^(Title|URL|Published|Author):\s*(.*)$", re.MULTILINE)


def _plain(text: str | None, max_chars: int = 400) -> str:
    cleaned = _SPACE_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _clip(text: str | None, max_chars: int) -> str:
    value = (text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def _looks_like_cookie_wall(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in COOKIE_WALL_MARKERS) and len(text) < 4000


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if extra:
        headers.update(extra)
    return headers


def _get(url: str, *, headers: dict[str, str] | None = None, timeout: float = 60.0) -> tuple[int, str]:
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url, headers=_headers(headers))
        response.raise_for_status()
        return response.status_code, response.text


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.post(url, json=payload, headers=_headers(headers))
        response.raise_for_status()
        return response.json()


def _await(coro: Any) -> Any:
    """Run an async coroutine from sync tool handlers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    holder: dict[str, Any] = {}

    def _runner() -> None:
        try:
            holder["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            holder["error"] = exc

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join()
    if "error" in holder:
        raise holder["error"]
    return holder["value"]


def _mcp_result_text(result: Any) -> str:
    parts: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def parse_exa_mcp_text(text: str) -> list[dict[str, Any]]:
    """Turn Exa MCP `web_search_exa` markdown blocks into the REST-shaped result list."""
    chunks = [chunk.strip() for chunk in re.split(r"\n---\n", text.strip()) if chunk.strip()]
    results: list[dict[str, Any]] = []
    for chunk in chunks:
        fields = {key.lower(): value.strip() for key, value in _MCP_FIELD_RE.findall(chunk)}
        highlights: list[str] = []
        if "Highlights:" in chunk:
            tail = chunk.split("Highlights:", 1)[1]
            for line in tail.splitlines():
                stripped = line.strip().lstrip("-").strip()
                if len(stripped) < 8 or stripped in {"...", "|", "N/A"}:
                    continue
                highlights.append(stripped)
                if len(highlights) >= 3:
                    break
        title = fields.get("title")
        url = fields.get("url")
        published = fields.get("published")
        if published in {None, "", "N/A"}:
            published = None
        if not title and not url:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "published_date": published,
                "score": None,
                "highlights": highlights,
                "text": _clip(" ".join(highlights), 500),
            }
        )
    if not results and text.strip():
        results.append(
            {
                "title": None,
                "url": None,
                "published_date": None,
                "score": None,
                "highlights": [],
                "text": _clip(text, 2000),
            }
        )
    return results


async def _exa_mcp_call(query: str, num_results: int, timeout: float) -> str:
    from mcp import Client

    async with Client(EXA_MCP_URL, read_timeout_seconds=timeout) as client:
        result = await client.call_tool(
            "web_search_exa",
            {"query": query, "numResults": num_results},
        )
        text = _mcp_result_text(result)
        if result.is_error:
            raise RuntimeError(text or "Exa MCP web_search_exa failed")
        return text


def search_via_exa_mcp(query: str, num_results: int, timeout: float) -> dict[str, Any]:
    """Hosted Exa MCP (`mcp.exa.ai`) — free tier, no API key."""
    text = _await(_exa_mcp_call(query, num_results, timeout))
    return {"backend": "exa_mcp", "query": query, "results": parse_exa_mcp_text(text)}


def search_via_exa_rest(
    query: str,
    num_results: int,
    *,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    """Authenticated Exa Search REST API — higher limits than the MCP free tier."""
    payload = {
        "query": query,
        "numResults": num_results,
        "contents": {
            "highlights": {"maxCharacters": 400, "numSentences": 2},
            "text": {"maxCharacters": 500},
        },
    }
    raw = _post_json(
        EXA_SEARCH_URL,
        payload,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        timeout=timeout,
    )
    results = []
    for item in raw.get("results") or []:
        highlights = item.get("highlights") or []
        if isinstance(highlights, str):
            highlights = [highlights]
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "published_date": item.get("publishedDate") or item.get("published_date"),
                "score": item.get("score"),
                "highlights": [str(h) for h in highlights[:3]],
                "text": _clip(item.get("text"), 500),
            }
        )
    return {"backend": "exa", "query": query, "results": results}


def search_web(
    query: str,
    num_results: int = 6,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Search the public web via Exa.

    With `EXA_API_KEY`, uses the Search REST API. Without a key, uses Exa's hosted
    MCP free tier (`web_search_exa` on `https://mcp.exa.ai/mcp`) — the same door
    mcporter uses in the Cursor harness.
    """
    settings = settings or get_settings()
    query = (query or "").strip()
    if not query:
        raise ValueError("query is required")
    n = max(1, min(int(num_results or 6), 10))
    if settings.exa_api_key:
        return search_via_exa_rest(
            query,
            n,
            api_key=settings.exa_api_key,
            timeout=settings.http_timeout_s,
        )
    try:
        return search_via_exa_mcp(query, n, timeout=max(settings.http_timeout_s, 45.0))
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "rate limit" in message.lower():
            raise RuntimeError(
                "Exa MCP free tier rate-limited. Set EXA_API_KEY to use the Search API."
            ) from exc
        raise RuntimeError(f"Exa MCP free-tier search failed: {exc}") from exc


def read_rss_feed(
    url: str | None = None,
    limit: int = 12,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Parse an RSS/Atom feed. Defaults to the Hellenic dry-bulk market feed."""
    settings = settings or get_settings()
    feed_url = (url or HELLENIC_DRY_BULK_RSS).strip()
    if not feed_url:
        raise ValueError("url is required")
    n = max(1, min(int(limit or 12), 20))
    status, body = _get(feed_url, timeout=settings.http_timeout_s)
    parsed = feedparser.parse(body)
    entries = []
    for item in (parsed.entries or [])[:n]:
        entries.append(
            {
                "title": item.get("title"),
                "url": item.get("link"),
                "published": item.get("published") or item.get("updated"),
                "summary": _plain(item.get("summary") or item.get("description"), 280),
            }
        )
    feed_title = None
    if parsed.feed:
        feed_title = parsed.feed.get("title")
    return {
        "backend": "rss",
        "url": feed_url,
        "title": feed_title,
        "status_code": status,
        "entries": entries,
    }


def fetch_url_text(
    url: str,
    max_chars: int = 8000,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Fetch a URL through Jina Reader (`r.jina.ai`), as in the research skill."""
    settings = settings or get_settings()
    target = (url or "").strip()
    if not target:
        raise ValueError("url is required")
    n = max(500, min(int(max_chars or 8000), 20000))
    jina_url = target if target.startswith(JINA_READER_PREFIX) else f"{JINA_READER_PREFIX}{target}"
    status, body = _get(jina_url, timeout=max(settings.http_timeout_s, 60.0))
    cookie_wall = _looks_like_cookie_wall(body)
    note = None
    if cookie_wall:
        note = (
            "Fetch looks like a cookie/consent wall, not article text. "
            "Prefer Exa highlights, a hosted PDF, or a Hellenic/Cyprus reprint."
        )
    return {
        "backend": "jina",
        "url": target,
        "jina_url": jina_url,
        "status_code": status,
        "cookie_wall": cookie_wall,
        "note": note,
        "text": _clip(body, n),
    }
