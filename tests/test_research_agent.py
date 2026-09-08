from freight_second_brain.agent.research import (
    registry_tools_to_langchain,
    research_system_prompt,
    run_research_query,
    startup_check,
)
from freight_second_brain.tools.registry import AGENT_TOOL_NAMES, ToolRegistry
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_research_system_prompt_pins_horizon() -> None:
    prompt = research_system_prompt()
    assert "as_of" in prompt
    assert "schema" in prompt
    assert "sql" in prompt
    assert "show_source" in prompt
    assert "web_search" in prompt
    assert "rss_feed" in prompt
    assert "fetch_url" in prompt
    assert "Do not invent numerical forecasts" in prompt
    assert "Warehouse vintages are not live prints" in prompt
    assert "Do not query a warehouse" not in prompt
    assert "no stored claims" in prompt
    assert "RSS first" in prompt
    assert "independence group" in prompt
    assert "professional" in prompt.lower()
    assert "brief" in prompt.lower()
    assert "Answer only what the user asked" in prompt


def test_langchain_wrappers_call_registry(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "freight_second_brain.tools.registry.read_rss_feed",
        lambda url=None, limit=12, settings=None: {"entries": [{"title": "Hellenic BDI"}]},
    )
    registry = ToolRegistry(Warehouse(settings))
    tools = registry_tools_to_langchain(registry, ("rss_feed",))
    assert len(tools) == 1
    payload = tools[0].invoke({"limit": 4})
    assert "Hellenic BDI" in payload


def test_langchain_wrappers_include_warehouse_tools(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    warehouse.rebuild_sql()
    registry = ToolRegistry(warehouse)
    tools = {tool.name: tool for tool in registry_tools_to_langchain(registry, AGENT_TOOL_NAMES)}
    assert set(tools) == set(AGENT_TOOL_NAMES)

    schema_payload = tools["schema"].invoke({})
    assert "observations" in schema_payload

    sql_payload = tools["sql"].invoke(
        {"query": "SELECT series_id, value FROM observations", "limit": 5}
    )
    assert "TEST.SERIES" in sql_payload


def test_research_agent_startup(settings) -> None:
    report = startup_check(settings=settings)
    assert report["ok"] is True
    assert report["agent_built"] is True
    assert report["tools"] == list(AGENT_TOOL_NAMES)
    assert report["langchain"]
    assert report["langchain_openrouter"]
    assert report["exa_backend"] == "exa_mcp"


class _FakeAgent:
    def invoke(self, payload, config=None):
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        query = payload["messages"][0]["content"]
        return {
            "messages": [
                HumanMessage(content=query),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "rss_feed", "args": {"limit": 3}, "id": "call-1"}],
                ),
                ToolMessage(content='{"ok": true, "data": {"entries": []}}', tool_call_id="call-1"),
                AIMessage(content="Latest Hellenic RSS items do not include a sourced BDI print."),
            ]
        }


def test_run_research_query_with_fake_agent(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "freight_second_brain.agent.research.build_research_agent",
        lambda **kwargs: _FakeAgent(),
    )
    out = run_research_query("What is the latest BDI print?", settings=settings)
    assert out["ok"] is True
    assert "rss_feed" in out["tools_used"]
    assert "BDI" in out["answer"]
