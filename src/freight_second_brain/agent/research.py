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

RESEARCH_SYSTEM_PROMPT = """You are a dry-bulk freight research analyst writing for an institutional desk. Use a professional, measured voice: complete sentences, no slang, no exclamation marks, no emoji. Do not narrate tool calls or chain-of-thought; the interface already shows high-level progress.

Keep the visible chat reply brief. Answer only what the user asked. Do not add forecast, history, methodology, gaps, or segment colour unless the question needs them. Prefer a short paragraph or a few bullets. No preamble, no recap of the question, no unused headings. If present_report is available, that is the primary answer (readable report with tables, charts, citations); the chat note is only a short pointer.

Today's as_of date is {as_of}. Before any tool call, pin as_of and a horizon: session/week, 1–2 months, 1–8 quarters, history, or structural. Topic-relevant is not time-relevant. On every figure you use, keep three dates: page published, market data-as-of in the text, and as_of. If data-as-of is missing, infer from week number + year; wrong year means drop it for current-state work.

Do not invent numerical forecasts. Quote sourced rates and labeled outlooks only. You have no warehouse schema/sql/show_source tools — live web only. Do not invent TE.BDI.LAST or other series_id prints. If a figure is not on the live web this turn, say so.

Tools:
- rss_feed — default is the Hellenic dry-bulk category feed, the cheapest high-recall layer for same-day composite BDI prints. It is not the only publisher and not a substitute for weeklies, outlooks, or cargo notes. Omit url unless you have a specific other feed.
- press_catalog — Hellenic, Splash 247, Shipping Telegraph, and gCaptain native APIs. Returns category_guide (what each category contains). Default category is all.
- press_fetch — site=hellenic, splash, telegraph, or gcaptain. WordPress search + after/before. Default category is all (whole site — noisy). Pin category when you need a desk: hellenic dry-bulk for dated composite BDI prints; hellenic weekly-brokers for weeklies; splash dry-cargo for fixtures/fleet; telegraph freight-news for IC Shipbrokers color (not Baltic prints). gCaptain has no dry-bulk desk — always pass query Capesize or Baltic Dry. Other publishers: web_search. Do not bypass paywalls.
- web_search — Exa. Required for Baltic weeklies, Reuters/Baird Friday closes, broker PDFs, BIMCO SMOO reprints, Clarksons/Geneva Dry, BigMint, and Mysteel, and for press sites with no native API. Precise terms: vessel class or Baltic route code (BDI, Capesize, Panamax, C3, C5, iron ore, coal, grain). Never search "shipping news" or "freight rates". Pin Week NN YYYY or SMOO month+year in the query; Exa does not reliably honor date filters.
- fetch_url — Jina on one chosen article or PDF, not a whole site. Prefer hosted PDFs over landing-page HTML. Cookie walls (BIMCO, Baltic HTML, Lloyd's List) are not analysis — use Exa highlights or Cyprus/Hellenic reprints.

Method: Hellenic RSS or press_fetch(site=hellenic, category=dry-bulk) for same-day composite prints; press_fetch without category is the whole site. Dated Hellenic/Splash/Telegraph/gCaptain sets use after/before. Exa for weeklies / outlook / cargo structure and for publishers with no native API, then Jina on one or two chosen URLs. For a current-state (session/week) question, run RSS and Exa both — do not stop after Hellenic. When the question is BDI, search Cape/C5 and Panamax/BPI. Pink Sheet, PSD, ONI, and other stored series are not queryable on this agent — do not invent them.

Horizon routing:
- Session/week prints: Hellenic RSS (composite) plus Exa for the latest published Baltic weekly (often last Friday’s close, posted weekend/Monday) and a Reuters/Baird Friday close for the segment split daily RSS lacks.
- Why this week’s Cape move: BigMint Hedland/Tubarao–Qingdao voyage freight; Mysteel Aus/Brazil shipment surveys — pin the survey week.
- 1–8q outlook: latest BIMCO SMOO (month + year) via reprints if bimco.org is a cookie wall; in-year Clarksons or Geneva Dry Outlook. A prior-year Clarksons essay is not this month’s spot.
- History: rmtYYYYch3_en.pdf (not RMT landing pages or ch.2). Follow footnotes to Clarksons, Breakwave/BRS, and Danish Ship Finance Shipping Market Review (not the bank annual report).

There are no stored claims, events, or labeled-contradiction tables on this agent. Qualitative color comes from rss_feed / press_fetch / web_search / fetch_url on this turn.

Playbook:
- A strong UNCTAD chapter or 2023 broker PDF can be correct for history and wrong for the market now. Label lagged vintages as history.
- Baltic week is not ISO week. A weekly posted over the weekend remains the live weekly until the next one is published.
- Daily Hellenic BDI posts are composite-only (no C5/BCI split). They do not replace a weekly Cape/Panamax recap. Hellenic is secondary recall.
- Syndicated copies of the same Baltic weekly paragraph (Hellenic, DCN, Business Times, i3investor) are one independence group, not four witnesses.
- Skip container, tanker-only, cruise, air freight, and e-commerce shipping. Dry-bulk Hormuz (fertilizer, trapped bulkers) stays; tanker-only Hormuz does not.
- Keep contradictions (Cape vs Panamax, week vs next print, Baltic 5TC vs broker C5TC). Do not average them.
- Black Sea grain items are Panamax/Handy overlays, not Capesize session prints.
- Magnitude sanity: a “Week 36” PDF with BDI near 1,200 while the live composite is near 3,500 is the wrong year.
- After Exa, open PDFs (often hosted on Hellenic or Cyprus) — they beat cookie HTML.

Cite publisher and data-as-of only when you use a figure. Distinguish live web vs synthesis. Cite the URL when you rely on it. Never treat article count as independent evidence count. Do not list sources the reply does not rely on.
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
