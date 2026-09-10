"""Multi-turn research sessions with streamed steps, tool calls, and desk artifacts."""

from __future__ import annotations

import asyncio
import json
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from freight_second_brain.agent.artifacts import (
    new_artifact,
    normalize_citations,
    normalize_report_blocks,
    citations_from_blocks,
    report_id_for_turn,
    materialize_from_tool,
    merge_print_points,
)
from freight_second_brain.agent.process_sources import process_source_cards
from freight_second_brain.agent.source_tags import AGENT_OVERRIDE_FIELDS, coerce_override
from freight_second_brain.agent.research import (
    MAX_RECURSION,
    _message_text,
    build_research_agent,
    research_system_prompt,
)
from freight_second_brain.config import Settings, get_settings
from freight_second_brain.tools.registry import ToolRegistry, WEB_TOOL_NAMES
from freight_second_brain.warehouse.store import Warehouse

DESK_SYSTEM_PROMPT = """
Desk UI: the right pane is a generative report with a labelled source list below. Call present_report on every user-facing turn — the report is the full answer. Chat is a short pointer only; do not duplicate the report in chat.

Chat format (required): one or two sentences with the headline answer, then a final line exactly: "See the report for sources and charts." No preamble, recap, or extra headings.

present_report (required every turn):
- subtitle (required): "As of YYYY-MM-DD · {horizon}" using the horizon you pinned (session/week, 1–2 months, 1–8 quarters, history, structural).
- Prefer tables and charts over prose walls. Chart market_feed history; do not paste long series into chat.
- Each turn keeps its own report; earlier turns stay in history.

Report shapes by question:
- Session/week print: KPI row (BDI, BCI or segment, as-of) + 30d chart from market_feed when available + short markdown on drivers.
- Segment split: table or KPIs for Cape vs Panamax with data-as-of; callout if sources disagree.
- Outlook / forecast: callout for vintage + table of claims with publisher and as-of; label lagged items as history.
- Driver / why: quote block from the best source + cargo overlay table if relevant.

Citations: use [1], [2] in markdown and table cells matching citations_json — a 1-based list of {url, title?, publisher?, as_of?, note?}. Numbers open the matching source card. Cite only sources the report uses. No citations block in blocks_json.

Source cards are auto-collected from tools and tagged. After fetch_url, call label_sources to fix claim_type, polarity, and freshness when clear. Leave polarity unknown unless the source supports it.

Progress labels are rendered separately; do not narrate tool calls in chat.
"""

PROGRESS_LABELS = {
    "web_search": "Searching Baltic and cargo sources",
    "press_catalog": "Checking press-site coverage",
    "press_fetch": "Reading a publisher feed",
    "market_feed": "Reading Baltic and cargo prices",
    "fetch_url": "Opening a selected source",
    "present_report": "Writing the report",
    "label_sources": "Classifying sources",
}

PRESENT_REPORT_DESCRIPTION = (
    "Publish a generative report for this turn. Earlier turns stay in the history; "
    "this call writes (or updates) only the current turn's report. "
    "Chat stays a short pointer; the report is the full reply. "
    "title: heading. subtitle (required): as-of date and horizon, e.g. 'As of 2026-09-10 · session/week'. "
    "blocks_json: JSON array of blocks. Types: "
    "markdown {type, text} (GitHub-flavored markdown; cite as [1], [2]); "
    "heading {type, text, level?} (1-3); "
    "callout {type, tone?, title?, text} (tone: info|note|warn|risk); "
    "kpis {type, items:[{label, value, caption?}]}; "
    "table {type, title?, subtitle?, columns:[{key,label}] or [str], rows:[object], numeric?:[key]}; "
    "chart {type, title?, subtitle?, x_label?, y_label?, variant?: line|area|bar, series:[{name, points:[{x,y}]}]}; "
    "expand {type, title, blocks:[...]} (nested, collapsed); "
    "quote {type, text, attribution?}; "
    "divider {type}; "
    "diagram {type, title?, nodes:[{id,label}], edges:[{from,to,label?}]}. "
    "citations_json: JSON list of {url, title?, publisher?, as_of?, note?} in [1]..[n] order. "
    "Each url should match a fetched source so the numbered mark opens that card. "
    "Do not include a citations block in blocks_json."
)

_current_desk: ContextVar["ResearchDesk | None"] = ContextVar("freight_sb_desk", default=None)
_current_session_id: ContextVar[str | None] = ContextVar("freight_sb_session", default=None)


def _json_load(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _tool_payload_text(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    content = getattr(output, "content", None)
    if isinstance(content, str):
        return content
    if hasattr(output, "model_dump"):
        dumped = output.model_dump()
        return dumped.get("content") or json.dumps(dumped, default=str)
    return str(output)


def _chunk_text(chunk: Any) -> tuple[str, str]:
    """Return (visible_text, reasoning_text) from a chat model stream chunk."""
    if chunk is None:
        return "", ""
    extra = getattr(chunk, "additional_kwargs", None) or {}
    reasoning_bits: list[str] = []
    for key in ("reasoning_content", "reasoning"):
        value = extra.get(key) if isinstance(extra, dict) else None
        if value:
            reasoning_bits.append(str(value))
    direct = getattr(chunk, "reasoning_content", None) or getattr(chunk, "reasoning", None)
    if direct and str(direct) not in reasoning_bits:
        reasoning_bits.append(str(direct))
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content, "".join(reasoning_bits)
    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind in {"reasoning", "thinking"}:
                reasoning_bits.append(str(block.get("reasoning") or block.get("text") or ""))
            elif block.get("text"):
                texts.append(str(block["text"]))
        return "".join(texts), "".join(reasoning_bits)
    return "", "".join(reasoning_bits)


def _is_recursion_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return name == "GraphRecursionError" or "recursion limit" in text


def desk_system_prompt() -> str:
    return DESK_SYSTEM_PROMPT


def combined_system_prompt(*, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    market_feed_available = bool(settings.oilprice_api_token)
    return research_system_prompt(market_feed_available=market_feed_available) + desk_system_prompt()


def friendly_error_message(exc: BaseException | str) -> str:
    text = str(exc).strip()
    lower = text.lower()
    if _is_recursion_error(exc if isinstance(exc, BaseException) else RuntimeError(text)):
        return f"Stopped: the agent reached the maximum of {MAX_RECURSION} steps. Try a narrower question."
    if "oilprice_api_token" in lower or ("oilpriceapi" in lower and "token" in lower):
        return (
            "OilPriceAPI token is not set. Add OILPRICE_API_TOKEN to .env for dated BDI/BCI prints, "
            "or ask a narrative-only question."
        )
    if "empty_window" in lower:
        return (
            "The requested price history returned no data. Baltic series on this feed start in 2026; "
            "older windows are empty."
        )
    if "openrouter" in lower and ("key" in lower or "401" in text or "403" in text):
        return "OpenRouter API key missing or invalid. Check OPENROUTER_API_KEY in .env."
    if "unknown session" in lower:
        return "Session expired. Refresh the page to start a new session."
    if lower in {"internal server error", "500"} or text.startswith("500"):
        return "The desk server returned an error. Check the terminal running freight-sb ui for details."
    return text


@dataclass
class ResearchSession:
    session_id: str
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    print_points: list[dict[str, Any]] = field(default_factory=list)
    title: str = "New session"
    turn: int = 0
    show_report: bool = False
    active_report_id: str | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    run_task: asyncio.Task[Any] | None = field(default=None, repr=False)

    def upsert(self, artifact: dict[str, Any], *, supersedes: str | None = None, reason: str | None = None) -> dict[str, Any]:
        object_id = artifact["id"]
        prior = self.artifacts.get(object_id)
        if prior:
            artifact["revision"] = int(prior.get("revision") or 1) + 1
            payload = dict(artifact.get("payload") or {})
            prior_payload = dict(prior.get("payload") or {})
            if "origin_turn" not in payload and prior_payload.get("origin_turn") is not None:
                payload["origin_turn"] = prior_payload["origin_turn"]
            artifact["payload"] = payload
            if prior.get("status") == "superseded" and not artifact.get("superseded_by"):
                artifact["status"] = "superseded"
                artifact["superseded_by"] = prior.get("superseded_by")
                artifact["supersede_reason"] = prior.get("supersede_reason")
        self.artifacts[object_id] = artifact
        if supersedes and supersedes in self.artifacts and supersedes != object_id:
            self.supersede(supersedes, object_id, reason or "Replaced by a later vintage")
        return artifact

    def supersede(self, object_id: str, replacement_id: str, reason: str) -> dict[str, Any] | None:
        current = self.artifacts.get(object_id)
        if not current:
            return None
        current = {
            **current,
            "status": "superseded",
            "superseded_by": replacement_id,
            "supersede_reason": reason,
        }
        self.artifacts[object_id] = current
        return current

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "turn": self.turn,
            "show_report": self.show_report,
            "active_report_id": self.active_report_id,
            "artifacts": list(self.artifacts.values()),
        }


class ResearchDesk:
    """Process-wide multi-turn desk: one agent graph, many thread ids."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        from langgraph.checkpoint.memory import InMemorySaver

        self.settings = settings or get_settings()
        self.registry = ToolRegistry(Warehouse(self.settings))
        self.sessions: dict[str, ResearchSession] = {}
        self.checkpointer = InMemorySaver()
        self.agent = build_research_agent(
            settings=self.settings,
            registry=self.registry,
            extra_tools=self._ui_tools(),
            checkpointer=self.checkpointer,
            system_prompt=combined_system_prompt(settings=self.settings),
        )

    def create_session(self) -> ResearchSession:
        session = ResearchSession(session_id=uuid.uuid4().hex)
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ResearchSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def stop_turn(self, session_id: str) -> dict[str, Any]:
        """Cancel the in-flight agent turn for this session."""
        session = self.get(session_id)
        session.cancel_event.set()
        task = session.run_task
        if task is not None and not task.done():
            task.cancel()
        return {"ok": True, "stopped": True, "session_id": session_id}

    def _ui_tools(self) -> list[Any]:
        from langchain_core.tools import StructuredTool

        def present_report(
            title: str,
            blocks_json: str,
            subtitle: str | None = None,
            citations_json: str | None = None,
        ) -> str:
            session = _require_session()
            parsed = _json_load(blocks_json)
            blocks = normalize_report_blocks(parsed if parsed is not None else blocks_json)
            citations = normalize_citations(_json_load(citations_json) if citations_json else None)
            if not citations:
                citations = citations_from_blocks(blocks)
            blocks = [block for block in blocks if block.get("type") != "citations"]
            artifact = new_artifact(
                object_id=report_id_for_turn(session.turn),
                kind="report",
                title=title,
                subtitle=subtitle,
                provenance={"tool": "present_report"},
                payload={"blocks": blocks, "citations": citations, "turn": session.turn},
            )
            stored = session.upsert(artifact)
            session.show_report = True
            session.active_report_id = stored["id"]
            return json.dumps(
                {
                    "ok": True,
                    "artifact": stored,
                    "show_report": True,
                    "block_count": len(blocks),
                    "citation_count": len(citations),
                },
                default=str,
            )

        def label_sources(updates_json: str) -> str:
            session = _require_session()
            parsed = _json_load(updates_json) or []
            if isinstance(parsed, dict):
                parsed = parsed.get("updates") or parsed.get("sources") or [parsed]
            labeled = 0
            for row in parsed:
                if not isinstance(row, dict):
                    continue
                object_id = str(row.get("id") or row.get("object_id") or "")
                card = session.artifacts.get(object_id)
                if not card or card.get("kind") != "source_card":
                    continue
                payload = dict(card.get("payload") or {})
                changed = False
                for field in AGENT_OVERRIDE_FIELDS:
                    coerced = coerce_override(field, row.get(field))
                    if coerced:
                        payload[field] = coerced
                        changed = True
                if not changed:
                    continue
                payload["classified_by"] = "agent"
                session.upsert({**card, "payload": payload})
                labeled += 1
            refreshed = self._refresh_sources(session)
            return json.dumps({"ok": True, "labeled": labeled, "artifacts": refreshed}, default=str)

        return [
            StructuredTool.from_function(
                func=present_report,
                name="present_report",
                description=PRESENT_REPORT_DESCRIPTION,
            ),
            StructuredTool.from_function(
                func=label_sources,
                name="label_sources",
                description=(
                    "Correct classification tags on source cards after reading them. "
                    "updates_json is a JSON list of "
                    "{id, claim_type?, polarity?, freshness?, access?, provenance?}. "
                    "claim_type: observation|explanation|forecast|scenario|risk|methodology "
                    "(aliases: fact, analysis, prediction). "
                    "polarity: bullish|bearish|mixed|neutral|unknown. "
                    "freshness: current|recent|aging|historical_vintage. "
                    "provenance: primary|secondary|tertiary|overlay. "
                    "Leave polarity unknown unless the source supports a rate implication."
                ),
            ),
        ]

    def _refresh_sources(self, session: ResearchSession) -> list[dict[str, Any]]:
        raw = [item for item in session.artifacts.values() if item.get("kind") == "source_card"]
        processed = process_source_cards(raw, origin_turn=session.turn)
        changed: list[dict[str, Any]] = []
        keep_ids = {item["id"] for item in processed}
        for item in processed:
            changed.append(session.upsert(item))
        for object_id, item in list(session.artifacts.items()):
            if item.get("kind") == "source_card" and object_id not in keep_ids:
                session.artifacts.pop(object_id, None)
                changed.append({"id": object_id, "removed": True})
        return changed

    def _ingest_tool_result(self, session: ResearchSession, name: str, output: Any) -> list[dict[str, Any]]:
        changed: list[dict[str, Any]] = []
        parsed = _json_load(_tool_payload_text(output))
        if not isinstance(parsed, dict):
            return changed
        if parsed.get("artifact"):
            stored = session.upsert(parsed["artifact"])
            payload = dict(stored.get("payload") or {})
            payload["origin_turn"] = session.turn
            stored = session.upsert({**stored, "payload": payload})
            changed.append(stored)
        data = parsed.get("data") if name in WEB_TOOL_NAMES else None
        cards, points = materialize_from_tool(name, data or {})
        for card in cards:
            payload = dict(card.get("payload") or {})
            payload["origin_turn"] = session.turn
            session.upsert({**card, "payload": payload})
        if points:
            session.print_points = merge_print_points(session.print_points, points)
        if cards:
            changed.extend(self._refresh_sources(session))
        if "show_report" in parsed:
            session.show_report = bool(parsed["show_report"])
        if isinstance(parsed.get("artifact"), dict) and parsed["artifact"].get("kind") == "report":
            session.active_report_id = parsed["artifact"].get("id")
        if name == "label_sources":
            for item in parsed.get("artifacts") or []:
                if isinstance(item, dict) and item.get("id"):
                    changed.append(item)
        return changed

    async def _final_answer(self, config: dict[str, Any]) -> str:
        try:
            state = await self.agent.aget_state(config)
            messages = (state.values or {}).get("messages") or []
        except Exception:  # noqa: BLE001
            return ""
        for message in reversed(list(messages)):
            tool_calls = getattr(message, "tool_calls", None) or []
            if getattr(message, "type", "") == "ai" and not tool_calls:
                return _message_text(message)
        if messages:
            return _message_text(messages[-1])
        return ""

    async def stream_turn(self, session_id: str, query: str) -> AsyncIterator[dict[str, Any]]:
        session = self.get(session_id)
        session.turn += 1
        session.cancel_event = asyncio.Event()
        if session.title == "New session":
            session.title = query.strip()[:80]
        desk_token = _current_desk.set(self)
        session_token = _current_session_id.set(session_id)
        yield {"type": "run_start", "session_id": session_id, "title": session.title, "turn": session.turn}
        stream = None
        aiter: Any = None
        stopped = False
        try:
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": MAX_RECURSION,
            }
            stream = self.agent.astream_events(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                version="v2",
            )
            aiter = stream.__aiter__()
            while True:
                if session.cancel_event.is_set():
                    stopped = True
                    break
                nxt = asyncio.create_task(aiter.__anext__())
                session.run_task = nxt
                cancel_wait = asyncio.create_task(session.cancel_event.wait())
                try:
                    done, pending = await asyncio.wait(
                        {nxt, cancel_wait},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    for pending_task in pending:
                        pending_task.cancel()
                if session.cancel_event.is_set() or cancel_wait in done:
                    nxt.cancel()
                    try:
                        await nxt
                    except (asyncio.CancelledError, StopAsyncIteration):
                        pass
                    stopped = True
                    break
                try:
                    event = nxt.result()
                except StopAsyncIteration:
                    break
                except asyncio.CancelledError:
                    stopped = True
                    break
                except Exception as exc:
                    yield {"type": "error", "message": friendly_error_message(exc)}
                    return
                async for outgoing in self._events_from_model(session, event):
                    yield outgoing
                    if session.cancel_event.is_set():
                        stopped = True
                        break
                if stopped:
                    break
            if stopped:
                yield {"type": "stopped", "message": "Run stopped."}
                return
            answer = await self._final_answer(config)
            yield {"type": "message", "content": answer}
            yield {"type": "done", "session": session.snapshot()}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": friendly_error_message(exc)}
        finally:
            session.run_task = None
            closer = getattr(aiter, "aclose", None) or getattr(stream, "aclose", None)
            if callable(closer):
                try:
                    await closer()
                except Exception:  # noqa: BLE001
                    pass
            _current_session_id.reset(session_token)
            _current_desk.reset(desk_token)

    async def _events_from_model(
        self, session: ResearchSession, event: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        kind = event.get("event")
        name = event.get("name") or ""
        data = event.get("data") or {}
        node = (event.get("metadata") or {}).get("langgraph_node")
        if kind == "on_chat_model_stream":
            _text, reasoning = _chunk_text(data.get("chunk"))
            if reasoning:
                yield {"type": "reasoning", "delta": reasoning}
            return
        if kind in {"on_chat_model_start", "on_chat_model_end"}:
            return
        if node not in (None, "tools", "model") and str(kind).startswith("on_tool"):
            return
        if kind == "on_tool_start":
            label = PROGRESS_LABELS.get(name)
            if label:
                yield {"type": "progress", "id": name, "label": label, "status": "running"}
            return
        if kind != "on_tool_end":
            return
        label = PROGRESS_LABELS.get(name)
        if label:
            yield {"type": "progress", "id": name, "label": label, "status": "done"}
        output = data.get("output")
        for artifact in self._ingest_tool_result(session, name, output):
            if artifact.get("removed"):
                yield {"type": "remove", "id": artifact["id"]}
            else:
                yield {"type": "artifact", "artifact": artifact, "turn": session.turn}
        yield {
            "type": "display",
            "show_report": session.show_report,
            "active_report_id": session.active_report_id,
        }


def _require_session() -> ResearchSession:
    desk = _current_desk.get()
    session_id = _current_session_id.get()
    if desk is None or not session_id:
        raise RuntimeError("present_* tools only run inside a research desk turn")
    return desk.get(session_id)


_desk: ResearchDesk | None = None


def get_desk() -> ResearchDesk:
    global _desk
    if _desk is None:
        _desk = ResearchDesk()
    return _desk


def reset_desk() -> None:
    global _desk
    _desk = None
