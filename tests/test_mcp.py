import asyncio
import os
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from freight_second_brain.config import repo_root, resolve_data_root
from freight_second_brain.tools.mcp_server import make_server, mcp_tool_definitions
from freight_second_brain.tools.registry import AGENT_TOOL_NAMES, WAREHOUSE_TOOL_NAMES, WEB_TOOL_NAMES, ToolRegistry, ToolSpec
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_mcp_definitions_match_registry(settings) -> None:
    registry = ToolRegistry(Warehouse(settings))
    names = {tool.name for tool in mcp_tool_definitions(registry)}
    assert names == {spec["name"] for spec in registry.list_tools()}
    assert names == set(AGENT_TOOL_NAMES)


def test_new_registry_tool_is_listed_by_mcp(settings) -> None:
    registry = ToolRegistry(Warehouse(settings))
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo a string. Development-only extra tool.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=lambda _warehouse, text: text,
        )
    )
    names = {tool.name for tool in mcp_tool_definitions(registry)}
    assert "echo" in names
    assert set(WAREHOUSE_TOOL_NAMES) <= names
    assert set(WEB_TOOL_NAMES) <= names


def test_mcp_client_lists_and_calls_registry_tools(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    warehouse.rebuild_sql()
    registry = ToolRegistry(warehouse)

    async def run() -> None:
        async with Client(make_server(registry)) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == set(AGENT_TOOL_NAMES)
            called = await client.call_tool(
                "sql",
                {"query": "SELECT series_id FROM observations", "limit": 5},
            )
            assert called.is_error is False
            assert called.structured_content["ok"] is True
            assert called.structured_content["data"]["rows"][0]["series_id"] == "TEST.SERIES"
            missing = await client.call_tool("not_a_tool", {})
            assert missing.is_error is True
            assert missing.structured_content["ok"] is False

    asyncio.run(run())


def test_mcp_stdio_wrapper_lists_registry_tools() -> None:
    """Same launch path Cursor uses: `.cursor/run-mcp.sh` → `freight-sb mcp`."""

    async def run() -> None:
        params = StdioServerParameters(
            command="/bin/bash",
            args=[str(repo_root() / ".cursor/run-mcp.sh")],
            cwd=str(repo_root()),
            env={
                "PYTHONUNBUFFERED": "1",
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
            },
        )
        async with Client(params) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == set(AGENT_TOOL_NAMES)

    asyncio.run(run())


def test_resolve_data_root_is_repo_relative(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FREIGHT_SB_DATA_ROOT", raising=False)
    assert resolve_data_root(Path("data")).parent == repo_root()
    monkeypatch.setenv("FREIGHT_SB_DATA_ROOT", "")
    assert resolve_data_root() == (repo_root() / "data").resolve()
    monkeypatch.setenv("FREIGHT_SB_DATA_ROOT", str(tmp_path))
    assert resolve_data_root() == tmp_path.resolve()
