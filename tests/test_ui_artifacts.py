import json

from freight_second_brain.agent.artifacts import extract_bdi_print, materialize_from_tool, normalize_report_blocks, prints_chart
from freight_second_brain.agent.session import (
    DESK_SYSTEM_PROMPT,
    ResearchDesk,
    ResearchSession,
    _current_desk,
    _current_session_id,
)


def test_extract_bdi_print() -> None:
    assert extract_bdi_print("Baltic Dry Index climbs to 3584 up 9 points") == 3584
    assert extract_bdi_print("the Baltic Dry Index decreased by 53 points, reaching 3575 points") == 3575
    assert extract_bdi_print("fell by 1.4% to 3,575 points. Baltic Dry Index") == 3575


def test_materialize_rss_builds_cards_and_prints() -> None:
    cards, points = materialize_from_tool(
        "rss_feed",
        {
            "entries": [
                {
                    "title": "Baltic Dry Index climbs to 3584 up 9 points",
                    "url": "https://example.test/bdi-3584",
                    "published": "Tue, 08 Sep 2026 12:00:56 +0000",
                    "summary": "Today, Tuesday, September 8 2026, the Baltic Dry Index climbed 9 points, 3584 points.",
                }
            ]
        },
    )
    assert len(cards) == 1
    assert cards[0]["kind"] == "source_card"
    assert cards[0]["payload"]["print"] == 3584
    assert points[0]["v"] == 3584


def test_session_supersede_keeps_old_object() -> None:
    session = ResearchSession("s1")
    session.upsert(
        {
            "id": "src-old",
            "kind": "source_card",
            "status": "active",
            "title": "Old weekly",
            "payload": {"url": "https://example.test/old"},
            "revision": 1,
        }
    )
    session.upsert(
        {
            "id": "src-new",
            "kind": "source_card",
            "status": "active",
            "title": "New weekly",
            "payload": {"url": "https://example.test/new"},
            "revision": 1,
        },
        supersedes="src-old",
        reason="Newer Baltic week",
    )
    assert session.artifacts["src-old"]["status"] == "superseded"
    assert session.artifacts["src-old"]["superseded_by"] == "src-new"
    assert session.artifacts["src-new"]["status"] == "active"


def test_prints_chart_groups_multiple_series() -> None:
    chart = prints_chart(
        [
            {"t": "2026-09-01", "v": 3500, "series": "BDI"},
            {"t": "2026-09-08", "v": 3584, "series": "BDI"},
            {"t": "2026-09-01", "v": 28000, "series": "Capesize 5TC"},
            {"t": "2026-09-08", "v": 31000, "series": "Capesize 5TC"},
        ]
    )
    series = chart["payload"]["series"]
    names = {item["name"] for item in series}
    assert names == {"BDI", "Capesize 5TC"}
    bdi = next(item for item in series if item["name"] == "BDI")
    assert [pt["y"] for pt in bdi["points"]] == [3500, 3584]


def test_normalize_report_blocks_coerces_unknown_and_tables() -> None:
    blocks = normalize_report_blocks(
        [
            "Plain sentence.",
            {"type": "unknown", "text": "Fallback prose."},
            {
                "type": "table",
                "columns": ["date", "value"],
                "rows": [{"date": "2026-09-08", "value": 3584}],
            },
            {
                "type": "chart",
                "variant": "bar",
                "series": [{"name": "BDI", "data": [["Mon", 3584], ["Tue", 3575]]}],
            },
            {
                "type": "expand",
                "title": "Method",
                "blocks": [{"type": "markdown", "text": "Hellenic RSS plus Exa."}],
            },
        ]
    )
    types = [item["type"] for item in blocks]
    assert types == ["markdown", "markdown", "table", "chart", "expand"]
    assert blocks[2]["columns"][0] == {"key": "date", "label": "date"}
    assert blocks[3]["variant"] == "bar"
    assert blocks[3]["series"][0]["points"][0]["y"] == 3584
    assert blocks[4]["blocks"][0]["type"] == "markdown"


def test_desk_prompt_asks_for_generative_report() -> None:
    assert "present_report" in DESK_SYSTEM_PROMPT
    assert "source cards" not in DESK_SYSTEM_PROMPT.lower()
    assert "present_table" not in DESK_SYSTEM_PROMPT


def test_present_report_upserts_main_artifact(settings, monkeypatch) -> None:
    monkeypatch.setattr("freight_second_brain.agent.session.build_research_agent", lambda **_kwargs: object())
    desk = ResearchDesk(settings=settings)
    session = desk.create_session()
    desk_token = _current_desk.set(desk)
    session_token = _current_session_id.set(session.session_id)
    try:
        tools = {tool.name: tool for tool in desk._ui_tools()}
        assert set(tools) == {"present_report"}
        payload = tools["present_report"].invoke(
            {
                "title": "Session BDI",
                "subtitle": "as_of 2026-09-10 · horizon session/week",
                "blocks_json": json.dumps(
                    [
                        {"type": "kpis", "items": [{"label": "BDI", "value": "3,584", "caption": "8 Sep"}]},
                        {"type": "markdown", "text": "Cape and Panamax split below."},
                    ]
                ),
            }
        )
    finally:
        _current_desk.reset(desk_token)
        _current_session_id.reset(session_token)
    result = json.loads(payload)
    assert result["ok"] is True
    report = session.artifacts["report-main"]
    assert report["kind"] == "report"
    assert report["title"] == "Session BDI"
    assert session.show_report is True
    assert [block["type"] for block in report["payload"]["blocks"]] == ["kpis", "markdown"]
    assert session.snapshot()["show_report"] is True
