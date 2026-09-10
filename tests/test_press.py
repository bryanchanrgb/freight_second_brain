import json

import pytest

from freight_second_brain.tools.press import press_catalog, press_fetch
from freight_second_brain.tools.registry import ToolRegistry
from freight_second_brain.warehouse.store import Warehouse


def test_press_catalog_lists_wp_sites() -> None:
    out = press_catalog()
    ids = [row["id"] for row in out["sites"]]
    assert ids == ["hellenic", "splash", "telegraph", "gcaptain"]
    for row in out["sites"]:
        assert row["default_category"] == "all"
        assert "all" in row["categories"]
        assert "all" in row["category_guide"]
    hellenic = next(row for row in out["sites"] if row["id"] == "hellenic")
    assert "date_range" in hellenic["supports"]
    assert "BDI" in hellenic["category_guide"]["dry-bulk"]
    assert hellenic["categories"]["dry-bulk"] == 122
    assert "weekly-brokers" in hellenic["categories"]
    telegraph = next(row for row in out["sites"] if row["id"] == "telegraph")
    assert telegraph["categories"]["freight-news"] == 118
    assert "IC Shipbrokers" in telegraph["category_guide"]["freight-news"]
    splash = next(row for row in out["sites"] if row["id"] == "splash")
    assert splash["categories"]["dry-cargo"] == 57
    gcaptain = next(row for row in out["sites"] if row["id"] == "gcaptain")
    assert "Baltic Dry" in gcaptain["note"] or "Capesize" in gcaptain["note"]


def test_press_fetch_rejects_unknown_site() -> None:
    with pytest.raises(ValueError, match="unknown site"):
        press_fetch("lloyds", query="Capesize")


def test_press_fetch_wp_search_and_range(monkeypatch) -> None:
    captured: dict = {}

    def fake_http_get(url, *, headers=None, timeout=60.0):
        captured["url"] = url
        body = json.dumps(
            [
                {
                    "id": 1,
                    "date_gmt": "2026-09-08T12:00:00",
                    "link": "https://www.hellenicshippingnews.com/bdi-3584/",
                    "title": {"rendered": "Baltic Dry Index climbs to 3584"},
                    "excerpt": {"rendered": "<p>The Baltic Dry Index climbed 9 points, 3584 points.</p>"},
                }
            ]
        )
        return 200, {"x-wp-total": "17", "x-wp-totalpages": "2"}, body

    monkeypatch.setattr("freight_second_brain.tools.press.http_get", fake_http_get)
    out = press_fetch(
        "hellenic",
        query="Baltic Dry",
        after="2026-09-01",
        before="2026-09-10",
        limit=5,
    )
    assert "search=Baltic" in captured["url"]
    assert "after=2026-09-01T00%3A00%3A00" in captured["url"]
    assert "categories=" not in captured["url"]
    assert out["category"] == "all"
    assert out["default_category"] == "all"
    assert "BDI" in out["category_guide"]["dry-bulk"]
    assert out["total"] == 17
    assert out["entries"][0]["title"].startswith("Baltic Dry")
    assert "3584" in out["entries"][0]["summary"]
    assert out["entries"][0]["url"].endswith("/bdi-3584/")


def test_registry_exposes_press_tools(settings) -> None:
    registry = ToolRegistry(Warehouse(settings))
    names = {spec["name"] for spec in registry.list_tools()}
    assert {"press_catalog", "press_fetch"} <= names
    listed = registry.call("press_catalog")
    assert listed.ok
    assert [row["id"] for row in listed.data["sites"]] == [
        "hellenic",
        "splash",
        "telegraph",
        "gcaptain",
    ]
    blocked = registry.call("press_fetch", site="drewry")
    assert not blocked.ok
    fetch = next(spec for spec in registry.list_tools() if spec["name"] == "press_fetch")
    cat_desc = fetch["parameters"]["properties"]["category"]["description"]
    assert "Defaults to all" in cat_desc
    assert "dry-bulk (BDI composite color)" in cat_desc
    assert "IC Shipbrokers" in cat_desc
    assert "Do not call press_catalog first" in fetch["description"]
    catalog = next(spec for spec in registry.list_tools() if spec["name"] == "press_catalog")
    assert "do not call this first" in catalog["description"].lower()
    market = next(spec for spec in registry.list_tools() if spec["name"] == "market_feed")
    assert "Skip it unless you need a live alias check" in market["description"]


def test_press_fetch_default_all_and_pinned_desks(monkeypatch) -> None:
    captured: list[str] = []

    def fake_http_get(url, *, headers=None, timeout=60.0):
        captured.append(url)
        return 200, {}, "[]"

    monkeypatch.setattr("freight_second_brain.tools.press.http_get", fake_http_get)
    telegraph = press_fetch("telegraph", query="Capesize", after="2026-09-01", limit=4)
    assert telegraph["site"] == "telegraph"
    assert telegraph["category"] == "all"
    assert "categories=" not in captured[0]
    assert "search=Capesize" in captured[0]

    pinned = press_fetch("hellenic", category="dry-bulk", limit=4)
    assert pinned["category"] == "dry-bulk"
    assert "categories=122" in captured[1]

    freight = press_fetch("telegraph", category="freight-news", limit=4)
    assert freight["category"] == "freight-news"
    assert "categories=118" in captured[2]

    gcaptain = press_fetch("gcaptain", query="Baltic Dry", limit=4)
    assert gcaptain["site"] == "gcaptain"
    assert gcaptain["category"] == "all"
    assert "categories=" not in captured[3]
    assert "search=Baltic" in captured[3]
