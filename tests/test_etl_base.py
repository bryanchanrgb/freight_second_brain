from datetime import date

from freight_second_brain.etl.extractors.base import (
    infer_commodity,
    infer_vessel_class,
    observation_id,
    parse_month_token,
    slug,
    to_float,
)
from freight_second_brain.etl.extractors import EXTRACTORS


def test_slug_normalizes_and_falls_back() -> None:
    assert slug("Coal, Australian") == "coal_australian"
    assert slug("   ") == "unknown"


def test_parse_month_token_formats() -> None:
    assert parse_month_token("1960M01") == date(1960, 1, 1)
    assert parse_month_token("2024-08") == date(2024, 8, 1)
    assert parse_month_token("202401") == date(2024, 1, 1)
    assert parse_month_token("2024") == date(2024, 1, 1)
    assert parse_month_token("202413") is None
    assert parse_month_token("not-a-date") is None


def test_to_float_skips_sentinels() -> None:
    assert to_float(1.5) == 1.5
    assert to_float("3,575.00") == 3575.0
    assert to_float("…") is None
    assert to_float("NA") is None
    assert to_float("abc") is None
    assert to_float(float("nan")) is None


def test_infer_commodity_and_vessel_class() -> None:
    assert infer_commodity("Iron ore, cfr spot") == "iron_ore"
    assert infer_commodity("Coal, Australian") == "coal"
    assert infer_commodity("platinum") is None
    assert infer_vessel_class("Baltic Capesize Index") == "capesize"
    assert infer_vessel_class("BPI daily") == "panamax"
    assert infer_vessel_class("BSI") == "supramax"
    assert infer_vessel_class("BHSI") == "handysize"
    assert infer_vessel_class("container ship") is None


def test_observation_id_is_stable_and_vintage_sensitive() -> None:
    first = observation_id("src", "SERIES", date(2020, 1, 1))
    assert first == observation_id("src", "SERIES", date(2020, 1, 1))
    assert first != observation_id("src", "SERIES", date(2020, 1, 1), "v2")
    assert len(first) == 16


def test_extractor_registry_covers_named_classes() -> None:
    assert set(EXTRACTORS) >= {
        "world_bank_pink_sheet",
        "world_bank_api",
        "fao_fpi",
        "usda_psd",
        "comtrade",
        "mendeley_bdi",
        "yahoo_finance",
        "noaa_enso",
        "data360_maritime",
        "eia_coal",
        "hellenic_rss",
        "trading_economics_bdi",
        "qualitative_pages",
    }
    for name, cls in EXTRACTORS.items():
        assert cls.name == name
