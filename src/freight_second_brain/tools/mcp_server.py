from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from freight_second_brain.config import Settings, resolve_data_root
from freight_second_brain.tools.registry import ToolRegistry
from freight_second_brain.warehouse.store import Warehouse


def harness_warehouse() -> Warehouse:
    """Always use this repo's data/ directory, independent of MCP process cwd."""
    return Warehouse(Settings(data_root=resolve_data_root()))


def json_payload(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def mcp_tool_definitions(registry: ToolRegistry) -> list[types.Tool]:
    """Mirror ToolRegistry into MCP tool descriptors. New registry tools show up here."""
    return [
        types.Tool(
            name=spec["name"],
            description=spec["description"],
            input_schema=spec["parameters"],
        )
        for spec in registry.list_tools()
    ]


def make_server(registry: ToolRegistry | None = None) -> Server[Any]:
    registry = registry or ToolRegistry(harness_warehouse())

    async def on_list_tools(
        _ctx: Any,
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=mcp_tool_definitions(registry))

    async def on_call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        result = registry.call(params.name, **(params.arguments or {}))
        payload = json_payload({"ok": result.ok, "data": result.data, "error": result.error})
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))],
            structured_content=payload,
            is_error=not result.ok,
        )

    return Server(
        "freight-second-brain",
        version="0.1.0",
        instructions=(
            "ToolRegistry for Freight Second Brain: warehouse query tools "
            "(schema, sql, show_source) and live web research tools "
            "(web_search via Exa, press_fetch, rss_feed, fetch_url via Jina, "
            "market_feed via OilPriceAPI). "
            "Warehouse tools and rss_feed stay on this Cursor harness and CLI; "
            "the deployable LangChain agent is live-web only and does not bind "
            "schema/sql/show_source or rss_feed."
        ),
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def serve() -> None:
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

    async def main() -> None:
        server = make_server()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())


if __name__ == "__main__":
    serve()
