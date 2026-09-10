from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from freight_second_brain.agent.preload import (
    DEFAULT_QUERY,
    apply_preload,
    collect_preload,
    load_preload,
    serialize_traces,
    ui_messages_from_events,
    write_preload,
)
from freight_second_brain.agent.session import ResearchDesk
from freight_second_brain.ui.server import create_app


class FakeAgent:
    def __init__(self) -> None:
        self.states: dict[str, list] = {}

    def update_state(self, config, values):
        thread = config["configurable"]["thread_id"]
        self.states[thread] = list(values.get("messages") or [])
        return config

    def get_state(self, config):
        thread = config["configurable"]["thread_id"]

        class State:
            values = {"messages": self.states.get(thread, [])}

        return State()

    async def aget_state(self, config):
        return self.get_state(config)


def _desk(settings, monkeypatch) -> ResearchDesk:
    monkeypatch.setattr("freight_second_brain.agent.session.build_research_agent", lambda **_kwargs: FakeAgent())
    return ResearchDesk(settings=settings)


def _payload(query: str = DEFAULT_QUERY) -> dict:
    traces = serialize_traces(
        [
            HumanMessage(content=query),
            AIMessage(
                content="",
                tool_calls=[{"name": "web_search", "args": {"query": "BDI"}, "id": "c1", "type": "tool_call"}],
            ),
            ToolMessage(content='{"ok": true}', tool_call_id="c1", name="web_search"),
            AIMessage(content="See the report."),
        ]
    )
    return {
        "version": 1,
        "ok": True,
        "query": query,
        "messages": [
            {"id": "preload-user", "role": "user", "content": query, "progress": []},
            {
                "id": "preload-assistant",
                "role": "assistant",
                "content": "See the report.",
                "progress": [{"id": "web_search", "label": "Searching Baltic and cargo sources", "status": "done"}],
                "reasoning": "pin horizon",
                "streaming": False,
            },
        ],
        "display": {"showReport": True, "turn": 1, "activeReportId": "report-turn-1"},
        "session": {
            "title": query[:80],
            "turn": 1,
            "show_report": True,
            "active_report_id": "report-turn-1",
            "print_points": [],
            "artifacts": [
                {
                    "id": "report-turn-1",
                    "kind": "report",
                    "status": "active",
                    "title": "August BDI claims",
                    "payload": {
                        "blocks": [{"type": "markdown", "text": "Consensus was mixed. [1]"}],
                        "citations": [],
                        "turn": 1,
                    },
                }
            ],
        },
        "traces": traces,
    }


def test_default_query_is_the_bdi_example() -> None:
    assert "August 2026" in DEFAULT_QUERY
    assert "BDI" in DEFAULT_QUERY
    assert "BPI" not in DEFAULT_QUERY
    assert "30 day" in DEFAULT_QUERY
    assert "September" in DEFAULT_QUERY


def test_ui_messages_from_events_capture_progress_and_reasoning() -> None:
    messages = ui_messages_from_events(
        "What is BPI?",
        [
            {"type": "progress", "id": "web_search", "label": "Searching", "status": "running"},
            {"type": "progress", "id": "web_search", "label": "Searching", "status": "done"},
            {"type": "reasoning", "delta": "pin as_of"},
            {"type": "message", "content": "See the report."},
        ],
    )
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is BPI?"
    assistant = messages[1]
    assert assistant["content"] == "See the report."
    assert assistant["progress"] == [{"id": "web_search", "label": "Searching", "status": "done"}]
    assert assistant["reasoning"] == "pin as_of"
    assert assistant["streaming"] is False


def test_apply_preload_restores_artifacts_and_traces(settings, monkeypatch) -> None:
    desk = _desk(settings, monkeypatch)
    payload = _payload()
    session = apply_preload(desk, payload)
    assert session.turn == 1
    assert session.show_report is True
    assert session.artifacts["report-turn-1"]["title"] == "August BDI claims"
    restored = desk.agent.get_state({"configurable": {"thread_id": session.session_id}}).values["messages"]
    assert [type(item).__name__ for item in restored] == [
        "HumanMessage",
        "AIMessage",
        "ToolMessage",
        "AIMessage",
    ]
    assert restored[0].content == payload["query"]
    assert restored[-1].content == "See the report."
    assert restored[2].name == "web_search"


def test_write_and_load_preload_roundtrip(tmp_path: Path) -> None:
    dest = tmp_path / "preload.json"
    payload = _payload()
    write_preload(payload, dest)
    loaded = load_preload(dest)
    assert loaded is not None
    assert loaded["query"] == payload["query"]
    assert loaded["traces"][0]["type"] == "human"
    assert load_preload(tmp_path / "missing.json") is None


def test_collect_preload_builds_static_asset(settings, monkeypatch) -> None:
    desk = _desk(settings, monkeypatch)
    query = "What did BPI do?"

    async def fake_stream(session_id: str, query: str):
        session = desk.get(session_id)
        session.turn = 1
        session.title = query[:80]
        session.show_report = True
        session.active_report_id = "report-turn-1"
        session.upsert(
            {
                "id": "report-turn-1",
                "kind": "report",
                "status": "active",
                "title": "BPI",
                "payload": {"blocks": [{"type": "markdown", "text": "Note."}], "citations": [], "turn": 1},
            }
        )
        yield {"type": "run_start", "session_id": session_id, "title": session.title, "turn": 1}
        yield {"type": "progress", "id": "press_fetch", "label": "Reading a publisher feed", "status": "done"}
        yield {"type": "message", "content": "See the report."}
        yield {"type": "done", "session": session.snapshot()}

    desk.stream_turn = fake_stream
    desk.agent.states["pending"] = []

    async def aget_state(config):
        class State:
            values = {
                "messages": [
                    HumanMessage(content=query),
                    AIMessage(content="See the report."),
                ]
            }

        return State()

    desk.agent.aget_state = aget_state
    import asyncio

    payload = asyncio.run(collect_preload(desk, query))
    assert payload["ok"] is True
    assert payload["query"] == query
    assert payload["messages"][1]["content"] == "See the report."
    assert payload["display"]["activeReportId"] == "report-turn-1"
    assert payload["session"]["artifacts"][0]["id"] == "report-turn-1"
    assert payload["traces"][0]["type"] == "human"
    assert payload["traces"][-1]["data"]["content"] == "See the report."


def test_create_session_hydrates_preload(settings, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    desk = _desk(settings, monkeypatch)
    payload = _payload()
    monkeypatch.setattr("freight_second_brain.ui.server.load_preload", lambda: payload)
    monkeypatch.setattr("freight_second_brain.ui.server.get_desk", lambda: desk)
    client = TestClient(create_app())
    preloaded = client.post("/api/sessions?preload=true")
    assert preloaded.status_code == 200
    body = preloaded.json()
    assert body["preloaded"] is True
    assert body["messages"][0]["content"] == payload["query"]
    assert body["artifacts"][0]["id"] == "report-turn-1"
    assert body["display"]["showReport"] is True
    assert body["session_id"] in desk.sessions
    restored = desk.agent.states[body["session_id"]]
    assert restored[0].content == payload["query"]

    fresh = client.post("/api/sessions")
    assert fresh.json()["preloaded"] is False
    assert fresh.json()["messages"] == []
    assert fresh.json()["session_id"] != body["session_id"]


def test_preload_json_is_served(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    dest = tmp_path / "preload.json"
    payload = _payload()
    dest.write_text(json.dumps(payload))
    monkeypatch.setattr("freight_second_brain.ui.server.candidate_paths", lambda: [dest])
    client = TestClient(create_app())
    res = client.get("/preload.json")
    assert res.status_code == 200
    assert res.json()["query"] == payload["query"]
