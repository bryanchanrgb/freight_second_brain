from datetime import date

from freight_second_brain.agent.artifacts import new_artifact
from freight_second_brain.agent.process_sources import process_source_cards
from freight_second_brain.agent.source_tags import classify_source, coerce_override


AS_OF = date(2026, 9, 9)


def test_classify_daily_bdi_print() -> None:
    tagged = classify_source(
        title="Baltic Dry Index climbs to 3584 up 9 points",
        url="https://www.hellenicshippingnews.com/baltic-dry-index-climbs-to-3584-up-9-points/",
        snippet="Today the Baltic Dry Index climbed 9 points, reaching 3584 points.",
        published="Tue, 08 Sep 2026 12:00:56 +0000",
        host="hellenicshippingnews.com",
        role="reprint",
        hierarchy="primary",
        print_value=3584,
        tool="rss_feed",
        as_of=AS_OF,
    )
    assert tagged["claim_type"] == "observation"
    assert tagged["polarity"] == "bullish"
    assert tagged["freshness"] == "current"
    assert tagged["medium"] == "rss"
    assert tagged["provenance"] == "secondary"
    assert tagged["hierarchy"] == "primary"
    assert "claim_type:observation" in tagged["tag_ids"]
    assert "polarity:bullish" in tagged["tag_ids"]


def test_classify_unctad_as_historical_research() -> None:
    tagged = classify_source(
        title="Review of Maritime Transport 2025 chapter 3",
        url="https://unctad.org/system/files/official-document/rmt2025ch3_en.pdf",
        snippet="Dry bulk rates remained under pressure in 2024.",
        published="2025-10-01",
        host="unctad.org",
        role="primary",
        print_value=None,
        tool="fetch_url",
        as_of=AS_OF,
    )
    assert tagged["freshness"] == "historical_vintage"
    assert tagged["medium"] == "pdf"
    assert tagged["channel"] == "research"
    assert tagged["claim_type"] in {"explanation", "forecast"}


def test_coerce_aliases() -> None:
    assert coerce_override("claim_type", "fact") == "observation"
    assert coerce_override("claim_type", "analysis") == "explanation"
    assert coerce_override("claim_type", "prediction") == "forecast"
    assert coerce_override("freshness", "historical") == "historical_vintage"
    assert coerce_override("polarity", "hot") is None


def test_agent_override_survives_refresh() -> None:
    card = new_artifact(
        object_id="src-smoo",
        kind="source_card",
        title="BIMCO SMOO July 2026 dry bulk",
        payload={
            "url": "https://www.maritimecyprus.com/bimco-smoo-july-2026.pdf",
            "snippet": "Supply-demand still supportive in 2026.",
            "published": "2026-07-31",
            "classified_by": "agent",
            "claim_type": "forecast",
            "polarity": "mixed",
            "freshness": "recent",
        },
        provenance={"tool": "fetch_url"},
    )
    processed = process_source_cards([card], origin_turn=1, as_of=AS_OF)
    payload = processed[0]["payload"]
    assert payload["claim_type"] == "forecast"
    assert payload["polarity"] == "mixed"
    assert payload["classified_by"] == "agent"
    assert "claim_type:forecast" in payload["tag_ids"]
