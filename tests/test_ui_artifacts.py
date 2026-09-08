from freight_second_brain.agent.artifacts import extract_bdi_print, materialize_from_tool, prints_chart
from freight_second_brain.agent.session import ResearchSession


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
