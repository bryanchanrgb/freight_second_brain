from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from freight_second_brain.tools.web import WEB_TOOL_NAMES, fetch_url_text, read_rss_feed, search_web
from freight_second_brain.warehouse.store import Warehouse

WAREHOUSE_TOOL_NAMES = ("schema", "sql", "show_source")
AGENT_TOOL_NAMES = WAREHOUSE_TOOL_NAMES + WEB_TOOL_NAMES


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
                "the cheapest high-recall layer for current BDI/Baltic headlines."
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
                "Use after web_search or rss_feed, on one article or PDF at a time. "
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
