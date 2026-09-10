from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from freight_second_brain.tools.market import market_feed
from freight_second_brain.tools.press import press_catalog, press_fetch
from freight_second_brain.tools.web import WEB_TOOL_NAMES, fetch_url_text, read_rss_feed, search_web
from freight_second_brain.warehouse.store import Warehouse

WAREHOUSE_TOOL_NAMES = ("schema", "sql", "show_source")
AGENT_TOOL_NAMES = WAREHOUSE_TOOL_NAMES + WEB_TOOL_NAMES
# Desk / `freight-sb agent`: live web only. No warehouse SQL, no rss_feed
# (Hellenic dry-bulk is press_fetch). rss_feed stays on MCP/CLI.
DEPLOYABLE_TOOL_NAMES = tuple(name for name in WEB_TOOL_NAMES if name != "rss_feed")


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    category: str = "query"


@dataclass
class ToolResult:
    name: str
    ok: bool
    data: Any
    error: str | None = None


class ToolRegistry:
    def __init__(self, warehouse: Warehouse | None = None) -> None:
        self.warehouse = warehouse or Warehouse()
        self._tools: dict[str, ToolSpec] = {}
        register_default_tools(self)

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "category": spec.category,
            }
            for spec in self._tools.values()
        ]

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(name=name, ok=False, data=None, error=f"unknown tool {name}")
        try:
            data = spec.handler(self.warehouse, **kwargs)
            return ToolResult(name=name, ok=True, data=data)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(name=name, ok=False, data=None, error=f"{exc}\n{traceback.format_exc(limit=2)}")

    def execute_json(self, name: str, arguments: str | dict[str, Any]) -> ToolResult:
        payload = json.loads(arguments) if isinstance(arguments, str) else arguments
        return self.call(name, **payload)


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="schema",
            description="List warehouse SQL tables, column types, and row counts. Call this before writing SQL.",
            parameters={"type": "object", "properties": {}},
            handler=_schema,
            category="query",
        )
    )
    registry.register(
        ToolSpec(
            name="sql",
            description=(
                "Run a read-only SQL query against the warehouse. "
                "Tables include observations, series, sources, and catalog. "
                "SELECT/WITH/DESCRIBE/SHOW/FROM only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Read-only SQL statement."},
                    "limit": {"type": "integer", "description": "Max rows to return (default 200, max 2000)."},
                },
                "required": ["query"],
            },
            handler=_sql,
            category="query",
        )
    )
    registry.register(
        ToolSpec(
            name="show_source",
            description="Display catalog metadata, retrieval record, and a text preview of a stored raw source snapshot.",
            parameters={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["source_id"],
            },
            handler=_show_source,
            category="display",
        )
    )
    registry.register(
        ToolSpec(
            name="web_search",
            description=(
                "Search the public web via Exa for dry-bulk freight sources. "
                "Use precise Baltic/cargo terms (BDI, Capesize, C5, iron ore), not generic 'shipping news'. "
                "Works without EXA_API_KEY via Exa's hosted MCP free tier; set the key to lift rate limits."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query. Include a vessel class or Baltic route code.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 6, max 10).",
                    },
                },
                "required": ["query"],
            },
            handler=_web_search,
            category="web",
        )
    )
    registry.register(
        ToolSpec(
            name="rss_feed",
            description=(
                "Read an RSS/Atom feed. Defaults to the Hellenic Shipping News dry-bulk market feed, "
                "the cheapest high-recall layer for same-day composite BDI headlines. "
                "Weeklies, outlooks, Reuters/Baird closes, broker PDFs, and cargo notes come from web_search, not this tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Feed URL. Omit to use the Hellenic dry-bulk market feed.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return (default 12, max 20).",
                    },
                },
            },
            handler=_rss_feed,
            category="web",
        )
    )
    registry.register(
        ToolSpec(
            name="fetch_url",
            description=(
                "Fetch a chosen URL through Jina Reader and return extracted text. "
                "Use after press_fetch or web_search, on one article or PDF at a time. "
                "Cookie walls (BIMCO, Baltic HTML) are flagged — do not treat them as analysis."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "http(s) URL to fetch."},
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of extracted text (default 8000).",
                    },
                },
                "required": ["url"],
            },
            handler=_fetch_url,
            category="web",
        )
    )
    registry.register(
        ToolSpec(
            name="press_catalog",
            description=(
                "List maritime press sites with a native WordPress search/date API. "
                "Prefer these over web_search for news from these publishers. "
                "hellenic (Hellenic Shipping News): Baltic reprints, daily BDI composites, "
                "broker weeklies (Xclusiv/Intermodal/Banchero), dry TCE sheet, MMI iron ore. "
                "splash (Splash 247): trade press; dry-cargo desk is bulker fixtures and fleet. "
                "telegraph (Shipping Telegraph): IC Shipbrokers daily freight color and fixtures; "
                "not Baltic prints. "
                "gcaptain (gCaptain): operational/maritime news; no dry-bulk desk. "
                "Each site includes default_category (all), categories, and category_guide. "
                "Call before press_fetch if you need to pin a desk."
            ),
            parameters={"type": "object", "properties": {}},
            handler=_press_catalog,
            category="web",
        )
    )
    registry.register(
        ToolSpec(
            name="press_fetch",
            description=(
                "Preferred tool for maritime news stories on Hellenic, Splash 247, "
                "Shipping Telegraph, or gCaptain (WordPress REST: search + after/before). "
                "Do not use web_search for these four publishers unless press_fetch missed them. "
                "Default category is all (whole site, noisy). Pin a desk: "
                "hellenic dry-bulk = daily BDI composite prints and Cape/Panamax color; "
                "hellenic weekly-brokers = Xclusiv, Intermodal, Banchero Costa weeklies/PDFs; "
                "hellenic weekly-tce = weekly dry TCE estimates; "
                "hellenic iron-ore = MMI Chinese iron ore/steelmaking prices; "
                "splash dry-cargo = bulker fixtures and fleet; "
                "telegraph freight-news = IC Shipbrokers commentary and fixtures (not Baltic prints); "
                "telegraph dry-bulk = bulker-only items. "
                "gCaptain has no dry-bulk desk — pass query Capesize or Baltic Dry. "
                "Call press_catalog for the full category_guide. "
                "Does not cover paywalled titles (Lloyd's List, TradeWinds) — use web_search for those."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "enum": ["hellenic", "splash", "telegraph", "gcaptain"],
                        "description": (
                            "hellenic, splash, telegraph, or gcaptain. "
                            "Default category is all on every site."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Keyword search (e.g. Baltic Dry, Capesize).",
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO date or datetime lower bound (e.g. 2026-09-01).",
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO date or datetime upper bound (e.g. 2026-09-10).",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Defaults to all (whole site) on every publisher. "
                            "hellenic: all | dry-bulk (BDI composite color) | weekly-tce (TCE sheet) | "
                            "weekly-brokers (Xclusiv/Intermodal/Banchero) | iron-ore (MMI daily) | "
                            "freight-news (oil/LNG, not BDI) | commodity | ports | international "
                            "(general maritime). "
                            "splash: all | dry-cargo (bulker fixtures/fleet) | containers | "
                            "tankers | ports. "
                            "telegraph: all | freight-news (IC Shipbrokers color/fixtures) | "
                            "dry-bulk | shipping-reports | shipping-news | commodity. "
                            "gcaptain: all | shipping | shipping-news | ports | offshore "
                            "(no dry-bulk desk; pass query)."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries (default 12, max 20).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "WordPress page number (default 1).",
                    },
                },
                "required": ["site"],
            },
            handler=_press_fetch,
            category="web",
        )
    )
    registry.register(
        ToolSpec(
            name="market_feed",
            description=(
                "Dated Baltic Dry and cargo prices from OilPriceAPI. "
                "Use this FIRST for BDI/BCI prints and daily history; "
                "press_fetch is narrative color, not the primary print source. "
                "HISTORY LIMIT (hard): this key's plan may allow 1y/5y, but Baltic series "
                "on OilPriceAPI currently start in 2026 (BDI ~2026-04-10, BCI ~2026-06-08). "
                "A 2025 or 2021 BDI window returns empty_window — do not invent those prints. "
                "WTI/Brent do have 1-year and 5-year daily history. "
                "BPI/BSI/BHSI are not in the catalog (404). "
                "Free published plans: 30 days / Developer 1y / Starter 5y / Professional full archive. "
                "Obey history_available_from, can_read_1y, can_read_5y, date_min, and empty_window. "
                "action=catalog lists aliases (no API key). "
                "action=latest (default) batches codes in one call — default bdi,bci. "
                "action=history is daily: free default past=30d; past=1y needs Developer+; "
                "start around 5 years ago needs Starter+. "
                "codes: comma-separated aliases or OilPriceAPI codes "
                "(iron_ore, coal, wti, brent, copper, coking_coal). "
                "Requires OILPRICE_API_TOKEN (free signup, 50 req/day). "
                "Cite as OilPriceAPI reprint, not official Baltic Exchange data. "
                "Chart rows with present_report; do not dump long history into chat."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["catalog", "latest", "history"],
                        "description": "catalog (no key), latest (default), or history (daily).",
                    },
                    "codes": {
                        "type": "string",
                        "description": (
                            "Comma-separated aliases or OilPriceAPI codes. "
                            "Default for latest/history: bdi,bci. "
                            "Also: bhsi, iron_ore, coal, coking_coal, wti, brent, copper."
                        ),
                    },
                    "start": {
                        "type": "string",
                        "description": (
                            "History start YYYY-MM-DD. 1-year-ago dates need Developer+; "
                            "5-year-ago dates need Starter+. Clipped to history_available_from."
                        ),
                    },
                    "end": {
                        "type": "string",
                        "description": "History end date YYYY-MM-DD (paid plans).",
                    },
                    "past": {
                        "type": "string",
                        "description": (
                            "Relative window: 7d, 30d (default; Free), 3m, 6m, 1y (Developer+). "
                            "There is no past=5y; use start ~5 years ago on Starter+."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max daily rows returned (default 120, max 500). Newest kept if truncated.",
                    },
                    "live": {
                        "type": "boolean",
                        "description": "catalog only: merge the authenticated OilPriceAPI commodity list (uses 1 request).",
                    },
                },
            },
            handler=_market_feed,
            category="web",
        )
    )


def _schema(warehouse: Warehouse) -> Any:
    return warehouse.schema()


def _sql(warehouse: Warehouse, query: str, limit: int = 200) -> Any:
    return warehouse.sql(query, limit=limit)


def _show_source(warehouse: Warehouse, source_id: str, url: str | None = None, max_chars: int = 4000) -> Any:
    return warehouse.show_source(source_id, url=url, max_chars=max_chars)


def _web_search(_warehouse: Warehouse, query: str, num_results: int = 6) -> Any:
    return search_web(query, num_results=num_results)


def _rss_feed(_warehouse: Warehouse, url: str | None = None, limit: int = 12) -> Any:
    return read_rss_feed(url=url, limit=limit)


def _fetch_url(_warehouse: Warehouse, url: str, max_chars: int = 8000) -> Any:
    return fetch_url_text(url, max_chars=max_chars)


def _press_catalog(_warehouse: Warehouse) -> Any:
    return press_catalog()


def _press_fetch(
    _warehouse: Warehouse,
    site: str,
    query: str | None = None,
    after: str | None = None,
    before: str | None = None,
    category: str | None = None,
    limit: int = 12,
    page: int = 1,
) -> Any:
    return press_fetch(
        site,
        query=query,
        after=after,
        before=before,
        category=category,
        limit=limit,
        page=page,
    )


def _market_feed(
    _warehouse: Warehouse,
    action: str | None = "latest",
    codes: str | None = None,
    start: str | None = None,
    end: str | None = None,
    past: str | None = None,
    limit: int | None = None,
    live: bool | None = False,
) -> Any:
    return market_feed(
        action=action,
        codes=codes,
        start=start,
        end=end,
        past=past,
        limit=limit,
        live=live,
        settings=_warehouse.settings,
    )
