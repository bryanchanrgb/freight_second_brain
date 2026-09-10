"""Preload an illustrative desk session as a static asset for first paint and resume."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from freight_second_brain.agent.session import ResearchDesk, ResearchSession
from freight_second_brain.config import Settings, get_settings, repo_root

PRELOAD_VERSION = 1
DEFAULT_QUERY = (
    "Identify all predictive claims made in August 2026 regarding short term BDI "
    "movements (30 day horizon), by conviction and consensus vs disagreement "
    "between analysts. Test these claims against September data."
)


def default_output_path() -> Path:
    return repo_root() / "web" / "public" / "preload.json"


def candidate_paths() -> list[Path]:
    root = repo_root()
    return [
        root / "web" / "public" / "preload.json",
        root / "web" / "dist" / "preload.json",
    ]


def load_preload(path: Path | None = None) -> dict[str, Any] | None:
    paths = [path] if path is not None else candidate_paths()
    for candidate in paths:
        if candidate is None or not candidate.is_file():
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("messages") and payload.get("traces"):
            return payload
    return None


def session_dump(session: ResearchSession) -> dict[str, Any]:
    snap = session.snapshot()
    snap.pop("session_id", None)
    snap["print_points"] = list(session.print_points)
    return snap


def display_from_session(session: ResearchSession) -> dict[str, Any]:
    return {
        "showReport": session.show_report,
        "turn": session.turn,
        "activeReportId": session.active_report_id,
    }


def ui_messages_from_events(query: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user = {"id": "preload-user", "role": "user", "content": query, "progress": []}
    assistant: dict[str, Any] = {
        "id": "preload-assistant",
        "role": "assistant",
        "content": "",
        "progress": [],
        "reasoning": "",
        "streaming": False,
    }
    for event in events:
        kind = event.get("type")
        if kind == "progress":
            incoming = {
                "id": str(event.get("id") or ""),
                "label": str(event.get("label") or ""),
                "status": "done" if event.get("status") == "done" else "running",
            }
            items: list[dict[str, Any]] = assistant["progress"]
            idx = next((i for i, item in enumerate(items) if item["id"] == incoming["id"]), -1)
            if idx == -1:
                items.append(incoming)
            else:
                items[idx] = incoming
        elif kind == "reasoning":
            assistant["reasoning"] = f"{assistant.get('reasoning') or ''}{event.get('delta') or event.get('content') or ''}"
        elif kind == "message":
            assistant["content"] = str(event.get("content") or "")
        elif kind == "stopped":
            assistant["stopped"] = True
            assistant["content"] = assistant["content"] or str(event.get("message") or "Run stopped.")
        elif kind == "error":
            assistant["content"] = assistant["content"] or str(event.get("message") or "The run failed.")
    if not assistant.get("reasoning"):
        assistant.pop("reasoning", None)
    return [user, assistant]


def serialize_traces(messages: list[Any]) -> list[dict[str, Any]]:
    from langchain_core.messages import message_to_dict

    return [message_to_dict(message) for message in messages]


def traces_to_messages(traces: list[dict[str, Any]]) -> list[Any]:
    from langchain_core.messages import messages_from_dict

    return messages_from_dict(traces)


def _preload_traces_enabled() -> bool:
    raw = os.environ.get("DESK_PRELOAD_TRACES", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def apply_preload(desk: ResearchDesk, payload: dict[str, Any]) -> ResearchSession:
    """Hydrate the example session. Traces are optional (hosted desks skip them)."""
    session = desk.create_session()
    snap = payload.get("session") or {}
    session.title = str(snap.get("title") or payload.get("query") or "Example")
    session.turn = int(snap.get("turn") or 1)
    session.show_report = bool(snap.get("show_report"))
    session.active_report_id = snap.get("active_report_id")
    session.print_points = list(snap.get("print_points") or [])
    for artifact in snap.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("id"):
            session.artifacts[str(artifact["id"])] = artifact
    traces = payload.get("traces") or []
    if traces and _preload_traces_enabled():
        try:
            desk.agent.update_state(
                {"configurable": {"thread_id": session.session_id}},
                {"messages": traces_to_messages(traces)},
            )
        except Exception:
            logging.getLogger(__name__).exception("preload traces were not restored")
    return session


def write_preload(payload: dict[str, Any], path: Path, *, mirror_dist: bool | None = None) -> list[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, default=str) + "\n"
    path.write_text(text, encoding="utf-8")
    written = [path]
    if mirror_dist is None:
        mirror_dist = path.resolve() == default_output_path().resolve()
    dist = repo_root() / "web" / "dist" / "preload.json"
    if mirror_dist and dist.parent.is_dir() and dist.resolve() != path.resolve():
        dist.write_text(text, encoding="utf-8")
        written.append(dist)
    return written


async def collect_preload(desk: ResearchDesk, query: str) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("query is required")
    session = desk.create_session()
    events: list[dict[str, Any]] = []
    async for event in desk.stream_turn(session.session_id, query):
        events.append(event)
        kind = event.get("type")
        if kind == "progress":
            print(f"  {event.get('status')}: {event.get('label')}", flush=True)
        elif kind == "message":
            print("  answer ready", flush=True)
        elif kind in {"error", "stopped"}:
            print(f"  {kind}: {event.get('message')}", flush=True)
    config = {"configurable": {"thread_id": session.session_id}}
    try:
        state = await desk.agent.aget_state(config)
        graph_messages = list((state.values or {}).get("messages") or [])
    except Exception:  # noqa: BLE001
        graph_messages = []
    ok = any(event.get("type") == "done" for event in events)
    return {
        "version": PRELOAD_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model": desk.settings.openrouter_model,
        "query": query,
        "ok": ok,
        "messages": ui_messages_from_events(query, events),
        "display": display_from_session(session),
        "session": session_dump(session),
        "traces": serialize_traces(graph_messages),
    }


def run_preload(
    query: str | None = None,
    *,
    output: Path | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run the desk agent once and write `web/public/preload.json` (and dist if present)."""
    question = (query or DEFAULT_QUERY).strip()
    dest = output or default_output_path()
    print(f"preload query: {question}", flush=True)
    desk = ResearchDesk(settings=settings or get_settings())
    payload = asyncio.run(collect_preload(desk, question))
    if not payload.get("ok"):
        raise RuntimeError("preload run did not finish; not writing a static asset")
    if not payload.get("traces"):
        raise RuntimeError("preload run produced no agent traces; not writing a static asset")
    written = write_preload(payload, dest)
    for path in written:
        print(f"wrote {path}", flush=True)
    return payload
