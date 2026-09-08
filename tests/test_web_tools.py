from freight_second_brain.config import Settings
from freight_second_brain.tools.registry import ToolRegistry
from freight_second_brain.tools.web import (
    HELLENIC_DRY_BULK_RSS,
    fetch_url_text,
    parse_exa_mcp_text,
    read_rss_feed,
    search_web,
)
from freight_second_brain.warehouse.store import Warehouse


def test_web_search_calls_exa_rest_when_keyed(monkeypatch, settings: Settings) -> None:
    captured: dict = {}

    def fake_post(url, payload, *, headers=None, timeout=60.0):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {
            "results": [
                {
                    "title": "Baltic Dry weekly",
                    "url": "https://example.test/bdi",
                    "publishedDate": "2026-09-08",
                    "score": 0.9,
                    "highlights": ["BDI rose to 3575"],
                    "text": "Capesize strength",
                }
            ]
        }

    monkeypatch.setattr("freight_second_brain.tools.web._post_json", fake_post)
    keyed = settings.model_copy(update={"exa_api_key": "test-exa"})
    out = search_web("Baltic Dry Index Capesize weekly C5", num_results=5, settings=keyed)
    assert captured["url"] == "https://api.exa.ai/search"
    assert captured["headers"]["x-api-key"] == "test-exa"
    assert captured["payload"]["numResults"] == 5
    assert out["backend"] == "exa"
    assert out["results"][0]["title"] == "Baltic Dry weekly"
    assert "3575" in out["results"][0]["highlights"][0]


def test_web_search_uses_mcp_free_tier_without_key(monkeypatch, settings: Settings) -> None:
    def fake_mcp(query, num_results, timeout):
        return {
            "backend": "exa_mcp",
            "query": query,
            "results": [
                {
                    "title": "Baltic Exchange Weekly Report",
                    "url": "https://example.test/week-36",
                    "published_date": "2026-09-04",
                    "highlights": ["BDI ended last week at 3628"],
                    "text": "BDI ended last week at 3628",
                }
            ],
        }

    monkeypatch.setattr("freight_second_brain.tools.web.search_via_exa_mcp", fake_mcp)
    keyed = settings.model_copy(update={"exa_api_key": ""})
    out = search_web("Baltic Dry Index Capesize weekly", num_results=3, settings=keyed)
    assert out["backend"] == "exa_mcp"
    assert out["results"][0]["title"] == "Baltic Exchange Weekly Report"


def test_parse_exa_mcp_text() -> None:
    text = """
Title: Baltic Exchange Weekly Report - 4 September 2026
URL: https://www.thedcn.com.au/news/baltic-exchange-weekly-report-4-september-2026
Published: 2026-09-04T00:00:00.000Z
Author: N/A
Highlights:
- THE BALTIC Dry Index (BDI) ended last week at 3 628 points
- The market enjoyed a notably bullish week

---

Title: WEEKLY MARKET REPORT
URL: https://www.hellenicshippingnews.com/wp-content/uploads/2026/09/Market-Report-Week-36.pdf
Published: N/A
Author: Un-named
Highlights:
## DRY BULK | BDI: 3,628
"""
    rows = parse_exa_mcp_text(text)
    assert len(rows) == 2
    assert rows[0]["url"].endswith("4-september-2026")
    assert "3 628" in rows[0]["highlights"][0]
    assert rows[1]["published_date"] is None
    assert rows[1]["title"] == "WEEKLY MARKET REPORT"


def test_rss_feed_parses_entries(monkeypatch, settings: Settings) -> None:
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <title>Dry Bulk Market</title>
      <item>
        <title>Baltic Dry Index climbed 9 points</title>
        <link>https://example.test/bdi-daily</link>
        <pubDate>Mon, 08 Sep 2026 12:00:00 GMT</pubDate>
        <description>The Baltic Dry Index climbed 9 points to 3584.</description>
      </item>
    </channel></rss>
    """

    monkeypatch.setattr(
        "freight_second_brain.tools.web._get",
        lambda url, *, headers=None, timeout=60.0: (200, feed),
    )
    out = read_rss_feed(limit=5, settings=settings)
    assert out["backend"] == "rss"
    assert out["url"] == HELLENIC_DRY_BULK_RSS
    assert out["entries"][0]["title"].startswith("Baltic Dry Index")
    assert "3584" in out["entries"][0]["summary"]


def test_fetch_url_flags_cookie_wall(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.tools.web._get",
        lambda url, *, headers=None, timeout=60.0: (
            200,
            "This website uses cookies. Enable JavaScript and cookies to continue.",
        ),
    )
    out = fetch_url_text("https://www.bimco.org/outlook", settings=settings)
    assert out["backend"] == "jina"
    assert out["jina_url"].startswith("https://r.jina.ai/")
    assert out["cookie_wall"] is True
    assert "cookie" in (out["note"] or "").lower()


def test_registry_web_tools_delegate(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.tools.registry.read_rss_feed",
        lambda url=None, limit=12, settings=None: {"entries": [{"title": "ok"}], "url": url},
    )
    result = ToolRegistry(Warehouse(settings)).call("rss_feed", limit=3)
    assert result.ok
    assert result.data["entries"][0]["title"] == "ok"
