import pytest

from freight_second_brain.agent.artifacts import materialize_from_tool
from freight_second_brain.tools.market import (
    _history_route,
    market_feed,
    resolve_code,
)
from freight_second_brain.tools.registry import DEPLOYABLE_TOOL_NAMES, ToolRegistry
from freight_second_brain.warehouse.store import Warehouse


def test_deployable_agent_binds_market_feed() -> None:
    assert "market_feed" in DEPLOYABLE_TOOL_NAMES
    assert "rss_feed" not in DEPLOYABLE_TOOL_NAMES


def test_resolve_aliases() -> None:
    assert resolve_code("bdi") == "BALTIC_DRY_INDEX"
    assert resolve_code("BCI") == "BALTIC_CAPESIZE_INDEX"
    assert resolve_code("iron_ore") == "IRON_ORE_USD"
    assert resolve_code("coal") == "NEWCASTLE_COAL_USD"
    assert resolve_code("BALTIC_DRY_INDEX") == "BALTIC_DRY_INDEX"
    with pytest.raises(ValueError, match="unknown series"):
        resolve_code("not a ticker!")


def test_history_route_prefers_free_windows() -> None:
    assert _history_route(start=None, end=None, past=None) == ("/prices/past_month", {"interval": "1d"})
    assert _history_route(start=None, end=None, past="7d")[0] == "/prices/past_week"
    assert _history_route(start=None, end=None, past="1y")[0] == "/prices/past_year"
    path, params = _history_route(start="2025-01-01", end="2025-06-01", past=None)
    assert path == "/prices/historical"
    assert params["start_date"] == "2025-01-01"
    assert params["interval"] == "daily"


def test_history_floor_1y_vs_5y() -> None:
    from datetime import date

    from freight_second_brain.tools.market import apply_history_floor

    today = date(2026, 9, 10)
    developer = apply_history_floor(
        start="2021-09-10",
        end="2026-09-10",
        past=None,
        history_available_from="2025-09-10",
        today=today,
    )
    assert developer["can_read_1y"] is True
    assert developer["can_read_5y"] is False
    assert developer["clipped"] is True
    assert developer["start"] == "2025-09-10"
    assert "5-year" in (developer["warning"] or "")

    starter = apply_history_floor(
        start="2021-09-10",
        end="2026-09-10",
        past=None,
        history_available_from="2021-09-10",
        today=today,
    )
    assert starter["can_read_1y"] is True
    assert starter["can_read_5y"] is True
    assert starter["clipped"] is False

    free = apply_history_floor(
        start=None,
        end=None,
        past="1y",
        history_available_from="2026-08-11",
        today=today,
    )
    assert free["can_read_1y"] is False
    assert free["can_read_5y"] is False
    assert free["clipped"] is True
    assert free["start"] == "2026-08-11"


def test_catalog_needs_no_key(settings) -> None:
    out = market_feed(action="catalog", settings=settings)
    assert out["ok"] is True
    codes = {row["code"] for row in out["series"]}
    assert {"BALTIC_DRY_INDEX", "BALTIC_CAPESIZE_INDEX", "IRON_ORE_USD", "NEWCASTLE_COAL_USD"} <= codes
    assert out["default_latest"] == ["bdi", "bci"]
    assert "empty_window" in out["history_notes"]
    assert "not a licensed baltic" in out["disclaimer"].lower()
    assert "cannot read 1-year or 5-year" in out["history_notes"]


def test_latest_requires_token(settings) -> None:
    blank = settings.model_copy(update={"oilprice_api_token": ""})
    with pytest.raises(RuntimeError, match="OILPRICE_API_TOKEN"):
        market_feed(action="latest", settings=blank)


def test_latest_batches_codes(monkeypatch, settings) -> None:
    captured: dict = {}

    def fake_request(path, params, token, timeout=30.0):
        captured["path"] = path
        captured["params"] = params
        captured["token"] = token
        return (
            200,
            {
                "status": "success",
                "data": {
                    "prices": [
                        {
                            "code": "BALTIC_DRY_INDEX",
                            "price": 3620,
                            "formatted": "3620",
                            "as_of": "2026-09-09T12:00:00Z",
                            "unit": "index",
                        },
                        {
                            "code": "BALTIC_CAPESIZE_INDEX",
                            "price": 6400,
                            "as_of": "2026-09-09T12:00:00Z",
                            "unit": "index",
                        },
                    ]
                },
            },
            {},
        )

    monkeypatch.setattr("freight_second_brain.tools.market._request", fake_request)
    keyed = settings.model_copy(update={"oilprice_api_token": "tok_test"})
    out = market_feed(action="latest", settings=keyed)
    assert captured["path"] == "/prices/latest"
    assert captured["token"] == "tok_test"
    assert "BALTIC_DRY_INDEX" in captured["params"]["by_code"]
    assert "BALTIC_CAPESIZE_INDEX" in captured["params"]["by_code"]
    assert out["latest"]["BALTIC_DRY_INDEX"]["value"] == 3620.0
    assert out["latest"]["BALTIC_DRY_INDEX"]["date"] == "2026-09-09"
    assert out["latest"]["BALTIC_DRY_INDEX"]["alias"] == "BDI"


def test_history_uses_past_month(monkeypatch, settings) -> None:
    captured: dict = {}

    def fake_request(path, params, token, timeout=30.0):
        captured["path"] = path
        captured["params"] = params
        if path.startswith("/commodities/"):
            return (
                200,
                {
                    "status": "success",
                    "data": {
                        "your_access": {
                            "history_available_from": "2025-09-10",
                            "note": "1-year history",
                        }
                    },
                },
                {},
            )
        return (
            200,
            {
                "status": "success",
                "data": {
                    "prices": [
                        {
                            "code": "BALTIC_DRY_INDEX",
                            "price": 3500,
                            "created_at": "2026-08-12T00:00:00Z",
                        },
                        {
                            "code": "BALTIC_DRY_INDEX",
                            "price": 3620,
                            "created_at": "2026-09-09T00:00:00Z",
                        },
                    ]
                },
            },
            {},
        )

    monkeypatch.setattr("freight_second_brain.tools.market._ACCESS_CACHE", {})
    monkeypatch.setattr("freight_second_brain.tools.market._request", fake_request)
    keyed = settings.model_copy(update={"oilprice_api_token": "tok_test"})
    out = market_feed(action="history", codes="bdi", settings=keyed)
    assert captured["path"] == "/prices/past_month"
    assert captured["params"]["interval"] == "1d"
    assert captured["params"]["by_code"] == "BALTIC_DRY_INDEX"
    assert [row["value"] for row in out["rows"]] == [3500.0, 3620.0]
    assert out["latest"]["BALTIC_DRY_INDEX"]["date"] == "2026-09-09"
    assert out["can_read_1y"] is True
    assert out["can_read_5y"] is False


def test_history_clips_five_year_on_one_year_plan(monkeypatch, settings) -> None:
    captured: dict = {}

    def fake_request(path, params, token, timeout=30.0):
        captured["path"] = path
        captured["params"] = params
        if path.startswith("/commodities/"):
            return (
                200,
                {
                    "status": "success",
                    "data": {"your_access": {"history_available_from": "2025-09-10"}},
                },
                {},
            )
        return (
            200,
            {
                "status": "success",
                "data": {
                    "prices": [
                        {
                            "code": "BALTIC_DRY_INDEX",
                            "price": 2000,
                            "created_at": "2025-09-10T00:00:00Z",
                        }
                    ]
                },
            },
            {},
        )

    monkeypatch.setattr("freight_second_brain.tools.market._ACCESS_CACHE", {})
    monkeypatch.setattr("freight_second_brain.tools.market._request", fake_request)
    keyed = settings.model_copy(update={"oilprice_api_token": "tok_test"})
    out = market_feed(
        action="history",
        codes="bdi",
        start="2021-09-10",
        end="2026-09-10",
        settings=keyed,
    )
    assert captured["path"] == "/prices/historical"
    assert captured["params"]["start_date"] == "2025-09-10"
    assert out["clipped"] is True
    assert out["can_read_5y"] is False
    assert "5-year" in (out["warning"] or "")


def test_history_surfaces_empty_window(monkeypatch, settings) -> None:
    def fake_request(path, params, token, timeout=30.0):
        if path.startswith("/commodities/"):
            return 200, {"status": "success", "data": {"your_access": {"history_available_from": None, "note": "full"}}}, {}
        return (
            200,
            {
                "status": "success",
                "data": {
                    "prices": [],
                    "availability": {
                        "missing": [
                            {
                                "code": "BALTIC_DRY_INDEX",
                                "reason": "empty_window",
                                "message": "BALTIC_DRY_INDEX has price history, but no rows matched the requested window.",
                            }
                        ]
                    },
                },
            },
            {},
        )

    monkeypatch.setattr("freight_second_brain.tools.market._ACCESS_CACHE", {})
    monkeypatch.setattr("freight_second_brain.tools.market._request", fake_request)
    keyed = settings.model_copy(update={"oilprice_api_token": "tok_test"})
    out = market_feed(action="history", codes="bdi", start="2021-09-08", end="2021-09-12", settings=keyed)
    assert out["row_count"] == 0
    assert out["missing"][0]["reason"] == "empty_window"
    assert "no rows matched" in (out["empty_window"] or "")


def test_invalid_code_retries_confirmed(monkeypatch, settings) -> None:
    calls: list[str] = []

    def fake_request(path, params, token, timeout=30.0):
        calls.append(params["by_code"])
        if "BALTIC_PANAMAX_INDEX" in params["by_code"]:
            return 400, {"status": "fail", "data": {"error": "invalid_code"}}, {}
        return (
            200,
            {
                "status": "success",
                "data": {
                    "prices": [
                        {
                            "code": "BALTIC_DRY_INDEX",
                            "price": 3620,
                            "as_of": "2026-09-09T12:00:00Z",
                        }
                    ]
                },
            },
            {},
        )

    monkeypatch.setattr("freight_second_brain.tools.market._request", fake_request)
    keyed = settings.model_copy(update={"oilprice_api_token": "tok_test"})
    out = market_feed(action="latest", codes="bdi,bpi", settings=keyed)
    assert calls[0] == "BALTIC_DRY_INDEX,BALTIC_PANAMAX_INDEX"
    assert "BALTIC_PANAMAX_INDEX" not in calls[1]
    assert out["skipped"] == ["BALTIC_PANAMAX_INDEX"]
    assert out["latest"]["BALTIC_DRY_INDEX"]["value"] == 3620.0


def test_registry_catalog_and_missing_key(settings) -> None:
    blank = settings.model_copy(update={"oilprice_api_token": ""})
    registry = ToolRegistry(Warehouse(blank))
    listed = registry.call("market_feed", action="catalog")
    assert listed.ok
    spec = next(item for item in registry.list_tools() if item["name"] == "market_feed")
    assert "empty_window" in spec["description"]
    assert "HISTORY LIMIT" in spec["description"]
    assert listed.data["action"] == "catalog"
    missing = registry.call("market_feed", action="latest")
    assert missing.ok is False
    assert "OILPRICE_API_TOKEN" in (missing.error or "")


def test_materialize_market_feed_cards() -> None:
    cards, points = materialize_from_tool(
        "market_feed",
        {
            "latest": {
                "BALTIC_DRY_INDEX": {
                    "code": "BALTIC_DRY_INDEX",
                    "alias": "BDI",
                    "name": "Baltic Dry Index",
                    "date": "2026-09-09",
                    "value": 3620,
                    "formatted": "3620",
                    "cite_url": "https://www.oilpriceapi.com/live/baltic-dry-index",
                    "as_of": "2026-09-09T12:00:00Z",
                },
                "BALTIC_CAPESIZE_INDEX": {
                    "code": "BALTIC_CAPESIZE_INDEX",
                    "alias": "BCI",
                    "name": "Baltic Capesize Index",
                    "date": "2026-09-09",
                    "value": 6400,
                    "cite_url": "https://www.oilpriceapi.com/live/baltic-capesize-index",
                },
            }
        },
    )
    assert len(cards) == 2
    assert cards[0]["payload"]["print"] == 3620
    assert {point["series"] for point in points} == {"BDI", "BCI"}
