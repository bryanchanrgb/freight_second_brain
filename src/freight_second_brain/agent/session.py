"""Multi-turn research sessions with streamed steps, tool calls, and desk artifacts."""

from __future__ import annotations

import asyncio
import json
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from freight_second_brain.agent.artifacts import (
    PRINTS_CHART_ID,
    PRINTS_TABLE_ID,
    materialize_from_tool,
    merge_print_points,
    new_artifact,
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
You are writing for a professional research desk UI. Ranked source cards are processed, tagged, and grouped automatically. A table or chart appears only if you decide it helps the reader.

Voice: calm, precise, institutional, and short. Prefer "The latest composite print is 3,584" over casual phrasing. Do not narrate tool calls. Do not pad the note with background the user did not ask for.

Source tags (desk UI, not warehouse tables):
- provenance: primary | secondary | tertiary | overlay (Baltic/benchmark vs reprint vs blog vs Handy/grain overlay)
- hierarchy: primary (lead in an independence group) | duplicate (syndicated reprint)
- claim_type: observation (fact) | explanation (analysis) | forecast (outlook) | scenario | risk | methodology
- polarity: bullish | bearish | mixed | neutral | unknown — implication for dry-bulk rates, not a keyword list
- freshness: current | recent | aging | historical_vintage | post_cutoff_outcome
- medium: website | pdf | rss | warehouse

After fetch_url (or when a headline is clearly a print vs outlook), call label_sources to correct claim_type, polarity, and freshness. Leave polarity unknown unless the source supports it. Do not invent tags.

Generative display:
- present_table — only when several dated prints or a segment split would help. Use id table-prints.
- present_chart — when a sourced time series (three or more points) or a comparison of two or more series is meaningful. Put each line in series[] as {name, points:[{x,y}]}. Use id chart-bdi. Do not chart a single print. If units or scales are incomparable, use two charts instead of one axis.
- set_display — show_table / show_chart booleans to hide an object that is no longer relevant.
- supersede_object — when a newer independent vintage replaces an older card.

Do not present a table or chart for a one-line RSS headline unless the user asked for a series.
On follow-up questions, update or hide objects rather than repeating the entire sweep unless asked.
Your final message is the desk note only: brief, on-question, no unused sections. Progress labels are rendered separately.
"""

PROGRESS_LABELS = {
    "schema": "Inspecting warehouse tables",
    "sql": "Querying the warehouse",
    "show_source": "Opening a stored snapshot",
    "web_search": "Searching Baltic and cargo sources",
    "rss_feed": "Reading the dry-bulk news feed",
    "fetch_url": "Opening a selected source",
    "present_table": "Updating the prints table",
    "present_chart": "Updating the chart",
    "supersede_object": "Revising the source list",
    "set_display": "Arranging the board",
    "label_sources": "Classifying sources",
}

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


@dataclass
class ResearchSession:
    session_id: str
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    print_points: list[dict[str, Any]] = field(default_factory=list)
    title: str = "New session"
    turn: int = 0
    show_table: bool = False
    show_chart: bool = False
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
            "show_table": self.show_table,
            "show_chart": self.show_chart,
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
            system_prompt=research_system_prompt() + DESK_SYSTEM_PROMPT,
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

        def present_table(
            object_id: str,
            title: str,
            payload_json: str,
            subtitle: str | None = None,
            supersedes: str | None = None,
            reason: str | None = None,
        ) -> str:
            session = _require_session()
            payload = _json_load(payload_json) or {}
            artifact = new_artifact(
                object_id=object_id or PRINTS_TABLE_ID,
                kind="table",
                title=title,
                subtitle=subtitle,
                provenance={"tool": "present_table"},
                payload=payload,
            )
            stored = session.upsert(artifact, supersedes=supersedes, reason=reason)
            if artifact["kind"] == "table":
                session.show_table = True
            return json.dumps({"ok": True, "artifact": stored, "show_table": session.show_table}, default=str)

        def present_chart(
            object_id: str,
            title: str,
            payload_json: str,
            subtitle: str | None = None,
            supersedes: str | None = None,
            reason: str | None = None,
        ) -> str:
            session = _require_session()
            payload = _json_load(payload_json) or {}
            artifact = new_artifact(
                object_id=object_id or PRINTS_CHART_ID,
                kind="chart",
                title=title,
                subtitle=subtitle,
                provenance={"tool": "present_chart"},
                payload=payload,
            )
            stored = session.upsert(artifact, supersedes=supersedes, reason=reason)
            session.show_chart = True
            return json.dumps({"ok": True, "artifact": stored, "show_chart": True}, default=str)

        def supersede_object(object_id: str, replacement_id: str, reason: str) -> str:
            session = _require_session()
            updated = session.supersede(object_id, replacement_id, reason)
            return json.dumps({"ok": bool(updated), "artifact": updated}, default=str)

        def set_display(show_table: bool | None = None, show_chart: bool | None = None) -> str:
            session = _require_session()
            if show_table is not None:
                session.show_table = bool(show_table)
            if show_chart is not None:
                session.show_chart = bool(show_chart)
            return json.dumps(
                {"ok": True, "show_table": session.show_table, "show_chart": session.show_chart},
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
                func=present_table,
                name="present_table",
                description=(
                    "Upsert an interactive table on the research desk. "
                    "payload_json is {columns:[{key,label}], rows:[object], numeric?:[key]}. "
                    "Use id table-prints for Baltic prints. Set supersedes to replace another table id."
                ),
            ),
            StructuredTool.from_function(
                func=present_chart,
                name="present_chart",
                description=(
                    "Upsert an interactive chart. payload_json is "
                    "{x_label, y_label, series:[{name, points:[{x,y}]}]}. "
                    "Each series is drawn as its own line on a shared x-axis "
                    "(e.g. BDI and Capesize 5TC). Use id chart-bdi. "
                    "Do not mix incomparable units on one chart."
                ),
            ),
            StructuredTool.from_function(
                func=supersede_object,
                name="supersede_object",
                description=(
                    "Mark an existing desk object as superseded by a newer one "
                    "(better vintage, fuller fetch, or a correction)."
                ),
            ),
            StructuredTool.from_function(
                func=set_display,
                name="set_display",
                description=(
                    "Show or hide the prints table and chart on the board. "
                    "Use show_chart=false when a single print does not warrant a series. "
                    "Use show_table=true only when a comparison table helps."
                ),
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
        if "show_table" in parsed or "show_chart" in parsed:
            if "show_table" in parsed:
                session.show_table = bool(parsed["show_table"])
            if "show_chart" in parsed:
                session.show_chart = bool(parsed["show_chart"])
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
                    if _is_recursion_error(exc):
                        yield {
                            "type": "error",
                            "message": f"Stopped: the agent reached the maximum of {MAX_RECURSION} steps.",
                        }
                        return
                    raise
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
            if _is_recursion_error(exc):
                yield {
                    "type": "error",
                    "message": f"Stopped: the agent reached the maximum of {MAX_RECURSION} steps.",
                }
            else:
                yield {"type": "error", "message": str(exc)}
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
            "show_table": session.show_table,
            "show_chart": session.show_chart,
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
