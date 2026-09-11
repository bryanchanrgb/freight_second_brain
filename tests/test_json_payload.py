import json

from freight_second_brain.agent.artifacts import (
    BLOCKS_JSON_ERROR,
    PARSE_FAIL_CALLOUT,
    normalize_report_blocks,
)
from freight_second_brain.agent.json_payload import parse_json_payload
from freight_second_brain.agent.session import (
    ResearchDesk,
    _current_desk,
    _current_session_id,
)


def test_parse_json_payload_accepts_lists_and_fences() -> None:
    blocks = [{"type": "markdown", "text": "Cape firmed."}]
    assert parse_json_payload(blocks) == blocks
    assert parse_json_payload({"blocks": blocks}) == {"blocks": blocks}
    fenced = "```json\n" + json.dumps(blocks) + "\n```"
    assert parse_json_payload(fenced) == blocks
    trailing = '[{"type": "markdown", "text": "Hi"},]'
    assert parse_json_payload(trailing) == [{"type": "markdown", "text": "Hi"}]
    wrapped = "blocks_json = " + json.dumps(blocks)
    assert parse_json_payload(wrapped) == blocks
    encoded = json.dumps(json.dumps(blocks))
    assert parse_json_payload(encoded) == blocks


def test_normalize_does_not_render_raw_json() -> None:
    broken = '[{"type": "markdown", "text": "Cape said "firm" this week."}]'
    blocks = normalize_report_blocks(broken)
    assert blocks == [PARSE_FAIL_CALLOUT]
    assert broken not in json.dumps(blocks)
    assert "Cape said" not in json.dumps(blocks)


def test_normalize_parses_fenced_and_nested_json_markdown() -> None:
    inner = [{"type": "kpis", "items": [{"label": "BDI", "value": "3,521"}]}]
    fenced = "```json\n" + json.dumps(inner) + "\n```"
    assert [block["type"] for block in normalize_report_blocks(fenced)] == ["kpis"]
    stuffed = [{"type": "markdown", "text": json.dumps(inner)}]
    assert [block["type"] for block in normalize_report_blocks(stuffed)] == ["kpis"]


def test_present_report_rejects_raw_json_blob(settings, monkeypatch) -> None:
    monkeypatch.setattr("freight_second_brain.agent.session.build_research_agent", lambda **_kwargs: object())
    desk = ResearchDesk(settings=settings)
    session = desk.create_session()
    desk_token = _current_desk.set(desk)
    session_token = _current_session_id.set(session.session_id)
    broken = '[{"type": "markdown", "text": "Cape said "firm"."}]'
    try:
        tools = {tool.name: tool for tool in desk._ui_tools()}
        payload = tools["present_report"].invoke({"title": "Broken", "blocks_json": broken})
    finally:
        _current_desk.reset(desk_token)
        _current_session_id.reset(session_token)
    result = json.loads(payload)
    assert result["ok"] is False
    assert result["error"] == BLOCKS_JSON_ERROR
    assert "report-turn-1" not in session.artifacts
    assert session.show_report is False
