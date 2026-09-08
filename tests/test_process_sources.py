from datetime import date

from freight_second_brain.agent.artifacts import new_artifact, source_card_from_web_hit
from freight_second_brain.agent.process_sources import pretty_url, process_source_cards


def test_pretty_url_strips_www_and_slug() -> None:
    pretty = pretty_url(
        "https://www.hellenicshippingnews.com/baltic-dry-index-climbs-to-3584-up-9-points/"
    )
    assert pretty["host"] == "hellenicshippingnews.com"
    assert "baltic dry index" in pretty["path"].lower()
    assert pretty["url"].startswith("https://")


def _card(title: str, url: str, snippet: str, published: str, origin_turn: int = 1) -> dict:
    hit = source_card_from_web_hit(
        {"title": title, "url": url, "summary": snippet, "published": published},
        tool="rss_feed",
    )
    assert hit is not None
    payload = dict(hit["payload"])
    payload["origin_turn"] = origin_turn
    return {**hit, "payload": payload}


def test_process_groups_syndicated_daily_prints() -> None:
    published = "Tue, 08 Sep 2026 12:00:56 +0000"
    cards = [
        _card(
            "Baltic Dry Index climbs to 3584 up 9 points",
            "https://www.hellenicshippingnews.com/baltic-dry-index-climbs-to-3584-up-9-points/",
            "Today the Baltic Dry Index climbed 9 points, reaching 3584 points.",
            published,
            origin_turn=1,
        ),
        _card(
            "Baltic Dry Index climbs to 3584 points",
            "https://www.thedcn.com.au/news/bulk-exports/baltic-dry-index-climbs-to-3584/",
            "The Baltic Dry Index climbed to 3584 points.",
            published,
            origin_turn=2,
        ),
        _card(
            "Black Sea grain corridor lifts Handy rates",
            "https://www.hellenicshippingnews.com/black-sea-grain-corridor-handy/",
            "Russian wheat shipments supported Handysize.",
            published,
            origin_turn=2,
        ),
        _card(
            "Hapag-Lloyd raises container rates as SCFI jumps",
            "https://example.test/hapag-scfi",
            "Container shipping market tightened.",
            published,
        ),
    ]
    processed = process_source_cards(cards, origin_turn=2, as_of=date(2026, 9, 9))
    urls = {item["payload"]["url"] for item in processed}
    assert not any("hapag" in url for url in urls)

    groups: dict[str, list[dict]] = {}
    for item in processed:
        groups.setdefault(item["payload"]["independence_group"], []).append(item)

    daily = next(g for g in groups.values() if any(c["payload"].get("print") == 3584 for c in g))
    assert len(daily) == 2
    hierarchies = {c["payload"]["hierarchy"] for c in daily}
    assert hierarchies == {"primary", "duplicate"}
    primary = next(c for c in daily if c["payload"]["hierarchy"] == "primary")
    assert "BDI 3,584" in primary["payload"]["one_liner"]
    assert primary["payload"]["origin_turn"] == 1

    overlay = next(c for c in processed if c["payload"]["role"] == "overlay")
    assert overlay["payload"]["hierarchy"] == "primary"
    assert "overlay" in overlay["payload"]["one_liner"].lower()
    assert "provenance:overlay" in overlay["payload"]["tag_ids"]
    assert "claim_type:observation" in primary["payload"]["tag_ids"]


def test_process_preserves_existing_origin_turn() -> None:
    card = new_artifact(
        object_id="src-old",
        kind="source_card",
        title="Baltic Dry Index climbs to 3575 up 4 points",
        payload={
            "url": "https://www.hellenicshippingnews.com/bdi-3575/",
            "snippet": "The Baltic Dry Index climbed to 3575 points.",
            "published": "Mon, 07 Sep 2026 12:00:00 +0000",
            "origin_turn": 1,
        },
    )
    processed = process_source_cards([card], origin_turn=3)
    assert processed[0]["payload"]["origin_turn"] == 1
    assert processed[0]["payload"]["pretty_host"] == "hellenicshippingnews.com"
