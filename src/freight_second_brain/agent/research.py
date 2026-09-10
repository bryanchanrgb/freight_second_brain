"""Deployable dry-bulk research agent: LangChain tool loop + OpenRouter."""

from __future__ import annotations

import json
from datetime import date
from importlib import metadata
from typing import Any

from pydantic import Field, create_model

from freight_second_brain.config import Settings, get_settings
from freight_second_brain.tools.registry import DEPLOYABLE_TOOL_NAMES, ToolRegistry
from freight_second_brain.warehouse.store import Warehouse

MAX_RECURSION = 100

RESEARCH_SYSTEM_PROMPT = """You are a dry-bulk freight research analyst for an institutional desk. Professional, measured voice. No slang, emoji, or narration of tool calls.

Today's as_of is {as_of}. Before any tool call, pin as_of and a horizon: session/week, 1–2 months, 1–8 quarters, history, or structural. Topic-relevant is not time-relevant. On every figure, track page published, market data-as-of, and as_of. Wrong year on a week number means drop it for current-state work.

Do not invent numerical forecasts or series_id prints. Quote sourced rates and labelled outlooks only. No warehouse schema/sql/show_source — live web only. If a figure is not available this turn, say so.

{market_feed_note}

Tools:
- market_feed — dated BDI/BCI and cargo/energy prices (OilPriceAPI). Default latest: bdi,bci. BPI/BSI/BHSI are not in this catalog — do not request or invent them. Baltic history on this feed starts in 2026; empty_window means no data, not a guess. Cite OilPriceAPI, not official Baltic Exchange data. Chart history in the report, not long dumps in chat.
- press_catalog — lists Hellenic, Splash, Telegraph, gCaptain desks and category_guide.
- press_fetch — maritime news on those four sites (search + after/before). Default category is all (noisy); pin a desk. hellenic dry-bulk = composite color; weekly-brokers = broker PDFs; weekly-tce = TCE sheet; iron-ore = MMI prices. splash dry-cargo = bulker fixtures. telegraph freight-news = IC Shipbrokers commentary. gcaptain: pass query Capesize or Baltic Dry; no dry-bulk desk.
- web_search — Exa for publishers without a native API (Baltic weeklies on other hosts, BIMCO SMOO reprints, Reuters/Baird, Clarksons/Geneva Dry, BigMint, Mysteel). Not first for the four press sites. Precise Baltic/cargo terms; pin Week NN YYYY or SMOO month+year.
- fetch_url — one article or PDF via Jina. Prefer hosted PDFs. Cookie walls are not analysis.

Method: market_feed for index levels and short history when available. press_fetch for the four press sites. Exa then fetch_url for weeklies, outlooks, and cargo notes. Session/week: market_feed latest plus Exa for the Baltic weekly and segment split — do not stop after Hellenic alone. Panamax/BPI: Baltic weekly, Reuters/Baird, or broker notes — not market_feed (BPI is not in the catalog). Cape/BDI composite: market_feed bdi,bci when available.

Horizon routing:
- Session/week: market_feed latest (bdi,bci) when available; Exa for latest Baltic weekly; press_fetch hellenic dry-bulk for narrative color. Segment split from the weekly or Reuters/Baird, not Hellenic daily composite alone.
- Cape drivers: BigMint voyage freight; Mysteel dispatch surveys — align survey week with Baltic week.
- 1–8q outlook: BIMCO SMOO (month+year) via reprints; in-year Clarksons or Geneva Dry. Prior-year essays are history, not spot.
- History: UNCTAD RMT ch.3 PDF and cited footnotes.

No stored claims on this agent. Dated prints from market_feed when configured; qualitative color from press_fetch / web_search / fetch_url.

Playbook:
- Label lagged vintages as history. Baltic week is not ISO week.
- Daily Hellenic BDI posts are composite-only; they do not replace market_feed or a weekly Cape/Panamax recap.
- Syndicated Baltic weekly copies (Hellenic, DCN, Business Times, i3investor) are one independence group.
- Skip container, tanker-only, cruise, and e-commerce unless overlay. Keep contradictions; do not average them.
- Magnitude sanity: Week 36 with BDI near 1,200 while live composite is near 3,500 is the wrong year.

Cite publisher and data-as-of when you use a figure. Do not list sources the answer does not rely on.
"""

MARKET_FEED_AVAILABLE_NOTE = (
    "market_feed is configured (OILPRICE_API_TOKEN set). Use it for BDI/BCI prints before headline recall."
)

MARKET_FEED_MISSING_NOTE = (
    "market_feed is not configured (OILPRICE_API_TOKEN missing). Do not quote a numeric BDI/BCI from "
    "headlines alone — say dated prints are unavailable on this desk. Use press_fetch and web_search "
    "for narrative only; label any headline figure as unsourced."
)

_JSON_TYPES = {"string": str, "integer": int, "number": float, "boolean": bool}


def research_system_prompt(
    *,
    as_of: date | None = None,
    market_feed_available: bool | None = None,
) -> str:
    settings = get_settings()
    if market_feed_available is None:
        market_feed_available = bool(settings.oilprice_api_token)
    note = MARKET_FEED_AVAILABLE_NOTE if market_feed_available else MARKET_FEED_MISSING_NOTE
    return RESEARCH_SYSTEM_PROMPT.format(
        as_of=(as_of or date.today()).isoformat(),
        market_feed_note=note,
    )


def make_openrouter_model(settings: Settings, *, api_key: str | None = None) -> Any:
    """Chat model via OpenRouter (`langchain-openrouter`)."""
    from langchain_openrouter import ChatOpenRouter

    key = settings.openrouter_api_key if api_key is None else api_key
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return ChatOpenRouter(
        model=settings.openrouter_model,
        api_key=key,
        temperature=0,
        app_title="Freight Second Brain",
        app_url="https://github.com/bryanchanrgb/freight-second-brain",
    )


def registry_tools_to_langchain(registry: ToolRegistry, names: tuple[str, ...] | list[str]) -> list[Any]:
    """Wrap selected ToolRegistry tools as LangChain StructuredTools."""
    from langchain_core.tools import StructuredTool

    wanted = set(names)
    tools: list[Any] = []
    for spec in registry.list_tools():
        if spec["name"] not in wanted:
            continue
        params = spec["parameters"] or {}
        props = params.get("properties") or {}
        required = set(params.get("required") or [])
        field_defs: dict[str, Any] = {}
        for key, schema in props.items():
            py_type = _JSON_TYPES.get(schema.get("type"), str)
            desc = schema.get("description") or ""
            if key in required:
                field_defs[key] = (py_type, Field(description=desc))
            else:
                field_defs[key] = (py_type | None, Field(default=None, description=desc))
        args_model = create_model(f"{spec['name']}_args", **field_defs)

        def _make(tool_name: str, description: str):
            def _run(**kwargs: Any) -> str:
                cleaned = {k: v for k, v in kwargs.items() if v is not None}
                result = registry.call(tool_name, **cleaned)
                return json.dumps(
                    {"ok": result.ok, "data": result.data, "error": result.error},
                    default=str,
                )

            _run.__name__ = tool_name
            _run.__doc__ = description
            return _run

        tools.append(
            StructuredTool.from_function(
                func=_make(spec["name"], spec["description"]),
                name=spec["name"],
                description=spec["description"],
                args_schema=args_model,
            )
        )
    missing = wanted - {tool.name for tool in tools}
    if missing:
        raise RuntimeError(f"registry is missing tools: {sorted(missing)}")
    return tools


def build_research_agent(
    *,
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
    model: Any | None = None,
    as_of: date | None = None,
    extra_tools: list[Any] | None = None,
    checkpointer: Any | None = None,
    system_prompt: str | None = None,
) -> Any:
    """LangChain `create_agent` tool-calling loop over live web tools."""
    from langchain.agents import create_agent

    settings = settings or get_settings()
    registry = registry or ToolRegistry(Warehouse(settings))
    llm = model or make_openrouter_model(settings)
    tools = registry_tools_to_langchain(registry, DEPLOYABLE_TOOL_NAMES)
    if extra_tools:
        tools.extend(extra_tools)
    kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools,
        "system_prompt": system_prompt or research_system_prompt(as_of=as_of),
    }
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    return create_agent(**kwargs)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
        return "\n".join(parts)
    return str(content)


def _tool_names_from_messages(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                names.append(name)
    return names


def _serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for message in messages:
        rows.append(
            {
                "type": getattr(message, "type", message.__class__.__name__),
                "content": getattr(message, "content", None),
                "tool_calls": getattr(message, "tool_calls", None),
            }
        )
    return rows


def _pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def startup_check(*, settings: Settings | None = None) -> dict[str, Any]:
    """Construct the research agent without calling the LLM (placeholder key is allowed)."""
    settings = settings or get_settings()
    errors: list[str] = []
    try:
        from langchain.agents import create_agent  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        errors.append(f"langchain import failed: {exc}")
    try:
        from langchain_openrouter import ChatOpenRouter  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        errors.append(f"langchain-openrouter import failed: {exc}")

    registry = ToolRegistry(Warehouse(settings))
    listed = {spec["name"] for spec in registry.list_tools()}
    missing = [name for name in DEPLOYABLE_TOOL_NAMES if name not in listed]
    if missing:
        errors.append(f"agent tools missing: {missing}")

    agent_built = False
    if not errors:
        try:
            key = settings.openrouter_api_key or "sk-or-placeholder"
            model = make_openrouter_model(settings, api_key=key)
            build_research_agent(settings=settings, registry=registry, model=model)
            agent_built = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"create_agent failed: {exc}")

    return {
        "ok": not errors,
        "agent_built": agent_built,
        "model": settings.openrouter_model,
        "openrouter_key": bool(settings.openrouter_api_key),
        "oilprice_key": bool(settings.oilprice_api_token),
        "exa_key": bool(settings.exa_api_key),
        "exa_backend": "exa" if settings.exa_api_key else "exa_mcp",
        "tools": list(DEPLOYABLE_TOOL_NAMES),
        "langchain": _pkg_version("langchain"),
        "langchain_openrouter": _pkg_version("langchain-openrouter"),
        "errors": errors,
    }


def run_research_query(
    query: str,
    *,
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
    model: Any | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Invoke the research agent once and return the final answer plus tool trace."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query is required")
    settings = settings or get_settings()
    agent = build_research_agent(settings=settings, registry=registry, model=model, as_of=as_of)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"recursion_limit": MAX_RECURSION},
    )
    messages = list(result.get("messages") or [])
    answer = _message_text(messages[-1]) if messages else ""
    return {
        "ok": True,
        "answer": answer,
        "model": settings.openrouter_model,
        "tools_used": _tool_names_from_messages(messages),
        "messages": _serialize_messages(messages),
    }
