"""Deployable dry-bulk research agent: LangChain tool loop + OpenRouter."""

from __future__ import annotations

import json
from datetime import date
from importlib import metadata
from typing import Any

from pydantic import Field, create_model

from freight_second_brain.config import Settings, get_settings
from freight_second_brain.tools.registry import AGENT_TOOL_NAMES, ToolRegistry
from freight_second_brain.warehouse.store import Warehouse

MAX_RECURSION = 100

RESEARCH_SYSTEM_PROMPT = """You are a dry-bulk freight research analyst writing for an institutional desk. Use a professional, measured voice: complete sentences, no slang, no exclamation marks, no emoji. Do not narrate tool calls or chain-of-thought; the interface already shows high-level progress.

Keep the visible reply brief. Answer only what the user asked. Do not add forecast, history, methodology, gaps, or segment colour unless the question needs them. Prefer a short paragraph or a few bullets. No preamble, no recap of the question, no unused headings.

Today's as_of date is {as_of}. Before any tool call, pin as_of and a horizon: session/week, 1–2 months, 1–8 quarters, history, or structural. Topic-relevant is not time-relevant.

Do not invent numerical forecasts. Quote sourced rates and labeled outlooks only. Warehouse vintages are not live prints: TE.BDI.LAST and other stored observations stay dated to observed_at. If a figure is not in the warehouse and not on the live web, say so.

Tools:
- schema — list warehouse SQL tables, columns, and row counts. Call this before writing SQL.
- sql — read-only SELECT/WITH/DESCRIBE/SHOW/FROM against observations, series, sources, catalog. Quote "end" (it is a reserved column name).
- show_source — catalog metadata, retrieval record, and a text preview of a stored snapshot.
- rss_feed — Hellenic dry-bulk market feed by default; cheapest high-recall layer for current BDI headlines.
- web_search — Exa. Precise Baltic/cargo terms (BDI, Capesize, Panamax, C3, C5, iron ore, coal, grain, BIMCO SMOO). Always include a vessel class or Baltic route code. Never search "shipping news" or "freight rates".
- fetch_url — Jina Reader on one chosen article or PDF, not a whole site. Cookie walls are not analysis.

Method: for stored series (Pink Sheet, PSD, ONI, Mendeley, TE last print), use schema then sql (then show_source if you need the raw snapshot). For news, prints, and outlook, use live web: RSS first, then Exa with vessel class / route codes, then Jina on one or two chosen URLs. When the question needs both, query both layers and keep vintages as separate columns. For outlook, search the latest BIMCO SMOO (month + year) and in-year Clarksons/Geneva Dry material. For history, prefer rmtYYYYch3_en.pdf, not RMT landing pages.

The warehouse has no stored claims, events, or labeled contradictions. Do not look for those tables. Qualitative color comes from rss_feed / web_search / fetch_url on this turn.

Playbook:
- A strong UNCTAD chapter or 2023 broker PDF can be correct for history and wrong for the market now. Label lagged vintages as history.
- Baltic week is not ISO week. A weekly posted over the weekend remains the live weekly until the next one is published.
- Daily Hellenic BDI posts are often composite-only (no C5/BCI split). Take segment colour from weeklies or a Friday close.
- Syndicated copies of the same Baltic weekly paragraph (Hellenic, DCN, Business Times) are one independence group, not three witnesses.
- Skip container, tanker-only, cruise, air freight, and e-commerce shipping.
- Keep contradictions (Cape vs Panamax, week vs next print, 5TC vs C5TC). Do not average them.
- Black Sea grain items are Panamax/Handy overlays, not Capesize session prints.
- Magnitude sanity: a “Week 36” PDF with BDI near 1,200 while the live composite is near 3,500 is the wrong year.

Cite publisher and data-as-of only when you use a figure. Distinguish warehouse record vs live web vs synthesis. Cite series_id / URL when you rely on them. Never treat article count as independent evidence count. Do not list sources the reply does not rely on.
"""

_JSON_TYPES = {"string": str, "integer": int, "number": float, "boolean": bool}


def research_system_prompt(*, as_of: date | None = None) -> str:
    return RESEARCH_SYSTEM_PROMPT.format(as_of=(as_of or date.today()).isoformat())


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
    """LangChain `create_agent` tool-calling loop over warehouse and web tools."""
    from langchain.agents import create_agent

    settings = settings or get_settings()
    registry = registry or ToolRegistry(Warehouse(settings))
    llm = model or make_openrouter_model(settings)
    tools = registry_tools_to_langchain(registry, AGENT_TOOL_NAMES)
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
    missing = [name for name in AGENT_TOOL_NAMES if name not in listed]
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
        "exa_key": bool(settings.exa_api_key),
        "exa_backend": "exa" if settings.exa_api_key else "exa_mcp",
        "tools": list(AGENT_TOOL_NAMES),
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
