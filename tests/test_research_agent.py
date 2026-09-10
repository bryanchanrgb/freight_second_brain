from freight_second_brain.agent.research import (
    MARKET_FEED_AVAILABLE_NOTE,
    MARKET_FEED_MISSING_NOTE,
    registry_tools_to_langchain,
    research_system_prompt,
    run_research_query,
    startup_check,
)
from freight_second_brain.tools.registry import AGENT_TOOL_NAMES, DEPLOYABLE_TOOL_NAMES, WAREHOUSE_TOOL_NAMES, ToolRegistry
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_research_system_prompt_pins_horizon() -> None:
    prompt = research_system_prompt()
    assert "as_of" in prompt
    assert "No warehouse schema/sql/show_source" in prompt
    assert "- schema —" not in prompt
    assert "- sql —" not in prompt
    assert "- show_source —" not in prompt
    assert "web_search" in prompt
    assert "rss_feed" not in prompt
    assert "- rss_feed" not in prompt
    assert "press_fetch" in prompt
    assert "dry-bulk" in prompt
    assert "Do not call press_catalog first" in prompt
    assert "read each tool's description" in prompt.lower()
    assert "fetch_url" in prompt
    assert "Do not invent numerical forecasts" in prompt
    assert "No stored claims" in prompt
    assert "do not stop after Hellenic" in prompt
    assert "market_feed" in prompt
    assert "OilPriceAPI" in prompt
    assert "empty_window" in prompt
    assert "independence group" in prompt
    assert "BPI/BSI/BHSI are unavailable" in prompt
    assert "Panamax/BPI" in prompt
    assert "Keep the visible chat reply brief" in prompt
    assert "Effort" in prompt
    assert "inventory this session" in prompt
    assert "0–2 tools" in prompt
    assert "Latest print only" in prompt
    assert "40% Capesize / 30% Panamax / 30% Supramax" in prompt
    assert "Handysize is not in the BDI" in prompt
    assert "Investment advice" in prompt
    assert "SCFI" in prompt
    assert "Adversarial" in prompt
    assert "broker FFAs" in prompt
    assert MARKET_FEED_AVAILABLE_NOTE.split(".")[0] in prompt


def test_research_system_prompt_without_market_feed() -> None:
    prompt = research_system_prompt(market_feed_available=False)
    assert MARKET_FEED_MISSING_NOTE.split(".")[0] in prompt
    assert "headlines alone" in prompt


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
    assert report["tools"] == list(DEPLOYABLE_TOOL_NAMES)
    for name in WAREHOUSE_TOOL_NAMES:
        assert name not in report["tools"]
    assert "rss_feed" not in report["tools"]
    assert report["langchain"]
    assert report["langchain_openrouter"]
    assert report["exa_backend"] == "exa_mcp"
    assert "oilprice_key" in report


class _FakeAgent:
    def invoke(self, payload, config=None):
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        query = payload["messages"][0]["content"]
        return {
            "messages": [
                HumanMessage(content=query),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "press_fetch", "args": {"site": "hellenic", "category": "dry-bulk"}, "id": "call-1"}],
                ),
                ToolMessage(content='{"ok": true, "data": {"entries": []}}', tool_call_id="call-1"),
                AIMessage(content="Latest Hellenic dry-bulk items do not include a sourced BDI print."),
            ]
        }


def test_run_research_query_with_fake_agent(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "freight_second_brain.agent.research.build_research_agent",
        lambda **kwargs: _FakeAgent(),
    )
    out = run_research_query("What is the latest BDI print?", settings=settings)
    assert out["ok"] is True
    assert "press_fetch" in out["tools_used"]
    assert "BDI" in out["answer"]
